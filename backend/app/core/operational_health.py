"""Low-risk runtime checks for load balancers and operators."""

from __future__ import annotations

from sqlalchemy import func, select, text

from app.core.database import AsyncSessionLocal
from app.models.task_execution import TaskExecution


_VISIBLE_QUEUE_STATUSES = (
    "pending",
    "running",
    "retry_wait",
    "dead_letter",
    "needs_attention",
)


async def collect_operational_snapshot(factory=AsyncSessionLocal) -> dict:
    """Prove database access and report queue counts without customer content."""
    async with factory() as db:
        await db.execute(text("SELECT 1"))
        rows = await db.execute(
            select(TaskExecution.status, func.count(TaskExecution.id))
            .where(TaskExecution.status.in_(_VISIBLE_QUEUE_STATUSES))
            .group_by(TaskExecution.status)
        )
        counts = {status: int(count) for status, count in rows.all()}

    queue = {status: counts.get(status, 0) for status in _VISIBLE_QUEUE_STATUSES}
    queue["status"] = "ok"
    return {"database": {"status": "ok"}, "task_queue": queue}
