"""Generate ~50 multi-hop questions from the live graph (read-only).

Example:
    python -m benchmark.generate_questions --count 50 --output benchmark/questions.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from benchmark.graph_questions import generate_questions
from benchmark.models import Edge, Node

ENTITIES_QUERY = """
MATCH (e:Entity)
RETURN e.id AS id, e.name AS name, e.type AS type
ORDER BY e.id
"""

EDGES_QUERY = """
MATCH (a:Entity)-[r:RELATION]->(b:Entity)
RETURN a.id AS source, b.id AS target, r.type AS type, r.detail AS detail
ORDER BY a.id, b.id, r.type
"""


def load_graph() -> tuple[list[Node], list[Edge]]:
    # Imported lazily: importing graph.neo4j_client constructs a driver and
    # validates environment configuration at import time.
    from graph.neo4j_client import neo4j_client

    entity_rows = neo4j_client.run_query(ENTITIES_QUERY)
    edge_rows = neo4j_client.run_query(EDGES_QUERY)

    nodes = [
        Node(
            id=str(row["id"]),
            name=str(row.get("name") or row["id"]),
            type=str(row.get("type") or "Entity"),
        )
        for row in entity_rows
        if row.get("id")
    ]
    edges = [
        Edge(
            source=str(row["source"]),
            target=str(row["target"]),
            type=str(row.get("type") or "RELATED"),
            detail=row.get("detail"),
        )
        for row in edge_rows
        if row.get("source") and row.get("target")
    ]
    return nodes, edges


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=50, help="Number of questions (default: 50)")
    parser.add_argument("--seed", type=int, default=7, help="Deterministic sampling seed")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmark/questions.jsonl"),
        help="Output JSONL path",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the output file if it already exists",
    )
    args = parser.parse_args()

    if args.output.exists() and not args.force:
        print(
            f"Refusing to overwrite {args.output}. Pass --force to replace it.",
            file=sys.stderr,
        )
        return 1

    nodes, edges = load_graph()
    if not nodes:
        print("No :Entity nodes were found in Neo4j. Ingest a document first.", file=sys.stderr)
        return 1

    try:
        questions = generate_questions(nodes, edges, count=args.count, seed=args.seed)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for question in questions:
            handle.write(json.dumps(question.to_json(), ensure_ascii=False) + "\n")

    type_counts: dict[str, int] = {}
    for question in questions:
        type_counts[question.question_type] = type_counts.get(question.question_type, 0) + 1
    print(f"Wrote {len(questions)} questions to {args.output}")
    print("Question types: " + ", ".join(f"{key}={value}" for key, value in sorted(type_counts.items())))
    print("No entity names or answers were printed to this terminal.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
