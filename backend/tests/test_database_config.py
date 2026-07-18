from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event, inspect as sqlalchemy_inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.db_migrations import live_canary_provider_operations as live_canary_migration


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_TABLES = {
    "entity_extraction_runs",
    "entity_feedback",
    "live_canary_provider_operations",
    "production_state_events",
    "provider_asset_bindings",
    "quality_evaluations",
    "series_production_runs",
    "story_entity_mentions",
    "model_providers",
    "model_profiles",
    "model_connections",
    "model_profile_versions",
    "model_bindings",
    "production_recipe_versions",
    "model_certification_runs",
    "model_execution_snapshots",
    "model_config_audit_events",
}


def _run_subprocess(
    script: str,
    *,
    env_updates: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("DATABASE_URL", None)
    env.pop("E2E_REQUIRE_ISOLATED_DB", None)
    env.update(env_updates or {})
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def _run_database_import(
    *,
    database_url: str | None = None,
    require_isolated: bool = False,
) -> subprocess.CompletedProcess[str]:
    env_updates = {}
    if database_url is not None:
        env_updates["DATABASE_URL"] = database_url
    if require_isolated:
        env_updates["E2E_REQUIRE_ISOLATED_DB"] = "true"

    script = """
import json
from app.core import database

print(json.dumps({
    "async_url": database.engine.url.render_as_string(hide_password=False),
    "sync_url": database.sync_engine.url.render_as_string(hide_password=False),
    "diagnostic": (
        database.DATABASE_DIAGNOSTIC._asdict()
        if hasattr(database, "DATABASE_DIAGNOSTIC")
        else None
    ),
}))
"""
    return _run_subprocess(script, env_updates=env_updates)


def _read_result(process: subprocess.CompletedProcess[str]) -> dict[str, object]:
    assert process.returncode == 0, process.stderr
    return json.loads(process.stdout)


def test_database_url_controls_async_and_sync_sqlite_paths():
    result = _read_result(
        _run_database_import(database_url="sqlite+aiosqlite:////tmp/wave-1a.db")
    )

    assert result["async_url"] == "sqlite+aiosqlite:////tmp/wave-1a.db"
    assert result["sync_url"] == "sqlite:////tmp/wave-1a.db"


def test_default_database_url_is_preserved():
    result = _read_result(_run_database_import())

    assert result["async_url"] == "sqlite+aiosqlite:///./ai_video.db"
    assert result["sync_url"] == "sqlite:///./ai_video.db"


def test_subprocesses_do_not_inherit_database_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:////Users/example/leaked.db")
    monkeypatch.setenv("E2E_REQUIRE_ISOLATED_DB", "true")

    result = _read_result(_run_database_import())

    assert result["async_url"] == "sqlite+aiosqlite:///./ai_video.db"


@pytest.mark.parametrize(
    "database_url",
    [
        None,
        "sqlite+aiosqlite:///",
        "sqlite+aiosqlite:////Users/example/outside-tmp.db",
    ],
)
def test_isolated_mode_rejects_unsafe_sqlite_paths(database_url):
    process = _run_database_import(
        database_url=database_url,
        require_isolated=True,
    )

    assert process.returncode != 0
    assert "E2E_REQUIRE_ISOLATED_DB requires a SQLite .db path under /tmp" in process.stderr


def test_isolated_mode_accepts_tmp_sqlite_database():
    result = _read_result(
        _run_database_import(
            database_url="sqlite+aiosqlite:////tmp/wave-1a-isolated.db",
            require_isolated=True,
        )
    )

    assert result["diagnostic"] == {
        "async_url": "sqlite+aiosqlite:////tmp/wave-1a-isolated.db",
        "sync_url": "sqlite:////tmp/wave-1a-isolated.db",
        "isolation_required": True,
        "resolved_sqlite_path": str(Path("/tmp/wave-1a-isolated.db").resolve()),
    }


def test_database_diagnostic_is_read_only():
    script = """
from app.core.database import DATABASE_DIAGNOSTIC
DATABASE_DIAGNOSTIC.async_url = "sqlite+aiosqlite:////tmp/changed.db"
"""
    process = _run_subprocess(script)

    assert process.returncode != 0
    assert "can't set attribute" in process.stderr


def test_plain_postgresql_url_is_normalized_for_async_and_sync_engines():
    script = """
import json
from app.core.database import _derive_sync_database_url, _normalize_async_database_url

async_url = _normalize_async_database_url("postgresql://user:secret@db.example/app")
print(json.dumps({"async_url": async_url, "sync_url": _derive_sync_database_url(async_url)}))
"""
    process = _run_subprocess(script)

    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == {
        "async_url": "postgresql+asyncpg://user:secret@db.example/app",
        "sync_url": "postgresql+psycopg2://user:secret@db.example/app",
    }


def test_missing_postgresql_drivers_fail_with_pre_engine_configuration_error():
    script = """
import importlib.util

real_find_spec = importlib.util.find_spec
importlib.util.find_spec = lambda name, *args, **kwargs: (
    None if name in {"asyncpg", "psycopg2"} else real_find_spec(name, *args, **kwargs)
)
from app.core import database
"""
    process = _run_subprocess(
        script,
        env_updates={"DATABASE_URL": "postgresql://user:secret@db.example/app"},
    )

    assert process.returncode != 0
    assert "PostgreSQL database drivers are not installed" in process.stderr
    assert "asyncpg (async)" in process.stderr
    assert "psycopg2 (sync)" in process.stderr
    assert "create_async_engine" not in process.stderr


def test_database_diagnostic_masks_credentials_and_reports_no_sqlite_path():
    script = """
import json
from app.core.database import _build_database_diagnostic

diagnostic = _build_database_diagnostic(
    "postgresql+asyncpg://user:secret@db.example/app",
    "postgresql+psycopg2://user:secret@db.example/app",
    False,
)
print(json.dumps(diagnostic._asdict()))
"""
    process = _run_subprocess(script)

    assert process.returncode == 0, process.stderr
    assert "secret" not in process.stdout
    assert json.loads(process.stdout) == {
        "async_url": "postgresql+asyncpg://user:***@db.example/app",
        "sync_url": "postgresql+psycopg2://user:***@db.example/app",
        "isolation_required": False,
        "resolved_sqlite_path": None,
    }


def test_init_db_backfills_live_canary_artifact_id(tmp_path):
    database_path = tmp_path / "legacy-live-canary.db"
    script = """
import json
from sqlalchemy import create_engine, inspect, text

from init_db import init_db

engine = create_engine(%r)
with engine.begin() as connection:
    connection.execute(text(\"\"\"
        CREATE TABLE live_canary_provider_operations (
            id VARCHAR(36) PRIMARY KEY,
            run_id VARCHAR(36) NOT NULL,
            user_id VARCHAR(36) NOT NULL,
            reservation_id VARCHAR(200) NOT NULL,
            capability VARCHAR(20) NOT NULL,
            job_type VARCHAR(40) NOT NULL,
            job_id VARCHAR(100) NOT NULL,
            provider_task_id VARCHAR(200),
            status VARCHAR(30) NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        )
    \"\"\"))

init_db()
columns = {item[\"name\"] for item in inspect(engine).get_columns(\"live_canary_provider_operations\")}
indexes = {item[\"name\"] for item in inspect(engine).get_indexes(\"live_canary_provider_operations\")}
tables = set(inspect(engine).get_table_names())
print(json.dumps({\"columns\": sorted(columns), \"indexes\": sorted(indexes), \"tables\": sorted(tables)}))
""" % f"sqlite:///{database_path}"
    process = _run_subprocess(
        script,
        env_updates={"DATABASE_URL": f"sqlite+aiosqlite:///{database_path}"},
    )

    assert process.returncode == 0, process.stderr
    schema = json.loads(process.stdout.splitlines()[-1])
    assert {"artifact_id", "cost_source", "recovery_reason"} <= set(schema["columns"])
    assert "ix_live_canary_provider_operations_artifact_id" in schema["indexes"]
    assert PRODUCTION_TABLES <= set(schema["tables"])


def test_init_db_async_backfills_live_canary_artifact_id(tmp_path):
    database_path = tmp_path / "legacy-live-canary-async.db"
    script = """
import asyncio
import json
from sqlalchemy import create_engine, inspect, text

from init_db import init_db_async

engine = create_engine(%r)
with engine.begin() as connection:
    connection.execute(text(
        "CREATE TABLE live_canary_provider_operations (id VARCHAR(36) PRIMARY KEY)"
    ))

asyncio.run(init_db_async())
columns = {item["name"] for item in inspect(engine).get_columns("live_canary_provider_operations")}
indexes = {item["name"] for item in inspect(engine).get_indexes("live_canary_provider_operations")}
tables = set(inspect(engine).get_table_names())
print(json.dumps({"columns": sorted(columns), "indexes": sorted(indexes), "tables": sorted(tables)}))
""" % f"sqlite:///{database_path}"
    process = _run_subprocess(
        script,
        env_updates={"DATABASE_URL": f"sqlite+aiosqlite:///{database_path}"},
    )

    assert process.returncode == 0, process.stderr
    schema = json.loads(process.stdout.splitlines()[-1])
    assert {"artifact_id", "cost_source", "recovery_reason"} <= set(schema["columns"])
    assert "ix_live_canary_provider_operations_artifact_id" in schema["indexes"]
    assert PRODUCTION_TABLES <= set(schema["tables"])


def test_live_canary_artifact_migration_tolerates_concurrent_initializers(tmp_path):
    database_path = tmp_path / "concurrent-live-canary.db"
    script = """
import json
from threading import Barrier, Lock, Thread
from sqlalchemy import create_engine, text
import app.db_migrations.live_canary_provider_operations as migration

engine = create_engine(%r, connect_args={"check_same_thread": False})
with engine.begin() as connection:
    connection.execute(text("CREATE TABLE live_canary_provider_operations (id VARCHAR(36) PRIMARY KEY)"))

real_inspect = migration.inspect
barrier = Barrier(2)
counter_lock = Lock()
remaining_reads = 2

class InspectorBarrier:
    def __init__(self, inspector): self.inspector = inspector
    def has_table(self, name): return self.inspector.has_table(name)
    def get_columns(self, name):
        global remaining_reads
        columns = self.inspector.get_columns(name)
        with counter_lock:
            should_wait = remaining_reads > 0
            if should_wait: remaining_reads -= 1
        if should_wait: barrier.wait(timeout=5)
        return columns

migration.inspect = lambda bind: InspectorBarrier(real_inspect(bind))
errors = []

def run():
    try: migration.add_artifact_id(engine)
    except Exception as error: errors.append(f"{type(error).__name__}:{error}")

threads = [Thread(target=run), Thread(target=run)]
for thread in threads: thread.start()
for thread in threads: thread.join(timeout=10)
if any(thread.is_alive() for thread in threads):
    barrier.abort()
    errors.append("initializer thread timed out")
print(json.dumps(errors))
""" % f"sqlite:///{database_path}"
    process = _run_subprocess(script)

    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout.splitlines()[-1]) == []


def _create_legacy_live_canary_table(database_path: Path) -> None:
    engine = create_engine(f"sqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE live_canary_provider_operations ("
                "id VARCHAR(36) PRIMARY KEY)"
            )
        )
    engine.dispose()


def _coordinate_legacy_column_reads(monkeypatch) -> None:
    barrier = threading.Barrier(2)
    counter_lock = threading.Lock()
    remaining_reads = 2

    def coordinated_inspect(bind):
        inspector = sqlalchemy_inspect(bind)
        original_get_columns = inspector.get_columns

        def get_columns(*args, **kwargs):
            nonlocal remaining_reads
            columns = original_get_columns(*args, **kwargs)
            with counter_lock:
                should_wait = remaining_reads > 0
                if should_wait:
                    remaining_reads -= 1
            if should_wait:
                barrier.wait(timeout=5)
            return columns

        inspector.get_columns = get_columns
        return inspector

    monkeypatch.setattr(live_canary_migration, "inspect", coordinated_inspect)


def _assert_artifact_schema(database_path: Path) -> None:
    engine = create_engine(f"sqlite:///{database_path}")
    inspector = sqlalchemy_inspect(engine)
    columns = {item["name"] for item in inspector.get_columns("live_canary_provider_operations")}
    indexes = {item["name"] for item in inspector.get_indexes("live_canary_provider_operations")}
    engine.dispose()
    assert {"artifact_id", "cost_source", "recovery_reason"} <= columns
    assert "ix_live_canary_provider_operations_artifact_id" in indexes


def test_live_canary_migration_is_sync_concurrency_safe_for_30_rounds(
    tmp_path,
    monkeypatch,
):
    for round_number in range(30):
        database_path = tmp_path / f"sync-race-{round_number}.db"
        _create_legacy_live_canary_table(database_path)
        _coordinate_legacy_column_reads(monkeypatch)
        engines = [create_engine(f"sqlite:///{database_path}") for _ in range(2)]

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(live_canary_migration.add_artifact_id, engine) for engine in engines]
            for future in futures:
                future.result(timeout=10)

        for engine in engines:
            engine.dispose()
        _assert_artifact_schema(database_path)


def test_live_canary_migration_is_async_concurrency_safe_for_30_rounds(
    tmp_path,
    monkeypatch,
):
    def run_migration(database_url: str) -> None:
        async def execute() -> None:
            engine = create_async_engine(database_url)
            try:
                await live_canary_migration.add_artifact_id_async(engine)
            finally:
                await engine.dispose()

        asyncio.run(execute())

    for round_number in range(30):
        database_path = tmp_path / f"async-race-{round_number}.db"
        _create_legacy_live_canary_table(database_path)
        _coordinate_legacy_column_reads(monkeypatch)
        database_url = f"sqlite+aiosqlite:///{database_path}"

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(run_migration, database_url) for _ in range(2)]
            for future in futures:
                future.result(timeout=10)

        _assert_artifact_schema(database_path)


def test_live_canary_migration_does_not_swallow_non_duplicate_ddl_errors(tmp_path):
    database_path = tmp_path / "non-duplicate-error.db"
    _create_legacy_live_canary_table(database_path)
    engine = create_engine(f"sqlite:///{database_path}")

    @event.listens_for(engine, "before_cursor_execute")
    def fail_alter(_connection, _cursor, statement, _parameters, _context, _executemany):
        if statement.startswith("ALTER TABLE live_canary_provider_operations"):
            raise sqlite3.OperationalError("simulated disk I/O error")

    with pytest.raises(sqlite3.OperationalError, match="simulated disk I/O error"):
        live_canary_migration.add_artifact_id(engine)
    engine.dispose()


def test_postgresql_duplicate_index_race_recognizes_catalog_unique_violation():
    error = SimpleNamespace(orig=SimpleNamespace(sqlstate="23505"))

    assert live_canary_migration._is_duplicate_index(error, "postgresql") is True
