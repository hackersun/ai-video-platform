"""In-process launcher for resumable whole-book execution.

The database remains the source of truth. If the process restarts, the same run can
be submitted again and the orchestrator resumes from completed episode stages.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.series_production_run import SeriesProductionRun
from app.services.series_run_orchestrator import SeriesRunOrchestrator


logger = logging.getLogger(__name__)
_tasks: dict[str, asyncio.Task[None]] = {}


async def _execute(run_id: str, user_id: str) -> None:
    try:
        async with AsyncSessionLocal() as db:
            run = await db.scalar(select(SeriesProductionRun).where(
                SeriesProductionRun.id == run_id,
                SeriesProductionRun.user_id == user_id,
            ))
            if run is None or run.status in {"shots_ready", "completed", "paused"}:
                return
            await SeriesRunOrchestrator().execute(db, run)
    except Exception:
        logger.exception("series run background execution failed", extra={"run_id": run_id})
    finally:
        _tasks.pop(run_id, None)


def start_series_run_execution(run_id: str, user_id: str) -> bool:
    current = _tasks.get(run_id)
    if current and not current.done():
        return False
    _tasks[run_id] = asyncio.create_task(_execute(run_id, user_id), name=f"series-run:{run_id}")
    return True


def series_run_execution_active(run_id: str) -> bool:
    task = _tasks.get(run_id)
    return bool(task and not task.done())


__all__ = ["series_run_execution_active", "start_series_run_execution"]
