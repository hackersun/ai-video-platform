"""PostgreSQL-only schema and migration contract.

The main regression suite intentionally uses isolated SQLite databases. This file
uses production-sized identifiers and verifies the PostgreSQL path against a real
service in CI.
"""

from __future__ import annotations

import os
import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import sync_engine
from app.db_migrations.script_chapter_lineage import add_script_chapter_lineage
from app.features.task_execution.repository import claim_one
from app.models.task_execution import TaskExecution


pytestmark = pytest.mark.skipif(
    sync_engine.dialect.name != "postgresql",
    reason="requires the PostgreSQL contract job",
)


def test_postgresql_schema_and_json_lineage_backfill() -> None:
    assert os.environ["DATABASE_URL"].startswith("postgresql")
    user_id = str(uuid4())
    novel_id = str(uuid4())
    chapter_id = str(uuid4())
    script_id = str(uuid4())

    with sync_engine.begin() as connection:
        connection.execute(
            text("INSERT INTO novels (id, user_id, title) VALUES (:id, :user_id, :title)"),
            {"id": novel_id, "user_id": user_id, "title": "PostgreSQL contract novel"},
        )
        connection.execute(
            text(
                "INSERT INTO chapters "
                "(id, novel_id, user_id, title, chapter_number) "
                "VALUES (:id, :novel_id, :user_id, :title, 1)"
            ),
            {
                "id": chapter_id,
                "novel_id": novel_id,
                "user_id": user_id,
                "title": "Contract chapter",
            },
        )
        connection.execute(
            text(
                "INSERT INTO scripts (id, user_id, novel_id, title, extra_data) "
                "VALUES (:id, :user_id, :novel_id, :title, CAST(:extra_data AS JSON))"
            ),
            {
                "id": script_id,
                "user_id": user_id,
                "novel_id": novel_id,
                "title": "Legacy lineage script",
                "extra_data": f'{{"chapter_id": "{chapter_id}"}}',
            },
        )

    add_script_chapter_lineage(sync_engine)

    with sync_engine.connect() as connection:
        stored_chapter_id = connection.execute(
            text("SELECT chapter_id FROM scripts WHERE id = :id"),
            {"id": script_id},
        ).scalar_one()
    assert stored_chapter_id == chapter_id


def test_postgresql_auth_session_and_notification_schema() -> None:
    inspector = inspect(sync_engine)
    assert {"users", "user_sessions", "auth_notification_outbox"}.issubset(inspector.get_table_names())
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    assert {"account_status", "email_verified_at", "email_verification_token_hash"}.issubset(user_columns)
    session_indexes = {index["name"] for index in inspector.get_indexes("user_sessions")}
    assert "ix_user_sessions_user_active" in session_indexes
    outbox_indexes = {index["name"] for index in inspector.get_indexes("auth_notification_outbox")}
    assert "ix_auth_notification_outbox_delivery" in outbox_indexes


def test_postgresql_durable_task_schema_and_concurrent_claim() -> None:
    inspector = inspect(sync_engine)
    assert {"task_executions", "task_execution_events"}.issubset(inspector.get_table_names())
    execution_indexes = {index["name"] for index in inspector.get_indexes("task_executions")}
    assert {"ix_task_executions_claim", "ix_task_executions_user_status"}.issubset(execution_indexes)
    with sync_engine.connect() as connection:
        trigger_names = set(
            connection.execute(
                text(
                    "SELECT tgname FROM pg_trigger "
                    "WHERE tgrelid = 'task_execution_events'::regclass AND NOT tgisinternal"
                )
            ).scalars()
        )
    assert "trg_task_execution_events_append_only" in trigger_names

    async def verify_single_winner() -> None:
        async_url = os.environ["DATABASE_URL"].replace(
            "postgresql://", "postgresql+asyncpg://", 1
        )
        engine = create_async_engine(async_url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        execution_id = str(uuid4())
        async with factory() as db:
            db.add(
                TaskExecution(
                    id=execution_id,
                    user_id=str(uuid4()),
                    task_type="postgres.contract",
                    idempotency_key=str(uuid4()),
                    payload={},
                    priority=1_000_000,
                )
            )
            await db.commit()
        try:
            claims = await asyncio.gather(
                claim_one(factory, worker_id="postgres-worker-a", lease_seconds=60),
                claim_one(factory, worker_id="postgres-worker-b", lease_seconds=60),
            )
            assert sum(claim is not None and claim.id == execution_id for claim in claims) == 1
        finally:
            await engine.dispose()

    asyncio.run(verify_single_winner())
