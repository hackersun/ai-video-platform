"""Async Redis helpers for Series Run durable queue."""

from __future__ import annotations

import os
from functools import lru_cache

from redis.asyncio import Redis

KEY_PREFIX = "avp:series_run:"


def get_redis_url() -> str:
    url = (os.getenv("REDIS_URL") or "").strip()
    if not url:
        raise RuntimeError("REDIS_URL is required for Series Run queue backend")
    return url


def queue_key() -> str:
    return f"{KEY_PREFIX}queue"


def processing_key() -> str:
    return f"{KEY_PREFIX}processing"


def lock_key(run_id: str) -> str:
    return f"{KEY_PREFIX}lock:{run_id}"


def heartbeat_key(run_id: str) -> str:
    return f"{KEY_PREFIX}heartbeat:{run_id}"


def pause_key(run_id: str) -> str:
    return f"{KEY_PREFIX}pause:{run_id}"


@lru_cache(maxsize=1)
def _client_for(url: str) -> Redis:
    # socket_timeout must exceed worker BLMOVE block time; None lets command timeouts win.
    return Redis.from_url(
        url,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=None,
    )


async def get_redis() -> Redis:
    return _client_for(get_redis_url())


def reset_redis_client_cache() -> None:
    _client_for.cache_clear()


__all__ = [
    "KEY_PREFIX",
    "get_redis",
    "get_redis_url",
    "heartbeat_key",
    "lock_key",
    "pause_key",
    "processing_key",
    "queue_key",
    "reset_redis_client_cache",
]
