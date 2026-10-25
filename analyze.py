import asyncio
import sys
import uuid

from langgraph.types import Command
from workflow.workflow import build_workflow
from graph.neo4j_client import neo4j_client
from vectorstore.qdrant_client import vector_store_client

# Which ingested document to analyze. Override on the command line:
#   python analyze.py "Some_Other_Report.pdf"
DOCUMENT_FILENAME = "Brightwater_Industrial_Systems_FY2025_Annual_Report.pdf"

FIND_DOCUMENT_QUERY = """
MATCH (d:Document {filename: $filename})
WHERE d.status IN ['completed', 'partial']
RETURN d.hash AS hash
ORDER BY d.ingested_at DESC
LIMIT 1
"""

# Same rule main.py uses (pick_primary_company): the Company with the most relationships
# stated in THIS document. Ties are broken by id so the result is always the same.
FIND_PRIMARY_COMPANY_QUERY = """
MATCH (d:Document {hash: $hash})-[:MENTIONS]->(c:Entity {type: 'Company'})
OPTIONAL MATCH (c)-[r:RELATION]-()
WHERE r.source_document = $hash
WITH c, count(r) AS degree
RETURN c.id AS id, c.name AS name, degree
ORDER BY degree DESC, c.id
LIMIT 1
"""


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


def prompt_human(interrupt_payload: dict) -> dict:
    print(f"Human Review Required — {interrupt_payload['company_name']}")
    print("=" * 60)
    print("\nAuditor findings:")
    for f in interrupt_payload["auditor_findings"]:
        print(f"  - {f}")
    print(f"\nProposed risk score: {interrupt_payload['risk_score']}")
    print(f"(Review iteration {interrupt_payload['iteration']})\n")

    decision = input("Approve this assessment? (y/n): ").strip().lower()
    if decision == "y":
        return {"decision": "approve", "edited_score": None, "notes": input("Any notes? (optional): ")}

    print("Enter corrected values (leave blank to keep as-is):")
    current = interrupt_payload["risk_score"]
    edited = {}
    for field in ("risk_level", "debt_to_equity", "current_ratio", "net_margin"):
        while True:
            raw = input(f"  {field} [{current.get(field)}]: ").strip()
            if not raw:
                edited[field] = current.get(field)
                break
            if field == "risk_level":
                edited[field] = raw.upper()
                break
            try:
                edited[field] = float(raw)
                break
            except ValueError:
                print(f"    '{raw}' is not a number, try again.")
    notes = input("Reason for rejection/edit: ").strip()
    return {"decision": "reject", "edited_score": edited, "notes": notes}


async def run_analysis(filename: str = DOCUMENT_FILENAME):
    company_id, company_name, document_hash = resolve_target(filename)
    workflow = build_workflow()
    thread_config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    initial_state = {
        "company_id": company_id,
        "company_name": company_name,
        "document_hash": document_hash,
        "iteration": 0,
        "max_iterations": 3,
    }

    result = await workflow.ainvoke(initial_state, config=thread_config)

    while "__interrupt__" in result:
        human_response = prompt_human(result["__interrupt__"][0].value)
        result = await workflow.ainvoke(Command(resume=human_response), config=thread_config)

    print(f"\n[analyze] Done. Report at: {result.get('final_report_path')}")
    print(f"[analyze] Approval record: {result.get('approval_record')}")


if __name__ == "__main__":
    neo4j_client.verify_connection()
    vector_store_client.verify_connection()
    asyncio.run(run_analysis(sys.argv[1] if len(sys.argv) > 1 else DOCUMENT_FILENAME))