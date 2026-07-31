"""Audited one-time budget extension for a confirmed live-canary repair."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.time_utils import utc_now
from app.models.series_production_run import SeriesProductionRun
from app.services.live_canary_policy import money, money_text


BASE_MAXIMUM = Decimal("10.00")
REPAIR_EXTENSION = Decimal("1.00")


class RepairBudgetExtensionError(ValueError):
    pass


def _trusted_extension(run: SeriesProductionRun) -> Decimal:
    policy = run.budget_policy or {}
    audit = (run.run_metadata or {}).get("repair_budget_extension") or {}
    try:
        amount = money(policy.get("repair_extension_rmb", "0"))
    except ValueError:
        return Decimal("0.00")
    if (
        amount != REPAIR_EXTENSION
        or audit.get("status") != "approved"
        or audit.get("amount_rmb") != money_text(amount)
        or not str(audit.get("reason") or "").strip()
        or not list(audit.get("artifact_ids") or [])
    ):
        return Decimal("0.00")
    return amount


def effective_budget_maximum(run: SeriesProductionRun) -> Decimal:
    base = money((run.budget_policy or {}).get("max_rmb", "0"))
    return base + _trusted_extension(run)


async def grant_live_canary_repair_extension(
    db: AsyncSession,
    run: SeriesProductionRun,
    *,
    amount: Decimal,
    reason: str,
    artifact_ids: list[str],
) -> dict[str, Any]:
    policy = dict(run.budget_policy or {})
    summary = run.cost_summary or {}
    if (
        policy.get("profile") != "isolated_live_canary"
        or policy.get("live_canary") is not True
        or money(policy.get("max_rmb", "0")) != BASE_MAXIMUM
    ):
        raise RepairBudgetExtensionError("trusted live-canary base policy is required")
    if policy.get("repair_extension_rmb") or (run.run_metadata or {}).get("repair_budget_extension"):
        raise RepairBudgetExtensionError("repair budget extension was already granted")
    if money(amount) != REPAIR_EXTENSION:
        raise RepairBudgetExtensionError("repair budget extension must be exactly RMB1.00")
    scoped_ids = list(dict.fromkeys(str(value).strip() for value in artifact_ids if str(value).strip()))
    if not str(reason).strip() or not scoped_ids:
        raise RepairBudgetExtensionError("repair reason and affected artifacts are required")
    if money(summary.get("reserved_rmb", "0")) != Decimal("0.00"):
        raise RepairBudgetExtensionError("pending reservations must settle before repair extension")

    audit = {
        "status": "approved", "amount_rmb": "1.00", "base_maximum_rmb": "10.00",
        "effective_maximum_rmb": "11.00", "reason": str(reason).strip(),
        "artifact_ids": scoped_ids, "granted_at": utc_now().isoformat(),
    }
    policy["repair_extension_rmb"] = audit["amount_rmb"]
    metadata = dict(run.run_metadata or {})
    metadata["repair_budget_extension"] = audit
    run.budget_policy = policy
    run.run_metadata = metadata
    flag_modified(run, "budget_policy")
    flag_modified(run, "run_metadata")
    await db.commit()
    return audit


__all__ = [
    "RepairBudgetExtensionError",
    "effective_budget_maximum",
    "grant_live_canary_repair_extension",
]
