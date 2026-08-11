from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, update
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session

from app.models.billing import BillingAccount, BillingLedgerEntry


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_customer_billing_schema_and_immutable_ledger_are_created_by_alembic(tmp_path) -> None:
    database_path = tmp_path / "billing.db"
    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite+aiosqlite:///{database_path}"
    environment.pop("E2E_REQUIRE_ISOLATED_DB", None)

    result = subprocess.run(
        [sys.executable, "scripts/upgrade_database.py"],
        cwd=BACKEND_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    engine = create_engine(f"sqlite:///{database_path}")
    inspector = inspect(engine)
    expected = {
        "billing_accounts",
        "project_billing_budgets",
        "billing_reservations",
        "billing_ledger_entries",
        "usage_events",
        "provider_reconciliations",
    }
    assert "Database migration complete: 20260809_0006" in result.stdout
    assert expected.issubset(inspector.get_table_names())

    with Session(engine) as session:
        account = BillingAccount(
            id="account-1",
            owner_type="user",
            owner_id="user-1",
            available_micros=1_000_000,
        )
        entry = BillingLedgerEntry(
            id="entry-1",
            account_id=account.id,
            entry_type="credit",
            idempotency_key="credit-1",
            amount_micros=1_000_000,
            available_delta_micros=1_000_000,
            reserved_delta_micros=0,
            available_after_micros=1_000_000,
            reserved_after_micros=0,
            reason="开户测试资金",
        )
        session.add_all([account, entry])
        session.commit()
        with pytest.raises(DatabaseError, match="append-only"):
            session.execute(
                update(BillingLedgerEntry)
                .where(BillingLedgerEntry.id == entry.id)
                .values(reason="篡改")
            )
