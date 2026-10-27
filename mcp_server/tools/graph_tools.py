from typing import Union
from graph.queries import fetch_company_profile, fetch_connected_entities, fetch_degree_centrality
from schemas.mcp_outputs import CompanyProfile, ConnectedEntity, CentralityResult, ToolError


def register_graph_tools(mcp):
    @mcp.tool()
    def get_company_profile(company_id: str) -> Union[CompanyProfile, ToolError]:
        """Returns a company's basic structural profile: id, name, description and how many direct
        relationships it has in the graph. It deliberately contains NO risk scores or ratios."""
        profile = fetch_company_profile(company_id)
        if profile is None:
            return ToolError(error=f"No company found with id '{company_id}'.")
        return CompanyProfile(**profile)

    @mcp.tool()
    def get_connected_entities(company_id: str, hops: int = 2) -> list[ConnectedEntity]:
        """Returns entities connected to the given company within N hops
        (max 3) — subsidiaries, suppliers, auditors, risk factors, etc.
        company_id is the company's id (e.g. 'whitcombe_properties'); its exact
        name is also accepted."""
        results = fetch_connected_entities(company_id, hops)
        return [ConnectedEntity(**r) for r in results]

    @mcp.tool()
    def calculate_graph_centrality(limit: int = 15) -> list[CentralityResult]:
        """Returns the top entities by degree centrality (number of direct
        relationships) — plain Cypher degree count, not full GDS centrality."""
        results = fetch_degree_centrality(limit)
        return [CentralityResult(**r) for r in results]
