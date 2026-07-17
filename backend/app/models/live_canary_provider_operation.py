"""Recoverable server-owned accounting record for one provider submission attempt."""

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from app.core.database import Base
from app.core.time_utils import utc_now


class LiveCanaryProviderOperation(Base):
    __tablename__ = "live_canary_provider_operations"
    __table_args__ = (UniqueConstraint("run_id", "reservation_id", name="uq_live_canary_operation_reservation"),)

    id = Column(String(36), primary_key=True)
    run_id = Column(String(36), ForeignKey("series_production_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    reservation_id = Column(String(200), nullable=False)
    capability = Column(String(20), nullable=False)
    job_type = Column(String(40), nullable=False)
    job_id = Column(String(100), nullable=False, index=True)
    artifact_id = Column(String(100), nullable=True, index=True)
    provider_task_id = Column(String(200), nullable=True, index=True)
    status = Column(String(30), nullable=False, default="reserved")
    actual_rmb = Column(String(50), nullable=True)
    cost_source = Column(String(40), nullable=True)
    recovery_reason = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)
