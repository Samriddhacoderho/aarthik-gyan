from graph.neo4j_client import neo4j_client

# STRUCTURE ONLY. This query must never return anything from a RiskAssessment node: the auditor
# reads it BEFORE the quant step runs, and must not be steered by an earlier risk score.
COMPANY_PROFILE_QUERY = """
MATCH (c:Entity {id: $company_id, type: 'Company'})
OPTIONAL MATCH (c)-[rel:RELATION]-()
WITH c, count(rel) AS relationship_count
RETURN c.id AS id, c.name AS name, c.description AS description,
       relationship_count
"""

CONNECTED_ENTITIES_QUERY = """
MATCH (c:Entity)
WHERE c.id = $company_id OR toLower(c.name) = toLower($company_id)
MATCH (c)-[r:RELATION*1..{hops}]-(connected:Entity)
WHERE connected <> c
RETURN DISTINCT connected.id AS id, connected.name AS name, connected.type AS type,
       [rel in r | rel.type] AS relationship_path
LIMIT 50
"""

DEGREE_CENTRALITY_QUERY = """
MATCH (e:Entity)
OPTIONAL MATCH (e)-[r:RELATION]-()
WITH e, count(r) AS degree
RETURN e.id AS id, e.name AS name, e.type AS type, degree
ORDER BY degree DESC
LIMIT $limit
"""

# Used by the QUANT node only. document_hash lets it tell "the assessment for this report" (reuse /
# re-score) apart from "earlier years' assessments" (context). final_* are the analyst-approved values.
DEBT_RATIOS_QUERY = """
MATCH (c:Entity {id: $company_id, type: 'Company'})-[:HAS_ASSESSMENT]->(r:RiskAssessment)
OPTIONAL MATCH (r)-[:BASED_ON]->(d:Document)
RETURN r.debt_to_equity AS debt_to_equity, r.current_ratio AS current_ratio,
       r.net_margin AS net_margin, r.risk_level AS risk_level,
       r.notes AS notes, r.status AS status, r.created_at AS created_at,
       r.final_risk_level AS final_risk_level, r.overridden AS overridden,
       d.hash AS document_hash, d.filename AS document_filename
ORDER BY r.created_at DESC
"""


def fetch_company_profile(company_id: str) -> dict | None:
    results = neo4j_client.run_query(COMPANY_PROFILE_QUERY, {"company_id": company_id})
    return results[0] if results else None


def fetch_connected_entities(company_id: str, hops: int = 2) -> list[dict]:
    hops = max(1, min(hops, 3))
    query = CONNECTED_ENTITIES_QUERY.replace("{hops}", str(hops))
    return neo4j_client.run_query(query, {"company_id": company_id})


def fetch_degree_centrality(limit: int = 15) -> list[dict]:
    return neo4j_client.run_query(DEGREE_CENTRALITY_QUERY, {"limit": limit})


def fetch_debt_ratio_history(company_id: str) -> list[dict]:
    return neo4j_client.run_query(DEBT_RATIOS_QUERY, {"company_id": company_id})

