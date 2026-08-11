from __future__ import annotations

from fastapi.testclient import TestClient


def test_cookie_authenticated_write_requires_matching_csrf_header(session_api) -> None:
    client, _ = session_api
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "api-session-user", "password": "CommercialPass123!"},
    )
    assert login.status_code == 200
    csrf_token = client.cookies.get("csrf_token")
    assert csrf_token

    missing = client.put(
        "/api/v1/auth/profile",
        json={
            "username": "api-session-user",
            "email": "api-session@example.test",
            "avatar": None,
        },
    )
    assert missing.status_code == 403
    assert missing.json()["detail"] == "页面安全校验已过期，请刷新页面后重试"

    accepted = client.put(
        "/api/v1/auth/profile",
        headers={"X-CSRF-Token": csrf_token},
        json={
            "username": "api-session-user",
            "email": "api-session@example.test",
            "avatar": None,
        },
    )
    assert accepted.status_code == 200


def test_bearer_authenticated_write_remains_compatible_without_csrf(session_api) -> None:
    client, _ = session_api
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "api-session-user", "password": "CommercialPass123!"},
    )
    access_token = login.json()["access_token"]
    client.cookies.clear()

    response = client.put(
        "/api/v1/auth/profile",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "username": "api-session-user",
            "email": "api-session@example.test",
            "avatar": None,
        },
    )
    assert response.status_code == 200
