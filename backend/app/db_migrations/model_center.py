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
_VERSION_TABLES = (
    "model_profile_versions",
    "production_recipe_versions",
    "prompt_profile_versions",
)


def _quote_postgresql_identifier(value: str) -> str:
    return f'"{value.replace(chr(34), chr(34) * 2)}"'


def _postgresql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _sqlite_trigger_statements(tables: tuple[str, ...]):
    statements = []
    for table_name in tables:
        for operation in ("update", "delete"):
            trigger_name = f"trg_{table_name}_published_{operation}"
            statements.append(
                text(
                    f"""CREATE TRIGGER IF NOT EXISTS {trigger_name}
                    BEFORE {operation.upper()} ON {table_name}
                    FOR EACH ROW WHEN OLD.status = 'published'
                    BEGIN
                        SELECT RAISE(ABORT, 'published version is append-only');
                    END"""
                )
            )
    return tuple(statements)


def _postgresql_trigger_statements(schema_name: str, tables: tuple[str, ...]):
    schema = _quote_postgresql_identifier(schema_name)
    function_name = f'{schema}."model_center_reject_published_mutation"'
    statements = [text("SELECT pg_advisory_xact_lock(hashtext('model_center_version_guards'))")]
    statements.append(
        text(
            f"""CREATE OR REPLACE FUNCTION {function_name}()
            RETURNS trigger LANGUAGE plpgsql AS $model_center$
            BEGIN
                IF OLD.status = 'published' THEN
                    RAISE EXCEPTION 'published version is append-only' USING ERRCODE = '55000';
                END IF;
                IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
                RETURN NEW;
            END;
            $model_center$"""
        )
    )
    for table_name in tables:
        trigger_name = f"trg_{table_name}_published_guard"
        quoted_trigger = _quote_postgresql_identifier(trigger_name)
        qualified_table = f"{schema}.{_quote_postgresql_identifier(table_name)}"
        statements.append(
            text(
                f"""DO $model_center$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_trigger AS trigger
                        JOIN pg_class AS target ON target.oid = trigger.tgrelid
                        JOIN pg_namespace AS namespace ON namespace.oid = target.relnamespace
                        WHERE trigger.tgname = {_postgresql_literal(trigger_name)}
                          AND target.relname = {_postgresql_literal(table_name)}
                          AND namespace.nspname = {_postgresql_literal(schema_name)}
                    ) THEN
                        CREATE TRIGGER {quoted_trigger} BEFORE UPDATE OR DELETE ON {qualified_table}
                        FOR EACH ROW EXECUTE FUNCTION {function_name}();
                    END IF;
                END;
                $model_center$"""
            )
        )
    return tuple(statements)


def _version_guard_statements(bind):
    dialect_name = bind.dialect.name
    inspector = inspect(bind)
    if dialect_name == "sqlite":
        tables = tuple(table for table in _VERSION_TABLES if inspector.has_table(table))
        return _sqlite_trigger_statements(tables)
    if dialect_name == "postgresql":
        schema_name = inspector.default_schema_name or "public"
        tables = tuple(
            table for table in _VERSION_TABLES if inspector.has_table(table, schema=schema_name)
        )
        return _postgresql_trigger_statements(schema_name, tables) if tables else ()
    return ()


def _install_version_guards(engine: Engine) -> None:
    statements = _version_guard_statements(engine)
    if not statements:
        return
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(statement)


async def _install_version_guards_async(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        statements = await connection.run_sync(_version_guard_statements)
        for statement in statements:
            await connection.execute(statement)


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
    _install_version_guards(engine)


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
    await _install_version_guards_async(engine)
