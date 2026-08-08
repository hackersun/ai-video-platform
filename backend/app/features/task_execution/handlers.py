"""Handler registry for durable task types."""

from collections.abc import Awaitable, Callable

from app.features.task_execution.domain import TaskOutcome
from app.models.task_execution import TaskExecution


TaskHandler = Callable[[TaskExecution], Awaitable[TaskOutcome]]
DEFAULT_HANDLERS: dict[str, TaskHandler] = {}


def register_handler(task_type: str, handler: TaskHandler) -> None:
    DEFAULT_HANDLERS[task_type] = handler
