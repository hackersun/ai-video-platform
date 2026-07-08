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


def _make_audio_clip(path: Path, duration: float = 1.4) -> None:
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
            f"sine=frequency=440:duration={duration}:sample_rate=44100",
            "-c:a",
            "pcm_s16le",
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


def _stream_duration(metadata: dict, codec_type: str) -> float:
    stream = next(stream for stream in metadata["streams"] if stream["codec_type"] == codec_type)
    return float(stream["duration"])


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


def test_remote_video_error_redacts_signed_url_query(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    renderer = _renderer_module()
    monkeypatch.setattr(renderer.shutil, "which", lambda name: f"/usr/bin/{name}")

    with pytest.raises(renderer.FFmpegLocalRenderError) as exc_info:
        asyncio.run(
            renderer.render_workflow_package(
                _manifest(
                    _segment(
                        1,
                        "https://cdn.example.com/video.mp4?Expires=1&Signature=secret&OSSAccessKeyId=key",
                        0.0,
                        1.0,
                    )
                ),
                output_dir=tmp_path,
                burn_subtitles=False,
            )
        )

    detail_url = exc_info.value.detail["url"]
    assert detail_url == "https://cdn.example.com/video.mp4?Expires=<redacted>&Signature=<redacted>&OSSAccessKeyId=<redacted>"
    assert "secret" not in detail_url


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


def test_render_segment_mixes_music_under_primary_audio(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    renderer = _renderer_module()
    video_path = tmp_path / "clip.mp4"
    audio_path = tmp_path / "dialogue.wav"
    music_path = tmp_path / "bgm.wav"
    video_path.write_bytes(b"video")
    audio_path.write_bytes(b"dialogue")
    music_path.write_bytes(b"music")
    commands: list[list[str]] = []
    monkeypatch.setattr(renderer, "_run", lambda command, _logs: commands.append(command))

    renderer._render_segment(
        1,
        {
            "video_path": video_path,
            "audio_path": audio_path,
            "music_path": music_path,
            "music_volume": 0.16,
            "duration": 1.2,
        },
        tmp_path,
        "/usr/bin/ffmpeg",
        [],
    )

    command = commands[0]
    assert str(music_path) in command
    filter_index = command.index("-filter_complex") + 1
    assert "volume=0.16" in command[filter_index]
    assert "amix=inputs=2" in command[filter_index]


def test_prepare_segments_skips_unsupported_remote_music(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    renderer = _renderer_module()
    static_root = tmp_path / "static"
    fixture_dir = static_root / "fixtures"
    fixture_dir.mkdir(parents=True)
    video_path = fixture_dir / "clip.mp4"
    video_path.write_bytes(b"video")
    monkeypatch.setattr(renderer, "STATIC_ROOT", static_root)
    segment = _segment(1, "/static/fixtures/clip.mp4", 0.0, 1.0)
    segment["music"] = {"url": "https://cdn.example.com/music/suspense.mp3", "volume": 0.18}

    prepared = renderer._prepare_segments([segment], "/usr/bin/ffprobe")

    assert prepared[0]["music_path"] is None


def test_prepare_segments_keeps_local_music(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    renderer = _renderer_module()
    static_root = tmp_path / "static"
    fixture_dir = static_root / "fixtures"
    fixture_dir.mkdir(parents=True)
    video_path = fixture_dir / "clip.mp4"
    music_path = fixture_dir / "bgm.wav"
    video_path.write_bytes(b"video")
    music_path.write_bytes(b"music")
    monkeypatch.setattr(renderer, "STATIC_ROOT", static_root)
    segment = _segment(1, "/static/fixtures/clip.mp4", 0.0, 1.0)
    segment["music"] = {"url": "/static/fixtures/bgm.wav", "volume": 0.18}

    prepared = renderer._prepare_segments([segment], "/usr/bin/ffprobe")

    assert prepared[0]["music_path"] == music_path.resolve(strict=False)


def test_prepare_segments_downloads_remote_audio_to_work_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    renderer = _renderer_module()
    static_root = tmp_path / "static"
    fixture_dir = static_root / "fixtures"
    fixture_dir.mkdir(parents=True)
    video_path = fixture_dir / "clip.mp4"
    video_path.write_bytes(b"video")
    monkeypatch.setattr(renderer, "STATIC_ROOT", static_root)

    remote_audio_url = "https://minimax.example.com/audio/dialogue.mp3?Expires=1&Signature=secret"
    downloaded_audio_path = tmp_path / "remote-audio-001.mp3"

    def _fake_download_remote_audio(url: str, work_dir: Path, segment_index: int) -> Path:
        assert url == remote_audio_url
        assert work_dir == tmp_path
        assert segment_index == 1
        downloaded_audio_path.write_bytes(b"audio")
        return downloaded_audio_path

    monkeypatch.setattr(renderer, "_download_remote_audio", _fake_download_remote_audio, raising=False)
    segment = _segment(1, "/static/fixtures/clip.mp4", 0.0, 1.0)
    segment["audio"] = {"url": remote_audio_url, "duration_seconds": 1.0, "text": "远程配音"}

    prepared = renderer._prepare_segments([segment], "/usr/bin/ffprobe", tmp_path)

    assert prepared[0]["audio_path"] == downloaded_audio_path


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


@requires_ffmpeg
def test_render_extends_short_video_to_preserve_longer_dialogue_and_subtitle(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    renderer = _renderer_module()
    static_root = tmp_path / "static"
    fixture_dir = static_root / "fixtures"
    fixture_dir.mkdir(parents=True)
    monkeypatch.setattr(renderer, "STATIC_ROOT", static_root)
    _make_video_only_clip(fixture_dir / "short.mp4", "purple", duration=0.6)
    _make_audio_clip(fixture_dir / "dialogue.wav", duration=1.4)
    segment = _segment(1, "/static/fixtures/short.mp4", 0.0, 1.4, "Long dialogue")
    segment["audio"] = {
        "url": "/static/fixtures/dialogue.wav",
        "duration_seconds": 1.4,
        "text": "Long dialogue",
    }

    result = asyncio.run(
        renderer.render_workflow_package(
            _manifest(segment),
            output_dir=static_root / "exports",
            burn_subtitles=False,
        )
    )

    output_path = _path_from_static_url(static_root, result["output_url"])
    subtitle_path = _path_from_static_url(static_root, result["subtitle_url"])
    metadata = _probe(output_path)

    assert float(metadata["format"]["duration"]) == pytest.approx(1.4, abs=0.2)
    assert _stream_duration(metadata, "video") == pytest.approx(1.4, abs=0.2)
    assert _stream_duration(metadata, "audio") == pytest.approx(1.4, abs=0.2)
    assert "00:00:00,000 --> 00:00:01,400" in subtitle_path.read_text(encoding="utf-8")


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
