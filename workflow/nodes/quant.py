from risk.risk_agent import run_risk_agent
from graph.queries import fetch_debt_ratio_history
from workflow.state import GraphState


def quant_node(state: GraphState) -> dict:
    iteration = state.get("iteration", 0) + 1
    print(f"[quant] Running risk scoring (iteration {iteration})...")

    if state.get("human_notes"):
        print(f"[quant] Incorporating analyst notes from previous rejection: {state['human_notes']}")

    run_risk_agent(state["company_id"], state["company_name"], state["document_hash"])

    history = fetch_debt_ratio_history(state["company_id"])
    if not history:
        raise RuntimeError(f"No risk assessment found for {state['company_id']} after scoring.")

    latest = history[0]
    score = {
        "debt_to_equity": latest.get("debt_to_equity"),
        "current_ratio": latest.get("current_ratio"),
        "net_margin": latest.get("net_margin"),
        "risk_level": latest.get("risk_level"),
        "notes": latest.get("notes", []),
    }

    print(f"[quant] Score: {score['risk_level']} (D/E={score['debt_to_equity']}, "
          f"CR={score['current_ratio']}, margin={score['net_margin']})")

    return {"risk_score": score, "iteration": iteration}