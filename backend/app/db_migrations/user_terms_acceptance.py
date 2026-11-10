"""Add terms acceptance columns to users (idempotent, create_all companion)."""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine

_COLUMNS = {"terms_accepted_version": "VARCHAR(40)", "terms_accepted_at": "TIMESTAMP"}


def _missing(bind) -> list[str]:
    inspector = inspect(bind)
    if not inspector.has_table("users"):
        return []
    existing = {item["name"] for item in inspector.get_columns("users")}
    return [name for name in _COLUMNS if name not in existing]


def add_user_terms_columns(engine: Engine) -> None:
    with engine.begin() as connection:
        for name in _missing(connection):
            connection.execute(text(f"ALTER TABLE users ADD COLUMN {name} {_COLUMNS[name]}"))


async def add_user_terms_columns_async(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        missing = await connection.run_sync(_missing)
        for name in missing:
            await connection.execute(text(f"ALTER TABLE users ADD COLUMN {name} {_COLUMNS[name]}"))
