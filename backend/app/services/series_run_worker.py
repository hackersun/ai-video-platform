"""Series Run Redis consumer: durable queue worker process."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import socket
import uuid
from redis.exceptions import TimeoutError as RedisTimeoutError
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.core.redis_client import get_redis, processing_key, queue_key
from app.models.series_production_run import SeriesProductionRun
from app.services.series_run_execution_queue import (
    MAX_ATTEMPTS,
    acquire_run_lock,
    ack_processing,
    pause_signal_present,
    reclaim_stale_processing,
    record_queue_dead_letter,
    refresh_execution_heartbeat,
    release_run_lock,
)
from app.services.series_run_orchestrator import SeriesRunOrchestrator

logger = logging.getLogger(__name__)

BLMOVE_TIMEOUT_SECONDS = 5
RECLAIM_INTERVAL_SECONDS = 15
SKIP_STATUSES = {"shots_ready", "completed", "paused"}


def _worker_id() -> str:
    return os.getenv("SERIES_RUN_WORKER_ID") or f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


async def _execute_run(run_id: str, user_id: str, *, worker_id: str, lease_token: str) -> None:
    async with AsyncSessionLocal() as db:
        run = await db.scalar(
            select(SeriesProductionRun).where(
                SeriesProductionRun.id == run_id,
                SeriesProductionRun.user_id == user_id,
            )
        )
        if run is None or run.status in SKIP_STATUSES:
            return

        async def should_stop() -> bool:
            await db.refresh(run)
            if run.status == "paused":
                return True
            if await pause_signal_present(run_id):
                return True
            await refresh_execution_heartbeat(run_id, worker_id=worker_id, lease_token=lease_token)
            return False

        try:
            await SeriesRunOrchestrator(should_stop=should_stop).execute(db, run)
        except Exception:
            logger.exception("series run worker execution failed", extra={"run_id": run_id})


async def process_one(redis, worker_id: str) -> bool:
    """Claim one queue item. Returns False when the queue was empty (timeout)."""
    try:
        raw = await redis.blmove(queue_key(), processing_key(), BLMOVE_TIMEOUT_SECONDS, src="LEFT", dest="RIGHT")
    except RedisTimeoutError:
        # Defense: client socket timeout must not abort empty-queue waits.
        return False
    if raw is None:
        return False
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        await ack_processing(redis, raw)
        return True

    run_id = str(payload.get("run_id") or "")
    user_id = str(payload.get("user_id") or "")
    attempt = int(payload.get("attempt") or 1)
    if not run_id or not user_id:
        await ack_processing(redis, raw)
        return True

    lease_token = await acquire_run_lock(run_id, worker_id)
    if lease_token is None:
        await ack_processing(redis, raw)
        return True

    try:
        if attempt > MAX_ATTEMPTS:
            async with AsyncSessionLocal() as db:
                run = await db.scalar(
                    select(SeriesProductionRun).where(
                        SeriesProductionRun.id == run_id,
                        SeriesProductionRun.user_id == user_id,
                    )
                )
                if run is not None:
                    await record_queue_dead_letter(db, run, attempt=attempt, reason="max_attempts")
        else:
            await _execute_run(run_id, user_id, worker_id=worker_id, lease_token=lease_token)
    finally:
        await ack_processing(redis, raw)
        await release_run_lock(run_id, worker_id, lease_token)
    return True


async def reclaim_loop(redis, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await reclaim_stale_processing(redis)
        except Exception:
            logger.exception("series run queue reclaim failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=RECLAIM_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            continue


async def run_worker(stop_event: asyncio.Event | None = None) -> None:
    stop_event = stop_event or asyncio.Event()
    worker_id = _worker_id()
    redis = await get_redis()
    reclaim_task = asyncio.create_task(reclaim_loop(redis, stop_event), name="series-run-reclaim")
    logger.info("series-run-worker started", extra={"worker_id": worker_id})
    try:
        while not stop_event.is_set():
            try:
                await process_one(redis, worker_id=worker_id)
            except Exception:
                logger.exception("series-run-worker iteration failed")
                await asyncio.sleep(1)
    finally:
        stop_event.set()
        reclaim_task.cancel()
        try:
            await reclaim_task
        except asyncio.CancelledError:
            pass
        logger.info("series-run-worker stopped", extra={"worker_id": worker_id})


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _stop(*_args):
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop)
        except NotImplementedError:
            signal.signal(sig, lambda *_: _stop())
    await run_worker(stop_event)


if __name__ == "__main__":
    asyncio.run(main())
