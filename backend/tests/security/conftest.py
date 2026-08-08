from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.endpoints.auth import hash_password
from app.core.database import Base, get_db
from app.models.user import User
from main import app


@pytest.fixture
def registration_client(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DEV_MODE", "true")
    monkeypatch.setenv("FERNET_KEY", "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=")
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'registration.db'}")

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def setup() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def override_db():
        async with factory() as db:
            yield db

    asyncio.run(setup())
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            client.auth_factory = factory
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
        asyncio.run(engine.dispose())


@pytest.fixture
def session_api(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DEV_MODE", "false")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-that-is-definitely-long-enough")
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'auth-api.db'}")
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def setup() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as db:
            db.add(
                User(
                    id="api-session-user",
                    username="api-session-user",
                    email="api-session@example.test",
                    hashed_password=hash_password("CommercialPass123!"),
                    account_status="active",
                    is_active=True,
                )
            )
            await db.commit()

    async def override_db():
        async with factory() as db:
            yield db

    asyncio.run(setup())
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            yield client, factory
    finally:
        app.dependency_overrides.pop(get_db, None)
        asyncio.run(engine.dispose())
