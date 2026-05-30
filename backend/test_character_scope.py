"""
Tests for novel-scoped character management.
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


def _create_novel(client: TestClient, user_id: str, title: str) -> str:
    response = client.post(
        "/api/v1/novels",
        json={"title": title, "description": f"{title} description"},
        headers=auth_headers(user_id),
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_chapter(client: TestClient, user_id: str, novel_id: str, content: str) -> str:
    response = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "第一章",
            "chapter_number": 1,
            "content": content,
        },
        headers=auth_headers(user_id),
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_characters_are_filtered_by_novel_scope(client: TestClient) -> None:
    user_id = f"character-scope-user-{uuid4()}"
    novel_a = _create_novel(client, user_id, "青灯卷")
    novel_b = _create_novel(client, user_id, "赤霜卷")

    char_a_resp = client.post(
        "/api/v1/characters",
        json={"novel_id": novel_a, "name": "沈砚", "description": "青灯卷主角"},
        headers=auth_headers(user_id),
    )
    assert char_a_resp.status_code == 201
    char_a = char_a_resp.json()
    assert char_a["novel_id"] == novel_a

    char_b_resp = client.post(
        "/api/v1/characters",
        json={"novel_id": novel_b, "name": "沈砚", "description": "赤霜卷同名角色"},
        headers=auth_headers(user_id),
    )
    assert char_b_resp.status_code == 201
    char_b = char_b_resp.json()
    assert char_b["novel_id"] == novel_b

    global_resp = client.post(
        "/api/v1/characters",
        json={"name": "旁白", "description": "全局旁白"},
        headers=auth_headers(user_id),
    )
    assert global_resp.status_code == 201

    scoped_resp = client.get(
        f"/api/v1/characters?novel_id={novel_a}",
        headers=auth_headers(user_id),
    )
    assert scoped_resp.status_code == 200
    names = [item["description"] for item in scoped_resp.json()]
    assert "青灯卷主角" in names
    assert "赤霜卷同名角色" not in names
    assert "全局旁白" not in names

    scoped_with_global_resp = client.get(
        f"/api/v1/characters?novel_id={novel_a}&include_global=true",
        headers=auth_headers(user_id),
    )
    assert scoped_with_global_resp.status_code == 200
    descriptions = [item["description"] for item in scoped_with_global_resp.json()]
    assert "青灯卷主角" in descriptions
    assert "全局旁白" in descriptions
    assert "赤霜卷同名角色" not in descriptions


def test_shot_entity_context_prefers_same_novel_character(client: TestClient) -> None:
    user_id = f"character-context-user-{uuid4()}"
    novel_a = _create_novel(client, user_id, "北境旧案")
    novel_b = _create_novel(client, user_id, "南城旧案")
    _create_chapter(
        client,
        user_id,
        novel_a,
        "角色：沈砚。场景：北境档案室。沈砚在北境档案室发现线索。",
    )

    wrong_resp = client.post(
        "/api/v1/characters",
        json={"novel_id": novel_b, "name": "沈砚", "appearance": "红衣短发"},
        headers=auth_headers(user_id),
    )
    assert wrong_resp.status_code == 201

    right_resp = client.post(
        "/api/v1/characters",
        json={"novel_id": novel_a, "name": "沈砚", "appearance": "青衣长发"},
        headers=auth_headers(user_id),
    )
    assert right_resp.status_code == 201

    storyboard_resp = client.post(
        "/api/v1/storyboards/generate-smart",
        json={
            "novel_id": novel_a,
            "shot_count": 2,
            "style": "anime",
            "use_ai_refine": False,
        },
        headers=auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201
    shot = storyboard_resp.json()["shots"][0]
    character_refs = shot["extra_data"]["entity_refs"]["characters"]
    assert character_refs
    matched = next(ref for ref in character_refs if ref["name"] == "沈砚")
    assert matched["character_id"] == right_resp.json()["id"]
    assert matched["appearance"] == "青衣长发"


def test_tts_multi_character_voice_uses_same_novel_character(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = f"character-tts-user-{uuid4()}"
    novel_a = _create_novel(client, user_id, "云门案")
    novel_b = _create_novel(client, user_id, "江城案")

    wrong_resp = client.post(
        "/api/v1/characters",
        json={"novel_id": novel_b, "name": "沈砚", "voice": "wrong-voice"},
        headers=auth_headers(user_id),
    )
    assert wrong_resp.status_code == 201

    right_resp = client.post(
        "/api/v1/characters",
        json={"novel_id": novel_a, "name": "沈砚", "voice": "right-voice"},
        headers=auth_headers(user_id),
    )
    assert right_resp.status_code == 201

    used_voices: list[str] = []

    async def _fake_text_to_speech(self, *args, **kwargs):
        used_voices.append(kwargs.get("voice_id") or kwargs.get("voice"))
        return {
            "task_id": f"tts-task-{len(used_voices)}",
            "status": "succeeded",
            "audio_url": f"https://example.com/audio-{len(used_voices)}.mp3",
            "duration": 1.0,
        }

    monkeypatch.setattr(
        "app.services.minimax_service.MiniMaxService.text_to_speech",
        _fake_text_to_speech,
    )

    response = client.post(
        "/api/v1/tts/generate",
        json={
            "novel_id": novel_a,
            "text_content": "沈砚: 我发现线索了\n旁白: 风声穿过云门",
            "voice_model": "default-voice",
            "api_provider": "minimax",
            "api_key": "test-key",
            "use_consistency_context": False,
        },
        headers=auth_headers(user_id),
    )

    assert response.status_code == 200
    assert used_voices[0] == "right-voice"
    assert "wrong-voice" not in used_voices


def test_extract_characters_dedupes_within_same_novel_scope(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = f"character-dedupe-user-{uuid4()}"
    novel_id = _create_novel(client, user_id, "星灯案")
    chapter_id = _create_chapter(
        client,
        user_id,
        novel_id,
        "沈砚是男性侦探，穿青色长风衣。沈砚在旧车站调查星灯。苏晚是女性搭档。",
    )

    async def _fake_completion(self, *args, **kwargs):
        return {
            "choices": [
                {
                    "message": {
                        "content": """
                        [
                          {"name":"沈砚","description":"男性侦探","appearance":"青色长风衣","personality":"冷静","voice":"低沉","tags":["男主角"]},
                          {"name":"苏晚","description":"女性搭档","appearance":"短发","personality":"敏锐","voice":"清亮","tags":["女主角"]}
                        ]
                        """
                    }
                }
            ]
        }

    class _FakeTextService:
        async def safe_chat_completion(self, *args, **kwargs):
            return await _fake_completion(self, *args, **kwargs)

    async def _fake_key(*args, **kwargs):
        return "test-key", "qwen", "qwen-plus", None

    monkeypatch.setattr("app.api.v1.endpoints.characters.get_user_qwen_api_key", _fake_key)
    monkeypatch.setattr(
        "app.api.v1.endpoints.characters.create_text_generation_service",
        lambda *args, **kwargs: _FakeTextService(),
    )

    payload = {"chapter_id": chapter_id, "character_count": 5, "auto_generate_avatar": False}
    first_resp = client.post("/api/v1/characters/extract", json=payload, headers=auth_headers(user_id))
    second_resp = client.post("/api/v1/characters/extract", json=payload, headers=auth_headers(user_id))

    assert first_resp.status_code == 201
    assert second_resp.status_code == 201
    first_ids = {item["id"] for item in first_resp.json()}
    second_ids = {item["id"] for item in second_resp.json()}
    assert first_ids == second_ids

    scoped_resp = client.get(f"/api/v1/characters?novel_id={novel_id}", headers=auth_headers(user_id))
    assert scoped_resp.status_code == 200
    names = [item["name"] for item in scoped_resp.json()]
    assert names.count("沈砚") == 1
    assert names.count("苏晚") == 1


def test_character_avatar_generation_uses_dev_fallback_and_updates_character(client: TestClient) -> None:
    user_id = f"character-avatar-user-{uuid4()}"
    novel_id = _create_novel(client, user_id, "雪城档案")
    char_resp = client.post(
        "/api/v1/characters",
        json={
            "novel_id": novel_id,
            "name": "苏晚",
            "description": "女性法医，雪城档案女主角",
            "appearance": "银灰短发，深蓝制服",
            "tags": ["女主角", "女性"],
        },
        headers=auth_headers(user_id),
    )
    assert char_resp.status_code == 201
    character_id = char_resp.json()["id"]

    avatar_resp = client.post(
        f"/api/v1/characters/{character_id}/generate-avatar",
        json={"style": "anime"},
        headers=auth_headers(user_id),
    )
    assert avatar_resp.status_code == 200
    payload = avatar_resp.json()
    assert payload["avatar_url"].startswith("/static/dev/")
    assert payload["character"]["avatar"] == payload["avatar_url"]

    get_resp = client.get(f"/api/v1/characters/{character_id}", headers=auth_headers(user_id))
    assert get_resp.status_code == 200
    assert get_resp.json()["avatar"] == payload["avatar_url"]
