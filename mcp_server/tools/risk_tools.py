from graph.queries import fetch_debt_ratio_history


def register_risk_tools(mcp):
    @mcp.tool()
    def get_debt_ratios(company_id: str) -> dict:
        """Returns the full history of risk assessments for a company
        (debt_to_equity, current_ratio, net_margin, risk_level, status)
        ordered newest first — lets an agent see whether risk is trending
        up or down across documents/ingestions, not just the latest snapshot."""
        history = fetch_debt_ratio_history(company_id)
        if not history:
            return {"error": f"No risk assessments found for '{company_id}'."}
        return {"company_id": company_id, "assessment_count": len(history), "history": history}