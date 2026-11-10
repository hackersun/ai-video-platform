"""Batched latest-pipeline status for the novel list (replaces per-novel N+1)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from init_db import init_db
from main import app


@pytest.fixture(scope="module", autouse=True)
def _init_database() -> None:
    init_db()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DEV_MODE", "true")
    monkeypatch.setenv("PUBLICATION_PIPELINE_ENABLED", "true")

    async def fake_start(pipeline_id: str, uid: str) -> bool:
        return True

    monkeypatch.setattr("app.api.v1.endpoints.publication_pipelines.start_publication_pipeline_execution", fake_start)
    return TestClient(app)


def _h(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


def _novel(client: TestClient, user_id: str) -> str:
    resp = client.post("/api/v1/novels", json={"title": f"bs {uuid4()}", "description": "x"}, headers=_h(user_id))
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_batch_status_returns_latest_per_novel_scoped_to_user(client: TestClient) -> None:
    user, other = f"bs-{uuid4()}", f"bs-{uuid4()}"
    with_pipeline, without = _novel(client, user), _novel(client, user)
    foreign = _novel(client, other)
    created = client.post(
        f"/api/v1/novels/{with_pipeline}/publication-pipelines",
        json={"idempotency_key": f"k-{uuid4()}", "series_plan_version": "plan-v1", "ensure_series_plan": True},
        headers=_h(user),
    )
    assert created.status_code == 202, created.text
    client.post(
        f"/api/v1/novels/{foreign}/publication-pipelines",
        json={"idempotency_key": f"k-{uuid4()}", "series_plan_version": "plan-v1", "ensure_series_plan": True},
        headers=_h(other),
    )
    resp = client.get(
        f"/api/v1/publication-pipeline-statuses?novel_ids={with_pipeline},{without},{foreign}", headers=_h(user)
    )
    assert resp.status_code == 200, resp.text
    statuses = resp.json()["statuses"]
    assert set(statuses) == {with_pipeline}
    assert statuses[with_pipeline]["pipeline_id"] == created.json()["pipeline_id"]
    assert statuses[with_pipeline]["status"]


def test_batch_status_empty(client: TestClient) -> None:
    resp = client.get("/api/v1/publication-pipeline-statuses", headers=_h(f"bs-{uuid4()}"))
    assert resp.json() == {"statuses": {}}
