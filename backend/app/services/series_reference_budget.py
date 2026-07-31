"""Budget decision for scoped series-reference preparation."""

from __future__ import annotations

from decimal import Decimal
from typing import Any


def reference_budget_plan_is_safe(
    plan: dict[str, Any],
    *,
    scoped_repair_reservation_rmb: Decimal | None = None,
) -> bool:
    unsafe_codes = {
        "trusted_budget_policy_missing",
        "wave_one_budget_policy_invalid",
        "image_estimate_missing",
        "video_estimate_missing",
        "tts_estimate_missing",
        "production_entities_unapproved",
        "production_entity_conflict",
    }
    if any(code in unsafe_codes for code in plan.get("blocker_codes") or []):
        return False
    try:
        budget = plan["budget"]
        if Decimal(budget["projected_total_rmb"]) <= Decimal(budget["maximum_rmb"]):
            return True
        return (
            scoped_repair_reservation_rmb is not None
            and scoped_repair_reservation_rmb > 0
            and scoped_repair_reservation_rmb <= Decimal(budget["remaining_rmb"])
        )
    except (KeyError, TypeError, ValueError):
        return False


__all__ = ["reference_budget_plan_is_safe"]
