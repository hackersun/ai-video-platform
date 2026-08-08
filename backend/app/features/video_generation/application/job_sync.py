"""Persist provider video status and mirror shot state."""

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models import Shot, VideoJob
from app.features.private_media.integration import persist_private_video_output
from app.features.private_media.service import bind_provider_task


@dataclass(frozen=True)
class VideoJobSyncCommand:
    status_value: str
    progress: Optional[int]
    video_url: Optional[str]
    cover_url: Optional[str]
    error_message: Optional[str] = None


async def _persist_output(
    db: AsyncSession, job: VideoJob, url: Optional[str], *, cover: bool,
) -> Optional[str]:
    if not url:
        return url
    try:
        persisted, extra = await persist_private_video_output(db, job, url, cover=cover)
        job.extra_data = extra
        flag_modified(job, "extra_data")
        return persisted
    except Exception as exc:
        extra = dict(job.extra_data) if isinstance(job.extra_data, dict) else {}
        extra["cover_persist_error" if cover else "video_persist_error"] = str(exc)
        if not cover:
            extra["video_persisted"] = False
        job.extra_data = extra
        flag_modified(job, "extra_data")
        return url


def _update_job(
    job: VideoJob, status_value: str, progress: Optional[int],
    video_url: Optional[str], cover_url: Optional[str], error_message: Optional[str],
) -> None:
    job.status = status_value
    if progress is not None:
        job.progress = progress
    if video_url:
        job.video_url = video_url
    if cover_url:
        job.cover_url = cover_url
    if error_message:
        job.error_message = error_message


async def _auto_check(db: AsyncSession, job: VideoJob, shot: Shot, extra: dict) -> None:
    if extra.get("visual_consistency_auto_check") is not True or extra.get("visual_consistency"):
        return
    try:
        from app.services.visual_consistency_service import record_completed_shot_visual_consistency

        record = await record_completed_shot_visual_consistency(
            db, user_id=job.user_id, shot=shot, video_job=job,
            extract_frames=extra.get("visual_consistency_extract_frames") is True,
        )
        current = job.extra_data if isinstance(job.extra_data, dict) else {}
        current["visual_consistency_auto_checked" if record else "visual_consistency_auto_skipped"] = (
            True if record else "missing_front_reference"
        )
        job.extra_data = current
    except Exception as exc:
        current = job.extra_data if isinstance(job.extra_data, dict) else {}
        current.update(visual_consistency_auto_checked=False, visual_consistency_auto_error=str(exc))
        job.extra_data = current


async def _sync_shot(
    db: AsyncSession, job: VideoJob, status_value: str, video_url: Optional[str],
) -> None:
    extra = job.extra_data if isinstance(job.extra_data, dict) else {}
    shot_id = extra.get("shot_id")
    if not shot_id:
        return
    shot = await db.scalar(select(Shot).where(Shot.id == shot_id, Shot.user_id == job.user_id))
    if not shot:
        return
    shot.video_status = status_value
    if video_url:
        shot.video_url = video_url
    if status_value == "succeeded" and video_url:
        await _auto_check(db, job, shot, extra)


async def sync_video_job_and_shot(
    db: AsyncSession,
    job: VideoJob,
    command: VideoJobSyncCommand,
) -> None:
    if job.task_id:
        await bind_provider_task(
            db, user_id=job.user_id, submission_id=job.id, provider_task_id=job.task_id,
        )
    video_url, cover_url = command.video_url, command.cover_url
    if command.status_value == "succeeded":
        video_url = await _persist_output(db, job, video_url, cover=False)
        cover_url = await _persist_output(db, job, cover_url, cover=True)
    _update_job(job, command.status_value, command.progress, video_url, cover_url, command.error_message)
    await _sync_shot(db, job, command.status_value, video_url)
