"""Deterministic multi-hop question generation from a property graph.

The generator is pure: it receives nodes and edges, never touches a database,
and therefore can be unit-tested with a fixture. The CLI in
``generate_questions.py`` is the only part that reads Neo4j, and it uses a
read-only query.

Questions are deliberately structural. They are derived from the operator's
own graph at run time rather than shipped with private entity names, and every
gold answer/evidence item is computed from the graph rather than authored by a
model.
"""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass

from benchmark.models import BenchmarkQuestion, Edge, Node

TYPE_ORDER = (
    "common_neighbor",
    "bridge_path",
    "two_hop_type",
    "relationship_chain",
    "exact_two_hop_count",
    "mutual_neighbor_type",
    "two_hop_relationship_type",
)


@dataclass(frozen=True)
class _Candidate:
    question_type: str
    question: str
    answer: str
    answer_aliases: tuple[str, ...]
    evidence: tuple[str, ...]
    hops: int


def _clean(name: str) -> str:
    return " ".join(name.replace('"', "'").split())


def _adjacency(nodes: list[Node], edges: list[Edge]) -> dict[str, set[str]]:
    adjacency = {node.id: set() for node in nodes}
    for edge in edges:
        if edge.source == edge.target:
            continue
        if edge.source in adjacency and edge.target in adjacency:
            adjacency[edge.source].add(edge.target)
            adjacency[edge.target].add(edge.source)
    return adjacency


def _outgoing(nodes: list[Node], edges: list[Edge]) -> dict[str, list[Edge]]:
    outgoing: dict[str, list[Edge]] = {node.id: [] for node in nodes}
    for edge in edges:
        if edge.source == edge.target:
            continue
        if edge.source in outgoing and edge.target in outgoing:
            outgoing[edge.source].append(edge)
    return outgoing


def _distances(start: str, adjacency: dict[str, set[str]]) -> dict[str, int]:
    distance = {start: 0}
    queue: deque[str] = deque([start])
    while queue:
        current = queue.popleft()
        for neighbour in adjacency.get(current, set()):
            if neighbour not in distance:
                distance[neighbour] = distance[current] + 1
                queue.append(neighbour)
    return distance


def _common(adjacency: dict[str, set[str]], left: str, right: str) -> set[str]:
    return adjacency.get(left, set()) & adjacency.get(right, set())


def _common_neighbour_candidates(
    nodes: list[Node],
    adjacency: dict[str, set[str]],
    bridge_only: bool,
) -> list[_Candidate]:
    by_id = {node.id: node for node in nodes}
    candidates: list[_Candidate] = []
    for centre in sorted(by_id):
        neighbours = sorted(adjacency.get(centre, set()))
        for index, left in enumerate(neighbours):
            for right in neighbours[index + 1 :]:
                if left == right:
                    continue
                adjacent = right in adjacency.get(left, set())
                if bridge_only and adjacent:
                    continue
                if not bridge_only and not adjacent:
                    continue
                if _common(adjacency, left, right) != {centre}:
                    continue
                centre_node = by_id[centre]
                left_node = by_id[left]
                right_node = by_id[right]
                if centre_node.name in (left_node.name, right_node.name):
                    continue
                if bridge_only:
                    question = (
                        f'Which entity lies on the only two-hop relationship path between '
                        f'"{_clean(left_node.name)}" and "{_clean(right_node.name)}"?'
                    )
                    question_type = "bridge_path"
                else:
                    question = (
                        f'Which entity is directly connected to both '
                        f'"{_clean(left_node.name)}" and "{_clean(right_node.name)}"?'
                    )
                    question_type = "common_neighbor"
                candidates.append(
                    _Candidate(
                        question_type=question_type,
                        question=question,
                        answer=centre_node.name,
                        answer_aliases=(centre_node.id,),
                        evidence=(centre_node.name,),
                        hops=2,
                    )
                )
    return candidates


def _two_hop_type_candidates(
    nodes: list[Node], adjacency: dict[str, set[str]]
) -> list[_Candidate]:
    by_id = {node.id: node for node in nodes}
    candidates: list[_Candidate] = []
    for company in sorted(nodes, key=lambda item: item.id):
        if company.type != "Company":
            continue
        distance = _distances(company.id, adjacency)
        two_hop = [node for node in nodes if distance.get(node.id) == 2]
        for entity_type in sorted({node.type for node in two_hop}):
            typed = [node for node in two_hop if node.type == entity_type]
            if len(typed) != 1:
                continue
            target = typed[0]
            candidates.append(
                _Candidate(
                    question_type="two_hop_type",
                    question=(
                        f'Which {entity_type} is reachable from "{_clean(company.name)}" '
                        f'in exactly two relationship hops?'
                    ),
                    answer=target.name,
                    answer_aliases=(target.id,),
                    evidence=(target.name,),
                    hops=2,
                )
            )
    return candidates


def _relationship_chain_candidates(
    nodes: list[Node], edges: list[Edge], outgoing: dict[str, list[Edge]]
) -> list[_Candidate]:
    by_id = {node.id: node for node in nodes}
    candidates: list[_Candidate] = []
    ordered_edges = sorted(edges, key=lambda item: (item.source, item.target, item.type))
    for first in ordered_edges:
        if first.source == first.target:
            continue
        first_matches = [
            edge
            for edge in outgoing.get(first.source, [])
            if edge.type == first.type
        ]
        if len(first_matches) != 1:
            continue
        second_matches = [
            edge for edge in outgoing.get(first.target, []) if edge.type != first.type
        ]
        # Only continue when the second hop is unambiguous for its type.
        for second in second_matches:
            if second.source == second.target:
                continue
            if second.target in (first.source, first.target):
                continue
            same_type = [
                edge
                for edge in outgoing.get(first.target, [])
                if edge.type == second.type
            ]
            if len(same_type) != 1:
                continue
            source = by_id[first.source]
            target = by_id[second.target]
            if target.name in (source.name, by_id[first.target].name):
                continue
            candidates.append(
                _Candidate(
                    question_type="relationship_chain",
                    question=(
                        f'Starting at "{_clean(source.name)}", which entity is reached after '
                        f'following the "{first.type}" relationship and then the '
                        f'"{second.type}" relationship?'
                    ),
                    answer=target.name,
                    answer_aliases=(target.id,),
                    evidence=(target.name,),
                    hops=2,
                )
            )
    return candidates


def _exact_two_hop_count_candidates(
    nodes: list[Node], adjacency: dict[str, set[str]]
) -> list[_Candidate]:
    candidates: list[_Candidate] = []
    for company in sorted(nodes, key=lambda item: item.id):
        if company.type != "Company":
            continue
        distance = _distances(company.id, adjacency)
        two_hop = [node for node in nodes if distance.get(node.id) == 2]
        for entity_type in sorted({node.type for node in two_hop}):
            typed = [node for node in two_hop if node.type == entity_type]
            if not 1 <= len(typed) <= 8:
                continue
            candidates.append(
                _Candidate(
                    question_type="exact_two_hop_count",
                    question=(
                        f'How many distinct {entity_type} entities are exactly two '
                        f'relationship hops from "{_clean(company.name)}"?'
                    ),
                    answer=str(len(typed)),
                    answer_aliases=(f"{len(typed)} {entity_type}",),
                    evidence=tuple(node.name for node in typed),
                    hops=2,
                )
            )
    return candidates


def _mutual_neighbor_type_candidates(
    nodes: list[Node], adjacency: dict[str, set[str]]
) -> list[_Candidate]:
    by_id = {node.id: node for node in nodes}
    candidates: list[_Candidate] = []
    for centre in sorted(by_id):
        neighbours = sorted(adjacency.get(centre, set()))
        for index, left in enumerate(neighbours):
            for right in neighbours[index + 1 :]:
                if left == right:
                    continue
                if right in adjacency.get(left, set()):
                    continue
                if _common(adjacency, left, right) != {centre}:
                    continue
                centre_node = by_id[centre]
                candidates.append(
                    _Candidate(
                        question_type="mutual_neighbor_type",
                        question=(
                            f'What type of entity is "{_clean(centre_node.name)}", which links '
                            f'"{_clean(by_id[left].name)}" and "{_clean(by_id[right].name)}"?'
                        ),
                        answer=centre_node.type,
                        answer_aliases=(),
                        evidence=(centre_node.name, centre_node.type),
                        hops=2,
                    )
                )
    return candidates


def _two_hop_relationship_type_candidates(
    nodes: list[Node], edges: list[Edge], outgoing: dict[str, list[Edge]]
) -> list[_Candidate]:
    by_id = {node.id: node for node in nodes}
    candidates: list[_Candidate] = []
    for source_id in sorted(outgoing):
        first_edges = outgoing[source_id]
        for first in first_edges:
            for second in outgoing.get(first.target, []):
                if second.target in (source_id, first.target):
                    continue
                # Require exactly one two-hop path from source to the destination,
                # otherwise the question has more than one valid answer.
                paths = 0
                for candidate_first in first_edges:
                    for candidate_second in outgoing.get(candidate_first.target, []):
                        if candidate_second.target == second.target:
                            paths += 1
                if paths != 1:
                    continue
                source = by_id[source_id]
                target = by_id[second.target]
                if target.name == source.name:
                    continue
                candidates.append(
                    _Candidate(
                        question_type="two_hop_relationship_type",
                        question=(
                            f'Starting at "{_clean(source.name)}", which two relationship '
                            f'types lead to "{_clean(target.name)}" in exactly two hops?'
                        ),
                        answer=f"{first.type} then {second.type}",
                        answer_aliases=(f"{first.type}, {second.type}",),
                        evidence=(first.type, second.type),
                        hops=2,
                    )
                )
    return candidates


def generate_questions(
    nodes: list[Node],
    edges: list[Edge],
    count: int = 50,
    seed: int = 7,
) -> list[BenchmarkQuestion]:
    if count < 1:
        raise ValueError("count must be positive")
    if not nodes:
        raise ValueError("No entities were supplied.")

    adjacency = _adjacency(nodes, edges)
    outgoing = _outgoing(nodes, edges)
    candidates = {
        "common_neighbor": _common_neighbour_candidates(nodes, adjacency, bridge_only=False),
        "bridge_path": _common_neighbour_candidates(nodes, adjacency, bridge_only=True),
        "two_hop_type": _two_hop_type_candidates(nodes, adjacency),
        "relationship_chain": _relationship_chain_candidates(nodes, edges, outgoing),
        "exact_two_hop_count": _exact_two_hop_count_candidates(nodes, adjacency),
        "mutual_neighbor_type": _mutual_neighbor_type_candidates(nodes, adjacency),
        "two_hop_relationship_type": _two_hop_relationship_type_candidates(
            nodes, edges, outgoing
        ),
    }

    rng = random.Random(seed)
    pools: dict[str, list[_Candidate]] = {}
    for question_type, items in candidates.items():
        deduped: dict[str, _Candidate] = {}
        for item in items:
            deduped.setdefault(" ".join(item.question.lower().split()), item)
        pool = sorted(deduped.values(), key=lambda item: item.question)
        rng.shuffle(pool)
        pools[question_type] = pool

    selected: list[_Candidate] = []
    seen: set[str] = set()
    while len(selected) < count:
        progressed = False
        for question_type in TYPE_ORDER:
            pool = pools[question_type]
            while pool:
                item = pool.pop()
                key = " ".join(item.question.lower().split())
                if key in seen:
                    continue
                seen.add(key)
                selected.append(item)
                progressed = True
                break
            if len(selected) >= count:
                break
        if not progressed:
            counts = {key: len(value) for key, value in candidates.items()}
            raise ValueError(
                f"The graph yielded only {len(selected)} distinct multi-hop questions; "
                f"{count} were requested. Candidate counts: {counts}. "
                "Ingest a document with more relationships, or lower --count."
            )

    return [
        BenchmarkQuestion(
            id=f"q{index + 1:03d}",
            question=item.question,
            answer=item.answer,
            answer_aliases=item.answer_aliases,
            evidence=item.evidence,
            hops=item.hops,
            question_type=item.question_type,
        )
        for index, item in enumerate(selected)
    ]
