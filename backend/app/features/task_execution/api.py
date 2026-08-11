"""Current-user durable task query and recovery endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.features.task_execution.domain import (
    CANCELLED,
    DEAD_LETTER,
    FAILED,
    NEEDS_ATTENTION,
    SUCCEEDED,
    TaskTransitionError,
    status_label,
)
from app.features.task_execution.repository import request_cancel, retry_execution
from app.features.task_execution.schemas import (
    RetryTaskRequest,
    TaskExecutionDetail,
    TaskExecutionEventSummary,
    TaskExecutionList,
    TaskExecutionSummary,
)
from app.models.task_execution import TaskExecution, TaskExecutionEvent


router = APIRouter(prefix="/task-executions", tags=["生产任务"])
RETRYABLE = frozenset({FAILED, DEAD_LETTER, NEEDS_ATTENTION})
NOT_CANCELLABLE = frozenset({SUCCEEDED, FAILED, DEAD_LETTER, NEEDS_ATTENTION, CANCELLED})


def _safe_error_message(message: str | None) -> str | None:
    if not message:
        return None
    technical_markers = ("traceback", "sqlalchemy", "http://", "https://", "exception")
    if any(marker in message.lower() for marker in technical_markers):
        return "任务执行失败，请查看服务日志后重试"
    if not any("\u4e00" <= character <= "\u9fff" for character in message):
        return "任务执行失败，请查看服务日志后重试"
    return message


def _summary(execution: TaskExecution) -> TaskExecutionSummary:
    return TaskExecutionSummary(
        id=execution.id,
        project_id=execution.project_id,
        task_type=execution.task_type,
        status=execution.status,
        status_label=status_label(execution.status),
        attempt_count=execution.attempt_count or 0,
        max_attempts=execution.max_attempts or 0,
        provider_task_id=execution.provider_task_id,
        last_error_code=execution.last_error_code,
        last_error_message=_safe_error_message(execution.last_error_message),
        can_cancel=execution.status not in NOT_CANCELLABLE,
        can_retry=execution.status in RETRYABLE,
        requires_confirmation=execution.status == NEEDS_ATTENTION,
        created_at=execution.created_at,
        updated_at=execution.updated_at,
        completed_at=execution.completed_at,
    )


async def _owned_execution(db: AsyncSession, execution_id: str, user_id: str) -> TaskExecution:
    execution = await db.scalar(
        select(TaskExecution).where(
            TaskExecution.id == execution_id,
            TaskExecution.user_id == user_id,
        )
    )
    if not execution:
        raise HTTPException(status_code=404, detail="任务不存在")
    return execution


@router.get("", response_model=TaskExecutionList)
async def list_task_executions(
    status: str | None = Query(None),
    task_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> TaskExecutionList:
    query = select(TaskExecution).where(TaskExecution.user_id == user_id)
    if status:
        query = query.where(TaskExecution.status == status)
    if task_type:
        query = query.where(TaskExecution.task_type == task_type)
    executions = list((await db.scalars(query.order_by(desc(TaskExecution.created_at)).limit(limit))).all())
    return TaskExecutionList(items=[_summary(execution) for execution in executions])


@router.get("/{execution_id}", response_model=TaskExecutionDetail)
async def get_task_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> TaskExecutionDetail:
    execution = await _owned_execution(db, execution_id, user_id)
    events = list(
        (
            await db.scalars(
                select(TaskExecutionEvent)
                .where(TaskExecutionEvent.execution_id == execution.id)
                .order_by(TaskExecutionEvent.created_at)
                .limit(200)
            )
        ).all()
    )
    return TaskExecutionDetail(
        **_summary(execution).model_dump(),
        events=[
            TaskExecutionEventSummary(
                event_type=event.event_type,
                status=event.status,
                message=_safe_error_message(event.message) or "任务状态已更新",
                created_at=event.created_at,
            )
            for event in events
        ],
    )


@router.post("/{execution_id}/cancel", response_model=TaskExecutionSummary)
async def cancel_task_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> TaskExecutionSummary:
    execution = await _owned_execution(db, execution_id, user_id)
    try:
        await request_cancel(db, execution)
    except TaskTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(execution)
    return _summary(execution)


@router.post("/{execution_id}/retry", response_model=TaskExecutionSummary)
async def retry_task_execution(
    execution_id: str,
    body: RetryTaskRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> TaskExecutionSummary:
    execution = await _owned_execution(db, execution_id, user_id)
    try:
        await retry_execution(db, execution, confirm_uncertain=body.confirm_uncertain)
    except TaskTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(execution)
    return _summary(execution)
