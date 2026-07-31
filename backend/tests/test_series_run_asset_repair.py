from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.core.database import Base
from app.models import Chapter, Novel, Script, Shot, StoryEntity, Storyboard
from app.models.series_production_run import SeriesProductionRun
from app.services.default_prompt_skills import ensure_standard_prompt_skills
from app.services.story_entity_lifecycle import get_entity_review_status


@pytest_asyncio.fixture()
async def db_session() -> AsyncSession:
    database_path = Path(f"/tmp/series-asset-repair-{uuid4()}.db")
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()
    database_path.unlink(missing_ok=True)


def _legacy_auto_entity(*, user_id: str, novel_id: str, chapter_id: str, entity_type: str, name: str) -> StoryEntity:
    return StoryEntity(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id, chapter_id=chapter_id,
        first_seen_chapter_id=chapter_id, entity_type=entity_type, name=name,
        canonical_name=name, source="deterministic", is_approved=True, attributes={},
        extra_data={"lifecycle": {
            "status": "approved", "reason": "entity_extraction_v2:auto_approve",
        }},
    )


@pytest.mark.asyncio
async def test_repair_archives_noise_and_merges_exact_cross_chapter_assets(db_session: AsyncSession) -> None:
    from app.features.series_run_story_locks.application.asset_repair import repair_story_assets

    await ensure_standard_prompt_skills(db_session, commit=False)
    user_id, novel_id = str(uuid4()), str(uuid4())
    chapter_one = Chapter(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id, chapter_number=1,
        title="第一章", content="陆衡质问沈岚。沈岚背负青霄剑。",
    )
    chapter_two = Chapter(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id, chapter_number=2,
        title="第二章", content="沈岚以青霄剑斩断幻象。",
    )
    run = SeriesProductionRun(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id,
        series_plan_version="1", idempotency_key=str(uuid4()), status="shots_ready",
        episodes=[
            {"episode_number": 1, "chapter_ids": [chapter_one.id], "canonical_ids": {}},
            {"episode_number": 2, "chapter_ids": [chapter_two.id], "canonical_ids": {}},
        ],
        run_metadata={
            "story_locks": {"story_bible_id": "", "closure_hash": "old"},
            "reference_preparation": {
                "asset_id": "paid-reference-1", "asset_version": 1,
                "evidence_hash": "reference-evidence-1",
            },
        },
    )
    dirty_character = _legacy_auto_entity(
        user_id=user_id, novel_id=novel_id, chapter_id=chapter_one.id,
        entity_type="character", name="陆衡质",
    )
    dirty_prop = _legacy_auto_entity(
        user_id=user_id, novel_id=novel_id, chapter_id=chapter_two.id,
        entity_type="prop", name="她以青霄剑",
    )
    db_session.add_all([
        Novel(id=novel_id, user_id=user_id, title="五章玄幻"),
        chapter_one, chapter_two, run, dirty_character, dirty_prop,
    ])
    await db_session.commit()

    result = await repair_story_assets(db_session, run)

    rows = list((await db_session.scalars(select(StoryEntity).where(
        StoryEntity.novel_id == novel_id,
    ))).all())
    assert result["archived_noise_count"] >= 2
    assert result["cleared_shot_count"] == 0
    assert get_entity_review_status(dirty_character) == "archived"
    assert get_entity_review_status(dirty_prop) == "archived"
    assert any(item.name == "陆衡" and get_entity_review_status(item) == "approved" for item in rows)
    swords = [item for item in rows if item.canonical_name == "青霄剑"]
    assert len(swords) == 2
    assert sum(get_entity_review_status(item) == "approved" for item in swords) == 1
    assert sum(get_entity_review_status(item) == "archived" for item in swords) == 1
    assert "story_locks" not in run.run_metadata
    assert run.run_metadata["superseded_story_locks"][-1]["reason"] == "asset_normalization_repair"
    assert run.run_metadata["reference_preparation"]["asset_id"] == "paid-reference-1"
    assert result["reference_preserved"] is True


@pytest.mark.asyncio
async def test_repair_merges_unreviewed_character_candidate_into_unique_approved_character(
    db_session: AsyncSession,
) -> None:
    from app.features.series_run_story_locks.application.asset_repair import (
        _merge_exact_cross_chapter_assets,
    )

    user_id, novel_id = str(uuid4()), str(uuid4())
    chapter_one_id, chapter_two_id = str(uuid4()), str(uuid4())
    approved = StoryEntity(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id, chapter_id=chapter_two_id,
        first_seen_chapter_id=chapter_two_id, entity_type="character", name="顾清霜",
        canonical_name="顾清霜", appearance="固定服装与容貌", source="deterministic",
        is_approved=True,
        attributes={
            "approval_record": {"approved_by": user_id},
            "evidence_contract": {"status": "verified"},
        },
        extra_data={"lifecycle": {
            "status": "approved", "reason": "entity_extraction_v2:needs_review",
        }},
    )
    candidate = StoryEntity(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id, chapter_id=chapter_one_id,
        first_seen_chapter_id=chapter_one_id, entity_type="character", name="顾清霜",
        canonical_name="顾清霜", source="deterministic", is_approved=False,
        attributes={"evidence_contract": {"status": "verified"}},
        extra_data={
            "auto_decision": "needs_review",
            "lifecycle": {
                "status": "candidate", "reason": "entity_extraction_v2:needs_review",
            },
        },
    )
    run = SeriesProductionRun(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id,
        series_plan_version="1", idempotency_key=str(uuid4()), status="shots_ready",
        episodes=[
            {"episode_number": 1, "chapter_ids": [chapter_one_id], "canonical_ids": {}},
            {"episode_number": 2, "chapter_ids": [chapter_two_id], "canonical_ids": {}},
        ],
        run_metadata={},
    )
    db_session.add_all([approved, candidate, run])
    await db_session.commit()

    merged_count = await _merge_exact_cross_chapter_assets(db_session, run)

    assert merged_count == 1
    assert get_entity_review_status(approved) == "approved"
    assert get_entity_review_status(candidate) == "archived"
    assert candidate.attributes["merged_into_entity_id"] == approved.id
    assert candidate.extra_data["normalized_merge"]["canonical_entity_id"] == approved.id


@pytest.mark.asyncio
async def test_repair_restores_narrated_dialogue_speaker_on_existing_shot(db_session: AsyncSession) -> None:
    from app.features.series_run_story_locks.application.asset_repair import repair_story_assets

    await ensure_standard_prompt_skills(db_session, commit=False)
    user_id, novel_id, chapter_id = str(uuid4()), str(uuid4()), str(uuid4())
    chapter = Chapter(
        id=chapter_id, user_id=user_id, novel_id=novel_id, chapter_number=1,
        title="云台对质", content='沈岚握紧同一枚玄霜玉佩回答：“它不是灾祸，封印正在崩裂。”',
    )
    script = Script(id=str(uuid4()), user_id=user_id, novel_id=novel_id, title="剧本", content=chapter.content)
    storyboard = Storyboard(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id, script_id=script.id,
        title="分镜", content={}, shot_count=1,
    )
    shot = Shot(
        id=str(uuid4()), user_id=user_id, storyboard_id=storyboard.id, shot_number=1,
        dialogue="它不是灾祸，封印正在崩裂。", extra_data={"chapter_id": chapter_id},
    )
    run = SeriesProductionRun(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id, series_plan_version="1",
        idempotency_key=str(uuid4()), status="shots_ready",
        episodes=[{"episode_number": 1, "chapter_ids": [chapter_id],
                   "canonical_ids": {"shot_ids": [shot.id]}}],
        run_metadata={},
    )
    db_session.add_all([Novel(id=novel_id, user_id=user_id, title="玄幻"), chapter, script, storyboard, shot, run])
    await db_session.commit()

    result = await repair_story_assets(db_session, run)

    await db_session.refresh(shot)
    assert result["repaired_dialogue_count"] == 1
    assert shot.extra_data["dialogue_speaker"] == "沈岚"
    assert shot.extra_data["parsed_speaker"] == "沈岚"
    assert shot.extra_data["dialogue_spoken_text"] == "它不是灾祸，封印正在崩裂。"
