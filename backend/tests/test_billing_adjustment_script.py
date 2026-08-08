from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_operator_adjustment_is_idempotent_and_reports_readable_balance(tmp_path) -> None:
    database = tmp_path / "operator-billing.db"
    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite+aiosqlite:///{database}"
    environment.pop("E2E_REQUIRE_ISOLATED_DB", None)
    subprocess.run([sys.executable, "scripts/upgrade_database.py"], cwd=BACKEND_ROOT, env=environment, check=True, capture_output=True)
    command = [
        sys.executable, "scripts/adjust_billing_balance.py",
        "--user-id", "user-1", "--amount-rmb", "12.50",
        "--actor-user-id", "operator-1", "--reason", "商用开户充值",
        "--idempotency-key", "opening-credit-1",
    ]
    first = subprocess.run(command, cwd=BACKEND_ROOT, env=environment, check=True, capture_output=True, text=True)
    second = subprocess.run(command, cwd=BACKEND_ROOT, env=environment, check=True, capture_output=True, text=True)
    assert json.loads(first.stdout)["available_rmb"] == "12.500000"
    assert json.loads(second.stdout)["available_rmb"] == "12.500000"
