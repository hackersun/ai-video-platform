"""Multi-character novels must not fail-closed on archived supporting cast."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.core.database import Base
from app.features.series_run_story_locks.application.deterministic_acceptance import (
    reactivate_reused_archived_characters,
    seed_deterministic_local_mentions,
)
from app.features.series_run_story_locks.domain.approval_policy import (
    EntityFact,
    build_closure,
    validate_required_facts,
)
from app.features.series_run_story_locks.domain.errors import RequiredEntityBlocked
from app.models import Chapter, Novel, StoryEntity
from app.services.owned_shot_entity_refs import resolve_owned_shot_entity_context
from app.services.story_entity_lifecycle import (
    ARCHIVED,
    CANDIDATE,
    get_entity_review_status,
    set_entity_review_status,
)



@pytest_asyncio.fixture()
async def db_session() -> AsyncSession:
    database_path = Path(f"/tmp/multichar-reactivation-{uuid4()}.db")
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()
    database_path.unlink(missing_ok=True)


def _fact(*, entity_id: str, entity_type: str, lifecycle: str) -> EntityFact:
    return EntityFact(
        id=entity_id,
        entity_type=entity_type,
        user_id="user-1",
        novel_id="novel-1",
        chapter_id="chapter-1",
        lifecycle_status=lifecycle,
        evidence_status="verified",
        evidence_chapter_id="chapter-1",
        source_span=(0, 1),
        content_hash="a" * 64,
        expected_content_hash="a" * 64,
        chapter_content_length=100,
        parser_version="trusted-v1",
        conflicting_values=(),
        first_seen_chapter_id="chapter-1",
        identity={},
        relations=(),
        state_changes=(),
        tags=(),
        provenance_chapter_ids=(),
        canonical_identity_key=f"{entity_type}:{entity_id}",
        identity_keys=(f"{entity_type}:{entity_id}",),
    )


def test_validate_required_facts_rejects_archived_character() -> None:
    archived = _fact(entity_id="c-arch", entity_type="character", lifecycle="archived")
    ok = _fact(entity_id="c-ok", entity_type="character", lifecycle="candidate")
    closure = build_closure({"character": [archived.id, ok.id]}, [archived, ok])
    with pytest.raises(RequiredEntityBlocked) as raised:
        validate_required_facts(closure, [archived, ok])
    assert raised.value.code == "required_entity_state_invalid"


def test_validate_required_facts_accepts_candidate_multi_character() -> None:
    first = _fact(entity_id="c-1", entity_type="character", lifecycle="candidate")
    second = _fact(entity_id="c-2", entity_type="character", lifecycle="candidate")
    third = _fact(entity_id="c-3", entity_type="character", lifecycle="approved")
    closure = build_closure({"character": [first.id, second.id, third.id]}, [first, second, third])
    validate_required_facts(closure, [first, second, third])
    assert closure.required_counts["character"] == 3


@pytest.mark.asyncio
async def test_seed_keeps_distinct_supporting_cast_candidate(db_session: AsyncSession) -> None:
    user_id = str(uuid4())
    novel = Novel(id=str(uuid4()), user_id=user_id, title="雨夜来信")
    chapter = Chapter(
        id=str(uuid4()), user_id=user_id, novel_id=novel.id, chapter_number=1,
        title="一", content="林晚推开门。老陈说：那栋楼十年前就封了。",
    )
    protagonist = StoryEntity(
        id=str(uuid4()), user_id=user_id, novel_id=novel.id, chapter_id=chapter.id,
        first_seen_chapter_id=chapter.id, entity_type="character", name="主角",
        canonical_name="主角", source="deterministic", version=1, attributes={}, extra_data={},
    )
    lin = StoryEntity(
        id=str(uuid4()), user_id=user_id, novel_id=novel.id, chapter_id=chapter.id,
        first_seen_chapter_id=chapter.id, entity_type="character", name="林晚",
        canonical_name="林晚", source="deterministic", version=1, attributes={}, extra_data={},
    )
    chen = StoryEntity(
        id=str(uuid4()), user_id=user_id, novel_id=novel.id, chapter_id=chapter.id,
        first_seen_chapter_id=chapter.id, entity_type="character", name="老陈",
        canonical_name="老陈", source="deterministic", version=1, attributes={}, extra_data={},
    )
    for row in (lin, chen):
        merge = {"status": "merged_superseded", "canonical_entity_id": protagonist.id}
        row.attributes = {"merged_into_entity_id": protagonist.id}
        row.extra_data = {"deterministic_merge": dict(merge), "normalized_merge": dict(merge)}
        set_entity_review_status(row, ARCHIVED, changed_by=user_id, reason="merged_into_deterministic_protagonist")
    set_entity_review_status(protagonist, CANDIDATE, changed_by=user_id, reason="fixture")
    db_session.add_all([novel, chapter, protagonist, lin, chen])
    await db_session.commit()

    await seed_deterministic_local_mentions(
        db_session, user_id=user_id, novel_id=novel.id,
        episodes=[],  # character merge only; skip fixture scene/prop refs
        chapters_by_id={chapter.id: chapter},
        fixture_entities={"主角": protagonist},
    )
    await db_session.commit()
    await db_session.refresh(lin)
    await db_session.refresh(chen)
    await db_session.refresh(protagonist)

    assert get_entity_review_status(lin) == "candidate"
    assert "deterministic_merge" not in (lin.extra_data or {})
    assert get_entity_review_status(chen) == "archived"
    assert (chen.extra_data or {}).get("normalized_merge", {}).get("canonical_entity_id") == protagonist.id
    assert protagonist.canonical_name == "老陈"
    assert protagonist.aliases == ["老陈"]


@pytest.mark.asyncio
async def test_reactivate_reused_archived_distinct_character(db_session: AsyncSession) -> None:
    user_id = str(uuid4())
    novel = Novel(id=str(uuid4()), user_id=user_id, title="雨夜来信")
    chapter = Chapter(
        id=str(uuid4()), user_id=user_id, novel_id=novel.id, chapter_number=1,
        title="一", content="林晚站在雨里，苏明远没有说话。",
    )
    protagonist = StoryEntity(
        id=str(uuid4()), user_id=user_id, novel_id=novel.id, chapter_id=chapter.id,
        first_seen_chapter_id=chapter.id, entity_type="character", name="主角",
        canonical_name="老陈", source="deterministic", version=1, attributes={}, extra_data={},
    )
    lin = StoryEntity(
        id=str(uuid4()), user_id=user_id, novel_id=novel.id, chapter_id=chapter.id,
        first_seen_chapter_id=chapter.id, entity_type="character", name="林晚",
        canonical_name="林晚", source="deterministic", version=1,
        attributes={"merged_into_entity_id": protagonist.id},
        extra_data={"normalized_merge": {"status": "merged_superseded", "canonical_entity_id": protagonist.id}},
    )
    unused = StoryEntity(
        id=str(uuid4()), user_id=user_id, novel_id=novel.id, chapter_id=chapter.id,
        first_seen_chapter_id=chapter.id, entity_type="character", name="路人甲",
        canonical_name="路人甲", source="deterministic", version=1, attributes={}, extra_data={},
    )
    set_entity_review_status(protagonist, CANDIDATE, changed_by=user_id, reason="fixture")
    set_entity_review_status(lin, ARCHIVED, changed_by=user_id, reason="merged_into_deterministic_protagonist")
    set_entity_review_status(unused, ARCHIVED, changed_by=user_id, reason="merged_into_deterministic_protagonist")
    db_session.add_all([novel, chapter, protagonist, lin, unused])
    await db_session.commit()

    reactivated = await reactivate_reused_archived_characters(
        db_session, user_id=user_id, novel_id=novel.id, chapter_texts=[chapter.content],
    )
    await db_session.commit()
    await db_session.refresh(lin)
    await db_session.refresh(unused)
    assert lin.id in reactivated
    assert get_entity_review_status(lin) == "candidate"
    assert unused.id not in reactivated
    assert get_entity_review_status(unused) == "archived"


@pytest.mark.asyncio
async def test_discovery_emits_candidate_supporting_cast_not_archived_locals(
    db_session: AsyncSession,
) -> None:
    user_id = str(uuid4())
    novel = Novel(id=str(uuid4()), user_id=user_id, title="雨夜来信")
    chapter = Chapter(
        id=str(uuid4()), user_id=user_id, novel_id=novel.id, chapter_number=1,
        title="一", content="林晚推开门。老陈说：那栋楼十年前就封了。",
    )
    protagonist = StoryEntity(
        id=str(uuid4()), user_id=user_id, novel_id=novel.id, chapter_id=chapter.id,
        first_seen_chapter_id=chapter.id, entity_type="character", name="主角",
        canonical_name="老陈", source="deterministic", version=1, attributes={}, extra_data={},
    )
    lin = StoryEntity(
        id=str(uuid4()), user_id=user_id, novel_id=novel.id, chapter_id=chapter.id,
        first_seen_chapter_id=chapter.id, entity_type="character", name="林晚",
        canonical_name="林晚", source="deterministic", version=1, attributes={}, extra_data={},
    )
    local = StoryEntity(
        id=str(uuid4()), user_id=user_id, novel_id=novel.id, chapter_id=chapter.id,
        first_seen_chapter_id=chapter.id, entity_type="character", name="老陈·第1章提及",
        canonical_name="老陈", source="deterministic", version=1,
        attributes={"merged_into_entity_id": protagonist.id},
        extra_data={"normalized_merge": {"status": "merged_superseded", "canonical_entity_id": protagonist.id}},
    )
    set_entity_review_status(protagonist, CANDIDATE, changed_by=user_id, reason="fixture")
    set_entity_review_status(lin, CANDIDATE, changed_by=user_id, reason="fixture")
    set_entity_review_status(local, ARCHIVED, changed_by=user_id, reason="deterministic_chapter_local_mention")
    db_session.add_all([novel, chapter, protagonist, lin, local])
    await db_session.commit()

    discovered = await resolve_owned_shot_entity_context(
        db_session, user_id=user_id, novel_id=novel.id,
        chapter_ids=[chapter.id], as_of_chapter_id=chapter.id,
        source_text=chapter.content, shot_text=chapter.content,
    )
    char_ids = {item["entity_id"] for item in discovered["entity_refs"]["characters"]}
    assert lin.id in char_ids
    assert protagonist.id in char_ids
    assert local.id not in char_ids
