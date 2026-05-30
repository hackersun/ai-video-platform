"""
Dashboard analytics aggregation tests.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from init_db import init_db
from main import app


@pytest.fixture(scope="module", autouse=True)
def _init_database() -> None:
    init_db()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DEV_MODE", "true")
    return TestClient(app)


def auth_headers(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


def test_dashboard_analytics_uses_database_records(client: TestClient) -> None:
    user_id = f"analytics-user-{uuid4()}"
    headers = auth_headers(user_id)

    novel_resp = client.post(
        "/api/v1/novels",
        json={
            "title": "正式统计小说",
            "description": "用于验证数据分析页正式数据库统计。",
            "genre": "玄幻",
            "status": "writing",
        },
        headers=headers,
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_resp = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "第一章",
            "content": "少年在雨夜进入城中。",
            "chapter_number": 1,
        },
        headers=headers,
    )
    assert chapter_resp.status_code == 201
    chapter_id = chapter_resp.json()["id"]

    character_resp = client.post(
        "/api/v1/characters",
        json={
            "novel_id": novel_id,
            "name": "沈砚",
            "description": "主角",
        },
        headers=headers,
    )
    assert character_resp.status_code == 201

    script_resp = client.post(
        "/api/v1/scripts",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "title": "第一章剧本",
            "content": "沈砚推门进入雨夜。",
            "status": "draft",
        },
        headers=headers,
    )
    assert script_resp.status_code == 201
    script_id = script_resp.json()["id"]

    storyboard_resp = client.post(
        "/api/v1/storyboards",
        json={
            "script_id": script_id,
            "title": "雨夜分镜",
            "description": "正式统计分镜",
        },
        headers=headers,
    )
    assert storyboard_resp.status_code == 201
    storyboard_id = storyboard_resp.json()["id"]

    shot_resp = client.post(
        "/api/v1/shots",
        json={
            "storyboard_id": storyboard_id,
            "shot_number": 1,
            "duration": 4,
            "prompt": "雨夜街道，少年推门。",
            "dialogue": "我回来了。",
        },
        headers=headers,
    )
    assert shot_resp.status_code == 201
    shot_id = shot_resp.json()["id"]

    asset_resp = client.post(
        "/api/v1/assets",
        json={
            "category": "prompt",
            "name": "统计验证资产",
            "asset_type": "text",
            "description": "用于验证资产统计。",
        },
        headers=headers,
    )
    assert asset_resp.status_code == 201

    video_resp = client.post(
        "/api/v1/video/generate",
        json={
            "prompt": "雨夜动漫镜头",
            "shot_id": shot_id,
            "storyboard_id": storyboard_id,
            "script_id": script_id,
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "title": "统计验证视频",
        },
        headers=headers,
    )
    assert video_resp.status_code == 200

    tts_resp = client.post(
        "/api/v1/tts/generate",
        json={
            "text_content": "我回来了。",
            "voice_model": "default",
            "speed": 1.0,
            "title": "统计验证语音",
            "shot_id": shot_id,
        },
        headers=headers,
    )
    assert tts_resp.status_code == 200

    media_resp = client.post(
        "/api/v1/media/generate",
        json={
            "task_type": "shot_audio_video",
            "media_type": "audio_video",
            "title": "统计验证直生音视频",
            "prompt": "雨夜动漫镜头，含对白。",
            "shot_id": shot_id,
            "storyboard_id": storyboard_id,
            "script_id": script_id,
            "novel_id": novel_id,
            "chapter_id": chapter_id,
        },
        headers=headers,
    )
    assert media_resp.status_code == 200

    analytics_resp = client.get("/api/v1/dashboard/analytics?days=14", headers=headers)
    assert analytics_resp.status_code == 200
    payload = analytics_resp.json()

    assert payload["data_source"] == "database"
    assert payload["is_mock"] is False
    assert payload["content_stats"]["novels_count"] >= 1
    assert payload["content_stats"]["chapters_count"] >= 1
    assert payload["content_stats"]["scripts_count"] >= 1
    assert payload["content_stats"]["storyboards_count"] >= 1
    assert payload["content_stats"]["shots_count"] >= 1
    assert payload["content_stats"]["characters_count"] >= 1
    assert payload["content_stats"]["assets_count"] >= 1

    assert payload["task_summary"]["total"] >= 3
    assert payload["task_summary"]["completed"] >= 3
    task_types = {item["type"]: item for item in payload["task_by_type"]}
    assert task_types["video"]["completed"] >= 1
    assert task_types["tts"]["completed"] >= 1
    assert task_types["media"]["completed"] >= 1
    assert len(payload["daily_series"]) == 14
    assert any(item["created_tasks"] >= 3 for item in payload["daily_series"])
    assert payload["recent_activities"]
