"""Append-only provider invoice reconciliation."""

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.billing.domain import BillingConflict
from app.models.billing import BillingAccount, BillingReservation, ProviderReconciliation, UsageEvent


async def reconcile_provider_bill(
    db: AsyncSession,
    *,
    reservation_id: str,
    bill_reference: str,
    billed_supplier_cost_micros: int,
    difference_threshold_micros: int = 0,
) -> ProviderReconciliation:
    """Record one provider bill fact and hold the account on material differences."""
    existing = await db.scalar(select(ProviderReconciliation).where(
        ProviderReconciliation.reservation_id == reservation_id,
        ProviderReconciliation.bill_reference == bill_reference,
    ))
    if existing:
        if existing.billed_supplier_cost_micros != billed_supplier_cost_micros:
            raise BillingConflict("同一供应商账单编号的金额不一致")
        return existing
    reservation = await db.get(BillingReservation, reservation_id)
    if reservation is None or reservation.state != "captured":
        raise BillingConflict("供应商账单找不到已结算的生成任务")
    usage = await db.scalar(select(UsageEvent).where(UsageEvent.reservation_id == reservation.id))
    if usage is None or usage.supplier_cost_micros is None:
        raise BillingConflict("该任务缺少供应商成本快照，暂不能自动对账")
    difference = billed_supplier_cost_micros - usage.supplier_cost_micros
    status = "matched" if abs(difference) <= difference_threshold_micros else "difference_requires_review"
    reconciliation = ProviderReconciliation(
        id=str(uuid4()), account_id=reservation.account_id, reservation_id=reservation.id,
        usage_event_id=usage.id, provider_task_id=reservation.provider_task_id,
        bill_reference=bill_reference, internal_supplier_cost_micros=usage.supplier_cost_micros,
        billed_supplier_cost_micros=billed_supplier_cost_micros,
        difference_micros=difference, status=status,
    )
    db.add(reconciliation)
    if status != "matched":
        account = await db.get(BillingAccount, reservation.account_id)
        if account:
            account.status = "reconciliation_hold"
            account.version += 1
    await db.commit()
    return reconciliation
