from datetime import datetime, timezone
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from llm.provider import get_llm
from prompts.writer_prompt import WRITER_PROMPT
from workflow.state import GraphState
from schemas.audit import ApprovalRecord
from reports.pdf_builder import build_risk_report_pdf
from graph.neo4j_client import neo4j_client

WRITE_APPROVAL_QUERY = """
MATCH (c:Entity {id: $company_id, type: 'Company'})-[:HAS_ASSESSMENT]->(r:RiskAssessment)
WITH r ORDER BY r.created_at DESC LIMIT 1
SET r.status = $decision,
    r.approved_by = $approved_by,
    r.approved_at = datetime($approved_at),
    r.final_debt_to_equity = $debt_to_equity,
    r.final_current_ratio = $current_ratio,
    r.final_net_margin = $net_margin,
    r.final_risk_level = $risk_level,
    r.edit_notes = $edit_notes
RETURN r
"""


def writer_node(state: GraphState) -> dict:
    final_score = state.get("human_edited_score") or state["risk_score"]

    print(f"[writer] Generating report for {state['company_name']} "
          f"(final risk_level={final_score.get('risk_level')})...")

    prompt = PromptTemplate(template=WRITER_PROMPT, input_variables=[
        "company_name", "risk_level", "debt_to_equity", "current_ratio",
        "net_margin", "human_notes", "auditor_findings"
    ])
    chain = prompt | get_llm() | StrOutputParser()
    report_text = chain.invoke({
        "company_name": state["company_name"],
        "risk_level": final_score.get("risk_level"),
        "debt_to_equity": final_score.get("debt_to_equity"),
        "current_ratio": final_score.get("current_ratio"),
        "net_margin": final_score.get("net_margin"),
        "human_notes": state.get("human_notes") or "None provided.",
        "auditor_findings": "\n".join(f"- {f}" for f in state.get("auditor_findings", [])),
    })

    approved_at = datetime.now(timezone.utc).isoformat()
    decision = "APPROVED" if state["human_decision"] == "approve" else "REJECTED_FINALIZED"

    # Write audit trail back to the graph FIRST (source of truth), then generate the PDF
    neo4j_client.run_query(WRITE_APPROVAL_QUERY, {
        "company_id": state["company_id"],
        "decision": decision,
        "approved_by": "analyst",
        "approved_at": approved_at,
        "debt_to_equity": final_score.get("debt_to_equity"),
        "current_ratio": final_score.get("current_ratio"),
        "net_margin": final_score.get("net_margin"),
        "risk_level": final_score.get("risk_level"),
        "edit_notes": state.get("human_notes"),
    })
    print(f"[writer] Audit trail written to graph: {decision} by analyst at {approved_at}")

    approval_record = ApprovalRecord(
        company_id=state["company_id"],
        document_hash=state["document_hash"],
        decision=decision,
        approved_by="analyst",
        approved_at=approved_at,
        original_score=state["risk_score"],
        final_score=final_score,
        edit_notes=state.get("human_notes"),
        iteration_count=state["iteration"],
    )

    report_path = build_risk_report_pdf(
        company_name=state["company_name"],
        company_id=state["company_id"],
        report_text=report_text,
        final_score=final_score,
        approval_record=approval_record,
    )

    print(f"[writer] PDF report written to {report_path}")
    return {"final_report_path": report_path, "approval_record": approval_record.model_dump()}