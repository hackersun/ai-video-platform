from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.core.credential_encryption import decrypt_key
from app.models.auth_notification import AuthNotificationOutbox


def test_registration_persists_encrypted_verification_notification(registration_client) -> None:
    response = registration_client.post(
        "/api/v1/auth/register",
        json={
            "username": "outbox-user",
            "email": "outbox-user@example.test",
            "password": "CommercialPass123!",
        },
    )
    token = response.json()["verification_token"]

    async def read_notification():
        async with registration_client.auth_factory() as db:
            return (await db.execute(select(AuthNotificationOutbox))).scalar_one()

    notification = asyncio.run(read_notification())
    assert notification.kind == "verify_email"
    assert notification.status == "pending"
    assert notification.recipient == "outbox-user@example.test"
    assert token not in notification.encrypted_payload
    assert decrypt_key(notification.encrypted_payload) == token


def test_forgot_password_persists_reset_notification(registration_client) -> None:
    registered = registration_client.post(
        "/api/v1/auth/register",
        json={
            "username": "reset-outbox-user",
            "email": "reset-outbox-user@example.test",
            "password": "CommercialPass123!",
        },
    ).json()
    registration_client.post(
        "/api/v1/auth/verify-email",
        json={"token": registered["verification_token"]},
    )

    response = registration_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "reset-outbox-user@example.test"},
    )
    assert response.status_code == 200

    async def read_notification():
        async with registration_client.auth_factory() as db:
            result = await db.execute(
                select(AuthNotificationOutbox)
                .where(AuthNotificationOutbox.kind == "reset_password")
            )
            return result.scalar_one()

    notification = asyncio.run(read_notification())
    assert notification.status == "pending"
    assert decrypt_key(notification.encrypted_payload)
