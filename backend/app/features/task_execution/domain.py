"""Task execution states and safe transition outcomes."""

from dataclasses import dataclass, field
from datetime import timedelta


PENDING = "pending"
RUNNING = "running"
RETRY_WAIT = "retry_wait"
SUCCEEDED = "succeeded"
FAILED = "failed"
DEAD_LETTER = "dead_letter"
NEEDS_ATTENTION = "needs_attention"
CANCELLED = "cancelled"
TERMINAL_STATUSES = frozenset({SUCCEEDED, FAILED, DEAD_LETTER, NEEDS_ATTENTION, CANCELLED})

STATUS_LABELS = {
    PENDING: "等待执行",
    RUNNING: "执行中",
    RETRY_WAIT: "等待安全重试",
    SUCCEEDED: "已完成",
    FAILED: "执行失败",
    DEAD_LETTER: "已停止自动重试",
    NEEDS_ATTENTION: "需要人工确认",
    CANCELLED: "已取消",
}


class TaskTransitionError(ValueError):
    """A task action is unsafe or invalid for its current state."""


@dataclass(frozen=True)
class TaskOutcome:
    status: str
    message: str
    result_summary: dict = field(default_factory=dict)
    error_code: str | None = None
    retry_after: timedelta | None = None


def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, "状态未知")
