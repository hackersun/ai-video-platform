"""
数据库配置
"""

import importlib.util
import os
from pathlib import Path
from typing import NamedTuple

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, sessionmaker


DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./ai_video.db"


class DatabaseDiagnostic(NamedTuple):
    async_url: str
    sync_url: str
    isolation_required: bool
    resolved_sqlite_path: str | None


def _normalize_async_database_url(configured_database_url: str) -> str:
    database_url = make_url(configured_database_url)
    async_driver = {
        "postgresql": "postgresql+asyncpg",
        "postgresql+psycopg2": "postgresql+asyncpg",
    }.get(database_url.drivername, database_url.drivername)
    return database_url.set(drivername=async_driver).render_as_string(hide_password=False)


def _derive_sync_database_url(async_database_url: str) -> str:
    database_url = make_url(async_database_url)
    sync_driver = {
        "sqlite+aiosqlite": "sqlite",
        "postgresql+asyncpg": "postgresql+psycopg2",
        "postgresql+psycopg_async": "postgresql+psycopg",
    }.get(database_url.drivername, database_url.drivername)
    return database_url.set(drivername=sync_driver).render_as_string(hide_password=False)


def _build_database_diagnostic(
    async_database_url: str,
    sync_database_url: str,
    isolation_required: bool,
) -> DatabaseDiagnostic:
    async_url = make_url(async_database_url)
    database_path = async_url.database
    resolved_sqlite_path = None
    if (
        async_url.get_backend_name() == "sqlite"
        and database_path
        and database_path != ":memory:"
    ):
        resolved_sqlite_path = str(Path(database_path).expanduser().resolve())

    return DatabaseDiagnostic(
        async_url=async_url.render_as_string(hide_password=True),
        sync_url=make_url(sync_database_url).render_as_string(hide_password=True),
        isolation_required=isolation_required,
        resolved_sqlite_path=resolved_sqlite_path,
    )


def _validate_database_drivers(
    async_database_url: str,
    sync_database_url: str,
) -> None:
    async_url = make_url(async_database_url)
    if async_url.get_backend_name() != "postgresql":
        return

    driver_requirements = {
        "postgresql+asyncpg": ("asyncpg", "asyncpg (async)"),
        "postgresql+psycopg": ("psycopg", "psycopg (async)"),
        "postgresql+psycopg_async": ("psycopg", "psycopg (async)"),
        "postgresql": ("psycopg2", "psycopg2 (sync)"),
        "postgresql+psycopg2": ("psycopg2", "psycopg2 (sync)"),
    }
    required_drivers = []
    for database_url in (async_url, make_url(sync_database_url)):
        requirement = driver_requirements.get(database_url.drivername)
        if requirement and requirement not in required_drivers:
            required_drivers.append(requirement)

    missing_drivers = [
        label
        for module_name, label in required_drivers
        if importlib.util.find_spec(module_name) is None
    ]
    if missing_drivers:
        raise RuntimeError(
            "PostgreSQL database drivers are not installed: "
            + ", ".join(missing_drivers)
            + ". Configure the backend image before engine creation."
        )


def _validate_isolated_database(async_database_url: str, isolation_required: bool) -> None:
    if not isolation_required:
        return

    database_url = make_url(async_database_url)
    if database_url.get_backend_name() != "sqlite":
        return

    database_path = database_url.database
    tmp_root = Path("/tmp").resolve()
    if not database_path:
        raise ValueError("E2E_REQUIRE_ISOLATED_DB requires a SQLite .db path under /tmp")

    resolved_path = Path(database_path).expanduser().resolve()
    try:
        resolved_path.relative_to(tmp_root)
    except ValueError as error:
        raise ValueError(
            "E2E_REQUIRE_ISOLATED_DB requires a SQLite .db path under /tmp"
        ) from error
    if resolved_path.suffix.lower() != ".db":
        raise ValueError("E2E_REQUIRE_ISOLATED_DB requires a SQLite .db path under /tmp")


configured_database_url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
SQLALCHEMY_DATABASE_URL = _normalize_async_database_url(configured_database_url)
isolation_required = os.getenv("E2E_REQUIRE_ISOLATED_DB", "").lower() == "true"
_validate_isolated_database(SQLALCHEMY_DATABASE_URL, isolation_required)
sync_database_url = _derive_sync_database_url(SQLALCHEMY_DATABASE_URL)
DATABASE_DIAGNOSTIC = _build_database_diagnostic(
    SQLALCHEMY_DATABASE_URL,
    sync_database_url,
    isolation_required,
)
_validate_database_drivers(SQLALCHEMY_DATABASE_URL, sync_database_url)

# 异步引擎
engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL, 
    echo=False,
)

# 异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False,
    autocommit=False, 
    autoflush=False
)

Base = declarative_base()


async def get_db():
    """获取异步数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# 同步会话（用于初始化数据库等操作）
sync_engine_options = {}
if make_url(sync_database_url).get_backend_name() == "sqlite":
    sync_engine_options["connect_args"] = {"check_same_thread": False}
sync_engine = create_engine(sync_database_url, **sync_engine_options)
SyncSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)
