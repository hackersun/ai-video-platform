"""Public task execution facade."""

from app.features.task_execution.dispatcher import DatabaseTaskDispatcher
from app.features.task_execution.domain import TaskOutcome, TaskTransitionError, status_label
from app.features.task_execution.repository import claim_one, request_cancel, retry_execution

__all__ = [
    "DatabaseTaskDispatcher",
    "TaskOutcome",
    "TaskTransitionError",
    "claim_one",
    "request_cancel",
    "retry_execution",
    "status_label",
]
