import asyncio

from risk.ratios import extract_financial_metrics, compute_risk_score
from risk.metrics_retriever import metric_queries, merge_unique
from workflow.mcp_client import node_toolbox, NodeToolbox
from workflow.review import new_event
from workflow.state import GraphState

CENTRALITY_TOP_N = 100        
MAX_PRIOR_ASSESSMENTS = 5


def _score_from_entry(entry: dict) -> dict:
    return {
        "debt_to_equity": entry.get("debt_to_equity"),
        "current_ratio": entry.get("current_ratio"),
        "net_margin": entry.get("net_margin"),
        "risk_level": entry.get("risk_level"),
        "notes": entry.get("notes") or [],
    }


async def _calculate_score(tools: NodeToolbox, state: GraphState, hint: str | None) -> dict:
    """Find the numbers (MCP search) -> LLM reads them -> plain rules score them -> save (MCP)."""
    company_id, document_hash = state["company_id"], state["document_hash"]

    chunk_texts = []
    for query in metric_queries([hint] if hint else None):
        hits = await tools.call("retrieve_footnote_context",
                                {"query": query, "document_hash": document_hash, "top_k": 3})
        chunk_texts.extend(hit["text"] for hit in hits)
    context = merge_unique(chunk_texts)

    metrics = await asyncio.to_thread(
        extract_financial_metrics, context, company_hint=state["company_name"], analyst_hint=hint
    )
    risk = compute_risk_score(company_id, metrics)

    saved = await tools.call("save_risk_assessment", {
        "company_id": company_id, "document_hash": document_hash, "risk_level": risk.risk_level,
        "debt_to_equity": risk.debt_to_equity, "current_ratio": risk.current_ratio,
        "net_margin": risk.net_margin, "notes": risk.notes,
    })
    if "error" in saved:
        raise RuntimeError(f"Risk assessment was not written: {saved['error']}")
    return {
        "debt_to_equity": risk.debt_to_equity, "current_ratio": risk.current_ratio,
        "net_margin": risk.net_margin, "risk_level": risk.risk_level, "notes": risk.notes,
    }


def _summarize_prior(entries: list[dict]) -> list[dict]:
    """Earlier assessments of the same company on OTHER documents, using the analyst-approved level when there is one."""
    return [{
        "document": e.get("document_filename"),
        "risk_level": e.get("final_risk_level") or e.get("risk_level"),
        "status": e.get("status"),
        "overridden": bool(e.get("overridden")),
        "created_at": (e.get("created_at") or "")[:10],
    } for e in entries[:MAX_PRIOR_ASSESSMENTS]]


async def quant_node(state: GraphState) -> dict:
    iteration = state.get("iteration", 0) + 1
    rescoring = iteration > 1
    hint = state.get("rerun_hint") if rescoring else None
    company_id, document_hash = state["company_id"], state["document_hash"]
    print(f"[quant] Running risk scoring (iteration {iteration})...")

    if hint:
        print(f"[quant] Using the analyst's hint: {hint}")

    async with node_toolbox("quant") as tools:
        history = await tools.call("get_debt_ratios", {"company_id": company_id})
        entries = [] if "error" in history else history["history"]
        existing = next((e for e in entries if e.get("document_hash") == document_hash), None)
        others = [e for e in entries if e.get("document_hash") != document_hash]

        if existing and not rescoring:
            print(f"[quant] Reusing existing {existing.get('status')} assessment (no LLM call).")
            score = _score_from_entry(existing)
        else:
            score = await _calculate_score(tools, state, hint)

        top = await tools.call("calculate_graph_centrality", {"limit": CENTRALITY_TOP_N})
        rank = next((i + 1 for i, row in enumerate(top) if row["id"] == company_id), None)
        degree = next((row["degree"] for row in top if row["id"] == company_id), None)

    print(f"[quant] Score: {score['risk_level']} (D/E={score['debt_to_equity']}, "
          f"CR={score['current_ratio']}, margin={score['net_margin']})")

    update = {
        "risk_score": score, "iteration": iteration, "rerun_hint": None,
        "quant_context": {
            "prior_assessments": _summarize_prior(others),
            "centrality": {"rank": rank, "degree": degree, "top_n": CENTRALITY_TOP_N},
        },
    }
    if rescoring:
        update["review_history"] = [
            new_event("rescore", "system", iteration, hint or "", before=state.get("risk_score"), after=score)
        ]
    return update
