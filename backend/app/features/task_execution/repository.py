"""Atomic lease and transition operations for durable tasks."""

from datetime import timedelta
from uuid import uuid4

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.features.task_execution.domain import (
    CANCELLED,
    DEAD_LETTER,
    FAILED,
    NEEDS_ATTENTION,
    PENDING,
    RETRY_WAIT,
    RUNNING,
    SUCCEEDED,
    TaskTransitionError,
)
from app.models.task_execution import TaskExecution, TaskExecutionEvent


def add_event(
    db: AsyncSession,
    execution: TaskExecution,
    *,
    event_type: str,
    message: str,
    worker_id: str | None = None,
    details: dict | None = None,
) -> None:
    db.add(
        TaskExecutionEvent(
            id=str(uuid4()),
            execution_id=execution.id,
            event_type=event_type,
            status=execution.status,
            message=message,
            worker_id=worker_id,
            details=details or {},
        )
    )


async def claim_one(factory, *, worker_id: str, lease_seconds: int) -> TaskExecution | None:
    now = utc_now()
    async with factory() as db:
        candidate = await db.scalar(
            select(TaskExecution)
            .where(
                or_(
                    and_(
                        TaskExecution.status.in_([PENDING, RETRY_WAIT]),
                        TaskExecution.next_attempt_at <= now,
                    ),
                    and_(
                        TaskExecution.status == RUNNING,
                        TaskExecution.lease_expires_at <= now,
                    ),
                )
            )
            .order_by(TaskExecution.priority.desc(), TaskExecution.created_at)
            .limit(1)
        )
        if not candidate:
            return None
        claimed = await db.execute(
            update(TaskExecution)
            .where(
                TaskExecution.id == candidate.id,
                TaskExecution.version == candidate.version,
                TaskExecution.status == candidate.status,
            )
            .values(
                status=RUNNING,
                attempt_count=TaskExecution.attempt_count + 1,
                lease_owner=worker_id,
                lease_expires_at=now + timedelta(seconds=lease_seconds),
                heartbeat_at=now,
                version=TaskExecution.version + 1,
                updated_at=now,
            )
            .execution_options(synchronize_session=False)
        )
        if claimed.rowcount != 1:
            await db.rollback()
            return None
        await db.refresh(candidate)
        add_event(db, candidate, event_type="claimed", message="任务已由执行器领取", worker_id=worker_id)
        await db.commit()
        await db.refresh(candidate)
        return candidate


async def request_cancel(db: AsyncSession, execution: TaskExecution) -> TaskExecution:
    if execution.status in {SUCCEEDED, FAILED, DEAD_LETTER, NEEDS_ATTENTION, CANCELLED}:
        raise TaskTransitionError("当前任务已经结束，不能取消")
    now = utc_now()
    execution.cancel_requested_at = now
    if execution.status != RUNNING:
        execution.status = CANCELLED
        execution.completed_at = now
        message = "任务已取消"
        event_type = "cancelled"
    else:
        message = "已请求取消，任务将在安全点停止"
        event_type = "cancel_requested"
    execution.version += 1
    add_event(db, execution, event_type=event_type, message=message)
    await db.flush()
    return execution


async def retry_execution(
    db: AsyncSession,
    execution: TaskExecution,
    *,
    confirm_uncertain: bool,
) -> TaskExecution:
    if execution.status not in {FAILED, DEAD_LETTER, NEEDS_ATTENTION}:
        raise TaskTransitionError("当前任务不需要重试")
    if execution.status == NEEDS_ATTENTION and not confirm_uncertain:
        raise TaskTransitionError("请先确认供应商没有重复受理，再手动重试")
    execution.status = PENDING
    execution.next_attempt_at = utc_now()
    execution.lease_owner = None
    execution.lease_expires_at = None
    execution.heartbeat_at = None
    execution.cancel_requested_at = None
    execution.completed_at = None
    execution.last_error_code = None
    execution.last_error_message = None
    execution.version += 1
    add_event(db, execution, event_type="retried", message="任务已重新进入队列")
    await db.flush()
    return execution
