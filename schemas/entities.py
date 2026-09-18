from pydantic import BaseModel, Field
from typing import Literal, Optional, TypedDict
from langchain_core.output_parsers import PydanticOutputParser


class Entity(BaseModel):
    """A single node to be created in the graph."""
    id: str = Field(..., description="A short unique slug for this entity, e.g. 'company_x'")
    name: str = Field(..., description="Human-readable name, e.g. 'Company X Pvt. Ltd.'")
    type: Literal["Company", "Executive", "Subsidiary", "RiskFactor", "Auditor"] = Field(..., description="The category of this entity")
    description: Optional[str] = Field(None, description="One-line context extracted from the document, if any")
    
class Relationship(BaseModel):
    """A directed edge between two entities already listed in `entities`."""
    source_id: str = Field(..., description="id of the source entity")
    target_id: str = Field(..., description="id of the target entity")
    type: Literal["OWNS", "OWES_DEBT_TO", "SUPPLIES_TO", "AUDITED_BY","EMPLOYS", "FLAGGED_FOR", "SUBSIDIARY_OF"] = Field(..., description="The relationship type")
    detail: Optional[str] = Field(None, description="Supporting detail, e.g. 'NPR 40M as of FY2024'")
    

class ExtractionResult(BaseModel):
    """Top-level structured output the LLM must return for one document chunk."""
    entities:list[Entity] = Field(..., description="List of entities extracted from the document")
    relationships:list[Relationship] = Field(..., description="List of relationships between the entities")
    
parser=PydanticOutputParser(pydantic_object=ExtractionResult)