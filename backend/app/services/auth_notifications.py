"""Transaction-bound authentication notification producer."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.credential_encryption import encrypt_key
from app.models.auth_notification import AuthNotificationOutbox


def queue_auth_notification(
    db: AsyncSession,
    *,
    user_id: str,
    recipient: str,
    kind: str,
    token: str,
) -> AuthNotificationOutbox:
    notification = AuthNotificationOutbox(
        user_id=user_id,
        recipient=recipient.strip().lower(),
        kind=kind,
        encrypted_payload=encrypt_key(token),
    )
    db.add(notification)
    return notification
