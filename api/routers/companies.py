from __future__ import annotations

from fastapi import APIRouter, Query

from api.schemas import (
    AssessmentRecord,
    CompanySummary,
    DashboardResponse,
    GraphResponse,
)
from api.services import graph_service

router = APIRouter(prefix="/api/companies", tags=["companies"])


@router.get("", response_model=list[CompanySummary])
def list_companies() -> list[CompanySummary]:
    return graph_service.list_companies()


@router.get("/{company_id}", response_model=CompanySummary)
def get_company(company_id: str) -> CompanySummary:
    return graph_service.get_company(company_id)


@router.get("/{company_id}/dashboard", response_model=DashboardResponse)
def get_dashboard(company_id: str) -> DashboardResponse:
    return graph_service.get_dashboard(company_id)


@router.get("/{company_id}/assessments", response_model=list[AssessmentRecord])
def get_assessments(company_id: str) -> list[AssessmentRecord]:
    graph_service.get_company(company_id)
    return graph_service.get_assessments(company_id)


@router.get("/{company_id}/graph", response_model=GraphResponse)
def get_graph(
    company_id: str,
    depth: int = Query(default=1, ge=1, le=2),
) -> GraphResponse:
    return graph_service.get_graph(company_id, depth)
