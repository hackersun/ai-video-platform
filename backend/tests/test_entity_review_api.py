from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import AsyncSessionLocal
from app.models import Chapter, StoryEntity
from init_db import init_db
from main import app


@pytest.fixture(scope="module", autouse=True)
def _init_database() -> None:
    init_db()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DEV_MODE", "true")
    return TestClient(app)


def _auth_headers(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


def _create_novel(client: TestClient, user_id: str) -> str:
    response = client.post(
        "/api/v1/novels",
        json={"title": f"资产分析 API 测试 {uuid4()}", "genre": "奇幻", "description": "测试"},
        headers=_auth_headers(user_id),
    )
    assert response.status_code == 201
    return response.json()["id"]


def _seed_ai_candidate_without_mention(user_id: str, novel_id: str, *, entity_type: str, name: str) -> str:
    entity_id = f"entity-api-candidate-{uuid4()}"

    async def seed() -> None:
        from app.services.story_entity_lifecycle import CANDIDATE, set_entity_review_status

        async with AsyncSessionLocal() as db:
            entity = StoryEntity(
                id=entity_id,
                user_id=user_id,
                novel_id=novel_id,
                entity_type=entity_type,
                name=name,
                source="deterministic",
                confidence=90,
            )
            set_entity_review_status(entity, CANDIDATE, changed_by=user_id, reason="missing-evidence fixture")
            db.add(entity)
            await db.commit()

    asyncio.run(seed())
    return entity_id


def test_asset_analysis_api_runs_review_actions_and_targeted_enrichment(client: TestClient) -> None:
    user_id = f"entity-api-{uuid4().hex[:20]}"
    novel_id = _create_novel(client, user_id)

    analysis = client.post(
        "/api/v1/story-bibles/entities/analyze",
        json={
            "novel_id": novel_id,
            "text": "角色：林澈。角色：沈砚。林澈站在旧邮局门口，沈砚戴着裂纹银面具。场景：旧邮局。道具：铜铃。",
            "entity_types": ["character", "scene", "prop"],
            "persist": True,
        },
        headers=_auth_headers(user_id),
    )
    assert analysis.status_code == 200
    payload = analysis.json()
    assert payload["run_id"]
    assert payload["stats"]["created"] >= 3
    assert payload["prompt_routing"]["task"] == "entity_extraction"

    detail = client.get(
        f"/api/v1/story-bibles/entities/runs/{payload['run_id']}",
        headers=_auth_headers(user_id),
    )
    assert detail.status_code == 200
    assert detail.json()["mention_count"] >= 3

    summary = client.get(
        f"/api/v1/story-bibles/entities/review-summary?novel_id={novel_id}",
        headers=_auth_headers(user_id),
    )
    assert summary.status_code == 200
    assert summary.json()["candidate_count"] >= 3

    candidate_pack = client.get(
        f"/api/v1/story-bibles/entities/production-pack/{novel_id}",
        headers=_auth_headers(user_id),
    )
    assert candidate_pack.status_code == 200
    assert candidate_pack.json()["counts"] == {
        "characters": 0,
        "scenes": 0,
        "props": 0,
        "events": 0,
        "relationships": 0,
    }

    entities = payload["entities"]
    character = next(item for item in entities if item["entity_type"] == "character")
    promoted = client.post(
        f"/api/v1/story-bibles/entities/{character['id']}/promote",
        json={"reason": "证据清晰"},
        headers=_auth_headers(user_id),
    )
    assert promoted.status_code == 200
    assert promoted.json()["review_status"] == "approved"

    approved_pack = client.get(
        f"/api/v1/story-bibles/entities/production-pack/{novel_id}",
        headers=_auth_headers(user_id),
    )
    assert approved_pack.status_code == 200
    assert approved_pack.json()["counts"]["characters"] == 1
    assert [item["id"] for item in approved_pack.json()["characters"]] == [character["id"]]

    prop = next(item for item in entities if item["entity_type"] == "prop")
    rejected = client.post(
        f"/api/v1/story-bibles/entities/{prop['id']}/reject",
        json={"reason": "暂不制作"},
        headers=_auth_headers(user_id),
    )
    assert rejected.status_code == 200
    assert rejected.json()["review_status"] == "rejected"

    enrichment = client.post(
        "/api/v1/story-bibles/entities/enrich-target",
        json={
            "novel_id": novel_id,
            "text": "沈砚又名阿砚，与林澈在旧邮局结盟。沈砚戴着裂纹银面具。",
            "entity_type": "character",
            "entity_name": "沈砚",
            "fields": ["appearance", "aliases", "relations", "evidence"],
            "mode": "merge_candidate",
        },
        headers=_auth_headers(user_id),
    )
    assert enrichment.status_code == 200
    assert enrichment.json()["prompt_routing"]["task"] == "entity_extraction"


def test_promote_rejects_non_manual_entity_without_persisted_mention_evidence(client: TestClient) -> None:
    user_id = f"entity-api-{uuid4().hex[:20]}"
    novel_id = _create_novel(client, user_id)
    entity_id = _seed_ai_candidate_without_mention(
        user_id,
        novel_id,
        entity_type="character",
        name="无证据 AI 候选",
    )

    promoted = client.post(
        f"/api/v1/story-bibles/entities/{entity_id}/promote",
        json={"reason": "不应绕过证据门禁"},
        headers=_auth_headers(user_id),
    )

    assert promoted.status_code == 422
    assert "原文证据" in promoted.json()["detail"]


def test_bulk_approval_skips_entities_without_evidence_and_keeps_manual_compatibility(client: TestClient) -> None:
    user_id = f"entity-api-{uuid4().hex[:20]}"
    novel_id = _create_novel(client, user_id)
    manual = client.post(
        "/api/v1/story-bibles/entities",
        json={
            "novel_id": novel_id,
            "entity_type": "character",
            "name": "人工角色",
            "source": "manual",
        },
        headers=_auth_headers(user_id),
    )
    extracted_without_mention_id = _seed_ai_candidate_without_mention(
        user_id,
        novel_id,
        entity_type="scene",
        name="无证据场景",
    )
    assert manual.status_code == 201

    response = client.post(
        "/api/v1/story-bibles/entities/bulk-action",
        json={
            "entity_ids": [manual.json()["id"], extracted_without_mention_id],
            "action": "approve",
            "approved": True,
        },
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["updated_count"] == 1
    assert [item["id"] for item in payload["entities"]] == [manual.json()["id"]]
    assert payload["skipped"] == [
        {
            "id": extracted_without_mention_id,
            "reason": "AI 抽取实体缺少可验证原文证据，不能进入生产状态",
            "repair_action": "补充原文证据后再定稿",
        }
    ]


def test_bulk_approval_excludes_high_duplicate_risk(client: TestClient) -> None:
    user_id = f"entity-api-{uuid4().hex[:20]}"
    novel_id = _create_novel(client, user_id)
    entity_ids: list[str] = []
    for name in ("林澈", "林澈"):
        created = client.post(
            "/api/v1/story-bibles/entities",
            json={
                "novel_id": novel_id,
                "entity_type": "character",
                "name": name,
                "source": "manual",
            },
            headers=_auth_headers(user_id),
        )
        assert created.status_code == 201
        entity_ids.append(created.json()["id"])

    response = client.post(
        "/api/v1/story-bibles/entities/bulk-action",
        json={"entity_ids": entity_ids, "action": "approve", "approved": True},
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    assert response.json()["updated_count"] == 0
    assert {item["reason"] for item in response.json()["skipped"]} == {"存在高重复风险，不能批量定稿"}


def test_manual_create_is_immediately_auditable_and_production_visible(client: TestClient) -> None:
    user_id = f"entity-api-{uuid4().hex[:20]}"
    novel_id = _create_novel(client, user_id)

    created = client.post(
        "/api/v1/story-bibles/entities",
        json={
            "novel_id": novel_id,
            "entity_type": "character",
            "name": "人工确认角色",
            "source": "deterministic",
        },
        headers=_auth_headers(user_id),
    )

    assert created.status_code == 201
    entity = created.json()
    assert entity["source"] == "manual"
    assert entity["is_approved"] is True
    assert entity["extra_data"]["lifecycle"]["status"] == "approved"
    assert entity["extra_data"]["lifecycle"]["changed_by"] == user_id
    assert entity["extra_data"]["lifecycle"]["reason"] == "manual create"

    production = client.get(
        f"/api/v1/story-bibles/entities/production-pack/{novel_id}",
        headers=_auth_headers(user_id),
    )
    assert production.status_code == 200
    assert [item["id"] for item in production.json()["characters"]] == [entity["id"]]


def test_legacy_extract_assets_persists_candidates_with_evidence_but_creates_no_assets(client: TestClient) -> None:
    user_id = f"entity-api-{uuid4().hex[:20]}"
    novel_id = _create_novel(client, user_id)

    response = client.post(
        "/api/v1/story-bibles/entities/extract-assets",
        json={
            "novel_id": novel_id,
            "text": "角色：候选林澈。候选林澈走进旧邮局。道具：候选铜铃。",
            "entity_types": ["character", "prop"],
            "persist_entities": True,
            "create_assets": True,
            "asset_scope": "entity",
        },
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["entities"]
    assert payload["assets"] == []
    assert {item["extra_data"]["lifecycle"]["status"] for item in payload["entities"]} == {"candidate"}

    candidate = next(item for item in payload["entities"] if item["entity_type"] == "character")
    promoted = client.post(
        f"/api/v1/story-bibles/entities/{candidate['id']}/promote",
        json={"reason": "旧入口证据通过"},
        headers=_auth_headers(user_id),
    )
    assert promoted.status_code == 200


def test_legacy_reextract_keeps_new_entities_in_review_and_out_of_assets(client: TestClient) -> None:
    user_id = f"entity-api-{uuid4().hex[:20]}"
    novel_id = _create_novel(client, user_id)

    response = client.post(
        "/api/v1/story-bibles/entities/reextract",
        json={
            "novel_id": novel_id,
            "text": "角色：复抽林澈。复抽林澈携带复抽铜铃。道具：复抽铜铃。",
            "entity_types": ["character", "prop"],
            "mode": "overwrite",
            "create_assets": True,
            "asset_scope": "entity",
        },
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["created_count"] >= 2
    assert payload["assets"] == []
    assert {item["extra_data"]["lifecycle"]["status"] for item in payload["entities"]} == {"candidate"}


def test_generate_and_chapter_sync_do_not_copy_new_candidates_into_story_bible(client: TestClient) -> None:
    user_id = f"entity-api-{uuid4().hex[:20]}"
    novel_id = _create_novel(client, user_id)
    chapter_id = f"entity-api-chapter-{uuid4()}"

    async def seed_chapter() -> None:
        async with AsyncSessionLocal() as db:
            db.add(
                Chapter(
                    id=chapter_id,
                    user_id=user_id,
                    novel_id=novel_id,
                    title="候选章节",
                    chapter_number=1,
                    content="角色：候选沈砚。候选沈砚进入候选码头。场景：候选码头。",
                )
            )
            await db.commit()

    asyncio.run(seed_chapter())

    generated = client.post(
        "/api/v1/story-bibles/generate-from-novel",
        json={"novel_id": novel_id, "title": "候选隔离圣经"},
        headers=_auth_headers(user_id),
    )
    assert generated.status_code == 201
    bible = generated.json()
    assert bible["character_rules"] == []
    assert bible["scene_rules"] == []

    synced = client.post(
        "/api/v1/story-bibles/sync-from-chapter",
        json={"story_bible_id": bible["id"], "chapter_id": chapter_id},
        headers=_auth_headers(user_id),
    )
    assert synced.status_code == 200
    assert synced.json()["character_rules"] == []
    assert synced.json()["scene_rules"] == []


def test_legacy_bulk_approve_reports_each_skip_without_partial_422(client: TestClient) -> None:
    user_id = f"entity-api-{uuid4().hex[:20]}"
    novel_id = _create_novel(client, user_id)
    safe = client.post(
        "/api/v1/story-bibles/entities",
        json={"novel_id": novel_id, "entity_type": "prop", "name": "安全人工道具"},
        headers=_auth_headers(user_id),
    ).json()
    duplicate_ids = []
    for name in ("重复角色", "重复角色"):
        created = client.post(
            "/api/v1/story-bibles/entities",
            json={
                "novel_id": novel_id,
                "entity_type": "character",
                "name": name,
            },
            headers=_auth_headers(user_id),
        )
        assert created.status_code == 201
        duplicate_ids.append(created.json()["id"])

    response = client.post(
        "/api/v1/story-bibles/entities/bulk-approve",
        json={"entity_ids": [safe["id"], *duplicate_ids], "approved": True},
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    assert response.json()["updated_count"] == 1
    assert [item["id"] for item in response.json()["approved_entities"]] == [safe["id"]]
    assert {item["id"] for item in response.json()["skipped"]} == set(duplicate_ids)
    assert {item["reason"] for item in response.json()["skipped"]} == {"存在高重复风险，不能批量定稿"}
