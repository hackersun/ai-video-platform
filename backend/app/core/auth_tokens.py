"""Signed, short-lived access-token contract."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt


ACCESS_TOKEN_TTL = timedelta(minutes=15)
DEFAULT_LOCAL_JWT_SECRET = "dev-jwt-secret-change-in-production"


def _jwt_secret() -> str:
    return os.getenv("JWT_SECRET_KEY", DEFAULT_LOCAL_JWT_SECRET)


def _jwt_algorithm() -> str:
    return os.getenv("JWT_ALGORITHM", "HS256")


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    now = datetime.now(timezone.utc)
    expires_at = now + (expires_delta or ACCESS_TOKEN_TTL)
    payload = {
        "sub": subject,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=_jwt_algorithm())


def verify_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[_jwt_algorithm()])
    except JWTError:
        return None
    if payload.get("type") != "access":
        return None
    subject = payload.get("sub")
    return subject if isinstance(subject, str) and subject else None
