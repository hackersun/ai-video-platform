"""Schema upgrades for persisted live-canary provider operations."""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine


_TABLE = "live_canary_provider_operations"
_COLUMN = "artifact_id"
_COLUMNS = {"artifact_id": "VARCHAR(100)", "cost_source": "VARCHAR(40)", "recovery_reason": "VARCHAR(100)"}
_INDEX = "ix_live_canary_provider_operations_artifact_id"
_ADD_COLUMN = text(f"ALTER TABLE {_TABLE} ADD COLUMN {_COLUMN} VARCHAR(100)")
_ADD_INDEX = text(f"CREATE INDEX IF NOT EXISTS {_INDEX} ON {_TABLE} ({_COLUMN})")


def _has_column(bind, column: str = _COLUMN) -> bool | None:
    inspector = inspect(bind)
    if not inspector.has_table(_TABLE):
        return None
    return column in {item["name"] for item in inspector.get_columns(_TABLE)}


def _has_index(bind) -> bool:
    inspector = inspect(bind)
    if not inspector.has_table(_TABLE):
        return False
    return _INDEX in {item["name"] for item in inspector.get_indexes(_TABLE)}


def _sqlstate(error: DBAPIError) -> str | None:
    return getattr(error.orig, "sqlstate", None) or getattr(error.orig, "pgcode", None)


def _is_duplicate_column(error: DBAPIError, dialect_name: str, column: str = _COLUMN) -> bool:
    if dialect_name == "postgresql":
        return _sqlstate(error) == "42701"
    if dialect_name == "sqlite":
        return f"duplicate column name: {column}" in str(error.orig).lower()
    return False


def _is_duplicate_index(error: DBAPIError, dialect_name: str) -> bool:
    if dialect_name == "postgresql":
        return _sqlstate(error) in {"23505", "42P07"}
    if dialect_name == "sqlite":
        message = str(error.orig).lower()
        return f"index {_INDEX} already exists" in message
    return False


def _execute_sync_ddl(engine: Engine, statement, duplicate_check, state_check) -> None:
    try:
        with engine.begin() as connection:
            connection.execute(statement)
    except DBAPIError as error:
        if not duplicate_check(error, engine.dialect.name) or not state_check(engine):
            raise


def add_artifact_id(engine: Engine) -> None:
    """Backfill operation evidence columns safely on an old schema."""
    for column, sql_type in _COLUMNS.items():
        has_column = _has_column(engine, column)
        if has_column is None:
            return
        if not has_column:
            statement = text(f"ALTER TABLE {_TABLE} ADD COLUMN {column} {sql_type}")
            duplicate = lambda error, dialect, name=column: _is_duplicate_column(error, dialect, name)
            state = lambda bind, name=column: _has_column(bind, name)
            _execute_sync_ddl(engine, statement, duplicate, state)
    _execute_sync_ddl(engine, _ADD_INDEX, _is_duplicate_index, _has_index)


async def _has_column_async(engine: AsyncEngine, column: str = _COLUMN) -> bool | None:
    async with engine.connect() as connection:
        return await connection.run_sync(lambda bind: _has_column(bind, column))


async def _has_index_async(engine: AsyncEngine) -> bool:
    async with engine.connect() as connection:
        return await connection.run_sync(_has_index)


async def _execute_async_ddl(engine, statement, duplicate_check, state_check) -> None:
    try:
        async with engine.begin() as connection:
            await connection.execute(statement)
    except DBAPIError as error:
        if not duplicate_check(error, engine.dialect.name) or not await state_check(engine):
            raise


async def add_artifact_id_async(engine: AsyncEngine) -> None:
    """Async equivalent with the same duplicate-only recovery contract."""
    for column, sql_type in _COLUMNS.items():
        has_column = await _has_column_async(engine, column)
        if has_column is None:
            return
        if not has_column:
            statement = text(f"ALTER TABLE {_TABLE} ADD COLUMN {column} {sql_type}")
            duplicate = lambda error, dialect, name=column: _is_duplicate_column(error, dialect, name)

            async def state(bind, name=column):
                return await _has_column_async(bind, name)

            await _execute_async_ddl(engine, statement, duplicate, state)
    await _execute_async_ddl(engine, _ADD_INDEX, _is_duplicate_index, _has_index_async)
