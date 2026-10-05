from graph.queries import fetch_company_profile, fetch_connected_entities, fetch_degree_centrality



def register_graph_tools(mcp):
    @mcp.tool()
    def get_company_profile(company_id: str) -> dict:
        """Returns a company's basic profile plus its latest risk assessment
        (risk_level, debt_to_equity, current_ratio, net_margin), if one exists."""
        profile = fetch_company_profile(company_id)
        if profile is None:
            return {"error": f"No company found with id '{company_id}'."}
        return profile

    @mcp.tool()
    def get_connected_entities(company: str, hops: int = 2) -> list[dict]:
        """Returns entities connected to the given company within N hops
        (max 3) — subsidiaries, suppliers, auditors, risk factors, etc.
        Useful for spotting indirect exposure, e.g. 'who does this company's
        supplier depend on'."""
        return fetch_connected_entities(company, hops)

    @mcp.tool()
    def calculate_graph_centrality(limit: int = 15) -> list[dict]:
        """Returns the top entities by degree centrality (number of direct
        relationships) — a simple proxy for structural importance/exposure
        in the graph. Plain Cypher degree count, not full GDS centrality
        (e.g. not PageRank/betweenness) — upgrade path: Aura Graph Analytics."""
        return fetch_degree_centrality(limit)