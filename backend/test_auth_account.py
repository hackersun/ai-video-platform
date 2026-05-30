"""
Account/authentication flow tests.
"""

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


def _register(client: TestClient, suffix: str, password: str = "oldPass123") -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": f"account-{suffix}",
            "email": f"account-{suffix}@example.test",
            "password": password,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    return payload


def test_profile_update_and_change_password_persist(client: TestClient) -> None:
    suffix = uuid4().hex[:10]
    payload = _register(client, suffix)
    token = payload["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    profile_response = client.put(
        "/api/v1/auth/profile",
        json={
            "username": f"renamed-{suffix}",
            "email": f"renamed-{suffix}@example.test",
            "avatar": "https://example.test/avatar.png",
        },
        headers=headers,
    )
    assert profile_response.status_code == 200
    profile = profile_response.json()
    assert profile["username"] == f"renamed-{suffix}"
    assert profile["email"] == f"renamed-{suffix}@example.test"
    assert profile["avatar"] == "https://example.test/avatar.png"

    change_response = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "oldPass123", "new_password": "newPass123"},
        headers=headers,
    )
    assert change_response.status_code == 200

    old_login = client.post(
        "/api/v1/auth/login",
        json={"username": f"renamed-{suffix}", "password": "oldPass123"},
    )
    assert old_login.json()["success"] is False

    new_login = client.post(
        "/api/v1/auth/login",
        json={"username": f"renamed-{suffix}", "password": "newPass123"},
    )
    assert new_login.json()["success"] is True


def test_forgot_and_reset_password_flow(client: TestClient) -> None:
    suffix = uuid4().hex[:10]
    _register(client, suffix, password="beforeReset123")

    forgot_response = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": f"account-{suffix}@example.test"},
    )
    assert forgot_response.status_code == 200
    reset_token = forgot_response.json()["reset_token"]
    assert reset_token

    reset_response = client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "afterReset123"},
    )
    assert reset_response.status_code == 200

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": f"account-{suffix}", "password": "afterReset123"},
    )
    assert login_response.json()["success"] is True


def test_non_dev_mode_rejects_unsigned_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEV_MODE", "false")
    with TestClient(app) as test_client:
        response = test_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer unsigned-user-id"},
        )
    assert response.status_code == 401
