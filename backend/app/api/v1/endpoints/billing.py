"""R03: user billing settings and ledger summary."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.core.time_utils import utc_now
from app.services.billing_guard import (
    default_caps_rmb,
    ensure_user_billing_settings,
    get_or_create_settings,
    ledger_totals_rmb,
    settings_summary,
)
from app.services.live_canary_policy import InvalidAccountingInput, money as _money, money_text as _text

router = APIRouter(prefix="/billing", tags=["计费额度"])


class BillingSettingsUpdate(BaseModel):
    live_calls_opt_in: Optional[bool] = None
    per_user_cap_rmb: Optional[str] = None
    per_pipeline_cap_rmb: Optional[str] = None


class BillingSettingsResponse(BaseModel):
    live_calls_opt_in: bool
    opted_in_at: Optional[str] = None
    per_user_cap_rmb: str
    per_pipeline_cap_rmb: str
    used_rmb: str
    reserved_rmb: str
    settled_rmb: str
    released_rmb: str
    defaults: dict[str, str] = Field(default_factory=dict)


class BillingLedgerSummaryResponse(BaseModel):
    used_rmb: str
    reserved_rmb: str
    settled_rmb: str
    released_rmb: str
    blocked_cap_rmb: str
    per_user_cap_rmb: str
    per_pipeline_cap_rmb: str
    live_calls_opt_in: bool


def _defaults_payload() -> dict[str, str]:
    user_cap, pipe_cap = default_caps_rmb()
    return {
        "per_user_cap_rmb": _text(user_cap),
        "per_pipeline_cap_rmb": _text(pipe_cap),
    }


@router.get("/settings", response_model=BillingSettingsResponse)
async def get_billing_settings(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> BillingSettingsResponse:
    await ensure_user_billing_settings(db, user_id)
    summary = await settings_summary(db, user_id)
    return BillingSettingsResponse(**summary, defaults=_defaults_payload())


@router.put("/settings", response_model=BillingSettingsResponse)
async def put_billing_settings(
    body: BillingSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> BillingSettingsResponse:
    settings = await get_or_create_settings(db, user_id)
    try:
        if body.per_user_cap_rmb is not None:
            settings.per_user_cap_rmb = _text(_money(body.per_user_cap_rmb, positive=True))
        if body.per_pipeline_cap_rmb is not None:
            settings.per_pipeline_cap_rmb = _text(_money(body.per_pipeline_cap_rmb, positive=True))
    except InvalidAccountingInput as exc:
        raise HTTPException(status_code=400, detail={"code": "invalid_cap", "message": str(exc)}) from exc

    if body.live_calls_opt_in is not None:
        was = bool(settings.live_calls_opt_in)
        settings.live_calls_opt_in = bool(body.live_calls_opt_in)
        if settings.live_calls_opt_in and not was:
            settings.opted_in_at = utc_now()
        if not settings.live_calls_opt_in:
            settings.opted_in_at = None

    await db.commit()
    summary = await settings_summary(db, user_id)
    return BillingSettingsResponse(**summary, defaults=_defaults_payload())


@router.get("/ledger/summary", response_model=BillingLedgerSummaryResponse)
async def get_ledger_summary(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> BillingLedgerSummaryResponse:
    settings = await ensure_user_billing_settings(db, user_id)
    totals = await ledger_totals_rmb(db, user_id=user_id)
    return BillingLedgerSummaryResponse(
        used_rmb=_text(totals["used_toward_cap"]),
        reserved_rmb=_text(totals["reserved"]),
        settled_rmb=_text(totals["settled"]),
        released_rmb=_text(totals["released"]),
        blocked_cap_rmb=_text(totals["blocked_cap"]),
        per_user_cap_rmb=settings.per_user_cap_rmb,
        per_pipeline_cap_rmb=settings.per_pipeline_cap_rmb,
        live_calls_opt_in=bool(settings.live_calls_opt_in),
    )
