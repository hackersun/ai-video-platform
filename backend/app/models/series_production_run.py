"""Persistent state for an idempotent whole-book production run."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint

from app.core.database import Base
from app.core.time_utils import utc_now


class SeriesProductionRun(Base):
    __tablename__ = "series_production_runs"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "novel_id",
            "series_plan_version",
            "idempotency_key",
            name="uq_series_run_idempotency_scope",
        ),
    )

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    novel_id = Column(String(36), ForeignKey("novels.id", ondelete="CASCADE"), nullable=False, index=True)
    series_plan_version = Column(String(100), nullable=False)
    idempotency_key = Column(String(200), nullable=False)
    status = Column(String(30), nullable=False, default="created", index=True)
    current_episode_number = Column(Integer, nullable=False, default=0)
    requested_stages = Column(JSON, nullable=False, default=list)
    model_bindings = Column(JSON, nullable=False, default=dict)
    budget_policy = Column(JSON, nullable=False, default=dict)
    cost_summary = Column(JSON, nullable=False, default=dict)
    gate_summary = Column(JSON, nullable=False, default=dict)
    run_metadata = Column(JSON, nullable=False, default=dict)
    episodes = Column(JSON, nullable=False, default=list)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    __mapper_args__ = {
        "version_id_col": version,
        "version_id_generator": lambda current: (current or 0) + 1,
    }
