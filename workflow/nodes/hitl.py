from langgraph.types import interrupt

from workflow.review import apply_override, describe_event, new_event
from workflow.state import GraphState


def hitl_node(state: GraphState) -> dict:
    """Pauses and shows the analyst the findings and the proposed score. The analyst answers with one of:

      approve   accept what is shown (the system score, or the analyst's own override if one is pending)
      override  type corrected numbers; the risk level is recalculated from them, then the analyst confirms
      rerun     score again, with a hint that is used as an extra search and shown to the LLM

    Every answer is added to review_history. Nothing here ever overwrites an earlier answer."""
    current = state.get("final_score") or state["risk_score"]
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 3)

    # Everything above interrupt() runs again when the workflow resumes, so it must have no side effects.
    response = interrupt({
        "company_name": state["company_name"],
        "auditor_findings": state.get("auditor_findings", []),
        "risk_score": state["risk_score"],
        "final_score": state.get("final_score"),
        "iteration": iteration,
        "reruns_left": max(0, max_iterations - iteration),
        "review_history": state.get("review_history", []),
    })

    action = response.get("action")
    reviewer = state.get("reviewer") or "analyst"
    notes = (response.get("notes") or "").strip()

    if action == "approve":
        event = new_event("approve", reviewer, iteration, notes, before=current, after=current)
        print(f"[hitl] {describe_event(event)}")
        return {"human_action": "approve", "review_history": [event]}

    if action == "override":
        new_score = apply_override(current, response.get("edited_score"), response.get("risk_level"))
        event = new_event("override", reviewer, iteration, notes or "(no reason given)", before=current, after=new_score)
        print(f"[hitl] {describe_event(event)}")
        return {"human_action": "override", "final_score": new_score, "review_history": [event]}

    if action == "rerun":
        event = new_event("rerun", reviewer, iteration, notes or "(no hint given)", before=current, after=None)
        print(f"[hitl] {describe_event(event)}")
        # A fresh score replaces any pending override; the override stays in review_history.
        return {"human_action": "rerun", "final_score": None, "rerun_hint": notes or None,
                "review_history": [event]}

    raise ValueError(f"Unknown review action: {action!r} (expected approve, override or rerun)")


def route_after_hitl(state: GraphState) -> str:
    """approve  -> writer
    override -> back to the review step, so the analyst confirms the recalculated result once
    rerun    -> quant (bounded by max_iterations); at the limit the report is finalized as rejected"""
    action = state["human_action"]
    if action == "approve":
        return "writer"
    if action == "override":
        return "hitl"
    if state.get("iteration", 0) >= state.get("max_iterations", 3):
        print("[hitl] Re-run limit reached — finalizing with the last score despite the rejection.")
        return "writer"
    return "quant"