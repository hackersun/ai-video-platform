from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.database import Base
from app.models.task_execution import TaskExecution, TaskExecutionEvent


@pytest.mark.asyncio
async def test_task_execution_event_is_append_only() -> None:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        execution = TaskExecution(
            id="task-1",
            user_id="user-1",
            task_type="series_run.execute",
            idempotency_key="series-run-1:v1",
            payload={"run_id": "run-1"},
        )
        event = TaskExecutionEvent(
            id="event-1",
            execution_id=execution.id,
            event_type="queued",
            status="pending",
            message="任务已进入队列",
        )
        db.add_all([execution, event])
        await db.commit()

        event.message = "被篡改"
        with pytest.raises(RuntimeError, match="任务事件不可修改或删除"):
            await db.flush()
    await engine.dispose()
