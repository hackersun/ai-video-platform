from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.database import SyncSessionLocal
from app.models.external_api import ExternalAPIProvider
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


def test_external_providers_hide_internal_test_rows(client: TestClient) -> None:
    provider_ids = [f"external-provider-test-{uuid4()}" for _ in range(2)]
    with SyncSessionLocal() as db:
        for provider_id in provider_ids:
            db.add(
                ExternalAPIProvider(
                    id=provider_id,
                    name=f"external-provider-test-{uuid4()}",
                    name_cn="外部适配测试供应商",
                    api_type="video",
                    base_url="",
                    is_active=True,
                )
            )
        db.commit()

    try:
        response = client.get("/api/v1/external/providers")
        assert response.status_code == 200
        providers = response.json()
        assert "外部适配测试供应商" not in {provider["name_cn"] for provider in providers}
        assert not any(str(provider["name"]).startswith("external-provider-test-") for provider in providers)
        assert "text" not in {provider["api_type"] for provider in providers}
    finally:
        with SyncSessionLocal() as db:
            db.execute(delete(ExternalAPIProvider).where(ExternalAPIProvider.id.in_(provider_ids)))
            db.commit()


def _create_shot_with_lineage(client: TestClient, user_id: str) -> tuple[str, str, str, str, str]:
    novel_resp = client.post(
        "/api/v1/novels",
        json={
            "title": f"生产适配小说 {uuid4()}",
            "description": "角色：沈砚。场景：雾港旧码头。道具：铜铃。事件：密信失踪。",
        },
        headers=_auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_resp = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "第一章",
            "chapter_number": 1,
            "content": "沈砚在雾港旧码头听见铜铃声。",
        },
        headers=_auth_headers(user_id),
    )
    assert chapter_resp.status_code == 201
    chapter_id = chapter_resp.json()["id"]

    script_resp = client.post(
        "/api/v1/scripts",
        json={
            "novel_id": novel_id,
            "title": "第一集剧本",
            "content": "沈砚：铜铃又响了。",
            "extra_data": {"chapter_id": chapter_id},
        },
        headers=_auth_headers(user_id),
    )
    assert script_resp.status_code == 201
    script_id = script_resp.json()["id"]

    storyboard_resp = client.post(
        "/api/v1/storyboards",
        json={
            "script_id": script_id,
            "title": "第一集分镜",
            "description": "雨夜悬疑开场",
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
            "prompt": "雨夜旧码头，沈砚握住铜铃，镜头慢推。",
            "dialogue": "铜铃又响了。",
            "visual_description": "雨水打在木栈道上，远处灯塔闪烁。",
        },
        headers=_auth_headers(user_id),
    )
    assert shot_resp.status_code == 201
    return novel_id, chapter_id, script_id, storyboard_id, shot_resp.json()["id"]


def test_external_providers_and_config_lifecycle(client: TestClient) -> None:
    user_id = f"adapter-config-user-{uuid4()}"
    providers_resp = client.get("/api/v1/external/providers")
    assert providers_resp.status_code == 200
    provider_keys = {provider["name"] for provider in providers_resp.json()}
    assert {"openai", "google", "comfyui", "ffmpeg_cloud", "local_ffmpeg", "lip_sync"}.issubset(provider_keys)

    create_resp = client.post(
        "/api/v1/external/configs",
        json={
            "provider_id": "ffmpeg_cloud",
            "name": "测试云渲染",
            "custom_base_url": "http://127.0.0.1:9",
            "extra_config": {"submit_path": "/render", "health_path": "/health"},
            "is_default": True,
        },
        headers=_auth_headers(user_id),
    )
    assert create_resp.status_code == 201
    config = create_resp.json()
    assert config["provider_key"] == "ffmpeg_cloud"
    assert config["is_default"] is True

    test_resp = client.post(f"/api/v1/external/configs/{config['id']}/test", headers=_auth_headers(user_id))
    assert test_resp.status_code == 200
    assert test_resp.json()["status"] in {"configured", "success"}

    status_resp = client.get("/api/v1/external/capability-status", headers=_auth_headers(user_id))
    assert status_resp.status_code == 200
    readiness = status_resp.json()["readiness"]
    assert readiness["render"]["configured_count"] >= 1


def test_shot_production_context_stores_asset_locks_keyframes_lipsync_and_review(client: TestClient) -> None:
    user_id = f"shot-context-user-{uuid4()}"
    _novel_id, _chapter_id, _script_id, _storyboard_id, shot_id = _create_shot_with_lineage(client, user_id)

    asset_resp = client.post(
        "/api/v1/assets",
        json={
            "category": "character",
            "name": "沈砚正面定稿",
            "asset_type": "image",
            "url": "/static/dev/shenyan-front.png",
            "thumbnail_url": "/static/dev/shenyan-front-thumb.png",
        },
        headers=_auth_headers(user_id),
    )
    assert asset_resp.status_code == 201
    asset_id = asset_resp.json()["id"]

    update_resp = client.put(
        f"/api/v1/shots/{shot_id}/production-context",
        json={
            "asset_version_locks": [{"asset_id": asset_id, "role": "character_front", "version": 3}],
            "keyframes": [{"time": 0, "role": "start", "prompt": "沈砚正面看向码头"}, {"time": 4, "role": "end", "prompt": "沈砚握紧铜铃"}],
            "character_multiview_refs": [{"character": "沈砚", "front": "/static/dev/shenyan-front.png", "side": "/static/dev/shenyan-side.png"}],
            "lip_sync": {"mode": "provider", "audio_source": "shot_audio", "language": "zh-CN"},
            "review_state": "pending_review",
            "review_assignees": ["director", "animator"],
            "provider_hints": {"comfyui": {"workflow": "anime-shot-v1"}},
        },
        headers=_auth_headers(user_id),
    )
    assert update_resp.status_code == 200
    context = update_resp.json()["production_context"]
    assert context["asset_version_locks"][0]["asset_id"] == asset_id
    assert context["asset_version_locks"][0]["version"] == 3
    assert context["keyframes"][1]["role"] == "end"
    assert context["character_multiview_refs"][0]["side"].endswith("side.png")
    assert context["lip_sync"]["mode"] == "provider"
    assert context["review_state"] == "pending_review"


def test_shot_quality_report_and_budget_estimate_are_exposed(client: TestClient) -> None:
    user_id = f"shot-quality-user-{uuid4()}"
    _novel_id, _chapter_id, _script_id, _storyboard_id, shot_id = _create_shot_with_lineage(client, user_id)

    quality_resp = client.get(f"/api/v1/shots/{shot_id}/quality", headers=_auth_headers(user_id))
    assert quality_resp.status_code == 200
    payload = quality_resp.json()
    assert payload["shot_id"] == shot_id
    assert payload["quality_report"]["status"] in {"ready", "warning", "blocked"}
    assert payload["budget_estimate"]["estimated_duration_seconds"] == 4
    assert payload["budget_estimate"]["estimated_video_task"]["default_model_id"]

    refresh_resp = client.post(f"/api/v1/shots/{shot_id}/quality", headers=_auth_headers(user_id))
    assert refresh_resp.status_code == 200
    refreshed = refresh_resp.json()
    assert refreshed["quality_report"]["score"] <= 100
    assert refreshed["budget_estimate"]["estimated_total_tokens"] >= 16

    shot_resp = client.get(f"/api/v1/shots/{shot_id}", headers=_auth_headers(user_id))
    assert shot_resp.status_code == 200
    shot = shot_resp.json()
    assert shot["extra_data"]["quality_report"]["status"] in {"ready", "warning", "blocked"}
    assert shot["extra_data"]["budget_estimate"]["estimated_duration_seconds"] == 4


def test_shot_quality_batch_refreshes_reports_and_review_state(client: TestClient) -> None:
    user_id = f"shot-quality-batch-user-{uuid4()}"
    _novel_id, _chapter_id, _script_id, _storyboard_id, first_shot_id = _create_shot_with_lineage(client, user_id)
    _novel_id, _chapter_id, _script_id, _storyboard_id, second_shot_id = _create_shot_with_lineage(client, user_id)

    approve_resp = client.put(
        f"/api/v1/shots/{first_shot_id}/production-context",
        json={"review_state": "approved", "review_notes": "导演审核通过"},
        headers=_auth_headers(user_id),
    )
    assert approve_resp.status_code == 200

    batch_resp = client.post(
        "/api/v1/shots/quality/batch",
        json={"shot_ids": [first_shot_id, second_shot_id, "missing-shot-id", first_shot_id]},
        headers=_auth_headers(user_id),
    )
    assert batch_resp.status_code == 200
    payload = batch_resp.json()
    assert payload["total"] == 3
    assert payload["refreshed"] == 2
    assert payload["missing_ids"] == ["missing-shot-id"]

    reports = {item["shot_id"]: item["quality_report"] for item in payload["items"]}
    assert "完成镜头审核后再进入批量生成或真实渲染" not in reports[first_shot_id]["suggestions"]
    assert "完成镜头审核后再进入批量生成或真实渲染" in reports[second_shot_id]["suggestions"]


def test_comfyui_media_job_preserves_adapter_payload_and_production_context(client: TestClient) -> None:
    user_id = f"comfyui-job-user-{uuid4()}"
    novel_id, chapter_id, script_id, storyboard_id, shot_id = _create_shot_with_lineage(client, user_id)

    media_resp = client.post(
        "/api/v1/media/generate",
        json={
            "task_type": "comfyui_workflow",
            "media_type": "video",
            "prompt": "使用 ComfyUI 工作流生成动漫镜头",
            "provider_id": "comfyui",
            "shot_id": shot_id,
            "storyboard_id": storyboard_id,
            "script_id": script_id,
            "chapter_id": chapter_id,
            "novel_id": novel_id,
            "adapter_options": {"workflow_json": {"1": {"class_type": "CheckpointLoaderSimple"}}},
            "asset_version_locks": [{"asset_id": "logical-character-lock", "role": "character_front", "version": 1}],
            "keyframes": [{"time": 0, "role": "start"}, {"time": 4, "role": "end"}],
            "character_multiview_refs": [{"character": "沈砚", "front": "/static/dev/front.png"}],
            "lip_sync_mode": "provider",
            "review_required": True,
        },
        headers=_auth_headers(user_id),
    )
    assert media_resp.status_code == 200
    media_job = media_resp.json()
    assert media_job["task_type"] == "comfyui_workflow"
    assert media_job["status"] == "succeeded"
    assert media_job["extra_data"]["adapter_payload"]["workflow_json"]["1"]["class_type"] == "CheckpointLoaderSimple"
    assert media_job["extra_data"]["asset_version_locks"][0]["role"] == "character_front"
    assert media_job["extra_data"]["keyframes"][1]["role"] == "end"
    assert media_job["extra_data"]["review"]["state"] == "pending_review"


def test_workflow_cloud_render_returns_adapter_ready_without_claiming_output(client: TestClient) -> None:
    user_id = f"cloud-render-user-{uuid4()}"
    novel_id, chapter_id, script_id, storyboard_id, _shot_id = _create_shot_with_lineage(client, user_id)

    workflow_resp = client.post(
        "/api/v1/workflow/start",
        json={
            "title": "云渲染工作流",
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "script_id": script_id,
            "storyboard_id": storyboard_id,
        },
        headers=_auth_headers(user_id),
    )
    assert workflow_resp.status_code == 201
    workflow_id = workflow_resp.json()["workflow_id"]

    batch_resp = client.post(
        f"/api/v1/workflow/{workflow_id}/generate-media-batch",
        json={"strategy": "direct_av_first", "resolution": "720p"},
        headers=_auth_headers(user_id),
    )
    assert batch_resp.status_code == 200
    media_job_ids = batch_resp.json()["media_job_ids"]

    concat_resp = client.post(
        f"/api/v1/workflow/concatenate/{workflow_id}",
        json={"media_job_ids": media_job_ids, "title": "云渲染前置清单", "include_subtitles": True},
        headers=_auth_headers(user_id),
    )
    assert concat_resp.status_code == 200
    synthesis_job_id = concat_resp.json()["job_id"]

    render_resp = client.post(
        f"/api/v1/workflow/{workflow_id}/render",
        json={
            "synthesis_job_id": synthesis_job_id,
            "render_backend": "ffmpeg_cloud",
            "quality_profile": "review",
            "burn_subtitles": True,
        },
        headers=_auth_headers(user_id),
    )
    assert render_resp.status_code == 200
    render = render_resp.json()
    assert render["status"] == "adapter_ready"
    assert render["output_url"] is None
    assert render["render_manifest_url"].endswith(".json")
    assert render["srt_url"].endswith(".srt")
    assert render["timeline_url"].endswith("-timeline.json")

    status_resp = client.get(f"/api/v1/workflow/status/{workflow_id}", headers=_auth_headers(user_id))
    assert status_resp.status_code == 200
    synthesis_job = status_resp.json()["synthesis_jobs"][0]
    assert synthesis_job["output_url"] is None
    assert synthesis_job["extra_data"]["render_backend"] == "ffmpeg_cloud"
    assert synthesis_job["extra_data"]["render_status"] == "adapter_ready"
    assert synthesis_job["extra_data"]["cloud_render_payload"]["burn_subtitles"] is True
