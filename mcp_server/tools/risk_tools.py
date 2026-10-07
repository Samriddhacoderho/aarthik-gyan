from typing import Union
from graph.queries import fetch_debt_ratio_history
from schemas.mcp_outputs import DebtRatioHistory, RiskAssessmentEntry, ToolError


def register_risk_tools(mcp):
    @mcp.tool()
    def get_debt_ratios(company_id: str) -> Union[DebtRatioHistory, ToolError]:
        """Returns the full history of risk assessments for a company,
        ordered newest first."""
        history = fetch_debt_ratio_history(company_id)
        if not history:
            return ToolError(error=f"No risk assessments found for '{company_id}'.")

        entries = []
        for h in history:
            if h.get("created_at") is not None:
                h["created_at"] = str(h["created_at"])
            entries.append(RiskAssessmentEntry(**h))

        return DebtRatioHistory(company_id=company_id, assessment_count=len(entries), history=entries)