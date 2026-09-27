from pydantic import BaseModel, Field
from typing import Optional
from langchain_core.output_parsers import PydanticOutputParser



class FinancialMetrics(BaseModel):
    """Numeric figures pulled straight from a document:separate from the qualitative entity graph, since ratios need real numbers, not descriptions."""
    company_name: str = Field(..., description="Name of the company these figures belong to")
    fiscal_year: Optional[str] = Field(None, description="e.g. '2024' or 'FY2024', if stated")
    total_debt: Optional[float] = Field(None, description="Total liabilities / long-term + short-term debt")
    total_equity: Optional[float] = Field(None, description="Total owners'/stockholders' equity")
    current_assets: Optional[float] = Field(None, description="Total current assets")
    current_liabilities: Optional[float] = Field(None, description="Total current liabilities")
    revenue: Optional[float] = Field(None, description="Total revenue / sales revenue for the period")
    net_income: Optional[float] = Field(None, description="Net income for the period")


class RiskScore(BaseModel):
    """The output of the rule-based risk pass, attached to a Company node."""
    company_id: str
    debt_to_equity: Optional[float] = None
    current_ratio: Optional[float] = None
    net_margin: Optional[float] = None
    risk_level: str = Field(..., description="One of: LOW, MEDIUM, HIGH, UNKNOWN")
    notes: list[str] = Field(default_factory=list, description="Human-readable reasons for the score")
    
metrics_parser = PydanticOutputParser(pydantic_object=FinancialMetrics)
