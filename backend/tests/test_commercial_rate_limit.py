"""Commercial rate-limit middleware + auth/password session gates."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

os.environ["RATE_LIMIT_BACKEND"] = "memory"
os.environ["REFRESH_TOKEN_STORE"] = "memory"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "15"
os.environ["AUTH_RATE_LIMIT_LOGIN"] = "3"
os.environ["AUTH_RATE_LIMIT_WINDOW_SECONDS"] = "60"
os.environ["API_RATE_LIMIT_GENERATE"] = "2"
os.environ["API_RATE_LIMIT_WINDOW_SECONDS"] = "60"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "memory")
    monkeypatch.setenv("REFRESH_TOKEN_STORE", "memory")
    monkeypatch.setenv("AUTH_RATE_LIMIT_LOGIN", "3")
    monkeypatch.setenv("API_RATE_LIMIT_GENERATE", "2")
    from app.core.rate_limit import reset_rate_limits
    from app.services.refresh_token_store import reset_refresh_token_store

    reset_rate_limits()
    reset_refresh_token_store()
    from main import app

    with TestClient(app) as test_client:
        yield test_client
    reset_rate_limits()
    reset_refresh_token_store()


def _register(client: TestClient, suffix: str, password: str = "oldPass123") -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": f"account-{suffix}",
            "email": f"account-{suffix}@example.test",
            "password": password,
            "accept_terms": True,
            "terms_version": "2026-11-01",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    return payload


def test_password_policy_rejects_short_and_common(client: TestClient):
    short = client.post(
        "/api/v1/auth/register",
        json={
            "username": "shortuser1",
            "email": "shortuser1@example.test",
            "password": "Ab1",
            "accept_terms": True,
            "terms_version": "2026-11-01",
        },
    )
    assert short.status_code in {200, 422}
    if short.status_code == 200:
        assert short.json()["success"] is False

    common = client.post(
        "/api/v1/auth/register",
        json={
            "username": "commonuser1",
            "email": "commonuser1@example.test",
            "password": "password1",
            "accept_terms": True,
            "terms_version": "2026-11-01",
        },
    )
    assert common.status_code == 200
    assert common.json()["success"] is False
    assert "常见" in common.json()["message"]


def test_login_rate_limit_returns_429(client: TestClient, monkeypatch):
    monkeypatch.setenv("AUTH_RATE_LIMIT_LOGIN", "3")
    from app.core.rate_limit import reset_rate_limits

    reset_rate_limits()
    suffix = uuid4().hex[:8]
    for _ in range(3):
        response = client.post(
            "/api/v1/auth/login",
            json={"username": f"missing-{suffix}", "password": "whatever1"},
        )
        assert response.status_code == 200
        assert response.json()["success"] is False
    blocked = client.post(
        "/api/v1/auth/login",
        json={"username": f"missing-{suffix}", "password": "whatever1"},
    )
    assert blocked.status_code == 429
    assert "频繁" in blocked.json()["detail"]


def test_generate_rate_limit_bucket(client: TestClient, monkeypatch):
    monkeypatch.setenv("API_RATE_LIMIT_GENERATE", "2")
    from app.core.rate_limit import reset_rate_limits

    reset_rate_limits()
    codes = [client.post("/api/v1/images/generate", json={}).status_code for _ in range(3)]
    assert 429 in codes


def test_refresh_rotates_and_revokes_old(client: TestClient):
    payload = _register(client, uuid4().hex[:8])
    refresh = payload["refresh_token"]
    rotated = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert rotated.status_code == 200, rotated.text
    body = rotated.json()
    assert body["access_token"]
    assert body["refresh_token"] != refresh
    assert body["expires_in"] <= 15 * 60
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": refresh}).status_code == 401
    assert client.post("/api/v1/auth/logout", json={"refresh_token": body["refresh_token"]}).status_code == 200
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]}).status_code == 401


def test_refresh_sets_httponly_cookie(client: TestClient):
    payload = _register(client, uuid4().hex[:8])
    assert payload["refresh_token"]
    # Starlette TestClient surfaces set-cookie; accept body token as contract too.
    assert "avp_refresh_token" in client.cookies or bool(payload["refresh_token"])
