"""Append-only production graph state events."""

from typing import Any

from sqlalchemy import Column, DateTime, Index, Integer, JSON, String, UniqueConstraint, event
from sqlalchemy.orm import Session

from app.core.database import Base
from app.core.time_utils import utc_now


class ProductionStateEvent(Base):
    """An immutable fact used to project story and production state."""

    __tablename__ = "production_state_events"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "novel_id",
            "production_version",
            name="uq_production_state_event_version",
        ),
        Index(
            "ix_production_state_event_episode_scope",
            "user_id",
            "novel_id",
            "episode_index",
        ),
    )

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    novel_id = Column(String(36), nullable=False, index=True)
    chapter_id = Column(String(36), nullable=True, index=True)
    episode_index = Column(Integer, nullable=True, index=True)
    entity_id = Column(String(36), nullable=True, index=True)

    event_type = Column(String(64), nullable=False, index=True)
    story_time = Column(JSON, nullable=False, default=dict)
    production_time = Column(JSON, nullable=False, default=dict)
    before_state = Column(JSON, nullable=False, default=dict)
    after_state = Column(JSON, nullable=False, default=dict)
    evidence = Column(JSON, nullable=True)

    approval_status = Column(String(24), nullable=False, default="pending", index=True)
    approved_by = Column(String(36), nullable=True)
    approved_at = Column(DateTime, nullable=True)

    production_version = Column(Integer, nullable=False)
    previous_event_hash = Column(String(64), nullable=True)
    event_hash = Column(String(64), nullable=False, unique=True, index=True)

    created_at = Column(DateTime, nullable=False, default=utc_now)


IMMUTABLE_ERROR = "Production state events are immutable; append a compensating event instead."


@event.listens_for(ProductionStateEvent, "before_update")
def _reject_production_state_event_update(*_: Any) -> None:
    raise ValueError(IMMUTABLE_ERROR)


@event.listens_for(ProductionStateEvent, "before_delete")
def _reject_production_state_event_delete(*_: Any) -> None:
    raise ValueError(IMMUTABLE_ERROR)


@event.listens_for(Session, "do_orm_execute")
def _reject_production_state_event_bulk_dml(execute_state: Any) -> None:
    if not (execute_state.is_update or execute_state.is_delete):
        return
    statement = execute_state.statement
    target_table = getattr(statement, "table", None)
    annotations = getattr(target_table, "_annotations", {})
    if (
        target_table is ProductionStateEvent.__table__
        or annotations.get("parentmapper") is ProductionStateEvent.__mapper__
    ):
        raise ValueError(IMMUTABLE_ERROR)


__all__ = ["ProductionStateEvent", "IMMUTABLE_ERROR"]
