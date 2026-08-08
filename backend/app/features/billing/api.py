"""Authenticated read-only customer billing API."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.features.billing.domain import micros_to_rmb_text
from app.models.billing import BillingAccount, BillingLedgerEntry, ProviderReconciliation, UsageEvent


router = APIRouter(prefix="/billing", tags=["客户账务"])


async def _current_account(db: AsyncSession, user_id: str) -> BillingAccount:
    account = await db.scalar(select(BillingAccount).where(
        BillingAccount.owner_type == "user", BillingAccount.owner_id == user_id,
    ))
    if account is None:
        raise HTTPException(status_code=404, detail="当前用户还没有计费账户")
    return account


def _money(value: int | None) -> str | None:
    return None if value is None else micros_to_rmb_text(value)


@router.get("/account")
async def get_billing_account(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    account = await _current_account(db, user_id)
    return {
        "id": account.id, "currency": account.currency, "status": account.status,
        "available_rmb": _money(account.available_micros),
        "reserved_rmb": _money(account.reserved_micros),
        "period_spent_rmb": _money(account.period_spent_micros),
        "monthly_quota_rmb": _money(account.monthly_quota_micros),
        "active_reservations": account.active_reservations,
        "max_concurrent_jobs": account.max_concurrent_jobs,
    }


@router.get("/ledger")
async def list_billing_ledger(
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    account = await _current_account(db, user_id)
    rows = list((await db.scalars(select(BillingLedgerEntry).where(
        BillingLedgerEntry.account_id == account.id,
    ).order_by(BillingLedgerEntry.created_at.desc()).limit(limit).offset(offset))).all())
    return {"items": [{
        "id": row.id, "entry_type": row.entry_type, "reservation_id": row.reservation_id,
        "amount_rmb": _money(row.amount_micros),
        "available_delta_rmb": _money(row.available_delta_micros),
        "reserved_delta_rmb": _money(row.reserved_delta_micros),
        "available_after_rmb": _money(row.available_after_micros),
        "reserved_after_rmb": _money(row.reserved_after_micros),
        "reason": row.reason, "created_at": row.created_at,
    } for row in rows], "limit": limit, "offset": offset}


@router.get("/usage")
async def list_billing_usage(
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    account = await _current_account(db, user_id)
    rows = list((await db.scalars(select(UsageEvent).where(
        UsageEvent.account_id == account.id,
    ).order_by(UsageEvent.created_at.desc()).limit(limit).offset(offset))).all())
    return {"items": [{
        "id": row.id, "task_type": row.task_type, "model_id": row.model_id,
        "provider_id": row.provider_id, "provider_task_id": row.provider_task_id,
        "customer_charge_rmb": _money(row.customer_charge_micros),
        "created_at": row.created_at,
    } for row in rows], "limit": limit, "offset": offset}


@router.get("/reconciliations")
async def list_provider_reconciliations(
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    account = await _current_account(db, user_id)
    rows = list((await db.scalars(select(ProviderReconciliation).where(
        ProviderReconciliation.account_id == account.id,
    ).order_by(ProviderReconciliation.created_at.desc()).limit(limit).offset(offset))).all())
    return {"items": [{
        "id": row.id, "provider_task_id": row.provider_task_id,
        "status": row.status, "created_at": row.created_at,
    } for row in rows], "limit": limit, "offset": offset}
