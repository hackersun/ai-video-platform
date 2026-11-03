"""P3: quality automation / shot scope fail-closed for publication pipelines."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.models.publication_pipeline import NovelPublicationPipeline
from app.models.series_production_run import SeriesProductionRun
from app.services.publication_pipeline_media import (
    PipelineMediaBlocked,
    resolve_shot_scope,
    run_media_quality_for_pipeline,
)


def _pipeline(**overrides) -> NovelPublicationPipeline:
    base = dict(
        id=str(uuid4()),
        user_id="u1",
        novel_id="n1",
        series_plan_version="v1",
        idempotency_key="k1",
        status="running",
        stage="run_media_quality",
        delivery={"visibility": "private"},
        media_policy={"shot_scope": "all_episode_shots"},
        gates={"require_commercial_gates": False},
        gate_summary={},
        episodes=[],
        pipeline_metadata={},
    )
    base.update(overrides)
    return NovelPublicationPipeline(**base)


def test_resolve_shot_scope_defaults_all_episode_shots():
    assert resolve_shot_scope({}, {}) == "all_episode_shots"


def test_commercial_rejects_anchor_shots_only():
    with pytest.raises(PipelineMediaBlocked) as exc:
        resolve_shot_scope(
            {"shot_scope": "anchor_shots_only", "allow_anchor_smoke_only": True},
            {"require_commercial_gates": True},
        )
    assert exc.value.code == "anchor_shots_only_forbidden"


def test_anchor_shots_only_requires_explicit_allow():
    with pytest.raises(PipelineMediaBlocked):
        resolve_shot_scope({"shot_scope": "anchor_shots_only"}, {"require_commercial_gates": False})


@pytest.mark.asyncio
async def test_run_media_blocks_on_trusted_multimodal(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.database import AsyncSessionLocal
    from init_db import init_db

    init_db()
    shot_id = f"shot-{uuid4()}"
    run = SeriesProductionRun(
        id=str(uuid4()),
        user_id="u-media",
        novel_id="n-media",
        series_plan_version="v1",
        idempotency_key=f"r-{uuid4()}",
        status="shots_ready",
        episodes=[
            {
                "episode_number": 1,
                "stage": "shots_ready",
                "canonical_ids": {"workflow_id": "wf-1", "shot_ids": [shot_id]},
            }
        ],
        gate_summary={},
        run_metadata={},
    )
    pipeline = _pipeline(user_id="u-media", novel_id="n-media")

    async def enter(db, current):
        current.status = "media_running"
        await db.commit()
        return current

    async def generate(db, **kwargs):
        return {
            "status": "completed",
            "selected_shot_ids": [shot_id],
            "quality_results": [],
            "error_code": "trusted_multimodal_evaluation_required",
        }

    async with AsyncSessionLocal() as db:
        db.add(run)
        await db.commit()
        with pytest.raises(PipelineMediaBlocked) as exc:
            await run_media_quality_for_pipeline(
                db,
                run,
                pipeline,
                enter_media_fn=enter,
                generate_fn=generate,
                list_shots_fn=None,
            )
        assert exc.value.code == "trusted_multimodal_evaluation_required"


@pytest.mark.asyncio
async def test_run_media_passes_when_completed_with_ready_tail() -> None:
    from app.core.database import AsyncSessionLocal
    from init_db import init_db

    init_db()
    shot_id = f"shot-{uuid4()}"
    run = SeriesProductionRun(
        id=str(uuid4()),
        user_id="u-media2",
        novel_id="n-media2",
        series_plan_version="v1",
        idempotency_key=f"r-{uuid4()}",
        status="shots_ready",
        episodes=[
            {
                "episode_number": 1,
                "stage": "shots_ready",
                "canonical_ids": {"workflow_id": "wf-1", "shot_ids": [shot_id]},
            }
        ],
        gate_summary={},
        run_metadata={},
    )
    pipeline = _pipeline(user_id="u-media2", novel_id="n-media2")

    async def enter(db, current):
        current.status = "media_running"
        await db.commit()
        return current

    async def generate(db, **kwargs):
        run.status = "completed"
        run.gate_summary = {"media_tail": {"result": "passed"}}
        await db.commit()
        return {
            "status": "completed",
            "selected_shot_ids": [shot_id],
            "quality_results": [{"shot_id": shot_id, "ready": True}],
        }

    async with AsyncSessionLocal() as db:
        db.add(run)
        await db.commit()
        updated = await run_media_quality_for_pipeline(
            db,
            run,
            pipeline,
            enter_media_fn=enter,
            generate_fn=generate,
        )
        assert updated.status == "completed"
        assert (updated.gate_summary or {}).get("media_tail", {}).get("result") == "passed"
