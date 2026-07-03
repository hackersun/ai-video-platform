from __future__ import annotations

import asyncio
import importlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app.services.publication_readiness import evaluate_publication_readiness


def _ffmpeg_has_filter(name: str) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-filters"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False
    needle = f" {name} "
    return any(needle in line for line in result.stdout.splitlines())


requires_ffmpeg = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="ffmpeg/ffprobe not installed",
)
requires_subtitles_filter = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not _ffmpeg_has_filter("subtitles"),
    reason="ffmpeg subtitles filter not installed",
)


def _renderer_module():
    return importlib.import_module("app.services.ffmpeg_local_renderer")


def _segment(index: int, video_url: str, start: float, duration: float, text: str = "") -> dict:
    return {
        "index": index,
        "start_seconds": start,
        "duration_seconds": duration,
        "end_seconds": start + duration,
        "video": {
            "url": video_url,
            "duration_seconds": duration,
        },
        "audio": {
            "url": None,
            "duration_seconds": None,
            "text": text,
        },
        "subtitle": {
            "enabled": bool(text),
            "text": text,
            "start_seconds": start,
            "end_seconds": start + duration,
        },
    }


def _manifest(*segments: dict) -> dict:
    return {
        "id": "render-test",
        "workflow_id": "workflow-test",
        "title": "Local Render Test",
        "segments": list(segments),
    }


def _make_video_only_clip(path: Path, color: str, duration: float = 0.6) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s=160x90:r=24:d={duration}",
            "-an",
            "-c:v",
            "mpeg4",
            "-q:v",
            "5",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
    )


def _probe(path: Path) -> dict:
    result = subprocess.run(
        [
            "ffprobe",
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
    return json.loads(result.stdout)


def _path_from_static_url(static_root: Path, url: str) -> Path:
    assert url.startswith("/static/")
    return static_root / url.removeprefix("/static/")


def test_missing_ffmpeg_returns_structured_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    renderer = _renderer_module()
    monkeypatch.setattr(renderer.shutil, "which", lambda _name: None)

    with pytest.raises(renderer.FFmpegLocalRenderError) as exc_info:
        asyncio.run(
            renderer.render_workflow_package(
                _manifest(_segment(1, "/static/missing.mp4", 0.0, 1.0)),
                output_dir=tmp_path,
                burn_subtitles=False,
            )
        )

    assert exc_info.value.detail["code"] == "ffmpeg_not_installed"


def test_remote_video_url_returns_structured_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    renderer = _renderer_module()
    monkeypatch.setattr(renderer.shutil, "which", lambda name: f"/usr/bin/{name}")

    with pytest.raises(renderer.FFmpegLocalRenderError) as exc_info:
        asyncio.run(
            renderer.render_workflow_package(
                _manifest(_segment(1, "https://cdn.example.com/video.mp4", 0.0, 1.0)),
                output_dir=tmp_path,
                burn_subtitles=False,
            )
        )

    assert exc_info.value.detail["code"] == "remote_url_unsupported"
    assert exc_info.value.detail["url"] == "https://cdn.example.com/video.mp4"


def test_missing_static_video_url_returns_structured_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    renderer = _renderer_module()
    static_root = tmp_path / "static"
    monkeypatch.setattr(renderer.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(renderer, "STATIC_ROOT", static_root)

    with pytest.raises(renderer.FFmpegLocalRenderError) as exc_info:
        asyncio.run(
            renderer.render_workflow_package(
                _manifest(_segment(1, "/static/fixtures/missing.mp4", 0.0, 1.0)),
                output_dir=static_root / "exports",
                burn_subtitles=False,
            )
        )

    assert exc_info.value.detail["code"] == "local_file_missing"
    assert exc_info.value.detail["url"] == "/static/fixtures/missing.mp4"


def test_missing_subtitles_filter_returns_structured_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    renderer = _renderer_module()
    static_root = tmp_path / "static"
    fixture_dir = static_root / "fixtures"
    fixture_dir.mkdir(parents=True)
    (fixture_dir / "clip.mp4").write_bytes(b"placeholder")
    monkeypatch.setattr(renderer.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(renderer, "STATIC_ROOT", static_root)
    monkeypatch.setattr(renderer, "_ffmpeg_has_filter", lambda _ffmpeg_path, _name: False, raising=False)

    with pytest.raises(renderer.FFmpegLocalRenderError) as exc_info:
        asyncio.run(
            renderer.render_workflow_package(
                _manifest(_segment(1, "/static/fixtures/clip.mp4", 0.0, 1.0, "Needs burn")),
                output_dir=static_root / "exports",
                burn_subtitles=True,
            )
        )

    assert exc_info.value.detail["code"] == "ffmpeg_subtitles_filter_unavailable"


@requires_ffmpeg
def test_render_two_segment_manifest_produces_playable_mp4(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    renderer = _renderer_module()
    static_root = tmp_path / "static"
    fixture_dir = static_root / "fixtures"
    fixture_dir.mkdir(parents=True)
    monkeypatch.setattr(renderer, "STATIC_ROOT", static_root)
    _make_video_only_clip(fixture_dir / "one.mp4", "red")
    _make_video_only_clip(fixture_dir / "two.mp4", "blue")

    result = asyncio.run(
        renderer.render_workflow_package(
            _manifest(
                _segment(1, "/static/fixtures/one.mp4", 0.0, 0.6, "First line"),
                _segment(2, "/static/fixtures/two.mp4", 0.6, 0.6, "Second line"),
            ),
            output_dir=static_root / "exports",
            burn_subtitles=False,
        )
    )

    output_path = _path_from_static_url(static_root, result["output_url"])
    subtitle_path = _path_from_static_url(static_root, result["subtitle_url"])
    metadata = _probe(output_path)

    assert output_path.exists()
    assert subtitle_path.read_text(encoding="utf-8").count("-->") == 2
    assert float(metadata["format"]["duration"]) == pytest.approx(1.2, abs=0.35)
    assert any(stream["codec_type"] == "audio" for stream in metadata["streams"])
    assert result["width"] == 160
    assert result["height"] == 90
    assert result["duration"] == pytest.approx(float(metadata["format"]["duration"]), abs=0.05)
    assert result["log_tail"]


@requires_subtitles_filter
def test_render_burns_subtitles_when_requested(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    renderer = _renderer_module()
    static_root = tmp_path / "static"
    fixture_dir = static_root / "fixtures"
    fixture_dir.mkdir(parents=True)
    monkeypatch.setattr(renderer, "STATIC_ROOT", static_root)
    _make_video_only_clip(fixture_dir / "subtitle.mp4", "green")

    result = asyncio.run(
        renderer.render_workflow_package(
            _manifest(_segment(1, "/static/fixtures/subtitle.mp4", 0.0, 0.6, "Burn this subtitle")),
            output_dir=static_root / "exports",
            burn_subtitles=True,
        )
    )

    output_path = _path_from_static_url(static_root, result["output_url"])
    subtitle_path = _path_from_static_url(static_root, result["subtitle_url"])

    assert output_path.exists()
    assert output_path.suffix == ".mp4"
    assert "Burn this subtitle" in subtitle_path.read_text(encoding="utf-8")


@requires_ffmpeg
def test_rendered_output_passes_publication_readiness(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    renderer = _renderer_module()
    static_root = tmp_path / "static"
    fixture_dir = static_root / "fixtures"
    fixture_dir.mkdir(parents=True)
    monkeypatch.setattr(renderer, "STATIC_ROOT", static_root)
    _make_video_only_clip(fixture_dir / "final.mp4", "yellow")

    result = asyncio.run(
        renderer.render_workflow_package(
            _manifest(_segment(1, "/static/fixtures/final.mp4", 0.0, 0.6)),
            output_dir=static_root / "exports",
            burn_subtitles=False,
        )
    )
    rendered = evaluate_publication_readiness(
        result["output_url"],
        {
            "render_status": "rendered",
            "render_backend": "ffmpeg_local",
            "output_kind": "final_video",
        },
    )
    preview = evaluate_publication_readiness(
        "/static/exports/review-preview.html",
        {
            "render_status": "rendered",
            "render_backend": "local_artifact_package",
            "output_kind": "preview_package",
        },
    )

    assert rendered["is_publishable"] is True
    assert rendered["output_kind"] == "final_video"
    assert preview["is_publishable"] is False
    assert preview["publication_blockers"][0]["code"] == "preview_package_not_publishable"
