import uuid
from graph.neo4j_client import neo4j_client
from risk.ratios import extract_financial_metrics, compute_risk_score
from risk.metrics_retriever import retrieve_metrics_context
from schemas.risk import RiskScore

WRITE_RISK_ASSESSMENT_QUERY = """
MATCH (c:Entity {id: $company_id, type: 'Company'})
MATCH (d:Document {hash: $document_hash})
CREATE (r:RiskAssessment {
    id: $assessment_id,
    risk_level: $risk_level,
    debt_to_equity: $debt_to_equity,
    current_ratio: $current_ratio,
    net_margin: $net_margin,
    notes: $notes,
    status: 'DRAFT',
    created_at: datetime()
})
MERGE (c)-[:HAS_ASSESSMENT]->(r)
MERGE (r)-[:BASED_ON]->(d)
RETURN r
"""


def write_risk_assessment(score: RiskScore, document_hash: str) -> str:
    assessment_id = str(uuid.uuid4())
    result = neo4j_client.run_query(WRITE_RISK_ASSESSMENT_QUERY, {
        "assessment_id": assessment_id,
        "company_id": score.company_id,
        "document_hash": document_hash,
        "risk_level": score.risk_level,
        "debt_to_equity": score.debt_to_equity,
        "current_ratio": score.current_ratio,
        "net_margin": score.net_margin,
        "notes": score.notes,
    })
    if not result:
        print(f"[risk_agent] Warning: no Company/Document match for '{score.company_id}' — assessment not written.")
        return None
    print(f"[risk_agent] Wrote DRAFT RiskAssessment {assessment_id} for {score.company_id}: {score.risk_level}")
    return assessment_id


def run_risk_agent(company_id: str, company_name: str, document_hash: str):
    """V3.1: uses targeted Qdrant retrieval instead of full_text, and creates
    a new RiskAssessment node per run instead of overwriting the Company node
    — so history/traceability across documents/versions is preserved."""
    print(f"[risk_agent] Scoring '{company_name}' ({company_id})...")
    context = retrieve_metrics_context(document_hash)
    metrics = extract_financial_metrics(context, company_hint=company_name)
    score = compute_risk_score(company_id, metrics)
    return write_risk_assessment(score, document_hash)