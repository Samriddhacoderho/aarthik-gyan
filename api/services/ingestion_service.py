"""Upload validation and in-process ingestion jobs.

V3 ingestion is a synchronous, stateful pipeline. This service wraps
``main.ingest`` without changing it and serializes ingestion jobs so two
uploads cannot mutate the graph at the same time.

Jobs are intentionally ephemeral: they live in this Python process only.
Restarting the API loses job progress. The response says so explicitly.
"""

from __future__ import annotations

import hashlib
import re
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from api.errors import ApiError
from api.settings import settings


_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_INGEST_LOCK = threading.Lock()
_JOBS_LOCK = threading.Lock()
_JOBS: dict[str, "IngestJob"] = {}

_ACTIVE_STATUSES = {"queued", "running"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_filename(name: str | None) -> str:
    candidate = Path(name or "document.pdf").name
    candidate = _SAFE_NAME.sub("_", candidate).strip("._-")
    if not candidate:
        candidate = "document.pdf"
    if not candidate.lower().endswith(".pdf"):
        candidate += ".pdf"
    return candidate[:180]


def _batch_entry(index: int) -> dict[str, Any]:
    return {
        "index": index,
        "status": "pending",
        "entities": None,
        "cached": False,
        "error": None,
    }


@dataclass
class IngestJob:
    job_id: str
    filename: str
    document_hash: str
    path: Path
    status: str = "queued"
    stage: str = "queued"
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    batch_total: int = 0
    batches: list[dict[str, Any]] = field(default_factory=list)
    document: dict[str, Any] | None = None
    error: str | None = None


def _job_dict(job: IngestJob) -> dict[str, Any]:
    return {
        "job_id": job.job_id,
        "status": job.status,
        "stage": job.stage,
        "filename": job.filename,
        "document_hash": job.document_hash,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "batch_total": job.batch_total,
        "batches": [dict(batch) for batch in job.batches],
        "document": job.document,
        "error": job.error,
        "persistent": False,
    }


def get_job(job_id: str) -> dict[str, Any]:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            raise ApiError(404, "job_not_found", "No ingestion job exists with that id in this API process.")
        return _job_dict(job)


def list_jobs() -> list[dict[str, Any]]:
    with _JOBS_LOCK:
        jobs = sorted(_JOBS.values(), key=lambda item: item.created_at, reverse=True)
        return [_job_dict(job) for job in jobs]


def active_job_for_hash(document_hash: str) -> dict[str, Any] | None:
    with _JOBS_LOCK:
        for job in _JOBS.values():
            if job.document_hash == document_hash and job.status in _ACTIVE_STATUSES:
                return _job_dict(job)
    return None


def forget_jobs(document_hash: str) -> int:
    """Drop in-memory jobs for a document that has been deleted."""
    with _JOBS_LOCK:
        stale = [job_id for job_id, job in _JOBS.items() if job.document_hash == document_hash]
        for job_id in stale:
            _JOBS.pop(job_id, None)
    return len(stale)


@contextmanager
def ingestion_lock():
    """Serialize destructive document operations with ingestion."""
    if not _INGEST_LOCK.acquire(blocking=False):
        raise ApiError(
            409,
            "ingestion_in_progress",
            "An ingestion job is already running. Try again when it finishes.",
        )
    try:
        yield
    finally:
        _INGEST_LOCK.release()


def _set_job(job_id: str, **changes: Any) -> None:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            return
        for key, value in changes.items():
            setattr(job, key, value)
        job.updated_at = _now()


def _apply_progress(job_id: str, event: dict[str, Any]) -> None:
    """Map extraction progress events onto the job's batch grid."""
    kind = event.get("event")
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            return

        if kind == "stage":
            stage = event.get("stage")
            if stage:
                job.stage = str(stage)
        elif kind == "batches_planned":
            total = max(0, int(event.get("total") or 0))
            job.batch_total = total
            job.batches = [_batch_entry(index) for index in range(1, total + 1)]
        elif kind == "batch":
            index = int(event.get("index") or 0)
            if index <= 0:
                return
            total = max(int(event.get("total") or 0), job.batch_total, index)
            by_index = {batch["index"]: batch for batch in job.batches}
            if total > job.batch_total:
                job.batch_total = total
                for batch_index in range(1, total + 1):
                    by_index.setdefault(batch_index, _batch_entry(batch_index))

            entry = by_index.get(index) or _batch_entry(index)
            status = str(event.get("status") or entry["status"])
            entry["status"] = status
            if event.get("entities") is not None:
                entry["entities"] = int(event["entities"])
            entry["cached"] = bool(event.get("cached", status == "cached"))
            entry["error"] = event.get("error")
            by_index[index] = entry
            job.batches = [by_index[batch_index] for batch_index in sorted(by_index)]

        job.updated_at = _now()


async def save_upload(upload: UploadFile) -> tuple[str, str, int, Path]:
    """Validate and persist an upload, returning (hash, filename, size, path).

    The stored filename is derived from the hash directory plus a sanitized
    display name, so client paths cannot escape the upload directory.
    """

    settings.ensure_runtime_dirs()
    filename = _safe_filename(upload.filename)
    hasher = hashlib.sha256()
    size = 0
    header = b""
    part_path: Path | None = None
    final_dir: Path | None = None

    try:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            if not header:
                header = chunk[:5]
            size += len(chunk)
            if size > settings.max_upload_bytes:
                raise ApiError(
                    413,
                    "upload_too_large",
                    f"PDF exceeds the {settings.max_upload_mb} MB upload limit.",
                )
            hasher.update(chunk)

            if final_dir is None:
                # Hash is known only after reading, so buffer into a temporary
                # directory first and move it after validation.
                final_dir = settings.upload_path / ".incoming"
                final_dir.mkdir(parents=True, exist_ok=True)
                part_path = final_dir / f"{id(upload)}.part"

            assert part_path is not None
            with part_path.open("ab") as handle:
                handle.write(chunk)

        if size == 0:
            raise ApiError(400, "empty_upload", "The uploaded file is empty.")
        if header != b"%PDF-":
            raise ApiError(400, "invalid_pdf", "The uploaded file is not a PDF (missing %PDF- header).")

        document_hash = hasher.hexdigest()
        document_dir = settings.upload_path / document_hash
        document_dir.mkdir(parents=True, exist_ok=True)
        final_path = document_dir / filename
        if part_path is not None and part_path.exists():
            part_path.replace(final_path)
        return document_hash, filename, size, final_path
    except Exception:
        if part_path is not None and part_path.exists():
            part_path.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()


def create_job(filename: str, document_hash: str, path: Path) -> str:
    job_id = f"job_{document_hash[:12]}_{datetime.now(timezone.utc).strftime('%H%M%S%f')}"
    with _JOBS_LOCK:
        _JOBS[job_id] = IngestJob(
            job_id=job_id,
            filename=filename,
            document_hash=document_hash,
            path=path,
        )
    return job_id


def uploaded_pdf_path(document_hash: str) -> Path | None:
    """Find the stored PDF for a hash without allowing path traversal."""
    if not _SHA256.fullmatch(document_hash):
        return None
    root = settings.upload_path.resolve()
    document_dir = (settings.upload_path / document_hash).resolve()
    if not document_dir.is_dir() or not document_dir.is_relative_to(root):
        return None
    candidates = sorted(path for path in document_dir.glob("*.pdf") if path.is_file())
    return candidates[0] if candidates else None


def prepare_retry(document_hash: str) -> tuple[str, Path]:
    """Create a job that re-runs ``main.ingest`` for a partial/failed document.

    ``main.ingest`` already skips only completed documents, and the extractor
    already loads completed batches from ``.extraction_cache``. Reusing those
    entrypoints is what avoids repeating successful LLM calls.
    """
    from api.services.graph_service import get_document

    document = get_document(document_hash)
    if document.status not in {"partial", "failed"}:
        raise ApiError(
            409,
            "document_not_retryable",
            "Only partially ingested or failed documents can be retried.",
        )
    if active_job_for_hash(document_hash) is not None or _INGEST_LOCK.locked():
        raise ApiError(
            409,
            "ingestion_in_progress",
            "An ingestion job is already running. Try again when it finishes.",
        )

    path = uploaded_pdf_path(document_hash)
    if path is None:
        raise ApiError(
            409,
            "upload_missing",
            "The original PDF is no longer stored. Upload it again to retry.",
        )

    job_id = create_job(document.filename or path.name, document_hash, path)
    return job_id, path


def run_ingest_job(job_id: str, path: str) -> None:
    """Run the existing V3 ingestion pipeline in a background worker thread."""

    _set_job(job_id, status="running", stage="queued", error=None)

    def on_progress(event: dict[str, Any]) -> None:
        _apply_progress(job_id, event)

    try:
        with _INGEST_LOCK:
            # Imports are local: main.py pulls in config, Neo4j and Qdrant.
            from main import ingest

            ingest(path, on_progress=on_progress)

        from api.services.graph_service import get_document

        document = get_document(_hash_from_job(job_id))
        status = "partial" if document.status == "partial" else "completed"
        _set_job(
            job_id,
            status=status,
            stage="done",
            document=document.model_dump(),
            error=None,
        )
    except Exception as exc:
        # Do not expose raw exception text: it can contain connection details.
        _set_job(
            job_id,
            status="failed",
            stage="failed",
            error=f"Ingestion failed ({type(exc).__name__}). Check the backend logs.",
        )


def _hash_from_job(job_id: str) -> str:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            raise ApiError(404, "job_not_found", "No ingestion job exists with that id.")
        return job.document_hash
