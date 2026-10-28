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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from api.errors import ApiError
from api.settings import settings


_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")
_INGEST_LOCK = threading.Lock()
_JOBS_LOCK = threading.Lock()
_JOBS: dict[str, "IngestJob"] = {}


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


@dataclass
class IngestJob:
    job_id: str
    filename: str
    document_hash: str
    path: Path
    status: str = "queued"
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    document: dict[str, Any] | None = None
    error: str | None = None


def _job_dict(job: IngestJob) -> dict[str, Any]:
    return {
        "job_id": job.job_id,
        "status": job.status,
        "filename": job.filename,
        "document_hash": job.document_hash,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
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


def _set_job(job_id: str, **changes: Any) -> None:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            return
        for key, value in changes.items():
            setattr(job, key, value)
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


def run_ingest_job(job_id: str, path: str) -> None:
    """Run the existing V3 ingestion pipeline in a background worker thread."""

    _set_job(job_id, status="running", error=None)
    try:
        with _INGEST_LOCK:
            # Imports are local: main.py pulls in config, Neo4j and Qdrant.
            from main import ingest

            ingest(path)

        from api.services.graph_service import get_document

        document = get_document(_hash_from_job(job_id))
        status = "partial" if document.status == "partial" else "completed"
        _set_job(
            job_id,
            status=status,
            document=document.model_dump(),
        )
    except Exception as exc:
        # Do not expose raw exception text: it can contain connection details.
        _set_job(
            job_id,
            status="failed",
            error=f"Ingestion failed ({type(exc).__name__}). Check the backend logs.",
        )


def _hash_from_job(job_id: str) -> str:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            raise ApiError(404, "job_not_found", "No ingestion job exists with that id.")
        return job.document_hash
