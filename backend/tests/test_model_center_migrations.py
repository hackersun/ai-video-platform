from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import sqlite3
import threading
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, delete, event, inspect, text, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.db_migrations.runner import register_production_models
from app.models.model_center import ModelConnection, ModelProfileVersion, ProductionRecipeVersion


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

MODEL_CENTER_SCHEMA = {
    "model_providers": {
        "id": False, "code": False, "display_name": False, "provider_family": False,
        "is_builtin": False, "enabled": False, "revision": False,
        "created_at": False, "updated_at": False,
    },
    "model_profiles": {
        "id": False, "provider_id": False, "profile_key": False, "display_name": False,
        "enabled": False, "revision": False, "created_at": False, "updated_at": False,
    },
    "model_connections": {
        "id": False, "user_id": False, "provider_id": False, "name": False,
        "api_key": True, "api_secret": True, "endpoint_overrides": False,
        "connection_params": False, "status": False, "tested_at": True,
        "created_at": False, "updated_at": False,
    },
    "model_profile_versions": {
        "id": False, "model_id": False, "version": False, "api_model_id": False,
        "driver_key": False, "capabilities": False, "input_contract": False,
        "output_contract": False, "parameter_schema": False, "default_params": False,
        "limits": False, "pricing": False, "prompt_profile_key": True,
        "contract_version": False, "status": False, "checksum": False, "created_at": False,
    },
    "model_bindings": {
        "id": False, "user_id": False, "scope_type": False, "scope_id": False,
        "task": False, "capability": False, "profile_version_id": False,
        "connection_id": False, "priority": False, "route_policy": False,
        "fallback_profile_version_ids": False, "version": False, "is_active": False,
        "revision": False, "created_at": False, "updated_at": False,
    },
    "production_recipe_versions": {
        "id": False, "user_id": False, "recipe_key": False, "name": False,
        "version": False, "status": False, "spec": False, "checksum": False,
        "revision": False, "created_at": False, "published_at": True,
    },
    "model_certification_runs": {
        "id": False, "user_id": False, "profile_version_id": False,
        "connection_id": False, "level": False, "status": False,
        "request_fingerprint": False, "sanitized_evidence": False,
        "estimated_cost_rmb": False, "actual_cost_rmb": False,
        "created_at": False, "completed_at": True,
    },
    "model_execution_snapshots": {
        "id": False, "user_id": False, "run_id": True, "job_id": True,
        "task": False, "capability": False, "profile_version_id": False,
        "connection_id": False, "binding_id": False, "binding_version": False,
        "recipe_version_id": True, "prompt_profile_version_id": True,
        "model_contract_version": False, "sanitized_params": False,
        "checksum": False, "created_at": False,
    },
    "model_config_audit_events": {
        "id": False, "user_id": False, "resource_type": False, "resource_id": False,
        "action": False, "from_version_id": True, "to_version_id": True,
        "reason": False, "sanitized_change_summary": False, "created_at": False,
    },
}

MODEL_CENTER_UNIQUES = {
    "model_providers": {frozenset({"code"})},
    "model_profiles": {frozenset({"provider_id", "profile_key"})},
    "model_connections": {frozenset({"user_id", "provider_id", "name"})},
    "model_profile_versions": {frozenset({"model_id", "version"})},
    "model_bindings": {
        frozenset({"user_id", "scope_type", "scope_id", "task", "capability", "version"}),
    },
    "production_recipe_versions": {frozenset({"user_id", "recipe_key", "version"})},
    "model_certification_runs": set(),
    "model_execution_snapshots": set(),
    "model_config_audit_events": set(),
}


def _create_legacy_model_database(database_path) -> None:
    engine = create_engine(f"sqlite:///{database_path}")
    with engine.begin() as connection:
        for table_name in ("llm_configs", "external_api_configs", "prompt_skills"):
            connection.execute(text(f"CREATE TABLE {table_name} (id VARCHAR(36) PRIMARY KEY)"))
    engine.dispose()


def _column_names(engine, table_name: str) -> set[str]:
    return {column["name"] for column in inspect(engine).get_columns(table_name)}


def _unique_column_sets(inspector, table_name: str) -> set[frozenset[str]]:
    constraints = {
        frozenset(item["column_names"])
        for item in inspector.get_unique_constraints(table_name)
    }
    indexes = {
        frozenset(item["column_names"])
        for item in inspector.get_indexes(table_name)
        if item.get("unique")
    }
    return constraints | indexes


def _create_model_center_engine(tmp_path, name: str):
    engine = create_engine(f"sqlite:///{tmp_path / name}")
    register_production_models()
    Base.metadata.create_all(engine)
    return engine


def _profile_version(**overrides) -> ModelProfileVersion:
    values = {
        "id": "profile-version-1", "model_id": "model-1", "version": 1,
        "api_model_id": "api-model-v1", "driver_key": "driver-1",
        "capabilities": ["video_generation"], "input_contract": {"prompt": "string"},
        "output_contract": {"video_url": "string"}, "parameter_schema": {},
        "default_params": {}, "limits": {}, "pricing": {},
        "prompt_profile_key": "video.default", "contract_version": "v1",
        "status": "draft", "checksum": "a" * 64,
    }
    values.update(overrides)
    return ModelProfileVersion(**values)


def _recipe_version(**overrides) -> ProductionRecipeVersion:
    values = {
        "id": "recipe-version-1", "user_id": "user-1", "recipe_key": "anime.default",
        "name": "Anime Default", "version": 1, "status": "draft",
        "spec": {"stages": ["storyboard"]}, "checksum": "a" * 64,
    }
    values.update(overrides)
    return ProductionRecipeVersion(**values)


def test_model_center_tables_are_created(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'model-center.db'}")

    register_production_models()
    Base.metadata.create_all(engine)

    assert MODEL_CENTER_TABLES <= set(inspect(engine).get_table_names())
    engine.dispose()


def test_model_center_schema_matches_required_columns_nullability_and_uniques(tmp_path):
    engine = _create_model_center_engine(tmp_path, "model-center-contract.db")
    inspector = inspect(engine)

    for table_name, expected_columns in MODEL_CENTER_SCHEMA.items():
        actual_columns = {item["name"]: item["nullable"] for item in inspector.get_columns(table_name)}
        assert actual_columns == expected_columns
        assert _unique_column_sets(inspector, table_name) == MODEL_CENTER_UNIQUES[table_name]

    engine.dispose()


def test_model_connection_encrypts_credentials_before_persistence(tmp_path, monkeypatch):
    from app.models import llm_config as crypto

    monkeypatch.setenv("FERNET_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(crypto, "_fernet_cache", None)
    engine = _create_model_center_engine(tmp_path, "encrypted-connection.db")
    model_connection = ModelConnection(
        id="connection-1", user_id="user-1", provider_id="provider-1", name="primary",
    )

    model_connection.set_api_key_encrypted("key-plaintext")
    model_connection.set_api_secret_encrypted("secret-plaintext")
    with Session(engine) as session:
        session.add(model_connection)
        session.commit()
        session.refresh(model_connection)
        assert model_connection.get_api_key_decrypted() == "key-plaintext"
        assert model_connection.get_api_secret_decrypted() == "secret-plaintext"

    with engine.connect() as connection:
        stored = connection.execute(
            text("SELECT api_key, api_secret FROM model_connections WHERE id = 'connection-1'")
        ).mappings().one()
    assert stored["api_key"] != "key-plaintext"
    assert stored["api_secret"] != "secret-plaintext"
    assert stored["api_key"].startswith("gAAAAA")
    assert stored["api_secret"].startswith("gAAAAA")
    engine.dispose()


@pytest.mark.parametrize("field_name", ["api_key", "api_secret"])
def test_model_connection_rejects_direct_plaintext_credentials(field_name, monkeypatch):
    from app.models import llm_config as crypto

    monkeypatch.setenv("FERNET_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(crypto, "_fernet_cache", None)
    base_values = {
        "id": "connection-plain", "user_id": "user-1",
        "provider_id": "provider-1", "name": "primary",
    }

    with pytest.raises(ValueError, match="Fernet ciphertext"):
        ModelConnection(**base_values, **{field_name: "plaintext-secret"})

    model_connection = ModelConnection(**base_values)
    encrypted = crypto.encrypt_key("backfilled-secret")
    setattr(model_connection, field_name, encrypted)
    assert getattr(model_connection, field_name) == encrypted
    with pytest.raises(ValueError, match="Fernet ciphertext"):
        setattr(model_connection, field_name, "updated-plaintext")


@pytest.mark.parametrize(
    ("row_factory", "edit"),
    [
        (_profile_version, lambda row: setattr(row, "api_model_id", "mutated-model")),
        (_recipe_version, lambda row: setattr(row, "spec", {"stages": ["mutated"]})),
    ],
)
def test_published_versions_allow_publish_transition_but_reject_later_edits(
    tmp_path, row_factory, edit,
):
    engine = _create_model_center_engine(tmp_path, f"append-only-{row_factory.__name__}.db")

    with Session(engine, expire_on_commit=False) as session:
        row = row_factory()
        session.add(row)
        session.commit()
        row.status = "published"
        session.commit()
        edit(row)
        with pytest.raises(ValueError, match="published version is append-only"):
            session.commit()
        session.rollback()

    engine.dispose()


@pytest.mark.parametrize(
    ("row_factory", "edit"),
    [
        (_profile_version, lambda row: setattr(row, "api_model_id", "draft-model")),
        (_recipe_version, lambda row: setattr(row, "spec", {"stages": ["draft-edit"]})),
    ],
)
def test_draft_versions_allow_instance_edits_and_deletes(tmp_path, row_factory, edit):
    engine = _create_model_center_engine(tmp_path, f"draft-delete-{row_factory.__name__}.db")

    with Session(engine, expire_on_commit=False) as session:
        row = row_factory()
        session.add(row)
        session.commit()
        edit(row)
        session.commit()
        session.delete(row)
        session.commit()
        assert session.get(type(row), row.id) is None

    engine.dispose()


@pytest.mark.parametrize("row_factory", [_profile_version, _recipe_version])
def test_published_versions_reject_instance_delete(tmp_path, row_factory):
    engine = _create_model_center_engine(tmp_path, f"published-delete-{row_factory.__name__}.db")

    with Session(engine, expire_on_commit=False) as session:
        row = row_factory(status="published")
        session.add(row)
        session.commit()
        session.delete(row)
        with pytest.raises(ValueError, match="published version is append-only"):
            session.commit()
        session.rollback()
        assert session.get(type(row), row.id) is not None

    engine.dispose()


@pytest.mark.parametrize("model", [ModelProfileVersion, ProductionRecipeVersion])
@pytest.mark.parametrize(
    "statement_factory",
    [lambda model: update(model).values(status="disabled"), lambda model: delete(model)],
)
def test_version_tables_reject_bulk_orm_dml(tmp_path, model, statement_factory):
    engine = _create_model_center_engine(tmp_path, "bulk-version-dml.db")

    with Session(engine) as session:
        with pytest.raises(ValueError, match="bulk UPDATE/DELETE is disabled"):
            session.execute(statement_factory(model))

    engine.dispose()


@pytest.mark.parametrize(
    ("row_factory", "changes"),
    [
        (_profile_version, {"api_model_id": "api-model-v2"}),
        (_recipe_version, {"spec": {"stages": ["storyboard", "render"]}}),
    ],
)
def test_published_versions_create_unique_next_draft_rows(tmp_path, row_factory, changes):
    engine = _create_model_center_engine(tmp_path, f"next-version-{row_factory.__name__}.db")

    with Session(engine, expire_on_commit=False) as session:
        published = row_factory(status="published")
        session.add(published)
        session.commit()
        next_row = published.create_next_version(checksum="b" * 64, **changes)
        assert next_row.id != published.id
        assert next_row.version == published.version + 1
        assert next_row.status == "draft"
        assert next_row.checksum == "b" * 64
        session.add(next_row)
        session.commit()

        duplicate = published.create_next_version(checksum="c" * 64, **changes)
        assert duplicate.id != next_row.id
        session.add(duplicate)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

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
