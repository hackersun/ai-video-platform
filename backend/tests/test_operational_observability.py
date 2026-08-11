from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.task_execution import TaskExecution
from main import app


def test_health_endpoints_separate_liveness_and_readiness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def ready_snapshot() -> dict:
        return {
            "database": {"status": "ok"},
            "task_queue": {
                "status": "ok",
                "pending": 2,
                "running": 1,
                "needs_attention": 0,
            },
        }

    monkeypatch.setattr("main.collect_operational_snapshot", ready_snapshot)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DEV_MODE", "true")

    with TestClient(app) as client:
        live = client.get("/health/live", headers={"X-Request-ID": "release-check-1"})
        ready = client.get("/health/ready")

    assert live.status_code == 200
    assert live.json()["status"] == "alive"
    assert live.headers["x-request-id"] == "release-check-1"
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert ready.json()["checks"]["task_queue"]["pending"] == 2


def test_readiness_failure_returns_safe_chinese_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def failed_snapshot() -> dict:
        raise RuntimeError("postgresql://admin:secret@database/private")

    monkeypatch.setattr("main.collect_operational_snapshot", failed_snapshot)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DEV_MODE", "true")

    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["detail"] == "服务尚未准备好，请稍后重试"
    assert "secret" not in response.text
    assert response.headers["x-request-id"]


def test_metrics_require_operations_token_in_commercial_environments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPERATIONS_TOKEN", "commercial-operations-token")

    from app.core.request_observability import metrics_access_allowed

    assert metrics_access_allowed(None) is False
    assert metrics_access_allowed("Bearer wrong-token") is False
    assert metrics_access_allowed("Bearer commercial-operations-token") is True


def test_request_metrics_use_route_templates_and_prometheus_text() -> None:
    from app.core.request_observability import RequestMetrics

    metrics = RequestMetrics()
    metrics.observe("GET", "/api/v1/tasks/{execution_id}", 200, 0.125)
    metrics.observe("GET", "/api/v1/tasks/{execution_id}", 500, 0.250)

    rendered = metrics.render()

    assert 'path="/api/v1/tasks/{execution_id}"' in rendered
    assert 'status="2xx"' in rendered
    assert 'status="5xx"' in rendered
    assert "ai_video_http_requests_total" in rendered
    assert "ai_video_http_request_duration_seconds_sum" in rendered


def test_operational_metrics_render_low_cardinality_queue_gauges() -> None:
    from app.core.request_observability import render_operational_metrics

    rendered = render_operational_metrics(
        {
            "database": {"status": "ok"},
            "task_queue": {
                "status": "ok",
                "pending": 2,
                "running": 1,
                "retry_wait": 3,
                "dead_letter": 4,
                "needs_attention": 5,
                "oldest_active_age_seconds": 901.25,
            },
        }
    )

    assert "ai_video_database_ready 1" in rendered
    assert 'ai_video_task_queue_depth{status="dead_letter"} 4' in rendered
    assert 'ai_video_task_queue_depth{status="needs_attention"} 5' in rendered
    assert "ai_video_task_oldest_active_age_seconds 901.250" in rendered
    assert "payload" not in rendered


def test_metrics_report_database_failure_without_leaking_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def failed_snapshot() -> dict:
        raise RuntimeError("postgresql://admin:secret@database/private")

    monkeypatch.setattr("main.collect_operational_snapshot", failed_snapshot)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DEV_MODE", "true")

    with TestClient(app) as client:
        response = client.get("/metrics")

    assert response.status_code == 200
    assert "ai_video_database_ready 0" in response.text
    assert "secret" not in response.text


def test_operational_snapshot_counts_durable_queue_without_payloads(tmp_path) -> None:
    from app.core.operational_health import collect_operational_snapshot

    async def scenario() -> dict:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'health.db'}")
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as db:
            stale_at = datetime(2026, 8, 11, 4, 10)
            db.add_all(
                [
                    TaskExecution(
                        id="pending-task",
                        user_id="health-user",
                        task_type="shot_image",
                        idempotency_key="health-pending",
                        payload={"secret": "must-not-leak"},
                        status="pending",
                        updated_at=stale_at,
                    ),
                    TaskExecution(
                        id="attention-task",
                        user_id="health-user",
                        task_type="shot_video",
                        idempotency_key="health-attention",
                        payload={},
                        status="needs_attention",
                    ),
                ]
            )
            await db.commit()
        try:
            return await collect_operational_snapshot(
                factory,
                clock=lambda: stale_at + timedelta(minutes=20),
            )
        finally:
            await engine.dispose()

    snapshot = asyncio.run(scenario())

    assert snapshot["database"] == {"status": "ok"}
    assert snapshot["task_queue"]["pending"] == 1
    assert snapshot["task_queue"]["needs_attention"] == 1
    assert snapshot["task_queue"]["oldest_active_age_seconds"] == 1200.0
    assert "secret" not in str(snapshot)
