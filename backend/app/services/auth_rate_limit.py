"""Authentication endpoint rate limiting with Redis in commercial environments."""

from __future__ import annotations

import asyncio
import hashlib
import os
import time
from collections.abc import Callable

from fastapi import Request

from app.core.runtime_environment import AppEnvironment, effective_environment


class RateLimitExceeded(RuntimeError):
    pass


class InMemoryRateLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._attempts: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()

    async def check(self, key: str, *, limit: int, window_seconds: int) -> None:
        now = self._clock()
        cutoff = now - window_seconds
        async with self._lock:
            attempts = [item for item in self._attempts.get(key, []) if item > cutoff]
            if len(attempts) >= limit:
                raise RateLimitExceeded("操作过于频繁，请稍后再试")
            attempts.append(now)
            self._attempts[key] = attempts

    def reset(self) -> None:
        self._attempts.clear()


_local_limiter = InMemoryRateLimiter()
_DEFAULT_LIMITS = {"login": 10, "register": 5, "forgot": 5, "reset": 10, "verify": 10}


def reset_local_rate_limits() -> None:
    _local_limiter.reset()


def _privacy_safe_key(action: str, request: Request, identity: str) -> str:
    client_host = request.client.host if request.client else "unknown"
    digest = hashlib.sha256(identity.strip().lower().encode("utf-8")).hexdigest()[:24]
    return f"auth-rate:{action}:{client_host}:{digest}"


async def _check_redis(key: str, *, limit: int, window_seconds: int) -> None:
    from redis.asyncio import Redis

    redis_url = os.environ["REDIS_URL"]
    client = Redis.from_url(redis_url, decode_responses=True)
    script = """
    local current = redis.call('INCR', KEYS[1])
    if current == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
    return current
    """
    try:
        current = int(await client.eval(script, 1, key, window_seconds))
    finally:
        await client.aclose()
    if current > limit:
        raise RateLimitExceeded("操作过于频繁，请稍后再试")


async def enforce_auth_rate_limit(action: str, request: Request, identity: str) -> None:
    default_limit = _DEFAULT_LIMITS[action]
    limit = max(1, int(os.getenv(f"AUTH_RATE_LIMIT_{action.upper()}", default_limit)))
    window = max(1, int(os.getenv("AUTH_RATE_LIMIT_WINDOW_SECONDS", "60")))
    key = _privacy_safe_key(action, request, identity)
    if effective_environment() in {AppEnvironment.STAGING, AppEnvironment.PRODUCTION}:
        await _check_redis(key, limit=limit, window_seconds=window)
        return
    await _local_limiter.check(key, limit=limit, window_seconds=window)
