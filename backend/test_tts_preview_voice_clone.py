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


def test_tts_voice_preview_returns_playable_dev_audio(client: TestClient) -> None:
    user_id = f"tts-preview-user-{uuid4()}"

    response = client.post(
        "/api/v1/tts/preview",
        json={
            "text": "这是一段音色试听。",
            "voice_model": "female-shaonv",
            "speed": 1.0,
            "api_provider": "minimax",
        },
        headers=auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "succeeded"
    assert payload["voice"] == "female-shaonv"
    assert payload["audio_url"].startswith("/static/dev/")
    assert payload["audio_url"].endswith(".wav")


def test_tts_voice_preview_dev_mode_falls_back_when_provider_has_no_audio(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = f"tts-preview-fallback-user-{uuid4()}"

    async def _fake_resolve_config(*args, **kwargs):
        return "api-key", "minimax", "speech-2.6-hd", None

    async def _fake_text_to_speech(self, *args, **kwargs):
        return {"status": "succeeded", "message": "provider returned no audio"}

    monkeypatch.setattr(
        "app.api.v1.endpoints.tts._resolve_preview_tts_config",
        _fake_resolve_config,
    )
    monkeypatch.setattr(
        "app.services.minimax_service.MiniMaxService.text_to_speech",
        _fake_text_to_speech,
    )

    response = client.post(
        "/api/v1/tts/preview",
        json={
            "text": "这是一段音色试听。",
            "voice_model": "female-shaonv",
            "speed": 1.0,
            "api_provider": "minimax",
        },
        headers=auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "succeeded"
    assert payload["audio_url"].startswith("/static/dev/")
    assert "云端试听未返回音频" in payload["message"]


def test_voice_clone_profile_is_listed_as_custom_voice(client: TestClient) -> None:
    user_id = f"tts-clone-user-{uuid4()}"

    create_resp = client.post(
        "/api/v1/tts/voice-clones",
        data={
            "name": "林舟克隆音色",
            "provider": "minimax",
            "description": "少年感，语速稳定",
            "sample_audio_url": "https://example.com/sample.wav",
        },
        headers=auth_headers(user_id),
    )

    assert create_resp.status_code == 201, create_resp.text
    clone = create_resp.json()
    assert clone["voice_id"].startswith("clone-")
    assert clone["is_custom"] is True
    assert clone["sample_audio_url"] == "https://example.com/sample.wav"

    list_resp = client.get("/api/v1/tts/voices?provider=minimax", headers=auth_headers(user_id))
    assert list_resp.status_code == 200
    voices = list_resp.json()["voices"]
    listed = next(item for item in voices if item["voice_id"] == clone["voice_id"])
    assert listed["name"] == "林舟克隆音色"
    assert listed["is_custom"] is True


def test_voice_clone_audio_upload_records_sample_source(client: TestClient) -> None:
    user_id = f"tts-clone-upload-user-{uuid4()}"

    create_resp = client.post(
        "/api/v1/tts/voice-clones",
        data={
            "name": "录音克隆音色",
            "provider": "minimax",
            "description": "浏览器录音样本",
            "sample_source": "recording",
        },
        files={"sample_audio": ("recorded-voice.webm", b"fake-webm-audio", "audio/webm")},
        headers=auth_headers(user_id),
    )

    assert create_resp.status_code == 201, create_resp.text
    clone = create_resp.json()
    assert clone["sample_audio_url"].startswith("/static/generated/voice-clones/")
    assert clone["sample_audio_url"].endswith(".webm")
    assert clone["sample_source"] == "recording"

    list_resp = client.get("/api/v1/tts/voices?provider=minimax", headers=auth_headers(user_id))
    assert list_resp.status_code == 200
    voices = list_resp.json()["voices"]
    listed = next(item for item in voices if item["voice_id"] == clone["voice_id"])
    assert listed["sample_source"] == "recording"
