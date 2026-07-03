from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models import Asset, Character, Novel, Shot, StoryBible, StoryEntity
from app.services.asset_generation_service import ASSET_VIEW_PRESETS
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


def _run(coro):
    return asyncio.run(coro)


def _view_keys(entity_type: str) -> list[str]:
    return [view["key"] for view in ASSET_VIEW_PRESETS[entity_type]["views"]]


async def _seed_character_card_fixture() -> dict[str, str]:
    user_id = f"cards-user-{uuid4().hex[:20]}"
    novel_id = f"cards-novel-{uuid4()}"
    entity_id = f"cards-character-{uuid4()}"

    async with AsyncSessionLocal() as db:
        db.add(Novel(id=novel_id, user_id=user_id, title="定稿卡角色小说"))
        db.add(
            Character(
                id=f"cards-character-model-{uuid4()}",
                user_id=user_id,
                novel_id=novel_id,
                name="林澈",
                description="角色档案描述",
                personality="冷静敏锐",
            )
        )
        db.add(
            StoryEntity(
                id=entity_id,
                user_id=user_id,
                novel_id=novel_id,
                entity_type="character",
                name="林澈",
                description="黑发少年，青色长衫",
                attributes={
                    "visual_dna": {"hair": "black", "costume": "青色长衫"},
                    "relationships": [{"name": "阿月", "type": "ally"}],
                    "forbidden_changes": ["不要改变发色"],
                },
                confidence=98,
                is_approved=True,
            )
        )
        db.add(
            StoryBible(
                id=f"cards-bible-{uuid4()}",
                user_id=user_id,
                novel_id=novel_id,
                title="定稿卡 Story Bible",
                character_rules=[{"name": "林澈", "voice": "calm_male", "voice_speed": 0.9}],
                extra_data={
                    "state_machine": {
                        "current_state": {
                            "characters": {
                                "林澈": {"mood": "警觉", "location": "云桥"},
                            }
                        }
                    }
                },
            )
        )
        db.add_all(
            [
                Asset(
                    id=f"cards-asset-front-{uuid4()}",
                    user_id=user_id,
                    novel_id=novel_id,
                    entity_id=entity_id,
                    entity_type="character",
                    category="character",
                    name="林澈正面定稿",
                    asset_type="image",
                    url="https://cdn.example.test/linche-front.png",
                    version=2,
                    is_active=True,
                    is_final=True,
                    is_locked=True,
                    generation_params={"view_key": "front"},
                ),
                Asset(
                    id=f"cards-asset-side-{uuid4()}",
                    user_id=user_id,
                    novel_id=novel_id,
                    entity_id=entity_id,
                    entity_type="character",
                    category="character",
                    name="林澈侧面草稿",
                    asset_type="image",
                    url="https://cdn.example.test/linche-side.png",
                    version=1,
                    is_active=True,
                    is_final=True,
                    is_locked=False,
                    generation_params={"view_key": "side"},
                ),
            ]
        )
        db.add(
            Shot(
                id=f"cards-shot-{uuid4()}",
                storyboard_id=f"cards-storyboard-{uuid4()}",
                user_id=user_id,
                shot_number=7,
                extra_data={
                    "novel_id": novel_id,
                    "entity_refs": {
                        "characters": [{"entity_id": entity_id, "name": "林澈"}],
                        "scenes": [],
                        "props": [],
                    },
                },
            )
        )
        await db.commit()

    return {"user_id": user_id, "novel_id": novel_id, "entity_id": entity_id}


async def _seed_scene_prop_fixture() -> dict[str, str]:
    user_id = f"cards-user-{uuid4().hex[:20]}"
    novel_id = f"cards-novel-{uuid4()}"
    scene_id = f"cards-scene-{uuid4()}"
    prop_id = f"cards-prop-{uuid4()}"

    async with AsyncSessionLocal() as db:
        db.add(Novel(id=novel_id, user_id=user_id, title="定稿卡场景道具小说"))
        db.add_all(
            [
                StoryEntity(
                    id=scene_id,
                    user_id=user_id,
                    novel_id=novel_id,
                    entity_type="scene",
                    name="云桥",
                    description="悬在云海上的石桥",
                    attributes={"scene_dna": {"weather": "薄雾"}},
                    confidence=95,
                    is_approved=True,
                ),
                StoryEntity(
                    id=prop_id,
                    user_id=user_id,
                    novel_id=novel_id,
                    entity_type="prop",
                    name="青铜铃",
                    description="旧铜铃铛",
                    attributes={"prop_dna": {"material": "bronze"}},
                    confidence=92,
                    is_approved=True,
                ),
                Asset(
                    id=f"cards-scene-establishing-{uuid4()}",
                    user_id=user_id,
                    novel_id=novel_id,
                    entity_id=scene_id,
                    entity_type="scene",
                    category="scene",
                    name="云桥全景",
                    asset_type="image",
                    url="https://cdn.example.test/scene-establishing.png",
                    is_active=True,
                    is_final=True,
                    is_locked=True,
                    generation_params={"view_key": "establishing"},
                ),
                Asset(
                    id=f"cards-prop-main-{uuid4()}",
                    user_id=user_id,
                    novel_id=novel_id,
                    entity_id=prop_id,
                    entity_type="prop",
                    category="prop",
                    name="青铜铃主视图",
                    asset_type="image",
                    url="https://cdn.example.test/prop-main.png",
                    is_active=True,
                    is_final=True,
                    is_locked=True,
                    generation_params={"view_key": "main"},
                ),
            ]
        )
        await db.commit()

    return {"user_id": user_id, "novel_id": novel_id, "scene_id": scene_id, "prop_id": prop_id}


async def _seed_summary_fixture() -> dict[str, str]:
    user_id = f"cards-user-{uuid4().hex[:20]}"
    novel_id = f"cards-novel-{uuid4()}"
    prop_id = f"cards-prop-{uuid4()}"
    character_id = f"cards-character-{uuid4()}"

    async with AsyncSessionLocal() as db:
        db.add(Novel(id=novel_id, user_id=user_id, title="定稿卡汇总小说"))
        db.add_all(
            [
                StoryEntity(
                    id=prop_id,
                    user_id=user_id,
                    novel_id=novel_id,
                    entity_type="prop",
                    name="玉符",
                    description="泛光玉符",
                    attributes={},
                ),
                StoryEntity(
                    id=character_id,
                    user_id=user_id,
                    novel_id=novel_id,
                    entity_type="character",
                    name="无声角色",
                    description="缺少三视图和声线",
                    attributes={},
                ),
                Asset(
                    id=f"cards-prop-ready-{uuid4()}",
                    user_id=user_id,
                    novel_id=novel_id,
                    entity_id=prop_id,
                    entity_type="prop",
                    category="prop",
                    name="玉符主视图",
                    asset_type="image",
                    url="https://cdn.example.test/prop-ready.png",
                    is_active=True,
                    is_final=True,
                    is_locked=True,
                    generation_params={"view_key": "main"},
                ),
            ]
        )
        await db.commit()

    return {"user_id": user_id, "novel_id": novel_id, "prop_id": prop_id, "character_id": character_id}


async def _seed_supporting_finalize_fixture() -> dict[str, str]:
    user_id = f"cards-user-{uuid4().hex[:20]}"
    novel_id = f"cards-novel-{uuid4()}"
    protagonist_id = f"cards-protagonist-{uuid4()}"
    supporting_id = f"cards-supporting-{uuid4()}"
    rare_id = f"cards-rare-{uuid4()}"

    async with AsyncSessionLocal() as db:
        db.add(Novel(id=novel_id, user_id=user_id, title="配角批量定稿小说"))
        db.add(
            StoryBible(
                id=f"cards-bible-{uuid4()}",
                user_id=user_id,
                novel_id=novel_id,
                title="配角批量定稿 Story Bible",
                character_rules=[{"name": "孙剑", "role": "protagonist", "voice": "hero_voice"}],
            )
        )
        db.add_all(
            [
                StoryEntity(
                    id=protagonist_id,
                    user_id=user_id,
                    novel_id=novel_id,
                    entity_type="character",
                    name="孙剑",
                    description="主角",
                    attributes={"role_tier": "protagonist"},
                    is_approved=True,
                ),
                StoryEntity(
                    id=supporting_id,
                    user_id=user_id,
                    novel_id=novel_id,
                    entity_type="character",
                    name="阿月",
                    description="掌灯的配角少女",
                    attributes={},
                    is_approved=True,
                ),
                StoryEntity(
                    id=rare_id,
                    user_id=user_id,
                    novel_id=novel_id,
                    entity_type="character",
                    name="路人甲",
                    description="只出现一次",
                    attributes={},
                    is_approved=True,
                ),
            ]
        )
        for index in range(1, 4):
            character_refs = [{"entity_id": supporting_id, "name": "阿月"}]
            if index == 1:
                character_refs.append({"entity_id": rare_id, "name": "路人甲"})
            db.add(
                Shot(
                    id=f"cards-supporting-shot-{uuid4()}",
                    storyboard_id=f"cards-supporting-storyboard-{uuid4()}",
                    user_id=user_id,
                    shot_number=index,
                    extra_data={
                        "novel_id": novel_id,
                        "entity_refs": {
                            "characters": character_refs,
                            "scenes": [],
                            "props": [],
                        },
                    },
                )
            )
        await db.commit()

    return {
        "user_id": user_id,
        "novel_id": novel_id,
        "protagonist_id": protagonist_id,
        "supporting_id": supporting_id,
        "rare_id": rare_id,
    }


def test_character_card_aggregates_views_voice_profile_state_usage_and_readiness(client: TestClient) -> None:
    fixture = _run(_seed_character_card_fixture())

    response = client.get(
        f"/api/v1/production-cards/entity/{fixture['entity_id']}",
        headers=_auth_headers(fixture["user_id"]),
    )

    assert response.status_code == 200
    card = response.json()
    assert card["entity_id"] == fixture["entity_id"]
    assert card["entity_type"] == "character"
    assert card["novel_id"] == fixture["novel_id"]
    assert card["visual"]["required_views"] == ["front", "side", "back"]
    assert card["visual"]["missing_views"] == ["back"]
    assert card["visual"]["locked_count"] == 1
    views_by_key = {view["view_key"]: view for view in card["visual"]["views"]}
    assert views_by_key["front"]["is_locked"] is True
    assert views_by_key["front"]["is_final"] is True
    assert views_by_key["front"]["version"] == 2
    assert views_by_key["side"]["is_locked"] is False
    assert card["voice"] == {
        "voice": "calm_male",
        "voice_speed": 0.9,
        "story_bible_id": card["voice"]["story_bible_id"],
        "locked": True,
    }
    assert card["voice"]["story_bible_id"]
    assert card["profile"]["description"] == "黑发少年，青色长衫"
    assert card["profile"]["visual_dna"] == {"hair": "black", "costume": "青色长衫"}
    assert card["profile"]["personality"] == "冷静敏锐"
    assert card["profile"]["relationships"] == [{"name": "阿月", "type": "ally"}]
    assert card["profile"]["forbidden_changes"] == ["不要改变发色"]
    assert card["state"] == {"mood": "警觉", "location": "云桥"}
    assert card["usage"]["shot_count"] == 1
    assert card["usage"]["last_used_at"]
    assert card["readiness"]["final_ready"] is False
    assert card["readiness"]["score"] < 100
    gap_codes = {gap["code"]: gap for gap in card["readiness"]["gaps"]}
    assert "view_missing:back" in gap_codes
    assert "view_unlocked:side" in gap_codes
    assert fixture["entity_id"] in gap_codes["view_missing:back"]["fix_url"]
    assert gap_codes["view_missing:back"]["fix_url"].startswith("/assets?")


def test_scene_and_prop_cards_use_type_specific_required_views(client: TestClient) -> None:
    fixture = _run(_seed_scene_prop_fixture())

    scene_response = client.get(
        f"/api/v1/production-cards/entity/{fixture['scene_id']}",
        headers=_auth_headers(fixture["user_id"]),
    )
    prop_response = client.get(
        f"/api/v1/production-cards/entity/{fixture['prop_id']}",
        headers=_auth_headers(fixture["user_id"]),
    )

    assert scene_response.status_code == 200
    assert prop_response.status_code == 200
    scene_card = scene_response.json()
    prop_card = prop_response.json()
    assert scene_card["visual"]["required_views"] == _view_keys("scene")
    assert scene_card["visual"]["missing_views"] == ["layout", "detail", "lighting"]
    assert scene_card["voice"] is None
    assert scene_card["readiness"]["final_ready"] is False
    assert prop_card["visual"]["required_views"] == ["main"]
    assert prop_card["visual"]["missing_views"] == []
    assert prop_card["voice"] is None
    assert prop_card["readiness"]["final_ready"] is True


def test_novel_cards_summary_counts_ready_and_incomplete(client: TestClient) -> None:
    fixture = _run(_seed_summary_fixture())

    response = client.get(
        f"/api/v1/production-cards/novel/{fixture['novel_id']}",
        headers=_auth_headers(fixture["user_id"]),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["novel_id"] == fixture["novel_id"]
    assert {card["entity_id"] for card in payload["cards"]} == {fixture["prop_id"], fixture["character_id"]}
    assert payload["summary"] == {"ready": 1, "incomplete": 1}


def test_batch_finalize_supporting_creates_single_view_and_voice(client: TestClient) -> None:
    fixture = _run(_seed_supporting_finalize_fixture())

    response = client.post(
        f"/api/v1/production-cards/novel/{fixture['novel_id']}/batch-finalize-supporting",
        json={"min_occurrences": 2, "voice_pool": ["voice_a", "voice_b"]},
        headers=_auth_headers(fixture["user_id"]),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["finalized"] == [
        {
            "entity_id": fixture["supporting_id"],
            "name": "阿月",
            "asset_id": payload["finalized"][0]["asset_id"],
            "voice": "voice_a",
        }
    ]
    assert payload["skipped"]
    skipped_by_id = {item["entity_id"]: item["reason"] for item in payload["skipped"]}
    assert skipped_by_id[fixture["protagonist_id"]] == "protagonist"
    assert skipped_by_id[fixture["rare_id"]] == "occurrence_below_threshold"

    card_response = client.get(
        f"/api/v1/production-cards/entity/{fixture['supporting_id']}",
        headers=_auth_headers(fixture["user_id"]),
    )
    assert card_response.status_code == 200
    card = card_response.json()
    assert card["visual"]["required_views"] == ["front"]
    assert card["visual"]["missing_views"] == []
    assert card["visual"]["locked_count"] == 1
    assert card["voice"]["voice"] == "voice_a"
    assert card["voice"]["locked"] is True
    assert card["readiness"]["final_ready"] is True


def test_batch_finalize_supporting_filters_by_min_occurrences_and_round_robins_explicit_voice_pool(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _run(_seed_supporting_finalize_fixture())
    second_id = _run(_add_recurring_supporting_candidate(fixture, "青岚", 2))
    third_id = _run(_add_recurring_supporting_candidate(fixture, "石伯", 2))

    async def fake_generate_asset_image_url(self, prompt: str, *, size: str, aspect_ratio: str, prefix: str) -> str:
        return f"https://cdn.example.test/{prefix}.png"

    monkeypatch.setattr(
        "app.services.asset_generation_service.AssetGenerationService._generate_asset_image_url",
        fake_generate_asset_image_url,
    )

    response = client.post(
        f"/api/v1/production-cards/novel/{fixture['novel_id']}/batch-finalize-supporting",
        json={"min_occurrences": 2, "voice_pool": ["voice_a", "voice_b"]},
        headers=_auth_headers(fixture["user_id"]),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert [item["entity_id"] for item in payload["finalized"]] == [fixture["supporting_id"], second_id, third_id]
    assert [item["voice"] for item in payload["finalized"]] == ["voice_a", "voice_b", "voice_a"]
    skipped_by_id = {item["entity_id"]: item for item in payload["skipped"]}
    assert skipped_by_id[fixture["rare_id"]]["reason"] == "occurrence_below_threshold"
    assert skipped_by_id[fixture["rare_id"]]["occurrences"] == 1


def test_batch_finalize_supporting_records_image_model_config_on_generated_asset(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _run(_seed_supporting_finalize_fixture())
    configured_ids: list[str | None] = []

    async def fake_configure_image_model(self, model_config_id: str | None = None):
        configured_ids.append(model_config_id)
        self.provider_name = "test-provider"
        self.model_id = "test-image-model"
        self.image_service = object()

    async def fake_generate_asset_image_url(self, prompt: str, *, size: str, aspect_ratio: str, prefix: str) -> str:
        return f"https://cdn.example.test/{prefix}.png"

    monkeypatch.setattr(
        "app.services.asset_generation_service.AssetGenerationService.configure_image_model",
        fake_configure_image_model,
    )
    monkeypatch.setattr(
        "app.services.asset_generation_service.AssetGenerationService._generate_asset_image_url",
        fake_generate_asset_image_url,
    )

    response = client.post(
        f"/api/v1/production-cards/novel/{fixture['novel_id']}/batch-finalize-supporting",
        json={"min_occurrences": 2, "image_model_config_id": "image-config-s4b"},
        headers=_auth_headers(fixture["user_id"]),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert configured_ids == ["image-config-s4b"]
    params = _run(_asset_generation_params(payload["finalized"][0]["asset_id"]))
    assert params["image_model_config_id"] == "image-config-s4b"


def test_batch_finalize_supporting_defaults_to_builtin_tts_voice(client: TestClient) -> None:
    fixture = _run(_seed_supporting_finalize_fixture())

    response = client.post(
        f"/api/v1/production-cards/novel/{fixture['novel_id']}/batch-finalize-supporting",
        json={"min_occurrences": 2},
        headers=_auth_headers(fixture["user_id"]),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["finalized"][0]["voice"] == "female-shaonv"


def test_supporting_tier_readiness_only_requires_front(client: TestClient) -> None:
    fixture = _run(_seed_supporting_finalize_fixture())
    _run(_add_supporting_front_asset_and_voice(fixture))

    response = client.get(
        f"/api/v1/production-cards/entity/{fixture['supporting_id']}",
        headers=_auth_headers(fixture["user_id"]),
    )

    assert response.status_code == 200
    card = response.json()
    assert card["visual"]["required_views"] == ["front"]
    assert card["readiness"]["final_ready"] is True


async def _add_supporting_front_asset_and_voice(fixture: dict[str, str]) -> None:
    async with AsyncSessionLocal() as db:
        db.add(
            Asset(
                id=f"cards-supporting-front-{uuid4()}",
                user_id=fixture["user_id"],
                novel_id=fixture["novel_id"],
                entity_id=fixture["supporting_id"],
                entity_type="character",
                category="character",
                name="阿月正面定稿",
                asset_type="image",
                url="https://cdn.example.test/ayue-front.png",
                is_active=True,
                is_final=True,
                is_locked=True,
                generation_params={"view_key": "front"},
            )
        )
        result = await db.execute(
            select(StoryBible).where(StoryBible.user_id == fixture["user_id"], StoryBible.novel_id == fixture["novel_id"])
        )
        story_bible = result.scalar_one()
        story_bible.character_rules = [
            *(story_bible.character_rules or []),
            {"name": "阿月", "role_tier": "supporting", "voice": "voice_supporting"},
        ]
        entity = await db.get(StoryEntity, fixture["supporting_id"])
        assert entity is not None
        entity.attributes = {**(entity.attributes or {}), "role_tier": "supporting"}
        await db.commit()


async def _add_recurring_supporting_candidate(fixture: dict[str, str], name: str, occurrences: int) -> str:
    entity_id = f"cards-supporting-extra-{uuid4()}"
    async with AsyncSessionLocal() as db:
        db.add(
            StoryEntity(
                id=entity_id,
                user_id=fixture["user_id"],
                novel_id=fixture["novel_id"],
                entity_type="character",
                name=name,
                description=f"{name} 配角",
                attributes={},
                is_approved=True,
            )
        )
        for index in range(occurrences):
            db.add(
                Shot(
                    id=f"cards-supporting-extra-shot-{uuid4()}",
                    storyboard_id=f"cards-supporting-extra-storyboard-{uuid4()}",
                    user_id=fixture["user_id"],
                    shot_number=100 + index,
                    extra_data={
                        "novel_id": fixture["novel_id"],
                        "entity_refs": {
                            "characters": [{"entity_id": entity_id, "name": name}],
                            "scenes": [],
                            "props": [],
                        },
                    },
                )
            )
        await db.commit()
    return entity_id


async def _asset_generation_params(asset_id: str) -> dict:
    async with AsyncSessionLocal() as db:
        asset = await db.get(Asset, asset_id)
        assert asset is not None
        return asset.generation_params or {}
