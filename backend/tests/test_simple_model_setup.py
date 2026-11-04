"""Simple model setup: one key, four capability cards, defaults, per-novel overrides."""
from __future__ import annotations

import asyncio
import tempfile
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.core.time_utils import utc_now
from app.models.llm_config import LLMConfig, LLMModel, LLMProvider
from app.models.novel import Novel
from app.services import simple_model_setup as svc

SECRET = "sk-test-SECRET-value-123456"


_LOOP = asyncio.new_event_loop()


def _run(coro):
    return _LOOP.run_until_complete(coro)


async def _session():
    path = Path(tempfile.mkdtemp(prefix="simple-setup-")) / "db.sqlite"
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _seed(db):
    p = LLMProvider(id=str(uuid4()), name="volcano", name_cn="火山引擎", is_active=True)
    p2 = LLMProvider(id=str(uuid4()), name="minimax", name_cn="MiniMax", is_active=True)
    db.add_all([p, p2])
    models = {
        "text": LLMModel(id=str(uuid4()), provider_id=p.id, model_id="doubao-seed-1-8-251228", model_name="Seed 1.8",
                         model_type="chat", capabilities=["chat", "completion"], is_active=True),
        "image": LLMModel(id=str(uuid4()), provider_id=p.id, model_id="doubao-seedream-5-0-260128", model_name="Seedream 5",
                          model_type="image-generation", capabilities=["text-to-image"], is_active=True),
        "video": LLMModel(id=str(uuid4()), provider_id=p.id, model_id="doubao-seedance-2-0-260128", model_name="Seedance 2",
                          model_type="video-generation", capabilities=["text-to-video"], is_active=True),
        "tts": LLMModel(id=str(uuid4()), provider_id=p2.id, model_id="speech-2.6-hd", model_name="Speech HD",
                        model_type="tts", capabilities=["text-to-speech"], is_active=True),
    }
    db.add_all(models.values())
    await db.commit()
    return p, p2, models


@pytest.fixture
def env(monkeypatch):
    monkeypatch.delenv("DETERMINISTIC_PROVIDER_FAKE", raising=False)

    async def build():
        engine, Session = await _session()
        db = Session()
        p, p2, models = await _seed(db)
        return engine, db, p, p2, models
    engine, db, p, p2, models = _run(build())
    yield db, p, p2, models
    _run(db.close())
    _run(engine.dispose())


def test_empty_state_lists_four_cards_and_presets(env):
    db, p, _, _ = env
    state = _run(svc.get_simple_setup(db, "u1"))
    assert set(state["capabilities"]) == {"text", "image", "video", "tts"}
    assert all(card["config_id"] is None and card["has_key"] is False for card in state["capabilities"].values())
    assert state["configured"] is False
    volcano = next(x for x in state["providers"] if x["id"] == p.id)
    assert volcano["presets"]["video"]
    assert any(o["provider_id"] == p.id for o in state["capabilities"]["image"]["options"])


def test_save_one_key_creates_default_configs_and_never_returns_secret(env):
    db, p, p2, models = env
    state = _run(svc.save_simple_setup(db, "u1", {
        "provider_id": p.id, "api_key": SECRET,
        "capabilities": {
            "text": {"model_id": models["text"].id},
            "image": {"model_id": models["image"].id},
            "video": {"model_id": models["video"].id},
            "tts": {"model_id": models["tts"].id, "api_key": "other-provider-key", "extra_params": {"group_id": "g1"}},
        },
    }))
    assert SECRET not in repr(state)
    assert "other-provider-key" not in repr(state)
    assert all(card["has_key"] for card in state["capabilities"].values())
    rows = (await_all(db, select(LLMConfig).where(LLMConfig.user_id == "u1")))
    assert len(rows) == 4 and all(r.is_default for r in rows)
    text = next(r for r in rows if r.model_id == models["text"].id)
    assert text.get_api_key_decrypted() == SECRET
    tts = next(r for r in rows if r.model_id == models["tts"].id)
    assert tts.get_api_key_decrypted() == "other-provider-key"
    assert tts.extra_params == {"group_id": "g1", "simple_setup_capability": "tts"}


def await_all(db, stmt):
    return _run(db.scalars(stmt)).all()


def test_save_without_key_reuses_existing_provider_key(env):
    db, p, _, models = env
    _run(svc.save_simple_setup(db, "u1", {"provider_id": p.id, "api_key": SECRET,
                                          "capabilities": {"text": {"model_id": models["text"].id}}}))
    _run(svc.save_simple_setup(db, "u1", {"provider_id": p.id,
                                          "capabilities": {"image": {"model_id": models["image"].id}}}))
    row = _run(db.scalars(select(LLMConfig).where(LLMConfig.model_id == models["image"].id))).one()
    assert row.get_api_key_decrypted() == SECRET


def test_save_rejects_wrong_capability_and_missing_key(env):
    db, p, _, models = env
    with pytest.raises(svc.SimpleSetupError):
        _run(svc.save_simple_setup(db, "u1", {"provider_id": p.id, "api_key": SECRET,
                                              "capabilities": {"video": {"model_id": models["text"].id}}}))
    with pytest.raises(svc.SimpleSetupError):
        _run(svc.save_simple_setup(db, "u1", {"provider_id": p.id,
                                              "capabilities": {"text": {"model_id": models["text"].id}}}))


def test_test_all_updates_status_without_leaking(env, monkeypatch):
    db, p, _, models = env
    _run(svc.save_simple_setup(db, "u1", {"provider_id": p.id, "api_key": SECRET,
                                          "capabilities": {"text": {"model_id": models["text"].id}}}))
    seen = []

    async def fake_exec(provider_id, api_key, model_id, message, **kw):
        seen.append(api_key)
        return {"success": True, "message": "ok", "response": "hi", "response_time_ms": 5, "tokens_used": 1}
    monkeypatch.setattr("app.api.v1.endpoints.llm_config._execute_config_test", fake_exec)
    result = _run(svc.test_simple_setup(db, "u1", ["text", "image"]))
    assert seen == [SECRET]
    assert result["results"]["text"]["success"] is True
    assert result["results"]["image"]["success"] is False and result["results"]["image"]["code"] == "not_configured"
    assert SECRET not in repr(result)
    assert result["state"]["capabilities"]["text"]["test_status"] == "success"


def test_novel_override_wins_over_global_default(env):
    db, p, _, models = env
    _run(svc.save_simple_setup(db, "u1", {"provider_id": p.id, "api_key": SECRET,
                                          "capabilities": {"text": {"model_id": models["text"].id}}}))
    other = LLMModel(id=str(uuid4()), provider_id=p.id, model_id="doubao-pro-32k", model_name="Pro 32k",
                     model_type="chat", capabilities=["chat"], is_active=True)
    db.add(other)
    novel = Novel(id=str(uuid4()), user_id="u1", title="n", extra_data={})
    db.add(novel)
    _run(db.commit())
    alt = LLMConfig(id=str(uuid4()), user_id="u1", model_id=other.id, name="alt", is_active=True)
    alt.set_api_key_encrypted(SECRET)
    db.add(alt)
    _run(db.commit())
    _run(svc.set_novel_overrides(db, "u1", novel.id, {"text": alt.id}))
    resolved = _run(svc.resolve_effective_configs(db, "u1", novel.id))
    assert resolved["text"][0].id == alt.id
    assert _run(svc.resolve_effective_configs(db, "u1", None))["text"][0].id != alt.id
    state = _run(svc.get_simple_setup(db, "u1", novel_id=novel.id))
    assert state["novel_overrides"]["text"] == alt.id
    choice_ids = {c["config_id"] for c in state["novel_choices"]["text"]}
    assert alt.id in choice_ids and len(choice_ids) == 2
    assert all(SECRET not in str(c) and "api_key" not in c for c in state["novel_choices"]["text"])
    assert _run(svc.novel_override_config_id(db, "u1", novel.id, "text")) == alt.id
    assert _run(svc.novel_override_config_id(db, "u1", novel.id, "video")) is None
    assert _run(svc.novel_override_config_id(db, "u2", novel.id, "text")) is None
    assert _run(svc.novel_override_config_id(db, "u1", None, "text")) is None
    _run(svc.set_novel_overrides(db, "u1", novel.id, {"text": None}))
    assert _run(svc.novel_override_config_id(db, "u1", novel.id, "text")) is None
    assert _run(svc.resolve_effective_configs(db, "u1", novel.id))["text"][0].id != alt.id
    with pytest.raises(svc.SimpleSetupError):
        _run(svc.set_novel_overrides(db, "u2", novel.id, {"text": alt.id}))


def test_ensure_fresh_retests_only_stale(env, monkeypatch):
    db, p, _, models = env
    _run(svc.save_simple_setup(db, "u1", {"provider_id": p.id, "api_key": SECRET,
                                          "capabilities": {"text": {"model_id": models["text"].id},
                                                           "image": {"model_id": models["image"].id}}}))
    rows = _run(db.scalars(select(LLMConfig))).all()
    fresh = next(r for r in rows if r.model_id == models["text"].id)
    fresh.test_status, fresh.tested_at = "success", utc_now()
    stale = next(r for r in rows if r.model_id == models["image"].id)
    stale.test_status, stale.tested_at = "success", utc_now() - timedelta(hours=2)
    _run(db.commit())
    calls = []

    async def fake_exec(provider_id, api_key, model_id, message, **kw):
        calls.append(model_id)
        return {"success": True, "message": "ok", "response": "", "response_time_ms": 1, "tokens_used": 0}
    monkeypatch.setattr("app.api.v1.endpoints.llm_config._execute_config_test", fake_exec)
    resolved = _run(svc.resolve_effective_configs(db, "u1", None))
    failures = _run(svc.ensure_fresh(db, {k: resolved[k] for k in ("text", "image")}, not_before=utc_now() - timedelta(minutes=5)))
    assert failures == {} and calls == [models["image"].model_id]


def test_http_routes_round_trip_without_secret(env, monkeypatch):
    import httpx
    from app.core.database import get_db
    from app.core.security import get_current_user_id
    from main import app

    db, p, _, models = env

    async def _db():
        yield db
    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user_id] = lambda: "u1"

    async def go():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
            empty = await client.get("/api/v1/model-center/simple-setup")
            assert empty.status_code == 200 and empty.json()["configured"] is False
            bad = await client.put("/api/v1/model-center/simple-setup", json={
                "provider_id": p.id, "capabilities": {"text": {"model_id": models["text"].id}}})
            assert bad.status_code == 422 and bad.json()["detail"]["code"] == "api_key_required"
            saved = await client.put("/api/v1/model-center/simple-setup", json={
                "provider_id": p.id, "api_key": SECRET,
                "capabilities": {"text": {"model_id": models["text"].id}}})
            assert saved.status_code == 200 and SECRET not in saved.text
            assert saved.json()["capabilities"]["text"]["has_key"] is True
            missing = await client.put("/api/v1/model-center/simple-setup/novels/nope", json={"overrides": {}})
            assert missing.status_code == 404
    try:
        _run(go())
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user_id, None)


def test_save_projects_into_model_center(env):
    from app.models.model_center import ModelConnection

    db, p, _, models = env
    _run(svc.save_simple_setup(db, "u1", {"provider_id": p.id, "api_key": SECRET,
                                          "capabilities": {"text": {"model_id": models["text"].id}}}))
    assert _run(svc.sync_model_center(db, "u1")) is True
    connections = _run(db.scalars(select(ModelConnection))).all()
    assert connections, "legacy config must be projected into model_config connections"


def test_save_accepts_model_outside_recommended_presets(env):
    db, p, _, _ = env
    custom = LLMModel(id=str(uuid4()), provider_id=p.id, model_id="custom-chat-not-in-presets", model_name="Custom",
                      model_type="chat", capabilities=["chat"], is_active=True)
    db.add(custom)
    _run(db.commit())
    assert "custom-chat-not-in-presets" not in repr(svc.PROVIDER_PRESETS)
    state = _run(svc.save_simple_setup(db, "u1", {"provider_id": p.id, "api_key": SECRET,
                                                  "capabilities": {"text": {"model_id": custom.id}}}))
    assert state["capabilities"]["text"]["has_key"] is True
    row = _run(db.scalars(select(LLMConfig).where(LLMConfig.user_id == "u1"))).one()
    assert row.model_id == custom.id and row.is_default
    assert SECRET not in repr(state)
