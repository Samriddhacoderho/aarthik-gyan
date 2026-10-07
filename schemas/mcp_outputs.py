from pydantic import BaseModel
from typing import Optional


class CompanyProfile(BaseModel):
    id: str
    name: Optional[str] = None
    description: Optional[str] = None
    risk_level: Optional[str] = None
    debt_to_equity: Optional[float] = None
    current_ratio: Optional[float] = None
    net_margin: Optional[float] = None
    assessment_status: Optional[str] = None
    assessment_date: Optional[str] = None


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


class DebtRatioHistory(BaseModel):
    company_id: str
    assessment_count: int
    history: list[RiskAssessmentEntry]


class FootnoteHit(BaseModel):
    text: str
    filename: Optional[str] = None
    score: float


class ToolError(BaseModel):
    error: str