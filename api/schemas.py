from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "UNKNOWN"]
ReviewAction = Literal["approve", "override", "rerun"]


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str
    version: str


class ReadinessCheck(BaseModel):
    name: str
    ok: bool
    detail: str | None = None


class ReadinessResponse(BaseModel):
    status: Literal["ready", "degraded"]
    checks: list[ReadinessCheck]


class DocumentSummary(BaseModel):
    hash: str
    filename: str | None = None
    status: str | None = None
    ingested_at: str | None = None
    entity_count: int | None = None
    relationship_count: int | None = None
    failed_batch_count: int | None = None


class CompanySummary(BaseModel):
    id: str
    name: str | None = None
    description: str | None = None
    relationship_count: int = 0
    assessment_count: int = 0


class LatestAssessment(BaseModel):
    id: str
    risk_level: str | None = None
    status: str | None = None
    final_risk_level: str | None = None
    debt_to_equity: float | None = None
    current_ratio: float | None = None
    net_margin: float | None = None
    document_hash: str | None = None
    document_filename: str | None = None
    approved_by: str | None = None
    approved_at: str | None = None
    overridden: bool | None = None
    created_at: str | None = None


class ReviewEvent(BaseModel):
    id: str | None = None
    at: str | None = None
    action: str | None = None
    reviewer: str | None = None
    iteration: int | None = None
    notes: str | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None


class AssessmentRecord(BaseModel):
    id: str
    risk_level: str | None = None
    final_risk_level: str | None = None
    debt_to_equity: float | None = None
    current_ratio: float | None = None
    net_margin: float | None = None
    final_debt_to_equity: float | None = None
    final_current_ratio: float | None = None
    final_net_margin: float | None = None
    status: str | None = None
    notes: list[str] = Field(default_factory=list)
    final_notes: list[str] = Field(default_factory=list)
    created_at: str | None = None
    approved_by: str | None = None
    approved_at: str | None = None
    overridden: bool | None = None
    edit_notes: str | None = None
    review_count: int | None = None
    document_hash: str | None = None
    document_filename: str | None = None
    review_events: list[ReviewEvent] = Field(default_factory=list)


class DashboardResponse(BaseModel):
    company: CompanySummary
    latest_assessment: AssessmentRecord | None = None
    assessments: list[AssessmentRecord] = Field(default_factory=list)
    documents: list[DocumentSummary] = Field(default_factory=list)
    totals: dict[str, int] = Field(default_factory=dict)


class GraphNode(BaseModel):
    id: str
    name: str | None = None
    type: str | None = None


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str | None = None
    detail: str | None = None


class GraphResponse(BaseModel):
    company_id: str
    depth: int
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    truncated: bool = False


class EvidenceHit(BaseModel):
    text: str
    filename: str | None = None
    score: float


class EvidenceSearchResponse(BaseModel):
    document_hash: str
    query: str
    results: list[EvidenceHit] = Field(default_factory=list)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class AskResponse(BaseModel):
    document_hash: str
    question: str
    answer: str


class UploadResponse(BaseModel):
    job_id: str
    status: str
    filename: str
    size_bytes: int
    document_hash: str
    persistent: bool = False
    message: str = "Ingestion jobs are held in this API process only."


class BatchProgress(BaseModel):
    index: int
    status: Literal["pending", "running", "cached", "completed", "failed"] = "pending"
    entities: int | None = None
    cached: bool = False
    error: str | None = None


class JobResponse(BaseModel):
    job_id: str
    status: str
    filename: str
    document_hash: str
    created_at: str
    updated_at: str
    stage: str = "queued"
    batch_total: int = 0
    batches: list[BatchProgress] = Field(default_factory=list)
    document: DocumentSummary | None = None
    error: str | None = None
    persistent: bool = False


class DeleteDocumentResponse(BaseModel):
    document_hash: str
    filename: str | None = None
    deleted_entities: int = 0
    deleted_relationships: int = 0
    deleted_assessments: int = 0
    deleted_points: int = 0
    upload_removed: bool = False


class AnalysisStartRequest(BaseModel):
    company_id: str = Field(min_length=1, max_length=200)
    document_hash: str = Field(min_length=1, max_length=200)
    reviewer: str = Field(default="analyst", min_length=1, max_length=120)
    max_iterations: int = Field(default=3, ge=1, le=5)


class ReviewRequest(BaseModel):
    action: ReviewAction
    notes: str = Field(default="", max_length=4000)
    edited_score: dict[str, float | None] | None = None
    risk_level: RiskLevel | None = None

    @model_validator(mode="after")
    def validate_review(self) -> "ReviewRequest":
        if self.action == "override":
            has_number = bool(self.edited_score) and any(
                value is not None for value in self.edited_score.values()
            )
            if not has_number and not self.risk_level:
                raise ValueError("An override needs at least one corrected value or a risk level.")
        if self.action == "rerun" and not self.notes.strip():
            raise ValueError("A re-run needs a hint for the analysis.")
        return self


class ReviewPayload(BaseModel):
    company_name: str
    auditor_findings: list[str] = Field(default_factory=list)
    risk_score: dict[str, Any] = Field(default_factory=dict)
    final_score: dict[str, Any] | None = None
    quant_context: dict[str, Any] | None = None
    iteration: int = 0
    reruns_left: int = 0
    review_history: list[dict[str, Any]] = Field(default_factory=list)


class AnalysisResponse(BaseModel):
    analysis_id: str
    status: Literal["awaiting_review", "completed", "failed", "running"]
    company_id: str
    company_name: str
    document_hash: str
    document_filename: str | None = None
    reviewer: str
    iteration: int = 0
    max_iterations: int = 3
    review: ReviewPayload | None = None
    approval_record: dict[str, Any] | None = None
    report_url: str | None = None
    error: str | None = None
    persistent: bool = False


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
