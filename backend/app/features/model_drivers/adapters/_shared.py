"""Small normalization helpers shared by built-in provider drivers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.features.model_drivers.domain import DriverResultError, DriverSubmission, DriverTestResult


async def connection_test(
    operation: Callable[[], Awaitable[DriverSubmission]],
    success_message: str,
) -> DriverTestResult:
    try:
        submission = await operation()
    except Exception as error:
        return DriverTestResult("failed", str(error), {"provider_error_type": type(error).__name__})
    return DriverTestResult(
        "connection_verified",
        success_message,
        {"submission_status": submission.status, "provider_task_id_present": bool(submission.provider_task_id)},
    )


def completed_output(result: dict[str, Any]) -> DriverSubmission:
    task_id = result.get("task_id") or result.get("id")
    status = str(result.get("status") or "completed")
    normalized = "completed" if status in {"success", "succeeded", "completed"} else status
    return DriverSubmission(normalized, str(task_id) if task_id else None, result)


async def unsupported_poll(_provider_task_id: str, _context: Any) -> DriverSubmission:
    raise DriverResultError("driver does not expose a separate polling operation")


def unsupported_submit() -> DriverSubmission:
    raise DriverResultError("driver capability is invoked through its existing production application service")
