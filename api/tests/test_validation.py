from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.services import ingestion_service


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_non_pdf_upload_is_rejected(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class FakeSettings:
        max_upload_bytes = 25 * 1024 * 1024
        max_upload_mb = 25
        upload_path = tmp_path

        def ensure_runtime_dirs(self) -> None:
            tmp_path.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(ingestion_service, "settings", FakeSettings())
    response = client.post(
        "/api/documents",
        files={"file": ("notes.txt", b"not a pdf", "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_pdf"


def test_empty_upload_is_rejected(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class FakeSettings:
        max_upload_bytes = 25 * 1024 * 1024
        max_upload_mb = 25
        upload_path = tmp_path

        def ensure_runtime_dirs(self) -> None:
            tmp_path.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(ingestion_service, "settings", FakeSettings())
    response = client.post(
        "/api/documents",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "empty_upload"


def test_override_without_a_change_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/analyses/missing/review",
        json={"action": "override", "notes": "", "edited_score": {}},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_rerun_without_a_hint_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/analyses/missing/review",
        json={"action": "rerun", "notes": ""},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_unknown_job_returns_not_found(client: TestClient) -> None:
    response = client.get("/api/jobs/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "job_not_found"


def test_unknown_analysis_returns_not_found(client: TestClient) -> None:
    response = client.get("/api/analyses/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "analysis_not_found"
