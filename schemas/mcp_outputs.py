from pydantic import BaseModel
from typing import Optional


class CompanyProfile(BaseModel):
    id: str
    name: Optional[str] = None
    description: Optional[str] = None
    relationship_count: int = 0
    # NOTE: no risk fields here on purpose. The auditor must not see any risk score.


class ConnectedEntity(BaseModel):
    id: str
    name: Optional[str] = None
    type: Optional[str] = None
    relationship_path: list[str] = []


class CentralityResult(BaseModel):
    id: str
    name: Optional[str] = None
    type: Optional[str] = None
    degree: int


class RiskAssessmentEntry(BaseModel):
    debt_to_equity: Optional[float] = None
    current_ratio: Optional[float] = None
    net_margin: Optional[float] = None
    risk_level: Optional[str] = None
    notes: list[str] = []
    status: Optional[str] = None
    created_at: Optional[str] = None
    final_risk_level: Optional[str] = None      # the analyst-approved level, if the assessment was reviewed
    overridden: Optional[bool] = None
    document_hash: Optional[str] = None
    document_filename: Optional[str] = None


class DebtRatioHistory(BaseModel):
    company_id: str
    assessment_count: int
    history: list[RiskAssessmentEntry]


class SavedAssessment(BaseModel):
    assessment_id: str
    risk_level: str


class FootnoteHit(BaseModel):
    text: str
    filename: Optional[str] = None
    score: float


class ToolError(BaseModel):
    error: str