"""Compliance: AI-generated mp4 metadata + optional watermark toggle (default off)."""

import json
import shutil
import subprocess

import pytest

from app.core.legal import AI_GENERATED_METADATA_COMMENT, TERMS_VERSION
from app.services import publication_pipeline_render as render

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="ffmpeg required")


def _make_clip(path, color="red"):
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c={color}:s=160x120:d=1",
         "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-shortest",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(path)],
        check=True,
    )


def _comment(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", str(path)],
                         check=True, capture_output=True, text=True).stdout
    return json.loads(out)["format"].get("tags", {}).get("comment")


@pytest.fixture
def clips(tmp_path, monkeypatch):
    a, b = tmp_path / "a.mp4", tmp_path / "b.mp4"
    _make_clip(a), _make_clip(b, "blue")
    monkeypatch.setattr(render, "_resolve_local_media", lambda url: tmp_path / url.rsplit("/", 1)[-1])
    monkeypatch.setattr(render, "_url_for_path", lambda p: f"/static/exports/{p.name}")
    return tmp_path


def test_watermark_default_off(monkeypatch):
    monkeypatch.delenv("AI_WATERMARK_BURN_IN", raising=False)
    assert render.ai_watermark_burn_in_enabled() is False
    monkeypatch.setenv("AI_WATERMARK_BURN_IN", "true")
    assert render.ai_watermark_burn_in_enabled() is True
    assert "-vf" not in render._ai_output_args(False)
    assert "-vf" in render._ai_output_args(True)


def test_multi_episode_book_has_ai_comment(clips):
    url = render.assemble_whole_book_mp4(["/x/a.mp4", "/x/b.mp4"], book_id="bk1", output_dir=clips / "out")
    assert url.endswith("book-bk1.mp4")
    assert _comment(clips / "out" / "book-bk1.mp4") == AI_GENERATED_METADATA_COMMENT


def test_single_episode_book_is_remuxed_with_ai_comment(clips):
    url = render.assemble_whole_book_mp4(["/x/a.mp4"], book_id="bk2", output_dir=clips / "out")
    assert url.endswith("book-bk2.mp4")
    assert _comment(clips / "out" / "book-bk2.mp4") == AI_GENERATED_METADATA_COMMENT


def test_single_episode_falls_back_when_not_local(clips, monkeypatch):
    def boom(url):
        raise FileNotFoundError(url)

    monkeypatch.setattr(render, "_resolve_local_media", boom)
    assert render.assemble_whole_book_mp4(["https://cdn/x.mp4"], book_id="bk3", output_dir=clips / "o") == "https://cdn/x.mp4"


def test_terms_version_marked_draft():
    assert "draft" in TERMS_VERSION
