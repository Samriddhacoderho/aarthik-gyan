from __future__ import annotations

import pytest

from benchmark.graph_questions import generate_questions
from benchmark.metrics import (
    answer_correct,
    evidence_recall,
    flatten_retrieval,
    normalize,
    retrieval_hit,
    summarize,
)
from benchmark.models import Edge, Node


def fixture_graph() -> tuple[list[Node], list[Edge]]:
    nodes = [
        Node("c1", "Alpha Industries", "Company"),
        Node("c2", "Beta Holdings", "Company"),
        Node("e1", "Asha Rai", "Executive"),
        Node("e2", "Bikash Menon", "Executive"),
        Node("e3", "Chen Li", "Executive"),
        Node("s1", "Alpha Parts", "Subsidiary"),
        Node("s2", "Beta Logistics", "Subsidiary"),
        Node("a1", "Doshi and Co", "Auditor"),
        Node("a2", "Mehta Audit", "Auditor"),
        Node("r1", "Currency Exposure", "RiskFactor"),
        Node("r2", "Supplier Concentration", "RiskFactor"),
        Node("r3", "Leverage Pressure", "RiskFactor"),
    ]
    edges = [
        Edge("c1", "e1", "EMPLOYS"),
        Edge("c1", "e2", "EMPLOYS"),
        Edge("c1", "s1", "OWNS"),
        Edge("c1", "a1", "AUDITED_BY"),
        Edge("c1", "r1", "FLAGGED_FOR"),
        Edge("c2", "e2", "EMPLOYS"),
        Edge("c2", "e3", "EMPLOYS"),
        Edge("c2", "s2", "OWNS"),
        Edge("c2", "a2", "AUDITED_BY"),
        Edge("c2", "r2", "FLAGGED_FOR"),
        Edge("s1", "r3", "FLAGGED_FOR"),
        Edge("s2", "r3", "FLAGGED_FOR"),
        Edge("a1", "r1", "FLAGGED_FOR"),
        Edge("a2", "r2", "FLAGGED_FOR"),
        Edge("s1", "s2", "SUPPLIES_TO"),
        Edge("s2", "s1", "SUPPLIES_TO"),
    ]
    return nodes, edges


def test_normalize_and_metrics() -> None:
    assert normalize("  Alpha-Industries, FY2025! ") == "alpha industries fy2025"
    contexts = ["Alpha Industries owns Alpha Parts.", "Beta Holdings is separate."]
    assert evidence_recall(["Alpha Parts", "Beta Holdings"], contexts) == 1.0
    assert evidence_recall(["Alpha Parts", "Missing"], contexts) == 0.5
    assert retrieval_hit(["Missing"], contexts) is False
    assert answer_correct("The answer is Alpha Industries.", "Alpha Industries")
    assert answer_correct("1", "1")
    assert answer_correct("10", "1") is False
    assert answer_correct("LOW", "HIGH") is False
    assert answer_correct("", "Alpha Industries") is False


def test_flatten_retrieval_skips_query_provenance() -> None:
    rows = {
        "source": "graph",
        "cypher": "MATCH (n) RETURN n",
        "results": [{"name": "Alpha Industries", "type": "Company"}],
    }
    flattened = flatten_retrieval(rows)
    assert "Alpha Industries" in flattened
    assert "Company" in flattened
    assert all("MATCH" not in item for item in flattened)


def test_generate_questions_is_deterministic_and_valid() -> None:
    nodes, edges = fixture_graph()
    first = generate_questions(nodes, edges, count=20, seed=7)
    second = generate_questions(nodes, edges, count=20, seed=7)
    assert [item.to_json() for item in first] == [item.to_json() for item in second]
    assert len(first) == 20
    assert len({item.question for item in first}) == 20
    assert len({item.id for item in first}) == 20
    assert {item.question_type for item in first} >= {
        "common_neighbor",
        "bridge_path",
        "two_hop_type",
        "relationship_chain",
        "exact_two_hop_count",
        "mutual_neighbor_type",
        "two_hop_relationship_type",
    }
    for item in first:
        assert item.hops >= 2
        assert item.answer
        assert item.evidence
        assert item.question.endswith("?")
        assert item.answer.lower() not in item.question.lower()


def test_generator_refuses_to_pad_a_small_graph() -> None:
    nodes, edges = fixture_graph()
    with pytest.raises(ValueError, match="only"):
        generate_questions(nodes, edges, count=500, seed=7)


def test_summary_does_not_invent_unmeasured_values() -> None:
    records = [
        {
            "system": "graphrag",
            "question_type": "bridge_path",
            "latency_ms": 10.0,
            "evidence_recall": 1.0,
            "retrieval_hit": True,
            "answer_correct": None,
            "answer_latency_ms": None,
            "hallucination": None,
            "error": None,
        },
        {
            "system": "graphrag",
            "question_type": "bridge_path",
            "latency_ms": 30.0,
            "evidence_recall": 0.5,
            "retrieval_hit": True,
            "answer_correct": None,
            "answer_latency_ms": None,
            "hallucination": None,
            "error": None,
        },
    ]
    summary = summarize(records)["graphrag"]
    assert summary["questions"] == 2
    assert summary["evidence_recall_mean"] == 0.75
    assert summary["retrieval_latency_ms_mean"] == 20.0
    assert summary["answer_accuracy"] is None
    assert summary["hallucination_rate"] is None
    assert summary["answered"] == 0
    assert summary["judged"] == 0
