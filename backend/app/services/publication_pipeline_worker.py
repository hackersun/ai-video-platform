"""Publication Pipeline Redis consumer."""

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
from app.core.redis_client import get_redis
from app.models.publication_pipeline import NovelPublicationPipeline
from app.services.publication_pipeline_orchestrator import PublicationPipelineOrchestrator
from app.services.publication_pipeline_media_hooks import run_media_quality_with_default_hooks
from app.services.publication_pipeline_queue import (
    HEARTBEAT_REFRESH_INTERVAL_SECONDS,
    MAX_ATTEMPTS,
    ack_processing,
    acquire_pipeline_lock,
    pause_signal_present,
    processing_key,
    queue_key,
    reclaim_stale_processing,
    record_queue_dead_letter,
    refresh_execution_heartbeat,
    release_pipeline_lock,
)

logger = logging.getLogger(__name__)

BLMOVE_TIMEOUT_SECONDS = 5
RECLAIM_INTERVAL_SECONDS = 15
SKIP_STATUSES = {"succeeded", "cancelled"}


def _worker_id() -> str:
    return (
        os.getenv("PUBLICATION_PIPELINE_WORKER_ID")
        or f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
    )


def _enabled() -> bool:
    return (os.getenv("PUBLICATION_PIPELINE_ENABLED") or "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


async def _heartbeat_loop(
    pipeline_id: str, *, worker_id: str, lease_token: str, stop_event: asyncio.Event
) -> None:
    """Timer-based lease refresh so long media/FFmpeg stages cannot be reclaimed."""
    while not stop_event.is_set():
        try:
            await refresh_execution_heartbeat(
                pipeline_id, worker_id=worker_id, lease_token=lease_token
            )
        except Exception:
            logger.exception(
                "publication pipeline heartbeat refresh failed",
                extra={"pipeline_id": pipeline_id},
            )
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=HEARTBEAT_REFRESH_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            continue


async def _execute_pipeline(
    pipeline_id: str, user_id: str, *, worker_id: str, lease_token: str
) -> None:
    async with AsyncSessionLocal() as db:
        pipeline = await db.scalar(
            select(NovelPublicationPipeline).where(
                NovelPublicationPipeline.id == pipeline_id,
                NovelPublicationPipeline.user_id == user_id,
            )
        )
        if pipeline is None or pipeline.status in SKIP_STATUSES:
            return

        async def should_stop() -> bool:
            await db.refresh(pipeline)
            if pipeline.status == "paused":
                return True
            if await pause_signal_present(pipeline_id):
                return True
            await refresh_execution_heartbeat(
                pipeline_id, worker_id=worker_id, lease_token=lease_token
            )
            return False

        hb_stop = asyncio.Event()
        hb_task = asyncio.create_task(
            _heartbeat_loop(
                pipeline_id, worker_id=worker_id, lease_token=lease_token, stop_event=hb_stop
            ),
            name=f"publication-pipeline-heartbeat:{pipeline_id}",
        )
        try:
            await PublicationPipelineOrchestrator(should_stop=should_stop, run_media_fn=run_media_quality_with_default_hooks).execute(db, pipeline)
        except Exception as exc:
            logger.exception(
                "publication pipeline worker execution failed",
                extra={"pipeline_id": pipeline_id},
            )
            await _fail_closed(db, pipeline_id, user_id, exc)
        finally:
            hb_stop.set()
            hb_task.cancel()
            try:
                await hb_task
            except asyncio.CancelledError:
                pass


async def _fail_closed(db, pipeline_id: str, user_id: str, exc: Exception) -> None:
    """Unhandled errors must not leave a pipeline stuck in ``running``."""
    try:
        await db.rollback()
        pipeline = await db.scalar(
            select(NovelPublicationPipeline).where(
                NovelPublicationPipeline.id == pipeline_id,
                NovelPublicationPipeline.user_id == user_id,
            )
        )
        if pipeline is None or pipeline.status in {"succeeded", "cancelled", "failed", "blocked", "paused"}:
            return
        detail = f"{type(exc).__name__}: {exc}"[:1000]
        pipeline.status = "failed"
        pipeline.blocker_code = "worker_unhandled_exception"
        pipeline.blocker_detail = detail
        summary = dict(pipeline.gate_summary or {})
        summary["blocker_code"] = "worker_unhandled_exception"
        summary["blocker_detail"] = detail
        pipeline.gate_summary = summary
        await db.commit()
    except Exception:
        logger.exception("publication pipeline fail-closed update failed", extra={"pipeline_id": pipeline_id})


async def process_one(redis, worker_id: str) -> bool:
    try:
        raw = await redis.blmove(
            queue_key(),
            processing_key(),
            BLMOVE_TIMEOUT_SECONDS,
            src="LEFT",
            dest="RIGHT",
        )
    except RedisTimeoutError:
        return False
    if raw is None:
        return False
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        await ack_processing(redis, raw)
        return True

    pipeline_id = str(payload.get("pipeline_id") or "")
    user_id = str(payload.get("user_id") or "")
    attempt = int(payload.get("attempt") or 1)
    if not pipeline_id or not user_id:
        await ack_processing(redis, raw)
        return True

    lease_token = await acquire_pipeline_lock(pipeline_id, worker_id)
    if lease_token is None:
        await ack_processing(redis, raw)
        return True

    try:
        if attempt > MAX_ATTEMPTS:
            async with AsyncSessionLocal() as db:
                pipeline = await db.scalar(
                    select(NovelPublicationPipeline).where(
                        NovelPublicationPipeline.id == pipeline_id,
                        NovelPublicationPipeline.user_id == user_id,
                    )
                )
                if pipeline is not None:
                    await record_queue_dead_letter(
                        db, pipeline, attempt=attempt, reason="max_attempts"
                    )
        else:
            await _execute_pipeline(
                pipeline_id, user_id, worker_id=worker_id, lease_token=lease_token
            )
    finally:
        await ack_processing(redis, raw)
        await release_pipeline_lock(pipeline_id, worker_id, lease_token)
    return True


async def reclaim_loop(redis, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await reclaim_stale_processing(redis)
        except Exception:
            logger.exception("publication pipeline queue reclaim failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=RECLAIM_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            continue


async def run_worker(stop_event: asyncio.Event | None = None) -> None:
    if not _enabled():
        raise RuntimeError("PUBLICATION_PIPELINE_ENABLED is false")
    stop_event = stop_event or asyncio.Event()
    worker_id = _worker_id()
    redis = await get_redis()
    reclaim_task = asyncio.create_task(
        reclaim_loop(redis, stop_event), name="publication-pipeline-reclaim"
    )
    logger.info("publication-pipeline-worker started", extra={"worker_id": worker_id})
    try:
        while not stop_event.is_set():
            try:
                await process_one(redis, worker_id=worker_id)
            except Exception:
                logger.exception("publication-pipeline-worker iteration failed")
                await asyncio.sleep(1)
    finally:
        stop_event.set()
        reclaim_task.cancel()
        try:
            await reclaim_task
        except asyncio.CancelledError:
            pass
        logger.info("publication-pipeline-worker stopped", extra={"worker_id": worker_id})


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
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
