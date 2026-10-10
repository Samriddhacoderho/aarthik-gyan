import uuid
from langgraph.types import Command
from workflow.workflow import build_workflow
from graph.neo4j_client import neo4j_client
from vectorstore.qdrant_client import vector_store_client

COMPANY_ID = "tesla_inc"
COMPANY_NAME = "Tesla, Inc."
DOCUMENT_HASH = "paste-the-document-hash-here"  


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
    edited = {}
    for field in ("risk_level", "debt_to_equity", "current_ratio", "net_margin"):
        raw = input(f"  {field} [{interrupt_payload['risk_score'].get(field)}]: ").strip()
        if raw:
            edited[field] = raw
    notes = input("Reason for rejection/edit: ").strip()
    return {"decision": "reject", "edited_score": edited or None, "notes": notes}


def run_analysis():
    workflow = build_workflow()
    thread_config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    initial_state = {
        "company_id": COMPANY_ID,
        "company_name": COMPANY_NAME,
        "document_hash": DOCUMENT_HASH,
        "iteration": 0,
        "max_iterations": 3,
    }

    result = workflow.invoke(initial_state, config=thread_config)

    while "__interrupt__" in result:
        interrupt_obj = result["__interrupt__"][0]
        human_response = prompt_human(interrupt_obj.value)
        result = workflow.invoke(Command(resume=human_response), config=thread_config)

    print(f"\n[analyze] Done. Report at: {result.get('final_report_path')}")
    print(f"[analyze] Approval record: {result.get('approval_record')}")


if __name__ == "__main__":
    neo4j_client.verify_connection()
    vector_store_client.verify_connection()
    run_analysis()