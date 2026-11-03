"""P4: commercial fail-closed gates + evidence summary for one-click publish."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import AsyncSessionLocal
from app.models.publication import Publication
from app.models.publication_pipeline import NovelPublicationPipeline
from app.models.series_production_run import SeriesProductionRun
from app.services.publication_pipeline_gates import (
    commercial_gates_required,
    evaluate_commercial_gates,
)
from app.services.publication_pipeline_orchestrator import PublicationPipelineOrchestrator
from init_db import init_db
from main import app


@pytest.fixture(scope="module", autouse=True)
def _init_database() -> None:
    init_db()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DEV_MODE", "true")
    monkeypatch.setenv("PUBLICATION_PIPELINE_ENABLED", "true")
    return TestClient(app)


def _headers(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


def test_evaluate_commercial_gates_requires_private_visibility():
    pipeline = NovelPublicationPipeline(
        id=str(uuid4()),
        user_id="u1",
        novel_id="n1",
        series_plan_version="v1",
        idempotency_key="k",
        status="running",
        stage="publication_gating",
        delivery={"visibility": "public"},
        media_policy={"shot_scope": "all_episode_shots"},
        gates={"require_commercial_gates": True},
        gate_summary={},
        final_video_url="/static/exports/a.mp4",
        episodes=[],
        pipeline_metadata={},
    )
    run = SeriesProductionRun(
        id=str(uuid4()),
        user_id="u1",
        novel_id="n1",
        series_plan_version="v1",
        idempotency_key="r",
        status="completed",
        gate_summary={"media_tail": {"result": "passed"}},
        budget_policy={"profile": "isolated_live_canary", "live_canary": True},
        episodes=[],
    )
    result = evaluate_commercial_gates(
        pipeline,
        run=run,
        readiness={"is_publishable": True, "output_kind": "final_video"},
    )
    assert result["passed"] is False
    assert any(b["code"] == "private_media_required" for b in result["blockers"])


def test_evaluate_commercial_gates_passes_with_evidence():
    pipeline = NovelPublicationPipeline(
        id=str(uuid4()),
        user_id="u1",
        novel_id="n1",
        series_plan_version="v1",
        idempotency_key="k",
        status="running",
        stage="publication_gating",
        delivery={"visibility": "private"},
        media_policy={"shot_scope": "all_episode_shots"},
        gates={"require_commercial_gates": True},
        gate_summary={"queue": {"attempt": 1}},
        final_video_url="/static/exports/a.mp4",
        series_run_id="run-1",
        episodes=[],
        pipeline_metadata={},
    )
    run = SeriesProductionRun(
        id="run-1",
        user_id="u1",
        novel_id="n1",
        series_plan_version="v1",
        idempotency_key="r",
        status="completed",
        gate_summary={"media_tail": {"result": "passed", "closed_at": "2026-11-03T00:00:00+00:00"}},
        budget_policy={"profile": "isolated_live_canary", "live_canary": True},
        episodes=[],
    )
    result = evaluate_commercial_gates(
        pipeline,
        run=run,
        readiness={"is_publishable": True, "output_kind": "final_video"},
    )
    assert result["passed"] is True
    evidence = result["evidence_summary"]
    assert evidence["pipeline_id"] == pipeline.id
    assert evidence["private_media"] is True
    assert evidence["publication_readiness"]["is_publishable"] is True


@pytest.mark.asyncio
async def test_orchestrator_blocks_publish_when_commercial_gates_fail(client: TestClient) -> None:
    user_id = f"p4-{uuid4()}"
    novel = client.post(
        "/api/v1/novels",
        json={"title": f"p4 {uuid4()}", "description": "gates"},
        headers=_headers(user_id),
    )
    assert novel.status_code == 201
    novel_id = novel.json()["id"]
    run_id = str(uuid4())
    pipeline_id = str(uuid4())
    final_url = "/static/exports/p4.mp4"

    async def fake_ensure(db, *, user_id, workflow_id, force=False, burn_subtitles=False):
        return {
            "workflow_id": workflow_id,
            "synthesis_job_id": "job-1",
            "render_status": "rendered",
            "render_backend": "ffmpeg_local",
            "output_url": final_url,
            "skipped": True,
        }

    created = {"n": 0}

    async def fake_create(db, **kwargs):
        created["n"] += 1
        pub = Publication(
            id=str(uuid4()),
            user_id=kwargs["user_id"],
            title=kwargs["title"],
            status="published",
            visibility=kwargs.get("visibility") or "private",
            video_url=kwargs["video_url"],
            export_url="/static/exports/x.json",
            artifact_path="/tmp/x.json",
            provider="local",
            publication_metadata={},
        )
        db.add(pub)
        await db.flush()
        return pub

    async with AsyncSessionLocal() as db:
        run = SeriesProductionRun(
            id=run_id,
            user_id=user_id,
            novel_id=novel_id,
            series_plan_version="plan-v1",
            idempotency_key=f"run-{uuid4()}",
            status="completed",
            gate_summary={"media_tail": {"result": "passed"}},
            episodes=[
                {
                    "episode_number": 1,
                    "stage": "shots_ready",
                    "canonical_ids": {"workflow_id": f"wf-{uuid4()}"},
                }
            ],
            budget_policy={},
        )
        db.add(run)
        pipeline = NovelPublicationPipeline(
            id=pipeline_id,
            user_id=user_id,
            novel_id=novel_id,
            series_run_id=run_id,
            series_plan_version="plan-v1",
            idempotency_key=f"idem-{uuid4()}",
            status="queued",
            stage="accepted",
            delivery={"mode": "whole_book_single_mp4", "visibility": "public"},
            media_policy={"shot_scope": "all_episode_shots"},
            gates={"require_commercial_gates": True},
            gate_summary={},
            episodes=[],
            pipeline_metadata={},
        )
        db.add(pipeline)
        await db.commit()

        orch = PublicationPipelineOrchestrator(
            ensure_episode_fn=fake_ensure,
            assemble_fn=lambda urls, **kw: final_url,
            create_publication_fn=fake_create,
        )
        result = await orch.execute(db, pipeline)
        await db.refresh(result)
        assert result.status == "blocked"
        assert result.blocker_code == "private_media_required"
        assert result.publication_id is None
        assert created["n"] == 0
        assert (result.gate_summary or {}).get("evidence_summary")


@pytest.mark.asyncio
async def test_orchestrator_succeeds_with_commercial_evidence(client: TestClient) -> None:
    user_id = f"p4ok-{uuid4()}"
    novel = client.post(
        "/api/v1/novels",
        json={"title": f"p4ok {uuid4()}", "description": "gates"},
        headers=_headers(user_id),
    )
    assert novel.status_code == 201
    novel_id = novel.json()["id"]
    run_id = str(uuid4())
    pipeline_id = str(uuid4())
    final_url = "/static/exports/p4ok.mp4"

    async def fake_ensure(db, *, user_id, workflow_id, force=False, burn_subtitles=False):
        return {
            "workflow_id": workflow_id,
            "synthesis_job_id": "job-1",
            "render_status": "rendered",
            "render_backend": "ffmpeg_local",
            "output_url": final_url,
            "skipped": True,
        }

    async def fake_create(db, **kwargs):
        assert kwargs.get("visibility") == "private"
        pub = Publication(
            id=str(uuid4()),
            user_id=kwargs["user_id"],
            title=kwargs["title"],
            status="published",
            visibility="private",
            video_url=kwargs["video_url"],
            export_url="/static/exports/ok.json",
            artifact_path="/tmp/ok.json",
            provider="local",
            publication_metadata={},
        )
        db.add(pub)
        await db.flush()
        return pub

    async with AsyncSessionLocal() as db:
        run = SeriesProductionRun(
            id=run_id,
            user_id=user_id,
            novel_id=novel_id,
            series_plan_version="plan-v1",
            idempotency_key=f"run-{uuid4()}",
            status="completed",
            gate_summary={"media_tail": {"result": "passed"}},
            episodes=[
                {
                    "episode_number": 1,
                    "stage": "shots_ready",
                    "canonical_ids": {"workflow_id": f"wf-{uuid4()}"},
                }
            ],
            budget_policy={"profile": "default"},
        )
        db.add(run)
        pipeline = NovelPublicationPipeline(
            id=pipeline_id,
            user_id=user_id,
            novel_id=novel_id,
            series_run_id=run_id,
            series_plan_version="plan-v1",
            idempotency_key=f"idem-{uuid4()}",
            status="queued",
            stage="accepted",
            delivery={"mode": "whole_book_single_mp4", "visibility": "private"},
            media_policy={"shot_scope": "all_episode_shots"},
            gates={"require_commercial_gates": True},
            gate_summary={"queue": {"attempt": 1}},
            episodes=[],
            pipeline_metadata={},
        )
        db.add(pipeline)
        await db.commit()
        orch = PublicationPipelineOrchestrator(
            ensure_episode_fn=fake_ensure,
            assemble_fn=lambda urls, **kw: final_url,
            create_publication_fn=fake_create,
        )
        result = await orch.execute(db, pipeline)
        await db.refresh(result)
        assert result.status == "succeeded"
        assert result.publication_id
        evidence = (result.gate_summary or {}).get("evidence_summary") or {}
        assert evidence.get("private_media") is True
        assert commercial_gates_required(result) is True
