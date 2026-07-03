"""Extract local video frames for non-blocking visual consistency checks."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import unquote, urlparse
from uuid import uuid4


BACKEND_ROOT = Path(__file__).resolve().parents[2]
STATIC_ROOT = BACKEND_ROOT / "static"


class VideoFrameExtractionError(RuntimeError):
    """Structured frame extraction failure."""

    def __init__(self, code: str, message: str, **details: Any) -> None:
        self.detail = {"code": code, "message": message, **details}
        super().__init__(message)


def extract_video_frames(
    video_url: str,
    *,
    fps: float = 1.0,
    max_frames: int = 6,
    output_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Extract frames from a local/static video URL and return /static URLs."""
    if max_frames < 1:
        raise VideoFrameExtractionError(
            "invalid_frame_limit",
            "max_frames must be at least 1",
            max_frames=max_frames,
        )
    if fps <= 0:
        raise VideoFrameExtractionError(
            "invalid_frame_rate",
            "fps must be positive",
            fps=fps,
        )

    video_path = _resolve_local_video(video_url)
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        raise VideoFrameExtractionError(
            "ffmpeg_not_installed",
            "FFmpeg must be installed to extract video frames",
        )

    run_id = _run_id(video_path)
    target_root = output_root or (STATIC_ROOT / "generated" / "frames")
    output_dir = (target_root / run_id).resolve(strict=False)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_pattern = output_dir / "frame-%03d.jpg"

    cmd = [
        ffmpeg_path,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-vf",
        f"fps={fps:g}",
        "-frames:v",
        str(max_frames),
        str(output_pattern),
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        raise VideoFrameExtractionError(
            "ffmpeg_frame_extraction_failed",
            "FFmpeg failed to extract video frames",
            returncode=exc.returncode,
            stdout=(exc.stdout or "").strip(),
            stderr=(exc.stderr or "").strip(),
        ) from exc

    frame_paths = sorted(output_dir.glob("frame-*.jpg"))
    if not frame_paths:
        raise VideoFrameExtractionError(
            "no_frames_extracted",
            "FFmpeg completed but did not produce frames",
            video_url=video_url,
            output_dir=str(output_dir),
        )

    return {
        "run_id": run_id,
        "frame_count": len(frame_paths),
        "frame_urls": [_static_url_for_path(path) for path in frame_paths],
        "fps": fps,
        "max_frames": max_frames,
        "source_video_url": video_url,
    }


def _run_id(video_path: Path) -> str:
    stem = re.sub(r"[^a-zA-Z0-9_-]+", "-", video_path.stem).strip("-") or "video"
    return f"{stem}-{uuid4().hex[:8]}"


def _resolve_local_video(url: str) -> Path:
    raw_url = str(url or "")
    if not raw_url:
        raise VideoFrameExtractionError("missing_video_url", "video_url is required")

    parsed = urlparse(raw_url)
    if parsed.scheme in {"http", "https"}:
        if parsed.hostname in {"localhost", "127.0.0.1", "0.0.0.0"} and parsed.path.startswith("/static/"):
            path = _static_path(parsed.path, raw_url)
        else:
            raise VideoFrameExtractionError(
                "remote_url_unsupported",
                "Remote video URLs must be persisted locally before frame extraction",
                url=raw_url,
            )
    elif parsed.scheme == "file":
        path = Path(unquote(parsed.path))
    elif raw_url.startswith("/static/"):
        path = _static_path(raw_url, raw_url)
    elif parsed.scheme:
        raise VideoFrameExtractionError(
            "unsupported_url_scheme",
            "Only local files and /static URLs are supported for frame extraction",
            url=raw_url,
        )
    else:
        path = Path(raw_url).expanduser()

    resolved = path.resolve(strict=False)
    if not resolved.exists():
        raise VideoFrameExtractionError(
            "local_file_missing",
            "Local video file does not exist",
            url=raw_url,
            path=str(resolved),
        )
    return resolved


def _static_path(path_or_url: str, original_url: str) -> Path:
    parsed_path = urlparse(path_or_url).path
    relative = Path(unquote(parsed_path).removeprefix("/static/"))
    static_root = STATIC_ROOT.resolve(strict=False)
    candidate = (static_root / relative).resolve(strict=False)
    try:
        candidate.relative_to(static_root)
    except ValueError as exc:
        raise VideoFrameExtractionError(
            "static_path_escape",
            "Static video URL cannot resolve outside the static directory",
            url=original_url,
        ) from exc
    return candidate


def _static_url_for_path(path: Path) -> str:
    static_root = STATIC_ROOT.resolve(strict=False)
    resolved = path.resolve(strict=False)
    try:
        relative = resolved.relative_to(static_root)
    except ValueError as exc:
        raise VideoFrameExtractionError(
            "frame_output_outside_static",
            "Extracted frame path is outside the static directory",
            path=str(resolved),
        ) from exc
    return f"/static/{relative.as_posix()}"
