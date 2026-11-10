"""Persistent state for novel → platform Publication pipelines (P1+)."""

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, text

from app.core.database import Base
from app.core.time_utils import utc_now


class NovelPublicationPipeline(Base):
    __tablename__ = "publication_pipelines"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "novel_id",
            "series_plan_version",
            "idempotency_key",
            name="uq_publication_pipeline_idempotency_scope",
        ),
        # R04: one active pipeline per (user, novel); mirrored in db_migrations.
        Index(
            "uq_publication_pipeline_active_novel",
            "user_id",
            "novel_id",
            unique=True,
            sqlite_where=text("status IN ('paused', 'queued', 'running')"),
            postgresql_where=text("status IN ('paused', 'queued', 'running')"),
        ),
    )

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    novel_id = Column(String(36), ForeignKey("novels.id", ondelete="CASCADE"), nullable=False, index=True)
    series_run_id = Column(
        String(36),
        ForeignKey("series_production_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    series_plan_version = Column(String(100), nullable=False)
    idempotency_key = Column(String(200), nullable=False)
    status = Column(String(30), nullable=False, default="queued", index=True)
    stage = Column(String(40), nullable=False, default="accepted", index=True)
    publication_id = Column(String(36), nullable=True, index=True)
    final_video_url = Column(Text, nullable=True)
    delivery = Column(JSON, nullable=False, default=dict)
    media_policy = Column(JSON, nullable=False, default=dict)
    quality_policy = Column(JSON, nullable=False, default=dict)
    gates = Column(JSON, nullable=False, default=dict)
    gate_summary = Column(JSON, nullable=False, default=dict)
    episodes = Column(JSON, nullable=False, default=list)
    blocker_code = Column(String(80), nullable=True)
    blocker_detail = Column(Text, nullable=True)
    pipeline_metadata = Column("metadata", JSON, nullable=False, default=dict)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    __mapper_args__ = {
        "version_id_col": version,
        "version_id_generator": lambda current: (current or 0) + 1,
    }

    def __repr__(self) -> str:
        return (
            f"<NovelPublicationPipeline {self.id} status={self.status} "
            f"stage={self.stage}>"
        )
