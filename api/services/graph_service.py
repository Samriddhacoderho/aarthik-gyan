from __future__ import annotations

import json
from typing import Any

from api.errors import ApiError, service_unavailable
from api.schemas import (
    AssessmentRecord,
    CompanySummary,
    DashboardResponse,
    DocumentSummary,
    GraphEdge,
    GraphNode,
    GraphResponse,
    ReviewEvent,
)
from api.settings import settings


def _run(query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Run a read-only query through the existing V3 Neo4j client.

    Imports are intentionally local: importing ``graph.neo4j_client`` pulls in
    ``config`` and constructs the driver at module import time.
    """

    try:
        from graph.neo4j_client import neo4j_client
    except Exception as exc:  # configuration/driver construction failed
        raise service_unavailable("Neo4j") from exc

    try:
        return neo4j_client.run_query(query, params or {})
    except Exception as exc:
        raise service_unavailable("Neo4j") from exc


def _as_str(value: Any) -> str | None:
    return None if value is None else str(value)


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_bool(value: Any) -> bool | None:
    return None if value is None else bool(value)


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if item is not None]
    return [str(value)]


def _json_or_none(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else None
    except (TypeError, ValueError):
        return None


LIST_DOCUMENTS_QUERY = """
MATCH (d:Document)
RETURN d.hash AS hash, d.filename AS filename, d.status AS status,
       toString(d.ingested_at) AS ingested_at,
       d.entity_count AS entity_count, d.relationship_count AS relationship_count,
       d.failed_batch_count AS failed_batch_count
ORDER BY d.ingested_at DESC
"""

GET_DOCUMENT_QUERY = """
MATCH (d:Document {hash: $hash})
RETURN d.hash AS hash, d.filename AS filename, d.status AS status,
       toString(d.ingested_at) AS ingested_at,
       d.entity_count AS entity_count, d.relationship_count AS relationship_count,
       d.failed_batch_count AS failed_batch_count
"""

LIST_COMPANIES_QUERY = """
MATCH (c:Entity {type: 'Company'})
OPTIONAL MATCH (c)-[r:RELATION]-()
WITH c, count(DISTINCT r) AS relationship_count
OPTIONAL MATCH (c)-[:HAS_ASSESSMENT]->(a:RiskAssessment)
WITH c, relationship_count, count(DISTINCT a) AS assessment_count
RETURN c.id AS id, c.name AS name, c.description AS description,
       relationship_count, assessment_count
ORDER BY relationship_count DESC, c.name
"""

GET_COMPANY_QUERY = """
MATCH (c:Entity {id: $company_id, type: 'Company'})
OPTIONAL MATCH (c)-[r:RELATION]-()
WITH c, count(DISTINCT r) AS relationship_count
OPTIONAL MATCH (c)-[:HAS_ASSESSMENT]->(a:RiskAssessment)
WITH c, relationship_count, count(DISTINCT a) AS assessment_count
RETURN c.id AS id, c.name AS name, c.description AS description,
       relationship_count, assessment_count
"""

DOCUMENT_COMPANIES_QUERY = """
MATCH (d:Document {hash: $hash})-[:MENTIONS]->(c:Entity {type: 'Company'})
OPTIONAL MATCH (c)-[r:RELATION]-()
WITH c, count(DISTINCT r) AS relationship_count
OPTIONAL MATCH (c)-[:HAS_ASSESSMENT]->(a:RiskAssessment)
WITH c, relationship_count, count(DISTINCT a) AS assessment_count
RETURN c.id AS id, c.name AS name, c.description AS description,
       relationship_count, assessment_count
ORDER BY relationship_count DESC, c.id
"""

GET_ASSESSMENTS_QUERY = """
MATCH (c:Entity {id: $company_id, type: 'Company'})-[:HAS_ASSESSMENT]->(a:RiskAssessment)
OPTIONAL MATCH (a)-[:BASED_ON]->(d:Document)
OPTIONAL MATCH (a)-[:HAS_REVIEW]->(e:ReviewEvent)
WITH a, d, collect(DISTINCT e) AS events
RETURN a.id AS id, a.risk_level AS risk_level, a.final_risk_level AS final_risk_level,
       a.debt_to_equity AS debt_to_equity, a.current_ratio AS current_ratio,
       a.net_margin AS net_margin, a.final_debt_to_equity AS final_debt_to_equity,
       a.final_current_ratio AS final_current_ratio, a.final_net_margin AS final_net_margin,
       a.status AS status, a.notes AS notes, a.final_notes AS final_notes,
       toString(a.created_at) AS created_at, a.approved_by AS approved_by,
       toString(a.approved_at) AS approved_at, a.overridden AS overridden,
       a.edit_notes AS edit_notes, a.review_count AS review_count,
       d.hash AS document_hash, d.filename AS document_filename,
       [x IN events | {
           id: x.id, at: toString(x.at), action: x.action, reviewer: x.reviewer,
           iteration: x.iteration, notes: x.notes, before: x.before, after: x.after
       }] AS review_events
ORDER BY a.created_at DESC
"""

TOTALS_QUERY = """
OPTIONAL MATCH (e:Entity)
WITH count(e) AS entities
OPTIONAL MATCH (d:Document)
WITH entities, count(d) AS documents
OPTIONAL MATCH ()-[r:RELATION]->()
RETURN entities, documents, count(r) AS relationships
"""

GRAPH_NODES_TEMPLATE = """
MATCH (c:Entity {id: $company_id, type: 'Company'})
OPTIONAL MATCH (c)-[:RELATION*1..{depth}]-(n:Entity)
WITH c, collect(DISTINCT n) AS others
WITH [c] + others AS nodes
UNWIND nodes AS n
WITH DISTINCT n
RETURN n.id AS id, n.name AS name, n.type AS type
LIMIT $limit
"""

GRAPH_EDGES_TEMPLATE = """
MATCH (c:Entity {id: $company_id, type: 'Company'})
MATCH p=(c)-[:RELATION*1..{depth}]-(n:Entity)
UNWIND relationships(p) AS rel
RETURN DISTINCT startNode(rel).id AS source, endNode(rel).id AS target,
       rel.type AS type, rel.detail AS detail
LIMIT $limit
"""


def _document(row: dict[str, Any]) -> DocumentSummary:
    return DocumentSummary(
        hash=str(row["hash"]),
        filename=row.get("filename"),
        status=row.get("status"),
        ingested_at=_as_str(row.get("ingested_at")),
        entity_count=_as_int(row.get("entity_count")),
        relationship_count=_as_int(row.get("relationship_count")),
        failed_batch_count=_as_int(row.get("failed_batch_count")),
    )


def list_documents() -> list[DocumentSummary]:
    return [_document(row) for row in _run(LIST_DOCUMENTS_QUERY)]


def get_document(document_hash: str) -> DocumentSummary:
    rows = _run(GET_DOCUMENT_QUERY, {"hash": document_hash})
    if not rows:
        raise ApiError(404, "document_not_found", "No ingested document has that hash.")
    return _document(rows[0])


def list_companies() -> list[CompanySummary]:
    return [
        CompanySummary(
            id=str(row["id"]),
            name=row.get("name"),
            description=row.get("description"),
            relationship_count=_as_int(row.get("relationship_count")) or 0,
            assessment_count=_as_int(row.get("assessment_count")) or 0,
        )
        for row in _run(LIST_COMPANIES_QUERY)
    ]


def get_company(company_id: str) -> CompanySummary:
    rows = _run(GET_COMPANY_QUERY, {"company_id": company_id})
    if not rows:
        raise ApiError(404, "company_not_found", "No company entity has that id.")
    row = rows[0]
    return CompanySummary(
        id=str(row["id"]),
        name=row.get("name"),
        description=row.get("description"),
        relationship_count=_as_int(row.get("relationship_count")) or 0,
        assessment_count=_as_int(row.get("assessment_count")) or 0,
    )


def get_document_companies(document_hash: str) -> list[CompanySummary]:
    """Companies this exact document mentions, most connected first.

    ``analyze.py`` uses the same degree rule to pick a primary company, so the
    first item here is the natural default. Only a mentioned company can have a
    risk assessment written for that document.
    """

    get_document(document_hash)
    return [
        CompanySummary(
            id=str(row["id"]),
            name=row.get("name"),
            description=row.get("description"),
            relationship_count=_as_int(row.get("relationship_count")) or 0,
            assessment_count=_as_int(row.get("assessment_count")) or 0,
        )
        for row in _run(DOCUMENT_COMPANIES_QUERY, {"hash": document_hash})
    ]


def _assessment(row: dict[str, Any]) -> AssessmentRecord:
    events = []
    for raw in row.get("review_events") or []:
        if not isinstance(raw, dict):
            continue
        events.append(
            ReviewEvent(
                id=_as_str(raw.get("id")),
                at=_as_str(raw.get("at")),
                action=_as_str(raw.get("action")),
                reviewer=_as_str(raw.get("reviewer")),
                iteration=_as_int(raw.get("iteration")),
                notes=_as_str(raw.get("notes")),
                before=_json_or_none(raw.get("before")),
                after=_json_or_none(raw.get("after")),
            )
        )
    return AssessmentRecord(
        id=str(row["id"]),
        risk_level=_as_str(row.get("risk_level")),
        final_risk_level=_as_str(row.get("final_risk_level")),
        debt_to_equity=_as_float(row.get("debt_to_equity")),
        current_ratio=_as_float(row.get("current_ratio")),
        net_margin=_as_float(row.get("net_margin")),
        final_debt_to_equity=_as_float(row.get("final_debt_to_equity")),
        final_current_ratio=_as_float(row.get("final_current_ratio")),
        final_net_margin=_as_float(row.get("final_net_margin")),
        status=_as_str(row.get("status")),
        notes=_as_list(row.get("notes")),
        final_notes=_as_list(row.get("final_notes")),
        created_at=_as_str(row.get("created_at")),
        approved_by=_as_str(row.get("approved_by")),
        approved_at=_as_str(row.get("approved_at")),
        overridden=_as_bool(row.get("overridden")),
        edit_notes=_as_str(row.get("edit_notes")),
        review_count=_as_int(row.get("review_count")),
        document_hash=_as_str(row.get("document_hash")),
        document_filename=_as_str(row.get("document_filename")),
        review_events=events,
    )


def get_assessments(company_id: str) -> list[AssessmentRecord]:
    return [_assessment(row) for row in _run(GET_ASSESSMENTS_QUERY, {"company_id": company_id})]


def get_dashboard(company_id: str) -> DashboardResponse:
    company = get_company(company_id)
    assessments = get_assessments(company_id)
    rows = _run(TOTALS_QUERY)
    totals = rows[0] if rows else {}
    return DashboardResponse(
        company=company,
        latest_assessment=assessments[0] if assessments else None,
        assessments=assessments[:8],
        documents=list_documents(),
        totals={
            "entities": _as_int(totals.get("entities")) or 0,
            "documents": _as_int(totals.get("documents")) or 0,
            "relationships": _as_int(totals.get("relationships")) or 0,
        },
    )


def get_graph(company_id: str, depth: int = 1) -> GraphResponse:
    # The company must exist even if it has no relationships yet.
    get_company(company_id)
    depth = max(1, min(int(depth), 2))
    node_rows = _run(
        GRAPH_NODES_TEMPLATE.replace("{depth}", str(depth)),
        {"company_id": company_id, "limit": settings.graph_max_nodes},
    )
    edge_rows = _run(
        GRAPH_EDGES_TEMPLATE.replace("{depth}", str(depth)),
        {"company_id": company_id, "limit": settings.graph_max_edges},
    )

    nodes: dict[str, GraphNode] = {}
    for row in node_rows:
        node_id = _as_str(row.get("id"))
        if node_id:
            nodes[node_id] = GraphNode(
                id=node_id,
                name=_as_str(row.get("name")),
                type=_as_str(row.get("type")),
            )

    edges: list[GraphEdge] = []
    for row in edge_rows:
        source = _as_str(row.get("source"))
        target = _as_str(row.get("target"))
        if not source or not target:
            continue
        # Include endpoints if the node cap omitted them.
        nodes.setdefault(source, GraphNode(id=source))
        nodes.setdefault(target, GraphNode(id=target))
        edges.append(
            GraphEdge(
                source=source,
                target=target,
                type=_as_str(row.get("type")),
                detail=_as_str(row.get("detail")),
            )
        )

    return GraphResponse(
        company_id=company_id,
        depth=depth,
        nodes=list(nodes.values()),
        edges=edges,
        truncated=len(node_rows) >= settings.graph_max_nodes
        or len(edge_rows) >= settings.graph_max_edges,
    )
