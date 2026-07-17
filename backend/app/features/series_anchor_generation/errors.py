"""Stable application errors for series-anchor API adapters."""

from __future__ import annotations

from typing import Any


class SeriesAnchorError(RuntimeError):
    def __init__(self, status_code: int, detail: str | dict[str, Any]):
        super().__init__(detail if isinstance(detail, str) else str(detail.get("code") or "series_anchor_error"))
        self.status_code = status_code
        self.detail = detail


__all__ = ["SeriesAnchorError"]
