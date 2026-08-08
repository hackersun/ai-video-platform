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
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import sync_engine
from app.db_migrations.script_chapter_lineage import add_script_chapter_lineage
from app.features.task_execution.repository import claim_one
from app.models.task_execution import TaskExecution
from app.models.billing import BillingAccount, BillingReservation
from app.features.billing.service import credit_account, reserve_charge


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


def test_postgresql_billing_schema_immutability_and_concurrent_reserve() -> None:
    inspector = inspect(sync_engine)
    assert {"billing_accounts", "billing_reservations", "billing_ledger_entries", "usage_events", "provider_reconciliations"}.issubset(inspector.get_table_names())
    with sync_engine.connect() as connection:
        triggers = set(connection.execute(text(
            "SELECT tgname FROM pg_trigger WHERE tgrelid = 'billing_ledger_entries'::regclass AND NOT tgisinternal"
        )).scalars())
    assert "trg_billing_ledger_entries_append_only" in triggers

    async def verify_single_reservation_winner() -> None:
        async_url = os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(async_url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        account = BillingAccount(owner_type="user", owner_id=str(uuid4()), max_concurrent_jobs=1)
        async with factory() as db:
            db.add(account)
            await db.commit()
            await credit_account(db, account_id=account.id, amount_micros=5_000_000, actor_user_id="contract-admin", reason="并发合同充值", idempotency_key=str(uuid4()))

        async def attempt(label: str):
            async with factory() as db:
                return await reserve_charge(
                    db, account_id=account.id, user_id=account.owner_id, project_id=None,
                    provider_operation_id=str(uuid4()), idempotency_key=f"request-{label}-{uuid4()}",
                    supplier_estimate_micros=1_000_000,
                )
        try:
            results = await asyncio.gather(attempt("a"), attempt("b"), return_exceptions=True)
            assert sum(isinstance(item, BillingReservation) for item in results) == 1, repr(results)
            async with factory() as db:
                stored = await db.get(BillingAccount, account.id)
                assert stored.active_reservations == 1
                assert stored.reserved_micros == 1_000_000
        finally:
            await engine.dispose()

    asyncio.run(verify_single_reservation_winner())


def test_postgresql_private_media_schema_and_append_only_receipts() -> None:
    inspector = inspect(sync_engine)
    assert {
        "media_objects", "provider_media_inputs", "media_deletion_requests",
        "media_deletion_receipts",
    }.issubset(inspector.get_table_names())
    with sync_engine.begin() as connection:
        triggers = set(connection.execute(text(
            "SELECT tgname FROM pg_trigger "
            "WHERE tgrelid = 'media_deletion_receipts'::regclass AND NOT tgisinternal"
        )).scalars())
    assert "trg_media_deletion_receipts_append_only" in triggers

    media_id = str(uuid4())
    receipt_id = str(uuid4())
    with sync_engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO media_objects "
            "(id, user_id, media_kind, lifecycle_class, storage_provider, object_key, sha256, "
            "size_bytes, content_type, status, legal_hold, media_metadata, created_at, updated_at) "
            "VALUES (:id, :user_id, 'video', 'final', 'qiniu', :object_key, :sha256, 1, "
            "'video/mp4', 'active', false, CAST('{}' AS JSON), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ), {"id": media_id, "user_id": str(uuid4()), "object_key": f"private/final/{media_id}.mp4", "sha256": "a" * 64})
        connection.execute(text(
            "INSERT INTO media_deletion_receipts "
            "(id, media_object_id, request_id, outcome, object_key_sha256, detail, created_at) "
            "VALUES (:id, :media_id, :request_id, 'deleted', :sha256, '对象已删除', CURRENT_TIMESTAMP)"
        ), {"id": receipt_id, "media_id": media_id, "request_id": str(uuid4()), "sha256": "b" * 64})
    with pytest.raises(DBAPIError, match="append-only"):
        with sync_engine.begin() as connection:
            connection.execute(text(
                "UPDATE media_deletion_receipts SET detail = '被篡改' WHERE id = :id"
            ), {"id": receipt_id})
