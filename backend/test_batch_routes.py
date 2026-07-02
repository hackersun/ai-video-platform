"""
Batch route mounting tests.
"""

from __future__ import annotations

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


def _auth_headers(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


def test_batch_queue_list_route_matches_frontend_path(client: TestClient) -> None:
    response = client.get("/api/v1/batch/list", headers=_auth_headers("batch-route-user"))

    assert response.status_code == 200
    assert response.json() == {"total": 0, "jobs": []}
