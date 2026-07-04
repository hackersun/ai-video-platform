"""Feature contract for the unified Series Studio console."""

from __future__ import annotations

import os
from typing import Any, Dict


def series_studio_enabled() -> bool:
    return os.getenv("SERIES_STUDIO_V2", "true").strip().lower() not in {"0", "false", "off", "no"}


def series_studio_contract() -> Dict[str, Any]:
    return {
        "enabled": series_studio_enabled(),
        "primary_console": "series_studio",
        "expert_drilldowns": [
            "/story-bibles",
            "/studio/cards",
            "/studio/shot-review",
            "/workflow",
            "/producer",
            "/video-generation",
        ],
    }
