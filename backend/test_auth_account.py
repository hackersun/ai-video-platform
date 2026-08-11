"""
Account/authentication flow tests.
"""

from __future__ import annotations

import base64
import json
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


def _register(client: TestClient, suffix: str, password: str = "OldCommercial123!") -> dict:
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
    verification_token = payload["verification_token"]
    verified = client.post(
        "/api/v1/auth/verify-email",
        json={"token": verification_token},
    )
    assert verified.status_code == 200
    return verified.json()


def _dev_style_token(user_id: str) -> str:
    payload = base64.urlsafe_b64encode(
        json.dumps({"sub": user_id, "exp": 4_102_444_800}).encode("utf-8")
    ).decode("ascii").rstrip("=")
    return f"dev.{payload}.sig"


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
        json={"current_password": "OldCommercial123!", "new_password": "NewCommercial123!"},
        headers=headers,
    )
    assert change_response.status_code == 200

    old_login = client.post(
        "/api/v1/auth/login",
        json={"username": f"renamed-{suffix}", "password": "OldCommercial123!"},
    )
    assert old_login.json()["success"] is False

    new_login = client.post(
        "/api/v1/auth/login",
        json={"username": f"renamed-{suffix}", "password": "NewCommercial123!"},
    )
    assert new_login.json()["success"] is True


def test_forgot_and_reset_password_flow(client: TestClient) -> None:
    suffix = uuid4().hex[:10]
    _register(client, suffix, password="BeforeReset123!")

    forgot_response = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": f"account-{suffix}@example.test"},
    )
    assert forgot_response.status_code == 200
    reset_token = forgot_response.json()["reset_token"]
    assert reset_token

    reset_response = client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "AfterReset123!"},
    )
    assert reset_response.status_code == 200

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": f"account-{suffix}", "password": "AfterReset123!"},
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


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/auth/me",
        "/api/v1/novels",
        "/api/v1/llm/configs",
        "/api/v1/video/jobs",
    ],
)
def test_non_dev_mode_rejects_dev_payload_tokens(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    monkeypatch.setenv("DEV_MODE", "false")
    with TestClient(app) as test_client:
        response = test_client.get(
            path,
            headers={"Authorization": f"Bearer {_dev_style_token('frontend-dev-user')}"},
        )
    assert response.status_code == 401
