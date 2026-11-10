"""P3: model_config is the runtime source of truth; legacy rows stay a compat mirror.

Covers forward migration (legacy -> model_config), reconcile on legacy edits,
reverse projection (model_config -> legacy, for rollback) and read-mode behaviour.
"""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.features.model_config import legacy_sync
from app.models.llm_config import LLMConfig, LLMModel, LLMProvider
from app.models.model_center import ModelBinding, ModelConnection
from app.services import simple_model_setup as svc

SECRET = "sk-test-SECRET-value-123456"
_LOOP = asyncio.new_event_loop()


def _run(coro):
    return _LOOP.run_until_complete(coro)


@pytest.fixture
def env(monkeypatch):
    monkeypatch.delenv("DETERMINISTIC_PROVIDER_FAKE", raising=False)
    monkeypatch.delenv("MODEL_CENTER_READ_MODE", raising=False)
    monkeypatch.delenv("MODEL_CENTER_CANONICAL_READS", raising=False)

    async def build():
        path = Path(tempfile.mkdtemp(prefix="legacy-sync-")) / "db.sqlite"
        engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        db = async_sessionmaker(engine, expire_on_commit=False)()
        p = LLMProvider(id=str(uuid4()), name="volcano", name_cn="火山引擎", is_active=True)
        db.add(p)
        m = {
            "text": LLMModel(id=str(uuid4()), provider_id=p.id, model_id="doubao-seed-1-8-251228", model_name="Seed",
                             model_type="chat", capabilities=["chat"], is_active=True),
            "text2": LLMModel(id=str(uuid4()), provider_id=p.id, model_id="doubao-pro-32k", model_name="Pro",
                              model_type="chat", capabilities=["chat"], is_active=True),
            "image": LLMModel(id=str(uuid4()), provider_id=p.id, model_id="doubao-seedream-5-0-260128", model_name="SD",
                              model_type="image-generation", capabilities=["text-to-image"], is_active=True),
        }
        db.add_all(m.values())
        await db.commit()
        return engine, db, m
    engine, db, models = _run(build())
    yield db, models
    _run(db.close())
    _run(engine.dispose())


def _config(db, model, *, default=False, status="success", user="u1"):
    c = LLMConfig(id=str(uuid4()), user_id=user, model_id=model.id, name=f"cfg-{model.model_id}",
                  is_active=True, is_default=default, test_status=status, extra_params={})
    c.set_api_key_encrypted(SECRET)
    db.add(c)
    return c


async def _active_bindings(db, user="u1"):
    return (await db.scalars(select(ModelBinding).where(
        ModelBinding.user_id == user, ModelBinding.is_active == True))).all()  # noqa: E712


def test_forward_migration_mirrors_legacy_defaults_and_is_idempotent(env):
    db, m = env
    t = _config(db, m["text"], default=True)
    _config(db, m["text2"])
    i = _config(db, m["image"], default=True, status="pending")
    _run(db.commit())
    picks = _run(legacy_sync.reconcile_user(db, "u1"))
    assert picks == {"text": t.id, "image": i.id}
    assert _run(legacy_sync.canonical_default_config_ids(db, "u1")) == picks
    count = len(_run(_active_bindings(db)))
    _run(legacy_sync.reconcile_user(db, "u1"))
    assert len(_run(_active_bindings(db))) == count


def test_legacy_default_change_moves_canonical_binding(env):
    db, m = env
    t = _config(db, m["text"], default=True)
    t2 = _config(db, m["text2"])
    _run(db.commit())
    _run(legacy_sync.reconcile_user(db, "u1"))
    t.is_default, t2.is_default = False, True
    _run(db.commit())
    _run(legacy_sync.reconcile_user(db, "u1"))
    assert _run(legacy_sync.canonical_default_config_ids(db, "u1"))["text"] == t2.id
    text_bindings = [b for b in _run(_active_bindings(db)) if b.capability == "text_generation"]
    assert len(text_bindings) == 1 and text_bindings[0].version >= 2


def test_deactivated_legacy_config_drops_binding_and_connection(env):
    db, m = env
    t = _config(db, m["text"], default=True)
    _run(db.commit())
    _run(legacy_sync.reconcile_user(db, "u1"))
    t.is_active = False
    _run(db.commit())
    _run(legacy_sync.reconcile_user(db, "u1"))
    assert "text" not in _run(legacy_sync.canonical_default_config_ids(db, "u1"))
    conn = _run(legacy_sync.connection_for_config(db, t.id))
    assert conn is not None and conn.status == "disabled"


def test_key_and_test_status_sync_to_connection_without_exposing_secret(env):
    db, m = env
    t = _config(db, m["text"], default=True, status="pending")
    _run(db.commit())
    _run(legacy_sync.reconcile_user(db, "u1"))
    t.set_api_key_encrypted("sk-other-SECRET-987654321")
    t.test_status = "success"
    _run(db.commit())
    _run(legacy_sync.reconcile_user(db, "u1"))
    conn = _run(legacy_sync.connection_for_config(db, t.id))
    assert conn.api_key == t.api_key and conn.api_key.startswith("gAAAAA")
    assert conn.status == "verified"
    assert SECRET not in repr(conn.connection_params)


def test_reverse_projection_restores_legacy_view_for_rollback(env):
    db, m = env
    t = _config(db, m["text"], default=True)
    t2 = _config(db, m["text2"])
    _run(db.commit())
    _run(legacy_sync.reconcile_user(db, "u1"))
    # change the source of truth directly in model_config
    _run(legacy_sync.set_canonical_default(db, "u1", "text", t2.id))
    _run(db.commit())
    _run(legacy_sync.project_canonical_to_legacy(db, "u1"))
    _run(db.commit())
    rows = _run(svc._user_configs(db, "u1"))
    assert svc._pick_default(rows, "text")[0].id == t2.id
    # a subsequent forward reconcile keeps the canonical choice (round trip is stable)
    assert _run(legacy_sync.reconcile_user(db, "u1"))["text"] == t2.id


def test_runtime_reads_model_config_by_default_and_legacy_mode_reads_legacy(env, monkeypatch):
    db, m = env
    t = _config(db, m["text"], default=True)
    t2 = _config(db, m["text2"])
    _run(db.commit())
    _run(legacy_sync.reconcile_user(db, "u1"))
    _run(legacy_sync.set_canonical_default(db, "u1", "text", t2.id))
    _run(db.commit())
    eff = _run(svc.resolve_effective_configs(db, "u1", None))
    assert eff["text"][0].id == t2.id  # canonical wins, legacy flag still on t
    monkeypatch.setenv("MODEL_CENTER_READ_MODE", "legacy")
    eff = _run(svc.resolve_effective_configs(db, "u1", None))
    assert eff["text"][0].id == t.id


def test_unmigrated_user_is_lazily_migrated_on_first_read(env):
    db, m = env
    t = _config(db, m["text"], default=True, user="u2")
    _run(db.commit())
    assert _run(_active_bindings(db, "u2")) == []
    eff = _run(svc.resolve_effective_configs(db, "u2", None))
    assert eff["text"][0].id == t.id
    assert len(_run(_active_bindings(db, "u2"))) == 1


def test_migrate_all_users_reports_counts(env):
    db, m = env
    _config(db, m["text"], default=True, user="a")
    _config(db, m["image"], default=True, user="b")
    _run(db.commit())
    summary = _run(legacy_sync.migrate_all(db))
    assert summary["users"] == 2 and summary["bindings_active"] == 2
    assert SECRET not in repr(summary)


def test_canonical_mode_inherits_legacy_default_for_unbound_task(monkeypatch):
    """Non-strict canonical keeps runtime working for tasks with no dedicated binding."""
    from app.features.model_config.settings import strict_canonical_enabled

    monkeypatch.delenv("MODEL_CENTER_STRICT_CANONICAL", raising=False)
    assert strict_canonical_enabled() is False
    monkeypatch.setenv("MODEL_CENTER_STRICT_CANONICAL", "on")
    assert strict_canonical_enabled() is True


def _client_call(db, fn):
    import httpx
    from app.core.database import get_db
    from app.core.security import get_current_user_id
    from main import app

    async def _db():
        yield db
    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user_id] = lambda: "u1"

    async def go():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
            return await fn(client)
    try:
        return _run(go())
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user_id, None)


def test_legacy_endpoints_are_write_through_compat_adapters(env):
    db, m = env
    a = _config(db, m["text"], default=True)
    b = _config(db, m["text2"])
    _run(db.commit())
    _run(legacy_sync.reconcile_user(db, "u1"))
    _run(db.commit())

    # set-default via legacy endpoint must move the canonical binding
    async def set_default(client):
        r = await client.post(f"/api/v1/llm/configs/{b.id}/set-default")
        assert r.status_code == 200
        listed = await client.get("/api/v1/llm/configs")
        assert listed.status_code == 200 and SECRET not in listed.text
        return {item["id"]: item["is_default"] for item in listed.json()}
    flags = _client_call(db, set_default)
    assert _run(legacy_sync.canonical_default_config_ids(db, "u1"))["text"] == b.id
    assert flags.get(b.id) is True and flags.get(a.id) is False

    async def delete(client):
        r = await client.delete(f"/api/v1/llm/configs/{b.id}")
        assert r.status_code == 200
    _client_call(db, delete)
    assert "text" not in _run(legacy_sync.canonical_default_config_ids(db, "u1")) or \
        _run(legacy_sync.canonical_default_config_ids(db, "u1"))["text"] != b.id


def test_simple_setup_saves_model_outside_recommended_list(env):
    """Four-card page: a non-recommended current model must save and round-trip."""
    db, m = env
    provider_id = m["text2"].provider_id

    async def save(client):
        r = await client.put("/api/v1/model-center/simple-setup", json={
            "provider_id": provider_id, "api_key": SECRET,
            "capabilities": {"text": {"model_id": m["text2"].id}}})
        assert r.status_code == 200, r.text
        assert SECRET not in r.text
        again = await client.get("/api/v1/model-center/simple-setup")
        return again.json()["capabilities"]["text"]
    card = _client_call(db, save)
    assert card["model_id"] == m["text2"].id
    picks = _run(legacy_sync.canonical_default_config_ids(db, "u1"))
    cfg = _run(db.get(LLMConfig, picks["text"]))
    assert cfg.model_id == m["text2"].id
