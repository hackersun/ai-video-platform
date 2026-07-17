from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app.services.native_audio_subtitle_renderer import burn_native_audio_subtitles


FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")


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
