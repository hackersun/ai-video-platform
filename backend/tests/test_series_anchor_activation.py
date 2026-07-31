from types import SimpleNamespace

import pytest

from app.features.series_anchor_generation import generation
from app.models import Shot


@pytest.mark.asyncio
async def test_activation_applies_shot_locks_after_media_transition(monkeypatch: pytest.MonkeyPatch) -> None:
    shot = Shot(id="shot-1", extra_data={})
    run = SimpleNamespace(id="run-1", status="anchor_ready", gate_summary={})
    submission = SimpleNamespace(status=None)
    commits = []

    class FakeDb:
        def add(self, _value):
            return None

        async def commit(self):
            commits.append(True)

        async def rollback(self):
            return None

    async def transition(_self, _db, transitioned_run, *, native_audio=False):
        shot.extra_data = {}
        transitioned_run.status = "media_running"

    monkeypatch.setattr(generation.SeriesRunOrchestrator, "enter_media_running", transition)
    context = {"asset_version_locks": [{"asset_id": "asset-1", "asset_version": 1}]}

    await generation._activate(
        FakeDb(), run=run, submission=submission, contexts={shot.id: context},
        selected_by_id={shot.id: shot}, is_new=False, native_audio=True,
    )

    assert shot.extra_data["production_context"] == context
    assert commits
