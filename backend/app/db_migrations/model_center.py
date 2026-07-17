"""Additive compatibility links for the versioned model center."""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine


_LINK_COLUMNS = {
    "llm_configs": {"connection_id": "VARCHAR(36)"},
    "external_api_configs": {"connection_id": "VARCHAR(36)"},
    "prompt_skills": {"prompt_profile_version_id": "VARCHAR(36)"},
}


def _has_column(bind, table_name: str, column: str) -> bool | None:
    inspector = inspect(bind)
    if not inspector.has_table(table_name):
        return None
    return column in {item["name"] for item in inspector.get_columns(table_name)}


def _sqlstate(error: DBAPIError) -> str | None:
    return getattr(error.orig, "sqlstate", None) or getattr(error.orig, "pgcode", None)


def _is_duplicate_column(error: DBAPIError, dialect_name: str, column: str) -> bool:
    if dialect_name == "postgresql":
        return _sqlstate(error) == "42701"
    if dialect_name == "sqlite":
        return f"duplicate column name: {column}" in str(error.orig).lower()
    return False


def _execute_sync_ddl(engine: Engine, statement, duplicate_check, state_check) -> None:
    try:
        with engine.begin() as connection:
            connection.execute(statement)
    except DBAPIError as error:
        if not duplicate_check(error, engine.dialect.name) or not state_check(engine):
            raise


def add_model_center_links(engine: Engine) -> None:
    """Add model-center compatibility columns to already-created legacy tables."""
    for table_name, columns in _LINK_COLUMNS.items():
        for column, sql_type in columns.items():
            if _has_column(engine, table_name, column) is not False:
                continue
            statement = text(f"ALTER TABLE {table_name} ADD COLUMN {column} {sql_type}")
            duplicate = lambda error, dialect, name=column: _is_duplicate_column(error, dialect, name)
            state = lambda bind, name=column, table=table_name: _has_column(bind, table, name) is True
            _execute_sync_ddl(engine, statement, duplicate, state)


async def _has_column_async(engine: AsyncEngine, table_name: str, column: str) -> bool | None:
    async with engine.connect() as connection:
        return await connection.run_sync(lambda bind: _has_column(bind, table_name, column))


async def _execute_async_ddl(engine, statement, duplicate_check, state_check) -> None:
    try:
        async with engine.begin() as connection:
            await connection.execute(statement)
    except DBAPIError as error:
        if not duplicate_check(error, engine.dialect.name) or not await state_check(engine):
            raise


async def add_model_center_links_async(engine: AsyncEngine) -> None:
    """Async equivalent with duplicate-only recovery for concurrent initializers."""
    for table_name, columns in _LINK_COLUMNS.items():
        for column, sql_type in columns.items():
            if await _has_column_async(engine, table_name, column) is not False:
                continue
            statement = text(f"ALTER TABLE {table_name} ADD COLUMN {column} {sql_type}")
            duplicate = lambda error, dialect, name=column: _is_duplicate_column(error, dialect, name)

            async def state(bind, name=column, table=table_name):
                return await _has_column_async(bind, table, name) is True

            await _execute_async_ddl(engine, statement, duplicate, state)
