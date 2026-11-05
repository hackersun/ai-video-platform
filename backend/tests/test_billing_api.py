"""R03: billing settings + ledger summary API (per-user authz)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from init_db import init_db
from main import app


@pytest.fixture(scope="module", autouse=True)
def _init_database() -> None:
    init_db()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DEV_MODE", "true")
    return TestClient(app)


def _h(uid: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {uid}"}


def test_billing_settings_get_put_and_cross_user_isolation(client: TestClient) -> None:
    a, b = f"bill-a-{uuid4()}", f"bill-b-{uuid4()}"
    mine = client.get("/api/v1/billing/settings", headers=_h(a))
    assert mine.status_code == 200
    body = mine.json()
    assert body["live_calls_opt_in"] is False
    assert "per_user_cap_rmb" in body and "defaults" in body

    updated = client.put(
        "/api/v1/billing/settings",
        headers=_h(a),
        json={"live_calls_opt_in": True, "per_user_cap_rmb": "120.00", "per_pipeline_cap_rmb": "30.00"},
    )
    assert updated.status_code == 200
    assert updated.json()["live_calls_opt_in"] is True
    assert updated.json()["per_user_cap_rmb"] == "120.00"
    assert updated.json()["opted_in_at"]

    other = client.get("/api/v1/billing/settings", headers=_h(b))
    assert other.status_code == 200
    assert other.json()["live_calls_opt_in"] is False
    assert other.json()["per_user_cap_rmb"] != "120.00" or other.json()["live_calls_opt_in"] is False

    summary = client.get("/api/v1/billing/ledger/summary", headers=_h(a))
    assert summary.status_code == 200
    assert summary.json()["live_calls_opt_in"] is True
    assert summary.json()["used_rmb"] == "0.00"

    # User B cannot see A's opted-in state via summary
    assert client.get("/api/v1/billing/ledger/summary", headers=_h(b)).json()["live_calls_opt_in"] is False


def test_invalid_cap_rejected(client: TestClient) -> None:
    uid = f"bill-bad-{uuid4()}"
    resp = client.put(
        "/api/v1/billing/settings",
        headers=_h(uid),
        json={"per_user_cap_rmb": "-1"},
    )
    assert resp.status_code == 400
