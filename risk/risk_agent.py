import uuid
from graph.neo4j_client import neo4j_client
from risk.ratios import extract_financial_metrics, compute_risk_score
from risk.metrics_retriever import retrieve_metrics_context
from schemas.risk import RiskScore

FIND_ASSESSMENT_QUERY = """
MATCH (:Entity {id: $company_id})-[:HAS_ASSESSMENT]->(r:RiskAssessment {id: $assessment_id})
RETURN r.status AS status
"""

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


def _assessment_id(company_id: str, document_hash: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{company_id}:{document_hash}"))


def write_risk_assessment(score: RiskScore, document_hash: str) -> str | None:
    assessment_id = _assessment_id(score.company_id, document_hash)
    result = neo4j_client.run_query(WRITE_RISK_ASSESSMENT_QUERY, {
        "assessment_id": assessment_id, "company_id": score.company_id, "document_hash": document_hash,
        "risk_level": score.risk_level, "debt_to_equity": score.debt_to_equity,
        "current_ratio": score.current_ratio, "net_margin": score.net_margin, "notes": score.notes,
    })
    if not result:
        print(f"[risk_agent] Warning: no Company/Document match for '{score.company_id}' — assessment not written.")
        return None
    print(f"[risk_agent] Wrote DRAFT RiskAssessment for {score.company_id}: {score.risk_level}")
    return assessment_id


def run_risk_agent(company_id: str, company_name: str, document_hash: str, force: bool = False):
    assessment_id = _assessment_id(company_id, document_hash)
    existing = neo4j_client.run_query(FIND_ASSESSMENT_QUERY, {"company_id": company_id, "assessment_id": assessment_id})

    if existing:
        status = existing[0]["status"]
        if status != "DRAFT":
            print(f"[risk_agent] {company_id} already has a {status} assessment for this document — leaving it untouched.")
            return assessment_id
        if not force:
            print(f"[risk_agent] Reusing existing DRAFT assessment for {company_id} (no LLM call).")
            return assessment_id

    print(f"[risk_agent] Scoring '{company_name}' ({company_id})...")
    context = retrieve_metrics_context(document_hash)
    metrics = extract_financial_metrics(context, company_hint=company_name)
    score = compute_risk_score(company_id, metrics)
    return write_risk_assessment(score, document_hash)