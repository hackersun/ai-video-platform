"""Honesty tests for media_running → evaluating → completed tail FSM."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import AsyncSessionLocal
from app.models.series_production_run import SeriesProductionRun
from app.services.series_run_orchestrator import (
    SeriesRunOrchestrator,
    quality_gate_passed,
    real_media_success,
    transition_run,
)
from init_db import init_db
from main import app


@pytest.fixture(scope="module", autouse=True)
def _init_database() -> None:
    init_db()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DEV_MODE", "true")
    return TestClient(app)


def _headers(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


def _job(shot_id: str, *, artifact_id: str | None = "art-1", status: str = "succeeded", active: bool = True):
    return SimpleNamespace(
        shot_id=shot_id,
        status=status,
        is_active=active,
        extra_data={"artifact_id": artifact_id} if artifact_id else {},
        output_manifest_url=None,
        output_video_url=None,
        output_audio_url=None,
    )


async def _media_running_run(client: TestClient, *, artifact_ready: bool) -> tuple[str, str]:
    user_id = f"tail-{uuid4()}"
    novel = client.post(
        "/api/v1/novels",
        json={"title": f"tail {uuid4()}", "description": "tail fsm"},
        headers=_headers(user_id),
    )
    assert novel.status_code == 201, novel.text
    novel_id = novel.json()["id"]
    run_id = str(uuid4())
    reports = {"art-1": {"ready": True, "overall_readiness": "passed"}} if artifact_ready else {}
    async with AsyncSessionLocal() as db:
        run = SeriesProductionRun(
            id=run_id,
            user_id=user_id,
            novel_id=novel_id,
            series_plan_version="plan-v1",
            idempotency_key=f"tail-{uuid4()}",
            status="media_running",
            requested_stages=["scripts", "storyboards", "shots"],
            run_metadata={
                "media_preflight": {"ready": True},
                "anchor_quality_reports": reports,
            },
            gate_summary={},
            episodes=[{"episode_number": 1, "stage": "shots_ready"}],
        )
        db.add(run)
        await db.commit()
    return run_id, user_id


def test_real_media_success_requires_active_succeeded_artifact() -> None:
    assert real_media_success({"s1": _job("s1")}, ["s1"]) is True
    assert real_media_success({"s1": _job("s1", artifact_id=None)}, ["s1"]) is False
    assert real_media_success({"s1": _job("s1", status="failed")}, ["s1"]) is False
    assert real_media_success({}, ["s1"]) is False


def test_quality_gate_requires_ready_true_per_artifact() -> None:
    run = SeriesProductionRun(
        status="media_running",
        run_metadata={"anchor_quality_reports": {"art-1": {"ready": True}}},
    )
    ok, blocker = quality_gate_passed(run, ["s1"], {"s1": _job("s1")})
    assert ok is True and blocker is None

    run.run_metadata = {"anchor_quality_reports": {"art-1": {"ready": False, "overall_readiness": "trusted_multimodal_evaluation_required"}}}
    ok, blocker = quality_gate_passed(run, ["s1"], {"s1": _job("s1")})
    assert ok is False and blocker == "quality_gate_incomplete"


@pytest.mark.asyncio
async def test_close_media_tail_completes_when_quality_ready(client: TestClient) -> None:
    run_id, _ = await _media_running_run(client, artifact_ready=True)
    async with AsyncSessionLocal() as db:
        run = await db.get(SeriesProductionRun, run_id)
        await SeriesRunOrchestrator().close_media_tail(
            db,
            run,
            selected_shot_ids=["s1"],
            submission_id="sub-1",
            quality_results=[{"shot_id": "s1", "artifact_id": "art-1", "ready": True}],
            jobs_by_shot={"s1": _job("s1")},
        )
        await db.refresh(run)
        assert run.status == "completed"
        media_tail = (run.gate_summary or {}).get("media_tail") or {}
        assert media_tail.get("result") == "passed"
        assert media_tail.get("submission_id") == "sub-1"
        assert media_tail.get("blocker_code") is None


@pytest.mark.asyncio
async def test_submission_completed_without_quality_does_not_complete_run(client: TestClient) -> None:
    run_id, _ = await _media_running_run(client, artifact_ready=False)
    async with AsyncSessionLocal() as db:
        run = await db.get(SeriesProductionRun, run_id)
        # Simulate Submission already completed independently of Run status.
        await SeriesRunOrchestrator().close_media_tail(
            db,
            run,
            selected_shot_ids=["s1"],
            submission_id="sub-incomplete",
            quality_results=[{"shot_id": "s1", "artifact_id": "art-1", "ready": False}],
            jobs_by_shot={"s1": _job("s1")},
        )
        await db.refresh(run)
        assert run.status == "blocked"
        assert run.status != "completed"
        media_tail = (run.gate_summary or {}).get("media_tail") or {}
        assert media_tail.get("result") == "blocked"
        assert media_tail.get("blocker_code") == "quality_gate_incomplete"


@pytest.mark.asyncio
async def test_media_failure_marks_run_failed(client: TestClient) -> None:
    run_id, _ = await _media_running_run(client, artifact_ready=False)
    async with AsyncSessionLocal() as db:
        run = await db.get(SeriesProductionRun, run_id)
        await SeriesRunOrchestrator().close_media_tail(
            db, run, selected_shot_ids=["s1"], submission_id="sub-fail", media_failed=True,
        )
        await db.refresh(run)
        assert run.status == "failed"
        media_tail = (run.gate_summary or {}).get("media_tail") or {}
        assert media_tail.get("result") == "failed"
        assert media_tail.get("blocker_code") == "media_batch_submission_failed"


@pytest.mark.asyncio
async def test_close_media_tail_resumes_from_evaluating(client: TestClient) -> None:
    run_id, _ = await _media_running_run(client, artifact_ready=True)
    async with AsyncSessionLocal() as db:
        run = await db.get(SeriesProductionRun, run_id)
        transition_run(run, "evaluating")
        await db.commit()
        await SeriesRunOrchestrator().close_media_tail(
            db,
            run,
            selected_shot_ids=["s1"],
            submission_id="sub-resume",
            jobs_by_shot={"s1": _job("s1")},
        )
        await db.refresh(run)
        assert run.status == "completed"


@pytest.mark.asyncio
async def test_close_media_tail_is_idempotent_when_already_completed(client: TestClient) -> None:
    run_id, _ = await _media_running_run(client, artifact_ready=True)
    async with AsyncSessionLocal() as db:
        run = await db.get(SeriesProductionRun, run_id)
        await SeriesRunOrchestrator().close_media_tail(
            db, run, selected_shot_ids=["s1"], submission_id="sub-1", jobs_by_shot={"s1": _job("s1")},
        )
        await db.refresh(run)
        assert run.status == "completed"
        await SeriesRunOrchestrator().close_media_tail(
            db, run, selected_shot_ids=["s1"], submission_id="sub-1", jobs_by_shot={"s1": _job("s1")},
        )
        await db.refresh(run)
        assert run.status == "completed"



@pytest.mark.asyncio
async def test_generate_selected_wires_run_status_without_forging_completed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Submission may complete while Run stays blocked when quality is incomplete."""
    from app.features.series_anchor_generation import generation as gen
    from app.models.series_anchor_generation_submission import SeriesAnchorGenerationSubmission

    run_id, user_id = await _media_running_run(client, artifact_ready=False)
    shot = SimpleNamespace(id="s1", user_id=user_id, extra_data={})

    async def fake_preflight(db, run, *, native_audio=False):
        return {"ready": True, "snapshot_hash": "x"}

    async def fake_contexts(db, *, run, selected, workflow_for_shot, media):
        return [shot], {"wf": {"episode_number": 1}}, {"s1": {}}

    async def fake_submission(db, run, user_id, key):
        sub = SeriesAnchorGenerationSubmission(
            id=str(uuid4()), run_id=run.id, user_id=user_id,
            generation_key=key, status="pending", response_payload={},
        )
        db.add(sub)
        await db.flush()
        return sub, None, True

    async def fake_groups(db, *, user_id, selected, workflow_for_shot, selected_by_id, contexts):
        return {"wf-1": ["s1"]}, []

    async def fake_activate(db, *, run, submission, contexts, selected_by_id, is_new, media_preflight, native_audio):
        return None

    async def fake_evidence(db, run, batches):
        return None

    async def fake_quality(db, **kwargs):
        return [{"shot_id": "s1", "artifact_id": "art-1", "ready": False,
                 "overall_readiness": "trusted_multimodal_evaluation_required"}]

    async def fake_batch(workflow_id, shot_ids, video_config_id, audio_config_id):
        return {"workflow_id": workflow_id, "shot_ids": shot_ids, "media_job_ids": ["job-1"]}

    monkeypatch.setattr(gen, "_selected_ids", lambda *a, **k: ["s1"])
    monkeypatch.setattr(gen, "_preflight", fake_preflight)
    monkeypatch.setattr(gen, "_quality_contexts", fake_contexts)
    monkeypatch.setattr(gen, "_generation_key", lambda *a, **k: f"key-{uuid4()}")
    monkeypatch.setattr(gen, "_submission", fake_submission)
    monkeypatch.setattr(gen, "_generation_groups", fake_groups)
    monkeypatch.setattr(gen, "_activate", fake_activate)
    monkeypatch.setattr(gen, "record_anchor_skill_evidence", fake_evidence)
    monkeypatch.setattr(gen, "pending_source_response", lambda *a, **k: None)
    monkeypatch.setattr(gen, "_evaluate_quality", fake_quality)

    # close_media_tail needs jobs; inject via wrapping
    original_close = SeriesRunOrchestrator.close_media_tail

    async def close_with_jobs(self, db, run, **kwargs):
        kwargs.setdefault("jobs_by_shot", {"s1": _job("s1")})
        return await original_close(self, db, run, **kwargs)

    monkeypatch.setattr(SeriesRunOrchestrator, "close_media_tail", close_with_jobs)

    async with AsyncSessionLocal() as db:
        run = await db.get(SeriesProductionRun, run_id)
        response = await gen.generate_selected(
            db, run=run, user_id=user_id, shots=[shot], workflow_for_shot={"s1": "wf-1"},
            requested=["s1"], mode="smoke", generate_batch=fake_batch,
        )
        await db.refresh(run)
        assert response["status"] == "completed"
        assert response["run_status"] == "blocked"
        assert run.status == "blocked"
        assert run.status != "completed"
