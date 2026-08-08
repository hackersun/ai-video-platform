from __future__ import annotations

import asyncio
from sqlalchemy import select
from app.models.user_session import UserSession


def test_login_sets_http_only_cookies_and_refresh_rotates(session_api) -> None:
    client, factory = session_api
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "api-session-user", "password": "CommercialPass123!"},
    )
    assert login.status_code == 200
    assert login.json()["success"] is True
    set_cookie = login.headers.get_list("set-cookie")
    assert any("access_token=" in item and "HttpOnly" in item for item in set_cookie)
    assert any("refresh_token=" in item and "HttpOnly" in item for item in set_cookie)
    original_refresh = client.cookies.get("refresh_token")
    assert original_refresh

    refreshed = client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": client.cookies.get("csrf_token")},
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"]
    assert client.cookies.get("refresh_token") != original_refresh

    async def stored_sessions() -> list[UserSession]:
        async with factory() as db:
            return list((await db.execute(select(UserSession))).scalars())

    sessions = asyncio.run(stored_sessions())
    assert len(sessions) == 2
    assert sum(item.revoked_at is None for item in sessions) == 1


def test_logout_revokes_refresh_session_and_clears_cookies(session_api) -> None:
    client, factory = session_api
    client.post(
        "/api/v1/auth/login",
        json={"username": "api-session-user", "password": "CommercialPass123!"},
    )
    logout = client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": client.cookies.get("csrf_token")},
    )

    assert logout.status_code == 200
    assert logout.json()["message"] == "已安全退出登录"
    assert client.cookies.get("refresh_token") is None

    async def active_count() -> int:
        async with factory() as db:
            sessions = list((await db.execute(select(UserSession))).scalars())
            return sum(item.revoked_at is None for item in sessions)

    assert asyncio.run(active_count()) == 0


def test_password_change_revokes_all_existing_refresh_sessions(session_api) -> None:
    client, _ = session_api
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "api-session-user", "password": "CommercialPass123!"},
    )
    access_token = login.json()["access_token"]

    changed = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "current_password": "CommercialPass123!",
            "new_password": "ReplacementPass456!",
        },
    )
    assert changed.status_code == 200

    refreshed = client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": client.cookies.get("csrf_token")},
    )
    assert refreshed.status_code == 401
    assert "失效" in refreshed.json()["detail"]
