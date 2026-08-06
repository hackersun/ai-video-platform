from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import AsyncSessionLocal
from app.models import StoryEntity
from app.services.story_entity_lifecycle import APPROVED, CANDIDATE, REJECTED, set_entity_review_status
from init_db import init_db
from main import app


@pytest.fixture(scope="module", autouse=True)
def _init_database() -> None:
    init_db()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DEV_MODE", "true")
    return TestClient(app)


def _headers(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


def _seed_entities(user_id: str, novel_id: str, count: int, *, name_prefix: str = "分页角色") -> None:
    async def seed() -> None:
        async with AsyncSessionLocal() as db:
            for index in range(count):
                entity = StoryEntity(
                    id=str(uuid4()),
                    user_id=user_id,
                    novel_id=novel_id,
                    entity_type="character" if index % 2 == 0 else "scene",
                    name=f"{name_prefix}{index:03d}",
                    aliases=[f"别名{index:03d}"],
                    description=f"描述关键词 {index:03d}",
                    evidence=f"原文证据 {index:03d}",
                    source="deterministic",
                )
                status = APPROVED if index % 7 == 0 else REJECTED if index % 11 == 0 else CANDIDATE
                set_entity_review_status(entity, status, changed_by=user_id, reason="fixture")
                db.add(entity)
            await db.commit()

    asyncio.run(seed())


def test_entity_review_pagination_is_complete_stable_and_user_scoped(client: TestClient) -> None:
    user_id = f"review-page-{uuid4().hex[:20]}"
    other_user = f"review-other-{uuid4().hex[:20]}"
    novel_id = str(uuid4())
    _seed_entities(user_id, novel_id, 121)
    _seed_entities(other_user, novel_id, 3, name_prefix="越权角色")

    first = client.get(
        f"/api/v1/entity-review/novels/{novel_id}/entities?page=1&page_size=50",
        headers=_headers(user_id),
    )
    third = client.get(
        f"/api/v1/entity-review/novels/{novel_id}/entities?page=3&page_size=50",
        headers=_headers(user_id),
    )

    assert first.status_code == 200
    assert third.status_code == 200
    assert first.json()["total"] == 121
    assert first.json()["total_pages"] == 3
    assert len(first.json()["items"]) == 50
    assert len(third.json()["items"]) == 21
    assert {item["id"] for item in first.json()["items"]}.isdisjoint(
        {item["id"] for item in third.json()["items"]}
    )
    assert all(not item["name"].startswith("越权") for item in first.json()["items"])


def test_entity_review_filters_search_and_summary_are_server_side(client: TestClient) -> None:
    user_id = f"review-filter-{uuid4().hex[:20]}"
    novel_id = str(uuid4())
    _seed_entities(user_id, novel_id, 36)

    filtered = client.get(
        f"/api/v1/entity-review/novels/{novel_id}/entities"
        "?page=1&page_size=20&entity_type=character&review_status=approved&query=描述关键词",
        headers=_headers(user_id),
    )
    alias_match = client.get(
        f"/api/v1/entity-review/novels/{novel_id}/entities?page=1&page_size=20&query=别名035",
        headers=_headers(user_id),
    )

    assert filtered.status_code == 200
    assert filtered.json()["items"]
    assert all(item["entity_type"] == "character" for item in filtered.json()["items"])
    assert all(item["review_status"] == "approved" for item in filtered.json()["items"])
    assert filtered.json()["summary"]["total"] == 36
    assert alias_match.status_code == 200
    assert [item["name"] for item in alias_match.json()["items"]] == ["分页角色035"]


def test_bulk_review_keeps_successes_and_reports_unsafe_or_out_of_scope_rows(client: TestClient) -> None:
    user_id = f"review-bulk-{uuid4().hex[:20]}"
    other_user = f"review-bulk-other-{uuid4().hex[:20]}"
    novel_id = str(uuid4())
    other_novel_id = str(uuid4())

    async def seed() -> tuple[str, str, str, str]:
        async with AsyncSessionLocal() as db:
            rows = [
                StoryEntity(id=str(uuid4()), user_id=user_id, novel_id=novel_id, entity_type="prop", name="人工安全道具", source="manual"),
                StoryEntity(id=str(uuid4()), user_id=user_id, novel_id=novel_id, entity_type="scene", name="无证据场景", source="deterministic"),
                StoryEntity(id=str(uuid4()), user_id=user_id, novel_id=other_novel_id, entity_type="character", name="其他小说角色", source="manual"),
                StoryEntity(id=str(uuid4()), user_id=other_user, novel_id=novel_id, entity_type="character", name="其他用户角色", source="manual"),
            ]
            for row in rows:
                set_entity_review_status(row, CANDIDATE, changed_by=row.user_id, reason="fixture")
                db.add(row)
            await db.commit()
            return tuple(row.id for row in rows)

    safe_id, missing_id, other_novel_id_entity, other_user_id_entity = asyncio.run(seed())
    response = client.post(
        "/api/v1/entity-review/bulk-review",
        json={
            "novel_id": novel_id,
            "entity_ids": [safe_id, missing_id, other_novel_id_entity, other_user_id_entity],
            "action": "approve",
        },
        headers=_headers(user_id),
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["updated"]] == [safe_id]
    assert {item["id"] for item in response.json()["skipped"]} == {
        missing_id, other_novel_id_entity, other_user_id_entity,
    }
    assert response.json()["summary"]["approved_count"] == 1

    rejected = client.post(
        "/api/v1/entity-review/bulk-review",
        json={"novel_id": novel_id, "entity_ids": [safe_id, missing_id], "action": "reject"},
        headers=_headers(user_id),
    )
    assert rejected.status_code == 200
    assert {item["review_status"] for item in rejected.json()["updated"]} == {"rejected"}


def test_reanalysis_requires_provider_preview_before_apply(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = f"review-reanalyze-{uuid4().hex[:20]}"
    novel_id = str(uuid4())
    _seed_entities(user_id, novel_id, 1, name_prefix="误识别角色")

    async def entity_id() -> str:
        from sqlalchemy import select
        async with AsyncSessionLocal() as db:
            return (await db.execute(select(StoryEntity.id).where(StoryEntity.user_id == user_id))).scalar_one()

    target_id = asyncio.run(entity_id())

    async def provider_preview(*_args, **_kwargs):
        return ([{
            "entity_type": "character", "name": "林辰", "canonical_name": "林辰",
            "aliases": ["辰儿"], "description": "外门弟子", "appearance": "黑发青衣少年",
            "visual_prompt": "black-haired young cultivator", "evidence": "误识别角色000",
            "confidence": 92, "source": "provider_model", "attributes": {},
        }], {"execution_mode": "provider_model", "provider": "test", "model_id": "model-x"})

    monkeypatch.setattr("app.features.entity_review.service._run_model_candidate_preview", provider_preview, raising=False)
    preview = client.post(
        f"/api/v1/entity-review/entities/{target_id}/reanalyze",
        json={"mode": "preview"},
        headers=_headers(user_id),
    )
    assert preview.status_code == 200
    assert preview.json()["current"]["name"] == "误识别角色000"
    assert preview.json()["proposed"]["name"] == "林辰"

    unchanged = client.get(
        f"/api/v1/entity-review/novels/{novel_id}/entities?query=误识别角色000",
        headers=_headers(user_id),
    )
    assert unchanged.json()["total"] == 1

    applied = client.post(
        f"/api/v1/entity-review/entities/{target_id}/reanalyze",
        json={"mode": "apply", "preview_run_id": preview.json()["preview_run_id"]},
        headers=_headers(user_id),
    )
    assert applied.status_code == 200
    assert applied.json()["current"]["name"] == "林辰"
    assert applied.json()["current"]["review_status"] == "candidate"


def test_rebuild_archives_only_review_rows_after_provider_preview(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sqlalchemy import select
    from app.services.story_entity_lifecycle import get_entity_review_status

    user_id = f"review-rebuild-{uuid4().hex[:20]}"
    novel_id = str(uuid4())

    async def seed() -> dict[str, str]:
        async with AsyncSessionLocal() as db:
            ids = {}
            for name, status in (("已定稿角色", APPROVED), ("旧候选", CANDIDATE), ("旧拒绝", REJECTED)):
                row = StoryEntity(id=str(uuid4()), user_id=user_id, novel_id=novel_id, entity_type="character", name=name, evidence=name, source="manual")
                set_entity_review_status(row, status, changed_by=user_id, reason="fixture")
                db.add(row)
                ids[name] = row.id
            await db.commit()
            return ids

    ids = asyncio.run(seed())

    async def provider_preview(*_args, **_kwargs):
        return ([{
            "entity_type": "character", "name": "新候选", "description": "模型识别",
            "evidence": "新候选", "confidence": 90, "source": "provider_model", "attributes": {},
        }], {"execution_mode": "provider_model", "provider": "test", "model_id": "model-x"})

    monkeypatch.setattr("app.features.entity_review.service._run_model_candidate_preview", provider_preview, raising=False)
    preview = client.post(
        f"/api/v1/entity-review/novels/{novel_id}/rebuild-candidates",
        json={"mode": "preview", "source_text": "新候选"}, headers=_headers(user_id),
    )
    assert preview.status_code == 200
    applied = client.post(
        f"/api/v1/entity-review/novels/{novel_id}/rebuild-candidates",
        json={"mode": "apply", "preview_run_id": preview.json()["preview_run_id"]},
        headers=_headers(user_id),
    )
    assert applied.status_code == 200

    async def statuses() -> dict[str, str]:
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(select(StoryEntity).where(StoryEntity.user_id == user_id))).scalars().all()
            return {row.name: get_entity_review_status(row) for row in rows}

    result = asyncio.run(statuses())
    assert result["已定稿角色"] == APPROVED
    assert result["旧候选"] == "archived"
    assert result["旧拒绝"] == "archived"
    assert result["新候选"] == CANDIDATE

    async def fallback_preview(*_args, **_kwargs):
        return ([{"entity_type": "character", "name": "兜底噪声"}], {"execution_mode": "deterministic_fallback"})

    monkeypatch.setattr("app.features.entity_review.service._run_model_candidate_preview", fallback_preview, raising=False)
    blocked = client.post(
        f"/api/v1/entity-review/novels/{novel_id}/rebuild-candidates",
        json={"mode": "preview", "source_text": "兜底噪声"}, headers=_headers(user_id),
    )
    assert blocked.status_code == 409
    assert asyncio.run(statuses()) == result
