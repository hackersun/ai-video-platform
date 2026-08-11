"""Customer billing boundary for real provider operations."""

from __future__ import annotations

import os
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.billing.domain import BillingLimitExceeded, rmb_to_micros
from app.features.billing.service import capture_charge, release_charge, reserve_charge
from app.models.billing import BillingAccount, BillingReservation
from app.models.live_canary_provider_operation import LiveCanaryProviderOperation
from app.models.novel import Novel
from app.models.series_production_run import SeriesProductionRun


def customer_billing_enforced() -> bool:
    return os.getenv("CUSTOMER_BILLING_MODE", "off").strip().lower() == "enforced"


async def reserve_customer_operation(
    db: AsyncSession,
    operation: LiveCanaryProviderOperation,
    *,
    supplier_estimate_rmb: Any,
) -> BillingReservation | None:
    if not customer_billing_enforced():
        return None
    account = await db.scalar(select(BillingAccount).where(
        BillingAccount.owner_type == "user",
        BillingAccount.owner_id == operation.user_id,
    ))
    if account is None:
        raise BillingLimitExceeded("当前用户还没有可用的客户计费账户，请联系运营人员开通")
    run = await db.get(SeriesProductionRun, operation.run_id)
    novel = await db.get(Novel, run.novel_id) if run else None
    return await reserve_charge(
        db, account_id=account.id, user_id=operation.user_id,
        project_id=novel.project_id if novel else None,
        provider_operation_id=operation.id, idempotency_key=f"provider:{operation.id}",
        supplier_estimate_micros=rmb_to_micros(supplier_estimate_rmb, positive=True),
    )


async def settle_customer_operation(
    db: AsyncSession,
    operation: LiveCanaryProviderOperation,
    *,
    provider_status: str,
    supplier_actual_rmb: Any = None,
) -> None:
    if not customer_billing_enforced():
        return
    reservation = await db.scalar(select(BillingReservation).where(
        BillingReservation.provider_operation_id == operation.id,
    ))
    if reservation is None:
        raise BillingLimitExceeded("供应商任务缺少客户计费预占，已停止自动结算")
    normalized = provider_status.strip().lower()
    if normalized in {"succeeded", "completed"}:
        supplier_actual = (
            reservation.supplier_estimate_micros
            if supplier_actual_rmb is None
            else rmb_to_micros(supplier_actual_rmb)
        )
        await capture_charge(
            db, reservation_id=reservation.id, supplier_actual_micros=supplier_actual,
            task_type=operation.job_type, model_id=None, provider_id=operation.capability,
            provider_task_id=operation.provider_task_id,
            usage_dimensions={"capability": operation.capability, "cost_source": "provider_actual" if supplier_actual_rmb is not None else "estimated_as_actual"},
        )
    elif normalized in {"failed", "rejected", "cancelled"}:
        await release_charge(
            db, reservation_id=reservation.id,
            provider_state="confirmed_failed" if normalized == "failed" else normalized,
        )
