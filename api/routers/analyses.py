from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, status
from fastapi.responses import FileResponse

from api.schemas import AnalysisResponse, AnalysisStartRequest, ReviewRequest
from api.services import analysis_service

router = APIRouter(prefix="/api/analyses", tags=["analyses"])


@router.get("", response_model=list[AnalysisResponse])
def list_analyses() -> list[AnalysisResponse]:
    return analysis_service.list_sessions()


@router.post(
    "",
    response_model=AnalysisResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_analysis(request: AnalysisStartRequest) -> AnalysisResponse:
    return await analysis_service.start_analysis(
        company_id=request.company_id,
        document_hash=request.document_hash,
        reviewer=request.reviewer,
        max_iterations=request.max_iterations,
    )


@router.get("/{analysis_id}", response_model=AnalysisResponse)
def get_analysis(analysis_id: str) -> AnalysisResponse:
    return analysis_service.get_session(analysis_id)


@router.post("/{analysis_id}/review", response_model=AnalysisResponse)
async def review_analysis(analysis_id: str, request: ReviewRequest) -> AnalysisResponse:
    return await analysis_service.submit_review(analysis_id, request)


@router.get("/{analysis_id}/report")
def download_report(analysis_id: str) -> FileResponse:
    path = analysis_service.get_report_path(analysis_id)
    return FileResponse(
        path=path,
        media_type="application/pdf",
        filename=Path(path).name,
    )
