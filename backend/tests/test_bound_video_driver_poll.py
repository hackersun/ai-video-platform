from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_snapshot_bound_video_job_polls_selected_driver_and_syncs(monkeypatch) -> None:
    from app.features.video_generation.application import driver_poll

    db = SimpleNamespace(commit=None)
    committed = False

    async def commit():
        nonlocal committed
        committed = True

    db.commit = commit
    job = SimpleNamespace(
        id="job-1", task_id="provider-task", status="pending", progress=10,
        video_url=None, cover_url=None, duration=4, resolution="768P",
        extra_data={"execution_snapshot_id": "snapshot-1", "config_model_id": "profile-1"},
    )
    context = SimpleNamespace(driver_context=object())
    captured = {}

    async def resolve(*_args, **kwargs):
        captured["profile"] = kwargs["explicit_profile_version_id"]
        return context

    async def poll(_registry, task_id, driver_context):
        captured.update(task_id=task_id, driver_context=driver_context)
        return SimpleNamespace(status="completed", output={"video_url": "https://cdn.test/video.mp4"})

    async def sync(_db, active_job, command):
        active_job.status = command.status_value
        active_job.progress = command.progress
        active_job.video_url = command.video_url

    monkeypatch.setattr(driver_poll, "resolve_generation_context", resolve)
    monkeypatch.setattr(driver_poll, "execute_poll", poll)
    monkeypatch.setattr(driver_poll, "sync_video_job_and_shot", sync)

    result = await driver_poll.poll_bound_video_job(db, "user-1", job)

    assert captured == {"profile": "profile-1", "task_id": "provider-task", "driver_context": context.driver_context}
    assert result["status"] == "succeeded"
    assert result["video_url"] == "https://cdn.test/video.mp4"
    assert committed is True
