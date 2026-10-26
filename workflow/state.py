import operator
from typing import Annotated, TypedDict, Optional


class GraphState(TypedDict):
    company_id: str
    company_name: str
    document_hash: str
    reviewer: Optional[str]              # who is doing the review (written into the audit trail)

    auditor_findings: Optional[list[str]]
    risk_score: Optional[dict]           # the latest score the SYSTEM calculated
    final_score: Optional[dict]          # the analyst's override (None = use risk_score as is)

    human_action: Optional[str]          # last review action: "approve" | "override" | "rerun"
    rerun_hint: Optional[str]            # the analyst's guidance for the next re-score

    # Append-only audit trail. The reducer (operator.add) means nodes can only ADD events:
    # a later "approve" can never erase an earlier override or note.
    review_history: Annotated[list[dict], operator.add]

    final_report_path: Optional[str]
    approval_record: Optional[dict]

    iteration: int                       # how many times the quant step has scored
    max_iterations: int