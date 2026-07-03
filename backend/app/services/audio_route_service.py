"""Audio routing decisions for shot media generation."""

from __future__ import annotations

from typing import Any


_DIALOGUE_FIELDS = ("dialogue", "subtitle", "subtitle_text")


def _get_value(source: Any, field_name: str) -> Any:
    if isinstance(source, dict):
        return source.get(field_name)
    return getattr(source, field_name, None)


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def has_dialogue_text(shot: Any) -> bool:
    for field_name in _DIALOGUE_FIELDS:
        if _has_text(_get_value(shot, field_name)):
            return True

    extra_data = _get_value(shot, "extra_data")
    if isinstance(extra_data, dict):
        for field_name in _DIALOGUE_FIELDS:
            if _has_text(extra_data.get(field_name)):
                return True

    return False


def has_voice_lock(voice_lock: dict | None) -> bool:
    if not isinstance(voice_lock, dict):
        return False
    for field_name in ("voice", "voice_id", "voice_model", "voice_profile"):
        if _has_text(voice_lock.get(field_name)):
            return True
    return False


_has_dialogue_text = has_dialogue_text
_has_voice_lock = has_voice_lock


def resolve_shot_audio_route(shot, *, model_limits: dict, voice_lock: dict | None) -> dict:
    """Return {"route": "tts"|"native_audio"|"silent", "reason": str}.

    Rules, in order:
      1. Dialogue/subtitle text with a voice lock routes to TTS.
      2. Dialogue/subtitle text without a voice lock routes to default TTS.
      3. Action-only shots use native audio when the model supports it.
      4. Otherwise, action-only shots stay silent.
    """
    if has_dialogue_text(shot):
        if has_voice_lock(voice_lock):
            return {"route": "tts", "reason": "voice_lock"}
        return {"route": "tts", "reason": "voice_lock_missing"}

    if model_limits.get("native_audio") is True:
        return {"route": "native_audio", "reason": "native_audio_supported"}

    return {"route": "silent", "reason": "native_audio_unavailable"}
