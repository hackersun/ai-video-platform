"""Immutable six-dimensional quality evaluation records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Float, Index, JSON, String, event
from sqlalchemy.orm import Session

from app.core.database import Base
from app.core.time_utils import utc_now


QUALITY_DIMENSIONS = (
    "narrative_truth",
    "character_visual",
    "scene_prop_state",
    "motion_camera",
    "voice_lipsync",
    "delivery_integrity",
)


class QualityEvaluation(Base):
    """One append-only evaluation result for one artifact dimension."""

    __tablename__ = "quality_evaluations"
    __table_args__ = (
        CheckConstraint(
            "dimension IN ("
            "'narrative_truth', 'character_visual', 'scene_prop_state', "
            "'motion_camera', 'voice_lipsync', 'delivery_integrity'"
            ")",
            name="ck_quality_evaluation_dimension",
        ),
        CheckConstraint(
            "severity IN ('pass', 'warning', 'blocking')",
            name="ck_quality_evaluation_severity",
        ),
        CheckConstraint(
            "score >= 0 AND score <= 100",
            name="ck_quality_evaluation_score_range",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_quality_evaluation_confidence_range",
        ),
        Index("ix_quality_evaluation_artifact_created", "artifact_id", "created_at"),
        Index("ix_quality_evaluation_workflow_shot", "workflow_id", "shot_id"),
    )

    id = Column(String(36), primary_key=True)
    artifact_id = Column(String(128), nullable=False, index=True)
    artifact_type = Column(String(64), nullable=False, index=True)
    workflow_id = Column(String(36), nullable=True, index=True)
    shot_id = Column(String(36), nullable=True, index=True)
    provider_id = Column(String(64), nullable=True, index=True)
    model_id = Column(String(128), nullable=True, index=True)

    dimension = Column(String(32), nullable=False, index=True)
    expected_state = Column(JSON, nullable=False)
    observed_state = Column(JSON, nullable=False)
    evidence = Column(JSON, nullable=False)
    score = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    severity = Column(String(16), nullable=False)
    blocking = Column(Boolean, nullable=False, default=False, index=True)
    threshold_version = Column(String(64), nullable=False)
    evaluator_version = Column(String(64), nullable=False)
    repair_action = Column(JSON, nullable=True)

    evaluated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


@event.listens_for(QualityEvaluation, "before_update")
def _reject_quality_evaluation_update(*_: Any) -> None:
    raise ValueError("quality evaluation records are immutable")


@event.listens_for(QualityEvaluation, "before_delete")
def _reject_quality_evaluation_delete(*_: Any) -> None:
    raise ValueError("quality evaluation records are immutable")


@event.listens_for(Session, "do_orm_execute")
def _reject_quality_evaluation_bulk_dml(execute_state: Any) -> None:
    """Prevent ORM/Core bulk DML from bypassing mapper immutability hooks."""

    if not (execute_state.is_update or execute_state.is_delete):
        return
    statement = execute_state.statement
    target_table = getattr(statement, "table", None)
    annotations = getattr(target_table, "_annotations", {})
    if (
        target_table is QualityEvaluation.__table__
        or annotations.get("parentmapper") is QualityEvaluation.__mapper__
    ):
        raise ValueError("quality evaluation records are immutable")


@dataclass(frozen=True)
class QualityIssue:
    code: str
    dimension: str
    severity: str
    blocking: bool
    message: str
    evidence: dict[str, Any]
    repair_action: dict[str, Any]


@dataclass(frozen=True)
class QualityEvaluationSet:
    artifact_id: str
    dimension_results: tuple[QualityEvaluation, ...]
    blockers: tuple[QualityIssue, ...]
    warnings: tuple[QualityIssue, ...]
    ready: bool
    overall_readiness: str
    evaluated_at: datetime


__all__ = [
    "QUALITY_DIMENSIONS",
    "QualityEvaluation",
    "QualityEvaluationSet",
    "QualityIssue",
]
