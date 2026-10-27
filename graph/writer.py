import uuid
from graph.neo4j_client import neo4j_client
from schemas.entities import ExtractionResult

WRITE_ENTITIES_QUERY = """
MATCH (d:Document {hash: $document_hash})
UNWIND $entities AS ent
MERGE (e:Entity {id: ent.id})
SET e.name = ent.name, e.type = ent.type, e.description = ent.description
MERGE (d)-[:MENTIONS]->(e)
"""

WRITE_RELATIONSHIPS_QUERY = """
UNWIND $relationships AS rel
MATCH (a:Entity {id: rel.source_id})
MATCH (b:Entity {id: rel.target_id})
MERGE (a)-[r:RELATION {type: rel.type}]->(b)
SET r.detail = rel.detail, r.source_document = $document_hash
"""


def write_extraction_to_graph(result: ExtractionResult, document_hash: str):
    entities = [e.model_dump() for e in result.entities]
    relationships = [r.model_dump() for r in result.relationships]

    if entities:
        neo4j_client.run_query(WRITE_ENTITIES_QUERY, {"document_hash": document_hash, "entities": entities})
        print(f"[writer] Merged {len(entities)} entities.")

    if relationships:
        neo4j_client.run_query(WRITE_RELATIONSHIPS_QUERY, {"document_hash": document_hash, "relationships": relationships})
        print(f"[writer] Merged up to {len(relationships)} relationships "
              f"(any pointing at a missing entity id are skipped).")


WRITE_RISK_ASSESSMENT_QUERY = """
MATCH (c:Entity {id: $company_id, type: 'Company'})
MATCH (d:Document {hash: $document_hash})
MERGE (r:RiskAssessment {id: $assessment_id})
ON CREATE SET r.status = 'DRAFT', r.created_at = datetime()
SET r.risk_level = $risk_level, r.debt_to_equity = $debt_to_equity,
    r.current_ratio = $current_ratio, r.net_margin = $net_margin, r.notes = $notes
MERGE (c)-[:HAS_ASSESSMENT]->(r)
MERGE (r)-[:BASED_ON]->(d)
RETURN r
"""


def assessment_id_for(company_id: str, document_hash: str) -> str:
    """One assessment per (company, document): the same inputs always give the same id."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{company_id}:{document_hash}"))


def save_risk_assessment(company_id: str, document_hash: str, risk_level: str,
                         debt_to_equity: float | None, current_ratio: float | None,
                         net_margin: float | None, notes: list[str]) -> str | None:
    """Stores the SYSTEM's numbers on the assessment node. Status is only set when the node is
    created (DRAFT); approved values (final_*) are never touched here."""
    assessment_id = assessment_id_for(company_id, document_hash)
    result = neo4j_client.run_query(WRITE_RISK_ASSESSMENT_QUERY, {
        "assessment_id": assessment_id, "company_id": company_id, "document_hash": document_hash,
        "risk_level": risk_level, "debt_to_equity": debt_to_equity,
        "current_ratio": current_ratio, "net_margin": net_margin, "notes": notes,
    })
    return assessment_id if result else None
