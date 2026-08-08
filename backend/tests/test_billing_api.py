from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.core.database import Base, get_db
from app.core.security import get_current_user_id
from app.features.billing.api import router
from app.models.billing import BillingAccount, BillingLedgerEntry, BillingReservation, ProviderReconciliation, UsageEvent


@pytest.fixture()
def billing_api(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'billing-api.db'}")
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    current_user = {"id": "user-1"}

    async def setup() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as db:
            own = BillingAccount(id="account-1", owner_type="user", owner_id="user-1", available_micros=1_250_000)
            other = BillingAccount(id="account-2", owner_type="user", owner_id="user-2", available_micros=9_000_000)
            db.add_all([
                own, other,
                BillingReservation(
                    id="reservation-1", account_id=own.id, user_id="user-1",
                    idempotency_key="request-1", state="captured",
                    estimated_charge_micros=1_000_000, supplier_estimate_micros=800_000,
                    captured_charge_micros=1_000_000, supplier_actual_micros=800_000,
                    provider_task_id="provider-task-1",
                ),
                UsageEvent(
                    id="usage-1", account_id=own.id, reservation_id="reservation-1",
                    user_id="user-1", task_type="shot_video", provider_task_id="provider-task-1",
                    supplier_cost_micros=800_000, customer_charge_micros=1_000_000,
                    gross_margin_micros=200_000, usage_dimensions={"seconds": 8},
                ),
                ProviderReconciliation(
                    id="reconciliation-1", account_id=own.id, reservation_id="reservation-1",
                    usage_event_id="usage-1", provider_task_id="provider-task-1",
                    bill_reference="supplier-secret-bill", internal_supplier_cost_micros=800_000,
                    billed_supplier_cost_micros=850_000, difference_micros=50_000,
                    status="difference_requires_review",
                ),
                BillingLedgerEntry(
                    id="entry-1", account_id=own.id, entry_type="credit", idempotency_key="credit-1",
                    amount_micros=1_250_000, available_delta_micros=1_250_000,
                    reserved_delta_micros=0, available_after_micros=1_250_000,
                    reserved_after_micros=0, reason="开户充值", entry_metadata={"secret": "must-not-leak"},
                ),
                BillingLedgerEntry(
                    id="entry-2", account_id=other.id, entry_type="credit", idempotency_key="credit-2",
                    amount_micros=9_000_000, available_delta_micros=9_000_000,
                    reserved_delta_micros=0, available_after_micros=9_000_000,
                    reserved_after_micros=0, reason="其他用户充值", entry_metadata={},
                ),
            ])
            await db.commit()

    async def override_db():
        async with factory() as db:
            yield db

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_id] = lambda: current_user["id"]
    asyncio.run(setup())
    with TestClient(app) as client:
        yield client, current_user
    asyncio.run(engine.dispose())


def test_account_and_ledger_are_current_user_scoped_and_use_readable_rmb(billing_api) -> None:
    client, current_user = billing_api
    account = client.get("/api/v1/billing/account")
    assert account.status_code == 200
    assert account.json()["available_rmb"] == "1.250000"
    assert "available_micros" not in account.json()
    ledger = client.get("/api/v1/billing/ledger").json()
    assert [item["id"] for item in ledger["items"]] == ["entry-1"]
    assert "entry_metadata" not in ledger["items"][0]
    usage = client.get("/api/v1/billing/usage").json()["items"][0]
    assert usage["customer_charge_rmb"] == "1.000000"
    assert "supplier_cost_rmb" not in usage and "gross_margin_rmb" not in usage
    reconciliation = client.get("/api/v1/billing/reconciliations").json()["items"][0]
    assert reconciliation["status"] == "difference_requires_review"
    assert "bill_reference" not in reconciliation and "difference_rmb" not in reconciliation

    current_user["id"] = "user-3"
    missing = client.get("/api/v1/billing/account")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "当前用户还没有计费账户"
