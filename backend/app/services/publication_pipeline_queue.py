"""Redis-backed durable launcher for publication pipelines.

DB remains authority for pipeline progress. Redis stores queue membership,
single-flight locks, heartbeats, and pause signals under avp:publication_pipeline:*.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import timezone
from typing import Any

from app.core.redis_client import get_redis
from app.core.time_utils import utc_now

logger = logging.getLogger(__name__)

KEY_PREFIX = "avp:publication_pipeline:"
LOCK_TTL_SECONDS = 120
HEARTBEAT_TTL_SECONDS = 60
HEARTBEAT_REFRESH_INTERVAL_SECONDS = 20
DEAD_LETTER_DETAIL = (
    "任务重试次数已用尽，已停止自动重跑。"
    "请到小说详情页点「重试」，或检查 Worker / Redis 后重新提交。"
)
PAUSE_TTL_SECONDS = 300
MAX_ATTEMPTS = 25


def queue_key() -> str:
    return f"{KEY_PREFIX}queue"


def processing_key() -> str:
    return f"{KEY_PREFIX}processing"


def lock_key(pipeline_id: str) -> str:
    return f"{KEY_PREFIX}lock:{pipeline_id}"


def heartbeat_key(pipeline_id: str) -> str:
    return f"{KEY_PREFIX}heartbeat:{pipeline_id}"


def pause_key(pipeline_id: str) -> str:
    return f"{KEY_PREFIX}pause:{pipeline_id}"


QUEUE_KEY = queue_key()
PROCESSING_KEY = processing_key()


def _backend() -> str:
    return (os.getenv("PUBLICATION_PIPELINE_QUEUE_BACKEND") or "redis").strip().lower()


def _enqueued_at() -> str:
    now = utc_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.isoformat()


def _payload(pipeline_id: str, user_id: str, *, attempt: int = 1) -> dict[str, Any]:
    return {
        "pipeline_id": pipeline_id,
        "user_id": user_id,
        "enqueued_at": _enqueued_at(),
        "attempt": int(attempt),
    }


async def publication_pipeline_execution_active(pipeline_id: str) -> bool:
    redis = await get_redis()
    if await redis.exists(lock_key(pipeline_id)):
        return True
    return bool(await redis.exists(heartbeat_key(pipeline_id)))


async def start_publication_pipeline_execution(pipeline_id: str, user_id: str) -> bool:
    """Enqueue a pipeline. Returns False when already active (single-flight)."""
    if _backend() == "memory":
        raise RuntimeError(
            "PUBLICATION_PIPELINE_QUEUE_BACKEND=memory is test-only and requires an injected redis client"
        )
    redis = await get_redis()
    if await publication_pipeline_execution_active(pipeline_id):
        return False
    await redis.lpush(queue_key(), json.dumps(_payload(pipeline_id, user_id), ensure_ascii=False))
    return True


async def signal_publication_pipeline_pause(pipeline_id: str) -> None:
    redis = await get_redis()
    await redis.set(pause_key(pipeline_id), "1", ex=PAUSE_TTL_SECONDS)


async def pause_signal_present(pipeline_id: str) -> bool:
    redis = await get_redis()
    return bool(await redis.exists(pause_key(pipeline_id)))


async def acquire_pipeline_lock(
    pipeline_id: str, worker_id: str, lease_token: str | None = None
) -> str | None:
    redis = await get_redis()
    token = lease_token or str(uuid.uuid4())
    value = f"{worker_id}:{token}"
    ok = await redis.set(lock_key(pipeline_id), value, ex=LOCK_TTL_SECONDS, nx=True)
    if not ok:
        return None
    await redis.set(heartbeat_key(pipeline_id), _enqueued_at(), ex=HEARTBEAT_TTL_SECONDS)
    return token


async def refresh_execution_heartbeat(
    pipeline_id: str, *, worker_id: str, lease_token: str
) -> None:
    redis = await get_redis()
    current = await redis.get(lock_key(pipeline_id))
    expected = f"{worker_id}:{lease_token}"
    if current != expected:
        return
    await redis.set(lock_key(pipeline_id), expected, ex=LOCK_TTL_SECONDS)
    await redis.set(heartbeat_key(pipeline_id), _enqueued_at(), ex=HEARTBEAT_TTL_SECONDS)


async def release_pipeline_lock(pipeline_id: str, worker_id: str, lease_token: str) -> None:
    redis = await get_redis()
    current = await redis.get(lock_key(pipeline_id))
    expected = f"{worker_id}:{lease_token}"
    if current == expected:
        await redis.delete(lock_key(pipeline_id), heartbeat_key(pipeline_id))
    else:
        await redis.delete(heartbeat_key(pipeline_id))


async def ack_processing(redis, payload_json: str) -> None:
    await redis.lrem(processing_key(), 1, payload_json)


async def reclaim_stale_processing(redis) -> int:
    items = await redis.lrange(processing_key(), 0, -1)
    reclaimed = 0
    for raw in items:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            await redis.lrem(processing_key(), 1, raw)
            continue
        pipeline_id = str(payload.get("pipeline_id") or "")
        if not pipeline_id:
            await redis.lrem(processing_key(), 1, raw)
            continue
        if await redis.exists(lock_key(pipeline_id)):
            continue
        if await redis.exists(heartbeat_key(pipeline_id)):
            continue
        attempt = int(payload.get("attempt") or 1) + 1
        await redis.lrem(processing_key(), 1, raw)
        if attempt > MAX_ATTEMPTS:
            logger.error(
                "publication pipeline queue dead-lettered after max attempts",
                extra={"pipeline_id": pipeline_id, "attempt": attempt},
            )
            # Requeue once so the worker can mark the DB pipeline failed + blocker.
            payload["attempt"] = attempt
            payload["dead_letter"] = True
            await redis.lpush(queue_key(), json.dumps(payload, ensure_ascii=False))
            continue
        payload["attempt"] = attempt
        await redis.lpush(queue_key(), json.dumps(payload, ensure_ascii=False))
        reclaimed += 1
    return reclaimed


async def record_queue_dead_letter(db, pipeline, *, attempt: int, reason: str) -> None:
    """Persist dead-letter metadata and force terminal failed + actionable blocker."""
    metadata = dict(pipeline.pipeline_metadata or {})
    dead = {
        "attempt": attempt,
        "reason": reason,
        "at": _enqueued_at(),
        "blocker_code": "queue_dead_letter",
        "message": DEAD_LETTER_DETAIL,
    }
    metadata["queue_dead_letter"] = dead
    pipeline.pipeline_metadata = metadata
    if pipeline.status not in {"succeeded", "cancelled"}:
        pipeline.status = "failed"
    pipeline.blocker_code = "queue_dead_letter"
    pipeline.blocker_detail = DEAD_LETTER_DETAIL
    summary = dict(pipeline.gate_summary or {})
    summary["blocker_code"] = "queue_dead_letter"
    summary["blocker_detail"] = DEAD_LETTER_DETAIL
    summary["queue_dead_letter"] = dead
    pipeline.gate_summary = summary
    await db.commit()


__all__ = [
    "DEAD_LETTER_DETAIL",
    "HEARTBEAT_REFRESH_INTERVAL_SECONDS",
    "HEARTBEAT_TTL_SECONDS",
    "KEY_PREFIX",
    "LOCK_TTL_SECONDS",
    "MAX_ATTEMPTS",
    "PAUSE_TTL_SECONDS",
    "PROCESSING_KEY",
    "QUEUE_KEY",
    "ack_processing",
    "acquire_pipeline_lock",
    "heartbeat_key",
    "lock_key",
    "pause_key",
    "pause_signal_present",
    "processing_key",
    "publication_pipeline_execution_active",
    "queue_key",
    "reclaim_stale_processing",
    "record_queue_dead_letter",
    "refresh_execution_heartbeat",
    "release_pipeline_lock",
    "signal_publication_pipeline_pause",
    "start_publication_pipeline_execution",
]
