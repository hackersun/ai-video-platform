"""
Local FFmpeg renderer for workflow render manifests.
"""

from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import unquote, unquote_plus, urlparse
from uuid import uuid4

import httpx


BACKEND_ROOT = Path(__file__).resolve().parents[2]
STATIC_ROOT = BACKEND_ROOT / "static"
_FILTER_CACHE: Dict[Tuple[str, str], bool] = {}
_REMOTE_AUDIO_MAX_BYTES = 50 * 1024 * 1024
_REMOTE_AUDIO_TIMEOUT_SECONDS = 90.0
_REMOTE_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".flac", ".mp4"}
_REMOTE_AUDIO_CONTENT_TYPES = {
    "audio/aac",
    "audio/flac",
    "audio/mp3",
    "audio/mp4",
    "audio/mpeg",
    "audio/ogg",
    "audio/opus",
    "audio/wav",
    "audio/wave",
    "audio/x-m4a",
    "audio/x-wav",
    "application/octet-stream",
    "binary/octet-stream",
    "video/mp4",
}
_SIGNED_URL_QUERY_KEYS = {
    "access_key",
    "accesskeyid",
    "e",
    "expires",
    "ossaccesskeyid",
    "security-token",
    "signature",
    "token",
    "x-amz-credential",
    "x-amz-security-token",
    "x-amz-signature",
    "x-oss-credential",
    "x-oss-date",
    "x-oss-expires",
    "x-oss-security-token",
    "x-oss-signature",
    "x-qiniu-deadline",
}


class FFmpegLocalRenderError(RuntimeError):
    """Structured renderer failure for route integration."""

    def __init__(self, code: str, message: str, **details: Any) -> None:
        self.detail = {"code": code, "message": message, **details}
        super().__init__(message)


async def render_workflow_package(
    manifest: dict,
    *,
    output_dir: Path,
    burn_subtitles: bool,
) -> dict:
    ffmpeg_path, ffprobe_path = _ensure_ffmpeg_tools()
    segments = manifest.get("segments") if isinstance(manifest, dict) else None
    if not isinstance(segments, list) or not segments:
        raise FFmpegLocalRenderError(
            "empty_render_manifest",
            "Render manifest must include at least one segment",
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    render_id = _safe_id(str(manifest.get("id") or manifest.get("workflow_id") or uuid4()))
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    work_dir = output_dir / f".ffmpeg-{render_id}-{timestamp}"
    work_dir.mkdir(parents=True, exist_ok=True)
    logs: List[str] = []

    try:
        prepared_segments = _prepare_segments(segments, ffprobe_path, work_dir)
        srt_path, has_subtitles = _write_srt(segments, output_dir / f"final-{render_id}-{timestamp}.srt")
        subtitle_filter_path = None
        if burn_subtitles and has_subtitles:
            if not _ffmpeg_has_filter(ffmpeg_path, "subtitles"):
                raise FFmpegLocalRenderError(
                    "ffmpeg_subtitles_filter_unavailable",
                    "FFmpeg subtitles filter is required to burn subtitles",
                    subtitle_url=_url_for_path(srt_path),
                )
            subtitle_filter_path = srt_path
        normalized_paths = [
            _render_segment(index, segment, work_dir, ffmpeg_path, logs)
            for index, segment in enumerate(prepared_segments, start=1)
        ]
        output_path = output_dir / f"final-{render_id}-{timestamp}.mp4"
        _concat_segments(
            normalized_paths,
            output_path,
            srt_path=subtitle_filter_path,
            work_dir=work_dir,
            ffmpeg_path=ffmpeg_path,
            logs=logs,
        )
        metadata = _probe_media(output_path, ffprobe_path)
    except FFmpegLocalRenderError:
        raise
    except subprocess.CalledProcessError as exc:
        _append_process_log(logs, exc.stdout, exc.stderr)
        raise FFmpegLocalRenderError(
            "ffmpeg_render_failed",
            "FFmpeg failed to render workflow package",
            log_tail=_tail(logs),
            returncode=exc.returncode,
        ) from exc
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    return {
        "output_url": _url_for_path(output_path),
        "duration": metadata["duration"],
        "width": metadata["width"],
        "height": metadata["height"],
        "subtitle_url": _url_for_path(srt_path),
        "log_tail": _tail(logs),
    }


def _ensure_ffmpeg_tools() -> Tuple[str, str]:
    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")
    if not ffmpeg_path or not ffprobe_path:
        raise FFmpegLocalRenderError(
            "ffmpeg_not_installed",
            "FFmpeg and ffprobe must be installed for local rendering",
        )
    return ffmpeg_path, ffprobe_path


def _ffmpeg_has_filter(ffmpeg_path: str, name: str) -> bool:
    cache_key = (ffmpeg_path, name)
    if cache_key in _FILTER_CACHE:
        return _FILTER_CACHE[cache_key]
    try:
        result = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-filters"],
            capture_output=True,
            text=True,
        )
    except OSError:
        _FILTER_CACHE[cache_key] = False
        return False
    needle = f" {name} "
    available = result.returncode == 0 and any(needle in line for line in result.stdout.splitlines())
    _FILTER_CACHE[cache_key] = available
    return available


def _prepare_segments(
    segments: List[dict],
    ffprobe_path: str,
    work_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    prepared: List[Dict[str, Any]] = []
    for index, segment in enumerate(segments, start=1):
        video_url = _segment_video_url(segment)
        if not video_url:
            raise FFmpegLocalRenderError(
                "missing_video_url",
                "Segment is missing a video URL",
                segment_index=segment.get("index") or index,
            )
        video_path = _resolve_local_media(video_url)
        audio_url = _segment_audio_url(segment)
        audio_path = _resolve_audio_media(audio_url, work_dir, index) if audio_url else None
        music_url = _segment_music_url(segment)
        music_path = _resolve_optional_music(music_url)
        prepared.append(
            {
                "index": segment.get("index") or index,
                "video_path": video_path,
                "audio_path": audio_path,
                "music_path": music_path,
                "music_volume": _segment_music_volume(segment),
                "duration": _segment_duration(segment, video_path, ffprobe_path),
            }
        )
    return prepared


def _resolve_optional_music(url: Optional[str]) -> Optional[Path]:
    if not url:
        return None
    try:
        return _resolve_local_media(url)
    except FFmpegLocalRenderError:
        return None


def _resolve_audio_media(url: str, work_dir: Optional[Path], segment_index: int) -> Path:
    raw_url = str(url)
    parsed = urlparse(raw_url)
    if parsed.scheme in {"http", "https"} and not _is_local_static_http_url(parsed):
        if work_dir is None:
            raise FFmpegLocalRenderError(
                "remote_audio_work_dir_missing",
                "Remote audio requires a renderer work directory",
                url=_redact_url(raw_url),
            )
        return _download_remote_audio(raw_url, work_dir, segment_index)
    return _resolve_local_media(raw_url)


def _segment_video_url(segment: dict) -> Optional[str]:
    video = segment.get("video") if isinstance(segment.get("video"), dict) else {}
    return video.get("url") or segment.get("video_url") or segment.get("videoUrl")


def _segment_audio_url(segment: dict) -> Optional[str]:
    audio = segment.get("audio") if isinstance(segment.get("audio"), dict) else {}
    return audio.get("url") or segment.get("audio_url") or segment.get("audioUrl")


def _segment_music_url(segment: dict) -> Optional[str]:
    music = segment.get("music") if isinstance(segment.get("music"), dict) else {}
    return music.get("url") or segment.get("music_url") or segment.get("musicUrl")


def _segment_music_volume(segment: dict) -> float:
    music = segment.get("music") if isinstance(segment.get("music"), dict) else {}
    value = _non_negative_float(music.get("volume"))
    if value is None:
        value = _non_negative_float(segment.get("music_volume"))
    return min(value, 1.0) if value is not None else 0.18


def _segment_duration(segment: dict, video_path: Path, ffprobe_path: str) -> float:
    video = segment.get("video") if isinstance(segment.get("video"), dict) else {}
    audio = segment.get("audio") if isinstance(segment.get("audio"), dict) else {}
    candidates = [
        segment.get("duration_seconds"),
        video.get("duration_seconds"),
        audio.get("duration_seconds"),
    ]
    if segment.get("start_seconds") is not None and segment.get("end_seconds") is not None:
        candidates.append(float(segment["end_seconds"]) - float(segment["start_seconds"]))
    for value in candidates:
        duration = _positive_float(value)
        if duration is not None:
            return duration
    return max(_probe_media(video_path, ffprobe_path)["duration"], 0.1)


def _resolve_local_media(url: str) -> Path:
    raw_url = str(url)
    parsed = urlparse(raw_url)
    if parsed.scheme in {"http", "https"}:
        if _is_local_static_http_url(parsed):
            path = _static_path(parsed.path, raw_url)
        else:
            raise FFmpegLocalRenderError(
                "remote_url_unsupported",
                "Remote media URLs are not supported by the local renderer yet",
                url=_redact_url(raw_url),
            )
    elif parsed.scheme == "file":
        path = Path(unquote(parsed.path))
    elif raw_url.startswith("/static/"):
        path = _static_path(raw_url, raw_url)
    elif parsed.scheme:
        raise FFmpegLocalRenderError(
            "unsupported_url_scheme",
            "Only local files and /static URLs are supported by the local renderer",
            url=raw_url,
        )
    else:
        path = Path(raw_url).expanduser()

    resolved = path.resolve(strict=False)
    if not resolved.exists():
        raise FFmpegLocalRenderError(
            "local_file_missing",
            "Local media file does not exist",
            url=raw_url,
            path=str(resolved),
        )
    return resolved


def _is_local_static_http_url(parsed: Any) -> bool:
    return parsed.hostname in {"localhost", "127.0.0.1", "0.0.0.0"} and parsed.path.startswith("/static/")


def _download_remote_audio(url: str, work_dir: Path, segment_index: int) -> Path:
    parsed = urlparse(url)
    extension = _remote_audio_extension(parsed.path)
    target_path = work_dir / f"remote-audio-{segment_index:03d}-{uuid4().hex}{extension}"

    try:
        with httpx.Client(timeout=_REMOTE_AUDIO_TIMEOUT_SECONDS, follow_redirects=True) as client:
            with client.stream("GET", url, headers={"Accept": "audio/*"}) as response:
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                if content_type and content_type not in _REMOTE_AUDIO_CONTENT_TYPES:
                    raise FFmpegLocalRenderError(
                        "remote_audio_type_unsupported",
                        "Remote audio content type is not supported by the local renderer",
                        content_type=content_type,
                        url=_redact_url(url),
                    )
                total_bytes = 0
                with target_path.open("wb") as file:
                    for chunk in response.iter_bytes():
                        if not chunk:
                            continue
                        total_bytes += len(chunk)
                        if total_bytes > _REMOTE_AUDIO_MAX_BYTES:
                            target_path.unlink(missing_ok=True)
                            raise FFmpegLocalRenderError(
                                "remote_audio_too_large",
                                "Remote audio exceeds the local renderer size limit",
                                max_bytes=_REMOTE_AUDIO_MAX_BYTES,
                                url=_redact_url(url),
                            )
                        file.write(chunk)
    except FFmpegLocalRenderError:
        raise
    except httpx.TimeoutException as exc:
        raise FFmpegLocalRenderError(
            "remote_audio_download_timeout",
            "Timed out downloading remote audio for local rendering",
            url=_redact_url(url),
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise FFmpegLocalRenderError(
            "remote_audio_download_failed",
            "Failed to download remote audio for local rendering",
            status_code=exc.response.status_code,
            url=_redact_url(url),
        ) from exc
    except httpx.HTTPError as exc:
        raise FFmpegLocalRenderError(
            "remote_audio_download_failed",
            "Failed to download remote audio for local rendering",
            url=_redact_url(url),
        ) from exc
    except OSError as exc:
        raise FFmpegLocalRenderError(
            "remote_audio_write_failed",
            "Failed to write remote audio for local rendering",
            url=_redact_url(url),
        ) from exc

    if not target_path.exists() or target_path.stat().st_size <= 0:
        raise FFmpegLocalRenderError(
            "remote_audio_empty",
            "Remote audio download produced an empty file",
            url=_redact_url(url),
        )
    return target_path


def _remote_audio_extension(path: str) -> str:
    extension = Path(unquote(path)).suffix.lower()
    if extension in _REMOTE_AUDIO_EXTENSIONS:
        return extension
    return ".mp3"


def _redact_url(raw_url: str) -> str:
    parsed = urlparse(str(raw_url))
    if not parsed.query:
        return str(raw_url)
    redacted_parts: List[str] = []
    for part in parsed.query.split("&"):
        key = part.split("=", 1)[0]
        if unquote_plus(key).lower() in _SIGNED_URL_QUERY_KEYS:
            redacted_parts.append(f"{key}=<redacted>")
        else:
            redacted_parts.append(part)
    return parsed._replace(query="&".join(redacted_parts)).geturl()


def _static_path(path_or_url: str, original_url: str) -> Path:
    parsed_path = urlparse(path_or_url).path
    relative = Path(unquote(parsed_path).removeprefix("/static/"))
    static_root = STATIC_ROOT.resolve(strict=False)
    candidate = (static_root / relative).resolve(strict=False)
    try:
        candidate.relative_to(static_root)
    except ValueError as exc:
        raise FFmpegLocalRenderError(
            "static_path_escape",
            "Static media URL cannot resolve outside the static directory",
            url=original_url,
        ) from exc
    return candidate


def _render_segment(
    index: int,
    segment: Dict[str, Any],
    work_dir: Path,
    ffmpeg_path: str,
    logs: List[str],
) -> Path:
    output_path = work_dir / f"segment-{index:03d}.mp4"
    cmd = [
        ffmpeg_path,
        "-y",
        "-hide_banner",
        "-i",
        str(segment["video_path"]),
    ]
    if segment["audio_path"]:
        cmd.extend(["-i", str(segment["audio_path"])])
        audio_input_index = 1
    else:
        cmd.extend(["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"])
        audio_input_index = 1

    music_path = segment.get("music_path")
    if music_path:
        cmd.extend(["-i", str(music_path)])
        music_input_index = 2
        music_volume = _non_negative_float(segment.get("music_volume"))
        music_volume = min(music_volume, 1.0) if music_volume is not None else 0.18
        filter_complex = (
            f"[{audio_input_index}:a:0]volume=1.0,apad[a0];"
            f"[{music_input_index}:a:0]volume={music_volume:g},apad[a1];"
            "[a0][a1]amix=inputs=2:duration=longest:dropout_transition=0[a]"
        )
        cmd.extend(["-filter_complex", filter_complex, "-map", "0:v:0", "-map", "[a]"])
    elif segment["audio_path"]:
        cmd.extend(["-filter_complex", "[1:a:0]apad[a]", "-map", "0:v:0", "-map", "[a]"])
    else:
        cmd.extend(["-map", "0:v:0", "-map", "1:a:0"])

    cmd.extend(
        [
            "-t",
            f"{segment['duration']:.3f}",
            "-vf",
            f"tpad=stop_mode=clone:stop_duration={segment['duration']:.3f},scale=trunc(iw/2)*2:trunc(ih/2)*2,setsar=1,fps=24",
            "-c:v",
            "mpeg4",
            "-q:v",
            "5",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-shortest",
            str(output_path),
        ]
    )
    _run(cmd, logs)
    return output_path


def _concat_segments(
    segment_paths: List[Path],
    output_path: Path,
    *,
    srt_path: Optional[Path],
    work_dir: Path,
    ffmpeg_path: str,
    logs: List[str],
) -> None:
    concat_path = work_dir / "concat.txt"
    concat_path.write_text(
        "\n".join(f"file {shlex.quote(str(path))}" for path in segment_paths),
        encoding="utf-8",
    )
    cmd = [
        ffmpeg_path,
        "-y",
        "-hide_banner",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_path),
    ]
    if srt_path:
        cmd.extend(["-vf", f"subtitles=filename={_escape_filter_path(srt_path)}"])
    cmd.extend(
        [
            "-c:v",
            "mpeg4",
            "-q:v",
            "5",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )
    _run(cmd, logs)


def _write_srt(segments: List[dict], path: Path) -> Tuple[Path, bool]:
    entries = list(_subtitle_entries(segments))
    lines: List[str] = []
    for index, (start, end, text) in enumerate(entries, start=1):
        lines.extend(
            [
                str(index),
                f"{_format_srt_time(start)} --> {_format_srt_time(end)}",
                text,
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path, bool(entries)


def _subtitle_entries(segments: List[dict]) -> Iterable[Tuple[float, float, str]]:
    cursor = 0.0
    for segment in segments:
        duration = _positive_float(segment.get("duration_seconds")) or 0.0
        start = _positive_float(segment.get("start_seconds"))
        if start is None:
            start = cursor
        end = _positive_float(segment.get("end_seconds")) or (start + duration)
        subtitle_items = segment.get("subtitles")
        if isinstance(subtitle_items, list):
            for item in subtitle_items:
                if isinstance(item, dict) and str(item.get("text") or "").strip():
                    item_start = _positive_float(item.get("start_seconds")) or start
                    item_end = _positive_float(item.get("end_seconds")) or end
                    yield item_start, item_end, str(item["text"])
        else:
            subtitle = segment.get("subtitle") if isinstance(segment.get("subtitle"), dict) else {}
            text = str(subtitle.get("text") or "").strip()
            if text:
                item_start = _positive_float(subtitle.get("start_seconds")) or start
                item_end = _positive_float(subtitle.get("end_seconds")) or end
                yield item_start, item_end, text
        cursor = end


def _probe_media(path: Path, ffprobe_path: str) -> Dict[str, Any]:
    result = subprocess.run(
        [
            ffprobe_path,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    video_stream = next(
        (stream for stream in payload.get("streams", []) if stream.get("codec_type") == "video"),
        {},
    )
    duration = _positive_float(payload.get("format", {}).get("duration"))
    if duration is None:
        duration = _positive_float(video_stream.get("duration")) or 0.0
    return {
        "duration": duration,
        "width": int(video_stream.get("width") or 0),
        "height": int(video_stream.get("height") or 0),
    }


def _run(cmd: List[str], logs: List[str]) -> None:
    logs.append("$ " + " ".join(shlex.quote(part) for part in cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    _append_process_log(logs, result.stdout, result.stderr)
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode,
            cmd,
            output=result.stdout,
            stderr=result.stderr,
        )


def _append_process_log(logs: List[str], stdout: Optional[str], stderr: Optional[str]) -> None:
    for text in (stdout, stderr):
        if text:
            logs.extend(line for line in text.splitlines() if line.strip())


def _url_for_path(path: Path) -> str:
    resolved = path.resolve(strict=False)
    static_root = STATIC_ROOT.resolve(strict=False)
    try:
        relative = resolved.relative_to(static_root)
    except ValueError:
        return str(resolved)
    return f"/static/{relative.as_posix()}"


def _format_srt_time(seconds: float) -> str:
    total_ms = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{milliseconds:03d}"


def _positive_float(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _non_negative_float(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _safe_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")
    return cleaned or "workflow"


def _escape_filter_path(path: Path) -> str:
    return "'" + str(path).replace("\\", "\\\\").replace("'", "\\'") + "'"


def _tail(logs: List[str], line_count: int = 20) -> str:
    return "\n".join(logs[-line_count:])
