"""Isolated database lifecycle for destructive Model Center API tests."""

from pathlib import Path
import tempfile

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base


TEST_DATABASE_PATH = (
    Path(tempfile.mkdtemp(prefix="model-center-api-", dir="/tmp")).resolve()
    / "model-center-api.db"
)
engine = create_async_engine(f"sqlite+aiosqlite:///{TEST_DATABASE_PATH}")
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def reset_database() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)


async def dispose_database() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()
