"""Public, persistence-independent Story Lock error type."""

from __future__ import annotations

from typing import Any


class StoryLockPreparationBlocked(ValueError):
    def __init__(self, message: str | None = None, **detail: Any) -> None:
        code = detail.get("code")
        super().__init__(code or message or "story_lock_preparation_blocked")
        self.code = code or "story_lock_preparation_blocked"
        self.blocker_category = detail.get("blocker_category")
        self.field = detail.get("field")
        self.values = tuple(detail.get("values") or ())
        self.required_counts = dict(detail.get("required_counts") or {})
        self.safe_detail = {"conflict_fields": detail.get("conflict_fields") or []}
