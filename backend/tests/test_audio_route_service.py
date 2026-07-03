from types import SimpleNamespace

import pytest


def _resolve_shot_audio_route(shot, *, model_limits: dict, voice_lock: dict | None) -> dict:
    try:
        from app.services.audio_route_service import resolve_shot_audio_route
    except ModuleNotFoundError:
        pytest.fail("audio route service is missing")

    return resolve_shot_audio_route(shot, model_limits=model_limits, voice_lock=voice_lock)


def test_dialogue_with_voice_lock_routes_to_tts() -> None:
    shot = SimpleNamespace(dialogue="We have to move now.")

    result = _resolve_shot_audio_route(
        shot,
        model_limits={"native_audio": True},
        voice_lock={"voice_id": "hero-voice"},
    )

    assert result["route"] == "tts"


def test_dialogue_without_voice_lock_routes_to_default_tts() -> None:
    shot = SimpleNamespace(subtitle_text="Where did the light go?")

    result = _resolve_shot_audio_route(shot, model_limits={}, voice_lock=None)

    assert result == {"route": "tts", "reason": "voice_lock_missing"}


def test_dialogue_with_blank_voice_lock_routes_to_default_tts() -> None:
    shot = SimpleNamespace(dialogue="Hold the line.")

    result = _resolve_shot_audio_route(
        shot,
        model_limits={"native_audio": True},
        voice_lock={"voice": "   "},
    )

    assert result == {"route": "tts", "reason": "voice_lock_missing"}


def test_action_shot_uses_native_audio_when_supported() -> None:
    shot = SimpleNamespace(prompt="Wide shot of rain hitting a neon alley.")

    result = _resolve_shot_audio_route(
        shot,
        model_limits={"native_audio": True},
        voice_lock=None,
    )

    assert result["route"] == "native_audio"


def test_action_shot_is_silent_without_native_audio_support() -> None:
    shot = SimpleNamespace(prompt="A silent establishing shot over the city.")

    result = _resolve_shot_audio_route(
        shot,
        model_limits={"native_audio": False},
        voice_lock=None,
    )

    assert result["route"] == "silent"
