"""Poll snapshot-bound video jobs through their selected model driver."""

from __future__ import annotations

from typing import Any

from app.features.model_config.public import resolve_generation_context
from app.features.model_drivers.public import build_builtin_driver_registry, execute_poll
from app.features.video_generation.application.job_sync import VideoJobSyncCommand, sync_video_job_and_shot


async def poll_bound_video_job(db: Any, user_id: str, job: Any) -> dict[str, Any] | None:
    extra = job.extra_data if isinstance(job.extra_data, dict) else {}
    if not extra.get("execution_snapshot_id") or not extra.get("config_model_id"):
        return None
    context = await resolve_generation_context(
        db, user_id=user_id, stage="video",
        explicit_profile_version_id=str(extra["config_model_id"]),
    )
    result = await execute_poll(
        build_builtin_driver_registry(), job.task_id, context.driver_context,
    )
    status_value = {"completed": "succeeded", "cancelled": "failed"}.get(result.status, result.status)
    progress = {"pending": 10, "running": 50, "succeeded": 100, "failed": 100}.get(status_value)
    video_url = result.output.get("video_url")
    cover_url = result.output.get("cover_url")
    error_message = "云端视频生成失败" if status_value == "failed" else None
    await sync_video_job_and_shot(
        db, job, VideoJobSyncCommand(status_value, progress, video_url, cover_url, error_message),
    )
    await db.commit()
    message = {
        "pending": "任务等待中", "running": "视频生成中，请稍候",
        "succeeded": "视频生成完成", "failed": error_message,
    }.get(status_value, f"云端任务状态：{status_value}")
    return {
        "task_id": job.task_id, "job_id": job.id, "status": status_value,
        "video_url": job.video_url, "cover_url": job.cover_url, "message": message,
        "progress": job.progress, "duration": job.duration, "resolution": job.resolution,
    }


__all__ = ["poll_bound_video_job"]
