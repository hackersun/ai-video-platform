"""Unique server submission record for one immutable anchor generation input."""

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String, UniqueConstraint

from app.core.database import Base
from app.core.time_utils import utc_now


class SeriesAnchorGenerationSubmission(Base):
    __tablename__ = "series_anchor_generation_submissions"
    __table_args__ = (
        UniqueConstraint("run_id", "generation_key", name="uq_series_anchor_generation_key"),
    )

    id = Column(String(36), primary_key=True)
    run_id = Column(String(36), ForeignKey("series_production_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    generation_key = Column(String(64), nullable=False)
    status = Column(String(20), nullable=False, default="pending", index=True)
    response_payload = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)


__all__ = ["SeriesAnchorGenerationSubmission"]
