from __future__ import annotations

from datetime import timedelta

import pytest
import jwt

from app.core.auth_tokens import (
    ACCESS_TOKEN_TTL,
    create_access_token,
    verify_access_token,
)


def test_access_token_expires_after_fifteen_minutes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-that-is-definitely-long-enough")

    token = create_access_token("user-123")
    payload = jwt.decode(token, options={"verify_signature": False})

    assert ACCESS_TOKEN_TTL == timedelta(minutes=15)
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"
    assert 895 <= payload["exp"] - payload["iat"] <= 900
    assert verify_access_token(token) == "user-123"


def test_access_token_rejects_forged_or_refresh_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-that-is-definitely-long-enough")
    wrong_key_token = jwt.encode(
        {"sub": "attacker", "type": "access"},
        "wrong-signing-key-that-is-definitely-long-enough",
        algorithm="HS256",
    )
    refresh_token = jwt.encode(
        {"sub": "user-123", "type": "refresh"},
        "test-jwt-secret-that-is-definitely-long-enough",
        algorithm="HS256",
    )

    assert verify_access_token(wrong_key_token) is None
    assert verify_access_token(refresh_token) is None
