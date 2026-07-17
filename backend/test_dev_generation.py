from __future__ import annotations

import shutil
import subprocess

import pytest

from app.core import dev_generation


def test_dev_video_url_replaces_tiny_placeholder_with_playable_preview(tmp_path, monkeypatch) -> None:
    job_id = "dev-video-playback"
    filename = f"video-{job_id}.mp4"
    monkeypatch.setattr(dev_generation, "DEV_DIR", tmp_path)
    (tmp_path / filename).write_bytes(b"bad placeholder")

    url = dev_generation.dev_video_url(job_id)

    video_path = tmp_path / filename
    assert url == f"/static/dev/{filename}"
    assert video_path.stat().st_size >= dev_generation.DEV_VIDEO_MIN_BYTES
    assert video_path.read_bytes() == dev_generation.DEV_PREVIEW_VIDEO.read_bytes()


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="ffmpeg/ffprobe not installed",
)
def test_dev_video_url_honors_requested_duration_when_ffmpeg_available(tmp_path, monkeypatch) -> None:
    job_id = "dev-video-duration"
    filename = f"video-{job_id}.mp4"
    monkeypatch.setattr(dev_generation, "DEV_DIR", tmp_path)

    url = dev_generation.dev_video_url(job_id, duration_seconds=4)

    video_path = tmp_path / filename
    duration = float(subprocess.check_output([
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]))
    assert url == f"/static/dev/{filename}"
    assert video_path.stat().st_size >= dev_generation.DEV_VIDEO_MIN_BYTES
    assert 3.8 <= duration <= 4.3


def test_dev_image_url_creates_stable_local_png(tmp_path, monkeypatch) -> None:
    job_id = "dev-image-cover"
    monkeypatch.setattr(dev_generation, "DEV_DIR", tmp_path)

    url = dev_generation.dev_image_url(job_id, "Cover")

    image_path = tmp_path / f"image-{job_id}.png"
    assert url == f"/static/dev/image-{job_id}.png"
    assert image_path.exists()
    assert image_path.stat().st_size >= dev_generation.DEV_IMAGE_MIN_BYTES
    assert image_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
