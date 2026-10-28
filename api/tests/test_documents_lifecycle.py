from __future__ import annotations

import contextlib
from pathlib import Path

import pytest

from api.errors import ApiError
from api.schemas import DocumentSummary
from api.services import document_service, graph_service, ingestion_service, qa_service


HASH = "a" * 64


@pytest.fixture(autouse=True)
def clear_jobs():
    with ingestion_service._JOBS_LOCK:
        ingestion_service._JOBS.clear()
    yield
    with ingestion_service._JOBS_LOCK:
        ingestion_service._JOBS.clear()


def _document(status: str) -> DocumentSummary:
    return DocumentSummary(hash=HASH, filename="report.pdf", status=status)


def test_progress_events_populate_batch_grid() -> None:
    job_id = ingestion_service.create_job("report.pdf", HASH, Path("/tmp/report.pdf"))

    ingestion_service._apply_progress(job_id, {"event": "batches_planned", "total": 3})
    ingestion_service._apply_progress(
        job_id,
        {"event": "batch", "index": 1, "total": 3, "status": "cached", "entities": 5, "cached": True},
    )
    ingestion_service._apply_progress(
        job_id,
        {"event": "batch", "index": 2, "total": 3, "status": "failed", "error": "RateLimitError"},
    )

    job = ingestion_service.get_job(job_id)
    assert job["batch_total"] == 3
    assert [batch["status"] for batch in job["batches"]] == ["cached", "failed", "pending"]
    assert job["batches"][0]["entities"] == 5
    assert job["batches"][0]["cached"] is True
    assert job["batches"][1]["error"] == "RateLimitError"


def test_retry_rejects_completed_document(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(graph_service, "get_document", lambda _: _document("completed"))

    with pytest.raises(ApiError) as error:
        ingestion_service.prepare_retry(HASH)

    assert error.value.status_code == 409
    assert error.value.code == "document_not_retryable"


def test_retry_rejects_missing_upload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(graph_service, "get_document", lambda _: _document("partial"))
    monkeypatch.setattr(ingestion_service, "uploaded_pdf_path", lambda _: None)

    with pytest.raises(ApiError) as error:
        ingestion_service.prepare_retry(HASH)

    assert error.value.status_code == 409
    assert error.value.code == "upload_missing"


def test_retry_creates_job_for_partial_document(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    stored = tmp_path / "report.pdf"
    stored.write_bytes(b"%PDF-1.4")
    monkeypatch.setattr(graph_service, "get_document", lambda _: _document("partial"))
    monkeypatch.setattr(ingestion_service, "uploaded_pdf_path", lambda _: stored)

    job_id, path = ingestion_service.prepare_retry(HASH)

    assert path == stored
    assert ingestion_service.get_job(job_id)["status"] == "queued"
    assert ingestion_service.get_job(job_id)["document_hash"] == HASH


def test_uploaded_pdf_path_is_confined_to_upload_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class FakeSettings:
        upload_path = tmp_path

    monkeypatch.setattr(ingestion_service, "settings", FakeSettings())

    assert ingestion_service.uploaded_pdf_path("../etc") is None
    assert ingestion_service.uploaded_pdf_path(HASH) is None

    document_dir = tmp_path / HASH
    document_dir.mkdir()
    stored = document_dir / "report.pdf"
    stored.write_bytes(b"%PDF-1.4")

    assert ingestion_service.uploaded_pdf_path(HASH) == stored


def test_delete_document_combines_store_results(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(graph_service, "get_document", lambda _: _document("completed"))
    monkeypatch.setattr(ingestion_service, "active_job_for_hash", lambda _: None)
    monkeypatch.setattr(ingestion_service, "ingestion_lock", contextlib.nullcontext)
    monkeypatch.setattr(document_service, "_delete_qdrant_points", lambda _: 7)
    monkeypatch.setattr(
        document_service,
        "_delete_graph",
        lambda _: {"entities": 2, "relationships": 3, "assessments": 1, "documents": 1},
    )
    monkeypatch.setattr(document_service, "_remove_upload", lambda _: True)
    monkeypatch.setattr(ingestion_service, "forget_jobs", lambda _: 1)

    response = document_service.delete_document(HASH)

    assert response.document_hash == HASH
    assert response.filename == "report.pdf"
    assert response.deleted_points == 7
    assert response.deleted_entities == 2
    assert response.deleted_relationships == 3
    assert response.deleted_assessments == 1
    assert response.upload_removed is True


def test_delete_document_refuses_active_job(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(graph_service, "get_document", lambda _: _document("completed"))
    monkeypatch.setattr(ingestion_service, "active_job_for_hash", lambda _: {"status": "running"})

    with pytest.raises(ApiError) as error:
        document_service.delete_document(HASH)

    assert error.value.status_code == 409
    assert error.value.code == "ingestion_in_progress"


def test_ask_document_returns_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(graph_service, "get_document", lambda _: _document("completed"))
    monkeypatch.setattr(
        qa_service,
        "_answer_question",
        lambda question: f"Answer: {question}",
    )

    response = qa_service.ask_document(HASH, "  What are the main risks?  ")

    assert response.document_hash == HASH
    assert response.question == "What are the main risks?"
    assert response.answer == "Answer: What are the main risks?"


def test_ask_document_rejects_unfinished_document(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(graph_service, "get_document", lambda _: _document("failed"))

    with pytest.raises(ApiError) as error:
        qa_service.ask_document(HASH, "What changed?")

    assert error.value.status_code == 409
    assert error.value.code == "document_not_ready"


def test_ask_document_rejects_blank_question(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(graph_service, "get_document", lambda _: _document("completed"))

    with pytest.raises(ApiError) as error:
        qa_service.ask_document(HASH, "   ")

    assert error.value.status_code == 400
    assert error.value.code == "empty_question"


def test_ask_document_hides_provider_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(graph_service, "get_document", lambda _: _document("completed"))

    def boom(_: str) -> str:
        raise RuntimeError("provider key rejected")

    monkeypatch.setattr(qa_service, "_answer_question", boom)

    with pytest.raises(ApiError) as error:
        qa_service.ask_document(HASH, "What changed?")

    assert error.value.status_code == 503
    assert error.value.code == "question_unavailable"
    assert "provider" not in error.value.message
