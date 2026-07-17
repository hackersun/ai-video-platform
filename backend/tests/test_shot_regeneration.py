from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import AsyncSessionLocal
from app.models import Asset, MediaGenerationJob, Shot, Workflow
from app.models.tts_job import TTSJob
from app.models.video_job import VideoJob
from init_db import init_db
from main import app
from test_workflow_routes import (
    _auth_headers,
    _create_chapter,
    _create_novel,
    _insert_model_config,
)


@pytest.fixture(scope="module", autouse=True)
def _init_database() -> None:
    init_db()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DEV_MODE", "true")
    return TestClient(app)


def _create_workflow_with_shots(
    client: TestClient,
    user_id: str,
    *,
    shot_specs: list[dict],
    metadata: dict | None = None,
) -> tuple[str, list[str]]:
    novel_id = _create_novel(client, user_id)
    chapter_id = _create_chapter(client, user_id, novel_id, "第一章 镜头重生")
    script_resp = client.post(
        "/api/v1/scripts",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "title": f"Script {uuid4()}",
            "content": "孙剑和林澜在雨夜街道推进剧情。",
        },
        headers=_auth_headers(user_id),
    )
    assert script_resp.status_code == 201, script_resp.text
    storyboard_resp = client.post(
        "/api/v1/storyboards",
        json={
            "script_id": script_resp.json()["id"],
            "title": f"Storyboard {uuid4()}",
            "content": {"chapter_id": chapter_id},
        },
        headers=_auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201, storyboard_resp.text
    storyboard_id = storyboard_resp.json()["id"]

    shot_ids: list[str] = []
    for index, spec in enumerate(shot_specs, start=1):
        response = client.post(
            "/api/v1/shots",
            json={
                "storyboard_id": storyboard_id,
                "shot_number": index,
                "duration": spec.get("duration", 4),
                "prompt": spec.get("prompt", f"镜头 {index}"),
                "dialogue": spec.get("dialogue", f"镜头 {index} 台词"),
                "character_refs": spec.get("character_refs", []),
            },
            headers=_auth_headers(user_id),
        )
        assert response.status_code == 201, response.text
        shot_id = response.json()["id"]
        shot_ids.append(shot_id)
        if spec.get("extra_data"):
            _update_shot_extra(shot_id, spec["extra_data"])

    workflow_resp = client.post(
        "/api/v1/workflow/start",
        json={
            "title": f"Workflow {uuid4()}",
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "script_id": script_resp.json()["id"],
            "storyboard_id": storyboard_id,
        },
        headers=_auth_headers(user_id),
    )
    assert workflow_resp.status_code == 201, workflow_resp.text
    workflow_id = workflow_resp.json()["workflow_id"]
    if metadata:
        _update_workflow_metadata(workflow_id, metadata)
    return workflow_id, shot_ids


def _update_shot_extra(shot_id: str, extra_data: dict) -> None:
    async def _update() -> None:
        async with AsyncSessionLocal() as session:
            shot = await session.get(Shot, shot_id)
            assert shot is not None
            shot.extra_data = {**(shot.extra_data or {}), **extra_data}
            await session.commit()

    asyncio.run(_update())


def _update_workflow_metadata(workflow_id: str, metadata: dict) -> None:
    async def _update() -> None:
        async with AsyncSessionLocal() as session:
            workflow = await session.get(Workflow, workflow_id)
            assert workflow is not None
            workflow.metadata_ = {**(workflow.metadata_ or {}), **metadata}
            await session.commit()

    asyncio.run(_update())


def _insert_video_job_for_shot(
    *,
    user_id: str,
    workflow_id: str,
    shot_id: str,
    shot_number: int,
    status: str = "succeeded",
    video_url: str | None = None,
    extra_data: dict | None = None,
) -> str:
    job_id = f"video-{uuid4()}"

    async def _insert() -> None:
        async with AsyncSessionLocal() as session:
            job = VideoJob(
                id=job_id,
                user_id=user_id,
                workflow_id=workflow_id,
                task_id=f"task-{job_id}",
                title=f"镜头{shot_number} 视频",
                prompt=f"shot {shot_number}",
                model_id="test-video",
                model_name="Test Video",
                duration=4,
                status=status,
                progress=100 if status in {"succeeded", "completed"} else 0,
                video_url=video_url or (f"https://example.com/{job_id}.mp4" if status in {"succeeded", "completed"} else None),
                extra_data={
                    "workflow_id": workflow_id,
                    "shot_id": shot_id,
                    "shot_number": shot_number,
                    "lineage": {
                        "workflow_id": workflow_id,
                        "shot_id": shot_id,
                        "shot_number": shot_number,
                    },
                    **(extra_data or {}),
                },
            )
            session.add(job)
            workflow = await session.get(Workflow, workflow_id)
            assert workflow is not None
            workflow.video_job_ids = list(dict.fromkeys((workflow.video_job_ids or []) + [job_id]))
            shot = await session.get(Shot, shot_id)
            assert shot is not None
            shot.extra_data = {**(shot.extra_data or {}), "latest_video_job_id": job_id}
            if job.video_url:
                shot.video_url = job.video_url
                shot.video_status = status
            await session.commit()

    asyncio.run(_insert())
    return job_id


def _insert_media_job_for_shot(
    *,
    user_id: str,
    workflow_id: str,
    shot_id: str,
    shot_number: int,
    status: str = "succeeded",
    video_url: str | None = None,
) -> str:
    job_id = f"media-{uuid4()}"

    async def _insert() -> None:
        async with AsyncSessionLocal() as session:
            job = MediaGenerationJob(
                id=job_id,
                user_id=user_id,
                workflow_id=workflow_id,
                task_id=f"task-{job_id}",
                task_type="video_generation",
                media_type="video",
                title=f"镜头{shot_number} 统一媒体",
                prompt=f"shot {shot_number}",
                provider_id="volcano",
                model_id="test-media-video",
                model_name="Test Media Video",
                shot_id=shot_id,
                duration_seconds=4,
                resolution="720p",
                status=status,
                progress=100 if status in {"succeeded", "completed"} else 0,
                output_video_url=video_url or (f"https://example.com/{job_id}.mp4" if status in {"succeeded", "completed"} else None),
                extra_data={
                    "workflow_id": workflow_id,
                    "shot_id": shot_id,
                    "shot_number": shot_number,
                },
                is_active=True,
            )
            session.add(job)
            workflow = await session.get(Workflow, workflow_id)
            assert workflow is not None
            workflow.metadata_ = {
                **(workflow.metadata_ or {}),
                "media_job_ids": list(dict.fromkeys(((workflow.metadata_ or {}).get("media_job_ids") or []) + [job_id])),
            }
            shot = await session.get(Shot, shot_id)
            assert shot is not None
            shot.extra_data = {**(shot.extra_data or {}), "latest_media_job_id": job_id}
            if job.output_video_url:
                shot.video_url = job.output_video_url
                shot.video_status = status
            await session.commit()

    asyncio.run(_insert())
    return job_id


def _insert_tts_job_for_shot(
    *,
    user_id: str,
    workflow_id: str,
    shot_id: str,
    shot_number: int,
    status: str = "succeeded",
    text: str = "测试台词",
    extra_data: dict | None = None,
) -> str:
    job_id = f"tts-{uuid4()}"

    async def _insert() -> None:
        async with AsyncSessionLocal() as session:
            job = TTSJob(
                id=job_id,
                user_id=user_id,
                workflow_id=workflow_id,
                task_id=f"task-{job_id}",
                title=f"镜头{shot_number} 配音",
                text=text,
                model_id="test-tts",
                model_name="Test TTS",
                voice="test-voice",
                status=status,
                progress=100 if status in {"succeeded", "completed"} else 0,
                audio_url=f"https://example.com/{job_id}.mp3" if status in {"succeeded", "completed"} else None,
                duration_seconds=2.0 if status in {"succeeded", "completed"} else None,
                shot_id=shot_id,
                extra_data={
                    "workflow_id": workflow_id,
                    "shot_id": shot_id,
                    "shot_number": shot_number,
                    **(extra_data or {}),
                },
            )
            session.add(job)
            workflow = await session.get(Workflow, workflow_id)
            assert workflow is not None
            workflow.tts_job_ids = list(dict.fromkeys((workflow.tts_job_ids or []) + [job_id]))
            shot = await session.get(Shot, shot_id)
            assert shot is not None
            shot.extra_data = {**(shot.extra_data or {}), "latest_tts_job_id": job_id}
            if job.audio_url:
                shot.audio_url = job.audio_url
                shot.audio_status = status
            await session.commit()

    asyncio.run(_insert())
    return job_id


def _get_video_job(job_id: str) -> dict:
    async def _get() -> dict:
        async with AsyncSessionLocal() as session:
            job = await session.get(VideoJob, job_id)
            assert job is not None
            return {
                "id": job.id,
                "status": job.status,
                "video_url": job.video_url,
                "extra_data": job.extra_data or {},
            }

    return asyncio.run(_get())


def _get_tts_job(job_id: str) -> dict:
    async def _get() -> dict:
        async with AsyncSessionLocal() as session:
            job = await session.get(TTSJob, job_id)
            assert job is not None
            return {
                "id": job.id,
                "status": job.status,
                "audio_url": job.audio_url,
                "extra_data": job.extra_data or {},
            }

    return asyncio.run(_get())


def _insert_front_reference_asset(user_id: str, entity_id: str) -> str:
    asset_id = f"asset-{uuid4()}"

    async def _insert() -> None:
        async with AsyncSessionLocal() as session:
            session.add(
                Asset(
                    id=asset_id,
                    user_id=user_id,
                    category="character",
                    asset_type="image",
                    entity_id=entity_id,
                    entity_type="character",
                    name="孙剑正面定稿",
                    url="https://cdn.example.com/sunjian-front.png",
                    is_active=True,
                    is_locked=True,
                    is_final=True,
                    generation_params={"view_key": "front"},
                )
            )
            await session.commit()

    asyncio.run(_insert())
    return asset_id


def _get_asset_generation_params(asset_id: str) -> dict:
    async def _get() -> dict:
        async with AsyncSessionLocal() as session:
            asset = await session.get(Asset, asset_id)
            assert asset is not None
            return asset.generation_params or {}

    return asyncio.run(_get())


def _video_jobs_for_workflow(workflow_id: str) -> list[dict]:
    async def _get() -> list[dict]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                VideoJob.__table__.select().where(VideoJob.workflow_id == workflow_id)
            )
            return [dict(row._mapping) for row in result.fetchall()]

    return asyncio.run(_get())


def _insert_dev_video_model_config(user_id: str) -> str:
    return _insert_model_config(
        user_id=user_id,
        provider_id="volcano",
        model_id=f"regen-video-model-{uuid4()}",
        api_model_id="doubao-seedance-2-0-fast-260128",
        model_type="video",
        capabilities=["text-to-video", "image-to-video"],
        api_key="",
    )


def test_regenerate_only_failed_shots(client: TestClient) -> None:
    user_id = uuid4().hex
    model_config_id = _insert_dev_video_model_config(user_id)
    workflow_id, shot_ids = _create_workflow_with_shots(
        client,
        user_id,
        shot_specs=[
            {"prompt": "成功镜头 1"},
            {"prompt": "失败镜头"},
            {"prompt": "成功镜头 3"},
        ],
    )
    old_jobs = [
        _insert_video_job_for_shot(user_id=user_id, workflow_id=workflow_id, shot_id=shot_ids[0], shot_number=1),
        _insert_video_job_for_shot(user_id=user_id, workflow_id=workflow_id, shot_id=shot_ids[1], shot_number=2, status="failed"),
        _insert_video_job_for_shot(user_id=user_id, workflow_id=workflow_id, shot_id=shot_ids[2], shot_number=3),
    ]

    response = client.post(
        f"/api/v1/workflow/{workflow_id}/regenerate-shots",
        json={
            "shot_ids": shot_ids,
            "filter": "failed",
            "model_config_id": model_config_id,
            "audio_mode": "none",
        },
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["regenerated_shot_ids"] == [shot_ids[1]]
    assert payload["created_count"] == 1
    assert len(payload["video_job_ids"]) == 1
    new_video_id = payload["video_job_ids"][0]
    assert payload["concatenate_video_job_ids"] == [old_jobs[0], new_video_id, old_jobs[2]]
    assert payload["concatenate_tts_job_ids"] == []
    assert payload["concatenate_media_job_ids"] == []
    all_jobs = _video_jobs_for_workflow(workflow_id)
    assert len([job for job in all_jobs if job["id"] not in old_jobs]) == 1


def test_regenerate_failed_shot_keeps_media_jobs_for_concatenate(client: TestClient) -> None:
    user_id = uuid4().hex
    model_config_id = _insert_dev_video_model_config(user_id)
    workflow_id, shot_ids = _create_workflow_with_shots(
        client,
        user_id,
        shot_specs=[
            {"prompt": "已有统一媒体任务的成功镜头"},
            {"prompt": "需要重生的失败镜头"},
        ],
    )
    existing_media_id = _insert_media_job_for_shot(
        user_id=user_id,
        workflow_id=workflow_id,
        shot_id=shot_ids[0],
        shot_number=1,
    )
    failed_video_id = _insert_video_job_for_shot(
        user_id=user_id,
        workflow_id=workflow_id,
        shot_id=shot_ids[1],
        shot_number=2,
        status="failed",
    )

    response = client.post(
        f"/api/v1/workflow/{workflow_id}/regenerate-shots",
        json={
            "shot_ids": shot_ids,
            "filter": "failed",
            "model_config_id": model_config_id,
            "audio_mode": "none",
        },
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["regenerated_shot_ids"] == [shot_ids[1]]
    assert payload["created_count"] == 1
    assert len(payload["video_job_ids"]) == 1
    new_video_id = payload["video_job_ids"][0]
    assert new_video_id != failed_video_id
    assert payload["concatenate_media_job_ids"] == [existing_media_id]
    assert payload["concatenate_video_job_ids"] == [new_video_id]
    assert payload["concatenate_tts_job_ids"] == []


def test_regenerate_by_character(client: TestClient) -> None:
    user_id = uuid4().hex
    model_config_id = _insert_dev_video_model_config(user_id)
    workflow_id, shot_ids = _create_workflow_with_shots(
        client,
        user_id,
        shot_specs=[
            {"prompt": "孙剑拔剑", "character_refs": [{"name": "孙剑"}]},
            {"prompt": "林澜望向窗外", "character_refs": [{"name": "林澜"}]},
        ],
    )
    _insert_video_job_for_shot(user_id=user_id, workflow_id=workflow_id, shot_id=shot_ids[0], shot_number=1)
    _insert_video_job_for_shot(user_id=user_id, workflow_id=workflow_id, shot_id=shot_ids[1], shot_number=2)

    response = client.post(
        f"/api/v1/workflow/{workflow_id}/regenerate-shots",
        json={
            "shot_ids": shot_ids,
            "filter": "all_selected",
            "character_name": "孙剑",
            "model_config_id": model_config_id,
            "audio_mode": "none",
        },
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["regenerated_shot_ids"] == [shot_ids[0]]
    new_job = _get_video_job(payload["video_job_ids"][0])
    assert new_job["extra_data"]["shot_id"] == shot_ids[0]


def test_regeneration_marks_superseded_and_concatenate_uses_latest(client: TestClient) -> None:
    user_id = uuid4().hex
    model_config_id = _insert_dev_video_model_config(user_id)
    workflow_id, shot_ids = _create_workflow_with_shots(
        client,
        user_id,
        shot_specs=[{"prompt": "孙剑雨夜拔剑", "dialogue": "孙剑：继续前进。"}],
    )
    old_video_id = _insert_video_job_for_shot(
        user_id=user_id,
        workflow_id=workflow_id,
        shot_id=shot_ids[0],
        shot_number=1,
        video_url="https://example.com/old-shot.mp4",
    )
    old_tts_id = _insert_tts_job_for_shot(
        user_id=user_id,
        workflow_id=workflow_id,
        shot_id=shot_ids[0],
        shot_number=1,
    )

    response = client.post(
        f"/api/v1/workflow/{workflow_id}/regenerate-shots",
        json={
            "shot_ids": shot_ids,
            "filter": "all_selected",
            "model_config_id": model_config_id,
            "audio_mode": "model_audio",
        },
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    new_video_id = payload["video_job_ids"][0]
    assert payload["concatenate_video_job_ids"] == [new_video_id]
    assert payload["concatenate_media_job_ids"] == []
    assert _get_video_job(old_video_id)["extra_data"]["superseded_by_regeneration"] is True
    assert _get_tts_job(old_tts_id)["extra_data"]["superseded_by_regeneration"] is True

    concat_resp = client.post(
        f"/api/v1/workflow/concatenate/{workflow_id}",
        json={
            "video_job_ids": [old_video_id, new_video_id],
            "tts_job_ids": payload["tts_job_ids"],
            "include_subtitles": True,
        },
        headers=_auth_headers(user_id),
    )
    assert concat_resp.status_code == 200, concat_resp.text
    manifest_resp = client.get(concat_resp.json()["manifest_url"])
    assert manifest_resp.status_code == 200
    manifest = manifest_resp.json()
    assert manifest["segment_count"] == 1
    assert manifest["segments"][0]["video"]["job_id"] == new_video_id
    assert manifest["segments"][0]["video"]["url"] != "https://example.com/old-shot.mp4"


def test_concatenate_uses_ready_success_job_when_same_shot_has_newer_running_job(client: TestClient) -> None:
    user_id = uuid4().hex
    workflow_id, shot_ids = _create_workflow_with_shots(
        client,
        user_id,
        shot_specs=[{"prompt": "云灯集市远景", "dialogue": "旁白：集市亮起来。"}],
    )
    succeeded_video_id = _insert_video_job_for_shot(
        user_id=user_id,
        workflow_id=workflow_id,
        shot_id=shot_ids[0],
        shot_number=1,
        status="succeeded",
        video_url="https://example.com/succeeded-shot.mp4",
    )
    running_video_id = _insert_video_job_for_shot(
        user_id=user_id,
        workflow_id=workflow_id,
        shot_id=shot_ids[0],
        shot_number=1,
        status="running",
    )

    concat_resp = client.post(
        f"/api/v1/workflow/concatenate/{workflow_id}",
        json={
            "video_job_ids": [succeeded_video_id, running_video_id],
            "include_subtitles": False,
        },
        headers=_auth_headers(user_id),
    )

    assert concat_resp.status_code == 200, concat_resp.text
    manifest_resp = client.get(concat_resp.json()["manifest_url"])
    assert manifest_resp.status_code == 200
    manifest = manifest_resp.json()
    assert [segment["video"]["job_id"] for segment in manifest["segments"]] == [succeeded_video_id]


def test_concatenate_uses_latest_ready_tts_for_same_shot(client: TestClient) -> None:
    user_id = uuid4().hex
    workflow_id, shot_ids = _create_workflow_with_shots(
        client,
        user_id,
        shot_specs=[{"prompt": "云灯集市近景", "dialogue": "旁白：集市亮起来。"}],
    )
    video_id = _insert_video_job_for_shot(
        user_id=user_id,
        workflow_id=workflow_id,
        shot_id=shot_ids[0],
        shot_number=1,
        status="succeeded",
    )
    old_tts_id = _insert_tts_job_for_shot(
        user_id=user_id,
        workflow_id=workflow_id,
        shot_id=shot_ids[0],
        shot_number=1,
        text="旧配音台词",
    )
    new_tts_id = _insert_tts_job_for_shot(
        user_id=user_id,
        workflow_id=workflow_id,
        shot_id=shot_ids[0],
        shot_number=1,
        text="新配音台词",
    )

    concat_resp = client.post(
        f"/api/v1/workflow/concatenate/{workflow_id}",
        json={
            "video_job_ids": [video_id],
            "tts_job_ids": [old_tts_id, new_tts_id],
            "include_subtitles": True,
        },
        headers=_auth_headers(user_id),
    )

    assert concat_resp.status_code == 200, concat_resp.text
    manifest_resp = client.get(concat_resp.json()["manifest_url"])
    assert manifest_resp.status_code == 200
    manifest = manifest_resp.json()
    segment = manifest["segments"][0]
    assert segment["audio"]["job_id"] == new_tts_id
    assert segment["audio"]["text"] == "新配音台词"
    assert segment["subtitle"]["text"] == "新配音台词"


def test_shot_review_aggregates_latest_evidence(client: TestClient) -> None:
    user_id = uuid4().hex
    latest_render_artifacts = {
        "output_url": "https://example.com/render/output.mp4",
        "manifest_url": "https://example.com/render/manifest.json",
        "preview_url": "https://example.com/render/preview.mp4",
        "srt_url": "https://example.com/render/subtitles.srt",
        "timeline_url": "https://example.com/render/timeline.json",
        "render_manifest_url": "https://example.com/render/render-manifest.json",
    }
    workflow_id, shot_ids = _create_workflow_with_shots(
        client,
        user_id,
        shot_specs=[
            {
                "prompt": "孙剑审阅镜头",
                "dialogue": "孙剑：证据齐了。",
                "character_refs": [{"name": "孙剑"}],
                "extra_data": {"subtitle_text": "孙剑：证据齐了。"},
            }
        ],
        metadata={"latest_render_artifacts": latest_render_artifacts},
    )
    old_video_id = _insert_video_job_for_shot(
        user_id=user_id,
        workflow_id=workflow_id,
        shot_id=shot_ids[0],
        shot_number=1,
        extra_data={"superseded_by_regeneration": True},
    )
    latest_video_id = _insert_video_job_for_shot(
        user_id=user_id,
        workflow_id=workflow_id,
        shot_id=shot_ids[0],
        shot_number=1,
        video_url="https://example.com/latest-shot.mp4",
        extra_data={
            "strategy_routing": "strategy",
            "reference_package_mode": "multi_reference",
            "reference_package": {
                "mode": "multimodal",
                "image_count": 3,
                "video_count": 1,
                "dropped": [],
            },
            "generation_preflight": {
                "ready": True,
                "blocking_issue_count": 0,
                "issues": [],
            },
        },
    )
    latest_tts_id = _insert_tts_job_for_shot(
        user_id=user_id,
        workflow_id=workflow_id,
        shot_id=shot_ids[0],
        shot_number=1,
        text="孙剑：证据齐了。",
    )

    response = client.get(
        f"/api/v1/workflow/{workflow_id}/shot-review",
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["workflow_id"] == workflow_id
    assert payload["latest_render_artifacts"] == latest_render_artifacts
    assert payload["shots"][0]["shot_id"] == shot_ids[0]
    assert payload["shots"][0]["video_url"] == "https://example.com/latest-shot.mp4"
    assert payload["shots"][0]["subtitle_text"] == "孙剑：证据齐了。"
    assert payload["shots"][0]["character_names"] == ["孙剑"]
    assert payload["shots"][0]["evidence"] == {
        "strategy_routing": "strategy",
        "reference_package_mode": "multi_reference",
        "reference_package": {
            "mode": "multimodal",
            "image_count": 3,
            "video_count": 1,
            "dropped": [],
        },
        "generation_preflight": {
            "ready": True,
            "blocking_issue_count": 0,
            "issues": [],
        },
        "visual_consistency": None,
    }
    assert payload["shots"][0]["regeneration_count"] == 1
    assert payload["shots"][0]["latest_video_job_id"] == latest_video_id
    assert payload["shots"][0]["latest_tts_job_id"] == latest_tts_id
    assert old_video_id != latest_video_id


def test_shot_review_prioritizes_low_visual_consistency_scores(client: TestClient) -> None:
    user_id = uuid4().hex
    workflow_id, shot_ids = _create_workflow_with_shots(
        client,
        user_id,
        shot_specs=[
            {
                "prompt": "孙剑稳定镜头",
                "dialogue": "孙剑：我没变。",
                "character_refs": [{"name": "孙剑"}],
                "extra_data": {
                    "quality_report": {
                        "status": "ready",
                        "visual_consistency_score": 94,
                        "visual_consistency": {
                            "score": 94,
                            "status": "passed",
                            "reference_asset_id": "asset-front-high",
                            "frame_count": 1,
                            "blocking": False,
                        },
                    }
                },
            },
            {
                "prompt": "孙剑疑似漂移镜头",
                "dialogue": "孙剑：这个镜头要先看。",
                "character_refs": [{"name": "孙剑"}],
                "extra_data": {
                    "quality_report": {
                        "status": "warning",
                        "visual_consistency_score": 62,
                        "visual_consistency": {
                            "score": 62,
                            "status": "needs_review",
                            "reference_asset_id": "asset-front-low",
                            "frame_count": 2,
                            "blocking": False,
                        },
                    }
                },
            },
        ],
    )
    _insert_video_job_for_shot(
        user_id=user_id,
        workflow_id=workflow_id,
        shot_id=shot_ids[0],
        shot_number=1,
        video_url="https://example.com/high.mp4",
    )
    _insert_video_job_for_shot(
        user_id=user_id,
        workflow_id=workflow_id,
        shot_id=shot_ids[1],
        shot_number=2,
        video_url="https://example.com/low.mp4",
    )

    response = client.get(
        f"/api/v1/workflow/{workflow_id}/shot-review",
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    shots = response.json()["shots"]
    assert [item["shot_id"] for item in shots] == [shot_ids[1], shot_ids[0]]
    assert shots[0]["visual_consistency_score"] == 62
    assert shots[0]["evidence"]["visual_consistency"] == {
        "score": 62,
        "status": "needs_review",
        "reference_asset_id": "asset-front-low",
        "frame_count": 2,
        "blocking": False,
    }
    assert shots[0]["quality_report"]["visual_consistency_score"] == 62


def test_workflow_visual_consistency_endpoint_records_latest_video_evidence(client: TestClient) -> None:
    user_id = uuid4().hex
    workflow_id, shot_ids = _create_workflow_with_shots(
        client,
        user_id,
        shot_specs=[
            {
                "prompt": "孙剑终稿镜头",
                "dialogue": "孙剑：检查我的脸。",
                "character_refs": [{"entity_id": "char-main", "name": "孙剑"}],
            }
        ],
    )
    asset_id = _insert_front_reference_asset(user_id, "char-main")
    video_id = _insert_video_job_for_shot(
        user_id=user_id,
        workflow_id=workflow_id,
        shot_id=shot_ids[0],
        shot_number=1,
        video_url="https://example.com/final-shot.mp4",
    )

    response = client.post(
        f"/api/v1/workflow/{workflow_id}/visual-consistency",
        json={"shot_ids": [shot_ids[0]], "extract_frames": False},
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["workflow_id"] == workflow_id
    assert payload["checked_count"] == 1
    assert payload["skipped"] == []

    review_resp = client.get(
        f"/api/v1/workflow/{workflow_id}/shot-review",
        headers=_auth_headers(user_id),
    )
    assert review_resp.status_code == 200, review_resp.text
    item = review_resp.json()["shots"][0]
    assert item["visual_consistency_score"] == 72
    assert item["evidence"]["visual_consistency"]["reference_asset_id"] == asset_id
    assert item["evidence"]["visual_consistency"]["blocking"] is False

    job = _get_video_job(video_id)
    assert job["extra_data"]["visual_consistency"]["score"] == 72
    asset_params = _get_asset_generation_params(asset_id)
    assert asset_params["visual_consistency_history"][0]["reference_asset_id"] == asset_id
