"""Burn reviewed subtitles into a local native-audio video without replacing its audio."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import unquote, urlparse
from uuid import uuid4


BACKEND_ROOT = Path(__file__).resolve().parents[2]
STATIC_ROOT = BACKEND_ROOT / "static"


class NativeAudioSubtitleRenderError(RuntimeError):
    def __init__(self, code: str, message: str, **details: Any) -> None:
        self.detail = {"code": code, "message": message, **details}
        super().__init__(message)


def _local_video_path(video_url: str) -> Path:
    raw = str(video_url or "")
    parsed = urlparse(raw)
    if raw.startswith("/static/"):
        candidate = STATIC_ROOT / unquote(parsed.path).removeprefix("/static/")
    elif parsed.scheme == "file":
        candidate = Path(unquote(parsed.path))
    elif not parsed.scheme:
        candidate = Path(raw).expanduser()
    else:
        raise NativeAudioSubtitleRenderError(
            "subtitle_source_not_local",
            "字幕烧录要求先把供应商视频持久化到本地静态目录",
        )
    resolved = candidate.resolve(strict=False)
    if raw.startswith("/static/"):
        try:
            resolved.relative_to(STATIC_ROOT.resolve(strict=False))
        except ValueError as error:
            raise NativeAudioSubtitleRenderError(
                "subtitle_source_path_invalid", "字幕源视频路径越界",
            ) from error
    if not resolved.exists():
        raise NativeAudioSubtitleRenderError(
            "subtitle_source_missing", "字幕源视频不存在", path=str(resolved),
        )
    return resolved


def _ass_time(seconds: Any) -> str:
    value = max(float(seconds or 0), 0.0)
    hours = int(value // 3600)
    minutes = int((value % 3600) // 60)
    remainder = value % 60
    return f"{hours}:{minutes:02d}:{remainder:05.2f}"


def _ass_text(value: Any) -> str:
    text = str(value or "").strip().replace("\\", "／").replace("{", "（").replace("}", "）")
    return re.sub(r"\r?\n", r"\\N", text)


def _write_ass(path: Path, segments: Iterable[dict[str, Any]]) -> int:
    events = []
    for item in segments:
        text = _ass_text(item.get("text"))
        start, end = float(item.get("start_seconds") or 0), float(item.get("end_seconds") or 0)
        if text and end > start:
            events.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Default,,0,0,0,,{text}")
    if not events:
        raise NativeAudioSubtitleRenderError("subtitle_segments_missing", "没有可烧录的有效字幕片段")
    lines = [
        "[Script Info]", "ScriptType: v4.00+", "PlayResX: 960", "PlayResY: 960", "WrapStyle: 0", "",
        "[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
        "Style: Default,PingFang SC,42,&H00FFFFFF,&H00FFFFFF,&H00000000,&H78000000,-1,0,0,0,100,100,0,0,1,3,1,2,48,48,58,1",
        "", "[Events]", "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text", *events,
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return len(events)


def _filter_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "\\\\").replace(":", r"\:").replace("'", r"\'")


def _static_url(path: Path) -> str:
    try:
        relative = path.resolve().relative_to(STATIC_ROOT.resolve())
    except ValueError:
        return str(path.resolve())
    return f"/static/{relative.as_posix()}"


def burn_native_audio_subtitles(
    video_url: str,
    segments: Iterable[dict[str, Any]],
    *,
    output_root: Path | None = None,
) -> dict[str, Any]:
    """Render subtitles while mapping and stream-copying the provider audio track."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise NativeAudioSubtitleRenderError("ffmpeg_not_installed", "本机缺少 FFmpeg，无法烧录字幕")
    source = _local_video_path(video_url)
    target_root = (output_root or STATIC_ROOT / "generated" / "videos").resolve(strict=False)
    target_root.mkdir(parents=True, exist_ok=True)
    token = uuid4().hex
    subtitle_path = target_root / f"native-subtitles-{token}.ass"
    output_path = target_root / f"native-subtitled-{source.stem}-{token}.mp4"
    count = _write_ass(subtitle_path, segments)
    command = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
        "-map", "0:v:0", "-map", "0:a?", "-vf", f"ass=filename='{_filter_path(subtitle_path)}'",
        "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
        "-c:a", "copy", "-movflags", "+faststart", str(output_path),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.SubprocessError) as error:
        output_path.unlink(missing_ok=True)
        detail = (getattr(error, "stderr", "") or "")[-800:]
        raise NativeAudioSubtitleRenderError(
            "native_audio_subtitle_render_failed", "原生有声视频字幕烧录失败", error_tail=detail,
        ) from error
    finally:
        subtitle_path.unlink(missing_ok=True)
    return {
        "video_url": _static_url(output_path), "local_path": str(output_path),
        "subtitle_count": count, "audio_preserved": True,
    }


__all__ = ["NativeAudioSubtitleRenderError", "burn_native_audio_subtitles"]
