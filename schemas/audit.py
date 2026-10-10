from pydantic import BaseModel
from typing import Optional


class ApprovalRecord(BaseModel):
    company_id: str
    document_hash: str
    decision: str                       
    approved_by: str = "analyst"       
    approved_at: str
    original_score: dict
    final_score: dict
    edit_notes: Optional[str] = None
    iteration_count: int