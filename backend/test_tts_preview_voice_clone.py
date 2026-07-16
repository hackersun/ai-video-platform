from __future__ import annotations

import asyncio
import io
from uuid import uuid4

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient

from app.api.v1.endpoints import tts as tts_endpoint
from app.core.database import SyncSessionLocal
from app.models.llm_config import LLMConfig, LLMModel, LLMProvider
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


def test_voice_clone_upload_keeps_existing_sample_when_voice_id_collides() -> None:
    voice_id = f"collision-{uuid4().hex[:8]}"
    first_file = UploadFile(filename=f"{voice_id}.mp3", file=io.BytesIO(b"first-audio"))
    second_file = UploadFile(filename=f"{voice_id}.mp3", file=io.BytesIO(b"second-audio"))
    written_paths = []

    try:
        first_url = asyncio.run(tts_endpoint._save_voice_clone_upload(first_file, voice_id))
        second_url = asyncio.run(tts_endpoint._save_voice_clone_upload(second_file, voice_id))
        written_paths.extend([first_url, second_url])

        assert first_url != second_url
        first_path = tts_endpoint.STATIC_ROOT / first_url.removeprefix("/static/")
        second_path = tts_endpoint.STATIC_ROOT / second_url.removeprefix("/static/")
        assert first_path.read_bytes() == b"first-audio"
        assert second_path.read_bytes() == b"second-audio"
    finally:
        for media_url in written_paths:
            media_path = tts_endpoint.STATIC_ROOT / media_url.removeprefix("/static/")
            media_path.unlink(missing_ok=True)


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


def test_tts_voice_preview_returns_provider_resolved_voice(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = f"tts-preview-volcano-user-{uuid4()}"

    async def _fake_resolve_config(*args, **kwargs):
        return "access-token", "volcano", "seed-tts-2.0", "https://example.com"

    async def _fake_text_to_speech(self, *args, **kwargs):
        return {
            "status": "succeeded",
            "audio_url": "https://example.com/preview.mp3",
            "voice": "zh_female_vv_uranus_bigtts",
        }

    monkeypatch.setattr(
        "app.api.v1.endpoints.tts._resolve_preview_tts_config",
        _fake_resolve_config,
    )
    monkeypatch.setattr(
        "app.services.volcano_service.VolcanoService.text_to_speech",
        _fake_text_to_speech,
    )

    response = client.post(
        "/api/v1/tts/preview",
        json={
            "text": "这是一段音色试听。",
            "voice_model": "female_nvsheng",
            "api_provider": "volcano",
        },
        headers=auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    assert response.json()["voice"] == "zh_female_vv_uranus_bigtts"


def test_volcano_speech_config_test_uses_tts_protocol(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = f"vtts-{uuid4().hex[:20]}"
    model_id = f"volcano-speech-model-{uuid4()}"
    config_id = f"volcano-speech-config-{uuid4()}"
    with SyncSessionLocal() as db:
        if db.get(LLMProvider, "volcano") is None:
            db.add(LLMProvider(id="volcano", name="volcano", is_active=True))
        db.add(LLMModel(
            id=model_id,
            provider_id="volcano",
            model_id="seed-tts-2.0",
            model_name="Doubao Seed TTS 2.0",
            model_type="tts",
            capabilities=["text-to-speech"],
            base_url="https://openspeech.bytedance.com/api/v3/tts/unidirectional",
            is_active=True,
        ))
        config = LLMConfig(
            id=config_id,
            user_id=user_id,
            model_id=model_id,
            name="豆包语音测试配置",
            extra_params={"app_id": "1234567890", "resource_id": "seed-tts-2.0"},
            is_active=True,
        )
        config.set_api_key_encrypted("access-token")
        db.add(config)
        db.commit()

    async def _reject_ark_test(*args, **kwargs):
        return {
            "success": False,
            "message": "wrong Ark test path",
            "response": None,
            "response_time_ms": 0,
            "tokens_used": 0,
        }

    async def _fake_synthesize(**kwargs):
        return {
            "status": "succeeded",
            "audio_url": "/static/audio/previews/test.mp3",
            "voice": "zh_female_vv_uranus_bigtts",
        }

    monkeypatch.setattr(
        "app.api.v1.endpoints.llm_config.test_volcano_api",
        _reject_ark_test,
    )
    monkeypatch.setattr(
        "app.services.volcano_speech_tts.synthesize_volcano_speech_v3",
        _fake_synthesize,
    )

    response = client.post(
        f"/api/v1/llm/configs/{config_id}/test",
        json={"message": "测试豆包语音连接"},
        headers=auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    assert response.json()["success"] is True
    with SyncSessionLocal() as db:
        assert db.get(LLMConfig, config_id).test_status == "success"


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


def test_minimax_voice_clone_upload_activates_provider_when_key_available(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = f"tts-clone-minimax-active-user-{uuid4()}"
    voice_id = f"sunqinyue-test-{uuid4().hex[:8]}"
    captured: dict = {}

    async def _fake_resolve_config(*args, **kwargs):
        return "api-key", "minimax", "speech-2.6-hd", None

    async def _fake_upload(self, audio_path: str):
        captured["upload_path"] = audio_path
        return {"file_id": "123456789"}

    async def _fake_clone(self, **kwargs):
        captured["clone"] = kwargs
        return {"demo_audio": "https://example.com/demo.mp3", "extra_info": {"audio_length": 8123}}

    monkeypatch.setattr("app.api.v1.endpoints.tts._resolve_preview_tts_config", _fake_resolve_config)
    monkeypatch.setattr("app.services.minimax_service.MiniMaxService.upload_voice_clone_audio", _fake_upload)
    monkeypatch.setattr("app.services.minimax_service.MiniMaxService.clone_voice", _fake_clone)

    create_resp = client.post(
        "/api/v1/tts/voice-clones",
        data={
            "name": "孙秦岳默认声线",
            "provider": "minimax",
            "voice_id": voice_id,
            "description": "本地个人数字员工声线资产",
            "sample_source": "upload",
        },
        files={"sample_audio": (f"{voice_id}.mp3", b"fake-mp3-audio", "audio/mpeg")},
        headers=auth_headers(user_id),
    )

    assert create_resp.status_code == 201, create_resp.text
    clone = create_resp.json()
    assert clone["voice_id"] == voice_id
    assert clone["status"] == "provider_ready"
    assert captured["upload_path"].endswith(f"{voice_id}.mp3")
    assert captured["clone"]["file_id"] == "123456789"
    assert captured["clone"]["voice_id"] == voice_id
    assert captured["clone"]["model"] == "speech-2.8-hd"

    list_resp = client.get("/api/v1/tts/voices?provider=minimax", headers=auth_headers(user_id))
    assert list_resp.status_code == 200
    listed = next(item for item in list_resp.json()["voices"] if item["voice_id"] == voice_id)
    assert listed["status"] == "provider_ready"
    assert listed["provider_ready"] is True
    assert listed["provider_file_id"] == "123456789"
    (tts_endpoint.STATIC_ROOT / clone["sample_audio_url"].removeprefix("/static/")).unlink(missing_ok=True)


def test_minimax_voice_preview_rejects_custom_clone_until_provider_ready(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = f"tts-clone-pending-preview-user-{uuid4()}"
    voice_id = f"pending-{uuid4().hex[:8]}"
    called = False

    create_resp = client.post(
        "/api/v1/tts/voice-clones",
        data={
            "name": "未激活声线",
            "provider": "minimax",
            "voice_id": voice_id,
            "description": "只有本地样本，云端未就绪",
            "sample_audio_url": "https://example.com/pending.mp3",
        },
        headers=auth_headers(user_id),
    )
    assert create_resp.status_code == 201, create_resp.text
    assert create_resp.json()["status"] == "provider_pending"

    async def _fake_resolve_config(*args, **kwargs):
        return "api-key", "minimax", "speech-2.6-hd", None

    async def _fake_text_to_speech(self, *args, **kwargs):
        nonlocal called
        called = True
        return {"audio_url": "https://example.com/should-not-call.mp3"}

    monkeypatch.setattr("app.api.v1.endpoints.tts._resolve_preview_tts_config", _fake_resolve_config)
    monkeypatch.setattr("app.services.minimax_service.MiniMaxService.text_to_speech", _fake_text_to_speech)

    preview_resp = client.post(
        "/api/v1/tts/preview",
        json={
            "text": "这是一段试听。",
            "voice_model": voice_id,
            "speed": 1.0,
            "api_provider": "minimax",
        },
        headers=auth_headers(user_id),
    )

    assert preview_resp.status_code == 422, preview_resp.text
    assert "云端克隆未就绪" in preview_resp.json()["detail"]
    assert called is False


def test_minimax_voice_preview_uses_clone_tts_model_when_provider_ready(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = f"tts-clone-ready-preview-user-{uuid4()}"
    voice_id = f"ready-{uuid4().hex[:8]}"
    captured: dict = {}

    async def _fake_resolve_config(*args, **kwargs):
        return "api-key", "minimax", "speech-2.6-hd", None

    async def _fake_upload(self, audio_path: str):
        return {"file_id": "123456789"}

    async def _fake_clone(self, **kwargs):
        return {"demo_audio": "https://example.com/demo.mp3"}

    async def _fake_text_to_speech(self, *args, **kwargs):
        captured["tts"] = kwargs
        return {"audio_url": "https://example.com/preview.mp3", "duration": 1.0}

    monkeypatch.setattr("app.api.v1.endpoints.tts._resolve_preview_tts_config", _fake_resolve_config)
    monkeypatch.setattr("app.services.minimax_service.MiniMaxService.upload_voice_clone_audio", _fake_upload)
    monkeypatch.setattr("app.services.minimax_service.MiniMaxService.clone_voice", _fake_clone)
    monkeypatch.setattr("app.services.minimax_service.MiniMaxService.text_to_speech", _fake_text_to_speech)

    create_resp = client.post(
        "/api/v1/tts/voice-clones",
        data={
            "name": "云端可用声线",
            "provider": "minimax",
            "voice_id": voice_id,
        },
        files={"sample_audio": (f"{voice_id}.mp3", b"fake-mp3-audio", "audio/mpeg")},
        headers=auth_headers(user_id),
    )
    assert create_resp.status_code == 201, create_resp.text
    assert create_resp.json()["status"] == "provider_ready"

    preview_resp = client.post(
        "/api/v1/tts/preview",
        json={
            "text": "这是一段试听。",
            "voice_model": voice_id,
            "speed": 1.0,
            "api_provider": "minimax",
        },
        headers=auth_headers(user_id),
    )

    assert preview_resp.status_code == 200, preview_resp.text
    assert captured["tts"]["model"] == "speech-2.8-hd"


def test_minimax_tts_generate_rejects_custom_clone_until_provider_ready(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = f"tts-clone-pending-generate-user-{uuid4()}"
    voice_id = f"pending-{uuid4().hex[:8]}"
    called = False

    create_resp = client.post(
        "/api/v1/tts/voice-clones",
        data={
            "name": "未激活生成声线",
            "provider": "minimax",
            "voice_id": voice_id,
            "description": "只有本地样本，云端未就绪",
            "sample_audio_url": "https://example.com/pending.mp3",
        },
        headers=auth_headers(user_id),
    )
    assert create_resp.status_code == 201, create_resp.text

    async def _fake_text_to_speech(self, *args, **kwargs):
        nonlocal called
        called = True
        return {"audio_url": "https://example.com/should-not-call.mp3", "duration": 1.0}

    monkeypatch.setattr("app.services.minimax_service.MiniMaxService.text_to_speech", _fake_text_to_speech)

    generate_resp = client.post(
        "/api/v1/tts/generate",
        json={
            "text_content": "这是一段生成测试。",
            "voice_model": voice_id,
            "speed": 1.0,
            "api_provider": "minimax",
            "api_key": "api-key",
        },
        headers=auth_headers(user_id),
    )

    assert generate_resp.status_code == 422, generate_resp.text
    assert "云端克隆未就绪" in generate_resp.json()["detail"]
    assert called is False


def test_minimax_tts_generate_uses_clone_tts_model_when_provider_ready(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = f"tts-clone-ready-generate-user-{uuid4()}"
    voice_id = f"ready-{uuid4().hex[:8]}"
    captured: dict = {}

    async def _fake_resolve_config(*args, **kwargs):
        return "api-key", "minimax", "speech-2.6-hd", None

    async def _fake_upload(self, audio_path: str):
        return {"file_id": "123456789"}

    async def _fake_clone(self, **kwargs):
        return {"demo_audio": "https://example.com/demo.mp3"}

    async def _fake_text_to_speech(self, *args, **kwargs):
        captured["tts"] = kwargs
        return {"audio_url": "https://example.com/generated.mp3", "duration": 1.0}

    monkeypatch.setattr("app.api.v1.endpoints.tts._resolve_preview_tts_config", _fake_resolve_config)
    monkeypatch.setattr("app.services.minimax_service.MiniMaxService.upload_voice_clone_audio", _fake_upload)
    monkeypatch.setattr("app.services.minimax_service.MiniMaxService.clone_voice", _fake_clone)
    monkeypatch.setattr("app.services.minimax_service.MiniMaxService.text_to_speech", _fake_text_to_speech)

    create_resp = client.post(
        "/api/v1/tts/voice-clones",
        data={
            "name": "云端可用生成声线",
            "provider": "minimax",
            "voice_id": voice_id,
        },
        files={"sample_audio": (f"{voice_id}.mp3", b"fake-mp3-audio", "audio/mpeg")},
        headers=auth_headers(user_id),
    )
    assert create_resp.status_code == 201, create_resp.text

    generate_resp = client.post(
        "/api/v1/tts/generate",
        json={
            "text_content": "这是一段生成测试。",
            "voice_model": voice_id,
            "speed": 1.0,
            "api_provider": "minimax",
            "api_key": "api-key",
        },
        headers=auth_headers(user_id),
    )

    assert generate_resp.status_code == 200, generate_resp.text
    assert captured["tts"]["model"] == "speech-2.8-hd"


def test_minimax_voice_clone_activate_existing_asset(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = f"tts-clone-activate-user-{uuid4()}"

    create_resp = client.post(
        "/api/v1/tts/voice-clones",
        data={
            "name": "待激活声线",
            "provider": "minimax",
            "voice_id": "pending-voice",
            "description": "需要云端激活",
        },
        files={"sample_audio": ("pending-voice.mp3", b"fake-mp3-audio", "audio/mpeg")},
        headers=auth_headers(user_id),
    )
    assert create_resp.status_code == 201, create_resp.text
    asset_id = create_resp.json()["id"]

    async def _fake_resolve_config(*args, **kwargs):
        return "api-key", "minimax", "speech-2.6-hd", None

    async def _fake_upload(self, audio_path: str):
        return {"file_id": "987654321"}

    async def _fake_clone(self, **kwargs):
        return {"demo_audio": "https://example.com/activated.mp3"}

    monkeypatch.setattr("app.api.v1.endpoints.tts._resolve_preview_tts_config", _fake_resolve_config)
    monkeypatch.setattr("app.services.minimax_service.MiniMaxService.upload_voice_clone_audio", _fake_upload)
    monkeypatch.setattr("app.services.minimax_service.MiniMaxService.clone_voice", _fake_clone)

    activate_resp = client.post(
        f"/api/v1/tts/voice-clones/{asset_id}/activate",
        data={"model_config_id": "", "preview_text": "这是一段激活试听。"},
        headers=auth_headers(user_id),
    )

    assert activate_resp.status_code == 200, activate_resp.text
    payload = activate_resp.json()
    assert payload["voice_id"] == "pending-voice"
    assert payload["status"] == "provider_ready"


def test_voice_clone_profile_accepts_existing_voice_id(client: TestClient) -> None:
    user_id = f"tts-clone-existing-user-{uuid4()}"

    create_resp = client.post(
        "/api/v1/tts/voice-clones",
        data={
            "name": "孙秦岳默认声线",
            "provider": "heygen",
            "voice_id": "sunqinyue-default",
            "description": "本地个人数字员工声线资产",
            "sample_audio_url": "https://example.com/sunqinyue-default.mp3",
        },
        headers=auth_headers(user_id),
    )

    assert create_resp.status_code == 201, create_resp.text
    clone = create_resp.json()
    assert clone["voice_id"] == "sunqinyue-default"
    assert clone["status"] == "provider_pending"

    list_resp = client.get("/api/v1/tts/voices?provider=heygen", headers=auth_headers(user_id))
    assert list_resp.status_code == 200
    voices = list_resp.json()["voices"]
    listed = next(item for item in voices if item["voice_id"] == "sunqinyue-default")
    assert listed["name"] == "孙秦岳默认声线"
    assert listed["status"] == "provider_pending"
