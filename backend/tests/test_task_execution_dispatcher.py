from __future__ import annotations

from datetime import timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.database import Base
from app.core.time_utils import utc_now
from app.features.task_execution.dispatcher import DatabaseTaskDispatcher
from app.features.task_execution.domain import TaskTransitionError
from app.features.task_execution.repository import claim_one, request_cancel, retry_execution
from app.models.task_execution import TaskExecution, TaskExecutionEvent


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


@pytest.mark.asyncio
async def test_submit_is_idempotent_for_user_task_type_and_key(factory) -> None:
    async with factory() as db:
        dispatcher = DatabaseTaskDispatcher(db)
        first, first_created = await dispatcher.submit(
            user_id="user-1",
            task_type="series_run.execute",
            idempotency_key="run-1:v1",
            payload={"run_id": "run-1"},
        )
        second, second_created = await dispatcher.submit(
            user_id="user-1",
            task_type="series_run.execute",
            idempotency_key="run-1:v1",
            payload={"run_id": "run-1"},
        )
        await db.commit()

    assert first.id == second.id
    assert (first_created, second_created) == (True, False)
    async with factory() as db:
        assert len((await db.scalars(select(TaskExecution))).all()) == 1
        events = list((await db.scalars(select(TaskExecutionEvent))).all())
        assert [event.event_type for event in events] == ["queued"]


@pytest.mark.asyncio
async def test_submit_recovers_when_concurrent_insert_wins_unique_constraint() -> None:
    winner = TaskExecution(
        id="winner",
        user_id="user-1",
        task_type="series_run.execute",
        idempotency_key="run-1:v1",
        payload={"run_id": "run-1"},
    )

    class Savepoint:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

    class RacingSession:
        def __init__(self):
            self.scalar_calls = 0
            self.flush_calls = 0

        async def scalar(self, _query):
            self.scalar_calls += 1
            return None if self.scalar_calls == 1 else winner

        def begin_nested(self):
            return Savepoint()

        def add(self, _item):
            return None

        async def flush(self):
            self.flush_calls += 1
            if self.flush_calls == 1:
                raise IntegrityError("INSERT", {}, RuntimeError("duplicate"))

    execution, created = await DatabaseTaskDispatcher(RacingSession()).submit(
        user_id="user-1",
        task_type="series_run.execute",
        idempotency_key="run-1:v1",
        payload={"run_id": "run-1"},
    )

    assert execution is winner
    assert created is False


@pytest.mark.asyncio
async def test_claim_uses_version_cas_and_only_one_worker_gets_task(factory) -> None:
    async with factory() as db:
        await DatabaseTaskDispatcher(db).submit(
            user_id="user-1",
            task_type="series_run.execute",
            idempotency_key="run-1:v1",
            payload={"run_id": "run-1"},
        )
        await db.commit()

    claimed = await claim_one(factory, worker_id="worker-a", lease_seconds=60)
    duplicate = await claim_one(factory, worker_id="worker-b", lease_seconds=60)

    assert claimed and claimed.lease_owner == "worker-a"
    assert claimed.status == "running"
    assert claimed.attempt_count == 1
    assert duplicate is None


@pytest.mark.asyncio
async def test_expired_lease_is_recovered_by_another_worker(factory) -> None:
    async with factory() as db:
        execution, _ = await DatabaseTaskDispatcher(db).submit(
            user_id="user-1",
            task_type="series_run.execute",
            idempotency_key="run-1:v1",
            payload={"run_id": "run-1"},
        )
        execution.status = "running"
        execution.lease_owner = "dead-worker"
        execution.lease_expires_at = utc_now() - timedelta(seconds=1)
        execution.attempt_count = 1
        await db.commit()

    recovered = await claim_one(factory, worker_id="worker-b", lease_seconds=60)

    assert recovered and recovered.lease_owner == "worker-b"
    assert recovered.attempt_count == 2


@pytest.mark.asyncio
async def test_pending_task_can_be_cancelled_without_worker(factory) -> None:
    async with factory() as db:
        execution, _ = await DatabaseTaskDispatcher(db).submit(
            user_id="user-1",
            task_type="series_run.execute",
            idempotency_key="run-1:v1",
            payload={"run_id": "run-1"},
        )
        await request_cancel(db, execution)
        await db.commit()

    assert execution.status == "cancelled"
    assert execution.completed_at is not None


@pytest.mark.asyncio
async def test_uncertain_task_requires_explicit_confirmation_before_retry(factory) -> None:
    async with factory() as db:
        execution, _ = await DatabaseTaskDispatcher(db).submit(
            user_id="user-1",
            task_type="series_run.execute",
            idempotency_key="run-1:v1",
            payload={"run_id": "run-1"},
        )
        execution.status = "needs_attention"
        execution.last_error_code = "provider_state_unknown"
        execution.last_error_message = "供应商状态不确定，需要人工确认"
        await db.commit()

        with pytest.raises(TaskTransitionError, match="确认供应商没有重复受理"):
            await retry_execution(db, execution, confirm_uncertain=False)
        await retry_execution(db, execution, confirm_uncertain=True)
        await db.commit()

    assert execution.status == "pending"
    assert execution.next_attempt_at is not None
