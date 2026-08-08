from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.database import Base
from app.features.task_execution.dispatcher import DatabaseTaskDispatcher
from app.features.task_execution.domain import RETRY_WAIT, SUCCEEDED, TaskOutcome
from app.features.task_execution.repository import claim_one
from app.features.task_execution.worker import execute_claimed
from app.models.task_execution import TaskExecution


@pytest_asyncio.fixture()
async def factory():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield session_factory
    await engine.dispose()


async def _claimed(factory, *, max_attempts: int = 3) -> TaskExecution:
    async with factory() as db:
        await DatabaseTaskDispatcher(db).submit(
            user_id="user-1",
            task_type="test.task",
            idempotency_key=f"task-{max_attempts}",
            payload={"value": 1},
            max_attempts=max_attempts,
        )
        await db.commit()
    execution = await claim_one(factory, worker_id="worker-1", lease_seconds=60)
    assert execution
    return execution


@pytest.mark.asyncio
async def test_worker_persists_successful_outcome(factory) -> None:
    execution = await _claimed(factory)

    async def handler(_execution):
        return TaskOutcome(SUCCEEDED, "任务执行完成", {"artifact_id": "artifact-1"})

    await execute_claimed(factory, execution, worker_id="worker-1", handlers={"test.task": handler})

    async with factory() as db:
        stored = await db.get(TaskExecution, execution.id)
        assert stored.status == "succeeded"
        assert stored.result_summary == {"artifact_id": "artifact-1"}
        assert stored.completed_at is not None


@pytest.mark.asyncio
async def test_safe_retry_waits_without_marking_failure(factory) -> None:
    execution = await _claimed(factory)

    async def handler(_execution):
        return TaskOutcome(
            RETRY_WAIT,
            "供应商仍在处理，稍后继续查询",
            error_code="provider_pending",
            retry_after=timedelta(seconds=30),
        )

    await execute_claimed(factory, execution, worker_id="worker-1", handlers={"test.task": handler})

    async with factory() as db:
        stored = await db.get(TaskExecution, execution.id)
        assert stored.status == "retry_wait"
        assert stored.last_error_message == "供应商仍在处理，稍后继续查询"
        assert stored.lease_owner is None


@pytest.mark.asyncio
async def test_exhausted_safe_retries_move_to_dead_letter(factory) -> None:
    execution = await _claimed(factory, max_attempts=1)

    async def handler(_execution):
        return TaskOutcome(
            RETRY_WAIT,
            "供应商仍在处理",
            error_code="provider_pending",
            retry_after=timedelta(seconds=30),
        )

    await execute_claimed(factory, execution, worker_id="worker-1", handlers={"test.task": handler})

    async with factory() as db:
        stored = await db.get(TaskExecution, execution.id)
        assert stored.status == "dead_letter"
        assert stored.last_error_message == "已达到最大安全重试次数，请人工检查后重试"


@pytest.mark.asyncio
async def test_unexpected_handler_error_needs_manual_attention(factory) -> None:
    execution = await _claimed(factory)

    async def handler(_execution):
        raise RuntimeError("provider secret must not leak")

    await execute_claimed(factory, execution, worker_id="worker-1", handlers={"test.task": handler})

    async with factory() as db:
        stored = await db.get(TaskExecution, execution.id)
        assert stored.status == "needs_attention"
        assert stored.last_error_code == "unexpected_execution_error"
        assert stored.last_error_message == "任务状态不确定，请人工确认后再决定是否重试"


@pytest.mark.asyncio
async def test_cancel_request_stops_before_handler_is_called(factory) -> None:
    execution = await _claimed(factory)
    async with factory() as db:
        stored = await db.get(TaskExecution, execution.id)
        stored.cancel_requested_at = stored.updated_at
        await db.commit()
    called = False

    async def handler(_execution):
        nonlocal called
        called = True
        return TaskOutcome(SUCCEEDED, "不应执行")

    await execute_claimed(factory, execution, worker_id="worker-1", handlers={"test.task": handler})

    async with factory() as db:
        stored = await db.get(TaskExecution, execution.id)
        assert stored.status == "cancelled"
        assert called is False


@pytest.mark.asyncio
async def test_long_handler_renews_lease_until_completion(factory) -> None:
    execution = await _claimed(factory)
    original_expiry = execution.lease_expires_at

    async def handler(_execution):
        await asyncio.sleep(0.15)
        return TaskOutcome(SUCCEEDED, "任务执行完成")

    running = asyncio.create_task(
        execute_claimed(
            factory,
            execution,
            worker_id="worker-1",
            handlers={"test.task": handler},
            heartbeat_seconds=0.03,
            lease_seconds=60,
        )
    )
    await asyncio.sleep(0.09)
    async with factory() as db:
        stored = await db.get(TaskExecution, execution.id)
        assert stored.lease_expires_at > original_expiry
    await running
