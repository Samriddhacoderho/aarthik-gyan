from pydantic import BaseModel
from typing import Optional
from schemas.audit import ApprovalRecord


class ReportSection(BaseModel):
    heading: str
    body: str


class RiskReportData(BaseModel):
    company_name: str
    company_id: str
    risk_level: str
    debt_to_equity: Optional[float]
    current_ratio: Optional[float]
    net_margin: Optional[float]
    sections: list[ReportSection]
    approval_record: Optional[ApprovalRecord] = None