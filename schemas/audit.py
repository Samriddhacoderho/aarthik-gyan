from pydantic import BaseModel, Field
from typing import Optional


class ApprovalRecord(BaseModel):
    company_id: str
    document_hash: str
    decision: str
    approved_by: str = "analyst"
    approved_at: str
    original_score: dict                # the first score the system proposed
    final_score: dict                   # what was approved (the analyst's override, if there was one)
    edit_notes: Optional[str] = None    # every note written by a person, joined
    iteration_count: int
    overridden: bool = False            # True if the final numbers were typed by the analyst
    review_history: list[dict] = Field(default_factory=list)   # the full audit trail, oldest first