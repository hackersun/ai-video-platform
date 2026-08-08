"""Durable execution records and append-only task events."""

from uuid import uuid4

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    event,
)

from app.core.database import Base
from app.core.time_utils import utc_now


class TaskExecution(Base):
    __tablename__ = "task_executions"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "task_type", "idempotency_key", name="uq_task_execution_idempotency"
        ),
        Index(
            "ix_task_executions_claim",
            "status",
            "next_attempt_at",
            "priority",
            "created_at",
        ),
        Index("ix_task_executions_user_status", "user_id", "status", "created_at"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String(36), nullable=False, index=True)
    project_id = Column(String(36), nullable=True, index=True)
    task_type = Column(String(80), nullable=False, index=True)
    idempotency_key = Column(String(200), nullable=False)
    payload = Column(JSON, nullable=False, default=dict)
    status = Column(String(24), nullable=False, default="pending", server_default="pending")
    priority = Column(Integer, nullable=False, default=0, server_default="0")
    attempt_count = Column(Integer, nullable=False, default=0, server_default="0")
    max_attempts = Column(Integer, nullable=False, default=3, server_default="3")
    next_attempt_at = Column(DateTime, nullable=False, default=utc_now)
    lease_owner = Column(String(100), nullable=True)
    lease_expires_at = Column(DateTime, nullable=True)
    heartbeat_at = Column(DateTime, nullable=True)
    provider_task_id = Column(String(160), nullable=True, index=True)
    result_summary = Column(JSON, nullable=False, default=dict)
    last_error_code = Column(String(80), nullable=True)
    last_error_message = Column(Text, nullable=True)
    cancel_requested_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    version = Column(Integer, nullable=False, default=1, server_default="1")
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)


class TaskExecutionEvent(Base):
    __tablename__ = "task_execution_events"
    __table_args__ = (
        Index("ix_task_execution_events_execution_time", "execution_id", "created_at"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    execution_id = Column(
        String(36),
        ForeignKey("task_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type = Column(String(40), nullable=False)
    status = Column(String(24), nullable=False)
    message = Column(Text, nullable=False)
    details = Column(JSON, nullable=False, default=dict)
    worker_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)


@event.listens_for(TaskExecutionEvent, "before_update")
@event.listens_for(TaskExecutionEvent, "before_delete")
def _reject_task_event_mutation(_mapper, _connection, _target) -> None:
    raise RuntimeError("任务事件不可修改或删除")
