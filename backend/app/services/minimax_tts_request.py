"""Shared MiniMax TTS request construction and redacted evidence."""

from dataclasses import dataclass
from typing import Any, Mapping

from app.core.minimax_config import get_minimax_model


@dataclass(frozen=True)
class MiniMaxTTSRequest:
    contract_version: str
    url_path: str
    payload: dict[str, Any]

    def safe_evidence(self) -> dict[str, Any]:
        voice = self.payload.get("voice_setting") or {}
        return {
            "request_contract_version": self.contract_version,
            "api_model_id": self.payload.get("model"),
            "voice_id": voice.get("voice_id"),
            "payload_fields": sorted(self.payload),
        }


def resolve_minimax_tts_model_id(model_id: str) -> str:
    model = get_minimax_model(model_id)
    if model.get("type") == "tts" and model.get("api_model_id"):
        return str(model["api_model_id"])
    return model_id


def build_minimax_tts_request(
    *,
    model_id: str,
    text: str,
    voice_id: str,
    speed: float,
    vol: float = 1.0,
    pitch: float = 0,
    output_format: str = "url",
    language_boost: str = "auto",
    extra_params: Mapping[str, Any] | None = None,
) -> MiniMaxTTSRequest:
    payload: dict[str, Any] = {
        "model": resolve_minimax_tts_model_id(model_id),
        "text": text,
        "stream": False,
        "output_format": output_format,
        "voice_setting": {
            "voice_id": voice_id,
            "speed": speed,
            "vol": vol,
            "pitch": pitch,
        },
        "language_boost": language_boost,
    }
    payload.update(extra_params or {})
    return MiniMaxTTSRequest("minimax.tts.v2.v1", "/t2a_v2", payload)
