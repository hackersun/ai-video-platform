from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.features.billing.domain import BillingLimitExceeded
from app.features.billing.service import credit_account
from app.models.billing import BillingAccount, BillingReservation
from app.models.novel import Novel
from app.models.series_production_run import SeriesProductionRun
from app.services.live_canary_budget import bind_provider_operation_task, prepare_provider_operation, settle_provider_operation


@pytest_asyncio.fixture
async def db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'billing-live.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _run(db: AsyncSession) -> SeriesProductionRun:
    user_id = f"user-{uuid4()}"
    novel = Novel(id=str(uuid4()), user_id=user_id, title="商用计费验收", status="draft")
    run = SeriesProductionRun(
        id=str(uuid4()), user_id=user_id, novel_id=novel.id, series_plan_version="v1",
        idempotency_key=str(uuid4()), status="created", requested_stages=[], model_bindings={},
        budget_policy={"max_rmb": "10.00"}, cost_summary={}, gate_summary={}, run_metadata={}, episodes=[], version=1,
    )
    db.add_all([novel, run])
    await db.commit()
    return run


@pytest.mark.asyncio
async def test_provider_operation_requires_customer_account_when_billing_is_enforced(db, monkeypatch) -> None:
    monkeypatch.setenv("CUSTOMER_BILLING_MODE", "enforced")
    run = await _run(db)
    with pytest.raises(BillingLimitExceeded, match="计费账户"):
        await prepare_provider_operation(
            db, run, capability="video", job_type="shot_video", job_id="job-1",
            reservation_id="reservation-1", estimate_rmb=Decimal("2.00"),
        )
    assert run.cost_summary == {}


@pytest.mark.asyncio
async def test_live_budget_and_customer_charge_are_both_reserved_and_settled(db, monkeypatch) -> None:
    monkeypatch.setenv("CUSTOMER_BILLING_MODE", "enforced")
    run = await _run(db)
    account = BillingAccount(owner_type="user", owner_id=run.user_id, pricing_markup_bps=1_000)
    db.add(account)
    await db.commit()
    await credit_account(db, account_id=account.id, amount_micros=5_000_000, actor_user_id="admin", reason="商用验收充值", idempotency_key="credit")
    operation = await prepare_provider_operation(
        db, run, capability="video", job_type="shot_video", job_id="job-1",
        reservation_id="reservation-1", estimate_rmb=Decimal("2.00"),
    )
    await bind_provider_operation_task(db, operation, provider_task_id="provider-task-1")
    await settle_provider_operation(
        db, operation_id=operation.id, user_id=run.user_id, run_id=run.id,
        reservation_id="reservation-1", capability="video", job_id="job-1",
        provider_task_id="provider-task-1", provider_status="completed", actual_rmb="1.50",
    )
    await db.refresh(account)
    billing = await db.scalar(select(BillingReservation).where(BillingReservation.provider_operation_id == operation.id))
    assert billing.state == "captured"
    assert billing.captured_charge_micros == 1_650_000
    assert account.available_micros == 3_350_000
    assert run.cost_summary["spent_rmb"] == "1.50"
