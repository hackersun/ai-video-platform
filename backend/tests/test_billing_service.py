from __future__ import annotations

from datetime import datetime
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.features.billing.domain import BillingLimitExceeded, InsufficientFunds
from app.features.billing.service import (
    capture_charge,
    credit_account,
    refund_charge,
    release_charge,
    reserve_charge,
)
from app.models.billing import BillingAccount, BillingLedgerEntry, BillingReservation, ProjectBillingBudget, UsageEvent


@pytest_asyncio.fixture
async def db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'billing-service.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _funded_account(db: AsyncSession, *, quota: int | None = None, concurrent: int = 4) -> BillingAccount:
    account = BillingAccount(
        owner_type="user", owner_id="user-1", monthly_quota_micros=quota,
        max_concurrent_jobs=concurrent, pricing_markup_bps=2_000,
    )
    db.add(account)
    await db.commit()
    await credit_account(db, account_id=account.id, amount_micros=10_000_000, actor_user_id="admin-1", reason="商用验收充值", idempotency_key="credit-1")
    return account


@pytest.mark.asyncio
async def test_reserve_is_idempotent_and_checks_balance_quota_and_concurrency(db: AsyncSession) -> None:
    account = await _funded_account(db, quota=5_000_000, concurrent=1)
    reservation = await reserve_charge(
        db, account_id=account.id, user_id="user-1", project_id=None,
        provider_operation_id="operation-1", idempotency_key="request-1",
        supplier_estimate_micros=2_000_000,
    )
    assert reservation.estimated_charge_micros == 2_400_000
    assert (await reserve_charge(
        db, account_id=account.id, user_id="user-1", project_id=None,
        provider_operation_id="operation-1", idempotency_key="request-1",
        supplier_estimate_micros=2_000_000,
    )).id == reservation.id
    with pytest.raises(BillingLimitExceeded, match="并发"):
        await reserve_charge(
            db, account_id=account.id, user_id="user-1", project_id=None,
            provider_operation_id="operation-2", idempotency_key="request-2",
            supplier_estimate_micros=1,
        )


@pytest.mark.asyncio
async def test_monthly_quota_rolls_to_a_new_period_before_reservation(db: AsyncSession) -> None:
    account = await _funded_account(db, quota=2_000_000)
    account.period_spent_micros = 2_000_000
    account.period_started_at = datetime(2020, 1, 1)
    await db.commit()
    await reserve_charge(
        db, account_id=account.id, user_id="user-1", project_id=None,
        provider_operation_id="period-operation", idempotency_key="period-request",
        supplier_estimate_micros=1_000_000,
    )
    await db.refresh(account)
    assert account.period_spent_micros == 0
    assert account.reserved_micros == 1_200_000

    account.max_concurrent_jobs = 4
    account.available_micros = 100
    await db.commit()
    with pytest.raises(InsufficientFunds, match="余额不足"):
        await reserve_charge(
            db, account_id=account.id, user_id="user-1", project_id=None,
            provider_operation_id="operation-3", idempotency_key="request-3",
            supplier_estimate_micros=1_000,
        )


@pytest.mark.asyncio
async def test_project_budget_capture_release_refund_and_usage_are_append_only(db: AsyncSession) -> None:
    account = await _funded_account(db)
    project_budget = ProjectBillingBudget(account_id=account.id, project_id="project-1", limit_micros=3_000_000)
    db.add(project_budget)
    await db.commit()
    reservation = await reserve_charge(
        db, account_id=account.id, user_id="user-1", project_id="project-1",
        provider_operation_id="operation-1", idempotency_key="request-1",
        supplier_estimate_micros=2_000_000,
    )
    with pytest.raises(BillingLimitExceeded, match="项目预算"):
        await reserve_charge(
            db, account_id=account.id, user_id="user-1", project_id="project-1",
            provider_operation_id="operation-2", idempotency_key="request-2",
            supplier_estimate_micros=1_000_000,
        )
    await capture_charge(
        db, reservation_id=reservation.id, supplier_actual_micros=1_500_000,
        task_type="shot_video", model_id="video-model", provider_id="provider-1",
        provider_task_id="provider-task-1", usage_dimensions={"seconds": 8},
    )
    settled = await db.get(BillingReservation, reservation.id)
    assert settled.state == "captured"
    assert settled.captured_charge_micros == 1_800_000
    assert (await db.scalar(select(UsageEvent).where(UsageEvent.reservation_id == reservation.id))).gross_margin_micros == 300_000
    await refund_charge(db, reservation_id=reservation.id, amount_micros=300_000, actor_user_id="admin-1", reason="供应商质量退款", idempotency_key="refund-1")
    await refund_charge(db, reservation_id=reservation.id, amount_micros=300_000, actor_user_id="admin-1", reason="供应商质量退款", idempotency_key="refund-1")
    assert (await db.get(BillingReservation, reservation.id)).refunded_micros == 300_000

    released = await reserve_charge(
        db, account_id=account.id, user_id="user-1", project_id=None,
        provider_operation_id="operation-3", idempotency_key="request-3", supplier_estimate_micros=100_000,
    )
    await release_charge(db, reservation_id=released.id, provider_state="unknown")
    assert (await db.get(BillingReservation, released.id)).state == "reserved"
    await release_charge(db, reservation_id=released.id, provider_state="confirmed_failed")
    assert (await db.get(BillingReservation, released.id)).state == "released"
    assert len((await db.scalars(select(BillingLedgerEntry))).all()) == 6
