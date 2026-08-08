from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, update
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session

from app.models.task_execution import TaskExecution, TaskExecutionEvent


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_durable_task_tables_are_created_by_alembic(tmp_path) -> None:
    database_path = tmp_path / "durable-tasks.db"
    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite+aiosqlite:///{database_path}"
    environment.pop("E2E_REQUIRE_ISOLATED_DB", None)

    result = subprocess.run(
        [sys.executable, "scripts/upgrade_database.py"],
        cwd=BACKEND_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    engine = create_engine(f"sqlite:///{database_path}")
    inspector = inspect(engine)

    assert "Database migration complete: 20260809_0004" in result.stdout
    assert {"task_executions", "task_execution_events"} <= set(inspector.get_table_names())
    execution_indexes = {item["name"] for item in inspector.get_indexes("task_executions")}
    assert "ix_task_executions_claim" in execution_indexes
    unique_constraints = {
        tuple(item["column_names"])
        for item in inspector.get_unique_constraints("task_executions")
    }
    assert ("user_id", "task_type", "idempotency_key") in unique_constraints

    with Session(engine) as session:
        execution = TaskExecution(
            id="migration-task",
            user_id="user-1",
            task_type="migration.contract",
            idempotency_key="migration-contract",
            payload={},
        )
        session.add_all(
            [
                execution,
                TaskExecutionEvent(
                    id="migration-event",
                    execution_id=execution.id,
                    event_type="queued",
                    status="pending",
                    message="任务已进入队列",
                ),
            ]
        )
        session.commit()
        with pytest.raises(DatabaseError, match="append-only"):
            session.execute(
                update(TaskExecutionEvent)
                .where(TaskExecutionEvent.id == "migration-event")
                .values(message="被批量篡改")
            )
