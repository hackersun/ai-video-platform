"""Lease-based delivery for authentication notification outbox rows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol
from urllib.parse import quote

from sqlalchemy import and_, or_, select, update

from app.core.credential_encryption import decrypt_key
from app.core.time_utils import utc_now
from app.models.auth_notification import AuthNotificationOutbox


@dataclass(frozen=True)
class AuthEmailMessage:
    recipient: str
    subject: str
    body: str
    action_url: str


class AuthEmailSender(Protocol):
    async def send(self, message: AuthEmailMessage) -> None: ...


def _message(item: AuthNotificationOutbox, token: str, public_app_url: str) -> AuthEmailMessage:
    base_url = public_app_url.rstrip("/")
    route = "verify-email" if item.kind == "verify_email" else "reset-password"
    action_url = f"{base_url}/{route}?token={quote(token, safe='')}"
    if item.kind == "verify_email":
        subject = "验证你的 AI 视频平台邮箱"
        body = f"请打开以下链接完成邮箱验证：\n{action_url}\n链接 24 小时内有效。"
    else:
        subject = "重置你的 AI 视频平台密码"
        body = f"请打开以下链接重置密码：\n{action_url}\n链接 30 分钟内有效。"
    return AuthEmailMessage(item.recipient, subject, body, action_url)


async def _claim_one(factory, lease_seconds: int) -> AuthNotificationOutbox | None:
    now = utc_now()
    async with factory() as db:
        candidate = (
            await db.execute(
                select(AuthNotificationOutbox)
                .where(
                    or_(
                        and_(
                            AuthNotificationOutbox.status == "pending",
                            AuthNotificationOutbox.next_attempt_at <= now,
                        ),
                        and_(
                            AuthNotificationOutbox.status == "processing",
                            AuthNotificationOutbox.lease_expires_at <= now,
                        ),
                    )
                )
                .order_by(AuthNotificationOutbox.created_at)
                .limit(1)
            )
        ).scalar_one_or_none()
        if candidate is None:
            return None
        claimed = await db.execute(
            update(AuthNotificationOutbox)
            .where(
                AuthNotificationOutbox.id == candidate.id,
                AuthNotificationOutbox.status == candidate.status,
            )
            .values(
                status="processing",
                attempts=AuthNotificationOutbox.attempts + 1,
                lease_expires_at=now + timedelta(seconds=lease_seconds),
            )
        )
        if claimed.rowcount != 1:
            await db.rollback()
            return None
        await db.commit()
        return await db.get(AuthNotificationOutbox, candidate.id)


async def deliver_pending_notifications(
    factory,
    sender: AuthEmailSender,
    *,
    public_app_url: str,
    limit: int = 20,
    lease_seconds: int = 120,
) -> int:
    delivered = 0
    for _ in range(limit):
        item = await _claim_one(factory, lease_seconds)
        if item is None:
            break
        try:
            token = decrypt_key(item.encrypted_payload)
            if not token:
                raise ValueError("notification payload cannot be decrypted")
            await sender.send(_message(item, token, public_app_url))
        except Exception:
            async with factory() as db:
                await db.execute(
                    update(AuthNotificationOutbox)
                    .where(AuthNotificationOutbox.id == item.id)
                    .values(
                        status="pending",
                        next_attempt_at=utc_now() + timedelta(minutes=min(60, 2 ** min(item.attempts, 5))),
                        lease_expires_at=None,
                        last_error_code="delivery_failed",
                    )
                )
                await db.commit()
            continue
        async with factory() as db:
            await db.execute(
                update(AuthNotificationOutbox)
                .where(AuthNotificationOutbox.id == item.id)
                .values(status="sent", sent_at=utc_now(), lease_expires_at=None, last_error_code=None)
            )
            await db.commit()
        delivered += 1
    return delivered
