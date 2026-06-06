from types import SimpleNamespace
from datetime import UTC, datetime

from pydantic import ValidationError
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.database import AsyncSessionLocal
from app.models import Asset, Chapter, LLMConfig, LLMModel, LLMProvider, Novel, Script, Shot, Storyboard
from init_db import init_db
from main import app


def _entity(entity_type: str, name: str, confidence: int = 90):
    return SimpleNamespace(
        id=f"{entity_type}-{name}",
        entity_type=entity_type,
        name=name,
        aliases=[],
        confidence=confidence,
        updated_at=None,
    )


def test_character_extract_request_accepts_large_legacy_count_without_hard_cap():
    from app.api.v1.endpoints.characters import CharacterExtractRequest

    try:
        request = CharacterExtractRequest(
            text="这是一段足够长的小说文本。" * 10,
            character_count=80,
            auto_generate_avatar=False,
        )
    except ValidationError as exc:
        raise AssertionError("character_count should remain backwards compatible without a 30-role cap") from exc

    assert request.character_count == 80


def test_character_extraction_prompt_requests_complete_character_set():
    from app.api.v1.endpoints.characters import _build_character_extraction_user_prompt

    prompt = _build_character_extraction_user_prompt("张三遇见李四。", chunk_index=1, chunk_total=1)

    assert "最多" not in prompt
    assert "所有" in prompt
    assert "不得因为数量较多而省略" in prompt


def test_merge_character_records_keeps_more_than_thirty_and_merges_aliases():
    from app.api.v1.endpoints.characters import _merge_character_records

    records = [
        {
            "name": f"角色{i}",
            "description": f"第{i}位角色",
            "appearance": f"外貌{i}",
            "personality": "冷静",
            "voice": "清亮",
            "tags": ["配角"],
            "aliases": [],
        }
        for i in range(35)
    ]
    records.append(
        {
            "name": "角色1",
            "description": "又名阿一，主角同伴",
            "appearance": "",
            "personality": "果断",
            "voice": "",
            "tags": ["同伴"],
            "aliases": ["阿一"],
        }
    )

    merged = _merge_character_records(records)

    assert len(merged) == 35
    role_one = next(item for item in merged if item["name"] == "角色1")
    assert "阿一" in role_one["aliases"]
    assert "同伴" in role_one["tags"]
    assert "又名阿一" in role_one["description"]


def test_fallback_entities_include_all_reasonable_matches_instead_of_2_1_1_1_caps():
    from app.services.consistency_context import _select_fallback_entities_for_generation

    grouped = {"character": [], "scene": [], "prop": [], "event": []}
    entities = [
        *[_entity("character", f"角色{i}", 90 - i) for i in range(6)],
        *[_entity("scene", f"场景{i}", 80 - i) for i in range(3)],
        *[_entity("prop", f"道具{i}", 70 - i) for i in range(3)],
        *[_entity("event", f"事件{i}", 60 - i) for i in range(2)],
    ]

    result = _select_fallback_entities_for_generation(entities, grouped, max_total=20)

    assert [item.name for item in result["character"]] == [f"角色{i}" for i in range(6)]
    assert [item.name for item in result["scene"]] == [f"场景{i}" for i in range(3)]
    assert [item.name for item in result["prop"]] == [f"道具{i}" for i in range(3)]
    assert [item.name for item in result["event"]] == [f"事件{i}" for i in range(2)]


def test_collect_character_multiview_refs_from_locked_assets():
    from app.api.v1.endpoints.video import _collect_character_multiview_refs

    character_refs = [{"character_id": "char-1", "name": "萧炎"}]
    assets = [
        SimpleNamespace(
            id="asset-front",
            character_id="char-1",
            name="萧炎正面定稿",
            url="/static/characters/xiao-front.png",
            thumbnail_url=None,
            category="character",
            is_locked=True,
            is_final=True,
            version=2,
            generation_params={"reference_role": "character_multiview", "view_angle": "front"},
            updated_at=None,
        ),
        SimpleNamespace(
            id="asset-side",
            character_id="char-1",
            name="萧炎侧面定稿",
            url="/static/characters/xiao-side.png",
            thumbnail_url=None,
            category="character",
            is_locked=True,
            is_final=True,
            version=1,
            generation_params={"reference_role": "character_multiview", "view_angle": "side"},
            updated_at=None,
        ),
        SimpleNamespace(
            id="asset-draft",
            character_id="char-1",
            name="草稿",
            url="/static/characters/draft.png",
            thumbnail_url=None,
            category="character",
            is_locked=False,
            is_final=False,
            version=1,
            generation_params={"reference_role": "character_multiview", "view_angle": "front"},
            updated_at=None,
        ),
    ]

    refs = _collect_character_multiview_refs(assets, character_refs)

    assert [(item["asset_id"], item["view_angle"]) for item in refs] == [
        ("asset-front", "front"),
        ("asset-side", "side"),
    ]
    assert refs[0]["character_name"] == "萧炎"


def test_prompt_composer_keeps_medium_story_bible_rule_sets():
    from app.services.prompt_composer import compose_generation_prompt

    story_bible = SimpleNamespace(
        style="统一玄幻动漫风格",
        worldview="修真大陆",
        negative_prompt=None,
        character_rules=[{"name": f"角色{i}", "appearance": f"外貌{i}"} for i in range(12)],
        scene_rules=[{"name": f"场景{i}", "description": f"空间{i}"} for i in range(10)],
        prop_rules=[],
        event_timeline=[],
        extra_data={},
    )

    prompt = compose_generation_prompt(task="shot_video", story_bible=story_bible)

    assert "角色11" in prompt
    assert "场景9" in prompt


def test_novel_continuity_entity_locks_keep_medium_cast():
    from app.services.novel_continuity import _entity_locks

    entities = [
        SimpleNamespace(
            id=f"char-{index}",
            entity_type="character",
            name=f"角色{index}",
            description=f"第{index}位角色",
            evidence="原文证据",
            chapter_id=None,
            attributes={"visual_dna": {"hair": "black", "costume": f"服装{index}"}},
            source="ai",
        )
        for index in range(15)
    ]

    locks = _entity_locks(entities)

    assert len(locks["characters"]) == 15
    assert locks["characters"][0]["visual_dna"]["hair"] == "black"


def test_video_job_response_exposes_character_multiview_refs():
    from app.api.v1.endpoints.video import _build_video_job_response

    multiview_refs = [{"character_id": "char-1", "view_angle": "front", "url": "/static/front.png"}]
    job = SimpleNamespace(
        id="job-1",
        task_id="task-1",
        title="测试任务",
        prompt="生成视频",
        project_id=None,
        workflow_id=None,
        image_url=None,
        model_name="模型",
        status="succeeded",
        progress=100,
        video_url="/static/video.mp4",
        cover_url=None,
        error_message=None,
        duration=5,
        resolution="720p",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        extra_data={
            "character_multiview_refs": multiview_refs,
            "consistency": {"character_multiview_refs": multiview_refs},
        },
    )

    response = _build_video_job_response(job)

    assert response.character_multiview_refs == multiview_refs


def test_normalize_entity_refs_converts_legacy_ids_and_preserves_dict_refs():
    from app.services.entity_ref_normalizer import entity_ref_ids, normalize_entity_refs

    normalized = normalize_entity_refs(
        {
            "characters": ["char-1", {"entity_id": "char-2", "name": "沈砚"}],
            "scenes": [{"id": "scene-1", "name": "旧码头"}],
            "props": [{"entity_id": "prop-1", "entity_type": "prop", "name": "铜铃"}],
            "events": [],
        }
    )

    assert normalized["characters"][0] == {"entity_id": "char-1", "entity_type": "character"}
    assert normalized["characters"][1]["name"] == "沈砚"
    assert normalized["scenes"][0]["entity_id"] == "scene-1"
    assert normalized["scenes"][0]["entity_type"] == "scene"
    assert entity_ref_ids(normalized, "characters") == ["char-1", "char-2"]


@pytest.mark.asyncio
async def test_asset_lock_service_handles_normalized_refs_without_unlocking_shared_assets():
    from app.services.asset_lock_service import AssetLockService

    user_id = f"asset-lock-user-{uuid4()}"
    entity_id = f"entity-{uuid4()}"
    asset_id = f"asset-{uuid4()}"
    service = AssetLockService()

    async with AsyncSessionLocal() as db:
        await db.execute(delete(Asset).where(Asset.user_id == user_id))
        asset = Asset(
            id=asset_id,
            user_id=user_id,
            category="character",
            entity_id=entity_id,
            entity_type="character",
            name="沈砚正面定稿",
            description="黑发青年，灰蓝长衫",
            asset_type="image",
            url="https://cdn.example.com/shenyan-front.png",
            is_locked=True,
            is_final=True,
            is_active=True,
        )
        db.add(asset)
        await db.flush()

        shot = SimpleNamespace(
            id=f"shot-{uuid4()}",
            user_id=user_id,
            extra_data={"entity_refs": {"characters": [{"entity_id": entity_id, "name": "沈砚"}]}},
        )

        result = await service.lock_shot_assets(db, shot)
        assert result["count"] == 1
        assert shot.extra_data["locked_assets"][f"character_{entity_id}"]["asset_id"] == asset_id

        unlock_result = await service.unlock_shot_assets(db, shot)
        assert unlock_result["unlocked_count"] == 1
        assert "locked_assets" not in shot.extra_data

        persisted = await db.get(Asset, asset_id)
        assert persisted is not None
        assert persisted.is_locked is True
        assert persisted.locked_by == asset.locked_by


@pytest.mark.asyncio
async def test_build_consistency_prompt_includes_shot_locked_assets():
    from app.services.consistency_context import build_consistency_prompt

    user_id = f"locked-prompt-user-{uuid4()}"
    novel_id = f"novel-{uuid4()}"
    script_id = f"script-{uuid4()}"
    storyboard_id = f"storyboard-{uuid4()}"
    shot_id = f"shot-{uuid4()}"

    async with AsyncSessionLocal() as db:
        db.add(Novel(id=novel_id, user_id=user_id, title="雾港铜铃", description="悬疑动漫"))
        db.add(Script(id=script_id, user_id=user_id, novel_id=novel_id, title="第一章剧本", content="沈砚追查铜铃"))
        db.add(Storyboard(id=storyboard_id, user_id=user_id, script_id=script_id, novel_id=novel_id, title="旧码头分镜"))
        db.add(
            Shot(
                id=shot_id,
                user_id=user_id,
                storyboard_id=storyboard_id,
                shot_number=1,
                prompt="沈砚站在旧码头",
                extra_data={
                    "locked_assets": {
                        "character-1": {
                            "asset_id": "asset-1",
                            "entity_type": "character",
                            "entity_id": "char-1",
                            "asset_name": "沈砚正面定稿",
                            "description": "黑发青年，灰蓝长衫",
                        }
                    }
                },
            )
        )
        await db.commit()

        context = await build_consistency_prompt(db, user_id, task="shot_video", shot_id=shot_id)

    assert "锁定资产一致性约束" in context["prompt"]
    assert "沈砚正面定稿" in context["prompt"]
    assert context["metadata"]["locked_assets"][0]["name"] == "沈砚正面定稿"


@pytest.fixture(scope="module", autouse=True)
def _init_database() -> None:
    init_db()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DEV_MODE", "true")
    return TestClient(app)


def _auth_headers(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


def test_consistency_preflight_standard_route_reports_unverified_model_and_local_reference(client: TestClient) -> None:
    user_id = str(uuid4())

    provider_id = f"provider-{uuid4()}"
    model_id = f"model-{uuid4()}"
    config_id = f"config-{uuid4()}"

    async def _seed_model_config() -> None:
        async with AsyncSessionLocal() as db:
            db.add(
                LLMProvider(
                    id=provider_id,
                    name=f"preflight-provider-{uuid4()}",
                    name_cn="预检供应商",
                    is_active=True,
                )
            )
            db.add(
                LLMModel(
                    id=model_id,
                    provider_id=provider_id,
                    model_id="preflight-video-model",
                    model_name="Preflight Video Model",
                    model_type="video",
                    capabilities=["text_to_video", "image_to_video"],
                    is_active=True,
                )
            )
            config = LLMConfig(
                id=config_id,
                user_id=user_id,
                model_id=model_id,
                name="未验证视频模型",
                test_status="pending",
                is_active=True,
            )
            config.set_api_key_encrypted("sk-preflight")
            db.add(config)
            await db.commit()

    import asyncio

    asyncio.run(_seed_model_config())

    response = client.post(
        "/api/v1/consistency/preflight",
        headers=_auth_headers(user_id),
        json={
            "task_type": "shot_video",
            "model_config_id": config_id,
            "image_url": "/static/generated/images/local.png",
            "production_mode": True,
            "require_public_reference_image": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    codes = {issue["code"] for issue in payload["issues"]}
    assert "model_unverified" in codes
    assert "reference_image_not_public" in codes
    assert payload["blocking_issue_count"] >= 2
    assert payload["ready"] is False
