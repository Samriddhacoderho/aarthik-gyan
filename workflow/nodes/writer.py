import json
from datetime import datetime, timezone
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from prompts.writer_prompt import WRITER_PROMPT
from workflow.review import joined_human_notes
from workflow.state import GraphState
from schemas.audit import ApprovalRecord
from reports.pdf_builder import build_risk_report_pdf
from graph.neo4j_client import neo4j_client
from llm.text_utils import strip_think
from llm.provider import get_extraction_llm

# Stamps the assessment for THIS company on THIS document (not "the newest one").
# The system's own numbers (risk_level, debt_to_equity, ...) stay as they were; the approved numbers
# go into the final_* fields, so both the proposal and the decision are kept.
WRITE_APPROVAL_QUERY = """
MATCH (:Entity {id: $company_id, type: 'Company'})-[:HAS_ASSESSMENT]->(r:RiskAssessment)
      -[:BASED_ON]->(:Document {hash: $document_hash})
SET r.status = $decision,
    r.approved_by = $approved_by,
    r.approved_at = datetime($approved_at),
    r.overridden = $overridden,
    r.final_debt_to_equity = $debt_to_equity,
    r.final_current_ratio = $current_ratio,
    r.final_net_margin = $net_margin,
    r.final_risk_level = $risk_level,
    r.final_notes = $final_notes,
    r.edit_notes = $edit_notes,
    r.review_count = $review_count
RETURN r.id AS id
"""

# One (:ReviewEvent) node per audit-trail entry, linked to the assessment. Event ids are random, so a
# second review of the same document ADDS events and never overwrites the first review's history.
WRITE_REVIEW_EVENTS_QUERY = """
MATCH (r:RiskAssessment {id: $assessment_id})
UNWIND $events AS ev
MERGE (e:ReviewEvent {id: ev.id})
SET e.seq = ev.seq, e.action = ev.action, e.reviewer = ev.reviewer, e.iteration = ev.iteration,
    e.at = datetime(ev.at), e.notes = ev.notes, e.before = ev.before, e.after = ev.after
MERGE (r)-[:HAS_REVIEW]->(e)
RETURN count(e) AS written
"""


def _event_rows(events: list[dict]) -> list[dict]:
    """Neo4j properties can't hold maps, so the before/after scores are stored as JSON text."""
    return [{
        "id": ev["id"], "seq": i, "action": ev["action"], "reviewer": ev.get("reviewer"),
        "iteration": ev.get("iteration"), "at": ev["at"], "notes": ev.get("notes") or "",
        "before": json.dumps(ev["before"]) if ev.get("before") else None,
        "after": json.dumps(ev["after"]) if ev.get("after") else None,
    } for i, ev in enumerate(events)]


def writer_node(state: GraphState) -> dict:
    events = state.get("review_history", [])
    overridden = state.get("final_score") is not None
    final_score = state.get("final_score") or state["risk_score"]
    reviewer = state.get("reviewer") or "analyst"
    human_notes = joined_human_notes(events)

    print(f"[writer] Generating report for {state['company_name']} "
          f"(final risk_level={final_score.get('risk_level')}{', analyst override' if overridden else ''})...")

    prompt = PromptTemplate(template=WRITER_PROMPT, input_variables=[
        "company_name", "risk_level", "debt_to_equity", "current_ratio",
        "net_margin", "human_notes", "auditor_findings"
    ])
    chain = prompt | get_extraction_llm(max_rounds=2) | StrOutputParser()
    report_text = chain.invoke({
        "company_name": state["company_name"],
        "risk_level": final_score.get("risk_level"),
        "debt_to_equity": final_score.get("debt_to_equity"),
        "current_ratio": final_score.get("current_ratio"),
        "net_margin": final_score.get("net_margin"),
        "human_notes": human_notes or "None provided.",
        "auditor_findings": "\n".join(f"- {f}" for f in state.get("auditor_findings", [])),
    })

    report_text = strip_think(report_text)
    approved_at = datetime.now(timezone.utc).isoformat()
    # "approve" is the only way to a normal approval. Anything else here means the re-run limit was hit.
    decision = "APPROVED" if state.get("human_action") == "approve" else "REJECTED_FINALIZED"

    # The first score the system proposed = what the analyst saw at their first decision.
    original_score = next((e["before"] for e in events if e.get("before")), None) or state["risk_score"]

    # Write audit trail back to the graph FIRST (source of truth), then generate the PDF
    updated = neo4j_client.run_query(WRITE_APPROVAL_QUERY, {
        "company_id": state["company_id"],
        "document_hash": state["document_hash"],
        "decision": decision,
        "approved_by": reviewer,
        "approved_at": approved_at,
        "overridden": overridden,
        "debt_to_equity": final_score.get("debt_to_equity"),
        "current_ratio": final_score.get("current_ratio"),
        "net_margin": final_score.get("net_margin"),
        "risk_level": final_score.get("risk_level"),
        "final_notes": final_score.get("notes"),
        "edit_notes": human_notes or None,
        "review_count": len(events),
    })
    if not updated:
        raise RuntimeError("No risk assessment matched this company and document; the decision was NOT recorded.")

    if events:
        neo4j_client.run_query(WRITE_REVIEW_EVENTS_QUERY, {
            "assessment_id": updated[0]["id"], "events": _event_rows(events),
        })
    print(f"[writer] Audit trail written to graph: {decision}{' (analyst override)' if overridden else ''} "
          f"by {reviewer} at {approved_at}, {len(events)} review event(s).")

    approval_record = ApprovalRecord(
        company_id=state["company_id"],
        document_hash=state["document_hash"],
        decision=decision,
        approved_by=reviewer,
        approved_at=approved_at,
        original_score=original_score,
        final_score=final_score,
        edit_notes=human_notes or None,
        iteration_count=state["iteration"],
        overridden=overridden,
        review_history=events,
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