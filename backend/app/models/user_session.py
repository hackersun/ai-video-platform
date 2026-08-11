"""Persistent refresh-token session state."""

from app.core.database import Base
from app.core.time_utils import utc_now
from sqlalchemy import Column, DateTime, ForeignKey, Index, String


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    family_id = Column(String(36), nullable=False, index=True)
    refresh_token_hash = Column(String(64), nullable=False, unique=True, index=True)
    device_summary = Column(String(200), nullable=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    last_used_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True, index=True)
    replaced_by_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_user_sessions_user_active", "user_id", "revoked_at", "expires_at"),
    )
