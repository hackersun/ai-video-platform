"""Lease-based durable task worker."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import timedelta
import logging

from sqlalchemy import update

from app.core.time_utils import utc_now
from app.features.task_execution.domain import (
    CANCELLED,
    DEAD_LETTER,
    NEEDS_ATTENTION,
    RETRY_WAIT,
    RUNNING,
    SUCCEEDED,
    TaskOutcome,
)
from app.features.task_execution.handlers import DEFAULT_HANDLERS, TaskHandler
from app.features.task_execution.repository import add_event, claim_one
from app.models.task_execution import TaskExecution


logger = logging.getLogger(__name__)


async def _persist_outcome(db, execution: TaskExecution, outcome: TaskOutcome, worker_id: str) -> None:
    now = utc_now()
    status = outcome.status
    message = outcome.message
    if status == RETRY_WAIT and execution.attempt_count >= execution.max_attempts:
        status = DEAD_LETTER
        message = "已达到最大安全重试次数，请人工检查后重试"
    execution.status = status
    execution.result_summary = dict(outcome.result_summary)
    execution.last_error_code = outcome.error_code
    execution.last_error_message = None if status == SUCCEEDED else message
    execution.lease_owner = None
    execution.lease_expires_at = None
    execution.heartbeat_at = None
    execution.next_attempt_at = now + (outcome.retry_after or timedelta(0))
    execution.completed_at = None if status == RETRY_WAIT else now
    execution.version += 1
    add_event(
        db,
        execution,
        event_type="completed" if status == SUCCEEDED else status,
        message=message,
        worker_id=worker_id,
    )
    await db.flush()


async def _heartbeat_loop(
    factory,
    execution_id: str,
    worker_id: str,
    heartbeat_seconds: float,
    lease_seconds: int,
) -> None:
    while True:
        await asyncio.sleep(heartbeat_seconds)
        now = utc_now()
        async with factory() as db:
            renewed = await db.execute(
                update(TaskExecution)
                .where(
                    TaskExecution.id == execution_id,
                    TaskExecution.status == RUNNING,
                    TaskExecution.lease_owner == worker_id,
                )
                .values(
                    heartbeat_at=now,
                    lease_expires_at=now + timedelta(seconds=lease_seconds),
                    updated_at=now,
                )
            )
            await db.commit()
            if renewed.rowcount != 1:
                return


async def execute_claimed(
    factory,
    execution: TaskExecution,
    *,
    worker_id: str,
    handlers: dict[str, TaskHandler] | None = None,
    heartbeat_seconds: float = 60,
    lease_seconds: int = 300,
) -> None:
    registry = handlers if handlers is not None else DEFAULT_HANDLERS
    async with factory() as db:
        current = await db.get(TaskExecution, execution.id)
        if not current or current.status != RUNNING or current.lease_owner != worker_id:
            return
        if current.cancel_requested_at:
            await _persist_outcome(db, current, TaskOutcome(CANCELLED, "任务已取消"), worker_id)
            await db.commit()
            return
        execution = current
    handler = registry.get(execution.task_type)
    heartbeat = asyncio.create_task(
        _heartbeat_loop(
            factory,
            execution.id,
            worker_id,
            heartbeat_seconds,
            lease_seconds,
        )
    )
    try:
        if not handler:
            raise LookupError(f"handler not registered: {execution.task_type}")
        outcome = await handler(execution)
    except Exception:
        logger.exception(
            "durable task handler failed",
            extra={"execution_id": execution.id, "task_type": execution.task_type},
        )
        outcome = TaskOutcome(
            NEEDS_ATTENTION,
            "任务状态不确定，请人工确认后再决定是否重试",
            error_code="unexpected_execution_error",
        )
    finally:
        heartbeat.cancel()
        with suppress(asyncio.CancelledError):
            await heartbeat
    async with factory() as db:
        current = await db.get(TaskExecution, execution.id)
        if not current or current.status != RUNNING or current.lease_owner != worker_id:
            return
        if current.cancel_requested_at:
            outcome = TaskOutcome(CANCELLED, "任务已取消")
        await _persist_outcome(db, current, outcome, worker_id)
        await db.commit()


async def run_worker(
    factory,
    *,
    worker_id: str,
    handlers: dict[str, TaskHandler] | None = None,
    lease_seconds: int = 300,
) -> None:
    while True:
        execution = await claim_one(factory, worker_id=worker_id, lease_seconds=lease_seconds)
        if execution:
            await execute_claimed(
                factory,
                execution,
                worker_id=worker_id,
                handlers=handlers,
                heartbeat_seconds=max(1, lease_seconds / 3),
                lease_seconds=lease_seconds,
            )
        else:
            await asyncio.sleep(2)
