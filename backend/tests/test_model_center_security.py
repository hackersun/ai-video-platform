from __future__ import annotations

import asyncio
import ast
import importlib.util
import json
import os
import sqlite3
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

if "DATABASE_URL" not in os.environ:
    test_database_dir = Path(
        tempfile.mkdtemp(prefix="model-center-security-", dir="/tmp")
    ).resolve()
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{test_database_dir / 'security.db'}"
os.environ.setdefault("E2E_REQUIRE_ISOLATED_DB", "true")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("FERNET_KEY", Fernet.generate_key().decode())

_TEST_DATABASE_PATH = Path(make_url(os.environ["DATABASE_URL"]).database or "").resolve()

from app.core import credential_encryption
from app.core.database import AsyncSessionLocal, _build_database_diagnostic, _derive_sync_database_url
from app.models import llm_config
from app.models.llm_config import LLMConfig
from init_db import init_db


@pytest.fixture(autouse=True)
def reset_fernet_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(credential_encryption, "_fernet_cache", None)


def test_llm_model_module_has_no_fernet_cache_owner() -> None:
    from app.models import llm_config

    assert not hasattr(llm_config, "_fernet_cache")
    assert not hasattr(llm_config, "_get_fernet")
    assert llm_config.encrypt_key is credential_encryption.encrypt_key
    assert llm_config.decrypt_key is credential_encryption.decrypt_key


def _load_audit_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "audit_llm_secret_storage.py"
    spec = importlib.util.spec_from_file_location("audit_llm_secret_storage", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_security_database_is_intrinsically_isolated() -> None:
    configured = os.environ["DATABASE_URL"]
    diagnostic = _build_database_diagnostic(configured, _derive_sync_database_url(configured), True)
    assert diagnostic.isolation_required is True
    assert diagnostic.resolved_sqlite_path == str(_TEST_DATABASE_PATH)


def test_llm_api_secret_is_encrypted_and_round_trips(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FERNET_KEY", Fernet.generate_key().decode())
    config = LLMConfig(id="cfg", user_id="user", model_id="model", name="name")

    config.set_api_secret_encrypted("secret-value")

    assert config.api_secret != "secret-value"
    assert config.get_api_secret_decrypted() == "secret-value"


def test_llm_api_secret_empty_value_is_not_persisted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FERNET_KEY", Fernet.generate_key().decode())
    config = LLMConfig(id="cfg", user_id="user", model_id="model", name="name")

    config.set_api_secret_encrypted(None)

    assert config.api_secret is None
    assert config.get_api_secret_decrypted() == ""


def test_production_requires_a_present_and_valid_fernet_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEV_MODE", "false")
    monkeypatch.setattr(credential_encryption, "_configured_encryption_key", lambda: None)

    with pytest.raises(RuntimeError, match="FERNET_KEY"):
        llm_config.require_stable_encryption_key()

    monkeypatch.setattr(credential_encryption, "_configured_encryption_key", lambda: b"not-a-valid-fernet-key")
    with pytest.raises(RuntimeError, match="FERNET_KEY"):
        llm_config.require_stable_encryption_key()


def test_production_startup_rejects_malformed_fernet_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEV_MODE", "false")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-that-is-definitely-long-enough")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:////tmp/model-center-security.db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("OBJECT_STORAGE_PROVIDER", "qiniu")
    monkeypatch.setenv("AUTH_EMAIL_PROVIDER", "smtp")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_USERNAME", "mailer")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("AUTH_EMAIL_FROM", "no-reply@example.test")
    monkeypatch.setenv("PUBLIC_APP_URL", "https://app.example.test")
    monkeypatch.setenv("FERNET_KEY", "not-a-valid-fernet-key")

    from main import app

    with pytest.raises(RuntimeError, match="FERNET_KEY"):
        with TestClient(app):
            pass


def test_fernet_cache_rebinds_when_configured_key_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    first_key = Fernet.generate_key()
    second_key = Fernet.generate_key()
    monkeypatch.setenv("FERNET_KEY", first_key.decode())
    llm_config.encrypt_key("first-value")

    monkeypatch.setenv("FERNET_KEY", second_key.decode())
    encrypted = llm_config.encrypt_key("second-value")

    assert Fernet(second_key).decrypt(encrypted.encode()).decode() == "second-value"


@pytest.mark.parametrize(
    ("field", "invalid_value", "secret_marker"),
    [
        ("api_key", {"nested": {"token": "api-key-marker"}}, "api-key-marker"),
        ("api_secret", ["api-secret-marker", {"nested": True}], "api-secret-marker"),
    ],
)
def test_validation_errors_redact_invalid_credentials(
    field: str,
    invalid_value: object,
    secret_marker: str,
) -> None:
    from main import app

    body = {"model_id": "model", "name": "name", "api_key": "valid-key"}
    body[field] = invalid_value
    with TestClient(app) as client:
        response = client.post("/api/v1/llm/configs", json=body)

    assert response.status_code == 422
    payload = response.json()
    assert secret_marker not in json.dumps(payload, ensure_ascii=False)
    error = next(item for item in payload["detail"] if item["loc"][-1] == field)
    assert error["input"] == "<redacted>"


def test_validation_errors_preserve_non_secret_input_structure() -> None:
    from main import app

    invalid_temperature = {"nested": "visible-marker"}
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/llm/configs",
            json={
                "model_id": "model",
                "name": "name",
                "api_key": "valid-key",
                "temperature": invalid_temperature,
            },
        )

    assert response.status_code == 422
    error = next(item for item in response.json()["detail"] if item["loc"][-1] == "temperature")
    assert error["input"] == invalid_temperature


def test_whole_body_validation_redacts_nested_credentials_by_key() -> None:
    from main import app

    invalid_body = [
        {"api_key": {"nested": ["whole-key-marker"]}},
        {"api_secret": [{"nested": "whole-secret-marker"}]},
        {"safe": {"nested": ["visible-marker"]}},
    ]
    with TestClient(app) as client:
        response = client.post("/api/v1/llm/configs", json=invalid_body)

    assert response.status_code == 422
    payload = response.json()
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "whole-key-marker" not in serialized
    assert "whole-secret-marker" not in serialized
    assert payload["detail"][0]["input"] == [
        {"api_key": "<redacted>"},
        {"api_secret": "<redacted>"},
        {"safe": {"nested": ["visible-marker"]}},
    ]


def test_validation_redaction_recurses_through_ctx_without_sensitive_loc() -> None:
    from app.core.validation_errors import redact_credential_validation_errors

    errors = [
        {
            "type": "value_error",
            "loc": ("body",),
            "msg": "invalid body",
            "input": {"safe": ["visible-input"]},
            "ctx": {
                "nested": [
                    {"api_key": ["ctx-key-marker"]},
                    {"api_secret": {"deep": "ctx-secret-marker"}},
                    {"safe": "visible-ctx"},
                ]
            },
        }
    ]

    sanitized = redact_credential_validation_errors(errors)

    serialized = json.dumps(sanitized, ensure_ascii=False)
    assert "ctx-key-marker" not in serialized
    assert "ctx-secret-marker" not in serialized
    assert sanitized[0]["input"] == {"safe": ["visible-input"]}
    assert sanitized[0]["ctx"] == {
        "nested": [
            {"api_key": "<redacted>"},
            {"api_secret": "<redacted>"},
            {"safe": "visible-ctx"},
        ]
    }


def test_config_routes_encrypt_and_do_not_return_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FERNET_KEY", Fernet.generate_key().decode())
    init_db()
    user_id = f"credential-user-{uuid4()}"
    headers = {"Authorization": f"Bearer {user_id}"}

    async def _seed_models() -> None:
        from app.api.v1.endpoints.llm_config import ensure_default_models, ensure_default_providers

        async with AsyncSessionLocal() as db:
            await ensure_default_providers(db)
            await ensure_default_models(db)
            await db.commit()

    asyncio.run(_seed_models())
    from main import app

    async def _read_credentials(config_id: str) -> tuple[str | None, str | None, str, str]:
        async with AsyncSessionLocal() as db:
            config = await db.get(LLMConfig, config_id)
            assert config is not None
            return (
                config.api_key,
                config.api_secret,
                config.get_api_key_decrypted(),
                config.get_api_secret_decrypted(),
            )

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/llm/configs",
            json={
                "model_id": "minimax-m2.7",
                "name": "credential config",
                "api_key": "key-create",
                "api_secret": "secret-create",
            },
            headers=headers,
        )
        assert created.status_code == 201
        assert "key-create" not in str(created.json())
        assert "secret-create" not in str(created.json())

        upserted = client.post(
            "/api/v1/llm/configs",
            json={
                "model_id": "minimax-m2.7",
                "name": "credential config upserted",
                "api_key": "key-upsert",
                "api_secret": "secret-upsert",
            },
            headers=headers,
        )
        assert upserted.status_code == 201
        assert upserted.json()["id"] == created.json()["id"]
        _, stored_secret, _, plain_secret = asyncio.run(_read_credentials(created.json()["id"]))
        assert stored_secret != "secret-upsert"
        assert plain_secret == "secret-upsert"

        updated = client.put(
            f"/api/v1/llm/configs/{created.json()['id']}",
            json={
                "model_id": "minimax-m2.7",
                "name": "credential config updated",
                "api_secret": "secret-replaced",
            },
            headers=headers,
        )
        assert updated.status_code == 200

        preserved = client.put(
            f"/api/v1/llm/configs/{created.json()['id']}",
            json={
                "model_id": "minimax-m2.7",
                "name": "credential config preserved",
                "api_secret": "",
            },
            headers=headers,
        )
        assert preserved.status_code == 200

    stored_key, stored_secret, plain_key, plain_secret = asyncio.run(_read_credentials(created.json()["id"]))
    assert stored_key != "key-upsert"
    assert stored_secret != "secret-replaced"
    assert plain_key == "key-upsert"
    assert plain_secret == "secret-replaced"


def test_audit_classifies_without_exposing_secret_values(tmp_path: Path) -> None:
    module = _load_audit_module()

    encrypted = Fernet.generate_key()
    token = Fernet(encrypted).encrypt(b"secret-value").decode()
    assert module.classify_secret(None) == "empty"
    assert module.classify_secret("") == "empty"
    assert module.classify_secret(token) == "encrypted"
    assert module.classify_secret("legacy-plaintext") == "legacy_plaintext"

    database_path = tmp_path / "audit.db"
    connection = sqlite3.connect(database_path)
    connection.execute("CREATE TABLE llm_configs (api_key TEXT, api_secret TEXT)")
    connection.execute("INSERT INTO llm_configs VALUES (?, ?)", (token, "legacy-secret"))
    connection.commit()
    connection.close()

    rows = module.load_secret_columns_read_only(f"sqlite:///{database_path}")
    assert rows == [token, "legacy-secret"]
    with pytest.raises(SystemExit):
        module.parse_args(["--apply"])


def test_postgres_audit_retains_credentials_and_sets_read_only_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_audit_module()
    configured_url = "postgresql+asyncpg://audit_user:p%40ss%2Fword@db.invalid/audit"
    calls: list[str] = []
    state: dict[str, object] = {}

    class FakeResult:
        def all(self):
            return [("gAAAAAtest", None)]

    class FakeTransaction:
        def rollback(self) -> None:
            state["rolled_back"] = True

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def begin(self):
            return FakeTransaction()

        def execute(self, statement):
            calls.append(str(statement))
            return FakeResult()

    class FakeEngine:
        def connect(self):
            return FakeConnection()

        def dispose(self) -> None:
            state["disposed"] = True

    def fake_create_engine(database_url: str):
        state["database_url"] = database_url
        return FakeEngine()

    monkeypatch.setattr(module, "create_engine", fake_create_engine)

    assert module.load_secret_columns_read_only(configured_url) == ["gAAAAAtest", None]
    sync_url = make_url(state["database_url"])
    assert sync_url.drivername == "postgresql+psycopg2"
    assert sync_url.password == "p@ss/word"
    assert calls == ["SET TRANSACTION READ ONLY", "SELECT api_key, api_secret FROM llm_configs"]
    assert state["rolled_back"] is True
    assert state["disposed"] is True


def test_security_hotspots_respect_ratchet_limits() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    model_source = (backend_root / "app/models/llm_config.py").read_text(encoding="utf-8")
    endpoint_source = (backend_root / "app/api/v1/endpoints/llm_config.py").read_text(encoding="utf-8")
    assert len(model_source.splitlines()) <= 255
    assert len(endpoint_source.splitlines()) < 2396

    route_sizes = {
        node.name: node.end_lineno - node.lineno + 1
        for node in ast.walk(ast.parse(endpoint_source))
        if isinstance(node, ast.AsyncFunctionDef) and node.name in {"create_config", "update_config"}
    }
    assert set(route_sizes) == {"create_config", "update_config"}
    assert all(size <= 60 for size in route_sizes.values())
