from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import insert, inspect, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import credential_encryption
from app.core.credential_encryption import validate_fernet_ciphertext
from app.models.model_center import ModelConnection
from tests.model_center_helpers import create_model_center_engine


MODEL_CENTER_TABLES = {
    "model_providers", "model_profiles", "model_connections", "model_profile_versions",
    "model_bindings", "production_recipe_versions", "model_certification_runs",
    "model_execution_snapshots", "model_config_audit_events",
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
        "revision": False, "created_at": False, "updated_at": False,
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

MODEL_CONNECTION_CHECKS = {
    "ck_model_connection_api_key_fernet",
    "ck_model_connection_api_secret_fernet",
}


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


def test_model_center_tables_are_created(tmp_path):
    engine = create_model_center_engine(tmp_path, "model-center.db")
    assert MODEL_CENTER_TABLES <= set(inspect(engine).get_table_names())
    engine.dispose()


def test_model_center_schema_matches_required_columns_nullability_and_uniques(tmp_path):
    engine = create_model_center_engine(tmp_path, "model-center-contract.db")
    inspector = inspect(engine)

    for table_name, expected_columns in MODEL_CENTER_SCHEMA.items():
        actual_columns = {item["name"]: item["nullable"] for item in inspector.get_columns(table_name)}
        assert actual_columns == expected_columns
        assert _unique_column_sets(inspector, table_name) == MODEL_CENTER_UNIQUES[table_name]
    assert {
        item["name"] for item in inspector.get_check_constraints("model_connections")
    } == MODEL_CONNECTION_CHECKS
    engine.dispose()


def test_model_connection_encrypts_credentials_before_persistence(tmp_path, monkeypatch):
    monkeypatch.setenv("FERNET_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(credential_encryption, "_fernet_cache", None)
    engine = create_model_center_engine(tmp_path, "encrypted-connection.db")
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
    monkeypatch.setenv("FERNET_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(credential_encryption, "_fernet_cache", None)
    base_values = {
        "id": "connection-plain", "user_id": "user-1",
        "provider_id": "provider-1", "name": "primary",
    }

    with pytest.raises(ValueError, match="Fernet ciphertext"):
        ModelConnection(**base_values, **{field_name: "plaintext-secret"})
    model_connection = ModelConnection(**base_values)
    encrypted = credential_encryption.encrypt_key("backfilled-secret")
    setattr(model_connection, field_name, encrypted)
    assert getattr(model_connection, field_name) == encrypted
    with pytest.raises(ValueError, match="Fernet ciphertext"):
        setattr(model_connection, field_name, "updated-plaintext")


def test_model_connection_rejects_malformed_fernet_looking_ciphertext(monkeypatch):
    monkeypatch.setenv("FERNET_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(credential_encryption, "_fernet_cache", None)
    malformed = "gAAAAA" + "x" * 94

    with pytest.raises(ValueError, match="Fernet ciphertext"):
        ModelConnection(
            id="connection-malformed", user_id="user-1", provider_id="provider-1",
            name="primary", api_key=malformed,
        )


def test_validate_fernet_ciphertext_rebinds_cache_after_key_rotation(monkeypatch):
    first_key = Fernet.generate_key()
    second_key = Fernet.generate_key()
    monkeypatch.setattr(credential_encryption, "_fernet_cache", None)
    monkeypatch.setenv("FERNET_KEY", first_key.decode())
    first_token = credential_encryption.encrypt_key("first-secret")
    assert validate_fernet_ciphertext(first_token) == first_token

    monkeypatch.setenv("FERNET_KEY", second_key.decode())
    second_token = credential_encryption.encrypt_key("second-secret")
    assert validate_fernet_ciphertext(second_token) == second_token
    with pytest.raises(ValueError, match="Fernet ciphertext"):
        validate_fernet_ciphertext(first_token)


@pytest.mark.parametrize("operation", ["insert", "update"])
def test_model_connection_check_constraints_reject_bulk_plaintext(
    tmp_path, monkeypatch, operation,
):
    monkeypatch.setenv("FERNET_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(credential_encryption, "_fernet_cache", None)
    engine = create_model_center_engine(tmp_path, f"connection-check-{operation}.db")
    encrypted = credential_encryption.encrypt_key("valid-key")

    with Session(engine) as session:
        if operation == "insert":
            statement = insert(ModelConnection).values(
                id="bulk-connection", user_id="user-1", provider_id="provider-1",
                name="bulk", api_key="plaintext-key",
            )
        else:
            session.execute(
                insert(ModelConnection).values(
                    id="bulk-connection", user_id="user-1", provider_id="provider-1",
                    name="bulk", api_key=encrypted, api_secret=encrypted,
                )
            )
            session.commit()
            statement = update(ModelConnection).where(
                ModelConnection.id == "bulk-connection"
            ).values(api_secret="plaintext-secret")

        with pytest.raises(IntegrityError, match="ck_model_connection_.*_fernet"):
            session.execute(statement)
            session.commit()
        session.rollback()
    engine.dispose()


def test_model_connection_check_constraints_accept_bulk_encrypted_tokens(tmp_path, monkeypatch):
    monkeypatch.setenv("FERNET_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(credential_encryption, "_fernet_cache", None)
    engine = create_model_center_engine(tmp_path, "connection-check-encrypted.db")
    first_token = credential_encryption.encrypt_key("first-secret")
    second_token = credential_encryption.encrypt_key("second-secret")

    with Session(engine) as session:
        session.execute(
            insert(ModelConnection).values(
                id="bulk-connection", user_id="user-1", provider_id="provider-1",
                name="bulk", api_key=first_token, api_secret=first_token,
            )
        )
        session.execute(
            update(ModelConnection).where(ModelConnection.id == "bulk-connection").values(
                api_key=second_token, api_secret=second_token,
            )
        )
        session.commit()

    with engine.connect() as connection:
        stored = connection.execute(
            text("SELECT api_key, api_secret FROM model_connections WHERE id = 'bulk-connection'")
        ).one()
    assert stored == (second_token, second_token)
    engine.dispose()


def test_model_connection_check_constraint_rejects_case_mismatched_fernet_prefix(tmp_path):
    engine = create_model_center_engine(tmp_path, "connection-check-prefix.db")
    with Session(engine) as session:
        with pytest.raises(IntegrityError, match="ck_model_connection_api_key_fernet"):
            session.execute(
                insert(ModelConnection).values(
                    id="bulk-connection", user_id="user-1", provider_id="provider-1",
                    name="bulk", api_key="gaaaaa" + "x" * 94,
                )
            )
    engine.dispose()
