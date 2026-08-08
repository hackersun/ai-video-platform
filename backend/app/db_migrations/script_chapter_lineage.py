"""Backfill direct script chapter lineage on SQLite and PostgreSQL."""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql.elements import TextClause


_TABLE = "scripts"
_COLUMN = "chapter_id"
_ADD_COLUMN = text(f"ALTER TABLE {_TABLE} ADD COLUMN {_COLUMN} VARCHAR(36)")
_BACKFILL = {
    "sqlite": text("""
        UPDATE scripts
        SET chapter_id = json_extract(extra_data, '$.chapter_id')
        WHERE (chapter_id IS NULL OR chapter_id = '')
          AND extra_data IS NOT NULL
          AND json_valid(extra_data)
          AND json_extract(extra_data, '$.chapter_id') IS NOT NULL
    """),
    "postgresql": text("""
        UPDATE scripts
        SET chapter_id = extra_data ->> 'chapter_id'
        WHERE (chapter_id IS NULL OR chapter_id = '')
          AND extra_data IS NOT NULL
          AND extra_data ->> 'chapter_id' IS NOT NULL
    """),
}


def backfill_statement(dialect_name: str) -> TextClause:
    """Return the dialect-native JSON backfill statement."""
    try:
        return _BACKFILL[dialect_name]
    except KeyError as error:
        raise ValueError(f"unsupported database dialect: {dialect_name}") from error


def _columns(bind) -> set[str] | None:
    inspector = inspect(bind)
    if not inspector.has_table(_TABLE):
        return None
    return {item["name"] for item in inspector.get_columns(_TABLE)}


def add_script_chapter_lineage(engine: Engine) -> None:
    """Add and backfill the direct chapter column synchronously."""
    with engine.begin() as connection:
        existing = _columns(connection)
        if existing is None:
            return
        if _COLUMN not in existing:
            connection.execute(_ADD_COLUMN)
        connection.execute(backfill_statement(engine.dialect.name))
    print("✅ Script chapter lineage migration completed.")


async def add_script_chapter_lineage_async(engine: AsyncEngine) -> None:
    """Async equivalent using the same dialect contract."""
    async with engine.begin() as connection:
        existing = await connection.run_sync(_columns)
        if existing is None:
            return
        if _COLUMN not in existing:
            await connection.execute(_ADD_COLUMN)
        await connection.execute(backfill_statement(engine.dialect.name))
    print("✅ Script chapter lineage migration completed (async).")


__all__ = ["add_script_chapter_lineage", "add_script_chapter_lineage_async", "backfill_statement"]
