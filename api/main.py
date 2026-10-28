from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from api.errors import ApiError
from api.routers import analyses, companies, documents, health
from api.settings import ROOT_DIR, settings

logger = logging.getLogger("aarthik.api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.ensure_runtime_dirs()
    yield


def _error(status_code: int, code: str, message: str, details=None) -> JSONResponse:
    body = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=body)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Aarthik Gyan API",
        version=settings.version,
        description="Browser-facing adapter over the existing V3 GraphRAG backend.",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Accept"],
    )

    @app.exception_handler(ApiError)
    async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
        return _error(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Do not echo request values back: they can contain private filenames or
        # other user data.
        details = [
            {
                "loc": list(item.get("loc", [])),
                "msg": item.get("msg", "Invalid value."),
                "type": item.get("type", "value_error"),
            }
            for item in exc.errors()
        ]
        return _error(422, "validation_error", "Request validation failed.", details)

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled API error: %s", type(exc).__name__)
        return _error(500, "internal_error", "An unexpected server error occurred.")

    app.include_router(health.router)
    app.include_router(documents.router)
    app.include_router(companies.router)
    app.include_router(analyses.router)

    # Serve a production frontend build when it exists. The Vite dev server is
    # still the normal development path and proxies /api to this app.
    frontend_dist = ROOT_DIR / "frontend" / "dist"
    index_file = frontend_dist / "index.html"
    if index_file.is_file():
        assets_dir = frontend_dist / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str) -> FileResponse:
            if full_path == "api" or full_path.startswith("api/"):
                raise ApiError(404, "not_found", "API route not found.")
            candidate = (frontend_dist / full_path).resolve()
            root = frontend_dist.resolve()
            if candidate.is_file() and candidate.is_relative_to(root):
                return FileResponse(candidate)
            return FileResponse(index_file)

    return app


app = create_app()
