"""Acceptance-only provider adapter.

The switch is deliberately exact and defaults off.  Callers must keep normal
HTTP/API and ORM boundaries intact and replace only the external provider call.
"""

from __future__ import annotations

import os

from app.core.dev_generation import dev_audio_url, dev_video_url


def deterministic_provider_fake_enabled() -> bool:
    return os.getenv("DETERMINISTIC_PROVIDER_FAKE") == "1"


def deterministic_config_test_result(model_id: str) -> dict:
    if not deterministic_provider_fake_enabled():
        raise RuntimeError("deterministic provider fake is disabled")
    return {
        "success": True,
        "message": "deterministic provider adapter verified",
        "response": f"deterministic:{model_id}",
        "response_time_ms": 0,
        "tokens_used": 0,
    }


def deterministic_media_provider_artifacts(job_id: str, *, duration_seconds: float, include_audio: bool) -> dict:
    """Final-I/O fake used by the normal workflow pipeline, never by its gates/evaluators."""
    if not deterministic_provider_fake_enabled():
        raise RuntimeError("deterministic provider fake is disabled")
    calls = [
        {"capability": "reference", "status": "consumed"},
        {"capability": "video", "status": "succeeded", "provider_task_id": f"det-video:{job_id}"},
    ]
    if include_audio:
        calls.append({"capability": "tts", "status": "succeeded", "provider_task_id": f"det-tts:{job_id}"})
    return {
        "video_url": dev_video_url(job_id, duration_seconds=duration_seconds),
        "audio_url": dev_audio_url(job_id) if include_audio else None,
        "provider_calls": calls,
    }
