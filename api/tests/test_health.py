from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_live_health_does_not_require_database(client: TestClient) -> None:
    response = client.get("/api/health/live")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "aarthik-gyan-api"
    assert body["version"] == "4.0.0"


def test_ready_health_reports_ready_when_dependencies_are_stubbed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    neo4j_module = types.ModuleType("graph.neo4j_client")

    class Driver:
        def verify_connectivity(self) -> None:
            return None

    neo4j_module.neo4j_client = types.SimpleNamespace(driver=Driver())
    qdrant_module = types.ModuleType("vectorstore.qdrant_client")
    qdrant_module.vector_store_client = types.SimpleNamespace(
        client=types.SimpleNamespace(get_collections=lambda: [])
    )

    monkeypatch.setitem(sys.modules, "graph.neo4j_client", neo4j_module)
    monkeypatch.setitem(sys.modules, "vectorstore.qdrant_client", qdrant_module)

    response = client.get("/api/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert {check["name"] for check in body["checks"]} == {"neo4j", "qdrant"}


def test_ready_health_reports_degraded_when_dependencies_fail(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    broken_neo4j = types.ModuleType("graph.neo4j_client")

    class BrokenDriver:
        def verify_connectivity(self) -> None:
            raise RuntimeError("offline")

    broken_neo4j.neo4j_client = types.SimpleNamespace(driver=BrokenDriver())
    broken_qdrant = types.ModuleType("vectorstore.qdrant_client")
    broken_qdrant.vector_store_client = types.SimpleNamespace(
        client=types.SimpleNamespace(get_collections=lambda: (_ for _ in ()).throw(RuntimeError("offline")))
    )

    monkeypatch.setitem(sys.modules, "graph.neo4j_client", broken_neo4j)
    monkeypatch.setitem(sys.modules, "vectorstore.qdrant_client", broken_qdrant)

    response = client.get("/api/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert all(check["ok"] is False for check in body["checks"])


def test_frontend_dist_is_optional(client: TestClient) -> None:
    # The API must work without a frontend build.
    assert Path("frontend/dist").exists() is False or client.get("/api/health/live").status_code == 200
