from langgraph.types import interrupt
from workflow.state import GraphState


def hitl_node(state: GraphState) -> dict:
    """Pauses execution and surfaces the current findings + score to a human.
    Resumes when the caller sends a Command(resume=...) with the decision."""
    payload = {
        "company_name": state["company_name"],
        "auditor_findings": state.get("auditor_findings", []),
        "risk_score": state.get("risk_score", {}),
        "iteration": state.get("iteration", 0),
    }

    human_response = interrupt(payload)

    decision = human_response.get("decision", "approve")
    edited_score = human_response.get("edited_score")
    notes = human_response.get("notes", "")

    print(f"[hitl] Human decision: {decision}" + (f" (with edits)" if edited_score else ""))

    return {
        "human_decision": decision,
        "human_edited_score": edited_score,
        "human_notes": notes,
    }


def route_after_hitl(state: GraphState) -> str:
    """Conditional edge: approve -> writer, reject -> back to quant (bounded),
    reject after max_iterations -> writer anyway (forced finalization, flagged)."""
    if state["human_decision"] == "approve":
        return "writer"
    if state["iteration"] >= state.get("max_iterations", 3):
        print("[hitl] Max iterations reached — finalizing with last score despite rejection.")
        return "writer"
    return "quant"