"""
Workflow route tests for TTS and synthesis.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models import Asset, Novel, Project, Script, StoryEntity, Storyboard
from app.models.series_production_run import SeriesProductionRun
from app.models.llm_config import LLMConfig, LLMModel, LLMProvider
from app.models.media_generation_job import MediaGenerationJob
from app.models.shot import Shot
from app.models.synthesis_job import SynthesisJob
from app.models.tts_job import TTSJob
from app.models.video_job import VideoJob
from app.models.workflow import Workflow
from app.models.live_canary_provider_operation import LiveCanaryProviderOperation
from app.core.time_utils import utc_now
from app.api.v1.endpoints.workflow import _dialogue_sync_diagnostics
from init_db import init_db
from main import app


@pytest.fixture(scope="module", autouse=True)
def _init_database() -> None:
    init_db()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DEV_MODE", "true")
    return TestClient(app)


def test_series_run_workflow_media_requires_passed_preflight(client: TestClient) -> None:
    user_id, novel_id, run_id, workflow_id = (str(uuid4()) for _ in range(4))

    async def _seed() -> None:
        async with AsyncSessionLocal() as session:
            session.add(Novel(id=novel_id, user_id=user_id, title="门禁测试小说"))
            session.add(SeriesProductionRun(
                id=run_id, user_id=user_id, novel_id=novel_id, series_plan_version="v1",
                idempotency_key=str(uuid4()), status="shots_ready", current_episode_number=1,
                requested_stages=["media"], model_bindings={}, budget_policy={}, cost_summary={},
                gate_summary={}, run_metadata={}, episodes=[], version=1,
            ))
            session.add(Workflow(
                id=workflow_id, user_id=user_id, novel_id=novel_id, title="整书第一集",
                metadata_={"series_run_id": run_id, "episode_number": 1},
            ))
            await session.commit()

    asyncio.run(_seed())
    response = client.post(
        f"/api/v1/workflow/{workflow_id}/generate-media-batch",
        json={"strategy": "direct_av_first"},
        headers={"Authorization": f"Bearer {user_id}"},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "series_run_media_preflight_required"


def test_live_canonical_shot_image_precommits_operation_before_mocked_provider(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id, novel_id, script_id, storyboard_id, shot_id, workflow_id, run_id = (str(uuid4()) for _ in range(7))
    bindings = {}

    async def _seed() -> None:
        async with AsyncSessionLocal() as db:
            db.add(Novel(id=novel_id, user_id=user_id, title="live image order"))
            from app.models.storyboard import Storyboard
            db.add(Script(id=script_id, user_id=user_id, novel_id=novel_id, title="live script", content="live"))
            db.add(Storyboard(id=storyboard_id, script_id=script_id, user_id=user_id, novel_id=novel_id, title="live", content={}))
            db.add(Shot(id=shot_id, user_id=user_id, storyboard_id=storyboard_id, shot_number=1, prompt="live shot"))
            db.add(Workflow(id=workflow_id, user_id=user_id, novel_id=novel_id, storyboard_id=storyboard_id, title="live", metadata_={"series_run_id": run_id}))
            for capability, tags, model_type in (
                ("text", ["chat"], "chat"), ("image", ["text-to-image"], "image-generation"),
                ("tts", ["text-to-speech"], "tts"), ("video", ["text-to-video"], "video-generation"),
            ):
                provider = LLMProvider(id=str(uuid4()), name=f"live-{capability}-{uuid4()}", is_active=True)
                model = LLMModel(id=str(uuid4()), provider_id=provider.id, model_id=f"api-{capability}", model_name=capability, model_type=model_type, capabilities=tags, is_active=True)
                config = LLMConfig(id=str(uuid4()), user_id=user_id, model_id=model.id, name=capability, api_key="opaque", is_active=True, test_status="success", tested_at=utc_now())
                db.add_all([provider, model, config]); bindings[capability] = config.id
            db.add(SeriesProductionRun(
                id=run_id, user_id=user_id, novel_id=novel_id, series_plan_version="v1", idempotency_key=str(uuid4()),
                status="media_running", requested_stages=["media"],
                model_bindings={"capabilities": {name: {"config_id": value} for name, value in bindings.items()}},
                budget_policy={"live_canary": True, "max_rmb": "5.00", "estimates_rmb": {"image": "1.00"}},
                cost_summary={}, gate_summary={}, run_metadata={},
                episodes=[{"episode_number": 1, "canonical_ids": {"workflow_id": workflow_id, "shot_ids": [shot_id]}}], version=1,
                created_at=utc_now() - timedelta(seconds=1),
            ))
            await db.commit()

    asyncio.run(_seed())
    _seed_shot_reference_assets(user_id, shot_id)

    async def _config(*args, **kwargs):
        return "opaque", "synthetic", "api-image", None

    async def _provider(*args, **kwargs):
        async with AsyncSessionLocal() as db:
            operation = await db.scalar(select(LiveCanaryProviderOperation).where(LiveCanaryProviderOperation.job_id == shot_id))
            assert operation is not None and operation.status == "reserved" and operation.provider_task_id is None
            run = await db.get(SeriesProductionRun, run_id)
            assert run.cost_summary["reserved_rmb"] == "1.00"
        return {"task_id": "mock-image-task", "data": [{"url": "/static/generated/mock-live.png"}]}

    monkeypatch.setattr("app.api.v1.endpoints.shots.get_user_image_model_config", _config)
    monkeypatch.setattr("app.api.v1.endpoints.shots.create_image_generation_service", lambda *args: object())
    monkeypatch.setattr("app.api.v1.endpoints.shots.call_image_generation_provider", _provider)
    response = client.post(f"/api/v1/shots/{shot_id}/generate-image", json={"style": "anime"}, headers=_auth_headers(user_id))
    assert response.status_code == 200, response.text

    async def _assert_terminal() -> None:
        async with AsyncSessionLocal() as db:
            operation = await db.scalar(select(LiveCanaryProviderOperation).where(LiveCanaryProviderOperation.job_id == shot_id))
            run = await db.get(SeriesProductionRun, run_id)
            assert operation.status == "reconciled" and operation.provider_task_id == "mock-image-task"
            assert run.cost_summary["spent_rmb"] == "1.00" and run.cost_summary["reserved_rmb"] == "0.00"
    asyncio.run(_assert_terminal())


def test_live_project_image_without_novel_id_still_requires_canonical_shot(client: TestClient) -> None:
    user_id, project_id, novel_id, run_id = (str(uuid4()) for _ in range(4))

    async def _seed() -> None:
        async with AsyncSessionLocal() as db:
            db.add(Project(id=project_id, user_id=user_id, name="live project"))
            db.add(Novel(id=novel_id, user_id=user_id, project_id=project_id, title="live project novel"))
            db.add(SeriesProductionRun(
                id=run_id, user_id=user_id, novel_id=novel_id, series_plan_version="v1",
                idempotency_key=str(uuid4()), status="media_running", requested_stages=["media"],
                model_bindings={}, budget_policy={"live_canary": True, "max_rmb": "5.00"},
                cost_summary={}, gate_summary={}, run_metadata={}, episodes=[], version=1,
            ))
            await db.commit()

    asyncio.run(_seed())
    response = client.post(
        "/api/v1/images/generate",
        json={"prompt": "must not call provider", "project_id": project_id},
        headers=_auth_headers(user_id),
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "live_canary_shot_context_required"


def test_series_run_workflow_media_rechecks_fresh_snapshot_before_provider_call(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id, novel_id, run_id, workflow_id = (str(uuid4()) for _ in range(4))

    async def _seed() -> None:
        async with AsyncSessionLocal() as session:
            session.add(Novel(id=novel_id, user_id=user_id, title="新鲜门禁测试"))
            session.add(SeriesProductionRun(
                id=run_id, user_id=user_id, novel_id=novel_id, series_plan_version="v1",
                idempotency_key=str(uuid4()), status="media_running", current_episode_number=1,
                requested_stages=["media"], model_bindings={}, budget_policy={}, cost_summary={},
                gate_summary={"media_preflight": {"ready": True, "snapshot_hash": "old"}},
                run_metadata={"media_preflight": {"ready": True, "snapshot_hash": "old"}},
                episodes=[{"episode_number": 1, "canonical_ids": {"workflow_id": workflow_id}}], version=1,
            ))
            session.add(Workflow(
                id=workflow_id, user_id=user_id, novel_id=novel_id, title="已通过旧门禁",
                metadata_={
                    "series_run_id": run_id,
                    "episode_contract": {"contract_id": "stable-contract", "status": "locked", "snapshot_hash": "old"},
                },
            ))
            await session.commit()

    async def _fresh(*_args, **_kwargs):
        return {"ready": True, "snapshot_hash": "fresh", "issues": []}

    asyncio.run(_seed())
    monkeypatch.setattr("app.features.workflow_media.application.load_context.evaluate_media_preflight", _fresh)
    response = client.post(
        f"/api/v1/workflow/{workflow_id}/generate-media-batch",
        json={"strategy": "direct_av_first"},
        headers={"Authorization": f"Bearer {user_id}"},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["snapshot_changed"] is True

    async def _load_contract():
        async with AsyncSessionLocal() as session:
            value = await session.get(Workflow, workflow_id)
            return value.metadata_["episode_contract"]

    contract = asyncio.run(_load_contract())
    assert contract["contract_id"] == "stable-contract"
    assert contract["status"] == "superseded_review_required"
    assert contract["superseded_reason"] == "input_snapshot_changed"


def test_series_run_workflow_persists_fresh_not_ready_even_when_hash_is_unchanged(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id, novel_id, run_id, workflow_id = (str(uuid4()) for _ in range(4))

    async def _seed() -> None:
        async with AsyncSessionLocal() as session:
            session.add(Novel(id=novel_id, user_id=user_id, title="同hash失败门禁"))
            session.add(SeriesProductionRun(
                id=run_id, user_id=user_id, novel_id=novel_id, series_plan_version="v1",
                idempotency_key=str(uuid4()), status="media_running", current_episode_number=1,
                requested_stages=["media"], model_bindings={}, budget_policy={}, cost_summary={},
                gate_summary={"media_preflight": {"ready": True, "snapshot_hash": "same"}},
                run_metadata={}, episodes=[{"canonical_ids": {"workflow_id": workflow_id}}], version=1,
            ))
            session.add(Workflow(
                id=workflow_id, user_id=user_id, novel_id=novel_id, title="待废弃contract",
                metadata_={
                    "series_run_id": run_id,
                    "episode_contract": {"contract_id": "same-contract", "snapshot_hash": "same", "status": "locked"},
                },
            ))
            await session.commit()

    async def _fresh(*_args, **_kwargs):
        return {"ready": False, "snapshot_hash": "same", "codes": ["state_machine_blocking"], "issues": [{"code": "state_machine_blocking"}]}

    asyncio.run(_seed())
    monkeypatch.setattr("app.features.workflow_media.application.load_context.evaluate_media_preflight", _fresh)
    response = client.post(
        f"/api/v1/workflow/{workflow_id}/generate-media-batch",
        json={"strategy": "direct_av_first"}, headers={"Authorization": f"Bearer {user_id}"},
    )
    assert response.status_code == 409

    async def _load():
        async with AsyncSessionLocal() as session:
            run = await session.get(SeriesProductionRun, run_id)
            workflow = await session.get(Workflow, workflow_id)
            return run.gate_summary["media_preflight"], workflow.metadata_["episode_contract"]

    gate, contract = asyncio.run(_load())
    assert gate["ready"] is False
    assert contract["status"] == "superseded_review_required"


@pytest.fixture()
def fake_tts_service(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_text_to_speech(self, *args, **kwargs):
        return {
            "task_id": "tts-task-123",
            "status": "succeeded",
            "audio_url": "https://example.com/audio.mp3",
            "duration": 3.5,
            "model": "test-tts-model",
            "message": "done",
        }

    monkeypatch.setattr(
        "app.services.volcano_service.VolcanoService.text_to_speech",
        _fake_text_to_speech,
    )


@pytest.fixture()
def fake_synthesis_service(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_video_voice_synthesis(self, *args, **kwargs):
        return {
            "task_id": "synthesis-task-123",
            "status": "succeeded",
            "output_url": "https://example.com/video.mp4",
            "duration": 10.0,
            "message": "done",
        }

    monkeypatch.setattr(
        "app.services.volcano_service.VolcanoService.video_voice_synthesis",
        _fake_video_voice_synthesis,
    )


def _auth_headers(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


def test_dialogue_sync_diagnostics_pads_short_audio_without_blocking() -> None:
    contract = {"version": 1, "spoken_text": "我们把愿望送回去。"}

    short_audio = _dialogue_sync_diagnostics(
        segment_index=4,
        video_duration=4.0,
        audio_duration=2.75,
        contract=contract,
    )
    assert short_audio["status"] == "needs_review"
    assert short_audio["issues"] == [
        {
            "code": "dialogue_audio_tail_padding",
            "severity": "warning",
            "message": "第 4 段配音短于视频镜头 1.25s，将以尾部静音对齐。",
            "segment_index": 4,
            "blocking": False,
            "direction": "shorter",
            "resolved_by": "pad_silence",
        }
    ]

    long_audio = _dialogue_sync_diagnostics(
        segment_index=4,
        video_duration=4.0,
        audio_duration=5.25,
        contract=contract,
    )
    assert long_audio["issues"][0]["code"] == "dialogue_audio_timing_mismatch"
    assert long_audio["issues"][0]["blocking"] is False
    assert long_audio["issues"][0]["resolved_by"] == "trim_to_segment"


def test_media_sync_health_uses_render_audio_duration_after_padding_or_trim() -> None:
    from app.api.v1.endpoints.workflow import _build_media_sync_health

    health = _build_media_sync_health([
        {
            "index": 1,
            "start_seconds": 0.0,
            "duration_seconds": 4.0,
            "video": {"duration_seconds": 4.0},
            "audio": {
                "duration_seconds": 6.25,
                "render_duration_seconds": 4.0,
                "duration_strategy": "trim_to_segment",
                "url": "https://example.com/a.mp3",
            },
            "subtitle": {"enabled": True, "text": "孙剑：我不会再输。", "start_seconds": 0.0, "end_seconds": 4.0},
            "sync_diagnostics": {
                "issues": [
                    {
                        "code": "dialogue_audio_timing_mismatch",
                        "blocking": False,
                        "resolved_by": "trim_to_segment",
                        "message": "配音超出视频",
                    }
                ],
            },
        },
        {
            "index": 2,
            "start_seconds": 4.0,
            "duration_seconds": 4.0,
            "video": {"duration_seconds": 4.0},
            "audio": {
                "duration_seconds": 2.59,
                "render_duration_seconds": 4.0,
                "duration_strategy": "pad_silence",
                "url": "https://example.com/b.mp3",
            },
            "subtitle": {"enabled": True, "text": "沈岚：先看记录。", "start_seconds": 4.0, "end_seconds": 8.0},
            "sync_diagnostics": {
                "issues": [
                    {
                        "code": "dialogue_audio_tail_padding",
                        "blocking": False,
                        "resolved_by": "pad_silence",
                        "message": "尾部静音补齐",
                    }
                ],
            },
        },
    ])

    assert health["status"] == "ok"
    assert health["summary"]["green"] == 2
    assert health["summary"]["red"] == 0
    assert health["summary"]["yellow"] == 0
    assert health["segments"][0]["status"] == "ok"
    assert health["segments"][0]["audio_duration_seconds"] == 4.0
    assert health["segments"][0]["audio_source_duration_seconds"] == 6.25
    assert health["segments"][0]["audio_duration_strategy"] == "trim_to_segment"
    assert health["segments"][0]["audio_video_delta_seconds"] == 0.0
    assert health["segments"][0]["subtitle_video_delta_seconds"] == 0.0
    assert health["segments"][1]["status"] == "ok"
    assert health["segments"][1]["audio_duration_seconds"] == 4.0
    assert health["segments"][1]["audio_source_duration_seconds"] == 2.59
    assert health["segments"][1]["audio_duration_strategy"] == "pad_silence"


def _attach_music_asset_to_shot(user_id: str, shot_id: str, novel_id: str, music_cue: str, url: str) -> None:
    async def _update() -> None:
        async with AsyncSessionLocal() as session:
            shot = await session.get(Shot, shot_id)
            assert shot is not None
            shot.music_cue = music_cue
            session.add(
                Asset(
                    id=f"music-asset-{uuid4()}",
                    user_id=user_id,
                    category="music",
                    name=music_cue,
                    asset_type="audio",
                    url=url,
                    novel_id=novel_id,
                    is_active=True,
                )
            )
            await session.commit()

    asyncio.run(_update())


def _signed_auth_headers(user_id: str) -> dict[str, str]:
    from app.api.v1.endpoints.auth import create_access_token

    return {"Authorization": f"Bearer {create_access_token({'sub': user_id})}"}


def _create_novel(client: TestClient, user_id: str) -> str:
    response = client.post(
        "/api/v1/novels",
        json={"title": f"Novel for {user_id}", "description": "test novel"},
        headers=_signed_auth_headers(user_id),
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_chapter(client: TestClient, user_id: str, novel_id: str, title: str = "Chapter") -> str:
    response = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": title,
            "chapter_number": 1,
            "content": "雨夜街道中，主角发现关键线索并推动剧情。",
        },
        headers=_signed_auth_headers(user_id),
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_numbered_chapter(
    client: TestClient,
    user_id: str,
    novel_id: str,
    *,
    chapter_number: int,
    title: str,
) -> str:
    response = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": title,
            "chapter_number": chapter_number,
            "content": f"{title}正文推动连续剧情。",
        },
        headers=_auth_headers(user_id),
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_script(client: TestClient, user_id: str) -> str:
    novel_id = _create_novel(client, user_id)
    response = client.post(
        "/api/v1/scripts",
        json={"novel_id": novel_id, "title": f"Script for {user_id}", "description": "test script"},
        headers=_auth_headers(user_id),
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_storyboard(client: TestClient, user_id: str) -> str:
    script_id = _create_script(client, user_id)
    response = client.post(
        "/api/v1/storyboards",
        json={"script_id": script_id, "title": f"Storyboard for {user_id}", "description": "test storyboard"},
        headers=_auth_headers(user_id),
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_lock_episode_contract_route_stores_workflow_metadata(client: TestClient) -> None:
    user_id = uuid4().hex
    novel_id = _create_novel(client, user_id)
    workflow_id = f"workflow-{uuid4()}"

    async def _insert_workflow() -> None:
        async with AsyncSessionLocal() as session:
            session.add(
                Workflow(
                    id=workflow_id,
                    user_id=user_id,
                    title="Episode contract route workflow",
                    status="running",
                    novel_id=novel_id,
                    metadata_={"existing": "kept"},
                )
            )
            await session.commit()

    asyncio.run(_insert_workflow())

    response = client.post(
        f"/api/v1/workflow/{workflow_id}/episode-contract/lock",
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["contract_id"]
    assert payload["workflow_id"] == workflow_id
    assert payload["production_bible_hash"]

    async def _load_metadata() -> dict:
        async with AsyncSessionLocal() as session:
            workflow = await session.get(Workflow, workflow_id)
            assert workflow is not None
            return workflow.metadata_ or {}

    metadata = asyncio.run(_load_metadata())
    assert metadata["existing"] == "kept"
    assert metadata["episode_contract"] == payload


def test_studio_snapshot_exposes_series_studio_contract(client: TestClient) -> None:
    user_id = f"series-studio-contract-{uuid4()}"
    workflow_resp = client.post(
        "/api/v1/workflow/start",
        json={"title": "Series Studio contract workflow"},
        headers=_auth_headers(user_id),
    )
    assert workflow_resp.status_code == 201
    workflow_id = workflow_resp.json()["workflow_id"]

    snapshot_resp = client.get(f"/api/v1/studio/workflows/{workflow_id}/snapshot", headers=_auth_headers(user_id))

    assert snapshot_resp.status_code == 200
    assert snapshot_resp.json()["series_studio"] == {
        "enabled": True,
        "primary_console": "series_studio",
        "expert_drilldowns": [
            "/story-bibles",
            "/studio/cards",
            "/studio/continuity-review",
            "/studio/shot-review",
            "/workflow",
            "/producer",
            "/video-generation",
        ],
    }


def test_studio_snapshot_exposes_series_plan_and_episode_contract(client: TestClient) -> None:
    user_id = uuid4().hex
    novel_id = _create_novel(client, user_id)
    chapter_1_id = _create_numbered_chapter(
        client,
        user_id,
        novel_id,
        chapter_number=1,
        title="第一章 雾港铜铃",
    )
    _create_numbered_chapter(
        client,
        user_id,
        novel_id,
        chapter_number=2,
        title="第二章 旧码头",
    )
    plan_resp = client.post(
        f"/api/v1/novels/{novel_id}/series-plan",
        json={"target_episode_count": 2},
        headers=_signed_auth_headers(user_id),
    )
    assert plan_resp.status_code == 200, plan_resp.text

    workflow_id = f"workflow-{uuid4()}"
    contract = {
        "contract_id": "contract-test",
        "workflow_id": workflow_id,
        "novel_id": novel_id,
        "chapter_id": chapter_1_id,
        "locked_at": "2026-07-04T00:00:00+00:00",
        "production_bible_hash": "hash-test",
        "entity_locks": [{"entity_id": "char-1", "entity_type": "character", "name": "沈砚"}],
        "required_checks": ["style", "characters"],
    }

    async def _insert_workflow() -> None:
        async with AsyncSessionLocal() as session:
            session.add(
                Workflow(
                    id=workflow_id,
                    user_id=user_id,
                    title="Series plan snapshot workflow",
                    status="running",
                    novel_id=novel_id,
                    chapter_id=chapter_1_id,
                    metadata_={"episode_contract": contract, "episode_number": 1},
                )
            )
            await session.commit()

    asyncio.run(_insert_workflow())

    snapshot_resp = client.get(
        f"/api/v1/studio/workflows/{workflow_id}/snapshot",
        headers=_signed_auth_headers(user_id),
    )

    assert snapshot_resp.status_code == 200, snapshot_resp.text
    payload = snapshot_resp.json()
    assert payload["series_plan"]["novel_id"] == novel_id
    assert payload["series_plan"]["current_episode"]["episode_index"] == 1
    assert payload["series_plan"]["current_episode"]["chapter_ids"] == [chapter_1_id]
    assert payload["episode_contract"]["contract_id"] == "contract-test"
    assert payload["episode_contract"]["entity_locks"][0]["name"] == "沈砚"


def test_studio_snapshot_exposes_consistency_ledger(client: TestClient) -> None:
    user_id = uuid4().hex
    novel_id = _create_novel(client, user_id)
    workflow_id = f"workflow-{uuid4()}"
    storyboard_id = f"storyboard-{uuid4()}"
    script_id = f"script-{uuid4()}"
    contract = {
        "contract_id": "contract-ledger",
        "workflow_id": workflow_id,
        "novel_id": novel_id,
        "production_bible_hash": "hash-ledger",
        "entity_locks": [{"entity_id": "char-1", "entity_type": "character", "name": "孙剑"}],
        "required_checks": ["characters"],
    }

    async def _insert_workflow_and_shot() -> None:
        async with AsyncSessionLocal() as session:
            session.add(Script(id=script_id, user_id=user_id, novel_id=novel_id, title="Ledger script", content=""))
            session.add(Storyboard(id=storyboard_id, script_id=script_id, user_id=user_id, novel_id=novel_id, title="Ledger board", content={}))
            session.add(
                Workflow(
                    id=workflow_id,
                    user_id=user_id,
                    title="Consistency ledger workflow",
                    status="running",
                    novel_id=novel_id,
                    script_id=script_id,
                    storyboard_id=storyboard_id,
                    metadata_={"episode_contract": contract, "episode_number": 1},
                )
            )
            session.add(
                Shot(
                    id=f"shot-{uuid4()}",
                    user_id=user_id,
                    storyboard_id=storyboard_id,
                    shot_number=1,
                    prompt="角色尚未绑定参考",
                    extra_data={"episode_number": 1, "entity_refs": {"character": []}},
                )
            )
            await session.commit()

    asyncio.run(_insert_workflow_and_shot())

    snapshot_resp = client.get(
        f"/api/v1/studio/workflows/{workflow_id}/snapshot",
        headers=_signed_auth_headers(user_id),
    )

    assert snapshot_resp.status_code == 200, snapshot_resp.text
    ledger = snapshot_resp.json()["consistency_ledger"]
    assert ledger["evaluation_status"] == "not_evaluated"
    assert ledger["overall_score"] is None
    assert ledger["preflight_status"] == "blocked"
    assert ledger["findings"][0]["code"] == "shot_character_unbound"


def test_studio_snapshot_consistency_ledger_uses_shot_character_refs(client: TestClient) -> None:
    user_id = uuid4().hex
    novel_id = _create_novel(client, user_id)
    workflow_id = f"workflow-{uuid4()}"
    storyboard_id = f"storyboard-{uuid4()}"
    script_id = f"script-{uuid4()}"
    contract = {
        "contract_id": "contract-ledger-bound",
        "workflow_id": workflow_id,
        "novel_id": novel_id,
        "production_bible_hash": "hash-ledger-bound",
        "entity_locks": [{"entity_id": "char-1", "entity_type": "character", "name": "孙剑"}],
        "required_checks": ["characters"],
    }

    async def _insert_workflow_and_bound_shot() -> None:
        async with AsyncSessionLocal() as session:
            session.add(Script(id=script_id, user_id=user_id, novel_id=novel_id, title="Bound ledger script", content=""))
            session.add(Storyboard(id=storyboard_id, script_id=script_id, user_id=user_id, novel_id=novel_id, title="Bound ledger board", content={}))
            session.add(
                Workflow(
                    id=workflow_id,
                    user_id=user_id,
                    title="Consistency ledger bound workflow",
                    status="running",
                    novel_id=novel_id,
                    script_id=script_id,
                    storyboard_id=storyboard_id,
                    metadata_={"episode_contract": contract, "episode_number": 1},
                )
            )
            session.add(
                Shot(
                    id=f"shot-{uuid4()}",
                    user_id=user_id,
                    storyboard_id=storyboard_id,
                    shot_number=1,
                    prompt="角色已绑定参考",
                    character_refs=[{"character_id": "char-1"}],
                    extra_data={"episode_number": 1, "entity_refs": {"character": []}},
                )
            )
            await session.commit()

    asyncio.run(_insert_workflow_and_bound_shot())

    snapshot_resp = client.get(
        f"/api/v1/studio/workflows/{workflow_id}/snapshot",
        headers=_signed_auth_headers(user_id),
    )

    assert snapshot_resp.status_code == 200, snapshot_resp.text
    ledger = snapshot_resp.json()["consistency_ledger"]
    assert ledger["evaluation_status"] == "not_evaluated"
    assert ledger["overall_score"] is None
    assert ledger["preflight_status"] == "ready"
    assert ledger["findings"] == []


def _create_shot(client: TestClient, user_id: str) -> tuple[str, str, str]:
    script_id = _create_script(client, user_id)
    storyboard_resp = client.post(
        "/api/v1/storyboards",
        json={"script_id": script_id, "title": f"Storyboard for {user_id}", "description": "test storyboard"},
        headers=_auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201
    storyboard_id = storyboard_resp.json()["id"]

    shot_resp = client.post(
        "/api/v1/shots",
        json={
            "storyboard_id": storyboard_id,
            "shot_number": 1,
            "duration": 4,
            "prompt": f"Shot for {user_id}",
            "dialogue": "test dialogue",
        },
        headers=_auth_headers(user_id),
    )
    assert shot_resp.status_code == 201
    return shot_resp.json()["id"], storyboard_id, script_id


def _insert_video_job(job: VideoJob) -> None:
    async def _insert() -> None:
        async with AsyncSessionLocal() as session:
            session.add(job)
            await session.commit()

    asyncio.run(_insert())


def _insert_tts_job(job: TTSJob) -> None:
    async def _insert() -> None:
        async with AsyncSessionLocal() as session:
            session.add(job)
            await session.commit()

    asyncio.run(_insert())


def _attach_source_preflight(
    *,
    video_job_ids: list[str],
    tts_job_ids: list[str],
) -> None:
    async def _update() -> None:
        async with AsyncSessionLocal() as session:
            for index, job_id in enumerate(video_job_ids, start=1):
                job = await session.get(VideoJob, job_id)
                assert job is not None
                extra = dict(job.extra_data or {})
                extra["generation_preflight"] = {
                    "ready": True,
                    "blocking_issue_count": 0,
                    "issues": [],
                    "marker": f"video-preflight-{index}",
                }
                job.extra_data = extra
            for index, job_id in enumerate(tts_job_ids, start=1):
                job = await session.get(TTSJob, job_id)
                assert job is not None
                extra = dict(job.extra_data or {})
                extra["generation_preflight"] = {
                    "ready": index > 1,
                    "blocking_issue_count": 0 if index > 1 else 1,
                    "issues": [] if index > 1 else [{"code": "voice_not_locked", "message": "音色尚未锁定"}],
                    "marker": f"tts-preflight-{index}",
                }
                job.extra_data = extra
            await session.commit()

    asyncio.run(_update())


def _insert_synthesis_job(job: SynthesisJob) -> None:
    async def _insert() -> None:
        async with AsyncSessionLocal() as session:
            session.add(job)
            await session.commit()

    asyncio.run(_insert())


def _get_media_job_extra(job_id: str) -> dict:
    async def _get() -> dict:
        async with AsyncSessionLocal() as session:
            job = await session.get(MediaGenerationJob, job_id)
            assert job is not None
            return job.extra_data or {}

    return asyncio.run(_get())


def _get_video_job_extra(job_id: str) -> dict:
    async def _get() -> dict:
        async with AsyncSessionLocal() as session:
            job = await session.get(VideoJob, job_id)
            assert job is not None
            return job.extra_data or {}

    return asyncio.run(_get())


def _get_video_job_prompt(job_id: str) -> str:
    async def _get() -> str:
        async with AsyncSessionLocal() as session:
            job = await session.get(VideoJob, job_id)
            assert job is not None
            return job.prompt

    return asyncio.run(_get())


def _get_first_workflow_shot_id(workflow_id: str) -> str:
    async def _get() -> str:
        async with AsyncSessionLocal() as session:
            workflow = await session.get(Workflow, workflow_id)
            assert workflow is not None
            result = await session.execute(
                select(Shot).where(Shot.storyboard_id == workflow.storyboard_id).order_by(Shot.shot_number)
            )
            shot = result.scalars().first()
            assert shot is not None
            return shot.id

    return asyncio.run(_get())


def _get_tts_job_extra(job_id: str) -> dict:
    async def _get() -> dict:
        async with AsyncSessionLocal() as session:
            job = await session.get(TTSJob, job_id)
            assert job is not None
            return job.extra_data or {}

    return asyncio.run(_get())


def _get_tts_job_text(job_id: str) -> str:
    async def _get() -> str:
        async with AsyncSessionLocal() as session:
            job = await session.get(TTSJob, job_id)
            assert job is not None
            return job.text

    return asyncio.run(_get())


def _set_shot_extra_data(shot_id: str, extra_data: dict) -> None:
    async def _update() -> None:
        async with AsyncSessionLocal() as session:
            shot = await session.get(Shot, shot_id)
            assert shot is not None
            shot.extra_data = extra_data
            await session.commit()

    asyncio.run(_update())


def _seed_shot_reference_assets(user_id: str, shot_id: str, views: tuple[str, ...] = ("front", "side")) -> None:
    async def _seed() -> None:
        entity_id = f"char-main-{shot_id[:8]}"
        async with AsyncSessionLocal() as session:
            shot = await session.get(Shot, shot_id)
            assert shot is not None
            shot.character_refs = [{"entity_id": entity_id, "name": "孙剑"}]
            session.add(
                StoryEntity(
                    id=entity_id,
                    user_id=user_id,
                    entity_type="character",
                    name="孙剑",
                    is_approved=True,
                )
            )
            view_labels = {"front": "正面", "side": "侧面", "back": "背面"}
            asset_locks = []
            for view_key in views:
                label = view_labels.get(view_key, view_key)
                asset_id = f"asset-{entity_id}-{view_key}-{uuid4()}"
                session.add(
                    Asset(
                        id=asset_id,
                        user_id=user_id,
                        category="character",
                        asset_type="image",
                        entity_id=entity_id,
                        entity_type="character",
                        name=f"孙剑{label}",
                        url=f"https://cdn.example.com/sunjian-{view_key}.png",
                        is_active=True,
                        is_locked=True,
                        is_final=True,
                        version=1,
                        generation_params={"view_key": view_key},
                    )
                )
                asset_locks.append({"asset_id": asset_id, "locked": True})
            shot.extra_data = {
                **(shot.extra_data or {}),
                "entity_refs": {"characters": [{"entity_id": entity_id, "name": "孙剑"}]},
                "production_context": {"asset_version_locks": asset_locks},
            }
            await session.commit()

    asyncio.run(_seed())


def _insert_model_config(
    *,
    user_id: str,
    provider_id: str,
    model_id: str,
    api_model_id: str,
    model_type: str,
    capabilities: list[str],
    api_key: str,
    test_status: str = "success",
) -> str:
    config_id = f"{model_id}-config-{uuid4()}"

    async def _insert() -> None:
        async with AsyncSessionLocal() as session:
            provider = await session.get(LLMProvider, provider_id)
            if provider is None:
                provider = LLMProvider(
                    id=provider_id,
                    name=provider_id,
                    name_cn=provider_id,
                    base_url="https://example.com",
                    is_active=True,
                )
                session.add(provider)
            model = await session.get(LLMModel, model_id)
            if model is None:
                model = LLMModel(
                    id=model_id,
                    provider_id=provider_id,
                    model_id=api_model_id,
                    model_name=model_id,
                    model_name_cn=model_id,
                    model_type=model_type,
                    capabilities=capabilities,
                    is_active=True,
                )
                session.add(model)
            config = LLMConfig(
                id=config_id,
                user_id=user_id,
                model_id=model_id,
                name=f"{model_id} config",
                is_active=True,
                is_default=True,
                test_status=test_status,
            )
            config.set_api_key_encrypted(api_key)
            session.add(config)
            await session.commit()

    asyncio.run(_insert())
    return config_id


def _create_public_storage_config(client: TestClient, user_id: str, public_base_url: str = "https://cdn.example.com") -> str:
    create_resp = client.post(
        "/api/v1/external/configs",
        json={
            "provider_id": "object_storage",
            "name": "测试 CDN 参考图出口",
            "custom_base_url": public_base_url,
            "extra_config": {
                "public_base_url": public_base_url,
                "local_static_prefix": "/static/",
                "public_static_prefix": "/static/",
            },
            "is_default": True,
        },
        headers=_auth_headers(user_id),
    )
    assert create_resp.status_code == 201, create_resp.text
    config_id = create_resp.json()["id"]
    test_resp = client.post(f"/api/v1/external/configs/{config_id}/test", headers=_auth_headers(user_id))
    assert test_resp.status_code == 200, test_resp.text
    assert test_resp.json()["status"] == "success"
    return config_id


def test_video_job_includes_workflow_lineage_fields(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            class _CreateResult:
                id = "video-task-123"

            return _CreateResult()

        @staticmethod
        def get(*args, **kwargs):
            class _GetResult:
                status = "succeeded"
                content = None

            return _GetResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    monkeypatch.setattr("app.api.v1.endpoints.video.create_ark_client", lambda *_: _FakeArkClient())

    shot_id, storyboard_id, script_id = _create_shot(client, "video-lineage-user")

    create_resp = client.post(
        "/api/v1/video/generate",
        json={
            "prompt": "Generate from shot",
            "api_key": "test-key",
            "shot_id": shot_id,
            "storyboard_id": storyboard_id,
            "script_id": script_id,
        },
        headers=_auth_headers("video-lineage-user"),
    )

    assert create_resp.status_code == 200
    job_id = create_resp.json()["job_id"]

    jobs_resp = client.get("/api/v1/video/jobs", headers=_auth_headers("video-lineage-user"))
    assert jobs_resp.status_code == 200
    job = next(item for item in jobs_resp.json() if item["id"] == job_id)
    assert job["shot_id"] == shot_id
    assert job["storyboard_id"] == storyboard_id
    assert job["script_id"] == script_id


def test_video_generation_passes_seed_and_sdk_parameters(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            captured.update(kwargs)

            class _CreateResult:
                id = "video-task-seeded"

            return _CreateResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    monkeypatch.setattr("app.api.v1.endpoints.video.create_ark_client", lambda *_: _FakeArkClient())

    user_id = f"video-seed-{uuid4().hex}"
    shot_id, storyboard_id, script_id = _create_shot(client, user_id)

    create_resp = client.post(
        "/api/v1/video/generate",
        json={
            "prompt": "Seeded shot video",
            "model": "doubao-seedance-1-5-pro-251215",
            "api_key": "test-key",
            "shot_id": shot_id,
            "storyboard_id": storyboard_id,
            "script_id": script_id,
            "duration": 8,
            "resolution": "1080p",
            "seed": 4242,
        },
        headers=_auth_headers(user_id),
    )

    assert create_resp.status_code == 200, create_resp.text
    assert captured["duration"] == 8
    assert captured["resolution"] == "1080p"
    assert captured["seed"] == 4242
    assert captured["camera_fixed"] is False
    assert captured["watermark"] is False
    assert "--resolution 1080p" in captured["content"][-1]["text"]

    job_resp = client.get(f"/api/v1/video/jobs/{create_resp.json()['job_id']}", headers=_auth_headers(user_id))
    assert job_resp.status_code == 200
    assert job_resp.json()["seed"] == 4242


def test_video_generation_uses_selected_video_model_config_metadata(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            captured.update(kwargs)

            class _CreateResult:
                id = "video-task-selected-model"

            return _CreateResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    monkeypatch.setattr("app.api.v1.endpoints.video.create_ark_client", lambda *_: _FakeArkClient())

    user_id = "video-selected-model-user"
    shot_id, storyboard_id, script_id = _create_shot(client, user_id)
    create_resp = client.post(
        "/api/v1/video/generate",
        json={
            "prompt": "Selected configured video model",
            "api_key": "test-key",
            "model": "Doubao-Seedance-1.0-pro-fast",
            "shot_id": shot_id,
            "storyboard_id": storyboard_id,
            "script_id": script_id,
            "image_url": "https://example.com/ref.png",
        },
        headers=_auth_headers(user_id),
    )

    assert create_resp.status_code == 200
    assert captured["model"] == "ep-20260322134751-fbglz"
    assert captured["content"][0]["type"] == "image_url"
    job_resp = client.get(f"/api/v1/video/jobs/{create_resp.json()['job_id']}", headers=_auth_headers(user_id))
    assert job_resp.status_code == 200
    job = job_resp.json()
    assert job["provider_id"] == "volcano"
    assert job["api_model_id"] == "Doubao-Seedance-1.0-pro-fast"
    assert job["model_endpoint_id"] == "ep-20260322134751-fbglz"
    assert job["prompt_parameters"]["image_url_sent"] is True
    assert job["prompt_parameters"]["duration"] == 5


def test_video_generation_skips_local_reference_image_for_provider(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            captured.update(kwargs)

            class _CreateResult:
                id = "video-task-local-image-skipped"

            return _CreateResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    monkeypatch.setattr("app.api.v1.endpoints.video.create_ark_client", lambda *_: _FakeArkClient())

    user_id = "video-local-image-user"
    shot_id, storyboard_id, script_id = _create_shot(client, user_id)
    create_resp = client.post(
        "/api/v1/video/generate",
        json={
            "prompt": "Local reference image should not be sent",
            "api_key": "test-key",
            "model": "Doubao-Seedance-1.0-pro-fast",
            "shot_id": shot_id,
            "storyboard_id": storyboard_id,
            "script_id": script_id,
            "image_url": "/static/generated/images/local-ref.png",
        },
        headers=_auth_headers(user_id),
    )

    assert create_resp.status_code == 200, create_resp.text
    assert captured["content"][0]["type"] == "text"
    assert all(item["type"] != "image_url" for item in captured["content"])

    job_resp = client.get(f"/api/v1/video/jobs/{create_resp.json()['job_id']}", headers=_auth_headers(user_id))
    assert job_resp.status_code == 200
    job = job_resp.json()
    assert job["image_url"] == "/static/generated/images/local-ref.png"
    assert job["prompt_parameters"]["image_url_sent"] is False
    assert job["prompt_parameters"]["provider_image_url"] is None
    assert "公网" in job["prompt_parameters"]["image_url_omitted_reason"]
    assert "参考图接入说明" in job["prompt"]


def test_video_generation_text_only_model_records_no_provider_image(client: TestClient) -> None:
    user_id = "video-text-only-contract-user"
    create_resp = client.post(
        "/api/v1/video/generate",
        json={
            "prompt": "HappyHorse T2V should ignore image references",
            "model": "happyhorse-1.1-t2v",
            "duration": 5,
            "resolution": "720P",
            "image_url": "https://cdn.example.com/should-not-send.png",
            "use_consistency_context": False,
        },
        headers=_auth_headers(user_id),
    )

    assert create_resp.status_code == 200, create_resp.text
    job_resp = client.get(f"/api/v1/video/jobs/{create_resp.json()['job_id']}", headers=_auth_headers(user_id))
    assert job_resp.status_code == 200
    job = job_resp.json()
    assert job["api_model_id"] == "happyhorse-1.1-t2v"
    assert job["prompt_parameters"]["model_input_mode"] == "text"
    assert job["prompt_parameters"]["image_url_sent"] is False
    assert job["prompt_parameters"]["provider_reference_image_count"] == 0
    assert job["extra_data"]["reference_package"]["mode"] == "text_only"
    assert job["extra_data"]["reference_package"]["dropped_image_count"] == 1


def test_video_generation_maps_local_reference_image_through_public_storage(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            captured.update(kwargs)

            class _CreateResult:
                id = "video-task-public-storage-image"

            return _CreateResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    monkeypatch.setattr("app.api.v1.endpoints.video.create_ark_client", lambda *_: _FakeArkClient())

    user_id = "video-public-storage-user"
    storage_config_id = _create_public_storage_config(client, user_id)
    shot_id, storyboard_id, script_id = _create_shot(client, user_id)
    create_resp = client.post(
        "/api/v1/video/generate",
        json={
            "prompt": "Local reference image should be delivered by CDN",
            "api_key": "test-key",
            "model": "Doubao-Seedance-1.0-pro-fast",
            "shot_id": shot_id,
            "storyboard_id": storyboard_id,
            "script_id": script_id,
            "image_url": "/static/generated/images/local-ref.png",
        },
        headers=_auth_headers(user_id),
    )

    assert create_resp.status_code == 200, create_resp.text
    assert captured["content"][0]["type"] == "image_url"
    assert captured["content"][0]["image_url"]["url"] == "https://cdn.example.com/static/generated/images/local-ref.png"

    job_resp = client.get(f"/api/v1/video/jobs/{create_resp.json()['job_id']}", headers=_auth_headers(user_id))
    assert job_resp.status_code == 200
    job = job_resp.json()
    assert job["image_url"] == "/static/generated/images/local-ref.png"
    assert job["prompt_parameters"]["image_url_sent"] is True
    assert job["prompt_parameters"]["provider_image_url"] == "https://cdn.example.com/static/generated/images/local-ref.png"
    assert job["prompt_parameters"]["image_delivery_method"] == "public_static_base_url"
    assert job["prompt_parameters"]["image_delivery_config_id"] == storage_config_id


def test_video_generation_records_multiview_refs_but_sends_single_provider_image(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            captured.update(kwargs)

            class _CreateResult:
                id = "video-task-single-image-multiview"

            return _CreateResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    monkeypatch.setattr("app.api.v1.endpoints.video.create_ark_client", lambda *_: _FakeArkClient())

    user_id = "video-multiview-single-image-user"
    novel_resp = client.post(
        "/api/v1/novels",
        json={"title": "雨夜追踪", "description": "沈砚在雨夜追查铜铃线索。"},
        headers=_auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]
    character_resp = client.post(
        "/api/v1/characters",
        json={
            "novel_id": novel_id,
            "name": "沈砚",
            "description": "年轻密探",
            "appearance": "青衣长发，眼神冷静",
        },
        headers=_auth_headers(user_id),
    )
    assert character_resp.status_code == 201
    script_resp = client.post(
        "/api/v1/scripts",
        json={
            "novel_id": novel_id,
            "title": "雨夜追踪剧本",
            "content": "沈砚在旧码头停步，铜铃在雨中轻晃。",
        },
        headers=_auth_headers(user_id),
    )
    assert script_resp.status_code == 201
    storyboard_resp = client.post(
        "/api/v1/storyboards",
        json={"script_id": script_resp.json()["id"], "title": "旧码头发现", "description": "多视图参考验证"},
        headers=_auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201
    shot_resp = client.post(
        "/api/v1/shots",
        json={
            "storyboard_id": storyboard_resp.json()["id"],
            "shot_number": 1,
            "duration": 4,
            "prompt": "沈砚在旧码头回头，青衣被雨水打湿。",
            "dialogue": "沈砚：铜铃声就在这里。",
        },
        headers=_auth_headers(user_id),
    )
    assert shot_resp.status_code == 201
    shot_id = shot_resp.json()["id"]
    multiview_refs = [
        {
            "character_name": "沈砚",
            "view_angle": "front",
            "url": "https://cdn.example.com/assets/shenyan-front.png",
        },
        {
            "character_name": "沈砚",
            "view_angle": "side",
            "url": "https://cdn.example.com/assets/shenyan-side.png",
        },
    ]
    context_resp = client.put(
        f"/api/v1/shots/{shot_id}/production-context",
        json={"character_multiview_refs": multiview_refs},
        headers=_auth_headers(user_id),
    )
    assert context_resp.status_code == 200, context_resp.text

    create_resp = client.post(
        "/api/v1/video/generate",
        json={
            "prompt": "按多视图参考生成沈砚雨夜镜头",
            "api_key": "test-key",
            "model": "Doubao-Seedance-1.0-pro-fast",
            "shot_id": shot_id,
        },
        headers=_auth_headers(user_id),
    )

    assert create_resp.status_code == 200, create_resp.text
    provider_images = [item for item in captured["content"] if item["type"] == "image_url"]
    assert len(provider_images) == 1
    assert provider_images[0]["image_url"]["url"] == "https://cdn.example.com/assets/shenyan-front.png"

    job_resp = client.get(f"/api/v1/video/jobs/{create_resp.json()['job_id']}", headers=_auth_headers(user_id))
    assert job_resp.status_code == 200
    job = job_resp.json()
    assert job["character_multiview_refs"] == multiview_refs
    assert job["prompt_parameters"]["reference_image_source"] == "character_multiview"
    assert job["prompt_parameters"]["provider_reference_image_limit"] == 1
    assert job["prompt_parameters"]["reference_image_strategy"] == "single_provider_image_with_textual_asset_constraints"
    assert job["prompt_parameters"]["supplemental_reference_image_count"] == 2
    assert job["prompt_parameters"]["image_url_sent"] is True


def test_video_generation_accepts_seedance_20_fast_model(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            captured.update(kwargs)

            class _CreateResult:
                id = "video-task-seedance-20-fast"

            return _CreateResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    monkeypatch.setattr("app.api.v1.endpoints.video.create_ark_client", lambda *_: _FakeArkClient())

    user_id = "video-seedance-20-fast-user"
    create_resp = client.post(
        "/api/v1/video/generate",
        json={
            "prompt": "Seedance 2.0 fast video model",
            "api_key": "test-key",
            "model": "doubao-seedance-2-0-fast-260128",
            "duration": 4,
            "resolution": "720p",
        },
        headers=_auth_headers(user_id),
    )

    assert create_resp.status_code == 200
    assert captured["model"] == "doubao-seedance-2-0-fast-260128"
    job_resp = client.get(f"/api/v1/video/jobs/{create_resp.json()['job_id']}", headers=_auth_headers(user_id))
    assert job_resp.status_code == 200
    job = job_resp.json()
    assert job["api_model_id"] == "doubao-seedance-2-0-fast-260128"
    assert job["model_endpoint_id"] == "doubao-seedance-2-0-fast-260128"


def test_video_generation_submits_seedance20_reference_package_content(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            captured.update(kwargs)

            class _CreateResult:
                id = "video-task-seedance-20-reference-package"

            return _CreateResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    monkeypatch.setattr("app.api.v1.endpoints.video.create_ark_client", lambda *_: _FakeArkClient())

    user_id = uuid4().hex
    shot_id, _storyboard_id, _script_id = _create_shot(client, user_id)
    _seed_shot_reference_assets(user_id, shot_id)
    create_resp = client.post(
        "/api/v1/video/generate",
        json={
            "prompt": "Seedance 2.0 should submit multiple locked views",
            "api_key": "test-key",
            "model": "doubao-seedance-2-0-260128",
            "duration": 4,
            "resolution": "720p",
            "shot_id": shot_id,
        },
        headers=_auth_headers(user_id),
    )

    assert create_resp.status_code == 200, create_resp.text
    provider_images = [item for item in captured["content"] if item["type"] == "image_url"]
    assert len(provider_images) == 2
    assert provider_images[0]["role"] == "reference_image"
    assert provider_images[0]["image_url"]["url"] == "https://cdn.example.com/sunjian-front.png"
    assert captured["content"][-1]["text"].startswith("@图1为主角孙剑正面形象基准")
    extra = _get_video_job_extra(create_resp.json()["job_id"])
    assert extra["reference_package"]["mode"] == "multimodal"
    assert extra["reference_package"]["image_count"] == 2
    assert extra["reference_package"]["items"][0]["url"] == "https://cdn.example.com/sunjian-front.png"
    assert extra["prompt_parameters"]["provider_reference_image_limit"] == 9
    job_resp = client.get(f"/api/v1/video/jobs/{create_resp.json()['job_id']}", headers=_auth_headers(user_id))
    assert job_resp.status_code == 200
    job = job_resp.json()
    assert job["extra_data"]["reference_package"]["mode"] == "multimodal"


def test_video_generation_accepts_volcano_agent_plan_video_model(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}
    captured_client: dict = {}

    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            captured.update(kwargs)

            class _CreateResult:
                id = "video-task-agent-plan"

            return _CreateResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    def _fake_create_ark_client(api_key: str, base_url: str | None = None):
        captured_client["api_key"] = api_key
        captured_client["base_url"] = base_url
        return _FakeArkClient()

    monkeypatch.setattr("app.api.v1.endpoints.video.create_ark_client", _fake_create_ark_client)

    user_id = "video-agent-plan-user"
    create_resp = client.post(
        "/api/v1/video/generate",
        json={
            "prompt": "Agent Plan Seedance video model",
            "api_key": "agent-plan-key",
            "model": "vplan-seedance-2-0-fast",
            "duration": 5,
            "resolution": "720p",
        },
        headers=_auth_headers(user_id),
    )

    assert create_resp.status_code == 200
    assert captured_client["api_key"] == "agent-plan-key"
    assert captured_client["base_url"] == "https://ark.cn-beijing.volces.com/api/plan/v3"
    assert captured["model"] == "doubao-seedance-2.0-fast"
    assert captured["duration"] == 5

    job_resp = client.get(f"/api/v1/video/jobs/{create_resp.json()['job_id']}", headers=_auth_headers(user_id))
    assert job_resp.status_code == 200
    job = job_resp.json()
    assert job["provider_id"] == "volcano_agent_plan"
    assert job["api_model_id"] == "doubao-seedance-2.0-fast"
    assert job["model_endpoint_id"] == "doubao-seedance-2.0-fast"


def test_video_job_infers_full_lineage_from_chapter_shot(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            class _CreateResult:
                id = "video-task-full-lineage"

            return _CreateResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    monkeypatch.setattr("app.api.v1.endpoints.video.create_ark_client", lambda *_: _FakeArkClient())

    user_id = "video-full-lineage-user"
    novel_id = _create_novel(client, user_id)
    chapter_id = _create_chapter(client, user_id, novel_id, "第一章 雨巷")

    storyboard_resp = client.post(
        "/api/v1/storyboards/generate-smart",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "shot_count": 3,
            "style": "anime",
            "use_ai_refine": False,
        },
        headers=_auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201
    storyboard_payload = storyboard_resp.json()
    storyboard_id = storyboard_payload["id"]
    script_id = storyboard_payload["script_id"]
    shot_id = storyboard_payload["shots"][0]["id"]

    create_resp = client.post(
        "/api/v1/video/generate",
        json={"prompt": "Generate from inferred shot lineage", "api_key": "test-key", "shot_id": shot_id},
        headers=_auth_headers(user_id),
    )
    assert create_resp.status_code == 200
    create_payload = create_resp.json()
    job_id = create_payload["job_id"]
    assert create_payload["novel_id"] == novel_id
    assert create_payload["chapter_id"] == chapter_id
    assert create_payload["script_id"] == script_id
    assert create_payload["storyboard_id"] == storyboard_id
    assert create_payload["shot_id"] == shot_id

    jobs_resp = client.get(
        f"/api/v1/video/jobs?novel_id={novel_id}&chapter_id={chapter_id}&script_id={script_id}&storyboard_id={storyboard_id}&shot_id={shot_id}",
        headers=_auth_headers(user_id),
    )
    assert jobs_resp.status_code == 200
    job = next(item for item in jobs_resp.json() if item["id"] == job_id)
    assert job["novel_id"] == novel_id
    assert job["chapter_id"] == chapter_id
    assert job["script_id"] == script_id
    assert job["storyboard_id"] == storyboard_id
    assert job["shot_id"] == shot_id
    assert job["chapter_title"] == "第一章 雨巷"

    wrong_chapter_id = _create_chapter(client, user_id, novel_id, "第二章 错误来源")
    mismatch_resp = client.post(
        "/api/v1/video/generate",
        json={
            "prompt": "Should reject mismatched chapter",
            "api_key": "test-key",
            "shot_id": shot_id,
            "chapter_id": wrong_chapter_id,
        },
        headers=_auth_headers(user_id),
    )
    assert mismatch_resp.status_code == 422


def test_chapter_generation_reuses_latest_script_when_multiple_scripts_exist(client: TestClient) -> None:
    user_id = f"chapter-production-duplicates-{uuid4()}"
    novel_id = _create_novel(client, user_id)
    chapter_id = _create_chapter(client, user_id, novel_id, "第一章 重复生成")

    first_script_resp = client.post(
        "/api/v1/scripts/generate",
        json={"chapter_id": chapter_id, "style": "anime"},
        headers=_auth_headers(user_id),
    )
    assert first_script_resp.status_code == 201, first_script_resp.text

    second_script_resp = client.post(
        "/api/v1/scripts/generate",
        json={"chapter_id": chapter_id, "style": "anime"},
        headers=_auth_headers(user_id),
    )
    assert second_script_resp.status_code == 201, second_script_resp.text
    latest_script_id = second_script_resp.json()["id"]
    assert latest_script_id != first_script_resp.json()["id"]

    status_resp = client.get(f"/api/v1/chapters/{chapter_id}/production-status", headers=_auth_headers(user_id))
    assert status_resp.status_code == 200, status_resp.text
    assert status_resp.json()["script_id"] == latest_script_id

    generate_resp = client.post(
        f"/api/v1/chapters/{chapter_id}/generate-all",
        json={"style": "anime", "shot_count": 2},
        headers=_auth_headers(user_id),
    )
    assert generate_resp.status_code == 200, generate_resp.text
    payload = generate_resp.json()
    assert payload["script_id"] == latest_script_id
    assert payload["shot_count"] == 2

    storyboard_resp = client.get(f"/api/v1/storyboards/{payload['storyboard_id']}", headers=_auth_headers(user_id))
    assert storyboard_resp.status_code == 200, storyboard_resp.text
    assert storyboard_resp.json()["script_id"] == latest_script_id


def test_chapter_generate_all_creates_draft_script_when_no_script_exists(client: TestClient) -> None:
    user_id = f"chapter-production-no-script-{uuid4()}"
    novel_id = _create_novel(client, user_id)
    chapter_id = _create_chapter(client, user_id, novel_id, "第一章 自动草稿")

    generate_resp = client.post(
        f"/api/v1/chapters/{chapter_id}/generate-all",
        json={"style": "anime"},
        headers=_auth_headers(user_id),
    )
    assert generate_resp.status_code == 200, generate_resp.text
    payload = generate_resp.json()
    assert payload["script_id"]
    assert payload["storyboard_id"]
    assert 2 <= payload["shot_count"] <= 8

    storyboard_resp = client.get(f"/api/v1/storyboards/{payload['storyboard_id']}", headers=_auth_headers(user_id))
    assert storyboard_resp.status_code == 200, storyboard_resp.text
    storyboard = storyboard_resp.json()
    assert storyboard["script_id"] == payload["script_id"]
    assert storyboard["content"]["shot_count_plan"]["source"] == "auto"


def test_video_job_update_cancel_and_archive_management(client: TestClient) -> None:
    user_id = "video-job-manage-user"
    shot_id, storyboard_id, script_id = _create_shot(client, user_id)
    job_id = f"video-job-manage-{uuid4()}"
    _insert_video_job(
        VideoJob(
            id=job_id,
            user_id=user_id,
            task_id=f"video-task-manage-{uuid4()}",
            title="待管理视频任务",
            prompt="镜头管理测试",
            model_id="test-model",
            model_name="测试模型",
            status="pending",
            progress=10,
            duration=4,
            resolution="720p",
            extra_data={
                "shot_id": shot_id,
                "storyboard_id": storyboard_id,
                "script_id": script_id,
            },
        )
    )

    update_resp = client.put(
        f"/api/v1/video/jobs/{job_id}",
        json={"title": "更新后的视频任务", "progress": 35, "status": "running"},
        headers=_auth_headers(user_id),
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["title"] == "更新后的视频任务"
    assert updated["status"] == "running"
    assert updated["progress"] == 35
    assert updated["shot_id"] == shot_id

    cancel_resp = client.post(f"/api/v1/video/jobs/{job_id}/cancel", headers=_auth_headers(user_id))
    assert cancel_resp.status_code == 200
    cancelled = cancel_resp.json()
    assert cancelled["status"] == "cancelled"
    assert cancelled["error_message"] == "任务已由用户取消"

    jobs_before_delete = client.get("/api/v1/video/jobs", headers=_auth_headers(user_id)).json()
    assert any(item["id"] == job_id for item in jobs_before_delete)

    delete_resp = client.delete(f"/api/v1/video/jobs/{job_id}", headers=_auth_headers(user_id))
    assert delete_resp.status_code == 200

    jobs_after_delete = client.get("/api/v1/video/jobs", headers=_auth_headers(user_id)).json()
    assert all(item["id"] != job_id for item in jobs_after_delete)


def test_video_job_cannot_cancel_completed_job(client: TestClient) -> None:
    user_id = "video-job-complete-cancel-user"
    job_id = f"video-job-complete-cancel-{uuid4()}"
    _insert_video_job(
        VideoJob(
            id=job_id,
            user_id=user_id,
            task_id=f"video-task-complete-cancel-{uuid4()}",
            title="已完成视频任务",
            prompt="已完成不能取消",
            model_id="test-model",
            model_name="测试模型",
            status="succeeded",
            progress=100,
            video_url="https://example.com/video.mp4",
        )
    )

    cancel_resp = client.post(f"/api/v1/video/jobs/{job_id}/cancel", headers=_auth_headers(user_id))
    assert cancel_resp.status_code == 400


def test_workflow_concatenate_builds_multi_shot_sequence_manifest(client: TestClient) -> None:
    user_id = "sequence-manifest-user"
    novel_id = _create_novel(client, user_id)
    chapter_id = _create_chapter(client, user_id, novel_id, "第一章 连续成片")

    storyboard_resp = client.post(
        "/api/v1/storyboards/generate-smart",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "shot_count": 2,
            "style": "anime",
            "use_ai_refine": False,
        },
        headers=_auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201
    storyboard_payload = storyboard_resp.json()
    storyboard_id = storyboard_payload["id"]
    script_id = storyboard_payload["script_id"]
    shots = storyboard_payload["shots"][:2]
    music_cue = "测试悬疑BGM"
    music_url = "https://cdn.example.com/music/suspense.mp3"
    _attach_music_asset_to_shot(user_id, shots[0]["id"], novel_id, music_cue, music_url)

    workflow_resp = client.post(
        "/api/v1/workflow/start",
        json={
            "title": "连续成片工作流",
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "script_id": script_id,
            "storyboard_id": storyboard_id,
        },
        headers=_auth_headers(user_id),
    )
    assert workflow_resp.status_code == 201
    workflow_id = workflow_resp.json()["workflow_id"]

    video_job_ids = []
    tts_job_ids = []
    for index, shot in enumerate(shots, start=1):
        video_resp = client.post(
            "/api/v1/video/generate",
                json={
                    "prompt": f"连续成片镜头 {index}",
                    "workflow_id": workflow_id,
                    "shot_id": shot["id"],
                    "duration": max(4, shot["duration"]),
                },
            headers=_auth_headers(user_id),
        )
        assert video_resp.status_code == 200
        video_job_ids.append(video_resp.json()["job_id"])

        tts_resp = client.post(
            "/api/v1/tts/generate",
            json={
                "text": f"第 {index} 个镜头台词",
                "title": f"镜头 {index} 配音",
                "workflow_id": workflow_id,
                "novel_id": novel_id,
                "chapter_id": chapter_id,
                "script_id": script_id,
                "storyboard_id": storyboard_id,
                "shot_id": shot["id"],
            },
            headers=_auth_headers(user_id),
        )
        assert tts_resp.status_code == 200
        tts_job_ids.append(tts_resp.json()["job_id"])

    _attach_source_preflight(video_job_ids=video_job_ids, tts_job_ids=tts_job_ids)

    concat_resp = client.post(
        f"/api/v1/workflow/concatenate/{workflow_id}",
        json={
            "video_job_ids": video_job_ids,
            "tts_job_ids": tts_job_ids,
            "title": "连续成片",
            "transition_style": "fade",
            "include_subtitles": True,
            "quality_profile": "review",
        },
        headers=_auth_headers(user_id),
    )
    assert concat_resp.status_code == 200
    concat_payload = concat_resp.json()
    assert concat_payload["job_id"]
    assert concat_payload["segment_count"] == 2
    assert concat_payload["manifest_url"].startswith("/static/exports/")
    assert concat_payload["output_url"].startswith("/static/dev/final-")
    assert concat_payload["duration_seconds"] >= 8

    synthesis_resp = client.get(
        f"/api/v1/synthesis/jobs/{concat_payload['job_id']}",
        headers=_auth_headers(user_id),
    )
    assert synthesis_resp.status_code == 200
    synthesis_payload = synthesis_resp.json()
    assert synthesis_payload["output_url"] != synthesis_payload["video_url"]
    extra = synthesis_payload["extra_data"]
    assert extra["manifest_url"] == concat_payload["manifest_url"]
    assert extra["segment_count"] == 2
    assert [segment["video"]["job_id"] for segment in extra["segments"]] == video_job_ids
    assert [segment["audio"]["job_id"] for segment in extra["segments"]] == tts_job_ids
    assert extra["segments"][0]["lineage"]["chapter_id"] == chapter_id
    assert extra["segments"][0]["subtitle"]["enabled"] is True
    assert extra["segments"][1]["transition"]["style"] == "fade"
    source_preflight = extra["generation_preflight"]
    assert {source["job_id"] for source in source_preflight["sources"]} == set(video_job_ids + tts_job_ids)
    assert extra["segments"][0]["video"]["generation_preflight"]["marker"] == "video-preflight-1"
    assert extra["segments"][0]["audio"]["generation_preflight"]["issues"][0]["code"] == "voice_not_locked"

    manifest_resp = client.get(concat_payload["manifest_url"])
    assert manifest_resp.status_code == 200
    manifest = manifest_resp.json()
    assert manifest["segment_count"] == 2
    assert manifest["tracks"]["subtitle"][0]["text"] == "第 1 个镜头台词"
    assert manifest["generation_preflight"]["sources"][0]["preflight"]["marker"] == "video-preflight-1"
    assert manifest["segments"][0]["audio"]["generation_preflight"]["marker"] == "tts-preflight-1"
    assert manifest["segments"][0]["music"] == {
        "url": music_url,
        "cue": music_cue,
        "volume": 0.18,
    }

    workflow_status = client.get(
        f"/api/v1/workflow/status/{workflow_id}",
        headers=_auth_headers(user_id),
    )
    assert workflow_status.status_code == 200
    status_payload = workflow_status.json()
    assert status_payload["synthesis_jobs"][0]["manifest_url"] == concat_payload["manifest_url"]
    assert status_payload["synthesis_jobs"][0]["segment_count"] == 2

    preflight_resp = client.get(
        f"/api/v1/workflow/{workflow_id}/render/preflight",
        headers=_auth_headers(user_id),
    )
    assert preflight_resp.status_code == 200
    preflight = preflight_resp.json()
    assert preflight["ready"] is True
    assert preflight["segment_count"] == 2
    assert preflight["manifest_url"] == concat_payload["manifest_url"]

    render_resp = client.post(
        f"/api/v1/workflow/{workflow_id}/render",
        json={"quality_profile": "review"},
        headers=_auth_headers(user_id),
    )
    assert render_resp.status_code == 200
    render_payload = render_resp.json()
    assert render_payload["status"] == "rendered"
    assert render_payload["render_status"] == "rendered"
    assert render_payload["render_backend"] == "local_artifact_package"
    assert render_payload["is_publishable"] is False
    assert render_payload["output_kind"] == "preview_package"
    assert render_payload["publication_blockers"][0]["code"] == "preview_package_not_publishable"
    assert render_payload["preview_url"].endswith("-preview.html")
    assert render_payload["srt_url"].endswith(".srt")
    assert render_payload["timeline_url"].endswith("-timeline.json")
    assert render_payload["render_manifest_url"].startswith("/static/exports/")

    preview_resp = client.get(render_payload["preview_url"])
    assert preview_resp.status_code == 200
    assert "连续成片" in preview_resp.text

    render_manifest_resp = client.get(render_payload["render_manifest_url"])
    assert render_manifest_resp.status_code == 200
    render_manifest = render_manifest_resp.json()
    assert render_manifest["output_url"] == render_payload["preview_url"]
    assert render_manifest["playable_url"] == render_payload["preview_url"]
    assert render_manifest["artifacts"]["preview_url"] == render_payload["preview_url"]
    assert [segment["index"] for segment in render_manifest["segments"]] == [1, 2]
    assert render_manifest["segments"][0]["audio"]["text"] == "第 1 个镜头台词"
    assert render_manifest["tracks"]["audio"][0]["url"]
    assert render_manifest["tracks"]["subtitle"][0]["text"] == "第 1 个镜头台词"

    srt_resp = client.get(render_payload["srt_url"])
    assert srt_resp.status_code == 200
    assert "第 1 个镜头台词" in srt_resp.text
    assert "00:00:00,000 -->" in srt_resp.text

    timeline_resp = client.get(render_payload["timeline_url"])
    assert timeline_resp.status_code == 200
    timeline = timeline_resp.json()
    assert timeline["tracks"][0]["track_type"] == "video"
    assert len(timeline["tracks"][0]["clips"]) == 2

    sync_timeline_resp = client.post(
        f"/api/v1/workflow/{workflow_id}/timeline/sync",
        json={"synthesis_job_id": concat_payload["job_id"], "name": "首集可编辑时间线"},
        headers=_auth_headers(user_id),
    )
    assert sync_timeline_resp.status_code == 200
    synced = sync_timeline_resp.json()
    assert synced["track_count"] == 3
    assert synced["clip_count"] == 6
    assert synced["duration_seconds"] == concat_payload["duration_seconds"]

    tracks_resp = client.get(f"/api/v1/timelines/{synced['timeline_id']}/tracks", headers=_auth_headers(user_id))
    assert tracks_resp.status_code == 200
    tracks = tracks_resp.json()
    assert [track["track_type"] for track in tracks] == ["video", "audio", "subtitle"]

    clips_resp = client.get(f"/api/v1/timelines/{synced['timeline_id']}/clips", headers=_auth_headers(user_id))
    assert clips_resp.status_code == 200
    clips = clips_resp.json()
    assert len(clips) == 6
    assert len([clip for clip in clips if clip["source_type"] in {"video_job", "direct_audio_video"}]) == 2
    assert len([clip for clip in clips if clip["source_type"] == "subtitle"]) == 2
    assert any(clip["text_content"] == "第 1 个镜头台词" for clip in clips)

    first_subtitle_clip = next(clip for clip in clips if clip["source_type"] == "subtitle")
    update_clip_resp = client.put(
        f"/api/v1/timelines/{synced['timeline_id']}/clips/{first_subtitle_clip['id']}",
        json={
            "text_content": "已编辑 Timeline 字幕",
            "position": 0.5,
            "duration": 3.0,
        },
        headers=_auth_headers(user_id),
    )
    assert update_clip_resp.status_code == 200

    timeline_preflight_resp = client.get(
        f"/api/v1/workflow/{workflow_id}/render/preflight",
        params={"synthesis_job_id": concat_payload["job_id"], "use_editable_timeline": "true"},
        headers=_auth_headers(user_id),
    )
    assert timeline_preflight_resp.status_code == 200
    timeline_preflight = timeline_preflight_resp.json()
    assert timeline_preflight["render_source"] == "editable_timeline"
    assert timeline_preflight["timeline_id"] == synced["timeline_id"]

    timeline_render_resp = client.post(
        f"/api/v1/workflow/{workflow_id}/render",
        json={
            "synthesis_job_id": concat_payload["job_id"],
            "force": True,
            "use_editable_timeline": True,
        },
        headers=_auth_headers(user_id),
    )
    assert timeline_render_resp.status_code == 200
    timeline_render = timeline_render_resp.json()
    assert timeline_render["render_source"] == "editable_timeline"
    assert timeline_render["timeline_id"] == synced["timeline_id"]

    edited_srt_resp = client.get(timeline_render["srt_url"])
    assert edited_srt_resp.status_code == 200
    assert "已编辑 Timeline 字幕" in edited_srt_resp.text
    assert "第 1 个镜头台词" not in edited_srt_resp.text
    assert "00:00:00,500 --> 00:00:03,500" in edited_srt_resp.text

    edited_timeline_resp = client.get(timeline_render["timeline_url"])
    assert edited_timeline_resp.status_code == 200
    edited_timeline = edited_timeline_resp.json()
    assert edited_timeline["source"] == "editable_timeline"
    assert edited_timeline["timeline_id"] == synced["timeline_id"]
    assert edited_timeline["tracks"][2]["clips"][0]["text_content"] == "已编辑 Timeline 字幕"

    rendered_job = client.get(
        f"/api/v1/synthesis/jobs/{concat_payload['job_id']}",
        headers=_auth_headers(user_id),
    ).json()
    assert rendered_job["output_url"] == timeline_render["preview_url"]
    assert rendered_job["is_publishable"] is False
    assert rendered_job["output_kind"] == "preview_package"
    assert rendered_job["publication_blockers"][0]["code"] == "preview_package_not_publishable"
    assert rendered_job["extra_data"]["render_status"] == "rendered"
    assert rendered_job["extra_data"]["render_artifacts"]["srt_url"] == timeline_render["srt_url"]
    assert rendered_job["extra_data"]["render_source"] == "editable_timeline"

    rendered_status = client.get(
        f"/api/v1/workflow/status/{workflow_id}",
        headers=_auth_headers(user_id),
    ).json()
    assert 10 in rendered_status["completed_steps"]
    rendered_status_job = rendered_status["synthesis_jobs"][0]
    assert rendered_status_job["render_status"] == "rendered"
    assert rendered_status_job["is_publishable"] is False
    assert rendered_status_job["output_kind"] == "preview_package"
    assert rendered_status_job["preview_url"] == timeline_render["preview_url"]
    assert rendered_status_job["srt_url"] == timeline_render["srt_url"]
    assert rendered_status_job["timeline_url"] == timeline_render["timeline_url"]
    assert rendered_status_job["render_manifest_url"] == timeline_render["render_manifest_url"]
    assert rendered_status_job["segment_count"] == 2


def test_workflow_concatenate_uses_dialogue_sync_contract_for_subtitle_and_timing(
    client: TestClient,
) -> None:
    user_id = f"dialogue-sync-concat-user-{uuid4()}"
    headers = _signed_auth_headers(user_id)
    novel_id = _create_novel(client, user_id)
    chapter_id = _create_chapter(client, user_id, novel_id, "第一章 对白同步")
    storyboard_resp = client.post(
        "/api/v1/storyboards/generate-smart",
        json={"novel_id": novel_id, "chapter_id": chapter_id, "shot_count": 1, "style": "anime", "use_ai_refine": False},
        headers=headers,
    )
    assert storyboard_resp.status_code == 201
    storyboard_payload = storyboard_resp.json()
    shot = storyboard_payload["shots"][0]

    async def _lock_shot_dialogue() -> None:
        async with AsyncSessionLocal() as session:
            db_shot = await session.get(Shot, shot["id"])
            assert db_shot is not None
            db_shot.dialogue = "孙剑：我不会再输。"
            db_shot.extra_data = {
                **(db_shot.extra_data or {}),
                "subtitle_text": "孙剑：我不会再输。",
            }
            await session.commit()

    asyncio.run(_lock_shot_dialogue())

    workflow_resp = client.post(
        "/api/v1/workflow/start",
        json={
            "title": "对白同步工作流",
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "script_id": storyboard_payload["script_id"],
            "storyboard_id": storyboard_payload["id"],
        },
        headers=headers,
    )
    assert workflow_resp.status_code == 201
    workflow_id = workflow_resp.json()["workflow_id"]

    video_resp = client.post(
        "/api/v1/video/generate",
        json={
            "prompt": "孙剑从木榻上坐起，压低声音开口。",
            "workflow_id": workflow_id,
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "script_id": storyboard_payload["script_id"],
            "storyboard_id": storyboard_payload["id"],
            "shot_id": shot["id"],
            "duration": 4,
        },
        headers=headers,
    )
    assert video_resp.status_code == 200
    video_job_id = video_resp.json()["job_id"]

    tts_resp = client.post(
        "/api/v1/tts/generate",
        json={
            "text": "我不会再输。",
            "title": "孙剑对白配音",
            "voice_model": "sunqinyue-default",
            "workflow_id": workflow_id,
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "script_id": storyboard_payload["script_id"],
            "storyboard_id": storyboard_payload["id"],
            "shot_id": shot["id"],
        },
        headers=headers,
    )
    assert tts_resp.status_code == 200
    tts_job_id = tts_resp.json()["job_id"]

    dialogue_sync_contract = {
        "version": 1,
        "speaker": "孙剑",
        "subtitle_text": "孙剑：我不会再输。",
        "spoken_text": "我不会再输。",
        "segments": [{"speaker": "孙剑", "text": "我不会再输。", "start_seconds": 0.0, "end_seconds": 4.0}],
        "start_seconds": 0.0,
        "end_seconds": 4.0,
        "audio_source": "separate_tts",
        "video_native_audio": False,
        "mouth_performance": "match_spoken_text_only",
        "voice": "sunqinyue-default",
        "voice_source": "story_bible",
    }

    async def _attach_dialogue_contract() -> None:
        async with AsyncSessionLocal() as session:
            video_job = await session.get(VideoJob, video_job_id)
            tts_job = await session.get(TTSJob, tts_job_id)
            assert video_job is not None
            assert tts_job is not None
            video_extra = dict(video_job.extra_data or {})
            video_extra["dialogue_sync_contract"] = dialogue_sync_contract
            video_extra["video_native_audio"] = False
            video_job.extra_data = video_extra
            tts_extra = dict(tts_job.extra_data or {})
            tts_extra["dialogue_sync_contract"] = dialogue_sync_contract
            tts_job.extra_data = tts_extra
            tts_job.text = "我不会再输。"
            tts_job.voice = "sunqinyue-default"
            tts_job.duration_seconds = 6.25
            await session.commit()

    asyncio.run(_attach_dialogue_contract())

    concat_resp = client.post(
        f"/api/v1/workflow/concatenate/{workflow_id}",
        json={
            "video_job_ids": [video_job_id],
            "tts_job_ids": [tts_job_id],
            "include_subtitles": True,
            "quality_profile": "review",
        },
        headers=headers,
    )
    assert concat_resp.status_code == 200, concat_resp.text
    manifest_resp = client.get(concat_resp.json()["manifest_url"])
    assert manifest_resp.status_code == 200
    manifest = manifest_resp.json()

    segment = manifest["segments"][0]
    assert segment["subtitle"]["text"] == "孙剑：我不会再输。"
    assert segment["audio"]["text"] == "我不会再输。"
    assert segment["dialogue_sync_contract"]["speaker"] == "孙剑"
    assert segment["dialogue_sync_contract"]["voice"] == "sunqinyue-default"
    assert segment["sync_diagnostics"]["duration_mismatch_seconds"] == 2.25
    assert segment["sync_diagnostics"]["issues"][0]["code"] == "dialogue_audio_timing_mismatch"
    assert segment["duration_seconds"] == 4.0
    assert segment["end_seconds"] == 4.0
    assert segment["audio"]["duration_seconds"] == 6.25
    assert segment["audio"]["render_duration_seconds"] == 4.0
    assert segment["audio"]["duration_strategy"] == "trim_to_segment"
    assert segment["sync_diagnostics"]["issues"][0]["blocking"] is False
    assert segment["sync_diagnostics"]["issues"][0]["resolved_by"] == "trim_to_segment"

    preflight_resp = client.get(
        f"/api/v1/workflow/{workflow_id}/render/preflight",
        headers=headers,
    )
    assert preflight_resp.status_code == 200
    preflight = preflight_resp.json()
    assert preflight["ready"] is True
    assert preflight["issues"] == []
    assert preflight["media_sync_health"]["status"] == "ok"
    assert preflight["media_sync_health"]["summary"]["green"] == 1


def test_workflow_media_batch_separate_video_tts_uses_selected_models(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_video: list[dict] = []
    captured_tts: list[dict] = []

    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            captured_video.append(kwargs)

            class _CreateResult:
                id = f"video-task-{len(captured_video)}"

            return _CreateResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    def _fake_create_ark_client(api_key: str, base_url: str | None = None):
        assert api_key == "sk-video"
        return _FakeArkClient()

    async def _fake_tts(self, *args, **kwargs):
        captured_tts.append(kwargs)
        return {
            "task_id": f"tts-task-{len(captured_tts)}",
            "audio_url": f"https://example.com/audio-{len(captured_tts)}.mp3",
            "duration": 3.0,
            "status": "succeeded",
        }

    monkeypatch.setattr("app.features.video_generation.public.create_ark_client", _fake_create_ark_client)
    monkeypatch.setattr("app.services.minimax_service.MiniMaxService.text_to_speech", _fake_tts)

    user_id = uuid4().hex
    video_config_id = _insert_model_config(
        user_id=user_id,
        provider_id="volcano",
        model_id=f"test-video-model-{uuid4()}",
        api_model_id="doubao-seedance-test",
        model_type="video",
        capabilities=["text-to-video"],
        api_key="sk-video",
    )
    audio_config_id = _insert_model_config(
        user_id=user_id,
        provider_id="minimax",
        model_id=f"test-audio-model-{uuid4()}",
        api_model_id="speech-test",
        model_type="tts",
        capabilities=["text-to-speech"],
        api_key="sk-audio",
    )

    novel_id = _create_novel(client, user_id)
    chapter_id = _create_chapter(client, user_id, novel_id, "第一章 分步模型")
    storyboard_resp = client.post(
        "/api/v1/storyboards/generate-smart",
        json={"novel_id": novel_id, "chapter_id": chapter_id, "shot_count": 2, "style": "anime", "use_ai_refine": False},
        headers=_auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201
    storyboard_payload = storyboard_resp.json()

    async def _make_all_generated_shots_dialogue() -> None:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Shot).where(Shot.storyboard_id == storyboard_payload["id"]).order_by(Shot.shot_number)
            )
            for index, shot in enumerate(result.scalars().all(), start=1):
                shot.dialogue = f"孙剑：第{index}句对白。"
                shot.extra_data = {
                    **(shot.extra_data or {}),
                    "subtitle_text": shot.dialogue,
                }
            await session.commit()

    asyncio.run(_make_all_generated_shots_dialogue())

    workflow_resp = client.post(
        "/api/v1/workflow/start",
        json={
            "title": "分步模型工作流",
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "script_id": storyboard_payload["script_id"],
            "storyboard_id": storyboard_payload["id"],
        },
        headers=_auth_headers(user_id),
    )
    assert workflow_resp.status_code == 201
    workflow_id = workflow_resp.json()["workflow_id"]

    batch_resp = client.post(
        f"/api/v1/workflow/{workflow_id}/generate-media-batch",
        json={
            "strategy": "separate_video_tts",
            "model_config_id": video_config_id,
            "audio_model_config_id": audio_config_id,
            "subtitle_mode": "shot_dialogue",
            "audio_mode": "model_audio",
            "voice_model": "female-shaonj",
        },
        headers=_auth_headers(user_id),
    )
    assert batch_resp.status_code == 200, batch_resp.text
    payload = batch_resp.json()
    assert payload["ready_for_concatenate"] is False
    assert len(payload["video_job_ids"]) == 2
    assert len(payload["tts_job_ids"]) == 2
    assert len(captured_video) == 2
    assert len(captured_tts) == 2
    assert captured_video[0]["model"] == "doubao-seedance-test"
    assert captured_tts[0]["model"] == "speech-test"
    assert captured_tts[0]["voice_id"] == "female-shaonj"

    video_job = client.get(f"/api/v1/video/jobs/{payload['video_job_ids'][0]}", headers=_auth_headers(user_id)).json()
    assert video_job["model_config_id"] == video_config_id or video_job["prompt_parameters"]["model_config_id"] == video_config_id
    assert video_job["api_model_id"] == "doubao-seedance-test"

    tts_jobs = client.get(f"/api/v1/tts/jobs?workflow_id={workflow_id}", headers=_auth_headers(user_id)).json()
    selected_tts = next(item for item in tts_jobs if item["id"] == payload["tts_job_ids"][0])
    assert selected_tts["extra_data"]["model_config_id"] == audio_config_id
    assert selected_tts["extra_data"]["api_model_id"] == "speech-test"


def test_workflow_media_batch_requires_explicit_real_tts_config_before_video_submit(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_video: list[dict] = []

    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            captured_video.append(kwargs)

            class _CreateResult:
                id = "video-task-default-tts"

            return _CreateResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    def _fake_create_ark_client(api_key: str, base_url: str | None = None):
        assert api_key == "sk-volcano"
        return _FakeArkClient()

    monkeypatch.setattr("app.features.video_generation.public.create_ark_client", _fake_create_ark_client)

    user_id = uuid4().hex
    video_config_id = _insert_model_config(
        user_id=user_id,
        provider_id="volcano",
        model_id=f"seedance-video-{uuid4()}",
        api_model_id="doubao-seedance-1-5-pro-251215",
        model_type="video",
        capabilities=["text-to-video"],
        api_key="sk-volcano",
    )
    novel_id = _create_novel(client, user_id)
    chapter_id = _create_chapter(client, user_id, novel_id, "第一章 默认火山 TTS")
    storyboard_resp = client.post(
        "/api/v1/storyboards/generate-smart",
        json={"novel_id": novel_id, "chapter_id": chapter_id, "shot_count": 1, "style": "anime", "use_ai_refine": False},
        headers=_auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201
    storyboard_payload = storyboard_resp.json()

    async def _make_shot_dialogue() -> None:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Shot).where(Shot.storyboard_id == storyboard_payload["id"]))
            shot = result.scalar_one()
            shot.dialogue = "许澜：别让钟声越过第三道防线。"
            shot.extra_data = {**(shot.extra_data or {}), "subtitle_text": shot.dialogue}
            await session.commit()

    asyncio.run(_make_shot_dialogue())

    workflow_resp = client.post(
        "/api/v1/workflow/start",
        json={
            "title": "默认火山 TTS 工作流",
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "script_id": storyboard_payload["script_id"],
            "storyboard_id": storyboard_payload["id"],
        },
        headers=_auth_headers(user_id),
    )
    assert workflow_resp.status_code == 201
    workflow_id = workflow_resp.json()["workflow_id"]

    monkeypatch.setenv("DEV_MODE", "false")
    batch_resp = client.post(
        f"/api/v1/workflow/{workflow_id}/generate-media-batch",
        json={
            "strategy": "separate_video_tts",
            "model_config_id": video_config_id,
            "subtitle_mode": "shot_dialogue",
            "audio_mode": "model_audio",
            "voice_model": "female_nvsheng",
        },
        headers=_signed_auth_headers(user_id),
    )
    assert batch_resp.status_code == 422, batch_resp.text
    detail = batch_resp.json()["detail"]
    assert detail["code"] == "real_tts_model_unconfigured"
    assert detail["provider_id"] == "minimax"
    assert detail["model_id"] == "speech-02-hd"
    assert captured_video == []

    video_jobs = client.get(f"/api/v1/video/jobs?workflow_id={workflow_id}", headers=_signed_auth_headers(user_id)).json()
    tts_jobs = client.get(f"/api/v1/tts/jobs?workflow_id={workflow_id}", headers=_signed_auth_headers(user_id)).json()
    assert video_jobs == []
    assert tts_jobs == []


def test_workflow_media_batch_tts_uses_story_bible_character_voice(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_tts: list[dict] = []

    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            class _CreateResult:
                id = "video-task-story-bible-voice"

            return _CreateResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    async def _fake_tts(self, *args, **kwargs):
        captured_tts.append(kwargs)
        return {
            "task_id": "tts-task-story-bible-voice",
            "audio_url": "https://example.com/story-bible-voice.mp3",
            "duration": 2.8,
            "status": "succeeded",
        }

    monkeypatch.setattr("app.features.video_generation.public.create_ark_client", lambda *_: _FakeArkClient())
    monkeypatch.setattr("app.services.minimax_service.MiniMaxService.text_to_speech", _fake_tts)

    user_id = uuid4().hex
    video_config_id = _insert_model_config(
        user_id=user_id,
        provider_id="volcano",
        model_id=f"test-video-story-bible-voice-{uuid4()}",
        api_model_id="doubao-seedance-story-bible-voice",
        model_type="video",
        capabilities=["text-to-video"],
        api_key="sk-video",
    )
    audio_config_id = _insert_model_config(
        user_id=user_id,
        provider_id="minimax",
        model_id=f"test-audio-story-bible-voice-{uuid4()}",
        api_model_id="speech-story-bible-voice",
        model_type="tts",
        capabilities=["text-to-speech"],
        api_key="sk-audio",
    )

    novel_id = _create_novel(client, user_id)
    chapter_id = _create_chapter(client, user_id, novel_id, "第一章 音色一致性")
    bible_resp = client.post(
        "/api/v1/story-bibles",
        json={
            "novel_id": novel_id,
            "title": "音色一致性 Story Bible",
            "style": "国风修仙赛璐璐动漫",
            "character_rules": [
                {
                    "name": "孙剑",
                    "appearance": "黑发束起，外门灰白短袍，眼神锐利沉稳",
                    "voice": "story-bible-sunjian",
                    "voice_speed": 1.25,
                }
            ],
        },
        headers=_auth_headers(user_id),
    )
    assert bible_resp.status_code == 201
    story_bible_id = bible_resp.json()["id"]

    script_resp = client.post(
        "/api/v1/scripts",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "title": "第一章剧本",
            "content": "孙剑醒来，确认自己重生。",
            "genre": "修仙",
            "style": "国风修仙",
        },
        headers=_auth_headers(user_id),
    )
    assert script_resp.status_code == 201
    storyboard_resp = client.post(
        "/api/v1/storyboards",
        json={
            "script_id": script_resp.json()["id"],
            "title": "醒来镜头",
            "content": {"chapter_id": chapter_id, "story_bible_id": story_bible_id},
        },
        headers=_auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201
    shot_resp = client.post(
        "/api/v1/shots",
        json={
            "storyboard_id": storyboard_resp.json()["id"],
            "shot_number": 1,
            "duration": 4,
            "prompt": "孙剑从木榻上惊醒",
            "dialogue": "孙剑：这一世，我不会再输。",
            "character_refs": [{"name": "孙剑"}],
            "extra_data": {"story_bible_id": story_bible_id},
        },
        headers=_auth_headers(user_id),
    )
    assert shot_resp.status_code == 201

    workflow_resp = client.post(
        "/api/v1/workflow/start",
        json={
            "title": "Story Bible 音色工作流",
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "script_id": script_resp.json()["id"],
            "storyboard_id": storyboard_resp.json()["id"],
        },
        headers=_auth_headers(user_id),
    )
    assert workflow_resp.status_code == 201
    workflow_id = workflow_resp.json()["workflow_id"]

    batch_resp = client.post(
        f"/api/v1/workflow/{workflow_id}/generate-media-batch",
        json={
            "strategy": "separate_video_tts",
            "model_config_id": video_config_id,
            "audio_model_config_id": audio_config_id,
            "audio_mode": "model_audio",
            "voice_model": "fallback-voice",
            "speed": 1.0,
        },
        headers=_auth_headers(user_id),
    )
    assert batch_resp.status_code == 200, batch_resp.text
    payload = batch_resp.json()
    assert payload["tts_voice_lock_count"] == 1
    assert captured_tts[0]["voice_id"] == "story-bible-sunjian"
    assert captured_tts[0]["speed"] == 1.25

    tts_jobs = client.get(f"/api/v1/tts/jobs?workflow_id={workflow_id}", headers=_auth_headers(user_id)).json()
    selected_tts = next(item for item in tts_jobs if item["id"] == payload["tts_job_ids"][0])
    assert selected_tts["voice"] == "story-bible-sunjian"
    assert selected_tts["extra_data"]["voice_source"] == "story_bible"
    assert selected_tts["extra_data"]["voice_character_name"] == "孙剑"
    assert selected_tts["extra_data"]["story_bible_id"] == story_bible_id


def test_workflow_media_batch_tts_uses_user_default_voice_clone_when_story_bible_has_no_voice(
    client: TestClient,
) -> None:
    user_id = uuid4().hex

    clone_resp = client.post(
        "/api/v1/tts/voice-clones",
        data={
            "name": "孙秦岳默认声线",
            "provider": "heygen",
            "voice_id": "sunqinyue-default",
            "description": "本地个人数字员工声线资产",
            "sample_audio_url": "/static/generated/voice-clones/sunqinyue-default.mp3",
        },
        headers=_auth_headers(user_id),
    )
    assert clone_resp.status_code == 201, clone_resp.text

    novel_id = _create_novel(client, user_id)
    chapter_id = _create_chapter(client, user_id, novel_id, "第一章 默认声线")
    bible_resp = client.post(
        "/api/v1/story-bibles",
        json={
            "novel_id": novel_id,
            "title": "无角色声线 Story Bible",
            "style": "科幻",
            "character_rules": [{"name": "孙剑", "appearance": "黑衣少年"}],
        },
        headers=_auth_headers(user_id),
    )
    assert bible_resp.status_code == 201
    story_bible_id = bible_resp.json()["id"]

    script_resp = client.post(
        "/api/v1/scripts",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "title": "默认声线剧本",
            "content": "孙剑确认任务。",
            "genre": "科幻",
            "style": "anime",
        },
        headers=_auth_headers(user_id),
    )
    assert script_resp.status_code == 201
    storyboard_resp = client.post(
        "/api/v1/storyboards",
        json={
            "script_id": script_resp.json()["id"],
            "title": "默认声线分镜",
            "content": {"chapter_id": chapter_id, "story_bible_id": story_bible_id},
        },
        headers=_auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201
    shot_resp = client.post(
        "/api/v1/shots",
        json={
            "storyboard_id": storyboard_resp.json()["id"],
            "shot_number": 1,
            "duration": 4,
            "prompt": "孙剑抬头确认星图",
            "dialogue": "孙剑：这一轮我来守住出口。",
            "character_refs": [{"name": "孙剑"}],
            "extra_data": {"story_bible_id": story_bible_id},
        },
        headers=_auth_headers(user_id),
    )
    assert shot_resp.status_code == 201

    workflow_resp = client.post(
        "/api/v1/workflow/start",
        json={
            "title": "默认声线工作流",
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "script_id": script_resp.json()["id"],
            "storyboard_id": storyboard_resp.json()["id"],
        },
        headers=_auth_headers(user_id),
    )
    assert workflow_resp.status_code == 201
    workflow_id = workflow_resp.json()["workflow_id"]

    batch_resp = client.post(
        f"/api/v1/workflow/{workflow_id}/generate-media-batch",
        json={
            "strategy": "separate_video_tts",
            "audio_mode": "model_audio",
            "voice_model": "female-shaonj",
            "story_bible_id": story_bible_id,
        },
        headers=_auth_headers(user_id),
    )
    assert batch_resp.status_code == 200, batch_resp.text
    payload = batch_resp.json()
    assert payload["tts_voice_lock_count"] == 1

    tts_jobs = client.get(f"/api/v1/tts/jobs?workflow_id={workflow_id}", headers=_auth_headers(user_id)).json()
    selected_tts = next(item for item in tts_jobs if item["id"] == payload["tts_job_ids"][0])
    assert selected_tts["voice"] == "sunqinyue-default"
    assert selected_tts["extra_data"]["voice_source"] == "user_default_voice_clone"
    assert selected_tts["extra_data"]["voice_lock_snapshot"]["voice"] == "sunqinyue-default"
    assert selected_tts["extra_data"]["voice_lock_snapshot"]["voice_asset_id"] == clone_resp.json()["id"]


def test_workflow_media_batch_limits_user_default_voice_clone_to_main_character(
    client: TestClient,
) -> None:
    user_id = uuid4().hex

    clone_resp = client.post(
        "/api/v1/tts/voice-clones",
        data={
            "name": "孙秦岳默认声线",
            "provider": "minimax",
            "voice_id": "sunqinyue-default",
            "description": "本地个人数字员工声线资产",
            "sample_audio_url": "/static/generated/voice-clones/sunqinyue-default.mp3",
        },
        headers=_auth_headers(user_id),
    )
    assert clone_resp.status_code == 201, clone_resp.text

    novel_id = _create_novel(client, user_id)
    chapter_id = _create_chapter(client, user_id, novel_id, "第一章 多角色声线")
    bible_resp = client.post(
        "/api/v1/story-bibles",
        json={
            "novel_id": novel_id,
            "title": "多角色声线 Story Bible",
            "style": "现代奇幻",
            "character_rules": [
                {"name": "孙剑", "role": "主角", "appearance": "黑衣青年"},
                {"name": "沈岚", "role": "配角", "gender": "female", "appearance": "白发女医"},
            ],
        },
        headers=_auth_headers(user_id),
    )
    assert bible_resp.status_code == 201
    story_bible_id = bible_resp.json()["id"]

    script_resp = client.post(
        "/api/v1/scripts",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "title": "多角色声线剧本",
            "content": "孙剑和沈岚在旧车站确认线索，旁白交代雨夜环境。",
            "genre": "现代奇幻",
            "style": "anime",
        },
        headers=_auth_headers(user_id),
    )
    assert script_resp.status_code == 201
    storyboard_resp = client.post(
        "/api/v1/storyboards",
        json={
            "script_id": script_resp.json()["id"],
            "title": "多角色声线分镜",
            "content": {"chapter_id": chapter_id, "story_bible_id": story_bible_id},
        },
        headers=_auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201
    storyboard_id = storyboard_resp.json()["id"]

    shots = [
        {
            "storyboard_id": storyboard_id,
            "shot_number": 1,
            "duration": 4,
            "prompt": "孙剑在旧车站举起铜铃",
            "dialogue": "孙剑：我来确认出口。",
            "character_refs": [{"name": "孙剑"}],
            "extra_data": {"story_bible_id": story_bible_id},
        },
        {
            "storyboard_id": storyboard_id,
            "shot_number": 2,
            "duration": 4,
            "prompt": "沈岚在雨棚下翻开病历",
            "dialogue": "沈岚：别急，先看这份记录。",
            "character_refs": [{"name": "沈岚"}],
            "extra_data": {"story_bible_id": story_bible_id},
        },
        {
            "storyboard_id": storyboard_id,
            "shot_number": 3,
            "duration": 4,
            "prompt": "雨夜旧车站空镜",
            "dialogue": "（旁白）雨水吞没了站台尽头的灯光。",
            "character_refs": [],
            "extra_data": {"story_bible_id": story_bible_id},
        },
    ]
    for shot in shots:
        shot_resp = client.post("/api/v1/shots", json=shot, headers=_auth_headers(user_id))
        assert shot_resp.status_code == 201, shot_resp.text

    workflow_resp = client.post(
        "/api/v1/workflow/start",
        json={
            "title": "多角色声线工作流",
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "script_id": script_resp.json()["id"],
            "storyboard_id": storyboard_id,
        },
        headers=_auth_headers(user_id),
    )
    assert workflow_resp.status_code == 201
    workflow_id = workflow_resp.json()["workflow_id"]

    batch_resp = client.post(
        f"/api/v1/workflow/{workflow_id}/generate-media-batch",
        json={
            "strategy": "separate_video_tts",
            "audio_mode": "model_audio",
            "voice_model": "female-shaonj",
            "story_bible_id": story_bible_id,
        },
        headers=_auth_headers(user_id),
    )
    assert batch_resp.status_code == 200, batch_resp.text

    tts_jobs = client.get(f"/api/v1/tts/jobs?workflow_id={workflow_id}", headers=_auth_headers(user_id)).json()
    main_tts = next(item for item in tts_jobs if "我来确认出口" in item["text"])
    side_tts = next(item for item in tts_jobs if "先看这份记录" in item["text"])
    narrator_tts = next(item for item in tts_jobs if "雨水吞没" in item["text"])
    assert main_tts["voice"] == "sunqinyue-default"
    assert main_tts["extra_data"]["voice_source"] == "user_default_voice_clone"
    assert side_tts["voice"] == "female-shaonj"
    assert side_tts["extra_data"]["voice_source"] == "provider_default_tts"
    assert narrator_tts["voice"] == "female-shaonj"
    assert narrator_tts["extra_data"]["voice_source"] == "provider_default_tts"


def test_video_consistency_package_uses_real_novel_character_and_shared_style_seed(
    client: TestClient,
) -> None:
    user_id = f"video-consistency-user-{uuid4()}"
    novel_resp = client.post(
        "/api/v1/novels",
        json={
            "title": "逆天至尊",
            "genre": "修仙",
            "description": "外门弟子孙剑重生归来，承接前世逆天至尊的记忆。",
        },
        headers=_auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]
    chapter_resp = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "第一章 重生外门",
            "chapter_number": 1,
            "content": "角色：孙剑。场景：青阳宗外门木屋。道具：断剑。事件：孙剑重生。孙剑从剧烈疼痛中醒来，狂喜地确认自己还活着。",
        },
        headers=_auth_headers(user_id),
    )
    assert chapter_resp.status_code == 201
    chapter_id = chapter_resp.json()["id"]
    character_resp = client.post(
        "/api/v1/characters",
        json={
            "novel_id": novel_id,
            "name": "孙剑",
            "description": "青阳宗外门弟子，前世为威震修真界的逆天至尊。",
            "appearance": "年轻瘦弱的身躯，双手带有修炼初期留下的茧子，眼神锐利而深沉。",
            "personality": "隐忍冷静，重生后目标明确。",
            "avatar": "/static/generated/images/sunjian-reference.png",
        },
        headers=_auth_headers(user_id),
    )
    assert character_resp.status_code == 201

    bible_resp = client.post(
        "/api/v1/story-bibles/generate-from-novel",
        json={"novel_id": novel_id, "style": "统一国风修仙赛璐璐动漫，冷暖对比光影"},
        headers=_auth_headers(user_id),
    )
    assert bible_resp.status_code == 201

    polluted_character_resp = client.post(
        "/api/v1/story-bibles/entities",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "entity_type": "character",
            "name": "疼痛",
            "description": "规则识别人物",
            "source": "deterministic",
        },
        headers=_auth_headers(user_id),
    )
    assert polluted_character_resp.status_code == 201
    polluted_prop_resp = client.post(
        "/api/v1/story-bibles/entities",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "entity_type": "prop",
            "name": "逆天至尊孙剑",
            "description": "错误道具",
            "source": "deterministic",
        },
        headers=_auth_headers(user_id),
    )
    assert polluted_prop_resp.status_code == 201

    script_resp = client.post(
        "/api/v1/scripts",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "title": "第一章剧本",
            "content": "孙剑在外门木屋醒来，确认重生，握紧断剑。",
            "genre": "修仙",
            "style": "国风修仙赛璐璐",
        },
        headers=_auth_headers(user_id),
    )
    assert script_resp.status_code == 201
    script_id = script_resp.json()["id"]
    storyboard_resp = client.post(
        "/api/v1/storyboards",
        json={
            "script_id": script_id,
            "title": "重生醒来",
            "description": "同一场景内连续两个镜头",
            "content": {"chapter_id": chapter_id},
        },
        headers=_auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201
    storyboard_id = storyboard_resp.json()["id"]

    shot_ids: list[str] = []
    for shot_number, prompt in (
        (1, "孙剑从木榻上惊醒，额头冷汗，窗外晨光落在青阳宗外门木屋。"),
        (2, "孙剑低头看见带茧的双手，握紧断剑，眼神从震惊转为锐利。"),
    ):
        shot_resp = client.post(
            "/api/v1/shots",
            json={
                "storyboard_id": storyboard_id,
                "shot_number": shot_number,
                "duration": 4,
                "prompt": prompt,
                "visual_description": prompt,
                "dialogue": "孙剑：这一世，我不会再输。",
                "character_refs": [{"name": "疼痛", "source": "deterministic"}],
            },
            headers=_auth_headers(user_id),
        )
        assert shot_resp.status_code == 201
        shot_ids.append(shot_resp.json()["id"])

    jobs = []
    for shot_id in shot_ids:
        video_resp = client.post(
            "/api/v1/video/generate",
            json={
                "prompt": "生成逆天至尊第一章连续镜头",
                "shot_id": shot_id,
                "duration": 4,
                "resolution": "720p",
            },
            headers=_auth_headers(user_id),
        )
        assert video_resp.status_code == 200
        job_resp = client.get(f"/api/v1/video/jobs/{video_resp.json()['job_id']}", headers=_auth_headers(user_id))
        assert job_resp.status_code == 200
        jobs.append(job_resp.json())

    assert jobs[0]["consistency"]["series_seed"] == jobs[1]["consistency"]["series_seed"]
    assert jobs[0]["consistency"]["style_lock"]["storyboard_id"] == storyboard_id
    assert jobs[0]["prompt_parameters"]["image_url_sent"] is False
    assert jobs[0]["prompt_parameters"]["reference_image_source"] == "character_avatar"
    assert "公网" in jobs[0]["prompt_parameters"]["image_url_omitted_reason"]
    assert jobs[0]["image_url"] == "/static/generated/images/sunjian-reference.png"
    assert "孙剑" in jobs[0]["prompt"]
    assert "年轻瘦弱" in jobs[0]["prompt"]
    assert "眼神锐利" in jobs[0]["prompt"]
    assert "疼痛: 规则识别人物" not in jobs[0]["prompt"]
    assert all(ref["name"] == "孙剑" for ref in jobs[0]["character_refs"])
    assert all("孙剑" not in ref.get("name", "") for ref in jobs[0]["prop_refs"])


def test_video_consistency_uses_same_novel_seed_across_chapters(
    client: TestClient,
) -> None:
    user_id = f"whole-novel-video-user-{uuid4()}"
    novel_resp = client.post(
        "/api/v1/novels",
        json={
            "title": "逆天至尊跨章",
            "genre": "修仙",
            "description": "角色：孙剑。场景：青阳宗。道具：断剑。事件：孙剑重生后继续修炼。",
        },
        headers=_auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_ids = []
    for number, title, content in [
        (
            1,
            "第一章 重生外门",
            "角色：孙剑。场景：青阳宗外门木屋。道具：断剑。事件：孙剑重生。孙剑醒来握紧断剑，确认自己重生。",
        ),
        (
            2,
            "第二章 断剑试炼",
            "角色：孙剑。场景：青阳宗试炼台。道具：断剑。事件：试炼反击。孙剑带着断剑走上试炼台，承接重生后的决心。",
        ),
    ]:
        chapter_resp = client.post(
            "/api/v1/chapters",
            json={
                "novel_id": novel_id,
                "title": title,
                "chapter_number": number,
                "content": content,
            },
            headers=_auth_headers(user_id),
        )
        assert chapter_resp.status_code == 201
        chapter_ids.append(chapter_resp.json()["id"])

    character_resp = client.post(
        "/api/v1/characters",
        json={
            "novel_id": novel_id,
            "name": "孙剑",
            "description": "青阳宗外门弟子，重生后保留前世记忆。",
            "appearance": "黑发束起，外门灰白短袍，眼神锐利沉稳。",
            "avatar": "/static/generated/images/sunjian-series-ref.png",
        },
        headers=_auth_headers(user_id),
    )
    assert character_resp.status_code == 201

    bible_resp = client.post(
        "/api/v1/story-bibles",
        json={
            "novel_id": novel_id,
            "title": "逆天至尊跨章 Story Bible",
            "style": "统一国风修仙赛璐璐动漫，角色线条干净，灵气光效稳定",
            "worldview": "青阳宗外门弟子通过试炼进入内门，断剑承载前世记忆。",
            "character_rules": [{"name": "孙剑", "appearance": "黑发束起，外门灰白短袍，眼神锐利沉稳"}],
            "scene_rules": [{"name": "青阳宗", "description": "山门青石、晨雾、冷暖对比光影"}],
            "prop_rules": [{"name": "断剑", "state": "由孙剑持有"}],
            "event_timeline": [{"name": "孙剑重生", "sequence": 1}],
        },
        headers=_auth_headers(user_id),
    )
    assert bible_resp.status_code == 201
    story_bible_id = bible_resp.json()["id"]

    for entity_type, name, chapter_id, attributes in [
        ("character", "孙剑", chapter_ids[0], {"state": "刚重生", "costume": "外门灰白短袍"}),
        ("character", "孙剑", chapter_ids[1], {"state": "准备试炼", "costume": "外门灰白短袍"}),
        ("scene", "青阳宗外门木屋", chapter_ids[0], {"scene_dna": {"lighting": "清晨冷光"}}),
        ("scene", "青阳宗试炼台", chapter_ids[1], {"scene_dna": {"lighting": "正午强光"}}),
        ("prop", "断剑", chapter_ids[0], {"state": "被孙剑握紧", "owner": "孙剑"}),
        ("event", "孙剑重生", chapter_ids[0], {"sequence": 1}),
        ("event", "试炼反击", chapter_ids[1], {"sequence": 2}),
    ]:
        entity_resp = client.post(
            "/api/v1/story-bibles/entities",
            json={
                "novel_id": novel_id,
                "chapter_id": chapter_id,
                "entity_type": entity_type,
                "name": name,
                "description": f"{name} 跨章连续性设定",
                "attributes": attributes,
                "source": "manual",
            },
            headers=_auth_headers(user_id),
        )
        assert entity_resp.status_code == 201

    machine_resp = client.post(
        f"/api/v1/story-bibles/{story_bible_id}/state-machine",
        json={"novel_id": novel_id, "persist": True},
        headers=_auth_headers(user_id),
    )
    assert machine_resp.status_code == 200

    jobs = []
    storyboards = []
    for chapter_id in chapter_ids:
        storyboard_resp = client.post(
            "/api/v1/storyboards/generate-smart",
            json={
                "novel_id": novel_id,
                "chapter_id": chapter_id,
                "story_bible_id": story_bible_id,
                "shot_count": 1,
                "style": "anime",
                "use_ai_refine": False,
            },
            headers=_auth_headers(user_id),
        )
        assert storyboard_resp.status_code == 201
        storyboard_payload = storyboard_resp.json()
        storyboards.append(storyboard_payload)
        shot = storyboard_payload["shots"][0]
        assert shot["extra_data"]["novel_series_seed"]
        assert shot["extra_data"]["continuity_lock"]["scope"] == "novel_series"

        video_resp = client.post(
            "/api/v1/video/generate",
            json={
                "prompt": "生成整部小说一致的动漫镜头",
                "shot_id": shot["id"],
                "story_bible_id": story_bible_id,
                "duration": 4,
                "resolution": "720p",
            },
            headers=_auth_headers(user_id),
        )
        assert video_resp.status_code == 200
        job_resp = client.get(f"/api/v1/video/jobs/{video_resp.json()['job_id']}", headers=_auth_headers(user_id))
        assert job_resp.status_code == 200
        jobs.append(job_resp.json())

    assert storyboards[0]["content"]["novel_series_seed"] == storyboards[1]["content"]["novel_series_seed"]
    assert storyboards[0]["content"]["chapter_seed"] != storyboards[1]["content"]["chapter_seed"]
    assert jobs[0]["consistency"]["novel_series_seed"] == jobs[1]["consistency"]["novel_series_seed"]
    assert jobs[0]["consistency"]["chapter_seed"] != jobs[1]["consistency"]["chapter_seed"]
    assert jobs[0]["consistency"]["style_lock"]["scope"] == "novel_series"
    assert jobs[0]["consistency"]["style_lock"]["novel_series_seed"] == jobs[1]["consistency"]["style_lock"]["novel_series_seed"]
    assert jobs[1]["consistency"]["previous_chapter_context"]["title"] == "第一章 重生外门"
    assert jobs[1]["consistency"]["chapter_state_snapshot"]["title"] == "第二章 断剑试炼"
    assert "整部小说连续性锁" in jobs[1]["prompt"]
    assert "上一章承接" in jobs[1]["prompt"]
    assert "第一章 重生外门" in jobs[1]["prompt"]
    assert "孙剑" in jobs[1]["prompt"]
    assert "断剑" in jobs[1]["prompt"]
    assert jobs[1]["prompt_parameters"]["reference_image_source"] == "character_avatar"


def test_non_dev_workflow_media_batch_blocks_unverified_video_model_before_jobs(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEV_MODE", "false")

    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            class _CreateResult:
                id = "should-not-create-provider-task"

            return _CreateResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    monkeypatch.setattr("app.features.video_generation.public.create_ark_client", lambda *_: _FakeArkClient())

    user_id = uuid4().hex
    headers = _signed_auth_headers(user_id)
    video_config_id = _insert_model_config(
        user_id=user_id,
        provider_id="volcano",
        model_id=f"test-workflow-unverified-video-{uuid4()}",
        api_model_id="doubao-seedance-unverified-test",
        model_type="video",
        capabilities=["text-to-video"],
        api_key="sk-video",
        test_status="pending",
    )
    novel_resp = client.post(
        "/api/v1/novels",
        json={"title": "非 DEV 批量门禁", "description": "测试生产预检不能被工作流绕过"},
        headers=headers,
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]
    chapter_resp = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "第一章 旧码头",
            "chapter_number": 1,
            "content": "沈砚在旧码头追查铜铃。",
        },
        headers=headers,
    )
    assert chapter_resp.status_code == 201
    chapter_id = chapter_resp.json()["id"]
    script_resp = client.post(
        "/api/v1/scripts",
        json={"novel_id": novel_id, "title": "第一章剧本", "content": "沈砚追查铜铃。"},
        headers=headers,
    )
    assert script_resp.status_code == 201
    storyboard_resp = client.post(
        "/api/v1/storyboards",
        json={
            "script_id": script_resp.json()["id"],
            "novel_id": novel_id,
            "title": "旧码头分镜",
            "content": {"chapter_id": chapter_id},
        },
        headers=headers,
    )
    assert storyboard_resp.status_code == 201
    shot_resp = client.post(
        "/api/v1/shots",
        json={
            "storyboard_id": storyboard_resp.json()["id"],
            "shot_number": 1,
            "duration": 4,
            "prompt": "沈砚站在旧码头，手持铜铃。",
            "dialogue": "沈砚：这里一定留下了线索。",
        },
        headers=headers,
    )
    assert shot_resp.status_code == 201
    workflow_resp = client.post(
        "/api/v1/workflow/start",
        json={
            "title": "非 DEV 批量门禁工作流",
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "script_id": script_resp.json()["id"],
            "storyboard_id": storyboard_resp.json()["id"],
        },
        headers=headers,
    )
    assert workflow_resp.status_code == 201

    batch_resp = client.post(
        f"/api/v1/workflow/{workflow_resp.json()['workflow_id']}/generate-media-batch",
        json={
            "strategy": "separate_video_tts",
            "model_config_id": video_config_id,
            "audio_mode": "none",
        },
        headers=headers,
    )

    assert batch_resp.status_code == 422
    detail = batch_resp.json()["detail"]
    assert detail["code"] == "generation_preflight_failed"
    codes = {issue["code"] for issue in detail["issues"]}
    assert "model_unverified" in codes

    async def _count_video_jobs() -> int:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(VideoJob).where(VideoJob.user_id == user_id))
            return len(result.scalars().all())

    assert asyncio.run(_count_video_jobs()) == 0


def test_workflow_media_batch_requires_real_video_when_requested(client: TestClient) -> None:
    user_id = uuid4().hex
    video_config_id = _insert_model_config(
        user_id=user_id,
        provider_id="volcano",
        model_id=f"test-real-video-required-{uuid4()}",
        api_model_id="doubao-seedance-1-5-pro-251215",
        model_type="video",
        capabilities=["text-to-video", "image-to-video"],
        api_key="",
    )
    shot_id, storyboard_id, script_id = _create_shot(client, user_id)
    workflow_resp = client.post(
        "/api/v1/workflow/start",
        json={
            "title": "真实视频门禁工作流",
            "script_id": script_id,
            "storyboard_id": storyboard_id,
        },
        headers=_auth_headers(user_id),
    )
    assert workflow_resp.status_code == 201

    batch_resp = client.post(
        f"/api/v1/workflow/{workflow_resp.json()['workflow_id']}/generate-media-batch",
        json={
            "strategy": "separate_video_tts",
            "model_config_id": video_config_id,
            "shot_ids": [shot_id],
            "audio_mode": "none",
            "require_real_video": True,
        },
        headers=_auth_headers(user_id),
    )

    assert batch_resp.status_code == 422
    detail = batch_resp.json()["detail"]
    assert detail["code"] == "real_video_model_unconfigured"

    async def _count_video_jobs() -> int:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(VideoJob).where(VideoJob.user_id == user_id))
            return len(result.scalars().all())

    assert asyncio.run(_count_video_jobs()) == 0


def test_workflow_media_batch_uses_consistency_prompt_and_reference_image(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_video: list[dict] = []

    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            captured_video.append(kwargs)

            class _CreateResult:
                id = f"video-consistency-task-{len(captured_video)}"

            return _CreateResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    monkeypatch.setattr("app.features.video_generation.public.create_ark_client", lambda *_: _FakeArkClient())

    user_id = uuid4().hex
    video_config_id = _insert_model_config(
        user_id=user_id,
        provider_id="volcano",
        model_id=f"test-video-consistency-model-{uuid4()}",
        api_model_id="doubao-seedance-consistency-test",
        model_type="video",
        capabilities=["text-to-video", "image-to-video"],
        api_key="sk-video",
    )
    novel_id = _create_novel(client, user_id)
    chapter_id = _create_chapter(client, user_id, novel_id, "第一章 批量一致性")
    character_resp = client.post(
        "/api/v1/characters",
        json={
            "novel_id": novel_id,
            "name": "沈砚",
            "appearance": "青衣长发，神情冷静",
            "avatar": "https://example.com/shenyan.png",
        },
        headers=_auth_headers(user_id),
    )
    assert character_resp.status_code == 201
    storyboard_resp = client.post(
        "/api/v1/storyboards/generate-smart",
        json={"novel_id": novel_id, "chapter_id": chapter_id, "shot_count": 2, "style": "anime", "use_ai_refine": False},
        headers=_auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201
    storyboard_payload = storyboard_resp.json()
    workflow_resp = client.post(
        "/api/v1/workflow/start",
        json={
            "title": "批量一致性工作流",
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "script_id": storyboard_payload["script_id"],
            "storyboard_id": storyboard_payload["id"],
        },
        headers=_auth_headers(user_id),
    )
    assert workflow_resp.status_code == 201
    workflow_id = workflow_resp.json()["workflow_id"]

    batch_resp = client.post(
        f"/api/v1/workflow/{workflow_id}/generate-media-batch",
        json={
            "strategy": "separate_video_tts",
            "model_config_id": video_config_id,
            "audio_mode": "none",
        },
        headers=_auth_headers(user_id),
    )
    assert batch_resp.status_code == 200, batch_resp.text
    payload = batch_resp.json()
    assert len(captured_video) == 2
    first_prompt = captured_video[0]["content"][-1]["text"]
    assert "视频一致性约束" in first_prompt
    assert "角色视觉DNA锁" in first_prompt
    assert "沈砚" in first_prompt
    assert "generate_audio" not in captured_video[0]
    assert captured_video[0]["content"][0]["type"] == "image_url"
    assert captured_video[0]["seed"] != captured_video[1]["seed"]

    jobs = [
        client.get(f"/api/v1/video/jobs/{job_id}", headers=_auth_headers(user_id)).json()
        for job_id in payload["video_job_ids"]
    ]
    assert jobs[0]["consistency"]["series_seed"] == jobs[1]["consistency"]["series_seed"]
    assert jobs[0]["prompt_parameters"]["reference_image_source"] == "character_avatar"


def test_workflow_media_batch_sanitizes_provider_video_prompt(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_video: list[dict] = []

    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            captured_video.append(kwargs)

            class _CreateResult:
                id = "video-safe-prompt-task"

            return _CreateResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    monkeypatch.setattr("app.features.video_generation.public.create_ark_client", lambda *_: _FakeArkClient())

    user_id = uuid4().hex
    video_config_id = _insert_model_config(
        user_id=user_id,
        provider_id="volcano",
        model_id=f"test-video-safe-prompt-model-{uuid4()}",
        api_model_id="doubao-seedance-safe-prompt-test",
        model_type="video",
        capabilities=["text-to-video", "image-to-video"],
        api_key="sk-video",
    )
    novel_id = _create_novel(client, user_id)
    chapter_id = _create_chapter(client, user_id, novel_id, "第一章 安全提示词")
    character_resp = client.post(
        "/api/v1/characters",
        json={
            "novel_id": novel_id,
            "name": "许澜",
            "appearance": "灰蓝外套，红围巾，冷静行动",
            "avatar": "https://example.com/xulan.png",
        },
        headers=_auth_headers(user_id),
    )
    assert character_resp.status_code == 201
    storyboard_resp = client.post(
        "/api/v1/storyboards/generate-smart",
        json={"novel_id": novel_id, "chapter_id": chapter_id, "shot_count": 1, "style": "anime", "use_ai_refine": False},
        headers=_auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201
    storyboard_payload = storyboard_resp.json()

    async def _inject_risky_prompt() -> None:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Shot).where(Shot.storyboard_id == storyboard_payload["id"]))
            shot = result.scalars().first()
            assert shot is not None
            shot.prompt = "失踪档案被抹除，主角拒绝牺牲别人。"
            shot.visual_description = "失踪档案被抹除，画面出现血迹。"
            await session.commit()

    asyncio.run(_inject_risky_prompt())

    workflow_resp = client.post(
        "/api/v1/workflow/start",
        json={
            "title": "安全提示词工作流",
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "script_id": storyboard_payload["script_id"],
            "storyboard_id": storyboard_payload["id"],
        },
        headers=_auth_headers(user_id),
    )
    assert workflow_resp.status_code == 201

    batch_resp = client.post(
        f"/api/v1/workflow/{workflow_resp.json()['workflow_id']}/generate-media-batch",
        json={
            "strategy": "separate_video_tts",
            "model_config_id": video_config_id,
            "audio_mode": "none",
        },
        headers=_auth_headers(user_id),
    )

    assert batch_resp.status_code == 200, batch_resp.text
    assert len(captured_video) == 1
    provider_text = captured_video[0]["content"][-1]["text"]
    assert "失踪" not in provider_text
    assert "抹除" not in provider_text
    assert "牺牲" not in provider_text
    assert "血迹" not in provider_text
    assert "档案" not in provider_text
    assert "待查资料" in provider_text
    assert "隐藏" in provider_text

    job = client.get(
        f"/api/v1/video/jobs/{batch_resp.json()['video_job_ids'][0]}",
        headers=_auth_headers(user_id),
    ).json()
    assert job["prompt_parameters"]["provider_prompt_sanitized"] is True
    replacement_sources = {item["source"] for item in job["prompt_parameters"]["provider_prompt_replacements"]}
    assert {"失踪档案", "抹除", "牺牲别人"}.issubset(replacement_sources)


def test_workflow_media_batch_skips_local_reference_image_for_provider(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_video: list[dict] = []

    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            captured_video.append(kwargs)

            class _CreateResult:
                id = f"video-local-ref-task-{len(captured_video)}"

            return _CreateResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    monkeypatch.setattr("app.features.video_generation.public.create_ark_client", lambda *_: _FakeArkClient())

    user_id = uuid4().hex
    video_config_id = _insert_model_config(
        user_id=user_id,
        provider_id="volcano",
        model_id=f"test-video-local-ref-model-{uuid4()}",
        api_model_id="doubao-seedance-local-ref-test",
        model_type="video",
        capabilities=["text-to-video", "image-to-video"],
        api_key="sk-video",
    )
    novel_id = _create_novel(client, user_id)
    chapter_id = _create_chapter(client, user_id, novel_id, "第一章 本地参考图")
    character_resp = client.post(
        "/api/v1/characters",
        json={
            "novel_id": novel_id,
            "name": "林澈",
            "appearance": "黑发少年，灰色短袍，目光坚定",
            "avatar": "/static/generated/images/linche-reference.png",
        },
        headers=_auth_headers(user_id),
    )
    assert character_resp.status_code == 201
    storyboard_resp = client.post(
        "/api/v1/storyboards/generate-smart",
        json={"novel_id": novel_id, "chapter_id": chapter_id, "shot_count": 1, "style": "anime", "use_ai_refine": False},
        headers=_auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201
    storyboard_payload = storyboard_resp.json()
    workflow_resp = client.post(
        "/api/v1/workflow/start",
        json={
            "title": "本地参考图批量工作流",
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "script_id": storyboard_payload["script_id"],
            "storyboard_id": storyboard_payload["id"],
        },
        headers=_auth_headers(user_id),
    )
    assert workflow_resp.status_code == 201

    batch_resp = client.post(
        f"/api/v1/workflow/{workflow_resp.json()['workflow_id']}/generate-media-batch",
        json={
            "strategy": "separate_video_tts",
            "model_config_id": video_config_id,
            "audio_mode": "none",
        },
        headers=_auth_headers(user_id),
    )
    assert batch_resp.status_code == 200, batch_resp.text
    payload = batch_resp.json()
    assert len(captured_video) == 1
    assert captured_video[0]["content"][0]["type"] == "text"
    assert all(item["type"] != "image_url" for item in captured_video[0]["content"])

    job = client.get(f"/api/v1/video/jobs/{payload['video_job_ids'][0]}", headers=_auth_headers(user_id)).json()
    assert job["image_url"] == "/static/generated/images/linche-reference.png"
    assert job["prompt_parameters"]["image_url_sent"] is False
    assert job["prompt_parameters"]["reference_image_source"] == "character_avatar"
    assert "公网" in job["prompt_parameters"]["image_url_omitted_reason"]
    assert "参考图接入说明" in job["prompt"]

    strict_resp = client.post(
        f"/api/v1/workflow/{workflow_resp.json()['workflow_id']}/generate-media-batch",
        json={
            "strategy": "separate_video_tts",
            "model_config_id": video_config_id,
            "audio_mode": "none",
            "require_provider_reference_image": True,
        },
        headers=_auth_headers(user_id),
    )
    assert strict_resp.status_code == 422
    strict_detail = strict_resp.json()["detail"]
    assert strict_detail["code"] == "provider_reference_image_missing"
    assert strict_detail["shot_id"] == storyboard_payload["shots"][0]["id"]
    assert len(captured_video) == 1


def test_workflow_media_batch_maps_local_reference_image_through_public_storage(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_video: list[dict] = []

    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            captured_video.append(kwargs)

            class _CreateResult:
                id = f"video-cdn-ref-task-{len(captured_video)}"

            return _CreateResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    monkeypatch.setattr("app.features.video_generation.public.create_ark_client", lambda *_: _FakeArkClient())

    user_id = uuid4().hex
    storage_config_id = _create_public_storage_config(client, user_id)
    video_config_id = _insert_model_config(
        user_id=user_id,
        provider_id="volcano",
        model_id=f"test-video-cdn-ref-model-{uuid4()}",
        api_model_id="doubao-seedance-cdn-ref-test",
        model_type="video",
        capabilities=["text-to-video", "image-to-video"],
        api_key="sk-video",
    )
    novel_id = _create_novel(client, user_id)
    chapter_id = _create_chapter(client, user_id, novel_id, "第一章 CDN参考图")
    character_resp = client.post(
        "/api/v1/characters",
        json={
            "novel_id": novel_id,
            "name": "林澈",
            "appearance": "黑发少年，灰色短袍，目光坚定",
            "avatar": "/static/generated/images/linche-reference.png",
        },
        headers=_auth_headers(user_id),
    )
    assert character_resp.status_code == 201
    storyboard_resp = client.post(
        "/api/v1/storyboards/generate-smart",
        json={"novel_id": novel_id, "chapter_id": chapter_id, "shot_count": 1, "style": "anime", "use_ai_refine": False},
        headers=_auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201
    storyboard_payload = storyboard_resp.json()
    workflow_resp = client.post(
        "/api/v1/workflow/start",
        json={
            "title": "CDN参考图批量工作流",
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "script_id": storyboard_payload["script_id"],
            "storyboard_id": storyboard_payload["id"],
        },
        headers=_auth_headers(user_id),
    )
    assert workflow_resp.status_code == 201

    batch_resp = client.post(
        f"/api/v1/workflow/{workflow_resp.json()['workflow_id']}/generate-media-batch",
        json={
            "strategy": "separate_video_tts",
            "model_config_id": video_config_id,
            "audio_mode": "none",
        },
        headers=_auth_headers(user_id),
    )
    assert batch_resp.status_code == 200, batch_resp.text
    payload = batch_resp.json()
    assert len(captured_video) == 1
    assert captured_video[0]["content"][0]["type"] == "image_url"
    assert captured_video[0]["content"][0]["image_url"]["url"] == "https://cdn.example.com/static/generated/images/linche-reference.png"

    job = client.get(f"/api/v1/video/jobs/{payload['video_job_ids'][0]}", headers=_auth_headers(user_id)).json()
    assert job["image_url"] == "/static/generated/images/linche-reference.png"
    assert job["prompt_parameters"]["image_url_sent"] is True
    assert job["prompt_parameters"]["provider_image_url"] == "https://cdn.example.com/static/generated/images/linche-reference.png"
    assert job["prompt_parameters"]["image_delivery_method"] == "public_static_base_url"
    assert job["prompt_parameters"]["image_delivery_config_id"] == storage_config_id


def test_workflow_media_batch_submits_seedance20_reference_package_content(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_video: list[dict] = []

    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            captured_video.append(kwargs)

            class _CreateResult:
                id = f"video-reference-package-task-{len(captured_video)}"

            return _CreateResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    monkeypatch.setattr("app.features.video_generation.public.create_ark_client", lambda *_: _FakeArkClient())

    user_id = uuid4().hex
    video_config_id = _insert_model_config(
        user_id=user_id,
        provider_id="volcano",
        model_id=f"test-video-ref-package-model-{uuid4()}",
        api_model_id="doubao-seedance-2-0-260128",
        model_type="video",
        capabilities=["text-to-video", "image-to-video"],
        api_key="sk-video",
    )
    shot_id, storyboard_id, script_id = _create_shot(client, user_id)
    _seed_shot_reference_assets(user_id, shot_id)
    workflow_resp = client.post(
        "/api/v1/workflow/start",
        json={
            "title": "多参考包批量工作流",
            "script_id": script_id,
            "storyboard_id": storyboard_id,
        },
        headers=_auth_headers(user_id),
    )
    assert workflow_resp.status_code == 201

    batch_resp = client.post(
        f"/api/v1/workflow/{workflow_resp.json()['workflow_id']}/generate-media-batch",
        json={
            "strategy": "separate_video_tts",
            "model_config_id": video_config_id,
            "audio_mode": "none",
        },
        headers=_auth_headers(user_id),
    )

    assert batch_resp.status_code == 200, batch_resp.text
    payload = batch_resp.json()
    assert len(captured_video) == 1
    provider_images = [item for item in captured_video[0]["content"] if item["type"] == "image_url"]
    assert len(provider_images) == 2
    assert provider_images[0]["role"] == "reference_image"
    assert provider_images[0]["image_url"]["url"] == "https://cdn.example.com/sunjian-front.png"
    assert provider_images[1]["image_url"]["url"] == "https://cdn.example.com/sunjian-side.png"
    assert captured_video[0]["content"][-1]["text"].startswith("@图1为主角孙剑正面形象基准")

    extra = _get_video_job_extra(payload["video_job_ids"][0])
    assert extra["reference_package"]["mode"] == "multimodal"
    assert extra["reference_package"]["image_count"] == 2
    assert extra["reference_package"]["items"][0]["type"] == "image"
    assert extra["reference_package"]["items"][0]["url"] == "https://cdn.example.com/sunjian-front.png"
    assert extra["prompt_parameters"]["provider_reference_image_limit"] == 9


def test_workflow_media_batch_keeps_legacy_single_image_reference_content(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_video: list[dict] = []

    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            captured_video.append(kwargs)

            class _CreateResult:
                id = f"video-legacy-reference-task-{len(captured_video)}"

            return _CreateResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    monkeypatch.setattr("app.features.video_generation.public.create_ark_client", lambda *_: _FakeArkClient())

    user_id = uuid4().hex
    video_config_id = _insert_model_config(
        user_id=user_id,
        provider_id="volcano",
        model_id=f"test-video-legacy-ref-model-{uuid4()}",
        api_model_id="Doubao-Seedance-1.0-pro-fast",
        model_type="video",
        capabilities=["text-to-video", "image-to-video"],
        api_key="sk-video",
    )
    shot_id, storyboard_id, script_id = _create_shot(client, user_id)
    _seed_shot_reference_assets(user_id, shot_id)
    workflow_resp = client.post(
        "/api/v1/workflow/start",
        json={
            "title": "单图兼容批量工作流",
            "script_id": script_id,
            "storyboard_id": storyboard_id,
        },
        headers=_auth_headers(user_id),
    )
    assert workflow_resp.status_code == 201

    batch_resp = client.post(
        f"/api/v1/workflow/{workflow_resp.json()['workflow_id']}/generate-media-batch",
        json={
            "strategy": "separate_video_tts",
            "model_config_id": video_config_id,
            "audio_mode": "none",
        },
        headers=_auth_headers(user_id),
    )

    assert batch_resp.status_code == 200, batch_resp.text
    payload = batch_resp.json()
    assert len(captured_video) == 1
    content = captured_video[0]["content"]
    provider_images = [item for item in content if item["type"] == "image_url"]
    assert len(provider_images) == 1
    assert "role" not in provider_images[0]
    assert provider_images[0]["image_url"]["url"] == "https://cdn.example.com/sunjian-side.png"
    assert content[-1]["type"] == "text"
    assert not content[-1]["text"].startswith("@图")

    extra = _get_video_job_extra(payload["video_job_ids"][0])
    assert extra["reference_package"]["mode"] == "single_image"
    assert extra["reference_package"]["image_count"] == 1
    assert extra["reference_package"]["items"] == []
    assert extra["prompt_parameters"]["provider_reference_image_limit"] == 1


def test_entity_extraction_does_not_treat_state_words_as_characters() -> None:
    from app.services.entity_extraction_service import extract_story_entities

    text = "剧烈疼痛之后，狂喜涌上心头，阳光照进木屋，年轻瘦弱的双手还在颤抖。角色：孙剑。孙剑说道：这一世我会改写命运。"
    entities = extract_story_entities(text, {"character"})
    names = {entity["name"] for entity in entities}
    assert "孙剑" in names
    assert "疼痛" not in names
    assert "狂喜" not in names
    assert "阳光" not in names
    assert "年轻" not in names
    assert "瘦弱" not in names


def test_workflow_render_preflight_reports_missing_manifest(client: TestClient) -> None:
    user_id = "render-preflight-missing-user"
    workflow_resp = client.post(
        "/api/v1/workflow/start",
        json={"title": "缺少清单工作流"},
        headers=_auth_headers(user_id),
    )
    assert workflow_resp.status_code == 201
    workflow_id = workflow_resp.json()["workflow_id"]

    preflight_resp = client.get(
        f"/api/v1/workflow/{workflow_id}/render/preflight",
        headers=_auth_headers(user_id),
    )
    assert preflight_resp.status_code == 200
    payload = preflight_resp.json()
    assert payload["ready"] is False
    assert payload["blocking_issue_count"] == 1
    assert payload["issues"][0]["code"] == "missing_synthesis_job"

    render_resp = client.post(
        f"/api/v1/workflow/{workflow_id}/render",
        json={},
        headers=_auth_headers(user_id),
    )
    assert render_resp.status_code == 404


def test_workflow_render_ffmpeg_local_marks_output_publishable(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid4().hex
    workflow_id = f"workflow-ffmpeg-local-{uuid4()}"
    synthesis_job_id = f"synthesis-ffmpeg-local-{uuid4()}"
    segments = [
        {
            "index": 1,
            "start_seconds": 0,
            "duration_seconds": 1.2,
            "end_seconds": 1.2,
            "video": {"url": "/static/dev/source-a.mp4", "duration_seconds": 1.2},
            "audio": {"url": None, "duration_seconds": None, "text": "第一句"},
            "subtitle": {"enabled": True, "text": "第一句", "start_seconds": 0, "end_seconds": 1.2},
        }
    ]

    async def _fake_render_workflow_package(manifest, *, output_dir, burn_subtitles):
        assert manifest["render_backend"] == "ffmpeg_local"
        assert manifest["segments"] == segments
        assert burn_subtitles is False
        assert output_dir.name == "exports"
        return {
            "output_url": "/static/exports/final-ffmpeg-local.mp4",
            "duration": 1.2,
            "width": 160,
            "height": 90,
            "subtitle_url": "/static/exports/final-ffmpeg-local.srt",
            "log_tail": "ffmpeg ok",
        }

    monkeypatch.setattr(
        "app.services.ffmpeg_local_renderer.render_workflow_package",
        _fake_render_workflow_package,
    )

    async def _insert() -> None:
        async with AsyncSessionLocal() as session:
            session.add(
                Workflow(
                    id=workflow_id,
                    user_id=user_id,
                    title="本地 FFmpeg 渲染工作流",
                    status="running",
                    current_step=8,
                    completed_steps=[1, 2, 3, 4, 5, 6, 7, 8],
                    synthesis_job_ids=[synthesis_job_id],
                )
            )
            session.add(
                SynthesisJob(
                    id=synthesis_job_id,
                    user_id=user_id,
                    workflow_id=workflow_id,
                    title="待真实渲染合成",
                    model_id="local-render",
                    model_name="本地渲染包",
                    video_url="/static/dev/source-a.mp4",
                    status="succeeded",
                    progress=100,
                    output_url="/static/dev/final-preview.mp4",
                    duration_seconds=1.2,
                    extra_data={
                        "manifest_url": "/static/exports/source-sequence.json",
                        "render_status": "ready",
                        "render_backend": "local_manifest",
                        "segment_count": 1,
                        "duration_seconds": 1.2,
                        "segments": segments,
                    },
                )
            )
            await session.commit()

    asyncio.run(_insert())

    response = client.post(
        f"/api/v1/workflow/{workflow_id}/render",
        json={"render_backend": "ffmpeg_local", "quality_profile": "publish"},
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "rendered"
    assert payload["render_backend"] == "ffmpeg_local"
    assert payload["output_url"] == "/static/exports/final-ffmpeg-local.mp4"
    assert payload["srt_url"] == "/static/exports/final-ffmpeg-local.srt"
    assert payload["duration_seconds"] == 1.2
    assert payload["is_publishable"] is True
    assert payload["output_kind"] == "final_video"
    assert payload["publication_blockers"] == []

    rendered_job = client.get(
        f"/api/v1/synthesis/jobs/{synthesis_job_id}",
        headers=_auth_headers(user_id),
    ).json()
    assert rendered_job["output_url"] == "/static/exports/final-ffmpeg-local.mp4"
    assert rendered_job["extra_data"]["render_backend"] == "ffmpeg_local"
    assert rendered_job["extra_data"]["render_artifacts"]["output_url"] == "/static/exports/final-ffmpeg-local.mp4"
    assert rendered_job["extra_data"]["is_publishable"] is True

    status_resp = client.get(f"/api/v1/workflow/status/{workflow_id}", headers=_auth_headers(user_id))
    assert status_resp.status_code == 200
    workflow_payload = status_resp.json()
    assert workflow_payload["current_step"] == 10
    assert 10 in workflow_payload["completed_steps"]


def test_workflow_render_ffmpeg_local_returns_structured_error(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.ffmpeg_local_renderer import FFmpegLocalRenderError

    user_id = uuid4().hex
    workflow_id = f"workflow-ffmpeg-local-error-{uuid4()}"
    synthesis_job_id = f"synthesis-ffmpeg-local-error-{uuid4()}"
    segments = [
        {
            "index": 1,
            "start_seconds": 0,
            "duration_seconds": 1.0,
            "end_seconds": 1.0,
            "video": {"url": "/static/dev/source-error.mp4", "duration_seconds": 1.0},
            "audio": {"url": None},
            "subtitle": {"enabled": False, "text": "", "start_seconds": 0, "end_seconds": 1.0},
        }
    ]

    async def _fake_render_error(*_args, **_kwargs):
        raise FFmpegLocalRenderError("ffmpeg_not_installed", "FFmpeg 未安装")

    monkeypatch.setattr(
        "app.services.ffmpeg_local_renderer.render_workflow_package",
        _fake_render_error,
    )

    async def _insert() -> None:
        async with AsyncSessionLocal() as session:
            session.add(
                Workflow(
                    id=workflow_id,
                    user_id=user_id,
                    title="本地 FFmpeg 错误工作流",
                    status="running",
                    current_step=8,
                    completed_steps=[1, 2, 3, 4, 5, 6, 7, 8],
                    synthesis_job_ids=[synthesis_job_id],
                )
            )
            session.add(
                SynthesisJob(
                    id=synthesis_job_id,
                    user_id=user_id,
                    workflow_id=workflow_id,
                    title="待真实渲染合成",
                    model_id="local-render",
                    model_name="本地渲染包",
                    video_url="/static/dev/source-error.mp4",
                    status="succeeded",
                    progress=100,
                    output_url="/static/dev/final-preview-error.mp4",
                    duration_seconds=1.0,
                    extra_data={
                        "manifest_url": "/static/exports/source-error-sequence.json",
                        "render_status": "ready",
                        "render_backend": "local_manifest",
                        "segment_count": 1,
                        "duration_seconds": 1.0,
                        "segments": segments,
                    },
                )
            )
            await session.commit()

    asyncio.run(_insert())

    response = client.post(
        f"/api/v1/workflow/{workflow_id}/render",
        json={"render_backend": "ffmpeg_local"},
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "ffmpeg_not_installed"
    rendered_job = client.get(
        f"/api/v1/synthesis/jobs/{synthesis_job_id}",
        headers=_auth_headers(user_id),
    ).json()
    assert rendered_job["status"] == "failed"
    assert rendered_job["extra_data"]["render_backend"] == "ffmpeg_local"
    assert rendered_job["extra_data"]["render_issues"][0]["code"] == "ffmpeg_not_installed"


def test_tts_job_includes_script_id_from_shot_context(client: TestClient, fake_tts_service: None) -> None:
    shot_id, _storyboard_id, script_id = _create_shot(client, "tts-lineage-user")

    response = client.post(
        "/api/v1/tts/generate",
        json={
            "text": "你好，世界",
            "title": "测试配音任务",
            "api_key": "test-key",
            "shot_id": shot_id,
        },
        headers=_auth_headers("tts-lineage-user"),
    )

    assert response.status_code == 200
    job_id = response.json()["job_id"]

    jobs_response = client.get("/api/v1/tts/jobs", headers=_auth_headers("tts-lineage-user"))
    assert jobs_response.status_code == 200
    jobs = jobs_response.json()
    job = next(job for job in jobs if job["id"] == job_id)
    assert job["shot_id"] == shot_id
    assert job["script_id"] == script_id


def test_synthesis_job_includes_video_tts_sources(client: TestClient, fake_synthesis_service: None) -> None:
    response = client.post(
        "/api/v1/synthesis/generate",
        json={
            "video_url": "https://example.com/source.mp4",
            "audio_url": "https://example.com/audio.mp3",
            "title": "测试合成任务",
            "api_key": "test-key",
            "video_job_id": "video-job-123",
            "tts_job_id": "tts-job-456",
        },
        headers=_auth_headers("synthesis-lineage-user"),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"]

    jobs_response = client.get("/api/v1/synthesis/jobs", headers=_auth_headers("synthesis-lineage-user"))
    assert jobs_response.status_code == 200
    jobs = jobs_response.json()
    job = next(job for job in jobs if job["id"] == payload["job_id"])
    assert job["video_job_id"] == "video-job-123"
    assert job["tts_job_id"] == "tts-job-456"


def test_synthesis_create_propagates_source_generation_preflight(client: TestClient) -> None:
    user_id = str(uuid4())
    video_job_id = f"video-source-preflight-{uuid4()}"
    tts_job_id = f"tts-source-preflight-{uuid4()}"
    video_preflight = {
        "ready": True,
        "blocking_issue_count": 0,
        "issues": [],
        "marker": "source-video-preflight",
    }
    tts_preflight = {
        "ready": False,
        "blocking_issue_count": 1,
        "issues": [{"code": "voice_not_locked", "message": "音色尚未锁定"}],
        "marker": "source-tts-preflight",
    }
    _insert_video_job(
        VideoJob(
            id=video_job_id,
            user_id=user_id,
            task_id="video-task-source-preflight",
            title="源视频",
            prompt="源视频 prompt",
            model_id="video-model",
            model_name="视频模型",
            status="succeeded",
            progress=100,
            video_url="https://example.com/source-video.mp4",
            extra_data={"generation_preflight": video_preflight},
        )
    )
    _insert_tts_job(
        TTSJob(
            id=tts_job_id,
            user_id=user_id,
            task_id="tts-task-source-preflight",
            title="源配音",
            text="沈砚: 我会查清铜铃的来历。",
            voice="female-shaonv",
            status="succeeded",
            progress=100,
            audio_url="https://example.com/source-audio.mp3",
            extra_data={"generation_preflight": tts_preflight},
        )
    )

    response = client.post(
        "/api/v1/synthesis/create",
        json={
            "video_job_id": video_job_id,
            "tts_job_id": tts_job_id,
            "title": "来源证据合成",
        },
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["video_url"] == "https://example.com/source-video.mp4"
    assert payload["audio_url"] == "https://example.com/source-audio.mp3"
    source_preflight = payload["extra_data"]["generation_preflight"]
    assert source_preflight["blocking_issue_count"] == 1
    assert {source["job_id"] for source in source_preflight["sources"]} == {video_job_id, tts_job_id}
    assert source_preflight["sources"][0]["preflight"]["marker"] == "source-video-preflight"
    assert source_preflight["sources"][1]["preflight"]["issues"][0]["code"] == "voice_not_locked"


def test_synthesis_jobs_filter_lineage_and_expose_render_artifacts(client: TestClient) -> None:
    user_id = "synthesis-filter-user"
    matched_job_id = f"synthesis-filter-match-{uuid4()}"
    other_job_id = f"synthesis-filter-other-{uuid4()}"
    novel_id = f"novel-{uuid4()}"
    chapter_id = f"chapter-{uuid4()}"
    script_id = f"script-{uuid4()}"
    storyboard_id = f"storyboard-{uuid4()}"
    shot_id = f"shot-{uuid4()}"

    _insert_synthesis_job(
        SynthesisJob(
            id=matched_job_id,
            user_id=user_id,
            workflow_id="workflow-filter-1",
            title="第一章可播放渲染包",
            model_id="local-render",
            model_name="本地渲染包",
            video_url="/static/dev/source-a.mp4",
            audio_url="/static/dev/audio-a.mp3",
            status="succeeded",
            progress=100,
            output_url="/static/exports/render-a-preview.html",
            duration_seconds=8,
            extra_data={
                "novel_id": novel_id,
                "chapter_id": chapter_id,
                "script_id": script_id,
                "storyboard_id": storyboard_id,
                "shot_id": shot_id,
                "render_status": "rendered",
                "manifest_url": "/static/exports/sequence-a.json",
                "segment_count": 1,
                "render_artifacts": {
                    "preview_url": "/static/exports/render-a-preview.html",
                    "srt_url": "/static/exports/render-a.srt",
                    "timeline_url": "/static/exports/render-a-timeline.json",
                    "render_manifest_url": "/static/exports/render-a.json",
                },
                "segments": [
                    {
                        "lineage": {
                            "novel_id": novel_id,
                            "chapter_id": chapter_id,
                            "script_id": script_id,
                            "storyboard_id": storyboard_id,
                            "shot_id": shot_id,
                        }
                    }
                ],
            },
        )
    )
    _insert_synthesis_job(
        SynthesisJob(
            id=other_job_id,
            user_id=user_id,
            workflow_id="workflow-filter-2",
            title="第二章草稿",
            model_id="local-render",
            model_name="本地渲染包",
            video_url="/static/dev/source-b.mp4",
            status="succeeded",
            progress=100,
            output_url="/static/exports/render-b-preview.html",
            extra_data={
                "novel_id": novel_id,
                "chapter_id": f"chapter-other-{uuid4()}",
                "script_id": f"script-other-{uuid4()}",
                "storyboard_id": f"storyboard-other-{uuid4()}",
                "shot_id": f"shot-other-{uuid4()}",
                "render_status": "ready",
                "manifest_url": "/static/exports/sequence-b.json",
                "segment_count": 1,
            },
        )
    )

    jobs_response = client.get(
        "/api/v1/synthesis/jobs",
        params={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "script_id": script_id,
            "storyboard_id": storyboard_id,
            "shot_id": shot_id,
            "status": "succeeded",
            "render_status": "rendered",
        },
        headers=_auth_headers(user_id),
    )

    assert jobs_response.status_code == 200
    jobs = jobs_response.json()
    assert [job["id"] for job in jobs] == [matched_job_id]
    job = jobs[0]
    assert job["novel_id"] == novel_id
    assert job["chapter_id"] == chapter_id
    assert job["script_id"] == script_id
    assert job["storyboard_id"] == storyboard_id
    assert job["shot_id"] == shot_id
    assert job["render_status"] == "rendered"
    assert job["manifest_url"] == "/static/exports/sequence-a.json"
    assert job["segment_count"] == 1
    assert job["preview_url"] == "/static/exports/render-a-preview.html"
    assert job["srt_url"] == "/static/exports/render-a.srt"
    assert job["timeline_url"] == "/static/exports/render-a-timeline.json"
    assert job["render_manifest_url"] == "/static/exports/render-a.json"


def test_tts_requires_api_key_outside_dev_mode(
    client: TestClient,
    fake_tts_service: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEV_MODE", "false")
    suffix = uuid4().hex[:10]
    register_resp = client.post(
        "/api/v1/auth/register",
        json={
            "username": f"tts-key-user-{suffix}",
            "email": f"tts-key-user-{suffix}@example.test",
            "password": "testPass123",
        },
    )
    assert register_resp.status_code == 200
    access_token = register_resp.json()["access_token"]
    response = client.post(
        "/api/v1/tts/generate",
        json={
            "text": "你好，世界",
            "title": "测试配音任务",
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 422


def test_tts_rejects_blank_api_key(client: TestClient, fake_tts_service: None) -> None:
    response = client.post(
        "/api/v1/tts/generate",
        json={
            "text": "你好，世界",
            "title": "测试配音任务",
            "api_key": "   ",
        },
    )

    assert response.status_code == 422


def test_tts_rejects_unknown_shot_id(client: TestClient, fake_tts_service: None) -> None:
    response = client.post(
        "/api/v1/tts/generate",
        json={
            "text": "你好，世界",
            "title": "测试配音任务",
            "shot_id": "missing-shot",
            "api_key": "test-key",
        },
    )

    assert response.status_code == 404


def test_synthesis_requires_api_key(client: TestClient, fake_synthesis_service: None) -> None:
    response = client.post(
        "/api/v1/synthesis/generate",
        json={
            "video_url": "https://example.com/source.mp4",
            "audio_url": "https://example.com/audio.mp3",
            "title": "测试合成任务",
        },
    )

    assert response.status_code == 422


def test_synthesis_requires_audio_url(client: TestClient, fake_synthesis_service: None) -> None:
    response = client.post(
        "/api/v1/synthesis/generate",
        json={
            "video_url": "https://example.com/source.mp4",
            "title": "测试合成任务",
            "api_key": "test-key",
        },
    )

    assert response.status_code == 422


def test_synthesis_rejects_blank_api_key(client: TestClient, fake_synthesis_service: None) -> None:
    response = client.post(
        "/api/v1/synthesis/generate",
        json={
            "video_url": "https://example.com/source.mp4",
            "audio_url": "https://example.com/audio.mp3",
            "title": "测试合成任务",
            "api_key": "   ",
        },
    )

    assert response.status_code == 422


def test_synthesis_rejects_invalid_video_url(client: TestClient, fake_synthesis_service: None) -> None:
    response = client.post(
        "/api/v1/synthesis/generate",
        json={
            "video_url": "not-a-url",
            "audio_url": "https://example.com/audio.mp3",
            "title": "测试合成任务",
            "api_key": "test-key",
        },
    )

    assert response.status_code == 422


def test_tts_generate_returns_502_when_service_fails(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _failing_text_to_speech(self, *args, **kwargs):
        raise Exception("upstream failure")

    monkeypatch.setattr(
        "app.services.volcano_service.VolcanoService.text_to_speech",
        _failing_text_to_speech,
    )

    response = client.post(
        "/api/v1/tts/generate",
        json={
            "text": "你好，世界",
            "title": "测试配音任务",
            "api_key": "test-key",
        },
    )

    assert response.status_code == 502


def test_synthesis_generate_returns_502_when_service_fails(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _failing_video_voice_synthesis(self, *args, **kwargs):
        raise Exception("upstream failure")

    monkeypatch.setattr(
        "app.services.volcano_service.VolcanoService.video_voice_synthesis",
        _failing_video_voice_synthesis,
    )

    response = client.post(
        "/api/v1/synthesis/generate",
        json={
            "video_url": "https://example.com/source.mp4",
            "audio_url": "https://example.com/audio.mp3",
            "title": "测试合成任务",
            "api_key": "test-key",
        },
    )

    assert response.status_code == 502


def test_tts_defaults_status_and_progress_when_service_omits_status(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _text_to_speech_without_status(self, *args, **kwargs):
        return {
            "task_id": "tts-task-no-status",
            "audio_url": "https://example.com/audio-no-status.mp3",
            "duration": 2.0,
            "model": "test-tts-model",
            "message": "done",
        }

    monkeypatch.setattr(
        "app.services.volcano_service.VolcanoService.text_to_speech",
        _text_to_speech_without_status,
    )

    response = client.post(
        "/api/v1/tts/generate",
        json={
            "text": "你好，世界",
            "title": "测试配音任务",
            "api_key": "test-key",
        },
    )

    assert response.status_code == 200
    job_id = response.json()["job_id"]

    jobs_response = client.get("/api/v1/tts/jobs")
    assert jobs_response.status_code == 200
    jobs = jobs_response.json()
    job = next(job for job in jobs if job["id"] == job_id)
    assert job["status"] == "succeeded"
    assert job["progress"] == 100


def test_synthesis_defaults_status_progress_and_model_metadata_when_service_omits_status(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _video_voice_synthesis_without_status(self, *args, **kwargs):
        return {
            "task_id": "synthesis-task-no-status",
            "output_url": "https://example.com/video-no-status.mp4",
            "duration": 6.0,
            "message": "done",
        }

    monkeypatch.setattr(
        "app.services.volcano_service.VolcanoService.video_voice_synthesis",
        _video_voice_synthesis_without_status,
    )

    response = client.post(
        "/api/v1/synthesis/generate",
        json={
            "video_url": "https://example.com/source.mp4",
            "audio_url": "https://example.com/audio.mp3",
            "title": "测试合成任务",
            "api_key": "test-key",
        },
    )

    assert response.status_code == 200
    job_id = response.json()["job_id"]

    jobs_response = client.get("/api/v1/synthesis/jobs")
    assert jobs_response.status_code == 200
    jobs = jobs_response.json()
    job = next(job for job in jobs if job["id"] == job_id)
    assert job["status"] == "succeeded"
    assert job["progress"] == 100
    assert job["model_name"] == "volcano-synthesis"


def test_video_download_supports_relative_static_url(client: TestClient) -> None:
    static_dev_dir = Path(__file__).resolve().parent / "static" / "dev"
    static_dev_dir.mkdir(parents=True, exist_ok=True)
    asset = static_dev_dir / f"download-{uuid4()}.mp4"
    asset.write_bytes(b"fake-video-bytes")
    try:
        response = client.post(
            "/api/v1/video/download",
            json={"video_url": f"/static/dev/{asset.name}", "filename": "clip.mp4"},
        )
    finally:
        asset.unlink(missing_ok=True)

    assert response.status_code == 200
    assert response.content == b"fake-video-bytes"
    assert "attachment" in response.headers.get("content-disposition", "")


def test_timeline_clip_create_uses_nested_clip_route(client: TestClient) -> None:
    user_id = f"timeline-clip-{uuid4()}"
    project_resp = client.post(
        "/api/v1/projects",
        json={"name": "Timeline Clip Project"},
        headers=_auth_headers(user_id),
    )
    assert project_resp.status_code == 201

    timeline_resp = client.post(
        "/api/v1/timelines",
        json={
            "project_id": project_resp.json()["id"],
            "name": "Editable Timeline",
            "video_track_count": 1,
            "audio_track_count": 1,
            "subtitle_track_count": 1,
        },
        headers=_auth_headers(user_id),
    )
    assert timeline_resp.status_code == 201
    timeline_id = timeline_resp.json()["id"]

    tracks_resp = client.get(f"/api/v1/timelines/{timeline_id}/tracks", headers=_auth_headers(user_id))
    assert tracks_resp.status_code == 200
    subtitle_track = next(track for track in tracks_resp.json() if track["track_type"] == "subtitle")

    clip_resp = client.post(
        f"/api/v1/timelines/{timeline_id}/clips",
        json={
            "timeline_id": timeline_id,
            "track_id": subtitle_track["id"],
            "source_type": "subtitle",
            "position": 0,
            "duration": 4,
            "name": "字幕片段",
            "text_content": "可编辑字幕",
        },
        headers=_auth_headers(user_id),
    )
    assert clip_resp.status_code == 201
    clip = clip_resp.json()
    assert clip["timeline_id"] == timeline_id
    assert clip["source_type"] == "subtitle"
    assert clip["text_content"] == "可编辑字幕"

    mismatch_resp = client.post(
        f"/api/v1/timelines/{timeline_id}/clips",
        json={
            "timeline_id": str(uuid4()),
            "track_id": subtitle_track["id"],
            "source_type": "subtitle",
        },
        headers=_auth_headers(user_id),
    )
    assert mismatch_resp.status_code == 422


def test_workflow_media_batch_tracks_final_quality_production_strategy(client: TestClient) -> None:
    user_id = f"strategy-trace-{uuid4()}"
    script_id = _create_script(client, user_id)
    story_bible_resp = client.post(
        "/api/v1/story-bibles",
        json={
            "title": "策略追踪 Story Bible",
            "style": "测试风格",
            "character_rules": [{"name": "策略角色", "voice": "strategy-voice"}],
        },
        headers=_auth_headers(user_id),
    )
    assert story_bible_resp.status_code == 201
    story_bible_id = story_bible_resp.json()["id"]
    storyboard_resp = client.post(
        "/api/v1/storyboards",
        json={
            "script_id": script_id,
            "title": "策略追踪分镜",
            "description": "test storyboard",
            "content": {"story_bible_id": story_bible_id},
        },
        headers=_auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201
    storyboard_id = storyboard_resp.json()["id"]
    shot_resp = client.post(
        "/api/v1/shots",
        json={
            "storyboard_id": storyboard_id,
            "shot_number": 1,
            "duration": 4,
            "prompt": "策略角色追踪镜头",
            "dialogue": "策略角色：最终质量策略应被记录。",
            "character_refs": [{"name": "策略角色"}],
        },
        headers=_auth_headers(user_id),
    )
    assert shot_resp.status_code == 201
    shot_id = shot_resp.json()["id"]
    _set_shot_extra_data(
        shot_id,
        {
            "story_bible_id": story_bible_id,
            "subtitle_text": "策略角色：最终质量策略应被记录。",
            "production_context": {
                "asset_version_locks": [
                    {
                        "asset_id": "strategy-asset-v1",
                        "asset_version_id": "strategy-asset-version-1",
                        "entity_name": "策略角色",
                        "category": "character",
                    }
                ]
            },
        },
    )

    workflow_resp = client.post(
        "/api/v1/workflow/start",
        json={
            "title": "策略追踪工作流",
            "script_id": script_id,
            "storyboard_id": storyboard_id,
        },
        headers=_auth_headers(user_id),
    )
    assert workflow_resp.status_code == 201
    workflow_id = workflow_resp.json()["workflow_id"]

    batch_resp = client.post(
        f"/api/v1/workflow/{workflow_id}/generate-media-batch",
        json={
            "strategy": "direct_av_first",
            "production_strategy": "final_quality",
            "subtitle_mode": "shot_dialogue",
            "audio_mode": "model_audio",
        },
        headers=_auth_headers(user_id),
    )
    assert batch_resp.status_code == 200, batch_resp.text
    batch_payload = batch_resp.json()
    assert batch_payload["production_strategy"] == "final_quality"
    assert len(batch_payload["media_job_ids"]) == 1

    status_resp = client.get(f"/api/v1/workflow/status/{workflow_id}", headers=_auth_headers(user_id))
    assert status_resp.status_code == 200
    metadata = status_resp.json()["metadata"]
    assert metadata["latest_production_strategy"] == "final_quality"
    assert metadata["latest_production_strategy_intent"] == "final"
    assert metadata["latest_recommended_model_hint"] == "Seedance-2.0"
    assert metadata["production_strategy_metadata"]["production_strategy_label"] == "Final Quality"
    assert metadata["production_strategy_metadata"]["routing_enabled"] is True
    status_media_extra = status_resp.json()["media_jobs"][0]["extra_data"]
    assert status_media_extra["production_strategy"] == "final_quality"
    assert status_media_extra["production_strategy_intent"] == "final"
    assert status_media_extra["recommended_model_hint"] == "Seedance-2.0"

    detail_resp = client.get(f"/api/v1/workflow/{workflow_id}", headers=_auth_headers(user_id))
    assert detail_resp.status_code == 200
    assert detail_resp.json()["metadata"]["latest_production_strategy_label"] == "Final Quality"

    snapshot_resp = client.get(f"/api/v1/studio/workflows/{workflow_id}/snapshot", headers=_auth_headers(user_id))
    assert snapshot_resp.status_code == 200
    snapshot = snapshot_resp.json()
    assert snapshot["workflow"]["latest_production_strategy"] == "final_quality"
    assert snapshot["workflow"]["latest_production_strategy_intent"] == "final"
    assert snapshot["workflow"]["metadata"]["latest_recommended_model_hint"] == "Seedance-2.0"
    assert snapshot["workflow"]["metadata"]["production_strategy_metadata"]["strategy_routing_enabled"] is True
    assert snapshot["jobs"]["media_jobs"][0]["production_strategy_label"] == "Final Quality"

    extra = _get_media_job_extra(batch_payload["media_job_ids"][0])
    assert extra["production_strategy"] == "final_quality"
    assert extra["production_strategy_label"] == "Final Quality"
    assert extra["production_strategy_intent"] == "final"
    assert extra["recommended_model_hint"] == "Seedance-2.0"


def test_tts_generate_and_list_job(client: TestClient, fake_tts_service: None) -> None:
    response = client.post(
        "/api/v1/tts/generate",
        json={
            "text": "你好，世界",
            "title": "测试配音任务",
            "api_key": "test-key",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"] == "tts-task-123"
    assert payload["status"] == "succeeded"
    assert payload["job_id"]

    jobs_response = client.get("/api/v1/tts/jobs")
    assert jobs_response.status_code == 200
    jobs = jobs_response.json()
    assert any(job["id"] == payload["job_id"] for job in jobs)
    assert any(job["audio_url"] == "https://example.com/audio.mp3" for job in jobs)


def test_synthesis_generate_and_list_job(client: TestClient, fake_synthesis_service: None) -> None:
    response = client.post(
        "/api/v1/synthesis/generate",
        json={
            "video_url": "https://example.com/source.mp4",
            "audio_url": "https://example.com/audio.mp3",
            "title": "测试合成任务",
            "api_key": "test-key",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"] == "synthesis-task-123"
    assert payload["status"] == "succeeded"
    assert payload["job_id"]

    jobs_response = client.get("/api/v1/synthesis/jobs")
    assert jobs_response.status_code == 200
    jobs = jobs_response.json()
    assert any(job["id"] == payload["job_id"] for job in jobs)
    assert any(job["output_url"] == "https://example.com/video.mp4" for job in jobs)

def _create_final_quality_workflow(
    client: TestClient,
    user_id: str,
    *,
    asset_locks: list[dict] | None = None,
    character_rules: list[dict] | None = None,
    dialogue: str = "孙剑：这次我要赢。",
) -> tuple[str, str]:
    novel_id = _create_novel(client, user_id)
    chapter_id = _create_chapter(client, user_id, novel_id, "第一章 终稿锁")
    bible_resp = client.post(
        "/api/v1/story-bibles",
        json={
            "novel_id": novel_id,
            "title": "终稿锁 Story Bible",
            "style": "国风动画",
            "character_rules": character_rules if character_rules is not None else [{"name": "孙剑"}],
        },
        headers=_auth_headers(user_id),
    )
    assert bible_resp.status_code == 201
    story_bible_id = bible_resp.json()["id"]

    script_resp = client.post(
        "/api/v1/scripts",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "title": "终稿锁剧本",
            "content": "孙剑在雨夜确认计划。",
        },
        headers=_auth_headers(user_id),
    )
    assert script_resp.status_code == 201
    storyboard_resp = client.post(
        "/api/v1/storyboards",
        json={
            "script_id": script_resp.json()["id"],
            "title": "终稿锁分镜",
            "content": {"chapter_id": chapter_id, "story_bible_id": story_bible_id},
        },
        headers=_auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201

    extra_data: dict = {"story_bible_id": story_bible_id}
    if asset_locks is not None:
        extra_data["production_context"] = {"asset_version_locks": asset_locks}
    shot_resp = client.post(
        "/api/v1/shots",
        json={
            "storyboard_id": storyboard_resp.json()["id"],
            "shot_number": 1,
            "duration": 4,
            "prompt": "孙剑雨夜拔剑" if dialogue else "雨夜空镜，雨水落在屋檐上。",
            "dialogue": dialogue,
            "character_refs": [{"name": "孙剑"}] if dialogue else [],
            "extra_data": extra_data,
        },
        headers=_auth_headers(user_id),
    )
    assert shot_resp.status_code == 201
    shot_id = shot_resp.json()["id"]

    workflow_resp = client.post(
        "/api/v1/workflow/start",
        json={
            "title": "终稿锁工作流",
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "script_id": script_resp.json()["id"],
            "storyboard_id": storyboard_resp.json()["id"],
        },
        headers=_auth_headers(user_id),
    )
    assert workflow_resp.status_code == 201
    _set_shot_extra_data(shot_id, extra_data)
    return workflow_resp.json()["workflow_id"], story_bible_id


def test_final_quality_media_batch_requires_asset_and_voice_locks(client: TestClient) -> None:
    user_id = f"final-locks-missing-{uuid4()}"
    workflow_id, _ = _create_final_quality_workflow(client, user_id)

    response = client.post(
        f"/api/v1/workflow/{workflow_id}/generate-media-batch",
        json={"strategy": "direct_av_first", "production_strategy": "final_quality"},
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "final_quality_locks_missing"
    assert detail["missing_assets"]
    assert detail["missing_voices"] == []


def test_final_quality_seedance20_blocks_insufficient_reference_package(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            class _CreateResult:
                id = "video-task-should-not-run"

            return _CreateResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    monkeypatch.setattr("app.features.video_generation.public.create_ark_client", lambda *_: _FakeArkClient())

    user_id = uuid4().hex
    asset_locks = [
        {
            "asset_id": "asset-sunjian-front",
            "asset_version_id": "asset-sunjian-front-v1",
            "entity_name": "孙剑",
            "category": "character",
        }
    ]
    workflow_id, _story_bible_id = _create_final_quality_workflow(
        client,
        user_id,
        asset_locks=asset_locks,
        character_rules=[{"name": "孙剑", "voice": "story-bible-sunjian"}],
    )
    shot_id = _get_first_workflow_shot_id(workflow_id)
    _seed_shot_reference_assets(user_id, shot_id, views=("front",))
    video_config_id = _insert_model_config(
        user_id=user_id,
        provider_id="volcano",
        model_id=f"test-video-final-ref-gate-{uuid4()}",
        api_model_id="doubao-seedance-2-0-260128",
        model_type="video",
        capabilities=["text-to-video", "image-to-video"],
        api_key="sk-video",
    )

    response = client.post(
        f"/api/v1/workflow/{workflow_id}/generate-media-batch",
        json={
            "strategy": "separate_video_tts",
            "production_strategy": "final_quality",
            "model_config_id": video_config_id,
            "audio_mode": "none",
        },
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "reference_package_insufficient"
    assert detail["issues"][0]["code"] == "reference_package_insufficient"
    assert detail["issues"][0]["entity_name"] == "孙剑"
    assert detail["issues"][0]["available_reference_images"] == 1


def test_final_quality_legacy_video_model_allows_single_reference_view(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_video: list[dict] = []

    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            captured_video.append(kwargs)

            class _CreateResult:
                id = "video-task-legacy-final-reference"

            return _CreateResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    monkeypatch.setattr("app.features.video_generation.public.create_ark_client", lambda *_: _FakeArkClient())

    user_id = uuid4().hex
    asset_locks = [
        {
            "asset_id": "asset-sunjian-front",
            "asset_version_id": "asset-sunjian-front-v1",
            "entity_name": "孙剑",
            "category": "character",
        }
    ]
    workflow_id, _story_bible_id = _create_final_quality_workflow(
        client,
        user_id,
        asset_locks=asset_locks,
        character_rules=[{"name": "孙剑", "voice": "story-bible-sunjian"}],
    )
    shot_id = _get_first_workflow_shot_id(workflow_id)
    _seed_shot_reference_assets(user_id, shot_id, views=("front",))
    video_config_id = _insert_model_config(
        user_id=user_id,
        provider_id="volcano",
        model_id=f"test-video-final-legacy-{uuid4()}",
        api_model_id="Doubao-Seedance-1.0-pro-fast",
        model_type="video",
        capabilities=["text-to-video", "image-to-video"],
        api_key="sk-video",
    )

    response = client.post(
        f"/api/v1/workflow/{workflow_id}/generate-media-batch",
        json={
            "strategy": "separate_video_tts",
            "production_strategy": "final_quality",
            "model_config_id": video_config_id,
            "audio_mode": "none",
        },
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    assert len(captured_video) == 1
    assert response.json()["video_job_ids"]
    video_extra = _get_video_job_extra(response.json()["video_job_ids"][0])
    assert video_extra["visual_consistency_auto_check"] is True
    assert "visual_consistency_extract_frames" not in video_extra


def test_draft_fast_media_batch_does_not_require_final_quality_locks(client: TestClient) -> None:
    user_id = f"draft-locks-open-{uuid4()}"
    workflow_id, _ = _create_final_quality_workflow(client, user_id)

    response = client.post(
        f"/api/v1/workflow/{workflow_id}/generate-media-batch",
        json={"strategy": "direct_av_first", "production_strategy": "draft_fast"},
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    assert response.json()["created_count"] == 1


def test_final_quality_media_batch_saves_asset_and_voice_lock_snapshots(client: TestClient) -> None:
    user_id = f"final-locks-snapshot-{uuid4()}"
    asset_locks = [
        {
            "asset_id": "asset-sunjian-v1",
            "asset_version_id": "asset-sunjian-version-1",
            "entity_name": "孙剑",
            "category": "character",
        }
    ]
    workflow_id, story_bible_id = _create_final_quality_workflow(
        client,
        user_id,
        asset_locks=asset_locks,
        character_rules=[{"name": "孙剑", "voice": "story-bible-sunjian", "voice_speed": 1.1}],
    )

    response = client.post(
        f"/api/v1/workflow/{workflow_id}/generate-media-batch",
        json={"strategy": "direct_av_first", "production_strategy": "final_quality"},
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    extra = _get_media_job_extra(response.json()["media_job_ids"][0])
    assert extra["asset_version_locks"] == asset_locks
    assert extra["asset_lock_snapshot"] == asset_locks
    assert extra["voice_lock_snapshot"] == {
        "character_name": "孙剑",
        "story_bible_id": story_bible_id,
        "voice": "story-bible-sunjian",
        "voice_source": "story_bible",
    }


def test_final_quality_separate_video_tts_uses_provider_default_voice_lock(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_video: list[dict] = []
    captured_tts: list[dict] = []

    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            captured_video.append(kwargs)

            class _CreateResult:
                id = "video-task-final-default-voice"

            return _CreateResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    def _fake_create_ark_client(api_key: str, base_url: str | None = None):
        assert api_key == "sk-volcano"
        return _FakeArkClient()

    async def _fake_volcano_tts(**kwargs):
        captured_tts.append(kwargs)
        return {
            "task_id": "tts-task-final-default-voice",
            "audio_url": "https://example.com/final-default-voice.mp3",
            "duration": 2.5,
            "status": "succeeded",
        }

    monkeypatch.setattr("app.features.video_generation.public.create_ark_client", _fake_create_ark_client)
    monkeypatch.setattr("app.services.volcano_speech_tts.synthesize_volcano_speech_v3", _fake_volcano_tts)

    user_id = f"final-provider-voice-{uuid4().hex[:15]}"
    video_config_id = _insert_model_config(
        user_id=user_id,
        provider_id="volcano",
        model_id=f"test-final-provider-video-{uuid4()}",
        api_model_id="doubao-seedance-1-5-pro-251215",
        model_type="video",
        capabilities=["text-to-video", "image-to-video"],
        api_key="sk-volcano",
    )
    audio_config_id = _insert_model_config(
        user_id=user_id,
        provider_id="volcano",
        model_id=f"test-final-provider-tts-{uuid4()}",
        api_model_id="doubao-tts",
        model_type="tts",
        capabilities=["text-to-speech"],
        api_key="sk-volcano-tts",
    )
    asset_locks = [
        {
            "asset_id": "asset-sunjian-v1",
            "asset_version_id": "asset-sunjian-version-1",
            "entity_name": "孙剑",
            "category": "character",
        }
    ]
    workflow_id, story_bible_id = _create_final_quality_workflow(
        client,
        user_id,
        asset_locks=asset_locks,
        character_rules=[{"name": "孙剑"}],
    )

    response = client.post(
        f"/api/v1/workflow/{workflow_id}/generate-media-batch",
        json={
            "strategy": "separate_video_tts",
            "production_strategy": "final_quality",
            "model_config_id": video_config_id,
            "audio_model_config_id": audio_config_id,
            "audio_mode": "model_audio",
            "voice_model": "female-shaonj",
        },
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["tts_voice_lock_count"] == 1
    assert len(payload["video_job_ids"]) == 1
    assert len(payload["tts_job_ids"]) == 1
    assert "generate_audio" not in captured_video[0]
    assert captured_tts[0]["voice"] == "female_nvsheng"
    video_extra = _get_video_job_extra(payload["video_job_ids"][0])
    tts_extra = _get_tts_job_extra(payload["tts_job_ids"][0])
    assert video_extra["voice_lock_snapshot"] == {
        "character_name": "孙剑",
        "story_bible_id": story_bible_id,
        "voice": "female_nvsheng",
        "speed": 1.0,
        "voice_source": "provider_default_tts",
    }
    assert tts_extra["voice_lock_snapshot"] == video_extra["voice_lock_snapshot"]
    assert tts_extra["dialogue_sync_contract"]["voice"] == "female_nvsheng"
    assert tts_extra["dialogue_sync_contract"]["video_native_audio"] is False


def test_final_quality_no_dialogue_shot_does_not_require_voice_lock(client: TestClient) -> None:
    user_id = f"final-locks-no-dialogue-{uuid4()}"
    asset_locks = [
        {
            "asset_id": "asset-empty-shot-v1",
            "asset_version_id": "asset-empty-shot-version-1",
            "entity_name": "环境",
            "category": "environment",
        }
    ]
    workflow_id, _ = _create_final_quality_workflow(
        client,
        user_id,
        asset_locks=asset_locks,
        character_rules=[],
        dialogue="",
    )

    response = client.post(
        f"/api/v1/workflow/{workflow_id}/generate-media-batch",
        json={"strategy": "direct_av_first", "production_strategy": "final_quality"},
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    extra = _get_media_job_extra(response.json()["media_job_ids"][0])
    assert extra["asset_version_locks"] == asset_locks
    assert extra.get("voice_lock_snapshot") is None


def _create_audio_route_workflow(
    client: TestClient,
    user_id: str,
    *,
    dialogue: str = "",
    legacy_subtitle: str = "",
    character_rules: list[dict] | None = None,
    asset_locks: list[dict] | None = None,
) -> tuple[str, str]:
    novel_id = _create_novel(client, user_id)
    chapter_id = _create_chapter(client, user_id, novel_id, "第一章 音频路由")
    bible_resp = client.post(
        "/api/v1/story-bibles",
        json={
            "novel_id": novel_id,
            "title": "音频路由 Story Bible",
            "style": "国风动画",
            "character_rules": character_rules or [],
        },
        headers=_auth_headers(user_id),
    )
    assert bible_resp.status_code == 201
    story_bible_id = bible_resp.json()["id"]

    script_resp = client.post(
        "/api/v1/scripts",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "title": "音频路由剧本",
            "content": "孙剑在雨夜确认计划。",
        },
        headers=_auth_headers(user_id),
    )
    assert script_resp.status_code == 201
    storyboard_resp = client.post(
        "/api/v1/storyboards",
        json={
            "script_id": script_resp.json()["id"],
            "title": "音频路由分镜",
            "content": {"chapter_id": chapter_id, "story_bible_id": story_bible_id},
        },
        headers=_auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201

    extra_data: dict = {"story_bible_id": story_bible_id}
    if legacy_subtitle:
        extra_data["subtitle"] = legacy_subtitle
    if asset_locks is not None:
        extra_data["production_context"] = {"asset_version_locks": asset_locks}

    shot_resp = client.post(
        "/api/v1/shots",
        json={
            "storyboard_id": storyboard_resp.json()["id"],
            "shot_number": 1,
            "duration": 4,
            "prompt": "孙剑雨夜拔剑" if dialogue or legacy_subtitle else "雨夜空镜，风吹过屋檐",
            "dialogue": dialogue,
            "character_refs": [{"name": "孙剑"}] if dialogue or legacy_subtitle else [],
            "extra_data": extra_data,
        },
        headers=_auth_headers(user_id),
    )
    assert shot_resp.status_code == 201
    _set_shot_extra_data(shot_resp.json()["id"], extra_data)

    workflow_resp = client.post(
        "/api/v1/workflow/start",
        json={
            "title": "音频路由工作流",
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "script_id": script_resp.json()["id"],
            "storyboard_id": storyboard_resp.json()["id"],
        },
        headers=_auth_headers(user_id),
    )
    assert workflow_resp.status_code == 201
    return workflow_resp.json()["workflow_id"], story_bible_id


def test_separate_video_tts_records_tts_audio_route_for_voice_lock(client: TestClient) -> None:
    user_id = f"audio-route-lock-{uuid4().hex[:16]}"
    workflow_id, story_bible_id = _create_audio_route_workflow(
        client,
        user_id,
        dialogue="孙剑：出发。",
        character_rules=[{"name": "孙剑", "voice": "story-bible-sunjian"}],
    )

    response = client.post(
        f"/api/v1/workflow/{workflow_id}/generate-media-batch",
        json={
            "strategy": "separate_video_tts",
            "production_strategy": "draft_fast",
            "story_bible_id": story_bible_id,
            "audio_mode": "model_audio",
        },
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload["video_job_ids"]) == 1
    assert len(payload["tts_job_ids"]) == 1
    video_extra = _get_video_job_extra(payload["video_job_ids"][0])
    tts_extra = _get_tts_job_extra(payload["tts_job_ids"][0])
    video_prompt = _get_video_job_prompt(payload["video_job_ids"][0])
    assert video_extra["audio_route"] == {"route": "tts", "reason": "voice_lock"}
    assert video_extra["video_native_audio"] is False
    assert "visual_consistency_auto_check" not in video_extra
    assert tts_extra["audio_route"] == {"route": "tts", "reason": "voice_lock"}
    assert video_extra["dialogue_sync_contract"] == tts_extra["dialogue_sync_contract"]
    contract = video_extra["dialogue_sync_contract"]
    assert contract["speaker"] == "孙剑"
    assert contract["spoken_text"] == "出发。"
    assert contract["subtitle_text"] == "孙剑：出发。"
    assert contract["voice"] == "story-bible-sunjian"
    assert contract["audio_source"] == "separate_tts"
    assert contract["video_native_audio"] is False
    assert _get_tts_job_text(payload["tts_job_ids"][0]) == contract["spoken_text"]
    assert "只做无声口型和表演" in video_prompt
    assert "不要生成原生对白或人声" in video_prompt
    assert "出发。" in video_prompt


def test_separate_video_tts_uses_legacy_subtitle_field_for_tts_text(client: TestClient) -> None:
    user_id = f"audio-route-subtitle-{uuid4().hex[:16]}"
    workflow_id, _story_bible_id = _create_audio_route_workflow(
        client,
        user_id,
        dialogue="",
        legacy_subtitle="孙剑：旧字段对白。",
    )

    response = client.post(
        f"/api/v1/workflow/{workflow_id}/generate-media-batch",
        json={
            "strategy": "separate_video_tts",
            "production_strategy": "draft_fast",
            "audio_mode": "model_audio",
        },
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload["video_job_ids"]) == 1
    assert len(payload["tts_job_ids"]) == 1
    video_extra = _get_video_job_extra(payload["video_job_ids"][0])
    tts_extra = _get_tts_job_extra(payload["tts_job_ids"][0])
    assert video_extra["audio_route"] == {"route": "tts", "reason": "voice_lock_missing"}
    assert tts_extra["audio_route"] == {"route": "tts", "reason": "voice_lock_missing"}
    assert video_extra["dialogue_sync_contract"] == tts_extra["dialogue_sync_contract"]
    assert tts_extra["dialogue_sync_contract"]["subtitle_text"] == "孙剑：旧字段对白。"
    assert tts_extra["dialogue_sync_contract"]["spoken_text"] == "旧字段对白。"
    assert _get_tts_job_text(payload["tts_job_ids"][0]) == "旧字段对白。"


def test_separate_video_tts_rejects_multi_speaker_single_tts_contract(client: TestClient) -> None:
    user_id = f"audio-route-multi-speaker-{uuid4().hex[:16]}"
    workflow_id, story_bible_id = _create_audio_route_workflow(
        client,
        user_id,
        dialogue="孙剑：出发。\n阿岚：等等。",
        character_rules=[
            {"name": "孙剑", "voice": "story-bible-sunjian"},
            {"name": "阿岚", "voice": "story-bible-alan"},
        ],
    )

    response = client.post(
        f"/api/v1/workflow/{workflow_id}/generate-media-batch",
        json={
            "strategy": "separate_video_tts",
            "production_strategy": "draft_fast",
            "story_bible_id": story_bible_id,
            "audio_mode": "model_audio",
        },
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "multi_speaker_dialogue_requires_segmented_tts"
    assert detail["shot_number"] == 1
    assert detail["speakers"] == ["孙剑", "阿岚"]


def test_action_shot_records_native_audio_route_on_seedance20(client: TestClient) -> None:
    user_id = f"audio-route-native-{uuid4().hex[:16]}"
    workflow_id, _story_bible_id = _create_audio_route_workflow(client, user_id, dialogue="")
    model_config_id = _insert_model_config(
        user_id=user_id,
        provider_id="volcano",
        model_id=f"seedance20-audio-route-{uuid4()}",
        api_model_id="doubao-seedance-2-0-260128",
        model_type="video",
        capabilities=["text-to-video", "image-to-video", "video"],
        api_key="",
    )

    response = client.post(
        f"/api/v1/workflow/{workflow_id}/generate-media-batch",
        json={
            "strategy": "separate_video_tts",
            "production_strategy": "draft_fast",
            "model_config_id": model_config_id,
            "audio_mode": "model_audio",
        },
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload["video_job_ids"]) == 1
    assert payload["tts_job_ids"] == []
    video_extra = _get_video_job_extra(payload["video_job_ids"][0])
    assert video_extra["audio_route"] == {
        "route": "native_audio",
        "reason": "native_audio_supported",
    }


def test_production_native_audio_route_does_not_require_tts_api_key(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_video: list[dict] = []

    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            captured_video.append(kwargs)

            class _CreateResult:
                id = f"native-video-task-{len(captured_video)}"

            return _CreateResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    async def _fake_generation_context_package(*args, **kwargs):
        return {
            "ready": True,
            "issues": [],
            "blocking_issue_count": 0,
        }

    monkeypatch.setattr("app.features.video_generation.public.create_ark_client", lambda *_: _FakeArkClient())
    monkeypatch.setattr(
            "app.features.workflow_media.application.prepare_separate_media.build_generation_context_package",
        _fake_generation_context_package,
    )

    user_id = f"native-no-tts-key-{uuid4().hex[:16]}"
    asset_locks = [
        {
            "asset_id": "asset-native-action-v1",
            "asset_version_id": "asset-native-action-version-1",
            "entity_name": "环境",
            "category": "environment",
        }
    ]
    workflow_id, _story_bible_id = _create_audio_route_workflow(
        client,
        user_id,
        dialogue="",
        asset_locks=asset_locks,
    )
    model_config_id = _insert_model_config(
        user_id=user_id,
        provider_id="volcano",
        model_id=f"seedance20-no-tts-key-{uuid4()}",
        api_model_id="doubao-seedance-2-0-260128",
        model_type="video",
        capabilities=["text-to-video", "image-to-video", "video"],
        api_key="sk-video",
    )

    monkeypatch.setenv("DEV_MODE", "false")
    response = client.post(
        f"/api/v1/workflow/{workflow_id}/generate-media-batch",
        json={
            "strategy": "separate_video_tts",
            "production_strategy": "draft_fast",
            "model_config_id": model_config_id,
            "audio_mode": "model_audio",
        },
        headers=_signed_auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload["video_job_ids"]) == 1
    assert payload["tts_job_ids"] == []
    assert len(captured_video) == 1
    video_extra = _get_video_job_extra(payload["video_job_ids"][0])
    assert video_extra["audio_route"] == {
        "route": "native_audio",
        "reason": "native_audio_supported",
    }


def test_character_card_ready_matches_final_quality_gate_happy_path(client: TestClient) -> None:
    user_id = uuid4().hex
    novel_id = _create_novel(client, user_id)
    chapter_id = _create_chapter(client, user_id, novel_id, "第一章 定稿一致性")
    bible_resp = client.post(
        "/api/v1/story-bibles",
        json={
            "novel_id": novel_id,
            "title": "定稿一致性 Story Bible",
            "style": "国风动画",
            "character_rules": [{"name": "孙剑", "voice": "story-bible-sunjian", "voice_speed": 1.0}],
        },
        headers=_auth_headers(user_id),
    )
    assert bible_resp.status_code == 201
    story_bible_id = bible_resp.json()["id"]

    script_resp = client.post(
        "/api/v1/scripts",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "title": "定稿一致性剧本",
            "content": "孙剑在雨夜确认计划。",
        },
        headers=_auth_headers(user_id),
    )
    assert script_resp.status_code == 201
    storyboard_resp = client.post(
        "/api/v1/storyboards",
        json={
            "script_id": script_resp.json()["id"],
            "title": "定稿一致性分镜",
            "content": {"chapter_id": chapter_id, "story_bible_id": story_bible_id},
        },
        headers=_auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201
    storyboard_id = storyboard_resp.json()["id"]

    entity_id = f"ready-character-{uuid4()}"
    asset_rows = []
    asset_locks = []
    for view_key in ("front", "side", "back"):
        asset_id = f"ready-asset-{view_key}-{uuid4()}"
        asset_rows.append(
            Asset(
                id=asset_id,
                user_id=user_id,
                novel_id=novel_id,
                entity_id=entity_id,
                entity_type="character",
                category="character",
                name=f"孙剑{view_key}定稿",
                asset_type="image",
                url=f"https://cdn.example.test/sunjian-{view_key}.png",
                version=1,
                is_active=True,
                is_final=True,
                is_locked=True,
                generation_params={"view_key": view_key},
            )
        )
        asset_locks.append(
            {
                "asset_id": asset_id,
                "asset_version_id": f"{asset_id}-v1",
                "entity_name": "孙剑",
                "category": "character",
                "view_key": view_key,
            }
        )

    async def _seed_entity_assets() -> None:
        async with AsyncSessionLocal() as session:
            session.add(
                StoryEntity(
                    id=entity_id,
                    user_id=user_id,
                    novel_id=novel_id,
                    entity_type="character",
                    name="孙剑",
                    description="雨夜持剑少年",
                    attributes={"visual_dna": {"hair": "black"}},
                    confidence=100,
                    is_approved=True,
                )
            )
            session.add_all(asset_rows)
            await session.commit()

    asyncio.run(_seed_entity_assets())

    card_resp = client.get(
        f"/api/v1/production-cards/entity/{entity_id}",
        headers=_auth_headers(user_id),
    )
    assert card_resp.status_code == 200, card_resp.text
    card = card_resp.json()
    assert card["readiness"]["final_ready"] is True
    assert card["readiness"]["gaps"] == []

    shot_extra = {
        "story_bible_id": story_bible_id,
        "production_context": {"asset_version_locks": asset_locks},
    }
    shot_resp = client.post(
        "/api/v1/shots",
        json={
            "storyboard_id": storyboard_id,
            "shot_number": 1,
            "duration": 4,
            "prompt": "孙剑雨夜拔剑",
            "dialogue": "孙剑：这次我要赢。",
            "character_refs": [{"name": "孙剑", "entity_id": entity_id}],
            "extra_data": shot_extra,
        },
        headers=_auth_headers(user_id),
    )
    assert shot_resp.status_code == 201
    _set_shot_extra_data(shot_resp.json()["id"], shot_extra)

    workflow_resp = client.post(
        "/api/v1/workflow/start",
        json={
            "title": "定稿一致性工作流",
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "script_id": script_resp.json()["id"],
            "storyboard_id": storyboard_id,
        },
        headers=_auth_headers(user_id),
    )
    assert workflow_resp.status_code == 201

    batch_resp = client.post(
        f"/api/v1/workflow/{workflow_resp.json()['workflow_id']}/generate-media-batch",
        json={"strategy": "direct_av_first", "production_strategy": "final_quality"},
        headers=_auth_headers(user_id),
    )

    assert batch_resp.status_code == 200, batch_resp.text
    extra = _get_media_job_extra(batch_resp.json()["media_job_ids"][0])
    assert extra["asset_version_locks"] == asset_locks
    assert extra["voice_lock_snapshot"]["voice"] == "story-bible-sunjian"
