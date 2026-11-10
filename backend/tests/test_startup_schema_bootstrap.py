"""822cf1ee: startup schema bootstrap respects DB_AUTO_MIGRATE."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_db_auto_migrate_false_skips_create_all(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    async def fake_init_db_async():
        calls.append("init_db_async")

    async def fake_add_terms(engine):
        calls.append("add_user_terms_columns_async")

    monkeypatch.setenv("DB_AUTO_MIGRATE", "false")
    monkeypatch.setattr("init_db.init_db_async", fake_init_db_async, raising=False)

    import main as main_mod

    monkeypatch.setattr(
        "app.db_migrations.user_terms_acceptance.add_user_terms_columns_async",
        fake_add_terms,
        raising=False,
    )
    # Patch the import targets used inside the function
    import types, sys
    fake_init = types.ModuleType("init_db")
    fake_init.init_db_async = fake_init_async = fake_init_db_async  # noqa: F841
    async def _init():
        calls.append("init_db_async")
    fake_init.init_db_async = _init
    monkeypatch.setitem(sys.modules, "init_db", fake_init)

    terms_mod = types.ModuleType("app.db_migrations.user_terms_acceptance")
    async def _terms(engine):
        calls.append("add_user_terms_columns_async")
    terms_mod.add_user_terms_columns_async = _terms
    monkeypatch.setitem(sys.modules, "app.db_migrations.user_terms_acceptance", terms_mod)

    db_mod = types.ModuleType("app.core.database")
    db_mod.engine = object()
    monkeypatch.setitem(sys.modules, "app.core.database", db_mod)

    await main_mod._startup_user_terms_columns()
    assert "init_db_async" not in calls
    assert calls == ["add_user_terms_columns_async"]


@pytest.mark.asyncio
async def test_db_auto_migrate_true_runs_init_db(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    import types, sys

    fake_init = types.ModuleType("init_db")
    async def _init():
        calls.append("init_db_async")
    fake_init.init_db_async = _init
    monkeypatch.setitem(sys.modules, "init_db", fake_init)
    monkeypatch.setenv("DB_AUTO_MIGRATE", "true")

    import main as main_mod
    await main_mod._startup_user_terms_columns()
    assert calls == ["init_db_async"]
