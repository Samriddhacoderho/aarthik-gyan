from __future__ import annotations

import json

from api.schemas import CompanySummary
from api.services import graph_service
from api.services.graph_service import _as_float, _as_int, _as_list, _assessment, _json_or_none
from api.services.graph_service import (
    DOCUMENT_COMPANIES_QUERY,
    GRAPH_EDGES_TEMPLATE,
    GRAPH_NODES_TEMPLATE,
)


def test_assessment_row_is_mapped_without_changing_backend_models() -> None:
    record = _assessment(
        {
            "id": "assessment-1",
            "risk_level": "MEDIUM",
            "final_risk_level": "LOW",
            "debt_to_equity": 1.4,
            "current_ratio": 1.2,
            "net_margin": 0.08,
            "final_debt_to_equity": 1.3,
            "final_current_ratio": 1.25,
            "final_net_margin": 0.09,
            "status": "APPROVED",
            "notes": ["Moderate debt-to-equity ratio (1.4)."],
            "final_notes": ["Healthy debt-to-equity ratio (1.3)."],
            "created_at": "2026-01-01T00:00:00",
            "approved_by": "analyst",
            "approved_at": "2026-01-02T00:00:00",
            "overridden": True,
            "edit_notes": "Corrected from source.",
            "review_count": 2,
            "document_hash": "abc",
            "document_filename": "report.pdf",
            "review_events": [
                {
                    "id": "event-1",
                    "at": "2026-01-02T00:00:00",
                    "action": "override",
                    "reviewer": "analyst",
                    "iteration": 1,
                    "notes": "Corrected from source.",
                    "before": json.dumps({"risk_level": "MEDIUM"}),
                    "after": json.dumps({"risk_level": "LOW"}),
                }
            ],
        }
    )
    assert record.final_risk_level == "LOW"
    assert record.document_filename == "report.pdf"
    assert record.review_events[0].before == {"risk_level": "MEDIUM"}
    assert record.review_events[0].after == {"risk_level": "LOW"}


def test_safe_coercions() -> None:
    assert _as_int("3") == 3
    assert _as_int("not-a-number") is None
    assert _as_float("1.5") == 1.5
    assert _as_list(None) == []
    assert _as_list(["a", "b"]) == ["a", "b"]
    assert _json_or_none('{"a": 1}') == {"a": 1}
    assert _json_or_none("not-json") is None


def test_graph_templates_preserve_cypher_property_maps() -> None:
    # Cypher property maps also use braces. Using str.format() here would raise
    # KeyError('id') and silently break the explorer.
    nodes_query = GRAPH_NODES_TEMPLATE.replace("{depth}", "2")
    edges_query = GRAPH_EDGES_TEMPLATE.replace("{depth}", "2")
    assert "{id: $company_id" in nodes_query
    assert "RELATION*1..2" in nodes_query
    assert "{id: $company_id" in edges_query
    assert "RELATION*1..2" in edges_query
    assert "{depth}" not in nodes_query
    assert "{depth}" not in edges_query


def test_document_companies_maps_real_rows_and_uses_hash_parameter(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_document(document_hash: str) -> dict[str, object]:
        return {"hash": document_hash}

    def fake_run(query: str, parameters: dict[str, object]) -> list[dict[str, object]]:
        calls.append((query, parameters))
        return [
            {
                "id": "company_a",
                "name": "Alpha Industries",
                "description": "Manufacturer",
                "relationship_count": "9",
                "assessment_count": 2,
            },
            {
                "id": "company_b",
                "name": None,
                "description": None,
                "relationship_count": None,
                "assessment_count": "3",
            },
        ]

    monkeypatch.setattr(graph_service, "get_document", fake_document)
    monkeypatch.setattr(graph_service, "_run", fake_run)

    companies = graph_service.get_document_companies("hash-123")

    assert companies == [
        CompanySummary(
            id="company_a",
            name="Alpha Industries",
            description="Manufacturer",
            relationship_count=9,
            assessment_count=2,
        ),
        CompanySummary(
            id="company_b",
            name=None,
            description=None,
            relationship_count=0,
            assessment_count=3,
        ),
    ]
    assert len(calls) == 1
    query, parameters = calls[0]
    assert query is DOCUMENT_COMPANIES_QUERY
    assert parameters == {"hash": "hash-123"}
    # The endpoint must filter by the document's content hash, not by filename.
    assert "Document {hash: $hash}" in query
    assert "MENTIONS" in query
    assert "type: 'Company'" in query

