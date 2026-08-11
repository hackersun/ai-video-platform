"""Low-risk runtime checks for load balancers and operators."""

from __future__ import annotations

from sqlalchemy import func, select, text

from app.core.database import AsyncSessionLocal
from app.core.time_utils import utc_now
from app.models.task_execution import TaskExecution


_VISIBLE_QUEUE_STATUSES = (
    "pending",
    "running",
    "retry_wait",
    "dead_letter",
    "needs_attention",
)
_ACTIVE_QUEUE_STATUSES = ("pending", "running", "retry_wait")


def _age_seconds(updated_at, now) -> float:
    if updated_at is None:
        return 0.0
    if updated_at.tzinfo is None and now.tzinfo is not None:
        now = now.replace(tzinfo=None)
    elif updated_at.tzinfo is not None and now.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=None)
    return max(0.0, (now - updated_at).total_seconds())


async def collect_operational_snapshot(factory=AsyncSessionLocal, clock=utc_now) -> dict:
    """Prove database access and report queue counts without customer content."""
    async with factory() as db:
        await db.execute(text("SELECT 1"))
        rows = await db.execute(
            select(TaskExecution.status, func.count(TaskExecution.id))
            .where(TaskExecution.status.in_(_VISIBLE_QUEUE_STATUSES))
            .group_by(TaskExecution.status)
        )
        counts = {status: int(count) for status, count in rows.all()}
        oldest_active = await db.scalar(
            select(func.min(TaskExecution.updated_at)).where(
                TaskExecution.status.in_(_ACTIVE_QUEUE_STATUSES)
            )
        )

    queue = {status: counts.get(status, 0) for status in _VISIBLE_QUEUE_STATUSES}
    queue["oldest_active_age_seconds"] = _age_seconds(oldest_active, clock())
    queue["status"] = "ok"
    return {"database": {"status": "ok"}, "task_queue": queue}
