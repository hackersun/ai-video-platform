from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.services.auth_rate_limit import (
    InMemoryRateLimiter,
    RateLimitExceeded,
    reset_local_rate_limits,
)
from main import app


@pytest.mark.anyio
async def test_memory_limiter_blocks_only_after_the_allowed_attempts() -> None:
    clock_value = 100.0
    limiter = InMemoryRateLimiter(clock=lambda: clock_value)

    await limiter.check("login:user", limit=2, window_seconds=60)
    await limiter.check("login:user", limit=2, window_seconds=60)
    with pytest.raises(RateLimitExceeded, match="操作过于频繁"):
        await limiter.check("login:user", limit=2, window_seconds=60)


def test_login_endpoint_returns_chinese_rate_limit_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DEV_MODE", "true")
    monkeypatch.setenv("AUTH_RATE_LIMIT_LOGIN", "2")
    reset_local_rate_limits()
    username = f"unknown-{uuid4().hex}"

    with TestClient(app) as client:
        responses = [
            client.post(
                "/api/v1/auth/login",
                json={"username": username, "password": "WrongCommercial123!"},
            )
            for _ in range(3)
        ]

    assert [response.status_code for response in responses] == [200, 200, 429]
    assert responses[-1].json()["detail"] == "操作过于频繁，请稍后再试"
