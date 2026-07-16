import base64
import json

import pytest

from app.services.volcano_service import VolcanoService
from app.services.volcano_speech_tts import (
    configure_volcano_speech_endpoint,
    normalize_volcano_speech_voice,
    parse_volcano_speech_endpoint,
    parse_volcano_speech_events,
)


def test_endpoint_parses_app_and_resource_without_token() -> None:
    endpoint = parse_volcano_speech_endpoint(
        "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
        "?app_id=1234567890&resource_id=seed-tts-2.0"
    )

    assert endpoint.url == "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
    assert endpoint.app_id == "1234567890"
    assert endpoint.resource_id == "seed-tts-2.0"
    assert "token" not in repr(endpoint).lower()


def test_endpoint_uses_user_scoped_app_and_resource_params() -> None:
    configured = configure_volcano_speech_endpoint(
        "https://openspeech.bytedance.com/api/v3/tts/unidirectional",
        {"app_id": "1234567890", "resource_id": "seed-tts-2.0"},
    )

    assert configured == (
        "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
        "?app_id=1234567890&resource_id=seed-tts-2.0"
    )


def test_concatenated_events_decode_mp3_chunks() -> None:
    first = base64.b64encode(b"ID3first").decode()
    second = base64.b64encode(b"second").decode()
    payload = "".join(
        json.dumps(event)
        for event in (
            {"code": 0, "data": first},
            {"code": 0, "data": second},
            {"code": 20000000, "message": "OK"},
        )
    )

    events, audio = parse_volcano_speech_events(payload)

    assert [event["code"] for event in events] == [0, 0, 20000000]
    assert audio == b"ID3firstsecond"


def test_legacy_voice_alias_maps_to_seed_tts_voice() -> None:
    assert normalize_volcano_speech_voice("female_nvsheng") == "zh_female_vv_uranus_bigtts"
    assert normalize_volcano_speech_voice("zh_male_dayi_uranus_bigtts") == "zh_male_dayi_uranus_bigtts"


def test_provider_error_event_is_rejected() -> None:
    payload = json.dumps({"code": 55000000, "message": "resource mismatch"})

    with pytest.raises(ValueError, match="55000000"):
        parse_volcano_speech_events(payload)


@pytest.mark.asyncio
async def test_volcano_service_delegates_openspeech_tts(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    async def fake_synthesize(**kwargs):
        captured.update(kwargs)
        return {"status": "succeeded", "audio_url": "/static/audio/test.mp3"}

    class RejectLegacySession:
        def __init__(self, *args, **kwargs):
            raise AssertionError("openspeech TTS must not use the Ark audio/speech transport")

    monkeypatch.setattr(
        "app.services.volcano_speech_tts.synthesize_volcano_speech_v3",
        fake_synthesize,
    )
    monkeypatch.setattr(
        "app.services.volcano_service.aiohttp.ClientSession",
        RejectLegacySession,
    )
    service = VolcanoService(
        "access-token",
        "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
        "?app_id=1234567890&resource_id=seed-tts-2.0",
    )

    result = await service.text_to_speech(
        text="你好",
        model="seed-tts-2.0",
        voice="female_nvsheng",
        speed=1.1,
        output_dir="audio/previews",
    )

    assert result["status"] == "succeeded"
    assert captured == {
        "access_token": "access-token",
        "base_url": service.base_url,
        "text": "你好",
        "voice": "female_nvsheng",
        "speed": 1.1,
        "output_dir": "audio/previews",
    }
