"""R04: one-click must not start multiple pipelines for the same novel."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.models.publication_pipeline import NovelPublicationPipeline
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

    monkeypatch.setattr(
        "app.api.v1.endpoints.publication_pipelines.start_publication_pipeline_execution",
        fake_start,
    )
    return TestClient(app)


def _h(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


def _novel(client: TestClient, user_id: str) -> str:
    resp = client.post("/api/v1/novels", json={"title": f"adm {uuid4()}", "description": "x"}, headers=_h(user_id))
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _post(client: TestClient, user_id: str, novel_id: str, key: str):
    return client.post(
        f"/api/v1/novels/{novel_id}/publication-pipelines",
        json={"idempotency_key": key, "series_plan_version": "plan-v1", "ensure_series_plan": True},
        headers=_h(user_id),
    )


async def _count(novel_id: str) -> int:
    async with AsyncSessionLocal() as db:
        return int(await db.scalar(
            select(func.count()).select_from(NovelPublicationPipeline).where(NovelPublicationPipeline.novel_id == novel_id)
        ))


@pytest.mark.asyncio
async def test_double_click_with_different_keys_returns_same_active_pipeline(client: TestClient) -> None:
    user_id = f"adm-{uuid4()}"
    novel_id = _novel(client, user_id)
    first = _post(client, user_id, novel_id, f"ui-{uuid4()}")
    second = _post(client, user_id, novel_id, f"ui-{uuid4()}")
    assert first.status_code == 202, first.text
    assert second.status_code == 202, second.text
    assert second.json()["pipeline_id"] == first.json()["pipeline_id"]
    assert second.json()["execution_status"] == "already_active"
    assert await _count(novel_id) == 1


@pytest.mark.asyncio
async def test_new_pipeline_allowed_after_previous_finished(client: TestClient) -> None:
    user_id = f"adm-{uuid4()}"
    novel_id = _novel(client, user_id)
    first = _post(client, user_id, novel_id, f"ui-{uuid4()}").json()
    async with AsyncSessionLocal() as db:
        row = await db.get(NovelPublicationPipeline, first["pipeline_id"])
        row.status = "succeeded"
        await db.commit()
    second = _post(client, user_id, novel_id, f"ui-{uuid4()}")
    assert second.status_code == 202
    assert second.json()["pipeline_id"] != first["pipeline_id"]
    assert await _count(novel_id) == 2


@pytest.mark.asyncio
async def test_db_rejects_second_active_pipeline_for_same_novel(client: TestClient) -> None:
    """Atomic guard: partial unique index blocks a racing second active insert."""
    from sqlalchemy.exc import IntegrityError

    user_id = f"adm-{uuid4()}"
    novel_id = _novel(client, user_id)
    _post(client, user_id, novel_id, f"ui-{uuid4()}")
    async with AsyncSessionLocal() as db:
        db.add(NovelPublicationPipeline(
            id=str(uuid4()), user_id=user_id, novel_id=novel_id, series_plan_version="plan-v1",
            idempotency_key=f"race-{uuid4()}", status="queued", stage="accepted",
        ))
        with pytest.raises(IntegrityError):
            await db.commit()


@pytest.mark.asyncio
async def test_other_novels_are_independent(client: TestClient) -> None:
    user_id = f"adm-{uuid4()}"
    a, b = _novel(client, user_id), _novel(client, user_id)
    ra = _post(client, user_id, a, "same-key").json()
    rb = _post(client, user_id, b, "same-key").json()
    assert ra["pipeline_id"] != rb["pipeline_id"]
