import asyncio
import math
import sys
import uuid

from langgraph.types import Command
from workflow.review import describe_event
from workflow.workflow import build_workflow
from graph.neo4j_client import neo4j_client
from vectorstore.qdrant_client import vector_store_client

DOCUMENT_FILENAME = "Brightwater_Industrial_Systems_FY2025_Annual_Report.pdf"

FIND_DOCUMENT_QUERY = """
MATCH (d:Document {filename: $filename})
WHERE d.status IN ['completed', 'partial']
RETURN d.hash AS hash
ORDER BY d.ingested_at DESC
LIMIT 1
"""

FIND_PRIMARY_COMPANY_QUERY = """
MATCH (d:Document {hash: $hash})-[:MENTIONS]->(c:Entity {type: 'Company'})
OPTIONAL MATCH (c)-[r:RELATION]-()
WHERE r.source_document = $hash
WITH c, count(r) AS degree
RETURN c.id AS id, c.name AS name, degree
ORDER BY degree DESC, c.id
LIMIT 1
"""

NUMBER_FIELDS = ("debt_to_equity", "current_ratio", "net_margin")
LEVELS = ("LOW", "MEDIUM", "HIGH", "UNKNOWN")


def resolve_target(filename: str) -> tuple[str, str, str]:
    """Returns (company_id, company_name, document_hash) for an ingested document,
    so nothing has to be hard-coded or kept in sync by hand."""
    docs = neo4j_client.run_query(FIND_DOCUMENT_QUERY, {"filename": filename})
    if not docs:
        raise SystemExit(f"'{filename}' has not been ingested yet (or failed). Run main.py first.")
    document_hash = docs[0]["hash"]

    companies = neo4j_client.run_query(FIND_PRIMARY_COMPANY_QUERY, {"hash": document_hash})
    if not companies:
        raise SystemExit(f"No Company entity was found for '{filename}'.")

    company = companies[0]
    print(f"[analyze] Target: {company['name']} ({company['id']}) from '{filename}'")
    return company["id"], company["name"], document_hash


def _show_score(label: str, score: dict) -> None:
    show = lambda v: "n/a" if v is None else v
    print(f"{label}")
    print(f"    risk level      : {score.get('risk_level')}")
    print(f"    debt-to-equity  : {show(score.get('debt_to_equity'))}")
    print(f"    current ratio   : {show(score.get('current_ratio'))}")
    print(f"    net margin      : {show(score.get('net_margin'))}")
    for note in score.get("notes") or []:
        print(f"      - {note}")


def _show_quant_context(context: dict | None) -> None:
    """Extra facts the quant step gathered through MCP. They are context for the analyst; they are NOT in the score."""
    if not context:
        return
    print("\nContext (not part of the score):")
    prior = context.get("prior_assessments") or []
    if prior:
        print("  Earlier assessments of this company:")
        for p in prior:
            tag = " (analyst-set)" if p.get("overridden") else ""
            print(f"    - {p.get('document')}: {p.get('risk_level')}{tag}, {p.get('status')}, {p.get('created_at')}")
    else:
        print("  No earlier assessments of this company on other documents.")
    c = context.get("centrality") or {}
    if c.get("rank") is not None:
        print(f"  Graph position: #{c['rank']} by number of direct relationships ({c['degree']} relationships).")
    else:
        print(f"  Graph position: not among the top {c.get('top_n')} most-connected entities.")


def _ask_required(prompt: str) -> str:
    while True:
        text = input(prompt).strip()
        if text:
            return text
        print("This cannot be empty: it goes into the audit trail.")


def _ask_overrides(current: dict) -> tuple[dict, str | None]:
    """Asks for corrected numbers. Blank = keep the current value. Returns (changed_fields, risk_level)."""
    print("Type the corrected values. Press Enter to keep the value in brackets.")
    edited = {}
    for field in NUMBER_FIELDS:
        while True:
            raw = input(f"  {field} [{current.get(field)}]: ").strip().replace(",", "")
            if not raw:
                break
            try:
                value = float(raw)
            except ValueError:
                print(f"    '{raw}' is not a number, try again.")
                continue
            if not math.isfinite(value):
                print("    Please type a normal number.")
                continue
            if value != current.get(field):
                edited[field] = value
            break

    level = None
    while True:
        raw = input("  risk level (Enter = recalculate from the numbers; or LOW/MEDIUM/HIGH): ").strip().upper()
        if not raw:
            break
        if raw in LEVELS:
            level = raw
            break
        print(f"    Choose one of {', '.join(LEVELS)}, or press Enter.")
    return edited, level


def prompt_human(payload: dict) -> dict:
    current = payload.get("final_score") or payload["risk_score"]
    reruns_left = payload.get("reruns_left", 0)

    print()
    print("=" * 64)
    print(f"Human Review Required: {payload['company_name']}   (scoring round {payload['iteration']})")
    print("=" * 64)
    print("\nAuditor findings:")
    for finding in payload["auditor_findings"]:
        print(f"  - {finding}")

    print()
    _show_score("Score calculated by the system:", payload["risk_score"])
    if payload.get("final_score"):
        print()
        _show_score(">>> YOUR OVERRIDE, waiting for your confirmation:", payload["final_score"])

    _show_quant_context(payload.get("quant_context"))

    if payload.get("review_history"):
        print("\nReview so far:")
        for event in payload["review_history"]:
            print(f"  [{event['at'][:19].replace('T', ' ')}] {event.get('reviewer')}: {describe_event(event)}")

    print("\nWhat do you want to do?")
    print("  [a] Approve what is shown above")
    print("  [o] Override: type corrected numbers (the risk level is recalculated)")
    if reruns_left > 0:
        print(f"  [r] Re-run the scoring with a hint for the system ({reruns_left} re-run(s) left)")

    while True:
        choice = input("Your choice: ").strip().lower()

        if choice == "a":
            return {"action": "approve", "notes": input("Any notes? (optional): ").strip()}

        if choice == "o":
            edited, level = _ask_overrides(current)
            if not edited and not level:
                print("Nothing was changed. Pick again.")
            reason = _ask_required("  Reason for the override (required): ")
            return {"action": "override", "edited_score": edited, "risk_level": level, "notes": reason}

        if choice == "r" and reruns_left > 0:
            print("Tell the system where to look or what was wrong, for example:")
            print('  "current assets and current liabilities are on the consolidated balance sheet"')
            hint = _ask_required("  Hint (required): ")
            return {"action": "rerun", "notes": hint}

        print("Please type a, o" + (" or r." if reruns_left > 0 else "."))


async def run_analysis(filename: str = DOCUMENT_FILENAME):
    company_id, company_name, document_hash = resolve_target(filename)
    reviewer = input("Your name for the audit trail [analyst]: ").strip() or "analyst"

    workflow = build_workflow()
    thread_config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    initial_state = {
        "company_id": company_id,
        "company_name": company_name,
        "document_hash": document_hash,
        "reviewer": reviewer,
        "review_history": [],
        "final_score": None,
        "iteration": 0,
        "max_iterations": 3,
    }

    result = await workflow.ainvoke(initial_state, config=thread_config)

    while "__interrupt__" in result:
        human_response = prompt_human(result["__interrupt__"][0].value)
        result = await workflow.ainvoke(Command(resume=human_response), config=thread_config)

    record = result.get("approval_record") or {}
    print(f"\n[analyze] Done. Report at: {result.get('final_report_path')}")
    print(f"[analyze] Decision: {record.get('decision')} by {record.get('approved_by')}"
          f"{' (numbers set by the analyst)' if record.get('overridden') else ''}")
    print(f"[analyze] Final score: {record.get('final_score')}")
    print("[analyze] Review history:")
    for event in record.get("review_history", []):
        print(f"    {event['at'][:19].replace('T', ' ')}  {event.get('reviewer')}: {describe_event(event)}")


if __name__ == "__main__":
    neo4j_client.verify_connection()
    vector_store_client.verify_connection()
    asyncio.run(run_analysis(sys.argv[1] if len(sys.argv) > 1 else DOCUMENT_FILENAME))