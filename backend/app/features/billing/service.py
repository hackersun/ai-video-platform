"""Transactional customer billing operations."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import and_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.features.billing.domain import BillingConflict, BillingLimitExceeded, InsufficientFunds, customer_charge_micros
from app.models.billing import BillingAccount, BillingLedgerEntry, BillingReservation, ProjectBillingBudget, UsageEvent


async def credit_account(
    db: AsyncSession, *, account_id: str, amount_micros: int, actor_user_id: str,
    reason: str, idempotency_key: str,
) -> BillingLedgerEntry:
    if amount_micros <= 0 or not actor_user_id.strip() or len(reason.strip()) < 2:
        raise ValueError("调账金额、操作者和中文原因必须完整")
    existing = await _ledger_by_key(db, account_id, idempotency_key)
    if existing:
        return existing
    account = await _account(db, account_id)
    result = await db.execute(
        update(BillingAccount).where(BillingAccount.id == account.id, BillingAccount.version == account.version)
        .values(available_micros=BillingAccount.available_micros + amount_micros, version=BillingAccount.version + 1, updated_at=utc_now())
    )
    if result.rowcount != 1:
        await db.rollback()
        raise BillingConflict("账户余额刚刚发生变化，请重试")
    await db.refresh(account)
    entry = _ledger(account, None, "credit", idempotency_key, amount_micros, amount_micros, 0, actor_user_id, reason)
    db.add(entry)
    await db.commit()
    return entry


async def reserve_charge(
    db: AsyncSession, *, account_id: str, user_id: str, project_id: str | None,
    provider_operation_id: str | None, idempotency_key: str, supplier_estimate_micros: int,
) -> BillingReservation:
    existing = await db.scalar(select(BillingReservation).where(
        BillingReservation.account_id == account_id,
        BillingReservation.idempotency_key == idempotency_key,
    ))
    if existing:
        if existing.supplier_estimate_micros != supplier_estimate_micros:
            raise BillingConflict("同一请求的预估费用不一致")
        return existing
    account = await _account(db, account_id)
    await _roll_billing_period(db, account)
    estimated = customer_charge_micros(supplier_estimate_micros, account.pricing_markup_bps)
    _check_account_limits(account, estimated)
    budget = await _reserve_project_budget(db, account.id, project_id, estimated)
    conditions = [
        BillingAccount.id == account.id,
        BillingAccount.version == account.version,
        BillingAccount.status == "active",
        BillingAccount.available_micros >= estimated,
        BillingAccount.active_reservations < BillingAccount.max_concurrent_jobs,
    ]
    if account.monthly_quota_micros is not None:
        conditions.append(BillingAccount.period_spent_micros + BillingAccount.reserved_micros + estimated <= BillingAccount.monthly_quota_micros)
    result = await db.execute(
        update(BillingAccount).where(and_(*conditions)).values(
            available_micros=BillingAccount.available_micros - estimated,
            reserved_micros=BillingAccount.reserved_micros + estimated,
            active_reservations=BillingAccount.active_reservations + 1,
            version=BillingAccount.version + 1,
            updated_at=utc_now(),
        )
    )
    if result.rowcount != 1:
        await db.rollback()
        raise BillingConflict("账户额度刚刚发生变化，请重试")
    await db.refresh(account)
    reservation = BillingReservation(
        account_id=account.id, user_id=user_id, project_id=project_id,
        provider_operation_id=provider_operation_id, idempotency_key=idempotency_key,
        estimated_charge_micros=estimated, supplier_estimate_micros=supplier_estimate_micros,
        markup_bps=account.pricing_markup_bps,
    )
    db.add(reservation)
    await db.flush()
    db.add(_ledger(account, reservation.id, "reserve", f"reserve:{idempotency_key}", estimated, -estimated, estimated, user_id, "生成任务费用预占"))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        duplicate = await db.scalar(select(BillingReservation).where(
            BillingReservation.account_id == account_id,
            BillingReservation.idempotency_key == idempotency_key,
        ))
        if duplicate:
            return duplicate
        raise BillingConflict("计费请求发生冲突，请重试")
    if budget:
        await db.refresh(budget)
    return reservation


async def capture_charge(
    db: AsyncSession, *, reservation_id: str, supplier_actual_micros: int,
    task_type: str, model_id: str | None, provider_id: str | None,
    provider_task_id: str | None, usage_dimensions: dict[str, Any],
) -> BillingReservation:
    reservation = await _reservation(db, reservation_id)
    actual = customer_charge_micros(supplier_actual_micros, reservation.markup_bps)
    if reservation.state == "captured":
        if reservation.captured_charge_micros != actual:
            raise BillingConflict("该任务已按不同金额结算")
        return reservation
    if reservation.state != "reserved":
        raise BillingConflict("只有预占中的任务可以结算")
    account = await _account(db, reservation.account_id)
    estimate = reservation.estimated_charge_micros
    await _update_account_for_terminal(db, account, estimate - actual, -estimate, actual, -1)
    await _settle_project_budget(db, reservation, estimate=estimate, spent_delta=actual)
    reservation.state = "captured"
    reservation.captured_charge_micros = actual
    reservation.supplier_actual_micros = supplier_actual_micros
    reservation.provider_task_id = provider_task_id or reservation.provider_task_id
    reservation.settled_at = utc_now()
    db.add(_ledger(account, reservation.id, "capture", f"capture:{reservation.id}", actual, estimate - actual, -estimate, reservation.user_id, "供应商任务成功结算"))
    db.add(UsageEvent(
        account_id=account.id, reservation_id=reservation.id, user_id=reservation.user_id,
        project_id=reservation.project_id, task_type=task_type, model_id=model_id,
        provider_id=provider_id, provider_task_id=provider_task_id,
        usage_dimensions=usage_dimensions, supplier_cost_micros=supplier_actual_micros,
        customer_charge_micros=actual, gross_margin_micros=actual - supplier_actual_micros,
    ))
    await db.commit()
    return reservation


async def release_charge(db: AsyncSession, *, reservation_id: str, provider_state: str) -> BillingReservation:
    reservation = await _reservation(db, reservation_id)
    if provider_state == "unknown" or reservation.state == "released":
        return reservation
    if provider_state not in {"confirmed_failed", "cancelled", "rejected"}:
        raise BillingConflict("只有供应商明确失败、取消或拒绝时才能释放预占")
    if reservation.state != "reserved":
        raise BillingConflict("只有预占中的任务可以释放")
    account = await _account(db, reservation.account_id)
    estimate = reservation.estimated_charge_micros
    await _update_account_for_terminal(db, account, estimate, -estimate, 0, -1)
    await _settle_project_budget(db, reservation, estimate=estimate, spent_delta=0)
    reservation.state = "released"
    reservation.settled_at = utc_now()
    db.add(_ledger(account, reservation.id, "release", f"release:{reservation.id}", estimate, estimate, -estimate, reservation.user_id, "供应商任务明确失败，释放预占"))
    await db.commit()
    return reservation


async def refund_charge(
    db: AsyncSession, *, reservation_id: str, amount_micros: int,
    actor_user_id: str, reason: str, idempotency_key: str,
) -> BillingLedgerEntry:
    reservation = await _reservation(db, reservation_id)
    existing = await _ledger_by_key(db, reservation.account_id, idempotency_key)
    if existing:
        return existing
    if reservation.state != "captured" or amount_micros <= 0 or reservation.refunded_micros + amount_micros > reservation.captured_charge_micros:
        raise BillingConflict("退款金额超过该任务可退金额")
    account = await _account(db, reservation.account_id)
    await _update_account_for_terminal(db, account, amount_micros, 0, -amount_micros, 0)
    if reservation.project_id:
        budget = await db.scalar(select(ProjectBillingBudget).where(
            ProjectBillingBudget.account_id == account.id,
            ProjectBillingBudget.project_id == reservation.project_id,
        ))
        if budget:
            budget.spent_micros -= amount_micros
            budget.version += 1
    reservation.refunded_micros += amount_micros
    entry = _ledger(account, reservation.id, "refund", idempotency_key, amount_micros, amount_micros, 0, actor_user_id, reason)
    db.add(entry)
    await db.commit()
    return entry


async def _account(db: AsyncSession, account_id: str) -> BillingAccount:
    account = await db.get(BillingAccount, account_id)
    if account is None:
        raise BillingConflict("客户计费账户不存在")
    return account


async def _roll_billing_period(db: AsyncSession, account: BillingAccount) -> None:
    now = utc_now()
    started = account.period_started_at
    if started and (started.year, started.month) == (now.year, now.month):
        return
    result = await db.execute(update(BillingAccount).where(
        BillingAccount.id == account.id, BillingAccount.version == account.version,
    ).values(period_spent_micros=0, period_started_at=now, version=BillingAccount.version + 1, updated_at=now))
    if result.rowcount != 1:
        await db.rollback()
        raise BillingConflict("账户月度额度刚刚发生变化，请重试")
    await db.refresh(account)


async def _reservation(db: AsyncSession, reservation_id: str) -> BillingReservation:
    reservation = await db.get(BillingReservation, reservation_id)
    if reservation is None:
        raise BillingConflict("计费预占记录不存在")
    return reservation


def _check_account_limits(account: BillingAccount, amount: int) -> None:
    if account.status != "active":
        raise BillingLimitExceeded("客户计费账户已暂停，请联系运营人员")
    if account.available_micros < amount:
        raise InsufficientFunds("客户余额不足，请充值后重试")
    if account.active_reservations >= account.max_concurrent_jobs:
        raise BillingLimitExceeded("并发生成任务已达上限，请等待已有任务完成")
    if account.monthly_quota_micros is not None and account.period_spent_micros + account.reserved_micros + amount > account.monthly_quota_micros:
        raise BillingLimitExceeded("本月生成额度不足，请提升额度后重试")


async def _reserve_project_budget(db: AsyncSession, account_id: str, project_id: str | None, amount: int) -> ProjectBillingBudget | None:
    if not project_id:
        return None
    budget = await db.scalar(select(ProjectBillingBudget).where(
        ProjectBillingBudget.account_id == account_id,
        ProjectBillingBudget.project_id == project_id,
    ))
    if not budget:
        return None
    if budget.spent_micros + budget.reserved_micros + amount > budget.limit_micros:
        raise BillingLimitExceeded("项目预算不足，请调整项目额度后重试")
    result = await db.execute(update(ProjectBillingBudget).where(
        ProjectBillingBudget.id == budget.id, ProjectBillingBudget.version == budget.version,
        ProjectBillingBudget.spent_micros + ProjectBillingBudget.reserved_micros + amount <= ProjectBillingBudget.limit_micros,
    ).values(reserved_micros=ProjectBillingBudget.reserved_micros + amount, version=ProjectBillingBudget.version + 1, updated_at=utc_now()))
    if result.rowcount != 1:
        await db.rollback()
        raise BillingConflict("项目预算刚刚发生变化，请重试")
    return budget


async def _settle_project_budget(db: AsyncSession, reservation: BillingReservation, *, estimate: int, spent_delta: int) -> None:
    if not reservation.project_id:
        return
    budget = await db.scalar(select(ProjectBillingBudget).where(
        ProjectBillingBudget.account_id == reservation.account_id,
        ProjectBillingBudget.project_id == reservation.project_id,
    ))
    if budget:
        budget.reserved_micros -= estimate
        budget.spent_micros += spent_delta
        budget.version += 1


async def _update_account_for_terminal(db: AsyncSession, account: BillingAccount, available_delta: int, reserved_delta: int, spent_delta: int, active_delta: int) -> None:
    result = await db.execute(update(BillingAccount).where(
        BillingAccount.id == account.id, BillingAccount.version == account.version,
    ).values(
        available_micros=BillingAccount.available_micros + available_delta,
        reserved_micros=BillingAccount.reserved_micros + reserved_delta,
        period_spent_micros=BillingAccount.period_spent_micros + spent_delta,
        active_reservations=BillingAccount.active_reservations + active_delta,
        version=BillingAccount.version + 1, updated_at=utc_now(),
    ))
    if result.rowcount != 1:
        await db.rollback()
        raise BillingConflict("账户余额刚刚发生变化，请重试")
    await db.refresh(account)


def _ledger(account: BillingAccount, reservation_id: str | None, entry_type: str, idempotency_key: str, amount: int, available_delta: int, reserved_delta: int, actor: str | None, reason: str) -> BillingLedgerEntry:
    return BillingLedgerEntry(
        id=str(uuid4()), account_id=account.id, reservation_id=reservation_id,
        entry_type=entry_type, idempotency_key=idempotency_key, amount_micros=amount,
        available_delta_micros=available_delta, reserved_delta_micros=reserved_delta,
        available_after_micros=account.available_micros,
        reserved_after_micros=account.reserved_micros,
        actor_user_id=actor, reason=reason,
    )


async def _ledger_by_key(db: AsyncSession, account_id: str, key: str) -> BillingLedgerEntry | None:
    return await db.scalar(select(BillingLedgerEntry).where(
        BillingLedgerEntry.account_id == account_id,
        BillingLedgerEntry.idempotency_key == key,
    ))
