import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.db_migrations.user_terms_acceptance import add_user_terms_columns, add_user_terms_columns_async


def test_sync_adds_columns_to_legacy_users(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'l.db'}")
    with engine.begin() as c:
        c.execute(text("CREATE TABLE users (id VARCHAR(36) PRIMARY KEY, username VARCHAR(50))"))
    add_user_terms_columns(engine)
    add_user_terms_columns(engine)  # idempotent
    cols = {c["name"] for c in inspect(engine).get_columns("users")}
    assert {"terms_accepted_version", "terms_accepted_at"} <= cols


@pytest.mark.asyncio
async def test_async_adds_columns(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path/'a.db'}")
    async with engine.begin() as c:
        await c.execute(text("CREATE TABLE users (id VARCHAR(36) PRIMARY KEY)"))
    await add_user_terms_columns_async(engine)
    await add_user_terms_columns_async(engine)
    async with engine.connect() as c:
        cols = await c.run_sync(lambda s: {x["name"] for x in inspect(s).get_columns("users")})
    assert "terms_accepted_at" in cols
    await engine.dispose()
