"""Refresh-token issuance, rotation and revocation."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.models.user_session import UserSession


REFRESH_TOKEN_TTL = timedelta(days=30)


class InvalidRefreshToken(ValueError):
    pass


@dataclass(frozen=True)
class IssuedSession:
    refresh_token: str
    session_id: str
    expires_at: datetime


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _new_token() -> str:
    return secrets.token_urlsafe(48)


async def issue_session(
    db: AsyncSession,
    user_id: str,
    device_summary: str | None,
    *,
    family_id: str | None = None,
    expires_at: datetime | None = None,
) -> IssuedSession:
    token = _new_token()
    session_id = str(uuid4())
    expiry = expires_at or (utc_now() + REFRESH_TOKEN_TTL)
    db.add(
        UserSession(
            id=session_id,
            user_id=user_id,
            family_id=family_id or str(uuid4()),
            refresh_token_hash=hash_refresh_token(token),
            device_summary=(device_summary or "")[:200] or None,
            expires_at=expiry,
        )
    )
    await db.commit()
    return IssuedSession(token, session_id, expiry)


async def _revoke_family(db: AsyncSession, family_id: str) -> None:
    await db.execute(
        update(UserSession)
        .where(UserSession.family_id == family_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=utc_now())
    )
    await db.commit()


async def rotate_session(
    db: AsyncSession,
    refresh_token: str,
    device_summary: str | None,
) -> IssuedSession:
    token_hash = hash_refresh_token(refresh_token)
    current = (
        await db.execute(select(UserSession).where(UserSession.refresh_token_hash == token_hash))
    ).scalar_one_or_none()
    if current is None:
        raise InvalidRefreshToken("刷新凭证无效，请重新登录")
    if current.revoked_at is not None or current.replaced_by_id is not None:
        await _revoke_family(db, current.family_id)
        raise InvalidRefreshToken("刷新凭证已失效，相关登录会话已撤销")
    if current.expires_at <= utc_now():
        await _revoke_family(db, current.family_id)
        raise InvalidRefreshToken("登录会话已过期，请重新登录")

    replacement_token = _new_token()
    replacement_id = str(uuid4())
    now = utc_now()
    result = await db.execute(
        update(UserSession)
        .where(
            UserSession.id == current.id,
            UserSession.revoked_at.is_(None),
            UserSession.replaced_by_id.is_(None),
        )
        .values(revoked_at=now, last_used_at=now, replaced_by_id=replacement_id)
    )
    if result.rowcount != 1:
        await db.rollback()
        await _revoke_family(db, current.family_id)
        raise InvalidRefreshToken("刷新凭证已被使用，相关登录会话已撤销")

    expiry = now + REFRESH_TOKEN_TTL
    db.add(
        UserSession(
            id=replacement_id,
            user_id=current.user_id,
            family_id=current.family_id,
            refresh_token_hash=hash_refresh_token(replacement_token),
            device_summary=(device_summary or current.device_summary or "")[:200] or None,
            expires_at=expiry,
        )
    )
    await db.commit()
    return IssuedSession(replacement_token, replacement_id, expiry)


async def revoke_session(db: AsyncSession, refresh_token: str) -> None:
    await db.execute(
        update(UserSession)
        .where(
            UserSession.refresh_token_hash == hash_refresh_token(refresh_token),
            UserSession.revoked_at.is_(None),
        )
        .values(revoked_at=utc_now())
    )
    await db.commit()


async def revoke_all_user_sessions(db: AsyncSession, user_id: str) -> None:
    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=utc_now())
    )
    await db.commit()
