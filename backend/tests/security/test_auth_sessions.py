from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.core.time_utils import utc_now
from app.models.user import User
from app.models.user_session import UserSession
from app.services.auth_sessions import (
    InvalidRefreshToken,
    issue_session,
    revoke_all_user_sessions,
    rotate_session,
)


@pytest.fixture
async def session_factory(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'auth-session.db'}")
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with factory() as db:
        db.add(
            User(
                id="session-user",
                username="session-user",
                email="session@example.test",
                hashed_password="not-used",
                is_active=True,
            )
        )
        await db.commit()
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_refresh_token_is_hashed_and_rotated_once(session_factory) -> None:
    async with session_factory() as db:
        issued = await issue_session(db, "session-user", "Safari on macOS")
        stored = (await db.execute(select(UserSession))).scalar_one()
        assert stored.refresh_token_hash != issued.refresh_token
        assert issued.refresh_token not in stored.refresh_token_hash
        first_session_id = stored.id

    async with session_factory() as db:
        rotated = await rotate_session(db, issued.refresh_token, "Safari on macOS")
        assert rotated.refresh_token != issued.refresh_token
        sessions = list((await db.execute(select(UserSession))).scalars())
        original = next(item for item in sessions if item.id == first_session_id)
        replacement = next(item for item in sessions if item.id != first_session_id)
        assert original.replaced_by_id == replacement.id
        assert original.revoked_at is not None
        assert replacement.revoked_at is None


@pytest.mark.anyio
async def test_reusing_rotated_token_revokes_its_session_family(session_factory) -> None:
    async with session_factory() as db:
        first = await issue_session(db, "session-user", "device-a")
    async with session_factory() as db:
        await rotate_session(db, first.refresh_token, "device-a")

    async with session_factory() as db:
        with pytest.raises(InvalidRefreshToken, match="已失效"):
            await rotate_session(db, first.refresh_token, "device-a")

    async with session_factory() as db:
        sessions = list((await db.execute(select(UserSession))).scalars())
        assert sessions
        assert all(item.revoked_at is not None for item in sessions)


@pytest.mark.anyio
async def test_expired_and_user_revoked_sessions_cannot_refresh(session_factory) -> None:
    async with session_factory() as db:
        expired = await issue_session(
            db,
            "session-user",
            "expired-device",
            expires_at=utc_now() - timedelta(seconds=1),
        )
        active = await issue_session(db, "session-user", "active-device")
        await revoke_all_user_sessions(db, "session-user")

    async with session_factory() as db:
        for token in (expired.refresh_token, active.refresh_token):
            with pytest.raises(InvalidRefreshToken):
                await rotate_session(db, token, "device")
