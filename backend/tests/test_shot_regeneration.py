from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import AsyncSessionLocal
from app.models import Shot, Workflow
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
    all_jobs = _video_jobs_for_workflow(workflow_id)
    assert len([job for job in all_jobs if job["id"] not in old_jobs]) == 1


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
        "generation_preflight": {
            "ready": True,
            "blocking_issue_count": 0,
            "issues": [],
        },
    }
    assert payload["shots"][0]["regeneration_count"] == 1
    assert payload["shots"][0]["latest_video_job_id"] == latest_video_id
    assert payload["shots"][0]["latest_tts_job_id"] == latest_tts_id
    assert old_video_id != latest_video_id
