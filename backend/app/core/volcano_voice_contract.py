"""Narrow Volcano Seed-TTS voices approved for paid live-canary runs."""

from __future__ import annotations


VOLCANO_LIVE_CANARY_VOICES = (
    ("zh_female_vv_uranus_bigtts", "普通话·Vivi"),
)
DEFAULT_VOLCANO_TTS_VOICE = VOLCANO_LIVE_CANARY_VOICES[0][0]


def volcano_live_canary_voice_ids() -> tuple[str, ...]:
    return tuple(voice_id for voice_id, _label in VOLCANO_LIVE_CANARY_VOICES)


__all__ = [
    "DEFAULT_VOLCANO_TTS_VOICE",
    "VOLCANO_LIVE_CANARY_VOICES",
    "volcano_live_canary_voice_ids",
]
