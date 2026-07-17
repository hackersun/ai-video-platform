from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.database import Base
from app.db_migrations.runner import register_production_models


MODEL_CENTER_TABLES = {
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


def _create_legacy_model_database(database_path) -> None:
    engine = create_engine(f"sqlite:///{database_path}")
    with engine.begin() as connection:
        for table_name in ("llm_configs", "external_api_configs", "prompt_skills"):
            connection.execute(text(f"CREATE TABLE {table_name} (id VARCHAR(36) PRIMARY KEY)"))
    engine.dispose()


def _column_names(engine, table_name: str) -> set[str]:
    return {column["name"] for column in inspect(engine).get_columns(table_name)}


def test_model_center_tables_are_created(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'model-center.db'}")

    register_production_models()
    Base.metadata.create_all(engine)

    assert MODEL_CENTER_TABLES <= set(inspect(engine).get_table_names())
    engine.dispose()


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
