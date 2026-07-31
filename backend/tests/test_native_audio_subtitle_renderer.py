from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app.services.native_audio_subtitle_renderer import (
    _ass_text,
    align_subtitle_segments_to_native_audio,
    burn_native_audio_subtitles,
)


FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")


def _mean_volume(path: Path) -> float:
    result = subprocess.run(
        [FFMPEG, "-hide_banner", "-i", str(path), "-map", "0:a:0",
         "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True, check=False,
    )
    for line in result.stderr.splitlines():
        if "mean_volume:" in line:
            return float(line.split("mean_volume:", 1)[1].split("dB", 1)[0].strip())
    raise AssertionError("mean volume evidence missing")


def test_ass_text_wraps_long_chinese_dialogue_inside_vertical_safe_area() -> None:
    text = _ass_text("沈岚：此剑封天，不为成仙，只为后来者仍能看见人间灯火。")
    lines = text.split(r"\N")
    assert len(lines) >= 2
    assert all(len(line) <= 16 for line in lines)


def test_ass_text_does_not_leave_chinese_punctuation_on_its_own_line() -> None:
    lines = _ass_text("顾清霜：回声只能困住重复过去的人。").split(r"\N")

    assert lines[-1] == "去的人。"
    assert all(line not in "，。！？；、,.!?;：:" for line in lines)


@pytest.mark.skipif(not FFMPEG or not FFPROBE, reason="FFmpeg is required")
def test_burn_native_audio_subtitles_preserves_audio_stream(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    subprocess.run(
        [
            FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=blue:s=640x640:d=1.2",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=1.2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            "-shortest", str(source),
        ],
        check=True,
    )

    result = burn_native_audio_subtitles(
        str(source),
        [{"start_seconds": 0.1, "end_seconds": 1.0, "text": "明天正午，钟楼会倒塌。"}],
        output_root=tmp_path / "rendered",
    )

    output = Path(result["local_path"])
    assert output.exists() and output.stat().st_size > source.stat().st_size
    streams = json.loads(subprocess.run(
        [FFPROBE, "-v", "error", "-show_streams", "-of", "json", str(output)],
        check=True, capture_output=True, text=True,
    ).stdout)["streams"]
    assert {stream["codec_type"] for stream in streams} == {"video", "audio"}
    assert result["subtitle_count"] == 1
    assert result["audio_preserved"] is True


@pytest.mark.skipif(not FFMPEG or not FFPROBE, reason="FFmpeg is required")
def test_burn_native_audio_subtitles_normalizes_quiet_provider_audio(tmp_path: Path) -> None:
    source = tmp_path / "quiet-source.mp4"
    subprocess.run(
        [
            FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=blue:s=320x320:d=1.2",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=1.2",
            "-filter:a", "volume=0.08", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", str(source),
        ],
        check=True,
    )
    assert _mean_volume(source) < -28

    result = burn_native_audio_subtitles(
        str(source),
        [{"start_seconds": 0.1, "end_seconds": 1.0, "text": "声音必须清楚。"}],
        output_root=tmp_path / "rendered",
    )

    assert result["audio_loudness"]["normalized"] is True
    assert result["audio_loudness"]["input_mean_db"] < -28
    assert result["audio_loudness"]["output_mean_db"] >= -24
    assert _mean_volume(Path(result["local_path"])) >= -24


@pytest.mark.skipif(not FFMPEG or not FFPROBE, reason="FFmpeg is required")
def test_burn_native_audio_subtitles_deduplicates_identical_events(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    subprocess.run(
        [
            FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=blue:s=320x320:d=1",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            "-shortest", str(source),
        ],
        check=True,
    )
    segment = {"start_seconds": 0.1, "end_seconds": 0.9, "text": "不要重复。"}

    result = burn_native_audio_subtitles(
        str(source), [segment, dict(segment)], output_root=tmp_path / "rendered",
    )

    assert result["subtitle_count"] == 1


@pytest.mark.skipif(not FFMPEG or not FFPROBE, reason="FFmpeg is required")
def test_align_single_full_span_subtitle_to_detected_native_audio(tmp_path: Path) -> None:
    source = tmp_path / "delayed-speech.mp4"
    subprocess.run([
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "color=c=blue:s=320x320:d=1.4",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono:d=0.4",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=0.6",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono:d=0.4",
        "-filter_complex", "[1:a][2:a][3:a]concat=n=3:v=0:a=1[a]",
        "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest", str(source),
    ], check=True)

    result = align_subtitle_segments_to_native_audio(
        str(source), [{"start_seconds": 0, "end_seconds": 1.4, "text": "开始撤离。"}],
    )

    assert result["aligned"] is True
    assert 0.3 <= result["segments"][0]["start_seconds"] <= 0.55
    assert 0.9 <= result["segments"][0]["end_seconds"] <= 1.15
