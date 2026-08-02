"""Stable input identity for deciding whether a completed shot video is reusable."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def shot_input_fingerprint(shot: Any) -> str:
    extra = shot.extra_data if isinstance(getattr(shot, "extra_data", None), dict) else {}
    value = {
        "shot_id": shot.id,
        "prompt": shot.prompt,
        "visual_description": shot.visual_description,
        "dialogue": shot.dialogue,
        "subtitle_text": extra.get("subtitle_text"),
    }
    if extra.get("first_frame_revision"):
        value["first_frame_revision"] = extra["first_frame_revision"]
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


__all__ = ["shot_input_fingerprint"]
