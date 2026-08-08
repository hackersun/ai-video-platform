"""Durable shot reference-image polling adapter."""

from app.core.database import AsyncSessionLocal
from app.features.task_execution.dispatcher import DatabaseTaskDispatcher
from app.features.task_execution.domain import DEAD_LETTER, RETRY_WAIT, TaskOutcome
from app.models.task_execution import TaskExecution
from app.services.image_poll_service import mark_shot_image_poll_exhausted, poll_shot_image_once


TASK_TYPE = "shot_image.poll"


async def enqueue_shot_image_poll(
    db,
    *,
    shot_id: str,
    provider_task_id: str,
    user_id: str,
) -> tuple[TaskExecution, bool]:
    return await DatabaseTaskDispatcher(db).submit(
        user_id=user_id,
        task_type=TASK_TYPE,
        idempotency_key=f"{shot_id}:{provider_task_id}",
        payload={"shot_id": shot_id, "provider_task_id": provider_task_id},
        provider_task_id=provider_task_id,
        max_attempts=60,
    )


async def queue_shot_image_poll(
    db,
    shot_id: str,
    provider_task_id: str,
    user_id: str,
) -> str:
    """Persist shot state and its polling task in one transaction."""
    execution, _created = await enqueue_shot_image_poll(
        db,
        shot_id=shot_id,
        provider_task_id=provider_task_id,
        user_id=user_id,
    )
    await db.commit()
    return execution.id


async def handle_shot_image_poll(execution: TaskExecution) -> TaskOutcome:
    payload = execution.payload or {}
    shot_id = str(payload.get("shot_id") or "")
    provider_task_id = str(payload.get("provider_task_id") or execution.provider_task_id or "")
    async with AsyncSessionLocal() as db:
        outcome = await poll_shot_image_once(
            db,
            shot_id=shot_id,
            task_id=provider_task_id,
            user_id=execution.user_id,
        )
        attempt_count = execution.attempt_count if execution.attempt_count is not None else 0
        max_attempts = execution.max_attempts if execution.max_attempts is not None else 60
        if outcome.status == RETRY_WAIT and attempt_count >= max_attempts:
            await mark_shot_image_poll_exhausted(db, shot_id)
            outcome = TaskOutcome(
                DEAD_LETTER,
                "参考图生成等待超时，请检查供应商任务后手动重试",
                error_code="provider_poll_exhausted",
            )
        await db.commit()
        return outcome
