from __future__ import annotations

from uuid import uuid4

import pytest

from app.services.password_policy import PasswordPolicyError, validate_password


@pytest.mark.parametrize(
    ("password", "message"),
    [
        ("Short1!", "至少需要 12 位"),
        ("password123!", "过于常见"),
        ("alllowercase123!", "大写字母"),
    ],
)
def test_password_policy_rejects_commercially_weak_passwords(password, message) -> None:
    with pytest.raises(PasswordPolicyError, match=message):
        validate_password(password, username="merchant", email="merchant@example.test")


def test_registration_requires_email_verification_before_login(registration_client) -> None:
    suffix = uuid4().hex[:8]
    username = f"verify-{suffix}"
    payload = {
        "username": username,
        "email": f"{username}@example.test",
        "password": "CommercialPass123!",
    }
    registered = registration_client.post("/api/v1/auth/register", json=payload)

    assert registered.status_code == 200
    assert registered.json()["success"] is True
    assert registered.json()["message"] == "注册申请已提交，请验证邮箱后登录"
    assert registered.json()["access_token"] is None
    verification_token = registered.json()["verification_token"]
    assert verification_token

    pending_login = registration_client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": payload["password"]},
    )
    assert pending_login.json()["success"] is False
    assert pending_login.json()["message"] == "请先完成邮箱验证"

    verified = registration_client.post(
        "/api/v1/auth/verify-email",
        json={"token": verification_token},
    )
    assert verified.status_code == 200
    assert verified.json()["success"] is True
    assert verified.json()["message"] == "邮箱验证成功，已为你登录"
    assert verified.json()["access_token"]


def test_duplicate_registration_uses_same_public_response(registration_client) -> None:
    suffix = uuid4().hex[:8]
    payload = {
        "username": f"duplicate-{suffix}",
        "email": f"duplicate-{suffix}@example.test",
        "password": "CommercialPass123!",
    }
    first = registration_client.post("/api/v1/auth/register", json=payload).json()
    second = registration_client.post("/api/v1/auth/register", json=payload).json()

    assert second["success"] is True
    assert second["message"] == first["message"]
    assert second.get("verification_token") is None


def test_registration_reports_service_unavailable_when_persistence_fails(
    registration_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.v1.endpoints import auth

    def fail_to_queue(*_args, **_kwargs):
        raise RuntimeError("simulated outbox failure")

    monkeypatch.setattr(auth, "queue_auth_notification", fail_to_queue)
    suffix = uuid4().hex[:8]
    response = registration_client.post(
        "/api/v1/auth/register",
        json={
            "username": f"unavailable-{suffix}",
            "email": f"unavailable-{suffix}@example.test",
            "password": "CommercialPass123!",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "注册服务暂时不可用，请稍后重试"
