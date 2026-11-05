"""R03: fail-closed spend caps and opt-in gate for live provider calls."""

from __future__ import annotations

import os
from decimal import Decimal
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.models.billing import BillingLedgerEntry, UserBillingSettings
from app.services.live_canary_policy import BudgetExceeded, money as _money, money_text as _text


DEFAULT_USER_CAP_RMB = Decimal("200.00")
DEFAULT_PIPELINE_CAP_RMB = Decimal("50.00")


class LiveCallsNotOptedIn(BudgetExceeded):
    """User has not opted into paid live provider calls."""


class SpendCapExceeded(BudgetExceeded):
    """Per-user or per-pipeline RMB cap would be exceeded."""


def default_caps_rmb(*, environ: Optional[dict[str, str]] = None) -> tuple[Decimal, Decimal]:
    source = os.environ if environ is None else environ
    user_cap = _money(source.get("BILLING_PER_USER_CAP_RMB") or DEFAULT_USER_CAP_RMB, positive=True)
    pipe_cap = _money(source.get("BILLING_PER_PIPELINE_CAP_RMB") or DEFAULT_PIPELINE_CAP_RMB, positive=True)
    return user_cap, pipe_cap


async def get_or_create_settings(db: AsyncSession, user_id: str) -> UserBillingSettings:
    row = await db.get(UserBillingSettings, user_id)
    if row is not None:
        return row
    user_cap, pipe_cap = default_caps_rmb()
    row = UserBillingSettings(
        user_id=user_id,
        live_calls_opt_in=False,
        opted_in_at=None,
        per_user_cap_rmb=_text(user_cap),
        per_pipeline_cap_rmb=_text(pipe_cap),
    )
    db.add(row)
    await db.flush()
    return row


async def ensure_user_billing_settings(db: AsyncSession, user_id: str) -> UserBillingSettings:
    row = await get_or_create_settings(db, user_id)
    await db.commit()
    await db.refresh(row)
    return row


def _live_statuses() -> tuple[str, ...]:
    return ("reserved", "settled")


async def ledger_totals_rmb(
    db: AsyncSession,
    *,
    user_id: str,
    pipeline_id: Optional[str] = None,
) -> dict[str, Decimal]:
    """Sum ledger amounts; fake rows are excluded from every total."""
    query = select(BillingLedgerEntry).where(
        BillingLedgerEntry.user_id == user_id,
        BillingLedgerEntry.is_fake.is_(False),
    )
    if pipeline_id:
        query = query.where(BillingLedgerEntry.pipeline_id == pipeline_id)
    rows = list((await db.scalars(query)).all())
    out = {
        "reserved": Decimal("0.00"),
        "settled": Decimal("0.00"),
        "released": Decimal("0.00"),
        "blocked_cap": Decimal("0.00"),
        "used_toward_cap": Decimal("0.00"),
    }
    for row in rows:
        amount = _money(row.actual_cost_rmb if row.status == "settled" and row.actual_cost_rmb else row.estimated_cost_rmb)
        if row.status == "reserved":
            out["reserved"] += amount
            out["used_toward_cap"] += amount
        elif row.status == "settled":
            out["settled"] += amount
            out["used_toward_cap"] += amount
        elif row.status == "released":
            out["released"] += amount
        elif row.status == "blocked_cap":
            out["blocked_cap"] += amount
    for key, value in list(out.items()):
        out[key] = _money(value)
    return out


async def _find_entry(
    db: AsyncSession, *, user_id: str, reservation_id: str
) -> Optional[BillingLedgerEntry]:
    return await db.scalar(
        select(BillingLedgerEntry).where(
            BillingLedgerEntry.user_id == user_id,
            BillingLedgerEntry.reservation_id == reservation_id,
        )
    )


async def record_blocked_cap(
    db: AsyncSession,
    *,
    user_id: str,
    reservation_id: str,
    estimate_rmb: Decimal,
    reason: str,
    novel_id: Optional[str] = None,
    pipeline_id: Optional[str] = None,
    series_run_id: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    capability: Optional[str] = None,
    units: Optional[str] = None,
    is_fake: bool = False,
    commit: bool = True,
) -> BillingLedgerEntry:
    existing = await _find_entry(db, user_id=user_id, reservation_id=reservation_id)
    if existing is not None:
        return existing
    entry = BillingLedgerEntry(
        id=str(uuid4()),
        user_id=user_id,
        novel_id=novel_id,
        pipeline_id=pipeline_id,
        series_run_id=series_run_id,
        provider=provider,
        model=model,
        capability=capability,
        units=units,
        estimated_cost_rmb=_text(_money(estimate_rmb, positive=True)),
        status="blocked_cap",
        reservation_id=reservation_id,
        is_fake=bool(is_fake),
        detail=reason,
    )
    db.add(entry)
    if commit:
        await db.commit()
    else:
        await db.flush()
    return entry


async def assert_may_reserve(
    db: AsyncSession,
    *,
    user_id: str,
    estimate_rmb: Decimal,
    reservation_id: str,
    is_fake: bool = False,
    novel_id: Optional[str] = None,
    pipeline_id: Optional[str] = None,
    series_run_id: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    capability: Optional[str] = None,
    units: Optional[str] = None,
    commit: bool = True,
) -> None:
    """Fail-closed: require opt-in and headroom under caps (skipped for fake)."""
    if is_fake:
        return
    settings = await get_or_create_settings(db, user_id)
    estimate = _money(estimate_rmb, positive=True)
    if not settings.live_calls_opt_in:
        await record_blocked_cap(
            db,
            user_id=user_id,
            reservation_id=reservation_id,
            estimate_rmb=estimate,
            reason="live_calls_not_opted_in",
            novel_id=novel_id,
            pipeline_id=pipeline_id,
            series_run_id=series_run_id,
            provider=provider,
            model=model,
            capability=capability,
            units=units,
            commit=commit,
        )
        raise LiveCallsNotOptedIn("live calls require explicit opt-in")

    user_totals = await ledger_totals_rmb(db, user_id=user_id)
    user_cap = _money(settings.per_user_cap_rmb, positive=True)
    if user_totals["used_toward_cap"] + estimate > user_cap:
        await record_blocked_cap(
            db,
            user_id=user_id,
            reservation_id=reservation_id,
            estimate_rmb=estimate,
            reason="per_user_cap_exceeded",
            novel_id=novel_id,
            pipeline_id=pipeline_id,
            series_run_id=series_run_id,
            provider=provider,
            model=model,
            capability=capability,
            units=units,
            commit=commit,
        )
        raise SpendCapExceeded("per-user spend cap would be exceeded")

    if pipeline_id:
        pipe_totals = await ledger_totals_rmb(db, user_id=user_id, pipeline_id=pipeline_id)
        pipe_cap = _money(settings.per_pipeline_cap_rmb, positive=True)
        if pipe_totals["used_toward_cap"] + estimate > pipe_cap:
            await record_blocked_cap(
                db,
                user_id=user_id,
                reservation_id=reservation_id,
                estimate_rmb=estimate,
                reason="per_pipeline_cap_exceeded",
                novel_id=novel_id,
                pipeline_id=pipeline_id,
                series_run_id=series_run_id,
                provider=provider,
                model=model,
                capability=capability,
                units=units,
                commit=commit,
            )
            raise SpendCapExceeded("per-pipeline spend cap would be exceeded")


async def write_reservation_ledger(
    db: AsyncSession,
    *,
    user_id: str,
    reservation_id: str,
    estimate_rmb: Decimal,
    is_fake: bool = False,
    novel_id: Optional[str] = None,
    pipeline_id: Optional[str] = None,
    series_run_id: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    capability: Optional[str] = None,
    units: Optional[str] = None,
    commit: bool = False,
) -> BillingLedgerEntry:
    existing = await _find_entry(db, user_id=user_id, reservation_id=reservation_id)
    if existing is not None:
        return existing
    entry = BillingLedgerEntry(
        id=str(uuid4()),
        user_id=user_id,
        novel_id=novel_id,
        pipeline_id=pipeline_id,
        series_run_id=series_run_id,
        provider=provider,
        model=model,
        capability=capability,
        units=units,
        estimated_cost_rmb=_text(_money(estimate_rmb, positive=True)),
        status="reserved",
        reservation_id=reservation_id,
        is_fake=bool(is_fake),
    )
    db.add(entry)
    if commit:
        await db.commit()
    else:
        await db.flush()
    return entry


async def settle_ledger_entry(
    db: AsyncSession, *, user_id: str, reservation_id: str, actual_rmb: Decimal, commit: bool = False
) -> Optional[BillingLedgerEntry]:
    entry = await _find_entry(db, user_id=user_id, reservation_id=reservation_id)
    if entry is None:
        return None
    if entry.status == "settled":
        return entry
    entry.status = "settled"
    entry.actual_cost_rmb = _text(_money(actual_rmb))
    entry.updated_at = utc_now()
    if commit:
        await db.commit()
    else:
        await db.flush()
    return entry


async def release_ledger_entry(
    db: AsyncSession, *, user_id: str, reservation_id: str, commit: bool = False
) -> Optional[BillingLedgerEntry]:
    entry = await _find_entry(db, user_id=user_id, reservation_id=reservation_id)
    if entry is None:
        return None
    if entry.status == "released":
        return entry
    entry.status = "released"
    entry.updated_at = utc_now()
    if commit:
        await db.commit()
    else:
        await db.flush()
    return entry


async def settings_summary(db: AsyncSession, user_id: str) -> dict[str, Any]:
    settings = await get_or_create_settings(db, user_id)
    totals = await ledger_totals_rmb(db, user_id=user_id)
    return {
        "live_calls_opt_in": bool(settings.live_calls_opt_in),
        "opted_in_at": settings.opted_in_at.isoformat() if settings.opted_in_at else None,
        "per_user_cap_rmb": settings.per_user_cap_rmb,
        "per_pipeline_cap_rmb": settings.per_pipeline_cap_rmb,
        "used_rmb": _text(totals["used_toward_cap"]),
        "reserved_rmb": _text(totals["reserved"]),
        "settled_rmb": _text(totals["settled"]),
        "released_rmb": _text(totals["released"]),
    }
