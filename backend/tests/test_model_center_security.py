from __future__ import annotations

import asyncio
import importlib.util
import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.models import llm_config
from app.models.llm_config import LLMConfig
from app.core.database import AsyncSessionLocal
from init_db import init_db


@pytest.fixture(autouse=True)
def reset_fernet_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_config, "_fernet_cache", None)


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
    monkeypatch.setenv("DEV_MODE", "false")
    monkeypatch.delenv("FERNET_KEY", raising=False)

    with pytest.raises(RuntimeError, match="FERNET_KEY"):
        llm_config.require_stable_encryption_key()

    monkeypatch.setenv("FERNET_KEY", "not-a-valid-fernet-key")
    with pytest.raises(RuntimeError, match="FERNET_KEY"):
        llm_config.require_stable_encryption_key()


def test_production_startup_rejects_malformed_fernet_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEV_MODE", "false")
    monkeypatch.setenv("FERNET_KEY", "not-a-valid-fernet-key")

    from main import app

    with pytest.raises(RuntimeError, match="FERNET_KEY"):
        with TestClient(app):
            pass


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

    stored_key, stored_secret, plain_key, plain_secret = asyncio.run(_read_credentials(created.json()["id"]))
    assert stored_key != "key-upsert"
    assert stored_secret != "secret-replaced"
    assert plain_key == "key-upsert"
    assert plain_secret == "secret-replaced"


def test_audit_classifies_without_exposing_secret_values(tmp_path: Path) -> None:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "audit_llm_secret_storage.py"
    spec = importlib.util.spec_from_file_location("audit_llm_secret_storage", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

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
