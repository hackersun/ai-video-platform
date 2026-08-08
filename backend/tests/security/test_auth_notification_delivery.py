from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.auth_notification import AuthNotificationOutbox
from app.services.auth_notification_delivery import deliver_pending_notifications
from app.services.auth_notifications import queue_auth_notification


class RecordingSender:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.messages = []

    async def send(self, message) -> None:
        if self.error:
            raise self.error
        self.messages.append(message)


def test_delivery_marks_notification_sent_without_exposing_token(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FERNET_KEY", "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=")
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'delivery.db'}")
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def scenario():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as db:
            from app.models.user import User
            db.add(User(id="delivery-user", username="delivery-user", email="delivery@example.test", hashed_password="hash"))
            queue_auth_notification(
                db, user_id="delivery-user", recipient="delivery@example.test",
                kind="verify_email", token="secret-verification-token",
            )
            await db.commit()
        sender = RecordingSender()
        assert await deliver_pending_notifications(factory, sender, public_app_url="https://app.example.test") == 1
        async with factory() as db:
            notification = (await db.execute(select(AuthNotificationOutbox))).scalar_one()
        return sender, notification

    sender, notification = asyncio.run(scenario())
    assert len(sender.messages) == 1
    assert "secret-verification-token" in sender.messages[0].action_url
    assert notification.status == "sent"
    assert notification.sent_at is not None
    asyncio.run(engine.dispose())


def test_delivery_failure_returns_task_to_retry_queue(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FERNET_KEY", "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=")
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'retry.db'}")
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def scenario():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as db:
            from app.models.user import User
            db.add(User(id="retry-user", username="retry-user", email="retry@example.test", hashed_password="hash"))
            item = queue_auth_notification(
                db, user_id="retry-user", recipient="retry@example.test",
                kind="reset_password", token="secret-reset-token",
            )
            await db.commit()
            item_id = item.id
        assert await deliver_pending_notifications(
            factory, RecordingSender(RuntimeError("provider unavailable")),
            public_app_url="https://app.example.test",
        ) == 0
        async with factory() as db:
            return await db.get(AuthNotificationOutbox, item_id)

    notification = asyncio.run(scenario())
    assert notification.status == "pending"
    assert notification.attempts == 1
    assert notification.last_error_code == "delivery_failed"
    asyncio.run(engine.dispose())
