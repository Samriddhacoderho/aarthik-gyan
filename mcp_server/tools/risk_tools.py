from typing import Literal, Optional, Union
from graph.queries import fetch_debt_ratio_history
from graph.writer import save_risk_assessment as write_assessment_to_graph
from schemas.mcp_outputs import DebtRatioHistory, RiskAssessmentEntry, SavedAssessment, ToolError


def register_risk_tools(mcp):
    @mcp.tool()
    def get_debt_ratios(company_id: str) -> Union[DebtRatioHistory, ToolError]:
        """Returns the full history of risk assessments for a company, newest first. Each entry says
        which document (document_hash / document_filename) it was calculated from, its status, and the
        analyst-approved level (final_risk_level) if it was reviewed."""
        history = fetch_debt_ratio_history(company_id)
        if not history:
            return ToolError(error=f"No risk assessments found for '{company_id}'.")

        entries = []
        for h in history:
            if h.get("created_at") is not None:
                h["created_at"] = str(h["created_at"])
            entries.append(RiskAssessmentEntry(**h))

        return DebtRatioHistory(company_id=company_id, assessment_count=len(entries), history=entries)

    @mcp.tool()
    def save_risk_assessment(
        company_id: str,
        document_hash: str,
        risk_level: Literal["LOW", "MEDIUM", "HIGH", "UNKNOWN"],
        debt_to_equity: Optional[float] = None,
        current_ratio: Optional[float] = None,
        net_margin: Optional[float] = None,
        notes: Optional[list[str]] = None,
    ) -> Union[SavedAssessment, ToolError]:
        """Stores the SYSTEM-calculated risk numbers for one company on one document (a DRAFT
        assessment; creates it, or re-calculates it in place). It never touches approved values
        (final_*) or the review history: those are only written when an analyst approves."""
        assessment_id = write_assessment_to_graph(
            company_id, document_hash, risk_level, debt_to_equity, current_ratio, net_margin, notes or [],
        )
        if assessment_id is None:
            return ToolError(
                error=f"No Company '{company_id}' or Document '{document_hash}' exists in the graph. "
                      "Run main.py to ingest the document first."
            )
        return SavedAssessment(assessment_id=assessment_id, risk_level=risk_level)
