from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.features.billing.reconciliation import reconcile_provider_bill
from app.features.billing.service import capture_charge, credit_account, reserve_charge
from app.models.billing import BillingAccount


@pytest_asyncio.fixture
async def settled(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'reconciliation.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        account = BillingAccount(owner_type="user", owner_id="user-1")
        db.add(account)
        await db.commit()
        await credit_account(db, account_id=account.id, amount_micros=10_000_000, actor_user_id="admin", reason="验收充值", idempotency_key="credit")
        reservation = await reserve_charge(
            db, account_id=account.id, user_id="user-1", project_id=None,
            provider_operation_id="operation", idempotency_key="request", supplier_estimate_micros=2_000_000,
        )
        await capture_charge(
            db, reservation_id=reservation.id, supplier_actual_micros=1_500_000,
            task_type="shot_video", model_id="model", provider_id="provider",
            provider_task_id="task-1", usage_dimensions={"seconds": 8},
        )
        yield db, account, reservation
    await engine.dispose()


@pytest.mark.asyncio
async def test_provider_bill_is_idempotent_and_matching_cost_keeps_account_active(settled) -> None:
    db, account, reservation = settled
    result = await reconcile_provider_bill(
        db, reservation_id=reservation.id, bill_reference="bill-1",
        billed_supplier_cost_micros=1_500_050, difference_threshold_micros=100,
    )
    duplicate = await reconcile_provider_bill(
        db, reservation_id=reservation.id, bill_reference="bill-1",
        billed_supplier_cost_micros=1_500_050, difference_threshold_micros=100,
    )
    assert result.id == duplicate.id
    assert result.status == "matched"
    assert (await db.get(BillingAccount, account.id)).status == "active"


@pytest.mark.asyncio
async def test_material_provider_bill_difference_freezes_new_charges(settled) -> None:
    db, account, reservation = settled
    result = await reconcile_provider_bill(
        db, reservation_id=reservation.id, bill_reference="bill-2",
        billed_supplier_cost_micros=2_000_000, difference_threshold_micros=100,
    )
    assert result.status == "difference_requires_review"
    assert result.difference_micros == 500_000
    assert (await db.get(BillingAccount, account.id)).status == "reconciliation_hold"
