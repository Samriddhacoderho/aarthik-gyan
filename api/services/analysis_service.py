"""Analysis orchestration wrapper.

This adapter deliberately reuses the existing V3 LangGraph workflow and its
``MemorySaver`` checkpointer. It does not reimplement Auditor/Quant/HITL/Writer
logic.

Sessions live in this Python process only. A restart loses them. The API
response says ``persistent: false``.
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from api.errors import ApiError
from api.schemas import AnalysisResponse, ReviewPayload, ReviewRequest
from api.services import graph_service
from api.settings import ROOT_DIR, settings


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AnalysisSession:
    analysis_id: str
    thread_id: str
    company_id: str
    company_name: str
    document_hash: str
    document_filename: str | None
    reviewer: str
    max_iterations: int
    status: str = "running"
    iteration: int = 0
    review: ReviewPayload | None = None
    approval_record: dict[str, Any] | None = None
    report_path: str | None = None
    error: str | None = None
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)


_SESSIONS: dict[str, AnalysisSession] = {}
_SESSIONS_LOCK = threading.Lock()
_BACKGROUND_TASKS: set[asyncio.Task[None]] = set()


def _track(coro: Any) -> None:
    """Keep a strong reference to a background task until it finishes.

    Without this set, asyncio may garbage-collect a task mid-flight, and an
    unhandled exception would be silent. The task functions catch and record
    their own failures in the session.
    """

    task = asyncio.create_task(coro)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)


def _public(session: AnalysisSession) -> AnalysisResponse:
    return AnalysisResponse(
        analysis_id=session.analysis_id,
        status=session.status,  # type: ignore[arg-type]
        company_id=session.company_id,
        company_name=session.company_name,
        document_hash=session.document_hash,
        document_filename=session.document_filename,
        reviewer=session.reviewer,
        iteration=session.iteration,
        max_iterations=session.max_iterations,
        review=session.review,
        approval_record=session.approval_record,
        report_url=f"/api/analyses/{session.analysis_id}/report"
        if session.status == "completed"
        else None,
        error=session.error,
        persistent=False,
    )


def _get(session_id: str) -> AnalysisSession:
    with _SESSIONS_LOCK:
        session = _SESSIONS.get(session_id)
    if session is None:
        raise ApiError(404, "analysis_not_found", "No analysis exists with that id in this API process.")
    return session


def list_sessions() -> list[AnalysisResponse]:
    with _SESSIONS_LOCK:
        sessions = sorted(_SESSIONS.values(), key=lambda item: item.created_at, reverse=True)
        return [_public(session) for session in sessions]


def get_session(session_id: str) -> AnalysisResponse:
    return _public(_get(session_id))


def _validate_target(company_id: str, document_hash: str) -> tuple[str, str | None]:
    document = graph_service.get_document(document_hash)
    if document.status not in ("completed", "partial"):
        raise ApiError(
            409,
            "document_not_ready",
            f"Document status is '{document.status or 'unknown'}'. Ingest it before running an analysis.",
        )
    company = graph_service.get_company(company_id)
    return company.name or company_id, document.filename


def _report_file(session: AnalysisSession) -> Path:
    if not session.report_path:
        raise ApiError(404, "report_not_ready", "No report has been generated for this analysis.")
    path = Path(session.report_path)
    if not path.is_absolute():
        path = ROOT_DIR / path
    resolved = path.resolve()
    allowed_resolved = settings.report_path.resolve()
    if not resolved.is_file() or not resolved.is_relative_to(allowed_resolved):
        raise ApiError(404, "report_not_found", "The report file is not available.")
    return resolved


def get_report_path(session_id: str) -> Path:
    session = _get(session_id)
    if session.status != "completed":
        raise ApiError(409, "report_not_ready", "The analysis has not been approved yet.")
    return _report_file(session)


async def _consume_result(session: AnalysisSession, result: dict[str, Any]) -> None:
    interrupts = result.get("__interrupt__") or []
    if interrupts:
        payload = interrupts[0].value
        try:
            review = ReviewPayload.model_validate(payload)
        except Exception as exc:
            session.status = "failed"
            session.error = "The workflow returned an unexpected review payload."
            session.updated_at = _now()
            raise ApiError(502, "invalid_workflow_payload", session.error) from exc
        session.review = review
        session.iteration = review.iteration
        session.status = "awaiting_review"
        session.updated_at = _now()
        return

    approval = result.get("approval_record")
    if approval:
        session.approval_record = approval
        session.report_path = result.get("final_report_path")
        session.status = "completed"
        session.updated_at = _now()
        # Verify the file now, before telling the browser the approval succeeded.
        _report_file(session)
        return

    session.status = "failed"
    session.error = "The workflow finished without a review checkpoint or an approval record."
    session.updated_at = _now()
    raise ApiError(502, "invalid_workflow_result", session.error)


async def _run_initial(session: AnalysisSession, initial_state: dict[str, Any]) -> None:
    async with session.lock:
        try:
            from workflow.workflow import build_workflow

            result = await build_workflow().ainvoke(
                initial_state,
                config={"configurable": {"thread_id": session.thread_id}},
            )
            await _consume_result(session, result)
        except ApiError as exc:
            if session.status != "failed":
                session.status = "failed"
                session.error = exc.message
        except Exception as exc:
            session.status = "failed"
            session.error = f"Analysis failed ({type(exc).__name__}). Check the backend logs."
        finally:
            session.updated_at = _now()


async def _run_review(session: AnalysisSession, payload: dict[str, Any]) -> None:
    async with session.lock:
        try:
            from langgraph.types import Command
            from workflow.workflow import build_workflow

            result = await build_workflow().ainvoke(
                Command(resume=payload),
                config={"configurable": {"thread_id": session.thread_id}},
            )
            await _consume_result(session, result)
        except ApiError as exc:
            if session.status != "failed":
                session.status = "failed"
                session.error = exc.message
        except Exception as exc:
            session.status = "failed"
            session.error = f"Review failed ({type(exc).__name__}). Check the backend logs."
        finally:
            session.updated_at = _now()


async def start_analysis(
    company_id: str,
    document_hash: str,
    reviewer: str = "analyst",
    max_iterations: int = 3,
) -> AnalysisResponse:
    company_name, document_filename = _validate_target(company_id, document_hash)
    analysis_id = f"an_{uuid.uuid4().hex[:12]}"
    thread_id = str(uuid.uuid4())
    session = AnalysisSession(
        analysis_id=analysis_id,
        thread_id=thread_id,
        company_id=company_id,
        company_name=company_name,
        document_hash=document_hash,
        document_filename=document_filename,
        reviewer=reviewer,
        max_iterations=max_iterations,
    )

    try:
        from workflow.workflow import build_workflow  # noqa: F401
    except Exception as exc:
        raise ApiError(
            503,
            "workflow_unavailable",
            "The analysis workflow is unavailable. Check backend configuration.",
        ) from exc

    with _SESSIONS_LOCK:
        _SESSIONS[analysis_id] = session

    initial_state = {
        "company_id": company_id,
        "company_name": company_name,
        "document_hash": document_hash,
        "reviewer": reviewer or "analyst",
        "review_history": [],
        "final_score": None,
        "iteration": 0,
        "max_iterations": max_iterations,
    }

    # Run the graph in the background so the browser can poll the real session
    # status. The interrupt is preserved by the workflow's MemorySaver.
    _track(_run_initial(session, initial_state))
    return _public(session)


async def submit_review(session_id: str, request: ReviewRequest) -> AnalysisResponse:
    session = _get(session_id)
    if session.status != "awaiting_review":
        raise ApiError(
            409,
            "review_not_pending",
            f"Analysis is '{session.status}', not awaiting review.",
        )

    payload: dict[str, Any] = {
        "action": request.action,
        "notes": request.notes.strip(),
    }
    if request.action == "override":
        payload["edited_score"] = request.edited_score or {}
        payload["risk_level"] = request.risk_level
    if request.action == "rerun" and not request.notes.strip():
        raise ApiError(422, "rerun_hint_required", "A re-run needs a hint for the analysis.")

    async with session.lock:
        if session.status != "awaiting_review" or session.review is None:
            raise ApiError(
                409,
                "review_not_pending",
                f"Analysis is '{session.status}', not awaiting review.",
            )
        try:
            from langgraph.types import Command  # noqa: F401
            from workflow.workflow import build_workflow  # noqa: F401
        except Exception as exc:
            raise ApiError(
                503,
                "workflow_unavailable",
                "The analysis workflow is unavailable. Check backend configuration.",
            ) from exc

        session.status = "running"
        session.updated_at = _now()

    _track(_run_review(session, payload))
    return _public(session)
