"""Durable whole-book series execution adapter."""

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.features.task_execution.dispatcher import DatabaseTaskDispatcher
from app.features.task_execution.domain import FAILED, SUCCEEDED, TaskOutcome
from app.models.series_production_run import SeriesProductionRun
from app.models.task_execution import TaskExecution
from app.services.series_run_orchestrator import SeriesRunOrchestrator


TASK_TYPE = "series_run.execute"
TERMINAL_RUN_STATUSES = frozenset({"shots_ready", "anchor_ready", "completed", "paused"})


async def enqueue_series_run_execution(db, run: SeriesProductionRun) -> tuple[TaskExecution, bool]:
    return await DatabaseTaskDispatcher(db).submit(
        user_id=run.user_id,
        task_type=TASK_TYPE,
        idempotency_key=f"{run.id}:v{run.version}",
        payload={"run_id": run.id},
        max_attempts=1,
    )


async def queue_series_run_execution(db, run: SeriesProductionRun) -> tuple[TaskExecution, bool]:
    """Persist a series execution before the HTTP request returns."""
    execution, created = await enqueue_series_run_execution(db, run)
    await db.commit()
    return execution, created


async def handle_series_run_execution(execution: TaskExecution) -> TaskOutcome:
    run_id = str((execution.payload or {}).get("run_id") or "")
    async with AsyncSessionLocal() as db:
        run = await db.scalar(
            select(SeriesProductionRun).where(
                SeriesProductionRun.id == run_id,
                SeriesProductionRun.user_id == execution.user_id,
            )
        )
        if not run:
            return TaskOutcome(FAILED, "整书生产运行不存在", error_code="series_run_missing")
        if run.status in TERMINAL_RUN_STATUSES:
            return TaskOutcome(SUCCEEDED, "整书生产运行无需继续执行", {"run_status": run.status})
        await SeriesRunOrchestrator().execute(db, run)
        await db.refresh(run)
        return TaskOutcome(SUCCEEDED, "整书生产运行已执行完成", {"run_status": run.status})
