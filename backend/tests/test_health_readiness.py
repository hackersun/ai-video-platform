"""Wave4: liveness vs readiness probes."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    # Ensure ambient redis from other shells does not force a redis check.
    monkeypatch.delenv("REDIS_URL", raising=False)
    from main import app

    return TestClient(app)


def test_liveness_always_healthy_without_redis(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body.get("probe") == "liveness"


def test_readiness_ok_when_database_up(client: TestClient) -> None:
    resp = client.get("/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"]["ok"] is True
    assert "redis" not in body["checks"]


def test_readiness_503_when_redis_configured_but_unreachable(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
    resp = client.get("/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["redis"]["ok"] is False
    assert "error" in body["checks"]["redis"]


def test_root_lists_ready_probe(client: TestClient) -> None:
    body = client.get("/").json()
    assert body["ready"] == "/ready"
    assert body["health"] == "/health"


def test_build_readiness_reports_storage_in_production(monkeypatch) -> None:
    import asyncio

    from app.core import health as health_mod

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("REDIS_URL", raising=False)
    for name in ("STORAGE_PROVIDER", "ALLOW_LOCAL_STORAGE_IN_PRODUCTION"):
        monkeypatch.delenv(name, raising=False)

    async def db_ok():
        return {"ok": True, "latency_ms": 0}

    monkeypatch.setattr(health_mod, "check_database", db_ok)
    payload = asyncio.run(health_mod.build_readiness())
    assert payload["status"] == "ready"  # storage advisory only
    assert payload["checks"]["storage"]["ok"] is False
    assert payload["checks"]["storage"]["problems"]
