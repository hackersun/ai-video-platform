"""Pure approval policy for extracted entity candidates."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


DETERMINISTIC_REVIEW_FLAG = "deterministic_requires_review"


def mention_has_approval_evidence(mention: Any) -> bool:
    return bool(
        str(getattr(mention, "source_id", "") or "").strip()
        and str(getattr(mention, "evidence", "") or "").strip()
        and getattr(mention, "confidence", None) is not None
    )


def can_auto_approve_candidate(
    quality: Mapping[str, Any],
    *,
    allow_auto_approve: bool,
    has_approval_evidence: bool,
) -> bool:
    if not allow_auto_approve or not has_approval_evidence:
        return False
    if quality.get("auto_decision") == "auto_approve":
        return True
    flags = {str(flag) for flag in quality.get("flags") or []}
    return int(quality.get("score") or 0) >= 86 and flags == {DETERMINISTIC_REVIEW_FLAG}


__all__ = ["can_auto_approve_candidate", "mention_has_approval_evidence"]
