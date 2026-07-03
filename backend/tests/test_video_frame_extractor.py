from __future__ import annotations

import importlib
import subprocess
from pathlib import Path

import pytest


def _extractor_module():
    return importlib.import_module("app.services.video_frame_extractor")


def test_missing_ffmpeg_returns_structured_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    extractor = _extractor_module()
    static_root = tmp_path / "static"
    clip = static_root / "fixtures" / "clip.mp4"
    clip.parent.mkdir(parents=True)
    clip.write_bytes(b"placeholder")

    monkeypatch.setattr(extractor, "STATIC_ROOT", static_root)
    monkeypatch.setattr(extractor.shutil, "which", lambda _name: None)

    with pytest.raises(extractor.VideoFrameExtractionError) as exc_info:
        extractor.extract_video_frames("/static/fixtures/clip.mp4", max_frames=3)

    assert exc_info.value.detail["code"] == "ffmpeg_not_installed"


def test_remote_video_url_returns_structured_error() -> None:
    extractor = _extractor_module()

    with pytest.raises(extractor.VideoFrameExtractionError) as exc_info:
        extractor.extract_video_frames("https://cdn.example.com/shot.mp4")

    assert exc_info.value.detail["code"] == "remote_url_unsupported"
    assert exc_info.value.detail["url"] == "https://cdn.example.com/shot.mp4"


def test_extract_video_frames_builds_static_urls_and_ffmpeg_command(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    extractor = _extractor_module()
    static_root = tmp_path / "static"
    clip = static_root / "generated" / "videos" / "shot.mp4"
    clip.parent.mkdir(parents=True)
    clip.write_bytes(b"placeholder")
    commands: list[list[str]] = []

    def fake_run(cmd: list[str], **_kwargs):
        commands.append(cmd)
        output_pattern = Path(cmd[-1])
        output_pattern.parent.mkdir(parents=True, exist_ok=True)
        (output_pattern.parent / "frame-001.jpg").write_bytes(b"one")
        (output_pattern.parent / "frame-002.jpg").write_bytes(b"two")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(extractor, "STATIC_ROOT", static_root)
    monkeypatch.setattr(extractor.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(extractor.subprocess, "run", fake_run)

    result = extractor.extract_video_frames(
        "/static/generated/videos/shot.mp4",
        fps=1.0,
        max_frames=3,
    )

    assert result["frame_count"] == 2
    assert result["frame_urls"] == [
        f"/static/generated/frames/{result['run_id']}/frame-001.jpg",
        f"/static/generated/frames/{result['run_id']}/frame-002.jpg",
    ]
    assert commands
    command = commands[0]
    assert command[:4] == ["/usr/bin/ffmpeg", "-y", "-hide_banner", "-loglevel"]
    assert "fps=1" in command
    assert "-frames:v" in command
    assert "3" in command
    assert str(clip) in command


def test_ffmpeg_failure_returns_structured_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    extractor = _extractor_module()
    static_root = tmp_path / "static"
    clip = static_root / "fixtures" / "clip.mp4"
    clip.parent.mkdir(parents=True)
    clip.write_bytes(b"placeholder")

    def fake_run(cmd: list[str], **_kwargs):
        raise subprocess.CalledProcessError(1, cmd, output="", stderr="bad video")

    monkeypatch.setattr(extractor, "STATIC_ROOT", static_root)
    monkeypatch.setattr(extractor.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(extractor.subprocess, "run", fake_run)

    with pytest.raises(extractor.VideoFrameExtractionError) as exc_info:
        extractor.extract_video_frames("/static/fixtures/clip.mp4")

    assert exc_info.value.detail["code"] == "ffmpeg_frame_extraction_failed"
    assert exc_info.value.detail["stderr"] == "bad video"
