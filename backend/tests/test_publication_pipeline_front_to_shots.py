"""P2: front-to-shots one-click via publication pipeline."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.chapter import Chapter
from app.models.publication import Publication
from app.models.publication_pipeline import NovelPublicationPipeline
from app.models.series_production_run import SeriesProductionRun
from app.services.publication_pipeline_front import (
    PipelineFrontBlocked,
    ensure_series_plan_for_pipeline,
    publication_run_idempotency_key,
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


async def _seed_novel_with_chapter(client: TestClient) -> tuple[str, str, str]:
    user_id = f"p2-{uuid4()}"
    novel = client.post(
        "/api/v1/novels",
        json={"title": f"p2 {uuid4()}", "description": "front"},
        headers=_headers(user_id),
    )
    assert novel.status_code == 201, novel.text
    novel_id = novel.json()["id"]
    chapter_id = str(uuid4())
    async with AsyncSessionLocal() as db:
        db.add(
            Chapter(
                id=chapter_id,
                user_id=user_id,
                novel_id=novel_id,
                title="第1章",
                content="正文",
                chapter_number=1,
            )
        )
        await db.commit()
    return user_id, novel_id, chapter_id


@pytest.mark.asyncio
async def test_ensure_plan_blocks_without_chapters(client: TestClient) -> None:
    user_id = f"p2-empty-{uuid4()}"
    novel = client.post(
        "/api/v1/novels",
        json={"title": f"empty {uuid4()}", "description": "x"},
        headers=_headers(user_id),
    )
    assert novel.status_code == 201
    novel_id = novel.json()["id"]
    async with AsyncSessionLocal() as db:
        with pytest.raises(PipelineFrontBlocked) as exc:
            await ensure_series_plan_for_pipeline(
                db, user_id=user_id, novel_id=novel_id, ensure=True
            )
        assert exc.value.code == "chapters_missing"


@pytest.mark.asyncio
async def test_orchestrator_front_to_shots_then_publish(client: TestClient) -> None:
    user_id, novel_id, chapter_id = await _seed_novel_with_chapter(client)
    pipeline_id = str(uuid4())
    final_url = "/static/exports/p2-final.mp4"
    run_id_box = {"id": None}

    async def fake_ensure_plan(db, *, user_id, novel_id, ensure, series_plan_version=None):
        return {
            "series_plan_version": "plan-p2",
            "episodes": [{"episode_number": 1, "chapter_ids": [chapter_id]}],
            "plan": {"version": "plan-p2", "episodes": [{"episode_number": 1, "chapter_ids": [chapter_id]}]},
        }

    async def fake_ensure_run(db, **kwargs):
        run = SeriesProductionRun(
            id=str(uuid4()),
            user_id=kwargs["user_id"],
            novel_id=kwargs["novel_id"],
            series_plan_version=kwargs["series_plan_version"],
            idempotency_key=publication_run_idempotency_key(kwargs["idempotency_key"]),
            status="created",
            requested_stages=["scripts", "storyboards", "shots"],
            episodes=[
                {
                    "episode_number": 1,
                    "stage": "created",
                    "chapter_ids": [chapter_id],
                    "canonical_ids": {},
                }
            ],
            gate_summary={},
            run_metadata={},
            budget_policy={},
            model_bindings={},
        )
        db.add(run)
        await db.commit()
        run_id_box["id"] = run.id
        return run

    async def fake_front(db, run, **kwargs):
        run.status = "shots_ready"
        run.episodes = [
            {
                "episode_number": 1,
                "stage": "shots_ready",
                "chapter_ids": [chapter_id],
                "canonical_ids": {"workflow_id": f"wf-{uuid4()}", "shot_ids": [f"shot-{uuid4()}"]},
            }
        ]
        await db.commit()
        return run

    async def fake_media(db, run, pipeline, **kwargs):
        run.status = "completed"
        run.gate_summary = {**(run.gate_summary or {}), "media_tail": {"result": "passed"}}
        await db.commit()
        return run

    async def fake_ensure_episode(db, *, user_id, workflow_id, force=False, burn_subtitles=False):
        return {
            "workflow_id": workflow_id,
            "synthesis_job_id": f"job-{workflow_id}",
            "render_status": "rendered",
            "render_backend": "ffmpeg_local",
            "output_url": final_url,
            "skipped": True,
        }

    async def fake_create(db, **kwargs):
        pub = Publication(
            id=str(uuid4()),
            user_id=kwargs["user_id"],
            title=kwargs["title"],
            status="published",
            visibility="private",
            video_url=kwargs["video_url"],
            export_url="/static/exports/p2.json",
            artifact_path="/tmp/exports/p2.json",
            provider="local",
            publication_metadata={},
        )
        db.add(pub)
        await db.flush()
        return pub

    async with AsyncSessionLocal() as db:
        pipeline = NovelPublicationPipeline(
            id=pipeline_id,
            user_id=user_id,
            novel_id=novel_id,
            series_run_id=None,
            series_plan_version="unspecified",
            idempotency_key=f"idem-{uuid4()}",
            status="queued",
            stage="accepted",
            delivery={"mode": "whole_book_single_mp4", "visibility": "private"},
            media_policy={"shot_scope": "all_episode_shots"},
            gates={"require_commercial_gates": False},
            gate_summary={},
            episodes=[],
            pipeline_metadata={"ensure_series_plan": True},
        )
        db.add(pipeline)
        await db.commit()

        orch = PublicationPipelineOrchestrator(
            ensure_plan_fn=fake_ensure_plan,
            ensure_run_fn=fake_ensure_run,
            run_front_fn=fake_front,
            run_media_fn=fake_media,
            ensure_episode_fn=fake_ensure_episode,
            assemble_fn=lambda urls, **kw: final_url,
            create_publication_fn=fake_create,
        )
        result = await orch.execute(db, pipeline)
        await db.refresh(result)
        assert result.status == "succeeded"
        assert result.stage == "succeeded"
        assert result.series_run_id == run_id_box["id"]
        assert result.publication_id
        assert result.final_video_url == final_url
        timings = (result.gate_summary or {}).get("stage_timings") or []
        stage_names = [t["stage"] for t in timings]
        assert "ensuring_plan" in stage_names
        assert "run_front_to_shots" in stage_names
        assert "run_media_quality" in stage_names


@pytest.mark.asyncio
async def test_create_api_queues_without_completed_run(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    user_id, novel_id, _chapter_id = await _seed_novel_with_chapter(client)

    async def fake_start(pipeline_id: str, user_id: str) -> bool:
        return True

    monkeypatch.setattr(
        "app.api.v1.endpoints.publication_pipelines.start_publication_pipeline_execution",
        fake_start,
    )
    resp = client.post(
        f"/api/v1/novels/{novel_id}/publication-pipelines",
        json={"idempotency_key": f"k-{uuid4()}", "ensure_series_plan": True},
        headers=_headers(user_id),
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["status"] == "queued"
    assert body["blocker_code"] is None
