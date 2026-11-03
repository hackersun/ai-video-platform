"""P1 post-tail publish glue: completed Series Run → Publication."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.models.publication import Publication
from app.models.publication_pipeline import NovelPublicationPipeline
from app.models.series_production_run import SeriesProductionRun
from app.services.publication_export import PublicationNotReadyError, create_platform_publication
from app.services.publication_pipeline_orchestrator import PublicationPipelineOrchestrator
from app.services.publication_readiness import evaluate_publication_readiness
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


async def _seed_completed_run(client: TestClient, *, workflow_id: str | None = None) -> tuple[str, str, str]:
    user_id = f"pubpipe-{uuid4()}"
    novel = client.post(
        "/api/v1/novels",
        json={"title": f"pubpipe {uuid4()}", "description": "p1 glue"},
        headers=_headers(user_id),
    )
    assert novel.status_code == 201, novel.text
    novel_id = novel.json()["id"]
    run_id = str(uuid4())
    wf = workflow_id or f"wf-{uuid4()}"
    async with AsyncSessionLocal() as db:
        run = SeriesProductionRun(
            id=run_id,
            user_id=user_id,
            novel_id=novel_id,
            series_plan_version="plan-v1",
            idempotency_key=f"run-{uuid4()}",
            status="completed",
            requested_stages=["scripts", "storyboards", "shots"],
            gate_summary={"media_tail": {"result": "passed"}},
            episodes=[
                {
                    "episode_number": 1,
                    "stage": "shots_ready",
                    "canonical_ids": {"workflow_id": wf},
                }
            ],
        )
        db.add(run)
        await db.commit()
    return user_id, novel_id, run_id


@pytest.mark.asyncio
async def test_orchestrator_succeeds_with_final_mp4(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    user_id, novel_id, run_id = await _seed_completed_run(client)
    pipeline_id = str(uuid4())
    final_url = "/static/exports/final-ep1.mp4"

    async def fake_ensure(db, *, user_id, workflow_id, force=False, burn_subtitles=False):
        return {
            "workflow_id": workflow_id,
            "synthesis_job_id": f"job-{workflow_id}",
            "render_status": "rendered",
            "render_backend": "ffmpeg_local",
            "output_url": final_url,
            "skipped": True,
        }

    def fake_assemble(urls, *, book_id, output_dir=None):
        assert urls == [final_url]
        return final_url

    async def fake_create(db, **kwargs):
        assert kwargs["allow_preview_export"] is False
        assert kwargs["video_url"] == final_url
        pub = Publication(
            id=str(uuid4()),
            user_id=kwargs["user_id"],
            title=kwargs["title"],
            status=kwargs.get("status") or "published",
            visibility=kwargs.get("visibility") or "private",
            video_url=kwargs["video_url"],
            export_url=f"/static/exports/{uuid4()}.json",
            artifact_path=f"/tmp/exports/{uuid4()}.json",
            provider="local",
            publication_metadata={"pipeline_id": pipeline_id},
        )
        db.add(pub)
        await db.flush()
        return pub

    async with AsyncSessionLocal() as db:
        pipeline = NovelPublicationPipeline(
            id=pipeline_id,
            user_id=user_id,
            novel_id=novel_id,
            series_run_id=run_id,
            series_plan_version="plan-v1",
            idempotency_key=f"idem-{uuid4()}",
            status="queued",
            stage="accepted",
            delivery={"mode": "whole_book_single_mp4", "visibility": "private", "publish_status": "published"},
            gate_summary={},
            episodes=[],
            pipeline_metadata={},
        )
        db.add(pipeline)
        await db.commit()

        orch = PublicationPipelineOrchestrator(
            ensure_episode_fn=fake_ensure,
            assemble_fn=fake_assemble,
            create_publication_fn=fake_create,
        )
        result = await orch.execute(db, pipeline)
        await db.refresh(result)
        assert result.status == "succeeded"
        assert result.stage == "succeeded"
        assert result.final_video_url == final_url
        assert result.publication_id
        count = await db.scalar(select(func.count()).select_from(Publication).where(Publication.id == result.publication_id))
        assert count == 1


@pytest.mark.asyncio
async def test_orchestrator_blocks_preview_package(client: TestClient) -> None:
    user_id, novel_id, run_id = await _seed_completed_run(client)
    pipeline_id = str(uuid4())
    preview_url = "/static/exports/preview.html"

    async def fake_ensure(db, *, user_id, workflow_id, force=False, burn_subtitles=False):
        return {
            "workflow_id": workflow_id,
            "synthesis_job_id": "job-preview",
            "render_status": "rendered",
            "render_backend": "local_artifact_package",
            "output_url": preview_url,
            "skipped": True,
        }

    async with AsyncSessionLocal() as db:
        pipeline = NovelPublicationPipeline(
            id=pipeline_id,
            user_id=user_id,
            novel_id=novel_id,
            series_run_id=run_id,
            series_plan_version="plan-v1",
            idempotency_key=f"idem-{uuid4()}",
            status="queued",
            stage="accepted",
            delivery={"mode": "whole_book_single_mp4"},
            gate_summary={},
            episodes=[],
            pipeline_metadata={},
        )
        db.add(pipeline)
        await db.commit()
        orch = PublicationPipelineOrchestrator(
            ensure_episode_fn=fake_ensure,
            assemble_fn=lambda urls, **kw: urls[0],
            create_publication_fn=create_platform_publication,
        )
        result = await orch.execute(db, pipeline)
        await db.refresh(result)
        assert result.status == "blocked"
        assert result.blocker_code in {"final_video_missing", "preview_package_not_publishable"}
        assert result.publication_id is None
        pubs = (
            await db.execute(select(Publication).where(Publication.user_id == user_id))
        ).scalars().all()
        assert pubs == []


@pytest.mark.asyncio
async def test_orchestrator_idempotent_publication(client: TestClient) -> None:
    user_id, novel_id, run_id = await _seed_completed_run(client)
    pipeline_id = str(uuid4())
    final_url = "/static/exports/final-idem.mp4"
    created = {"n": 0}

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
        created["n"] += 1
        pub = Publication(
            id=str(uuid4()),
            user_id=kwargs["user_id"],
            title=kwargs["title"],
            status="published",
            visibility="private",
            video_url=kwargs["video_url"],
            export_url="/static/exports/x.json",
            artifact_path="/tmp/exports/x.json",
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
            series_run_id=run_id,
            series_plan_version="plan-v1",
            idempotency_key=f"idem-{uuid4()}",
            status="queued",
            stage="accepted",
            delivery={"mode": "whole_book_single_mp4"},
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
        first = await orch.execute(db, pipeline)
        assert first.status == "succeeded"
        pub_id = first.publication_id
        # Re-run should reuse publication_id without creating another
        first.stage = "publishing"
        first.status = "running"
        await db.commit()
        second = await orch.execute(db, first)
        assert second.status == "succeeded"
        assert second.publication_id == pub_id
        assert created["n"] == 1


@pytest.mark.asyncio
async def test_blocks_when_series_run_not_completed(client: TestClient) -> None:
    user_id = f"pubpipe-{uuid4()}"
    novel = client.post(
        "/api/v1/novels",
        json={"title": f"incomplete {uuid4()}", "description": "x"},
        headers=_headers(user_id),
    )
    assert novel.status_code == 201
    novel_id = novel.json()["id"]
    run_id = str(uuid4())
    async with AsyncSessionLocal() as db:
        db.add(
            SeriesProductionRun(
                id=run_id,
                user_id=user_id,
                novel_id=novel_id,
                series_plan_version="plan-v1",
                idempotency_key=f"run-{uuid4()}",
                status="shots_ready",
                episodes=[],
            )
        )
        pipeline = NovelPublicationPipeline(
            id=str(uuid4()),
            user_id=user_id,
            novel_id=novel_id,
            series_run_id=run_id,
            series_plan_version="plan-v1",
            idempotency_key=f"idem-{uuid4()}",
            status="queued",
            stage="accepted",
            delivery={},
            gate_summary={},
            episodes=[],
            pipeline_metadata={},
        )
        db.add(pipeline)
        await db.commit()
        result = await PublicationPipelineOrchestrator().execute(db, pipeline)
        assert result.status == "blocked"
        assert result.blocker_code == "series_run_not_completed"


def test_reject_external_platform_fields():
    from app.api.v1.endpoints.publication_pipelines import _reject_external_platforms
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        _reject_external_platforms({"delivery": {"douyin": {"account": "x"}}})
    assert exc.value.status_code == 400


def test_create_platform_publication_rejects_preview(tmp_path, monkeypatch):
    readiness = evaluate_publication_readiness(
        "/static/exports/x.html",
        {"render_status": "rendered", "render_backend": "local_artifact_package", "output_kind": "preview_package"},
    )
    assert readiness["is_publishable"] is False


@pytest.mark.asyncio
async def test_api_create_blocks_without_completed_run(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = f"pubpipe-api-{uuid4()}"
    novel = client.post(
        "/api/v1/novels",
        json={"title": f"api {uuid4()}", "description": "x"},
        headers=_headers(user_id),
    )
    assert novel.status_code == 201
    novel_id = novel.json()["id"]

    async def boom(*_a, **_k):
        raise RuntimeError("should not enqueue")

    monkeypatch.setattr(
        "app.api.v1.endpoints.publication_pipelines.start_publication_pipeline_execution",
        boom,
    )
    resp = client.post(
        f"/api/v1/novels/{novel_id}/publication-pipelines",
        json={"idempotency_key": f"k-{uuid4()}", "series_plan_version": "plan-v1"},
        headers=_headers(user_id),
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["status"] == "blocked"
    assert body["blocker_code"] == "series_run_not_completed"
    assert body["execution_status"] == "not_required"


@pytest.mark.asyncio
async def test_api_idempotent_create_with_enqueue(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    user_id, novel_id, run_id = await _seed_completed_run(client)
    enqueues: list[str] = []

    async def fake_start(pipeline_id: str, uid: str) -> bool:
        enqueues.append(pipeline_id)
        return True

    monkeypatch.setattr(
        "app.api.v1.endpoints.publication_pipelines.start_publication_pipeline_execution",
        fake_start,
    )
    key = f"k-{uuid4()}"
    payload = {
        "idempotency_key": key,
        "series_plan_version": "plan-v1",
        "series_run_id": run_id,
        "delivery": {"mode": "whole_book_single_mp4"},
    }
    first = client.post(
        f"/api/v1/novels/{novel_id}/publication-pipelines",
        json=payload,
        headers=_headers(user_id),
    )
    assert first.status_code == 202, first.text
    second = client.post(
        f"/api/v1/novels/{novel_id}/publication-pipelines",
        json=payload,
        headers=_headers(user_id),
    )
    assert second.status_code == 202, second.text
    assert first.json()["pipeline_id"] == second.json()["pipeline_id"]
    assert len(enqueues) >= 1
