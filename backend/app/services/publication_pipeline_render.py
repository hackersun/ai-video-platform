"""Episode ffmpeg_local ensure + whole-book concat for publication pipelines."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.models.synthesis_job import SynthesisJob
from app.models.workflow import Workflow
from app.services.ffmpeg_local_renderer import FFmpegLocalRenderError, render_workflow_package
from app.services.publication_readiness import is_final_video_url

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
STATIC_EXPORTS = BACKEND_ROOT / "static" / "exports"


class PipelineRenderBlocked(RuntimeError):
    def __init__(self, code: str, message: str, **details: Any):
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


def _url_for_path(path: Path) -> str:
    try:
        rel = path.resolve().relative_to(BACKEND_ROOT.resolve())
    except ValueError:
        return str(path)
    return "/" + str(rel).replace("\\", "/")


def _resolve_local_media(url: str) -> Path:
    raw = str(url or "")
    if raw.startswith("/static/"):
        path = BACKEND_ROOT / raw.lstrip("/")
    elif raw.startswith("static/"):
        path = BACKEND_ROOT / raw
    else:
        path = Path(raw)
    if not path.exists():
        raise PipelineRenderBlocked(
            "episode_media_missing",
            f"Local media path missing for concat: {raw}",
            path=str(path),
        )
    return path


async def _latest_synthesis_job(
    db: AsyncSession,
    *,
    user_id: str,
    workflow_id: str,
) -> Optional[SynthesisJob]:
    result = await db.execute(
        select(SynthesisJob)
        .where(
            SynthesisJob.user_id == user_id,
            SynthesisJob.workflow_id == workflow_id,
        )
        .order_by(SynthesisJob.created_at.desc())
    )
    return result.scalars().first()


def _extract_segments(extra_data: Dict[str, Any]) -> List[dict]:
    if isinstance(extra_data.get("segments"), list) and extra_data["segments"]:
        return list(extra_data["segments"])
    artifacts = extra_data.get("render_artifacts") if isinstance(extra_data.get("render_artifacts"), dict) else {}
    for key in ("segments", "tracks"):
        value = artifacts.get(key)
        if isinstance(value, list) and value and key == "segments":
            return list(value)
    # Allow already-rendered jobs to skip without segments.
    return []


async def ensure_episode_ffmpeg_local(
    db: AsyncSession,
    *,
    user_id: str,
    workflow_id: str,
    force: bool = False,
    burn_subtitles: bool = False,
) -> Dict[str, Any]:
    """Ensure an episode workflow has a final ffmpeg_local mp4.

    Idempotent: skips when SynthesisJob already has rendered final video.
    """
    workflow = await db.scalar(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user_id)
    )
    if workflow is None:
        raise PipelineRenderBlocked(
            "workflow_not_found",
            "Episode workflow not found for publication pipeline render",
            workflow_id=workflow_id,
        )

    job = await _latest_synthesis_job(db, user_id=user_id, workflow_id=workflow_id)
    if job is None:
        raise PipelineRenderBlocked(
            "synthesis_job_missing",
            "Episode has no synthesis job to render",
            workflow_id=workflow_id,
        )

    extra = dict(job.extra_data or {})
    if (
        not force
        and extra.get("render_status") == "rendered"
        and extra.get("render_backend") == "ffmpeg_local"
        and is_final_video_url(job.output_url)
    ):
        return {
            "workflow_id": workflow_id,
            "synthesis_job_id": job.id,
            "render_status": "rendered",
            "render_backend": "ffmpeg_local",
            "output_url": job.output_url,
            "skipped": True,
        }

    segments = _extract_segments(extra)
    if not segments:
        # Fail closed unless already final — never invent preview success.
        if is_final_video_url(job.output_url) and extra.get("render_status") == "rendered":
            # Prefer upgrading metadata when backend already final.
            if extra.get("render_backend") != "ffmpeg_local":
                raise PipelineRenderBlocked(
                    "preview_package_not_publishable",
                    "Episode output is not an ffmpeg_local final render",
                    workflow_id=workflow_id,
                    render_backend=extra.get("render_backend"),
                )
        raise PipelineRenderBlocked(
            "episode_render_inputs_missing",
            "Episode synthesis job lacks segments for ffmpeg_local render",
            workflow_id=workflow_id,
            synthesis_job_id=job.id,
        )

    render_id = str(uuid4())
    manifest = {
        "id": render_id,
        "type": "ffmpeg_local_render_package",
        "version": "1.0",
        "workflow_id": workflow_id,
        "synthesis_job_id": job.id,
        "title": job.title or f"workflow-{workflow_id[:8]}",
        "segments": segments,
        "render_backend": "ffmpeg_local",
        "created_at": utc_now().isoformat(),
    }
    STATIC_EXPORTS.mkdir(parents=True, exist_ok=True)
    try:
        local_result = await render_workflow_package(
            manifest,
            output_dir=STATIC_EXPORTS,
            burn_subtitles=burn_subtitles,
        )
    except FFmpegLocalRenderError as exc:
        extra["render_status"] = "failed"
        extra["render_backend"] = "ffmpeg_local"
        extra["render_issues"] = [exc.detail]
        job.extra_data = extra
        job.status = "failed"
        job.error_message = exc.detail.get("message") if isinstance(exc.detail, dict) else str(exc)
        await db.flush()
        raise PipelineRenderBlocked(
            str(exc.detail.get("code") if isinstance(exc.detail, dict) else "ffmpeg_render_failed"),
            str(exc.detail.get("message") if isinstance(exc.detail, dict) else exc),
            workflow_id=workflow_id,
            detail=exc.detail if isinstance(exc.detail, dict) else {"message": str(exc)},
        ) from exc

    output_url = local_result.get("output_url")
    render_artifacts = {
        "output_url": output_url,
        "srt_url": local_result.get("subtitle_url"),
        "ffmpeg_log_tail": local_result.get("log_tail"),
    }
    extra["render_status"] = "rendered"
    extra["render_backend"] = "ffmpeg_local"
    extra["rendered_at"] = utc_now().isoformat()
    extra["render_artifacts"] = render_artifacts
    extra["output_kind"] = "final_video"
    extra["is_publishable"] = True
    job.extra_data = extra
    job.status = "succeeded"
    job.progress = 100
    job.output_url = output_url
    job.duration_seconds = local_result.get("duration") or job.duration_seconds
    job.error_message = None
    await db.flush()
    return {
        "workflow_id": workflow_id,
        "synthesis_job_id": job.id,
        "render_status": "rendered",
        "render_backend": "ffmpeg_local",
        "output_url": output_url,
        "skipped": False,
    }


def assemble_whole_book_mp4(
    episode_output_urls: Sequence[str],
    *,
    book_id: str,
    output_dir: Optional[Path] = None,
) -> str:
    """Concat episode mp4s into one book mp4. Single episode returns that URL."""
    urls = [str(u) for u in episode_output_urls if u]
    if not urls:
        raise PipelineRenderBlocked("book_assemble_empty", "No episode output URLs to assemble")
    if len(urls) == 1:
        return urls[0]

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise PipelineRenderBlocked("ffmpeg_not_installed", "FFmpeg required for whole-book assemble")

    out_dir = output_dir or STATIC_EXPORTS
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir = out_dir / f".book-concat-{book_id}-{uuid4().hex[:8]}"
    work_dir.mkdir(parents=True, exist_ok=True)
    concat_list = work_dir / "concat.txt"
    lines = []
    for url in urls:
        path = _resolve_local_media(url)
        # ffmpeg concat demuxer requires escaped single quotes
        escaped = str(path).replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    concat_list.write_text("\n".join(lines) + "\n", encoding="utf-8")
    output_path = out_dir / f"book-{book_id}.mp4"
    try:
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_list),
                "-c",
                "copy",
                str(output_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise PipelineRenderBlocked(
            "book_assemble_failed",
            "FFmpeg failed to concatenate episode mp4s",
            stderr=(exc.stderr or "")[-2000:],
        ) from exc
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
    return _url_for_path(output_path)


__all__ = [
    "PipelineRenderBlocked",
    "assemble_whole_book_mp4",
    "ensure_episode_ffmpeg_local",
]
