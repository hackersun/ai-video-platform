"""In-process / optional Redis rate limiting for commercial gates."""

from __future__ import annotations

import asyncio
import hashlib
import os
import time
from collections.abc import Callable
from dataclasses import dataclass


class RateLimitExceeded(RuntimeError):
    """Raised when a client exceeds the configured request budget."""


@dataclass(frozen=True)
class RateLimitRule:
    name: str
    limit: int
    window_seconds: int


class InMemoryRateLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._attempts: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()

    async def hit(self, key: str, *, limit: int, window_seconds: int) -> int:
        now = self._clock()
        cutoff = now - window_seconds
        async with self._lock:
            attempts = [item for item in self._attempts.get(key, []) if item > cutoff]
            if len(attempts) >= limit:
                raise RateLimitExceeded("操作过于频繁，请稍后再试")
            attempts.append(now)
            self._attempts[key] = attempts
            return len(attempts)

    def reset(self) -> None:
        self._attempts.clear()


_local = InMemoryRateLimiter()


def reset_rate_limits() -> None:
    _local.reset()


def privacy_safe_key(*parts: str) -> str:
    raw = "|".join(part.strip().lower() for part in parts if part)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
    return f"rl:{digest}"


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def auth_rule(action: str) -> RateLimitRule:
    defaults = {
        "login": (10, 60),
        "register": (5, 60),
        "forgot": (5, 60),
        "reset": (10, 60),
        "refresh": (30, 60),
    }
    limit_default, window_default = defaults.get(action, (20, 60))
    return RateLimitRule(
        name=f"auth:{action}",
        limit=_env_int(f"AUTH_RATE_LIMIT_{action.upper()}", limit_default),
        window_seconds=_env_int("AUTH_RATE_LIMIT_WINDOW_SECONDS", window_default),
    )


def traffic_rule(bucket: str) -> RateLimitRule:
    defaults = {"generate": (30, 60), "upload": (20, 60)}
    limit_default, window_default = defaults.get(bucket, (60, 60))
    return RateLimitRule(
        name=f"traffic:{bucket}",
        limit=_env_int(f"API_RATE_LIMIT_{bucket.upper()}", limit_default),
        window_seconds=_env_int("API_RATE_LIMIT_WINDOW_SECONDS", window_default),
    )


async def _hit_redis(key: str, *, limit: int, window_seconds: int) -> int:
    from redis.asyncio import Redis

    redis_url = (os.getenv("REDIS_URL") or "").strip()
    if not redis_url:
        raise RuntimeError("REDIS_URL missing")
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
    return current


async def enforce_rate_limit(key: str, rule: RateLimitRule) -> int:
    use_redis = bool((os.getenv("REDIS_URL") or "").strip()) and (
        (os.getenv("RATE_LIMIT_BACKEND") or "auto").strip().lower() != "memory"
    )
    if (os.getenv("RATE_LIMIT_BACKEND") or "").strip().lower() == "memory":
        use_redis = False
    if use_redis:
        try:
            return await _hit_redis(key, limit=rule.limit, window_seconds=rule.window_seconds)
        except Exception:
            from app.core.runtime_env import is_production_environment

            if is_production_environment():
                raise RateLimitExceeded("限流服务暂不可用，请稍后再试") from None
    return await _local.hit(key, limit=rule.limit, window_seconds=rule.window_seconds)


__all__ = [
    "RateLimitExceeded",
    "RateLimitRule",
    "auth_rule",
    "enforce_rate_limit",
    "privacy_safe_key",
    "reset_rate_limits",
    "traffic_rule",
]
