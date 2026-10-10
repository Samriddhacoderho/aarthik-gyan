from typing import TypedDict, Optional


class GraphState(TypedDict):
    company_id: str
    company_name: str
    document_hash: str

    auditor_findings: Optional[list[str]]
    risk_score: Optional[dict]          

    human_decision: Optional[str]       
    human_edited_score: Optional[dict]   
    human_notes: Optional[str]

    final_report_path: Optional[str]
    approval_record: Optional[dict]

    iteration: int                     
    max_iterations: int