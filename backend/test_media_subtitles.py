from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from uuid import uuid4

from app.core.database import SyncSessionLocal
from app.models import MediaGenerationJob
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


def _create_media_job(user_id: str, *, status: str = "pending") -> str:
    job_id = str(uuid4())
    db = SyncSessionLocal()
    try:
        db.add(
            MediaGenerationJob(
                id=job_id,
                user_id=user_id,
                task_id=f"test-media-{job_id}",
                task_type="shot_audio_video",
                media_type="audio_video",
                title="待维护媒体任务",
                prompt="用于验证任务中心取消和归档",
                status=status,
                progress=10,
                is_active=True,
            )
        )
        db.commit()
    finally:
        db.close()
    return job_id


def _create_shot_with_lineage(client: TestClient, user_id: str) -> tuple[str, str, str, str, str]:
    novel_resp = client.post(
        "/api/v1/novels",
        json={"title": "直生音视频小说", "description": "角色在雨夜中行动"},
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
            "content": "沈砚在雨夜街道发现线索。",
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
            "content": "沈砚：雨声不对。",
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
            "prompt": "雨夜街道，沈砚停下脚步，镜头慢推。",
            "dialogue": "雨声不对。",
            "visual_description": "雨夜街道霓虹反光。",
        },
        headers=_auth_headers(user_id),
    )
    assert shot_resp.status_code == 201
    return novel_id, chapter_id, script_id, storyboard_id, shot_resp.json()["id"]


def test_direct_audio_video_generation_creates_subtitle_track_and_exports_srt(client: TestClient) -> None:
    user_id = "media-subtitle-user"
    novel_id, chapter_id, script_id, storyboard_id, shot_id = _create_shot_with_lineage(client, user_id)

    media_resp = client.post(
        "/api/v1/media/generate",
        json={
            "task_type": "shot_audio_video",
            "media_type": "audio_video",
            "prompt": "保持角色、雨夜环境和字幕一致，生成带对白音频的动漫镜头。",
            "shot_id": shot_id,
            "storyboard_id": storyboard_id,
            "script_id": script_id,
            "chapter_id": chapter_id,
            "novel_id": novel_id,
            "duration": 4,
            "resolution": "720p",
        },
        headers=_auth_headers(user_id),
    )
    assert media_resp.status_code == 200
    media_job = media_resp.json()
    assert media_job["task_type"] == "shot_audio_video"
    assert media_job["media_type"] == "audio_video"
    assert media_job["status"] == "succeeded"
    assert media_job["output_video_url"].endswith(".mp4")
    assert media_job["output_audio_url"].endswith(".mp3")
    assert media_job["shot_id"] == shot_id
    assert media_job["novel_id"] == novel_id
    assert media_job["subtitle_track_id"]

    track_resp = client.get(
        f"/api/v1/subtitles/tracks/{media_job['subtitle_track_id']}",
        headers=_auth_headers(user_id),
    )
    assert track_resp.status_code == 200
    track = track_resp.json()
    assert track["source"] == "direct_av_model"
    assert track["segments"][0]["text"] == "雨声不对。"

    export_resp = client.post(
        f"/api/v1/subtitles/tracks/{track['id']}/export",
        json={"format": "srt"},
        headers=_auth_headers(user_id),
    )
    assert export_resp.status_code == 200
    assert export_resp.json()["url"].endswith(".srt")

    list_resp = client.get(
        f"/api/v1/media/jobs?task_type=shot_audio_video&shot_id={shot_id}",
        headers=_auth_headers(user_id),
    )
    assert list_resp.status_code == 200
    assert any(item["id"] == media_job["id"] for item in list_resp.json())

    script_filter_resp = client.get(
        f"/api/v1/media/jobs?task_type=shot_audio_video&script_id={script_id}",
        headers=_auth_headers(user_id),
    )
    assert script_filter_resp.status_code == 200
    assert any(item["id"] == media_job["id"] and item["script_id"] == script_id for item in script_filter_resp.json())


def test_media_job_cancel_and_archive_management(client: TestClient) -> None:
    user_id = "media-job-manage-user"
    job_id = _create_media_job(user_id)

    cancel_resp = client.post(f"/api/v1/media/jobs/{job_id}/cancel", headers=_auth_headers(user_id))
    assert cancel_resp.status_code == 200
    cancelled = cancel_resp.json()
    assert cancelled["status"] == "cancelled"
    assert cancelled["error_message"] == "任务已由用户取消"

    list_resp = client.get("/api/v1/media/jobs", headers=_auth_headers(user_id))
    assert list_resp.status_code == 200
    assert any(item["id"] == job_id for item in list_resp.json())

    delete_resp = client.delete(f"/api/v1/media/jobs/{job_id}", headers=_auth_headers(user_id))
    assert delete_resp.status_code == 200
    assert delete_resp.json()["job_id"] == job_id

    archived_list = client.get("/api/v1/media/jobs", headers=_auth_headers(user_id))
    assert archived_list.status_code == 200
    assert all(item["id"] != job_id for item in archived_list.json())

    detail_resp = client.get(f"/api/v1/media/jobs/{job_id}", headers=_auth_headers(user_id))
    assert detail_resp.status_code == 200
    assert detail_resp.json()["status"] == "archived"


def test_completed_media_job_cannot_be_cancelled(client: TestClient) -> None:
    user_id = "media-job-completed-user"
    job_id = _create_media_job(user_id, status="succeeded")

    cancel_resp = client.post(f"/api/v1/media/jobs/{job_id}/cancel", headers=_auth_headers(user_id))
    assert cancel_resp.status_code == 400


def test_subtitle_segment_can_be_edited(client: TestClient) -> None:
    user_id = "subtitle-edit-user"
    _, _, _, _, shot_id = _create_shot_with_lineage(client, user_id)
    track_resp = client.post(
        "/api/v1/subtitles/from-shot",
        json={"shot_id": shot_id, "duration_seconds": 4},
        headers=_auth_headers(user_id),
    )
    assert track_resp.status_code == 201
    track = track_resp.json()
    segment_id = track["segments"][0]["id"]

    update_resp = client.put(
        f"/api/v1/subtitles/tracks/{track['id']}/segments/{segment_id}",
        json={"text": "雨声有问题。", "start_seconds": 0.2, "end_seconds": 3.6, "review_status": "approved"},
        headers=_auth_headers(user_id),
    )
    assert update_resp.status_code == 200
    segment = update_resp.json()
    assert segment["text"] == "雨声有问题。"
    assert segment["review_status"] == "approved"
    assert segment["start_seconds"] == 0.2


def test_workflow_media_batch_generates_direct_audio_video_jobs(client: TestClient) -> None:
    user_id = "workflow-media-batch-user"
    novel_id, chapter_id, script_id, storyboard_id, shot_id = _create_shot_with_lineage(client, user_id)
    second_shot = client.post(
        "/api/v1/shots",
        json={
            "storyboard_id": storyboard_id,
            "shot_number": 2,
            "duration": 4,
            "prompt": "沈砚转身看向巷口，铜铃声变得急促。",
            "dialogue": "有人来了。",
            "visual_description": "镜头横移到巷口黑影。",
        },
        headers=_auth_headers(user_id),
    )
    assert second_shot.status_code == 201

    workflow_resp = client.post(
        "/api/v1/workflow/start",
        json={
            "title": "直生音视频工作流",
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
    batch = batch_resp.json()
    assert batch["created_count"] == 2
    assert len(batch["media_job_ids"]) == 2
    assert len(batch["subtitle_track_ids"]) == 2

    media_jobs = client.get(
        f"/api/v1/media/jobs?workflow_id={workflow_id}&task_type=shot_audio_video",
        headers=_auth_headers(user_id),
    )
    assert media_jobs.status_code == 200
    assert len(media_jobs.json()) == 2
    assert all(item["output_video_url"] for item in media_jobs.json())

    status_resp = client.get(f"/api/v1/workflow/status/{workflow_id}", headers=_auth_headers(user_id))
    assert status_resp.status_code == 200
    workflow_status = status_resp.json()
    assert len(workflow_status["media_jobs"]) == 2
    assert len(workflow_status["subtitle_tracks"]) == 2

    concat_resp = client.post(
        f"/api/v1/workflow/concatenate/{workflow_id}",
        json={
            "media_job_ids": batch["media_job_ids"],
            "title": "直生音视频连续成片",
            "include_subtitles": True,
            "subtitle_mode": "dialogue",
        },
        headers=_auth_headers(user_id),
    )
    assert concat_resp.status_code == 200
    concat = concat_resp.json()
    assert concat["segment_count"] == 2
    assert concat["manifest_url"].startswith("/static/exports/")

    first_shot = client.get(f"/api/v1/shots/{shot_id}", headers=_auth_headers(user_id))
    assert first_shot.status_code == 200
    assert first_shot.json()["video_status"] == "succeeded"
    assert first_shot.json()["audio_status"] == "succeeded"
