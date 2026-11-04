"""One-click publication pipeline: auto-prep, ffprobe metadata, rerun freshness."""
from __future__ import annotations

import asyncio
import shutil
import subprocess
from types import SimpleNamespace

import pytest

from app.services import publication_pipeline_prepare as prep
from app.services.publication_pipeline_media import PipelineMediaBlocked
from app.services.publication_pipeline_orchestrator import PublicationPipelineOrchestrator
from app.services.publication_pipeline_render import probe_final_video_metadata


def _run(**kw):
    base = dict(status="shots_ready", run_metadata={}, model_bindings={}, budget_policy={},
                user_id="u", novel_id="n", episodes=[])
    base.update(kw)
    return SimpleNamespace(**base)


def test_prepare_skips_runs_not_waiting_for_media():
    run = _run(status="media_running")
    assert asyncio.run(prep.prepare_run_for_media(None, run, None)) is run


def test_prepare_fails_closed_without_models_in_real_mode(monkeypatch):
    monkeypatch.setattr("app.services.deterministic_provider_fake.deterministic_provider_fake_enabled", lambda: False)
    with pytest.raises(PipelineMediaBlocked) as exc:
        asyncio.run(prep.prepare_run_for_media(None, _run(), None))
    assert exc.value.code == "models_not_configured"


def test_bindings_complete_requires_all_capabilities():
    caps = {c: {"config_id": "x"} for c in prep.REQUIRED_CAPABILITIES}
    assert prep._bindings_complete(_run(model_bindings={"capabilities": caps}))
    caps.pop("tts")
    assert not prep._bindings_complete(_run(model_bindings={"capabilities": caps}))


def test_preflight_codes_map_to_human_blockers():
    assert prep.PREFLIGHT_CODE_MAP["model_bindings_not_fresh"] == "models_not_configured"
    assert prep.PREFLIGHT_CODE_MAP["voice_selection_stale"] == "voice_selection_required"


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="ffmpeg required")
def test_probe_final_video_metadata_reads_real_duration_and_resolution(tmp_path):
    out = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=1280x720:d=2",
                    "-pix_fmt", "yuv420p", str(out)], check=True)
    meta = probe_final_video_metadata(str(out))
    assert meta["resolution"] == "720p" and meta["orientation"] == "landscape"
    assert 1.5 < meta["duration_seconds"] < 2.5


def test_probe_missing_file_is_best_effort():
    assert probe_final_video_metadata("/nonexistent/x.mp4") == {}
    assert probe_final_video_metadata(None) == {}


class _FakeDB:
    def __init__(self, chapters):
        self._chapters = chapters

    async def scalars(self, _stmt):
        return SimpleNamespace(all=lambda: self._chapters)


def test_completed_run_reused_only_when_chapter_inputs_unchanged():
    from app.services.publication_pipeline_front import _chapter_input_hash

    from datetime import datetime, timedelta

    ch = SimpleNamespace(id="c1", updated_at=datetime(2026, 1, 1))
    run = _run(episodes=[{"chapter_ids": ["c1"], "input_hash": _chapter_input_hash([ch])}])
    orch = PublicationPipelineOrchestrator()
    assert asyncio.run(orch._run_inputs_fresh(_FakeDB([ch]), run))
    ch.updated_at = ch.updated_at + timedelta(minutes=5)  # chapter edited
    assert not asyncio.run(orch._run_inputs_fresh(_FakeDB([ch]), run))
    assert not asyncio.run(orch._run_inputs_fresh(_FakeDB([]), run))
