from graph.neo4j_client import neo4j_client
from graph.writer import assessment_id_for, save_risk_assessment
from risk.ratios import extract_financial_metrics, compute_risk_score
from risk.metrics_retriever import retrieve_metrics_context
from schemas.risk import RiskScore

FIND_ASSESSMENT_QUERY = """
MATCH (:Entity {id: $company_id})-[:HAS_ASSESSMENT]->(r:RiskAssessment {id: $assessment_id})
RETURN r.status AS status
"""


def write_risk_assessment(score: RiskScore, document_hash: str) -> str | None:
    assessment_id = save_risk_assessment(
        score.company_id, document_hash, score.risk_level, score.debt_to_equity,
        score.current_ratio, score.net_margin, score.notes,
    )
    if assessment_id is None:
        print(f"[risk_agent] Warning: no Company/Document match for '{score.company_id}' — assessment not written.")
        return None
    print(f"[risk_agent] Wrote DRAFT RiskAssessment for {score.company_id}: {score.risk_level}")
    return assessment_id


# NOTE: this function is the INGESTION path (main.py): it talks to Neo4j/Qdrant directly. The review
# workflow (analyze.py) does NOT use it; workflow/nodes/quant.py does the same job through MCP tools.
def run_risk_agent(company_id: str, company_name: str, document_hash: str, force: bool = False,
                   analyst_hint: str | None = None, allow_overwrite_final: bool = False):
    """Scores a company on one document and stores it as a DRAFT RiskAssessment.

    force=True              re-score even if a DRAFT already exists.
    analyst_hint            a human's guidance: used as an extra search query AND shown to the LLM.
    allow_overwrite_final   only the analyst-requested re-run in the review loop passes True. It lets the
                            SYSTEM's numbers on an already approved assessment be re-calculated. The approved
                            values themselves (final_*) and the review history are never touched here; they
                            are only replaced when the writer records a new approval.
    """
    assessment_id = assessment_id_for(company_id, document_hash)
    existing = neo4j_client.run_query(FIND_ASSESSMENT_QUERY, {"company_id": company_id, "assessment_id": assessment_id})

    if existing:
        status = existing[0]["status"]
        if status != "DRAFT" and not allow_overwrite_final:
            print(f"[risk_agent] {company_id} already has a {status} assessment for this document — leaving it untouched.")
            return assessment_id
        if not force:
            print(f"[risk_agent] Reusing existing {status} assessment for {company_id} (no LLM call).")
            return assessment_id

    print(f"[risk_agent] Scoring '{company_name}' ({company_id})...")
    context = retrieve_metrics_context(document_hash, extra_queries=[analyst_hint] if analyst_hint else None)
    metrics = extract_financial_metrics(context, company_hint=company_name, analyst_hint=analyst_hint)
    score = compute_risk_score(company_id, metrics)
    return write_risk_assessment(score, document_hash)