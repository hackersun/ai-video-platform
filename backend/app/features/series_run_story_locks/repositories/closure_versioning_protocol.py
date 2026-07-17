"""Production persistence contract for atomic closure-v2 upgrades."""

from __future__ import annotations

from typing import Any, Mapping, Protocol


class ClosureVersioningRepository(Protocol):
    async def apply_in_transaction(
        self,
        run_id: str,
        request: Mapping[str, Any],
        *,
        expected_run_version: int,
        fail_at: str | None = None,
    ) -> dict[str, Any]: ...
