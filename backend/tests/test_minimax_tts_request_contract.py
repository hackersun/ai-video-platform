from types import SimpleNamespace

import pytest

from app.features.model_drivers import SpeechCommand
from app.features.model_drivers.adapters.minimax_speech import MiniMaxSpeechDriver
from app.services.minimax_tts_request import build_minimax_tts_request


def test_internal_model_id_builds_provider_tts_payload() -> None:
    request = build_minimax_tts_request(
        model_id="MiniMax-speech-2.6-hd",
        text="你好",
        voice_id="male-qn-qingse",
        speed=1.0,
    )

    assert request.contract_version == "minimax.tts.v2.v1"
    assert request.url_path == "/t2a_v2"
    assert request.payload == {
        "model": "speech-2.6-hd",
        "text": "你好",
        "stream": False,
        "output_format": "url",
        "voice_setting": {
            "voice_id": "male-qn-qingse",
            "speed": 1.0,
            "vol": 1.0,
            "pitch": 0,
        },
        "language_boost": "auto",
    }


def test_safe_evidence_excludes_text_and_provider_credentials() -> None:
    request = build_minimax_tts_request(
        model_id="speech-2.6-hd",
        text="不应出现在证据中的小说对白",
        voice_id="male-qn-qingse",
        speed=1.0,
    )

    evidence = request.safe_evidence()

    assert set(evidence) == {
        "request_contract_version",
        "api_model_id",
        "voice_id",
        "payload_fields",
    }
    assert evidence["payload_fields"] == sorted(request.payload)
    assert "不应出现在证据中的小说对白" not in str(evidence)


@pytest.mark.asyncio
async def test_minimax_speech_driver_delegates_to_production_tts_method(monkeypatch) -> None:
    captured = {}

    async def fake_text_to_speech(_service, **kwargs):
        captured.update(kwargs)
        return {"task_id": "tts-1", "status": "succeeded", "audio_url": "/static/audio/tts-1.mp3"}

    monkeypatch.setattr("app.services.minimax_service.MiniMaxService.text_to_speech", fake_text_to_speech)
    context = SimpleNamespace(
        api_key="not-a-real-key",
        base_url="https://minimax.example.test/v1",
        profile=SimpleNamespace(api_model_id="speech-2.6-hd"),
    )

    submission = await MiniMaxSpeechDriver().submit(
        SpeechCommand(text="你好", voice_id="male-qn-qingse", params={"speed": 1.2}),
        context,
    )

    assert captured == {
        "text": "你好",
        "model": "speech-2.6-hd",
        "voice_id": "male-qn-qingse",
        "speed": 1.2,
    }
    assert submission.status == "completed"
    assert submission.provider_task_id == "tts-1"
