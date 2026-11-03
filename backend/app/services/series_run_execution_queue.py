"""Redis-backed durable launcher for resumable whole-book execution.

The database remains the source of truth for run/episode progress. Redis only
stores queue membership, single-flight locks, heartbeats, and pause signals.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.redis_client import (
    get_redis,
    heartbeat_key,
    lock_key,
    pause_key,
    processing_key,
    queue_key,
)
from app.core.time_utils import utc_now

logger = logging.getLogger(__name__)

LOCK_TTL_SECONDS = 120
HEARTBEAT_TTL_SECONDS = 60
PAUSE_TTL_SECONDS = 300
MAX_ATTEMPTS = 25
QUEUE_KEY = queue_key()
PROCESSING_KEY = processing_key()


def _backend() -> str:
    return (os.getenv("SERIES_RUN_QUEUE_BACKEND") or "redis").strip().lower()


def _enqueued_at() -> str:
    now = utc_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.isoformat()


def _payload(run_id: str, user_id: str, *, attempt: int = 1) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "user_id": user_id,
        "enqueued_at": _enqueued_at(),
        "attempt": int(attempt),
    }


async def series_run_execution_active(run_id: str) -> bool:
    redis = await get_redis()
    if await redis.exists(lock_key(run_id)):
        return True
    return bool(await redis.exists(heartbeat_key(run_id)))


async def start_series_run_execution(run_id: str, user_id: str) -> bool:
    """Enqueue a run for the worker. Returns False when already active (single-flight)."""
    if _backend() == "memory":
        raise RuntimeError("SERIES_RUN_QUEUE_BACKEND=memory is test-only and requires an injected redis client")
    redis = await get_redis()
    if await series_run_execution_active(run_id):
        return False
    await redis.lpush(queue_key(), json.dumps(_payload(run_id, user_id), ensure_ascii=False))
    return True


async def signal_series_run_pause(run_id: str) -> None:
    redis = await get_redis()
    await redis.set(pause_key(run_id), "1", ex=PAUSE_TTL_SECONDS)


async def pause_signal_present(run_id: str) -> bool:
    redis = await get_redis()
    return bool(await redis.exists(pause_key(run_id)))


async def acquire_run_lock(run_id: str, worker_id: str, lease_token: str | None = None) -> str | None:
    redis = await get_redis()
    token = lease_token or str(uuid.uuid4())
    value = f"{worker_id}:{token}"
    ok = await redis.set(lock_key(run_id), value, ex=LOCK_TTL_SECONDS, nx=True)
    if not ok:
        return None
    await redis.set(heartbeat_key(run_id), _enqueued_at(), ex=HEARTBEAT_TTL_SECONDS)
    return token


async def refresh_execution_heartbeat(run_id: str, *, worker_id: str, lease_token: str) -> None:
    redis = await get_redis()
    current = await redis.get(lock_key(run_id))
    expected = f"{worker_id}:{lease_token}"
    if current != expected:
        return
    await redis.set(lock_key(run_id), expected, ex=LOCK_TTL_SECONDS)
    await redis.set(heartbeat_key(run_id), _enqueued_at(), ex=HEARTBEAT_TTL_SECONDS)


async def release_run_lock(run_id: str, worker_id: str, lease_token: str) -> None:
    redis = await get_redis()
    current = await redis.get(lock_key(run_id))
    expected = f"{worker_id}:{lease_token}"
    if current == expected:
        await redis.delete(lock_key(run_id), heartbeat_key(run_id))
    else:
        await redis.delete(heartbeat_key(run_id))


async def ack_processing(redis, payload_json: str) -> None:
    await redis.lrem(processing_key(), 1, payload_json)


async def reclaim_stale_processing(redis) -> int:
    """Requeue processing entries that lost their lock and heartbeat."""
    items = await redis.lrange(processing_key(), 0, -1)
    reclaimed = 0
    for raw in items:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            await redis.lrem(processing_key(), 1, raw)
            continue
        run_id = str(payload.get("run_id") or "")
        if not run_id:
            await redis.lrem(processing_key(), 1, raw)
            continue
        if await redis.exists(lock_key(run_id)):
            continue
        if await redis.exists(heartbeat_key(run_id)):
            continue
        attempt = int(payload.get("attempt") or 1) + 1
        await redis.lrem(processing_key(), 1, raw)
        if attempt > MAX_ATTEMPTS:
            logger.error(
                "series run queue dead-lettered after max attempts",
                extra={"run_id": run_id, "attempt": attempt},
            )
            # Worker/ops may persist queue_dead_letter on the run; reclaim itself only drops.
            continue
        payload["attempt"] = attempt
        await redis.lpush(queue_key(), json.dumps(payload, ensure_ascii=False))
        reclaimed += 1
    return reclaimed


async def record_queue_dead_letter(db, run, *, attempt: int, reason: str) -> None:
    metadata = dict(run.run_metadata or {})
    metadata["queue_dead_letter"] = {
        "attempt": attempt,
        "reason": reason,
        "at": _enqueued_at(),
    }
    run.run_metadata = metadata
    await db.commit()


__all__ = [
    "HEARTBEAT_TTL_SECONDS",
    "LOCK_TTL_SECONDS",
    "MAX_ATTEMPTS",
    "PAUSE_TTL_SECONDS",
    "PROCESSING_KEY",
    "QUEUE_KEY",
    "ack_processing",
    "acquire_run_lock",
    "pause_signal_present",
    "reclaim_stale_processing",
    "record_queue_dead_letter",
    "refresh_execution_heartbeat",
    "release_run_lock",
    "series_run_execution_active",
    "signal_series_run_pause",
    "start_series_run_execution",
]
