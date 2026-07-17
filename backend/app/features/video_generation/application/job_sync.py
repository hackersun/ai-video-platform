"""Persist provider video status and mirror shot state."""

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Shot, VideoJob
from app.services.media_persistence import persist_remote_media_url


@dataclass(frozen=True)
class VideoJobSyncCommand:
    status_value: str
    progress: Optional[int]
    video_url: Optional[str]
    cover_url: Optional[str]
    error_message: Optional[str] = None


async def _persist_output(job: VideoJob, url: Optional[str], *, cover: bool) -> Optional[str]:
    if not url:
        return url
    extra = job.extra_data if isinstance(job.extra_data, dict) else {}
    try:
        persisted = await persist_remote_media_url(
            url, media_type="image" if cover else "video", subdir="images" if cover else "videos",
            prefix=f"video-cover-{job.id[:8]}" if cover else f"video-{job.id[:8]}",
            max_bytes=20 * 1024 * 1024 if cover else 300 * 1024 * 1024,
        ) or url
        if persisted != url:
            extra["original_cover_url" if cover else "original_video_url"] = url
            if not cover:
                extra["video_persisted"] = True
        job.extra_data = extra
        return persisted
    except Exception as exc:
        extra["cover_persist_error" if cover else "video_persist_error"] = str(exc)
        if not cover:
            extra["video_persisted"] = False
        job.extra_data = extra
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
    video_url, cover_url = command.video_url, command.cover_url
    if command.status_value == "succeeded":
        video_url = await _persist_output(job, video_url, cover=False)
        cover_url = await _persist_output(job, cover_url, cover=True)
    _update_job(job, command.status_value, command.progress, video_url, cover_url, command.error_message)
    await _sync_shot(db, job, command.status_value, video_url)
