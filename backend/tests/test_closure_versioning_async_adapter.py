"""SQLite integration contract for the production closure-v2 adapter."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models import Novel, StoryBible
from app.models.series_production_run import SeriesProductionRun


pytestmark = pytest.mark.asyncio


def _request(run_id: str, novel_id: str, user_id: str = "owner-1") -> dict:
    from app.features.series_run_story_locks.domain.closure_v2 import edge
    from app.features.series_run_story_locks.domain.scoped_reference import (
        build_scoped_reference,
    )
    content = "第一章来源文本"
    context = {
        "run_id": run_id, "series_run_id": run_id, "shot_id": "shot-1",
        "episode_number": 1, "episode_input_hash": "episode-input-1",
        "chapter_id": "chapter-1", "chapter_ids": ["chapter-1"],
        "script_id": "script-1", "storyboard_id": "board-1", "prompt": "镜头提示",
        "dialogue": "沈砚：别碰铜铃。", "visual_description": "雨夜城门",
        "source_text": content, "shot_text": f"{content} 沈砚：别碰铜铃。",
    }
    source = {
        "id": "character-1", "user_id": user_id, "novel_id": novel_id,
        "entity_type": "character", "canonical_name": "沈砚", "chapter_id": "chapter-1",
        "evidence_contract": {
            "status": "verified", "chapter_id": "chapter-1", "source_span": [0, 2],
            "content_hash": hashlib.sha256(content.encode()).hexdigest(),
            "source_excerpt": content[:2], "parser_version": "deterministic-extraction-v2",
        },
    }
    chapter = {
        "id": "chapter-1", "content": content, "content_length": len(content),
        "content_hash": hashlib.sha256(content.encode()).hexdigest(),
    }
    reference = build_scoped_reference(context=context, source=source, chapter=chapter)
    owned = {
        "user_id": user_id, "novel_id": novel_id, "run_id": run_id,
        "shot_id": "shot-1", "chapter_id": "chapter-1", "entity_type": "character",
        "current_context": context, "authoritative_chapters": {"chapter-1": chapter},
        "source_rows": [source], "canonical_histories": [], "merge_edges": [],
        "canonical_subjects": [source],
    }
    return {
        "closure_contract_version": "required_entity_closure_v2",
        "source_hash": "source-v2", "closure_hash": "closure-v2",
        "snapshot_hash": "snapshot-v2",
        "subjects": [{
            "entity_type": "character", "canonical_entity_id": "character-1",
            "canonical_identity_sha256": reference["canonical_identity_sha256"],
        }],
        "evidence_edges": [edge(reference, "character-1")],
        "scoped_inputs": [{"reference": reference, "owned": owned}],
        "candidate_counts": {"character": 1, "scene": 0, "prop": 0, "event": 0},
    }


def _run(run_id: str, novel_id: str) -> SeriesProductionRun:
    return SeriesProductionRun(
        id=run_id, user_id="owner-1", novel_id=novel_id,
        series_plan_version="plan-v1", idempotency_key=run_id,
        status="anchor_ready", requested_stages=[], model_bindings={}, budget_policy={},
        cost_summary={}, gate_summary={}, episodes=[{
            "episode_number": 1, "chapter_ids": ["chapter-1"],
            "story_bible_id": "bible-v1", "contract_version": "legacy",
        }],
        run_metadata={"story_locks": {"story_bible_id": "bible-v1"},
                      "shot_lineage": {"story_bible_id": "bible-v1"}},
        version=1,
    )


@pytest_asyncio.fixture
async def database(tmp_path: Path):
    path = tmp_path / "closure-v2.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as db:
        novel_id, run_id = str(uuid4()), str(uuid4())
        db.add(Novel(id=novel_id, user_id="owner-1", title="Four chapters"))
        db.add(StoryBible(
            id="bible-v1", user_id="owner-1", novel_id=novel_id, title="Legacy",
            extra_data={"series_story_lock": {
                "run_id": run_id, "version": 1,
                "closure_contract_version": "required_entity_closure_v1",
                "immutable_payload": {"legacy": True},
            }},
        ))
        db.add(_run(run_id, novel_id))
        await db.commit()
    yield sessions, run_id, novel_id
    await engine.dispose()
    assert path.exists()


async def _snapshot(sessions, run_id: str) -> dict:
    async with sessions() as db:
        run = await db.get(SeriesProductionRun, run_id)
        bibles = list((await db.scalars(select(StoryBible).order_by(StoryBible.id))).all())
        return {
            "version": run.version, "metadata": copy.deepcopy(run.run_metadata),
            "episodes": copy.deepcopy(run.episodes),
            "bibles": [(item.id, copy.deepcopy(item.extra_data)) for item in bibles],
        }


async def test_v1_to_v2_upgrade_persists_one_atomic_lineage(database):
    from app.features.series_run_story_locks.application.story_transaction import apply_closure_v2_transaction
    sessions, run_id, novel_id = database
    async with sessions() as db:
        result = await apply_closure_v2_transaction(db, run_id, _request(run_id, novel_id), 1)

    state = await _snapshot(sessions, run_id)
    assert result["closure_contract_version"] == "required_entity_closure_v2"
    assert result["story_bible_id"] != "bible-v1"
    assert state["version"] > 1
    assert len(state["bibles"]) == 2
    assert state["bibles"][0][1]["series_story_lock"]["immutable_payload"] == {"legacy": True}
    assert state["metadata"]["story_locks"]["story_bible_id"] == result["story_bible_id"]
    assert state["metadata"]["shot_lineage"]["closure_contract_version"] == "required_entity_closure_v2"
    assert state["episodes"][0]["story_bible_id"] == result["story_bible_id"]


@pytest.mark.parametrize("fail_at", [
    "after_supersede", "after_bible_insert", "after_run_pointer",
    "after_episode_contracts", "before_commit",
])
async def test_each_failure_point_rolls_back_bible_run_and_lineage(database, fail_at):
    from app.features.series_run_story_locks.application.story_transaction import apply_closure_v2_transaction
    sessions, run_id, novel_id = database
    before = await _snapshot(sessions, run_id)
    async with sessions() as db:
        with pytest.raises(RuntimeError, match="injected"):
            await apply_closure_v2_transaction(db, run_id, _request(run_id, novel_id), 1, fail_at)
    assert await _snapshot(sessions, run_id) == before


async def test_stale_expected_version_fails_without_partial_upgrade(database):
    from app.features.series_run_story_locks.application.story_transaction import apply_closure_v2_transaction
    from app.features.series_run_story_locks.repositories.closure_versioning_async import ClosureVersionDrift
    sessions, run_id, novel_id = database
    async with sessions() as stale:
        observed = await stale.get(SeriesProductionRun, run_id)
        observed_version = int(observed.version)
        await stale.rollback()
        async with sessions() as winner:
            await apply_closure_v2_transaction(winner, run_id, _request(run_id, novel_id), observed_version)
        before = await _snapshot(sessions, run_id)
        with pytest.raises(ClosureVersionDrift, match="version drift"):
            await apply_closure_v2_transaction(
                stale, run_id, {**_request(run_id, novel_id), "source_hash": "stale-write"}, observed_version)
    assert await _snapshot(sessions, run_id) == before


@pytest.mark.parametrize("boundary", ["run", "novel", "owner"])
async def test_internally_consistent_cross_boundary_request_is_zero_write(database, boundary):
    from app.features.series_run_story_locks.application.story_transaction import apply_closure_v2_transaction
    sessions, run_id, novel_id = database
    request = _request(
        "other-run" if boundary == "run" else run_id,
        "other-novel" if boundary == "novel" else novel_id,
        "other-owner" if boundary == "owner" else "owner-1",
    )
    before = await _snapshot(sessions, run_id)
    async with sessions() as db:
        with pytest.raises(ValueError, match="authority|owner|novel|run"):
            await apply_closure_v2_transaction(db, run_id, request, 1)
    assert await _snapshot(sessions, run_id) == before
