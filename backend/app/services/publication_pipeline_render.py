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


async def _synthesize_from_succeeded_media(
    db: AsyncSession,
    *,
    user_id: str,
    workflow_id: str,
) -> Optional[SynthesisJob]:
    """Create the episode SynthesisJob from real succeeded media jobs.

    Uses the same ``/workflow/concatenate`` logic the editor uses, so the
    one-click pipeline does not require a manual "合成" click per episode.
    Fails closed (returns None) when no succeeded media exists.
    """
    from app.api.v1.endpoints.workflow import ConcatenateRequest, concatenate_videos
    from app.models.media_generation_job import MediaGenerationJob
    from app.models.shot import Shot

    rows = (
        await db.execute(
            select(MediaGenerationJob, Shot.shot_number)
            .outerjoin(Shot, Shot.id == MediaGenerationJob.shot_id)
            .where(
                MediaGenerationJob.user_id == user_id,
                MediaGenerationJob.workflow_id == workflow_id,
                MediaGenerationJob.status == "succeeded",
                MediaGenerationJob.output_video_url.isnot(None),
                MediaGenerationJob.is_active.isnot(False),
            )
            .order_by(MediaGenerationJob.created_at.desc())
        )
    ).all()
    latest_per_shot: Dict[str, Any] = {}
    for job, shot_number in rows:
        key = str(job.shot_id or job.id)
        if key not in latest_per_shot:
            latest_per_shot[key] = (shot_number if shot_number is not None else 10**6, job)
    if not latest_per_shot:
        return None
    ordered = [job.id for _, job in sorted(latest_per_shot.values(), key=lambda item: (item[0], str(item[1].created_at)))]
    await concatenate_videos(workflow_id, ConcatenateRequest(media_job_ids=ordered), db, user_id)
    return await _latest_synthesis_job(db, user_id=user_id, workflow_id=workflow_id)


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
        job = await _synthesize_from_succeeded_media(db, user_id=user_id, workflow_id=workflow_id)
    if job is None:
        raise PipelineRenderBlocked(
            "synthesis_job_missing",
            "Episode has no synthesis job and no succeeded media to synthesize",
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


def ai_watermark_burn_in_enabled() -> bool:
    """Optional burned-in「AI 生成」watermark; default off (env AI_WATERMARK_BURN_IN)."""
    import os

    return os.getenv("AI_WATERMARK_BURN_IN", "false").strip().lower() in {"1", "true", "yes", "on"}


def _ai_output_args(burn_watermark: bool) -> List[str]:
    from app.core.legal import AI_GENERATED_METADATA_COMMENT

    meta = ["-metadata", f"comment={AI_GENERATED_METADATA_COMMENT}", "-metadata", "description=AI-generated"]
    if burn_watermark:
        # ASCII text so no CJK font file is required.
        vf = "drawtext=text='AI Generated':x=w-tw-24:y=24:fontsize=h/28:fontcolor=white@0.75:box=1:boxcolor=black@0.35"
        return ["-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-c:a", "copy", *meta]
    return ["-c", "copy", *meta]


def assemble_whole_book_mp4(
    episode_output_urls: Sequence[str],
    *,
    book_id: str,
    output_dir: Optional[Path] = None,
    burn_watermark: Optional[bool] = None,
) -> str:
    """Concat episode mp4s into one book mp4 tagged as AI-generated (mp4 comment metadata).

    A single episode is remuxed (stream copy) to carry the metadata; if that fails or the
    file is not local, the original URL is returned unchanged.
    """
    urls = [str(u) for u in episode_output_urls if u]
    if not urls:
        raise PipelineRenderBlocked("book_assemble_empty", "No episode output URLs to assemble")
    if burn_watermark is None:
        burn_watermark = ai_watermark_burn_in_enabled()

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        if len(urls) == 1:
            return urls[0]
        raise PipelineRenderBlocked("ffmpeg_not_installed", "FFmpeg required for whole-book assemble")

    out_dir = output_dir or STATIC_EXPORTS
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / f"book-{book_id}.mp4"
    tail = _ai_output_args(bool(burn_watermark))

    if len(urls) == 1:
        try:
            src = _resolve_local_media(urls[0])
            tmp_out = out_dir / f".book-{book_id}-{uuid4().hex[:8]}.mp4"
            subprocess.run(
                [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(src), *tail, str(tmp_out)],
                check=True, capture_output=True, text=True,
            )
            tmp_out.replace(output_path)
            return _url_for_path(output_path)
        except Exception as exc:  # best effort: keep the episode as the book
            logger.warning("single-episode AI metadata remux skipped: %s", exc)
            return urls[0]

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
    try:
        subprocess.run(
            [
                ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                "-f", "concat", "-safe", "0", "-i", str(concat_list),
                *tail,
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


def probe_final_video_metadata(url: Optional[str]) -> Dict[str, Any]:
    """ffprobe a local final mp4 → duration_seconds / resolution / orientation (best effort)."""
    import json as _json
    import subprocess as _sp

    ffprobe = shutil.which("ffprobe")
    if not url or not ffprobe:
        return {}
    try:
        path = _resolve_local_media(str(url))
        out = _sp.run([ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
                      check=True, capture_output=True, text=True, timeout=30)
        payload = _json.loads(out.stdout)
    except Exception:
        return {}
    video = next((st for st in payload.get("streams", []) if st.get("codec_type") == "video"), {})
    width, height = int(video.get("width") or 0), int(video.get("height") or 0)
    result: Dict[str, Any] = {}
    try:
        duration = float(payload.get("format", {}).get("duration") or video.get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0.0
    if duration > 0:
        result["duration_seconds"] = round(duration, 3)
    if width and height:
        result["resolution"] = f"{min(width, height)}p"
        result["width"], result["height"] = width, height
        result["orientation"] = "portrait" if height > width else ("square" if height == width else "landscape")
    return result

