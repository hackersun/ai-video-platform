"""Feedback records for entity extraction review."""

from app.core.time_utils import utc_now
from sqlalchemy import Column, DateTime, JSON, String

from app.core.database import Base


class EntityFeedback(Base):
    """User or system feedback on entity extraction results."""

    __tablename__ = "entity_feedback"
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    entity_id = Column(String(36), nullable=True, index=True)
    run_id = Column(String(36), nullable=True, index=True)

    action = Column(String(40), nullable=False, index=True)
    before_data = Column(JSON, default=dict)
    after_data = Column(JSON, default=dict)
    reason = Column(String(1000), nullable=True)
    created_at = Column(DateTime, default=utc_now)
    extra_data = Column(JSON, default=dict)
