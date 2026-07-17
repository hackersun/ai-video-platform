import asyncio
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models import Asset, Chapter, LLMConfig, LLMModel, LLMProvider, Novel, Script, Shot, StoryBible, StoryEntity, Storyboard, TTSJob
from app.models.video_job import VideoJob
from app.models.workflow import Workflow
from init_db import init_db
from main import app


@pytest.fixture(scope="module", autouse=True)
def _init_database() -> None:
    init_db()


def _signed_auth_headers(user_id: str) -> dict[str, str]:
    from app.api.v1.endpoints.auth import create_access_token

    return {"Authorization": f"Bearer {create_access_token({'sub': user_id})}"}


async def _seed_llm_config(
    *,
    user_id: str,
    provider_name: str,
    model_type: str,
    capabilities: list[str],
    test_status: str = "pending",
    api_key: str | None = "sk-test",
    api_model_id: str | None = None,
) -> str:
    async with AsyncSessionLocal() as db:
        provider_result = await db.execute(
            select(LLMProvider).where((LLMProvider.name == provider_name) | (LLMProvider.id == provider_name))
        )
        provider = provider_result.scalar_one_or_none()
        if provider is None:
            provider = LLMProvider(
                id=provider_name,
                name=provider_name,
                name_cn=provider_name,
                is_active=True,
            )
            db.add(provider)

        model_id = f"{model_type}-model-{uuid4()}"
        config_id = f"{model_type}-config-{uuid4()}"
        model = LLMModel(
            id=model_id,
            provider_id=provider.id,
            model_id=api_model_id or f"{model_type}-api-model-{uuid4()}",
            model_name=f"{model_type} API Model",
            model_type=model_type,
            capabilities=capabilities,
            is_active=True,
        )
        db.add(model)
        config = LLMConfig(
            id=config_id,
            user_id=user_id,
            model_id=model_id,
            name=f"{model_type} production gate config",
            test_status=test_status,
            is_active=True,
        )
        if api_key is not None:
            config.set_api_key_encrypted(api_key)
        db.add(config)
        await db.commit()
        return config_id


async def _seed_workflow_with_shot(*, user_id: str, image_url: str | None = None) -> dict[str, str]:
    novel_id = f"novel-{uuid4()}"
    chapter_id = f"chapter-{uuid4()}"
    script_id = f"script-{uuid4()}"
    storyboard_id = f"storyboard-{uuid4()}"
    workflow_id = f"workflow-{uuid4()}"
    shot_id = f"shot-{uuid4()}"
    character_entity_id = f"char-{uuid4()}"
    character_asset_id = f"asset-char-{uuid4()}"
    entity_refs = {
        "characters": [{"entity_id": character_entity_id, "name": "沈砚"}],
        "scenes": [],
        "props": [],
        "events": [],
    }

    async with AsyncSessionLocal() as db:
        db.add(Novel(id=novel_id, user_id=user_id, title="生产门禁小说", description="生产门禁"))
        db.add(
            StoryBible(
                id=f"story-bible-{uuid4()}",
                user_id=user_id,
                novel_id=novel_id,
                title="生产门禁 Story Bible",
                style="冷色悬疑动漫风格",
                worldview="近未来港口城市",
                character_rules=[{"name": "沈砚", "rule": "黑发灰蓝长衫"}],
                scene_rules=[{"name": "旧码头", "rule": "冷雾与潮湿木栈道"}],
                prop_rules=[{"name": "铜铃", "rule": "斑驳旧铜材质"}],
                event_timeline=[{"name": "追查铜铃", "sequence": 1}],
                extra_data={
                    "voices": [{"character_name": "沈砚", "voice": "calm_male"}],
                    "state_machine": {
                        "generated_at": "2026-01-01T00:00:00+00:00",
                        "summary": {"characters": 1, "scenes": 1, "props": 1, "events": 1},
                        "current_state": {
                            "characters": {"沈砚": {"state": "追查中"}},
                            "scenes": {"旧码头": {"weather": "冷雾"}},
                            "props": {"铜铃": {"state": "线索"}},
                            "events": [{"name": "追查铜铃", "sequence": 1}],
                        },
                        "issues": [],
                    },
                },
            )
        )
        db.add(
            StoryEntity(
                id=character_entity_id,
                user_id=user_id,
                novel_id=novel_id,
                chapter_id=chapter_id,
                first_seen_chapter_id=chapter_id,
                entity_type="character",
                name="沈砚",
                description="黑发青年，灰蓝长衫",
                attributes={"visual_dna": {"hair": "black", "costume": "灰蓝长衫"}, "voice": "calm_male"},
                confidence=95,
                is_approved=True,
            )
        )
        db.add(
            StoryEntity(
                id=f"scene-{uuid4()}",
                user_id=user_id,
                novel_id=novel_id,
                chapter_id=chapter_id,
                first_seen_chapter_id=chapter_id,
                entity_type="scene",
                name="旧码头",
                description="冷雾弥漫的木质码头",
                attributes={"scene_dna": {"weather": "冷雾", "lighting": "低饱和蓝灰"}},
                confidence=90,
                is_approved=True,
            )
        )
        db.add(
            StoryEntity(
                id=f"prop-{uuid4()}",
                user_id=user_id,
                novel_id=novel_id,
                chapter_id=chapter_id,
                first_seen_chapter_id=chapter_id,
                entity_type="prop",
                name="铜铃",
                description="关键线索道具",
                attributes={"prop_dna": {"material": "旧铜", "state": "斑驳"}},
                confidence=90,
                is_approved=True,
            )
        )
        db.add(
            StoryEntity(
                id=f"event-{uuid4()}",
                user_id=user_id,
                novel_id=novel_id,
                chapter_id=chapter_id,
                first_seen_chapter_id=chapter_id,
                entity_type="event",
                name="追查铜铃",
                description="沈砚在旧码头发现铜铃线索",
                attributes={"sequence": 1, "participants": ["沈砚"], "location": "旧码头"},
                confidence=90,
                is_approved=True,
            )
        )
        db.add(
            Asset(
                id=character_asset_id,
                user_id=user_id,
                category="character",
                entity_id=character_entity_id,
                entity_type="character",
                name="沈砚角色定稿",
                description="黑发灰蓝长衫角色定稿",
                asset_type="image",
                url="https://cdn.example.com/shenyan.png",
                novel_id=novel_id,
                is_active=True,
                is_final=True,
                is_locked=True,
            )
        )
        db.add(
            Chapter(
                id=chapter_id,
                novel_id=novel_id,
                user_id=user_id,
                title="第一章",
                content="沈砚来到旧码头。",
                chapter_number=1,
            )
        )
        db.add(
            Script(
                id=script_id,
                user_id=user_id,
                novel_id=novel_id,
                chapter_id=chapter_id,
                title="第一章剧本",
                content="沈砚追查铜铃。",
                status="draft",
            )
        )
        db.add(
            Storyboard(
                id=storyboard_id,
                user_id=user_id,
                script_id=script_id,
                novel_id=novel_id,
                title="旧码头分镜",
                content={"chapter_id": chapter_id},
                shot_count=1,
            )
        )
        db.add(
            Workflow(
                id=workflow_id,
                user_id=user_id,
                title="生产门禁工作流",
                status="active",
                novel_id=novel_id,
                chapter_id=chapter_id,
                script_id=script_id,
                storyboard_id=storyboard_id,
                current_step=7,
                completed_steps=[1, 2, 3, 4, 5, 6],
                video_job_ids=[],
                tts_job_ids=[],
                synthesis_job_ids=[],
            )
        )
        db.add(
            Shot(
                id=shot_id,
                user_id=user_id,
                storyboard_id=storyboard_id,
                shot_number=1,
                duration=4,
                prompt="沈砚站在旧码头，回头看向雾中的铜铃。",
                dialogue="沈砚: 我会查清铜铃的来历。",
                visual_description="旧码头冷雾弥漫，沈砚保持角色定稿造型。",
                image_url=image_url,
                extra_data={
                    "entity_refs": entity_refs,
                    "subtitle_text": "沈砚: 我会查清铜铃的来历。",
                    "locked_assets": {
                        f"character_{character_entity_id}": {
                            "asset_id": character_asset_id,
                            "entity_type": "character",
                            "entity_id": character_entity_id,
                            "asset_name": "沈砚角色定稿",
                            "asset_url": "https://cdn.example.com/shenyan.png",
                        }
                    },
                },
            )
        )
        await db.commit()

    return {
        "novel_id": novel_id,
        "chapter_id": chapter_id,
        "script_id": script_id,
        "storyboard_id": storyboard_id,
        "workflow_id": workflow_id,
        "shot_id": shot_id,
    }


def test_production_bible_summary_endpoint_exposes_core_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEV_MODE", "true")
    user_id = str(uuid4())
    seeded = asyncio.run(_seed_workflow_with_shot(user_id=user_id, image_url="https://cdn.example.com/shot.png"))

    async def _seed_global_template_entity() -> None:
        async with AsyncSessionLocal() as db:
            db.add(
                StoryEntity(
                    id=f"global-template-{uuid4()}",
                    user_id=user_id,
                    novel_id=None,
                    entity_type="character",
                    name="全局模板角色",
                    description="不应计入单部小说 Production Bible",
                    attributes={},
                    confidence=90,
                )
            )
            await db.commit()

    asyncio.run(_seed_global_template_entity())

    with TestClient(app) as test_client:
        response = test_client.get(
            f"/api/v1/story-bibles/production-bible/{seeded['novel_id']}/summary",
            headers=_signed_auth_headers(user_id),
        )

    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary["style"]["style"] == "冷色悬疑动漫风格"
    assert summary["characters"][0]["name"] == "沈砚"
    assert "全局模板角色" not in {item["name"] for item in summary["characters"]}
    assert summary["counts"]["characters"] == 1
    assert summary["scenes"][0]["name"] == "旧码头"
    assert summary["props"][0]["name"] == "铜铃"
    assert summary["events"][0]["name"] == "追查铜铃"
    assert summary["voices"][0]["character_name"] == "沈砚"
    assert summary["asset_readiness"]["missing_asset_count"] >= 0
    assert summary["state_machine"]["available"] is True


def test_workflow_asset_locks_persist_production_bible_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEV_MODE", "true")
    user_id = str(uuid4())
    seeded = asyncio.run(_seed_workflow_with_shot(user_id=user_id, image_url="https://cdn.example.com/shot.png"))

    with TestClient(app) as test_client:
        response = test_client.post(
            f"/api/v1/production-control/workflow/{seeded['workflow_id']}/asset-locks",
            headers=_signed_auth_headers(user_id),
            json={"create_missing_assets": False, "persist": True},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["production_bible_summary"]["novel_id"] == seeded["novel_id"]
    assert payload["production_snapshot"]["reason"] == "asset_locks_applied"

    with TestClient(app) as test_client:
        status_response = test_client.get(
            f"/api/v1/workflow/status/{seeded['workflow_id']}",
            headers=_signed_auth_headers(user_id),
        )

    assert status_response.status_code == 200
    assert status_response.json()["production_bible_summary"]["novel_id"] == seeded["novel_id"]

    async def _load_snapshot() -> dict:
        async with AsyncSessionLocal() as db:
            workflow = await db.get(Workflow, seeded["workflow_id"])
            assert workflow is not None
            return workflow.metadata_["production_snapshot"]

    snapshot = asyncio.run(_load_snapshot())
    assert snapshot["summary"]["characters"][0]["name"] == "沈砚"
    assert snapshot["summary"]["asset_readiness"]["asset_count"] >= 1


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        (
            "/api/v1/video/generate",
            {"prompt": "生成一个孤立镜头", "model": "Doubao-Seedance-1.0-pro-fast", "duration": 4},
        ),
        ("/api/v1/images/generate", {"prompt": "生成孤立角色头像"}),
        ("/api/v1/tts/generate", {"text": "旁白: 旧码头的风停了。"}),
        (
            "/api/v1/media/generate",
            {"task_type": "shot_audio_video", "media_type": "audio_video", "prompt": "生成孤立音视频镜头"},
        ),
    ],
)
def test_production_generation_blocks_implicit_consistency_preflight_bypass(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    payload: dict,
) -> None:
    monkeypatch.setenv("DEV_MODE", "false")
    user_id = str(uuid4())
    request_payload = {**payload, "use_consistency_context": False}

    with TestClient(app) as test_client:
        response = test_client.post(path, headers=_signed_auth_headers(user_id), json=request_payload)

    assert response.status_code == 422
    assert "生产模式不能跳过一致性预检" in response.json()["detail"]


def test_production_video_preflight_blocks_unverified_missing_key_and_local_reference_before_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEV_MODE", "false")
    user_id = str(uuid4())
    config_id = asyncio.run(
        _seed_llm_config(
            user_id=user_id,
            provider_name="volcano",
            model_type="video",
            capabilities=["text_to_video", "image_to_video"],
            test_status="pending",
            api_key=None,
            api_model_id="Doubao-Seedance-1.0-pro-fast",
        )
    )

    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/v1/video/generate",
            headers=_signed_auth_headers(user_id),
            json={
                "prompt": "沈砚站在旧码头",
                "model": "Doubao-Seedance-1.0-pro-fast",
                "model_config_id": config_id,
                "duration": 4,
                "image_url": "/static/generated/images/local-reference.png",
            },
        )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "generation_preflight_failed"
    codes = {issue["code"] for issue in detail["issues"]}
    assert {"model_unverified", "model_api_key_missing", "reference_image_not_public"} <= codes
    assert detail["blocking_issue_count"] >= 3

    async def _count_video_jobs() -> int:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(VideoJob).where(VideoJob.user_id == user_id))
            return len(result.scalars().all())

    assert asyncio.run(_count_video_jobs()) == 0


def test_production_video_unsafe_skip_does_not_bypass_hard_preflight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEV_MODE", "false")
    user_id = str(uuid4())
    config_id = asyncio.run(
        _seed_llm_config(
            user_id=user_id,
            provider_name="volcano",
            model_type="video",
            capabilities=["text_to_video", "image_to_video"],
            test_status="pending",
            api_key="sk-video-test",
            api_model_id="Doubao-Seedance-1.0-pro-fast",
        )
    )
    create_calls: list[dict] = []

    class FakeTasks:
        def create(self, **kwargs):
            create_calls.append(kwargs)
            return type("Result", (), {"id": "fake-task"})()

    fake_client = type(
        "Client",
        (),
        {"content_generation": type("Content", (), {"tasks": FakeTasks()})()},
    )()
    monkeypatch.setattr("app.api.v1.endpoints.video.create_ark_client", lambda *_: fake_client)

    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/v1/video/generate",
            headers=_signed_auth_headers(user_id),
            json={
                "prompt": "沈砚站在旧码头",
                "model": "Doubao-Seedance-1.0-pro-fast",
                "model_config_id": config_id,
                "duration": 4,
                "image_url": "/static/generated/images/local-reference.png",
                "unsafe_skip_consistency_preflight": True,
            },
        )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "generation_preflight_failed"
    assert "reference_image_not_public" in {issue["code"] for issue in detail["issues"]}
    assert create_calls == []


def test_production_video_preflight_uses_resolved_model_config_when_request_omits_config_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEV_MODE", "false")
    user_id = str(uuid4())
    api_model_id = f"Doubao-Seedance-1.0-pro-fast-{uuid4()}"
    asyncio.run(
        _seed_llm_config(
            user_id=user_id,
            provider_name="volcano",
            model_type="video",
            capabilities=["text_to_video", "image_to_video"],
            test_status="pending",
            api_key="sk-video-test",
            api_model_id=api_model_id,
        )
    )
    create_calls: list[dict] = []

    class FakeTasks:
        def create(self, **kwargs):
            create_calls.append(kwargs)
            return type("Result", (), {"id": "fake-task"})()

    fake_client = type(
        "Client",
        (),
        {"content_generation": type("Content", (), {"tasks": FakeTasks()})()},
    )()
    monkeypatch.setattr("app.api.v1.endpoints.video.create_ark_client", lambda *_: fake_client)

    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/v1/video/generate",
            headers=_signed_auth_headers(user_id),
            json={
                "prompt": "沈砚站在旧码头",
                "model": api_model_id,
                "duration": 4,
            },
        )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "generation_preflight_failed"
    assert "model_unverified" in {issue["code"] for issue in detail["issues"]}
    assert create_calls == []


def test_production_video_unsafe_skip_checks_shot_local_reference_image(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEV_MODE", "false")
    user_id = str(uuid4())
    seeded = asyncio.run(
        _seed_workflow_with_shot(user_id=user_id, image_url="/static/generated/images/shot-reference.png")
    )
    config_id = asyncio.run(
        _seed_llm_config(
            user_id=user_id,
            provider_name="volcano",
            model_type="video",
            capabilities=["text_to_video", "image_to_video"],
            test_status="success",
            api_key="sk-video-test",
            api_model_id="Doubao-Seedance-1.0-pro-fast",
        )
    )
    create_calls: list[dict] = []

    class FakeTasks:
        def create(self, **kwargs):
            create_calls.append(kwargs)
            return type("Result", (), {"id": "fake-task"})()

    fake_client = type(
        "Client",
        (),
        {"content_generation": type("Content", (), {"tasks": FakeTasks()})()},
    )()
    monkeypatch.setattr("app.api.v1.endpoints.video.create_ark_client", lambda *_: fake_client)

    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/v1/video/generate",
            headers=_signed_auth_headers(user_id),
            json={
                "prompt": "沈砚站在旧码头",
                "model": "Doubao-Seedance-1.0-pro-fast",
                "model_config_id": config_id,
                "duration": 4,
                "shot_id": seeded["shot_id"],
                "use_consistency_context": False,
                "unsafe_skip_consistency_preflight": True,
            },
        )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "generation_preflight_failed"
    assert "reference_image_not_public" in {issue["code"] for issue in detail["issues"]}
    assert create_calls == []


def test_workflow_batch_video_preflight_failure_returns_generation_preflight_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEV_MODE", "false")
    user_id = str(uuid4())
    seeded = asyncio.run(
        _seed_workflow_with_shot(user_id=user_id, image_url="/static/generated/images/workflow-local.png")
    )
    video_config_id = asyncio.run(
        _seed_llm_config(
            user_id=user_id,
            provider_name="volcano",
            model_type="video",
            capabilities=["text_to_video", "image_to_video"],
            test_status="pending",
            api_key="sk-video-test",
            api_model_id="Doubao-Seedance-1.0-pro-fast",
        )
    )

    with TestClient(app) as test_client:
        response = test_client.post(
            f"/api/v1/workflow/{seeded['workflow_id']}/generate-media-batch",
            headers=_signed_auth_headers(user_id),
            json={
                "strategy": "separate_video_tts",
                "shot_ids": [seeded["shot_id"]],
                "model_config_id": video_config_id,
                "audio_mode": "none",
            },
        )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "generation_preflight_failed"
    codes = {issue["code"] for issue in detail["issues"]}
    assert {"model_unverified", "reference_image_not_public"} <= codes
    assert detail["blocking_issue_count"] >= 2


def test_workflow_batch_tts_preflight_failure_returns_generation_preflight_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEV_MODE", "false")
    user_id = str(uuid4())
    seeded = asyncio.run(_seed_workflow_with_shot(user_id=user_id, image_url="https://cdn.example.com/shot.png"))
    video_config_id = asyncio.run(
        _seed_llm_config(
            user_id=user_id,
            provider_name="volcano",
            model_type="video",
            capabilities=["text_to_video", "image_to_video"],
            test_status="success",
            api_key="sk-video-test",
            api_model_id="Doubao-Seedance-1.0-pro-fast",
        )
    )
    tts_config_id = asyncio.run(
        _seed_llm_config(
            user_id=user_id,
            provider_name=f"tts-provider-{uuid4()}",
            model_type="tts",
            capabilities=["tts", "text-to-speech"],
            test_status="pending",
            api_key="sk-tts-test",
        )
    )

    with TestClient(app) as test_client:
        response = test_client.post(
            f"/api/v1/workflow/{seeded['workflow_id']}/generate-media-batch",
            headers=_signed_auth_headers(user_id),
            json={
                "strategy": "separate_video_tts",
                "shot_ids": [seeded["shot_id"]],
                "model_config_id": video_config_id,
                "audio_model_config_id": tts_config_id,
                "audio_mode": "model_audio",
            },
        )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "generation_preflight_failed"
    assert {issue["code"] for issue in detail["issues"]} == {"model_unverified"}
    assert detail["blocking_issue_count"] == 1

    async def _count_created_jobs() -> tuple[int, int]:
        async with AsyncSessionLocal() as db:
            video_result = await db.execute(select(VideoJob).where(VideoJob.user_id == user_id))
            tts_result = await db.execute(select(TTSJob).where(TTSJob.user_id == user_id))
            return len(video_result.scalars().all()), len(tts_result.scalars().all())

    assert asyncio.run(_count_created_jobs()) == (0, 0)
