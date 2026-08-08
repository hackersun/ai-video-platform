"""Persistent authentication notification outbox."""

from uuid import uuid4

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text

from app.core.database import Base
from app.core.time_utils import utc_now


class AuthNotificationOutbox(Base):
    __tablename__ = "auth_notification_outbox"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    recipient = Column(String(320), nullable=False)
    kind = Column(String(32), nullable=False)
    encrypted_payload = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="pending", server_default="pending")
    attempts = Column(Integer, nullable=False, default=0, server_default="0")
    next_attempt_at = Column(DateTime, nullable=False, default=utc_now)
    lease_expires_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    last_error_code = Column(String(80), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)

    __table_args__ = (
        Index("ix_auth_notification_outbox_delivery", "status", "next_attempt_at"),
        Index("ix_auth_notification_outbox_user", "user_id", "created_at"),
    )
