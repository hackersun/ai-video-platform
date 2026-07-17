"""Provider and persistence independent Story Lock errors."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RequiredEntityBlocked(ValueError):
    code: str
    blocker_category: str
    field: str
    values: tuple[object, ...]
    required_counts: dict[str, int]

    def __str__(self) -> str:
        return self.code


class ProductionRequiredEntityBlocked(RequiredEntityBlocked):
    """Typed blocker proven to originate from a selected production reference."""


class StoryLockSourceStale(ValueError):
    """A persisted Story Lock source no longer satisfies its stable contract."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code
