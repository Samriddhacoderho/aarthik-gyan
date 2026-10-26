from risk.risk_agent import run_risk_agent
from graph.queries import fetch_assessment_for_document
from workflow.review import new_event
from workflow.state import GraphState


def quant_node(state: GraphState) -> dict:
    iteration = state.get("iteration", 0) + 1
    rescoring = iteration > 1
    hint = state.get("rerun_hint") if rescoring else None
    print(f"[quant] Running risk scoring (iteration {iteration})...")

    if hint:
        print(f"[quant] Using the analyst's hint: {hint}")

    assessment_id = run_risk_agent(
        state["company_id"], state["company_name"], state["document_hash"],
        force=rescoring,
        analyst_hint=hint,
        allow_overwrite_final=rescoring,   # the analyst asked for this re-run, so it may re-calculate the system numbers
    )
    if assessment_id is None:
        raise RuntimeError(
            f"Risk assessment was not written: no Company '{state['company_id']}' or "
            f"Document with hash '{state['document_hash']}' exists in Neo4j. "
            "Run main.py to ingest the document first."
        )

    # Read back the assessment for THIS company on THIS document, not "the newest one".
    latest = fetch_assessment_for_document(state["company_id"], state["document_hash"])
    if latest is None:
        raise RuntimeError(f"No risk assessment found for {state['company_id']} on this document after scoring.")

    score = {
        "debt_to_equity": latest.get("debt_to_equity"),
        "current_ratio": latest.get("current_ratio"),
        "net_margin": latest.get("net_margin"),
        "risk_level": latest.get("risk_level"),
        "notes": latest.get("notes") or [],
    }

    print(f"[quant] Score: {score['risk_level']} (D/E={score['debt_to_equity']}, "
          f"CR={score['current_ratio']}, margin={score['net_margin']})")

    update = {"risk_score": score, "iteration": iteration, "rerun_hint": None}
    if rescoring:
        # Record what the re-run produced, so the audit trail shows the hint AND its effect.
        update["review_history"] = [
            new_event("rescore", "system", iteration, hint or "", before=state.get("risk_score"), after=score)
        ]
    return update