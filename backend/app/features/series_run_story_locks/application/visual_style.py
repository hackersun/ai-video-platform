"""Canonical visual-style resolution for series Story Locks."""

from __future__ import annotations

import re
from typing import Any


_EXPLICIT_STYLE = re.compile(
    r"(?:\b3d\b|\b2d\b|三维|二维|写实|赛璐璐|水墨|像素|黏土|定格|CG|国风|动漫|动画)",
    re.IGNORECASE,
)


def resolve_novel_visual_style(novel: Any) -> str:
    """Prefer persisted style, then an explicit style statement, then genre."""
    extra = novel.extra_data or {}
    persisted = str(extra.get("visual_style") or extra.get("style") or "").strip()
    if persisted:
        return persisted
    description = str(novel.description or "").strip()
    if description and _EXPLICIT_STYLE.search(description):
        return description[:300]
    return str(novel.genre or "").strip()
