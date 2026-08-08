"""Idempotent database task submission."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.features.task_execution.repository import add_event
from app.models.task_execution import TaskExecution


class DatabaseTaskDispatcher:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def submit(
        self,
        *,
        user_id: str,
        task_type: str,
        idempotency_key: str,
        payload: dict,
        project_id: str | None = None,
        provider_task_id: str | None = None,
        max_attempts: int = 3,
        priority: int = 0,
    ) -> tuple[TaskExecution, bool]:
        duplicate_query = select(TaskExecution).where(
            TaskExecution.user_id == user_id,
            TaskExecution.task_type == task_type,
            TaskExecution.idempotency_key == idempotency_key,
        )
        existing = await self.db.scalar(duplicate_query)
        if existing:
            return existing, False
        execution = TaskExecution(
            user_id=user_id,
            project_id=project_id,
            task_type=task_type,
            idempotency_key=idempotency_key,
            payload=dict(payload),
            provider_task_id=provider_task_id,
            max_attempts=max(1, max_attempts),
            priority=priority,
            next_attempt_at=utc_now(),
        )
        try:
            async with self.db.begin_nested():
                self.db.add(execution)
                await self.db.flush()
                add_event(
                    self.db,
                    execution,
                    event_type="queued",
                    message="任务已进入队列",
                )
                await self.db.flush()
        except IntegrityError:
            existing = await self.db.scalar(duplicate_query)
            if not existing:
                raise
            return existing, False
        return execution, True
