from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from api.schemas import HealthResponse, ReadinessCheck, ReadinessResponse
from api.settings import settings

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("/live", response_model=HealthResponse)
def live() -> HealthResponse:
    return HealthResponse(service=settings.service_name, version=settings.version)


@router.get("/ready", response_model=ReadinessResponse)
def ready() -> JSONResponse:
    checks: list[ReadinessCheck] = []

    try:
        from graph.neo4j_client import neo4j_client

        neo4j_client.driver.verify_connectivity()
        checks.append(ReadinessCheck(name="neo4j", ok=True))
    except Exception:
        checks.append(
            ReadinessCheck(
                name="neo4j",
                ok=False,
                detail="Neo4j is not reachable or is not configured.",
            )
        )

    try:
        from vectorstore.qdrant_client import vector_store_client

        vector_store_client.client.get_collections()
        checks.append(ReadinessCheck(name="qdrant", ok=True))
    except Exception:
        checks.append(
            ReadinessCheck(
                name="qdrant",
                ok=False,
                detail="Qdrant is not reachable or is not configured.",
            )
        )

    healthy = all(check.ok for check in checks)
    payload = ReadinessResponse(
        status="ready" if healthy else "degraded",
        checks=checks,
    )
    return JSONResponse(
        status_code=200 if healthy else 503,
        content=payload.model_dump(),
    )
