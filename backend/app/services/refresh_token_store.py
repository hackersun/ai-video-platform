"""Refresh-token jti store: rotation + revocation without a DB migration."""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Callable


class RefreshTokenStore:
    def __init__(self, clock: Callable[[], float] = time.time) -> None:
        self._clock = clock
        self._denied: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def revoke(self, jti: str, *, ttl_seconds: int) -> None:
        if not jti:
            return
        expires_at = self._clock() + max(1, ttl_seconds)
        if await self._revoke_redis(jti, ttl_seconds=ttl_seconds):
            return
        async with self._lock:
            self._denied[jti] = expires_at

    async def is_revoked(self, jti: str) -> bool:
        if not jti:
            return True
        redis_hit = await self._is_revoked_redis(jti)
        if redis_hit is not None:
            return redis_hit
        now = self._clock()
        async with self._lock:
            expires_at = self._denied.get(jti)
            if expires_at is None:
                return False
            if expires_at <= now:
                self._denied.pop(jti, None)
                return False
            return True

    def reset(self) -> None:
        self._denied.clear()

    def _redis_enabled(self) -> bool:
        if (os.getenv("RATE_LIMIT_BACKEND") or "").strip().lower() == "memory":
            return False
        if (os.getenv("REFRESH_TOKEN_STORE") or "auto").strip().lower() == "memory":
            return False
        return bool((os.getenv("REDIS_URL") or "").strip())

    async def _revoke_redis(self, jti: str, *, ttl_seconds: int) -> bool:
        if not self._redis_enabled():
            return False
        from redis.asyncio import Redis

        client = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
        try:
            await client.setex(f"avp:auth:refresh:deny:{jti}", max(1, ttl_seconds), "1")
            return True
        finally:
            await client.aclose()

    async def _is_revoked_redis(self, jti: str) -> bool | None:
        if not self._redis_enabled():
            return None
        from redis.asyncio import Redis

        client = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
        try:
            return bool(await client.exists(f"avp:auth:refresh:deny:{jti}"))
        except Exception:
            return None
        finally:
            await client.aclose()


_store = RefreshTokenStore()


def get_refresh_token_store() -> RefreshTokenStore:
    return _store


def reset_refresh_token_store() -> None:
    _store.reset()


__all__ = ["RefreshTokenStore", "get_refresh_token_store", "reset_refresh_token_store"]
