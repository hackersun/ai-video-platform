from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import sqlite3
import threading
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import create_async_engine

from tests.model_center_helpers import create_model_center_engine


MODEL_CENTER_TRIGGER_NAMES = {
    "trg_model_profile_versions_published_update",
    "trg_model_profile_versions_published_delete",
    "trg_production_recipe_versions_published_update",
    "trg_production_recipe_versions_published_delete",
    "trg_prompt_profile_versions_published_update",
    "trg_prompt_profile_versions_published_delete",
    "trg_prompt_profiles_published_history_update",
    "trg_prompt_profiles_published_history_delete",
}


def _create_legacy_model_database(database_path) -> None:
    engine = create_engine(f"sqlite:///{database_path}")
    with engine.begin() as connection:
        for table_name in ("llm_configs", "external_api_configs", "prompt_skills"):
            connection.execute(text(f"CREATE TABLE {table_name} (id VARCHAR(36) PRIMARY KEY)"))
    engine.dispose()


def _column_names(engine, table_name: str) -> set[str]:
    return {column["name"] for column in inspect(engine).get_columns(table_name)}


def _sqlite_trigger_names(engine) -> set[str]:
    with engine.connect() as connection:
        return {
            row[0]
            for row in connection.execute(
                text("SELECT name FROM sqlite_master WHERE type = 'trigger'")
            )
        }


def test_model_center_migration_is_sync_idempotent(tmp_path):
    from app.db_migrations.model_center import add_model_center_links

    database_path = tmp_path / "legacy-sync.db"
    _create_legacy_model_database(database_path)
    engine = create_engine(f"sqlite:///{database_path}")

    add_model_center_links(engine)
    add_model_center_links(engine)

    assert "connection_id" in _column_names(engine, "llm_configs")
    assert "connection_id" in _column_names(engine, "external_api_configs")
    assert "prompt_profile_version_id" in _column_names(engine, "prompt_skills")
    engine.dispose()


def test_model_center_migration_is_async_idempotent(tmp_path):
    from app.db_migrations.model_center import add_model_center_links_async

    database_path = tmp_path / "legacy-async.db"
    _create_legacy_model_database(database_path)

    async def migrate() -> None:
        engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
        try:
            await add_model_center_links_async(engine)
            await add_model_center_links_async(engine)
        finally:
            await engine.dispose()

    asyncio.run(migrate())
    engine = create_engine(f"sqlite:///{database_path}")
    assert "connection_id" in _column_names(engine, "llm_configs")
    assert "connection_id" in _column_names(engine, "external_api_configs")
    assert "prompt_profile_version_id" in _column_names(engine, "prompt_skills")
    engine.dispose()


def test_model_center_sqlite_trigger_migration_is_sync_idempotent(tmp_path):
    from app.db_migrations.model_center import add_model_center_links

    engine = create_model_center_engine(tmp_path, "trigger-sync-idempotent.db")
    add_model_center_links(engine)
    add_model_center_links(engine)

    assert _sqlite_trigger_names(engine) == MODEL_CENTER_TRIGGER_NAMES
    engine.dispose()


def test_model_center_sqlite_trigger_migration_is_async_idempotent(tmp_path):
    from app.db_migrations.model_center import add_model_center_links_async

    database_path = tmp_path / "trigger-async-idempotent.db"
    engine = create_model_center_engine(tmp_path, database_path.name)
    engine.dispose()

    async def migrate() -> None:
        async_engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
        try:
            await add_model_center_links_async(async_engine)
            await add_model_center_links_async(async_engine)
        finally:
            await async_engine.dispose()

    asyncio.run(migrate())
    engine = create_engine(f"sqlite:///{database_path}")
    assert _sqlite_trigger_names(engine) == MODEL_CENTER_TRIGGER_NAMES
    engine.dispose()


def test_postgresql_trigger_ddl_is_idempotent_and_schema_qualified():
    from app.db_migrations.model_center import _postgresql_trigger_statements

    statements = _postgresql_trigger_statements(
        "tenant_schema",
        ("model_profile_versions", "production_recipe_versions"),
    )
    ddl = "\n".join(str(statement) for statement in statements)

    assert "pg_advisory_xact_lock(hashtext('model_center_version_guards'))" in ddl
    assert '"tenant_schema"."model_center_reject_published_mutation"' in ddl
    assert 'ON "tenant_schema"."model_profile_versions"' in ddl
    assert 'ON "tenant_schema"."production_recipe_versions"' in ddl
    assert "namespace.nspname = 'tenant_schema'" in ddl
    assert "target.relname = 'model_profile_versions'" in ddl
    assert "target.relname = 'production_recipe_versions'" in ddl
    assert "IF NOT EXISTS" in ddl
    assert "BEFORE UPDATE OR DELETE" in ddl
    assert "OLD.status = 'published'" in ddl


def test_postgresql_prompt_profile_parent_guard_is_schema_qualified():
    from app.db_migrations.model_center import _postgresql_prompt_profile_parent_guard_statements

    ddl = "\n".join(str(statement) for statement in (
        _postgresql_prompt_profile_parent_guard_statements("tenant_schema")
    ))

    assert 'ON "tenant_schema"."prompt_profiles"' in ddl
    assert 'FROM "tenant_schema"."prompt_profile_versions"' in ddl
    assert "version.status = 'published'" in ddl
    assert "version.profile_id = OLD.id" in ddl


def _coordinate_initial_column_reads(monkeypatch, migration) -> None:
    real_inspect = migration.inspect
    barrier = threading.Barrier(2)
    lock = threading.Lock()
    reads_remaining = 2

    def coordinated_inspect(bind):
        inspector = real_inspect(bind)
        get_columns = inspector.get_columns

        def wait_for_peer(*args, **kwargs):
            nonlocal reads_remaining
            columns = get_columns(*args, **kwargs)
            with lock:
                should_wait = reads_remaining > 0
                reads_remaining -= 1
            if should_wait:
                barrier.wait(timeout=5)
            return columns

        inspector.get_columns = wait_for_peer
        return inspector

    monkeypatch.setattr(migration, "inspect", coordinated_inspect)


def test_model_center_migration_recovers_sync_duplicate_column_race(tmp_path, monkeypatch):
    import app.db_migrations.model_center as migration

    database_path = tmp_path / "sync-race.db"
    _create_legacy_model_database(database_path)
    _coordinate_initial_column_reads(monkeypatch, migration)
    engines = [create_engine(f"sqlite:///{database_path}") for _ in range(2)]

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(migration.add_model_center_links, engine) for engine in engines]
        for future in futures:
            future.result(timeout=10)

    for engine in engines:
        engine.dispose()
    engine = create_engine(f"sqlite:///{database_path}")
    assert "connection_id" in _column_names(engine, "llm_configs")
    engine.dispose()


def test_model_center_migration_recovers_async_duplicate_column_race(tmp_path, monkeypatch):
    import app.db_migrations.model_center as migration

    database_path = tmp_path / "async-race.db"
    _create_legacy_model_database(database_path)
    _coordinate_initial_column_reads(monkeypatch, migration)

    def migrate() -> None:
        async def execute() -> None:
            engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
            try:
                await migration.add_model_center_links_async(engine)
            finally:
                await engine.dispose()

        asyncio.run(execute())

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(migrate) for _ in range(2)]
        for future in futures:
            future.result(timeout=10)

    engine = create_engine(f"sqlite:///{database_path}")
    assert "connection_id" in _column_names(engine, "llm_configs")
    engine.dispose()


def test_model_center_migration_propagates_non_duplicate_ddl_errors(tmp_path):
    from app.db_migrations.model_center import add_model_center_links

    database_path = tmp_path / "non-duplicate-error.db"
    _create_legacy_model_database(database_path)
    engine = create_engine(f"sqlite:///{database_path}")

    @event.listens_for(engine, "before_cursor_execute")
    def fail_alter(_connection, _cursor, statement, _parameters, _context, _executemany):
        if statement.startswith("ALTER TABLE llm_configs"):
            raise OperationalError(
                statement,
                None,
                sqlite3.OperationalError("simulated disk I/O error"),
            )

    with pytest.raises(OperationalError, match="simulated disk I/O error"):
        add_model_center_links(engine)
    engine.dispose()


def test_postgresql_duplicate_column_sqlstate_is_recognized():
    from app.db_migrations.model_center import _is_duplicate_column

    error = SimpleNamespace(orig=SimpleNamespace(sqlstate="42701"))
    assert _is_duplicate_column(error, "postgresql", "connection_id") is True
