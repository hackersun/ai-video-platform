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
QUIET_MEAN_DB = -28.0
TARGET_MEAN_DB = -20.0
INAUDIBLE_MAX_DB = -45.0
MAX_GAIN_DB = 24.0


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


def _wrap_subtitle_line(value: str, limit: int = 16) -> list[str]:
    lines: list[str] = []
    remaining = value.strip()
    while len(remaining) > limit:
        cut = limit
        for index in range(limit - 1, max(7, limit - 6), -1):
            if remaining[index] in "，。！？；、,.!?;：:":
                cut = index + 1
                break
        lines.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    if remaining:
        lines.append(remaining)
    if len(lines) > 1 and len(lines[-1]) < 4:
        shift = min(4 - len(lines[-1]), max(0, len(lines[-2]) - 7))
        if shift:
            lines[-2], lines[-1] = lines[-2][:-shift].rstrip(), f"{lines[-2][-shift:]}{lines[-1]}"
    return lines


def _ass_text(value: Any) -> str:
    text = str(value or "").strip().replace("\\", "／").replace("{", "（").replace("}", "）")
    paragraphs = re.split(r"\r?\n", text)
    return r"\N".join(line for paragraph in paragraphs for line in _wrap_subtitle_line(paragraph))


def _write_ass(path: Path, segments: Iterable[dict[str, Any]]) -> int:
    events = []
    seen = set()
    for item in segments:
        text = _ass_text(item.get("text"))
        start, end = float(item.get("start_seconds") or 0), float(item.get("end_seconds") or 0)
        key = (round(start, 3), round(end, 3), text)
        if text and end > start and key not in seen:
            seen.add(key)
            events.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Default,,0,0,0,,{text}")
    if not events:
        raise NativeAudioSubtitleRenderError("subtitle_segments_missing", "没有可烧录的有效字幕片段")
    lines = [
        "[Script Info]", "ScriptType: v4.00+", "PlayResX: 720", "PlayResY: 1280", "WrapStyle: 0", "",
        "[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
        "Style: Default,PingFang SC,36,&H00FFFFFF,&H00FFFFFF,&H00000000,&H78000000,-1,0,0,0,100,100,0,0,1,3,1,2,46,46,72,1",
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


def _duration_seconds(source: Path) -> float:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise NativeAudioSubtitleRenderError("ffprobe_not_installed", "本机缺少 FFprobe，无法校准字幕时间")
    result = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(source)],
        check=True, capture_output=True, text=True, timeout=30,
    )
    return max(float(result.stdout.strip()), 0.0)


def _native_audio_activity_window(source: Path, duration: float) -> tuple[float, float]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise NativeAudioSubtitleRenderError("ffmpeg_not_installed", "本机缺少 FFmpeg，无法校准字幕时间")
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(source), "-af", "silencedetect=noise=-35dB:d=0.15", "-f", "null", "-"],
        capture_output=True, text=True, timeout=60,
    )
    output = f"{result.stdout}\n{result.stderr}"
    starts = [float(value) for value in re.findall(r"silence_start:\s*([0-9.]+)", output)]
    ends = [float(value) for value in re.findall(r"silence_end:\s*([0-9.]+)", output)]
    start = ends[0] if starts and starts[0] <= 0.05 and ends else 0.0
    trailing = [value for value in starts if value > start + 0.15]
    trailing_reaches_end = bool(ends and ends[-1] >= duration - 0.1)
    end = trailing[-1] if trailing and (trailing[-1] > (ends[-2] if len(ends) > 1 else -1)
                                           and (trailing_reaches_end or trailing[-1] > ends[-1])) else duration
    return max(0.0, min(start, duration)), max(0.0, min(end, duration))


def _native_audio_loudness(source: Path) -> dict[str, float]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise NativeAudioSubtitleRenderError("ffmpeg_not_installed", "本机缺少 FFmpeg，无法检测原生音频")
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(source), "-map", "0:a:0",
         "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True, timeout=60,
    )
    output = f"{result.stdout}\n{result.stderr}"
    values = {
        key: (-120.0 if raw == "-inf" else float(raw))
        for key, raw in re.findall(r"(mean|max)_volume:\s*(-inf|-?[0-9.]+)\s*dB", output)
    }
    if result.returncode != 0 or set(values) != {"mean", "max"}:
        raise NativeAudioSubtitleRenderError(
            "native_audio_track_missing", "视频没有可检测的原生音轨，不能标记为有声成片",
        )
    return {"mean_db": values["mean"], "max_db": values["max"]}


def align_subtitle_segments_to_native_audio(
    video_url: str, segments: Iterable[dict[str, Any]], *, force: bool = False,
) -> dict[str, Any]:
    """Align a single script-wide subtitle to the provider audio activity window."""
    values = [dict(item) for item in segments]
    source = _local_video_path(video_url)
    duration = _duration_seconds(source)
    if len(values) != 1 or duration <= 0:
        return {"segments": values, "aligned": False, "activity_window": None}
    item = values[0]
    start, end = float(item.get("start_seconds") or 0), float(item.get("end_seconds") or 0)
    if not force and (start > 0.05 or end < duration - 0.15):
        return {"segments": values, "aligned": False, "activity_window": None}
    active_start, active_end = _native_audio_activity_window(source, duration)
    if active_end - active_start < 0.25:
        return {"segments": values, "aligned": False, "activity_window": None}
    item.update(start_seconds=active_start, end_seconds=active_end)
    return {"segments": values, "aligned": True,
            "activity_window": {"start_seconds": active_start, "end_seconds": active_end}}


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
    input_loudness = _native_audio_loudness(source)
    if input_loudness["max_db"] < INAUDIBLE_MAX_DB:
        raise NativeAudioSubtitleRenderError(
            "native_audio_inaudible",
            "视频原生音轨接近静音，请只重试该镜头视频生成。",
            audio_loudness=input_loudness,
        )
    count = _write_ass(subtitle_path, segments)
    normalized = input_loudness["mean_db"] < QUIET_MEAN_DB
    gain_db = min(MAX_GAIN_DB, max(0.0, TARGET_MEAN_DB - input_loudness["mean_db"]))
    audio_args = (
        ["-af", f"volume={gain_db:.2f}dB,alimiter=limit=0.95", "-c:a", "aac", "-b:a", "192k"]
        if normalized else ["-c:a", "copy"]
    )
    command = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
        "-map", "0:v:0", "-map", "0:a?", "-vf", f"ass=filename='{_filter_path(subtitle_path)}'",
        "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
        *audio_args, "-movflags", "+faststart", str(output_path),
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
    output_loudness = _native_audio_loudness(output_path)
    return {
        "video_url": _static_url(output_path), "local_path": str(output_path),
        "subtitle_count": count, "audio_preserved": True,
        "audio_loudness": {
            "input_mean_db": input_loudness["mean_db"],
            "input_max_db": input_loudness["max_db"],
            "output_mean_db": output_loudness["mean_db"],
            "output_max_db": output_loudness["max_db"],
            "normalized": normalized,
            "gain_db": round(gain_db, 2) if normalized else 0.0,
        },
    }


__all__ = [
    "NativeAudioSubtitleRenderError", "align_subtitle_segments_to_native_audio",
    "burn_native_audio_subtitles",
]
