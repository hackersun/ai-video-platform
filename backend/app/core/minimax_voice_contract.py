"""Narrow MiniMax system voices approved for paid live-canary runs."""

from __future__ import annotations


MINIMAX_LIVE_CANARY_VOICES = (
    ("male-qn-qingse", "普通话·青涩青年"),
)
DEFAULT_MINIMAX_TTS_VOICE = MINIMAX_LIVE_CANARY_VOICES[0][0]
MINIMAX_TTS_VERIFICATION_VERSION = "minimax-tts-exact-v1"


def minimax_live_canary_voice_ids() -> tuple[str, ...]:
    return tuple(voice_id for voice_id, _label in MINIMAX_LIVE_CANARY_VOICES)


def minimax_tts_verification_message(model_id: str) -> str:
    return (
        f"MiniMax TTS 精确验证成功 [{MINIMAX_TTS_VERIFICATION_VERSION};"
        f"model={model_id};voice={DEFAULT_MINIMAX_TTS_VOICE}]"
    )


def has_current_minimax_tts_verification(message: object, model_id: str) -> bool:
    return str(message or "") == minimax_tts_verification_message(model_id)


__all__ = [
    "DEFAULT_MINIMAX_TTS_VOICE",
    "MINIMAX_LIVE_CANARY_VOICES",
    "MINIMAX_TTS_VERIFICATION_VERSION",
    "has_current_minimax_tts_verification",
    "minimax_live_canary_voice_ids",
    "minimax_tts_verification_message",
]
