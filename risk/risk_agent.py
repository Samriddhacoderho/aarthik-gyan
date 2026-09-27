from graph.neo4j_client import neo4j_client
from risk.ratios import extract_financial_metrics, compute_risk_score
from schemas.risk import RiskScore

WRITE_RISK_SCORE_QUERY = """
MATCH (c:Entity {id: $company_id, type: 'Company'})
SET c.risk_level = $risk_level,
    c.debt_to_equity = $debt_to_equity,
    c.current_ratio = $current_ratio,
    c.net_margin = $net_margin,
    c.risk_notes = $notes,
    c.risk_scored_at = datetime()
RETURN c
"""


def write_risk_score_to_graph(score: RiskScore):
    result = neo4j_client.run_query(WRITE_RISK_SCORE_QUERY, {
        "company_id": score.company_id,
        "risk_level": score.risk_level,
        "debt_to_equity": score.debt_to_equity,
        "current_ratio": score.current_ratio,
        "net_margin": score.net_margin,
        "notes": score.notes,
    })
    if not result:
        print(f"[risk_agent] Warning: no Company node found for id '{score.company_id}' — score not attached.")
        return
    print(f"[risk_agent] {score.company_id} → risk_level={score.risk_level} "
          f"(D/E={score.debt_to_equity}, CR={score.current_ratio}, margin={score.net_margin})")


def run_risk_agent(full_document_text: str, company_id: str, company_name: str):
    """Runs the full risk pass for one company mentioned in one document:
    extract numeric metrics → compute ratios → write score to its Company node."""
    print(f"[risk_agent] Scoring '{company_name}' ({company_id})...")
    metrics = extract_financial_metrics(full_document_text, company_hint=company_name)
    score = compute_risk_score(company_id, metrics)
    write_risk_score_to_graph(score)
    return score