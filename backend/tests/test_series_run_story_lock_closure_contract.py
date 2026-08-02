from __future__ import annotations

import hashlib
import json
from pathlib import Path
from itertools import permutations
from uuid import uuid4

import pytest
import pytest_asyncio
import httpx
from fastapi import FastAPI
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.core.database import Base
from app.core.time_utils import utc_now
from app.models import Chapter, Novel, Script, Shot, StoryBible, StoryEntity, StoryEntityMention, Storyboard, Workflow
from app.models.series_production_run import SeriesProductionRun
from app.services.story_entity_lifecycle import get_entity_review_status


ENTITY_COUNTS = {"character": 12, "scene": 14, "prop": 13, "event": 7}
REQUIRED_BY_ANCHOR = {
    1: {"character": 0, "scene": 0, "prop": 0, "event": 0},
    4: {"character": 1, "scene": 1, "prop": 1, "event": 1},
}


def test_story_lock_accepts_five_contiguous_episode_chapters() -> None:
    from app.features.series_run_story_locks.application.inspect_freshness import run_chapter_ids

    run = SeriesProductionRun(
        episodes=[
            {"episode_number": number, "chapter_ids": [f"chapter-{number}"]}
            for number in range(1, 6)
        ]
    )

    assert run_chapter_ids(run) == [f"chapter-{number}" for number in range(1, 6)]


def test_story_lock_rejects_non_contiguous_episode_order() -> None:
    from app.features.series_run_story_locks.application.inspect_freshness import (
        StoryLockFreshnessBlocked,
        run_chapter_ids,
    )

    run = SeriesProductionRun(episodes=[
        {"episode_number": 1, "chapter_ids": ["chapter-1"]},
        {"episode_number": 3, "chapter_ids": ["chapter-3"]},
    ])

    with pytest.raises(StoryLockFreshnessBlocked, match="episode_order_invalid"):
        run_chapter_ids(run)


def _public_api():
    from app.features.series_run_story_locks.public import (
        StoryLockPreparationBlocked,
        build_required_entity_closure,
        capture_story_lock_response,
        prepare_story_locks,
        safe_story_lock_error_detail,
    )

    return (
        StoryLockPreparationBlocked,
        build_required_entity_closure,
        capture_story_lock_response,
        prepare_story_locks,
        safe_story_lock_error_detail,
    )


def _jsonable(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    return value


async def _database_snapshot(db: AsyncSession) -> str:
    snapshot = {}
    for table in Base.metadata.sorted_tables:
        rows = (await db.execute(select(table))).all()
        normalized = [
            {key: _jsonable(value) for key, value in sorted(row._mapping.items())}
            for row in rows
        ]
        snapshot[table.name] = sorted(normalized, key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True))
    return json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


async def _post_actual_story_lock_route(
    db: AsyncSession,
    run: SeriesProductionRun,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
) -> httpx.Response:
    from app.api.v1.endpoints import series_runs
    from app.core.database import get_db
    from app.core.security import get_current_user_id

    async def fail(*_args, **_kwargs):
        raise error

    async def override_db():
        yield db

    monkeypatch.setattr(series_runs, "prepare_story_locks", fail)
    app = FastAPI()
    app.include_router(series_runs.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_id] = lambda: run.user_id
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        return await client.post(f"/api/v1/series-runs/{run.id}/prepare-story-locks")


@pytest_asyncio.fixture()
async def db_session() -> AsyncSession:
    database_path = Path(f"/tmp/task1-story-lock-{uuid4()}.db")
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()
    database_path.unlink(missing_ok=True)


async def _production_shaped_fixture(db: AsyncSession) -> tuple[SeriesProductionRun, list[Shot]]:
    user_id, novel_id = str(uuid4()), str(uuid4())
    now = utc_now()
    db.add(Novel(
        id=novel_id,
        user_id=user_id,
        title="四章 Story Lock 聚焦测试",
        description="隔离测试正文",
        extra_data={"visual_style": "二维国风动漫"},
        created_at=now,
        updated_at=now,
    ))
    chapters: list[Chapter] = []
    shots: list[Shot] = []
    episodes: list[dict] = []
    for number in range(1, 5):
        chapter = Chapter(
            id=str(uuid4()),
            user_id=user_id,
            novel_id=novel_id,
            title=f"第{number}章",
            content=f"第{number}章隔离测试内容",
            chapter_number=number,
            status="completed",
            created_at=now,
            updated_at=now,
        )
        script = Script(
            id=str(uuid4()),
            user_id=user_id,
            novel_id=novel_id,
            chapter_id=chapter.id,
            title=f"第{number}章剧本",
            content=chapter.content,
            status="draft",
            extra_data={},
        )
        storyboard = Storyboard(
            id=str(uuid4()),
            script_id=script.id,
            user_id=user_id,
            novel_id=novel_id,
            title=f"第{number}章分镜",
            content={},
            shot_count=1,
            status="draft",
        )
        shot = Shot(
            id=str(uuid4()),
            user_id=user_id,
            storyboard_id=storyboard.id,
            shot_number=1,
            prompt=f"第{number}章锚点",
            dialogue="",
            character_refs=[],
            extra_data={"episode_number": number, "chapter_id": chapter.id},
        )
        db.add_all([chapter, script, storyboard, shot])
        chapters.append(chapter)
        shots.append(shot)
        episodes.append({
            "episode_number": number,
            "chapter_ids": [chapter.id],
            "stage": "shots_ready",
            "canonical_ids": {"shot_ids": [shot.id]},
            "input_hash": f"{chapter.id}:{chapter.updated_at.isoformat()}",
        })

    entities: dict[str, list[StoryEntity]] = {kind: [] for kind in ENTITY_COUNTS}
    for entity_type, count in ENTITY_COUNTS.items():
        for index in range(count):
            chapter = chapters[0 if index == 0 else min(index % 4, 3)]
            entity = StoryEntity(
                id=str(uuid4()),
                user_id=user_id,
                novel_id=novel_id,
                chapter_id=chapter.id,
                first_seen_chapter_id=chapter.id,
                entity_type=entity_type,
                name=f"{entity_type}-{index}",
                canonical_name=f"{entity_type}-{index}",
                source="deterministic",
                is_approved=False,
                evidence=f"owned-chapter-{chapter.chapter_number}-span-{index}",
                attributes={
                    "evidence_contract": {
                        "chapter_id": chapter.id,
                        "source_span": [0, 1],
                        "content_hash": hashlib.sha256(chapter.content.encode()).hexdigest(),
                        "parser_version": "fixture-trusted-v1",
                        "status": "verified",
                    }
                },
                extra_data={"lifecycle": {"status": "candidate"}},
            )
            entities[entity_type].append(entity)
            db.add(entity)

    for episode_number, indexes in REQUIRED_BY_ANCHOR.items():
        shot = shots[episode_number - 1]
        references = {
            f"{entity_type}s": [{"entity_id": entities[entity_type][index].id}]
            for entity_type, index in indexes.items()
        }
        shot.extra_data = {**(shot.extra_data or {}), "entity_refs": references}
        shot.character_refs = references["characters"]

    run = SeriesProductionRun(
        id=str(uuid4()),
        user_id=user_id,
        novel_id=novel_id,
        series_plan_version="four-chapter-v1",
        idempotency_key=str(uuid4()),
        status="anchor_ready",
        current_episode_number=4,
        requested_stages=["media"],
        model_bindings={},
        budget_policy={},
        cost_summary={},
        gate_summary={},
        episodes=episodes,
        run_metadata={
            "selected_anchor_shot_ids": [shots[0].id, shots[3].id],
            "selected_anchor_mode": "smoke",
            "anchor_selection_revision": 1,
        },
        created_at=now,
        updated_at=now,
        version=1,
    )
    db.add(run)
    await db.commit()
    return run, shots


@pytest.mark.asyncio
@pytest.mark.parametrize("lifecycle_status", ["approved", "rejected", "archived", "merged"])
async def test_chapter_resync_preserves_existing_manual_entity_governance(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    lifecycle_status: str,
) -> None:
    from app.api.v1.endpoints import chapters as chapter_endpoints

    now = utc_now()
    user_id, novel_id, chapter_id = str(uuid4()), str(uuid4()), str(uuid4())
    novel = Novel(id=novel_id, user_id=user_id, title="人工实体保护", created_at=now, updated_at=now)
    chapter = Chapter(
        id=chapter_id, user_id=user_id, novel_id=novel_id, title="第一章",
        content="角色：沈砚。", chapter_number=1, created_at=now, updated_at=now,
    )
    approval = {"approved_by": user_id, "approved_at": now.isoformat(), "source": "manual"}
    entity = StoryEntity(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id, chapter_id=chapter_id,
        first_seen_chapter_id="original-first-seen", entity_type="character", name="沈砚",
        description="人工描述", appearance="黑发", visual_prompt="固定立绘",
        attributes={
            "approval_record": approval,
            "voice_profile": {"voice_id": "voice-manual"},
            "evidence_contract": {"status": "verified", "chapter_id": "stale-chapter"},
        },
        extra_data={"lifecycle": {"status": lifecycle_status, "reason": "manual-review"}},
        is_approved=lifecycle_status == "approved",
    )
    db_session.add_all([novel, chapter, entity])
    await db_session.commit()

    monkeypatch.setattr(chapter_endpoints, "extract_story_entities", lambda *_args, **_kwargs: [{
        "entity_type": "character", "name": "沈砚", "description": "自动描述",
        "attributes": {"evidence_contract": {"status": "verified", "chapter_id": chapter_id}},
        "evidence": "沈砚", "source": "deterministic", "confidence": 90,
    }])

    await chapter_endpoints.persist_story_context_from_chapter(db_session, user_id, novel, chapter)
    await db_session.flush()

    assert entity.extra_data["lifecycle"] == {"status": lifecycle_status, "reason": "manual-review"}
    assert entity.attributes["approval_record"] == approval
    assert entity.attributes["voice_profile"] == {"voice_id": "voice-manual"}
    assert entity.attributes["evidence_contract"]["chapter_id"] == chapter_id
    assert entity.first_seen_chapter_id == "original-first-seen"
    assert entity.is_approved is (lifecycle_status == "approved")


async def _persisted_owner_chain_fixture(
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[SeriesProductionRun, list[Shot]]:
    from app.api.v1.endpoints import chapters as chapter_endpoints
    from app.services.entity_evidence_contract import attach_chapter_evidence_contracts

    run, shots = await _production_shaped_fixture(db)
    await db.execute(delete(StoryEntity).where(StoryEntity.novel_id == run.novel_id))
    chapters = list((await db.scalars(
        select(Chapter).where(Chapter.novel_id == run.novel_id).order_by(Chapter.chapter_number)
    )).all())
    novel = await db.get(Novel, run.novel_id)
    chapter_items: dict[str, list[dict]] = {chapter.id: [] for chapter in chapters}
    for entity_type, count in ENTITY_COUNTS.items():
        for index in range(count):
            chapter_index = 0 if index == 0 else 3 if index == 1 else (index % 4)
            name = f"{entity_type}-{index}"
            chapter_items[chapters[chapter_index].id].append({
                "entity_type": entity_type, "name": name, "canonical_name": name,
                "description": f"owner-chain {name}", "evidence": name,
                "source": "deterministic", "confidence": 100, "attributes": {},
            })
    for chapter in chapters:
        chapter.content = "；".join(item["name"] for item in chapter_items[chapter.id])

    def extract(content, entity_types, *, source_chapter_id, source_chapter_index):
        items = [dict(item) for item in chapter_items[source_chapter_id] if item["entity_type"] in entity_types]
        attach_chapter_evidence_contracts(items, content=content, chapter_id=source_chapter_id)
        return items

    monkeypatch.setattr(chapter_endpoints, "extract_story_entities", extract)
    for chapter in chapters:
        await chapter_endpoints.persist_story_context_from_chapter(db, run.user_id, novel, chapter)
    await db.flush()
    entities = list((await db.scalars(select(StoryEntity).where(StoryEntity.novel_id == run.novel_id))).all())
    by_key = {(item.entity_type, item.name): item for item in entities}
    for episode_number, index in ((1, 0), (4, 1)):
        references = {
            f"{entity_type}s": [{"entity_id": by_key[(entity_type, f"{entity_type}-{index}")].id}]
            for entity_type in ENTITY_COUNTS
        }
        shot = shots[episode_number - 1]
        shot.extra_data = {**(shot.extra_data or {}), "entity_refs": references}
        shot.character_refs = references["characters"]
    await db.commit()
    persisted_chapters = list((await db.scalars(
        select(Chapter).where(Chapter.novel_id == run.novel_id).order_by(Chapter.chapter_number)
    )).all())
    for chapter in persisted_chapters:
        await db.refresh(chapter)
    episodes = [dict(item) for item in run.episodes]
    for episode, chapter, shot in zip(episodes, persisted_chapters, shots, strict=True):
        episode["input_hash"] = f"{chapter.id}:{chapter.updated_at.isoformat()}"
        storyboard = await db.get(Storyboard,shot.storyboard_id)
        script = await db.get(Script,storyboard.script_id)
        tag={"series_run_id":run.id,"episode_number":episode["episode_number"],
             "input_hash":episode["input_hash"]}
        script.extra_data={**(script.extra_data or {}),**tag}
        storyboard.content={**(storyboard.content or {}),**tag}
        workflow = Workflow(id=str(uuid4()),user_id=run.user_id,novel_id=run.novel_id,
            chapter_id=chapter.id,script_id=storyboard.script_id,storyboard_id=storyboard.id,
            title=f"第{episode['episode_number']}集生产工程",metadata_=tag)
        db.add(workflow)
        canonical=dict(episode.get("canonical_ids") or {})
        canonical.update(workflow_id=workflow.id,script_id=storyboard.script_id,
                         storyboard_id=storyboard.id,shot_ids=[shot.id])
        episode["canonical_ids"]=canonical
        shot.extra_data={**(shot.extra_data or {}),"series_run_id":run.id,
            "episode_number":episode["episode_number"],"input_hash":episode["input_hash"]}
    run.episodes = episodes
    await db.flush()
    from app.services.episode_production_service import create_or_resolve_shots_stage
    for episode in episodes:
        await create_or_resolve_shots_stage(db,run=run,episode=episode)
    await db.commit()
    return run, shots


@pytest.mark.asyncio
async def test_chapter_story_context_persists_approval_evidence_mention(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.v1.endpoints import chapters as chapter_endpoints

    now = utc_now()
    user_id, novel_id, chapter_id = str(uuid4()), str(uuid4()), str(uuid4())
    novel = Novel(id=novel_id, user_id=user_id, title="证据血缘", created_at=now, updated_at=now)
    chapter = Chapter(
        id=chapter_id, user_id=user_id, novel_id=novel_id, title="第一章",
        content="角色：沈砚。", chapter_number=1, created_at=now, updated_at=now,
    )
    db_session.add_all([novel, chapter])
    await db_session.commit()
    monkeypatch.setattr(chapter_endpoints, "extract_story_entities", lambda *_args, **_kwargs: [{
        "entity_type": "character", "name": "沈砚", "evidence": "沈砚",
        "source": "deterministic", "confidence": 95, "attributes": {},
    }])

    await chapter_endpoints.persist_story_context_from_chapter(
        db_session, user_id, novel, chapter,
    )
    await chapter_endpoints.persist_story_context_from_chapter(
        db_session, user_id, novel, chapter,
    )
    await db_session.flush()

    entity = await db_session.scalar(select(StoryEntity).where(StoryEntity.novel_id == novel_id))
    mentions = list((await db_session.scalars(
        select(StoryEntityMention).where(StoryEntityMention.entity_id == entity.id)
    )).all())
    assert len(mentions) == 1
    assert mentions[0].source_id == chapter_id
    assert mentions[0].evidence == "沈砚"
    assert mentions[0].confidence == 95


@pytest.mark.asyncio
async def test_four_chapter_persistence_owner_chain_locks_8_of_46_candidates(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run, _ = await _persisted_owner_chain_fixture(db_session, monkeypatch)
    _, _, _, prepare_story_locks, _ = _public_api()
    persisted_chapters = list((await db_session.scalars(
        select(Chapter).where(Chapter.novel_id == run.novel_id).order_by(Chapter.chapter_number)
    )).all())
    assert [item["input_hash"] for item in run.episodes] == [
        f"{chapter.id}:{chapter.updated_at.isoformat()}" for chapter in persisted_chapters
    ]

    result = await prepare_story_locks(db_session, run)

    assert result["status"] == "locked"
    assert result["entity_extraction_contract_version"] == "entity-extraction-v3"
    assert result["candidate_counts"] == ENTITY_COUNTS
    assert result["required_counts"] == {kind: 2 for kind in ENTITY_COUNTS}
    assert len(result["required_entity_ids"]) == 8
    assert result["unrelated_candidate_count"] == 38


@pytest.mark.asyncio
async def test_series_production_shot_owner_persists_chapter_owned_typed_refs(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.v1.endpoints import chapters as chapter_endpoints
    from app.services.entity_evidence_contract import attach_chapter_evidence_contracts
    from app.services.story_entity_lifecycle import APPROVED, set_entity_review_status
    from app.services.episode_production_service import (
        create_or_resolve_script_stage,
        create_or_resolve_shots_stage,
        create_or_resolve_storyboard_stage,
        create_or_resolve_workflow_stage,
    )

    run, old_shots = await _production_shaped_fixture(db_session)
    chapters = list((await db_session.scalars(
        select(Chapter).where(Chapter.novel_id == run.novel_id).order_by(Chapter.chapter_number)
    )).all())
    novel = await db_session.get(Novel, run.novel_id)
    storyboard_ids = [shot.storyboard_id for shot in old_shots]
    script_ids = list((await db_session.scalars(
        select(Storyboard.script_id).where(Storyboard.id.in_(storyboard_ids))
    )).all())
    await db_session.execute(delete(Shot).where(Shot.storyboard_id.in_(storyboard_ids)))
    await db_session.execute(delete(Storyboard).where(Storyboard.id.in_(storyboard_ids)))
    await db_session.execute(delete(Script).where(Script.id.in_(script_ids)))
    await db_session.execute(delete(StoryEntity).where(StoryEntity.novel_id == run.novel_id))

    chapter_items: dict[str, list[dict]] = {}
    for chapter in chapters:
        chapter_items[chapter.id] = [{
            "entity_type": entity_type,
            "name": f"chapter-{chapter.chapter_number}-{entity_type}",
            "canonical_name": f"chapter-{chapter.chapter_number}-{entity_type}",
            "evidence": f"chapter-{chapter.chapter_number}-{entity_type}",
            "source": "deterministic", "confidence": 100, "attributes": {},
        } for entity_type in ENTITY_COUNTS]
        chapter.content = "；".join(item["name"] for item in chapter_items[chapter.id])

    def extract(content, entity_types, *, source_chapter_id, source_chapter_index):
        items = [dict(item) for item in chapter_items[source_chapter_id] if item["entity_type"] in entity_types]
        attach_chapter_evidence_contracts(items, content=content, chapter_id=source_chapter_id)
        return items

    monkeypatch.setattr(chapter_endpoints, "extract_story_entities", extract)
    for chapter in chapters:
        await chapter_endpoints.persist_story_context_from_chapter(
            db_session, run.user_id, novel, chapter,
        )
    await db_session.flush()
    persisted_entities = list((await db_session.scalars(
        select(StoryEntity).where(StoryEntity.novel_id == run.novel_id)
    )).all())
    for entity in persisted_entities:
        set_entity_review_status(
            entity, APPROVED, changed_by=run.user_id, reason="test production-visible fixture",
        )
    await db_session.flush()

    episodes = [dict(item, canonical_ids={}) for item in run.episodes]
    for episode, chapter in zip(episodes, chapters, strict=True):
        await db_session.refresh(chapter)
        episode["input_hash"] = f"{chapter.id}:{chapter.updated_at.isoformat()}"
        canonical: dict[str, object] = {}
        for stage in (
            create_or_resolve_workflow_stage,
            create_or_resolve_script_stage,
            create_or_resolve_storyboard_stage,
            create_or_resolve_shots_stage,
        ):
            episode["canonical_ids"] = canonical
            canonical.update(await stage(db_session, run=run, episode=episode))
        episode["canonical_ids"] = canonical
    run.episodes = episodes
    await db_session.commit()

    anchor_shots = [
        await db_session.get(Shot, episodes[index]["canonical_ids"]["shot_ids"][0])
        for index in (0, 3)
    ]
    for shot, chapter in zip(anchor_shots, (chapters[0], chapters[3]), strict=True):
        refs = (shot.extra_data or {}).get("entity_refs") or {}
        assert {key: len(refs.get(key) or []) for key in ("characters", "scenes", "props", "events")} == {
            "characters": 1, "scenes": 1, "props": 1, "events": 1,
        }
        assert all(ref["chapter_id"] == chapter.id for values in refs.values() for ref in values)

    candidates = list((await db_session.scalars(
        select(StoryEntity).where(StoryEntity.novel_id == run.novel_id)
    )).all())
    _, build_required_entity_closure, _, _, _ = _public_api()
    closure = build_required_entity_closure(selected_shots=anchor_shots, candidates=candidates)
    assert closure["required_counts"] == {kind: 2 for kind in ENTITY_COUNTS}
    assert len(closure["required_entity_ids"]) == 8
    assert closure["unrelated_candidate_count"] == 8
    run.run_metadata = {
        **(run.run_metadata or {}),
        "selected_anchor_shot_ids": [shot.id for shot in anchor_shots],
        "selected_anchor_mode": "smoke",
        "anchor_selection_revision": 2,
    }
    await db_session.commit()
    _, _, _, prepare_story_locks, _ = _public_api()
    locked = await prepare_story_locks(db_session, run)
    assert locked["status"] == "locked"
    assert locked["required_counts"] == {kind: 2 for kind in ENTITY_COUNTS}

    first_shot = anchor_shots[0]
    first_shot.extra_data = {**(first_shot.extra_data or {}), "entity_refs": {}}
    first_shot.character_refs = []
    await db_session.flush()
    await create_or_resolve_shots_stage(db_session, run=run, episode=episodes[0])
    assert all(((first_shot.extra_data or {}).get("entity_refs") or {}).get(key) for key in (
        "characters", "scenes", "props", "events",
    ))

    second_shot = anchor_shots[1]
    preserved = {"characters": [{"entity_id": "manual-preserved", "entity_type": "character"}]}
    second_shot.extra_data = {**(second_shot.extra_data or {}), "entity_refs": preserved}
    await db_session.flush()
    await create_or_resolve_shots_stage(db_session, run=run, episode=episodes[3])
    assert second_shot.extra_data["entity_refs"] == preserved


@pytest.mark.asyncio
async def test_owned_shot_resolver_rejects_ambiguous_and_cross_chapter_entities(
    db_session: AsyncSession,
) -> None:
    from app.services.owned_shot_entity_refs import resolve_owned_shot_entity_context

    now = utc_now()
    user_id, novel_id = str(uuid4()), str(uuid4())
    allowed = Chapter(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id, title="第一章",
        content="双生者进入跨章场景", chapter_number=1, created_at=now, updated_at=now,
    )
    foreign = Chapter(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id, title="第二章",
        content="跨章场景", chapter_number=2, created_at=now, updated_at=now,
    )
    db_session.add(Novel(id=novel_id, user_id=user_id, title="严格映射", created_at=now, updated_at=now))
    db_session.add_all([allowed, foreign])
    for suffix in ("a", "b"):
        db_session.add(StoryEntity(
            id=str(uuid4()), user_id=user_id, novel_id=novel_id, chapter_id=allowed.id,
            first_seen_chapter_id=allowed.id, entity_type="character", name=f"双生者-{suffix}",
            canonical_name="双生者", evidence="双生者", extra_data={"lifecycle": {"status": "candidate"}},
        ))
    db_session.add(StoryEntity(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id, chapter_id=foreign.id,
        first_seen_chapter_id=foreign.id, entity_type="scene", name="跨章场景",
        canonical_name="跨章场景", evidence="跨章场景", extra_data={"lifecycle": {"status": "candidate"}},
    ))
    await db_session.flush()

    context = await resolve_owned_shot_entity_context(
        db_session, user_id=user_id, novel_id=novel_id, chapter_ids=[allowed.id],
        source_text=allowed.content, shot_text=allowed.content,
    )

    assert context["entity_refs"] == {"characters": [], "scenes": [], "props": [], "events": []}


@pytest.mark.asyncio
async def test_owned_shot_resolver_prefers_one_signed_local_mention_over_its_canonical(
    db_session: AsyncSession,
) -> None:
    from app.features.series_run_story_locks.domain.scoped_reference import (
        canonical_identity_sha256,
        sign_merge_edge,
    )
    from app.services.owned_shot_entity_refs import resolve_owned_shot_entity_context
    from app.services.story_entity_lifecycle import ARCHIVED, set_entity_review_status

    now = utc_now()
    user_id, novel_id, chapter_id = str(uuid4()), str(uuid4()), str(uuid4())
    content = "沈岚说：守住师门。"
    db_session.add(Novel(id=novel_id, user_id=user_id, title="五章", created_at=now, updated_at=now))
    db_session.add(Chapter(
        id=chapter_id, user_id=user_id, novel_id=novel_id, title="第一章",
        content=content, chapter_number=1, created_at=now, updated_at=now,
    ))
    evidence = {
        "status": "verified", "chapter_id": chapter_id, "source_span": [0, 2],
        "content_hash": hashlib.sha256(content.encode()).hexdigest(),
        "source_excerpt": "沈岚", "parser_version": "explicit-dialogue-v1",
    }
    canonical = StoryEntity(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id, chapter_id=chapter_id,
        first_seen_chapter_id=chapter_id, entity_type="character", name="沈岚",
        canonical_name="沈岚", source="system", attributes={"evidence_contract": evidence},
        extra_data={"lifecycle": {"status": "approved"}}, is_approved=True,
    )
    mention = StoryEntity(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id, chapter_id=chapter_id,
        first_seen_chapter_id=chapter_id, entity_type="character", name="沈岚",
        canonical_name="沈岚", source="system",
        attributes={"evidence_contract": evidence, "merged_into_entity_id": canonical.id},
        extra_data={}, is_approved=False,
    )
    edge = sign_merge_edge({
        "source_entity_id": mention.id, "canonical_entity_id": canonical.id,
        "user_id": user_id, "novel_id": novel_id, "entity_type": "character",
        "canonical_identity_sha256": canonical_identity_sha256(
            entity_type="character", canonical_name="沈岚",
        ),
    })
    mention.extra_data = {
        "merge_edges": [edge],
        "normalized_merge": {"status": "merged_superseded", "canonical_entity_id": canonical.id},
    }
    set_entity_review_status(mention, ARCHIVED, changed_by=user_id, reason="explicit_dialogue_chapter_local_mention")
    db_session.add_all([canonical, mention])
    await db_session.flush()

    context = await resolve_owned_shot_entity_context(
        db_session, user_id=user_id, novel_id=novel_id, chapter_ids=[chapter_id],
        as_of_chapter_id=chapter_id, source_text=content, shot_text=content,
    )

    assert [item["entity_id"] for item in context["entity_refs"]["characters"]] == [mention.id]


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_source", ["missing", "cross", "future"])
async def test_persisted_owner_chain_invalid_sources_fail_closed_with_zero_writes(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    invalid_source: str,
) -> None:
    run, shots = await _persisted_owner_chain_fixture(db_session, monkeypatch)
    StoryLockPreparationBlocked, _, _, prepare_story_locks, _ = _public_api()
    required_id = shots[0].extra_data["entity_refs"]["props"][0]["entity_id"]
    entity = await db_session.get(StoryEntity, required_id)
    attributes = dict(entity.attributes or {})
    if invalid_source == "missing":
        attributes.pop("evidence_contract", None)
    elif invalid_source == "cross":
        attributes["evidence_contract"] = {
            **attributes["evidence_contract"], "chapter_id": run.episodes[1]["chapter_ids"][0],
        }
    else:
        future = await db_session.scalar(select(StoryEntity).where(
            StoryEntity.novel_id == run.novel_id,
            StoryEntity.entity_type == "prop",
            StoryEntity.chapter_id == run.episodes[3]["chapter_ids"][0],
        ))
        refs = dict(shots[0].extra_data["entity_refs"])
        refs["props"] = [{"entity_id": future.id}]
        shots[0].extra_data = {**shots[0].extra_data, "entity_refs": refs}
    entity.attributes = attributes
    await db_session.commit()
    before = await _database_snapshot(db_session)

    with pytest.raises(StoryLockPreparationBlocked) as raised:
        await prepare_story_locks(db_session, run)

    assert raised.value.code == "story_lock_source_invalid"
    assert await _database_snapshot(db_session) == before


@pytest.mark.asyncio
async def test_fixture_reproduces_four_chapters_and_46_candidate_shape(db_session: AsyncSession) -> None:
    run, shots = await _production_shaped_fixture(db_session)

    counts = {
        entity_type: await db_session.scalar(
            select(func.count()).select_from(StoryEntity).where(StoryEntity.entity_type == entity_type)
        )
        for entity_type in ENTITY_COUNTS
    }
    assert counts == ENTITY_COUNTS
    assert len(run.episodes) == 4
    assert run.run_metadata["selected_anchor_shot_ids"] == [shots[0].id, shots[3].id]


@pytest.mark.asyncio
async def test_two_selected_anchors_build_required_closure_smaller_than_46_candidates(
    db_session: AsyncSession,
) -> None:
    _, shots = await _production_shaped_fixture(db_session)
    _, build_required_entity_closure, _, _, _ = _public_api()
    candidates = list((await db_session.scalars(select(StoryEntity))).all())

    closure = build_required_entity_closure(selected_shots=[shots[0], shots[3]], candidates=candidates)

    assert len(candidates) == 46
    assert closure["candidate_counts"] == ENTITY_COUNTS
    assert closure["required_counts"] == {kind: 2 for kind in ENTITY_COUNTS}
    assert len(closure["required_entity_ids"]) == 8 < len(candidates)
    assert closure["unrelated_candidate_count"] == 38
    assert len(closure["closure_hash"]) == 64


@pytest.mark.asyncio
async def test_live_extraction_shape_blocks_missing_required_evidence_with_zero_writes(
    db_session: AsyncSession,
) -> None:
    run, shots = await _production_shaped_fixture(db_session)
    StoryLockPreparationBlocked, build_required_entity_closure, _, prepare_story_locks, _ = _public_api()
    candidates = list((await db_session.scalars(select(StoryEntity))).all())
    closure = build_required_entity_closure(selected_shots=[shots[0], shots[3]], candidates=candidates)
    required_ids = set(closure["required_entity_ids"])
    for entity in candidates:
        if entity.id not in required_ids:
            continue
        entity.attributes = {"extraction_notes": ["rule extraction"]}
        entity.extra_data = {}
        entity.is_approved = False
    await db_session.commit()
    before = await _database_snapshot(db_session)

    with pytest.raises(StoryLockPreparationBlocked) as raised:
        await prepare_story_locks(db_session, run)

    assert raised.value.code == "story_lock_source_invalid"
    assert raised.value.blocker_category == "selection_state"
    assert raised.value.field == "story_source"
    assert isinstance(raised.value.__cause__, ValueError)
    assert closure["unrelated_candidate_count"] == 38
    assert await _database_snapshot(db_session) == before


@pytest.mark.asyncio
async def test_unrelated_candidates_remain_candidates_and_do_not_block_lock(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run, _ = await _persisted_owner_chain_fixture(db_session, monkeypatch)
    _, _, _, prepare_story_locks, _ = _public_api()

    result = await prepare_story_locks(db_session, run)

    entities = list((await db_session.scalars(select(StoryEntity))).all())
    unrelated = [item for item in entities if item.id not in result["required_entity_ids"]]
    bible = await db_session.get(StoryBible, result["story_bible_id"])
    assert result["status"] == "locked"
    assert result["required_counts"] == {kind: 2 for kind in ENTITY_COUNTS}
    assert result["unrelated_candidate_count"] == 38
    assert len(unrelated) == 38
    assert bible.style == "二维国风动漫"
    assert all(not item.is_approved and get_entity_review_status(item) == "candidate" for item in unrelated)
    story_lock = bible.extra_data["series_story_lock"]
    assert story_lock["closure_hash"] == result["closure_hash"]
    assert story_lock["closure_contract_version"] == "required_entity_closure_v2"
    assert {item["canonical_entity_id"] for item in story_lock["subjects"]} == set(result["required_entity_ids"])
    assert story_lock["evidence_edges"] == result["evidence_edges"]


@pytest.mark.asyncio
async def test_story_lock_accepts_selected_shot_from_later_storyboard_in_same_episode(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run, shots = await _persisted_owner_chain_fixture(db_session, monkeypatch)
    _, _, _, prepare_story_locks, _ = _public_api()
    shot = shots[0]
    primary = await db_session.get(Storyboard, shot.storyboard_id)
    later = Storyboard(
        id=str(uuid4()), user_id=run.user_id, novel_id=run.novel_id,
        script_id=primary.script_id, title="同集第二场",
        content={"series_run_id": run.id, "episode_number": 1, "scene_index": 2,
                 "input_hash": run.episodes[0]["input_hash"]},
    )
    db_session.add(later)
    await db_session.flush()
    shot.storyboard_id = later.id
    episodes = [dict(item) for item in run.episodes]
    canonical = dict(episodes[0]["canonical_ids"])
    canonical["storyboard_ids"] = [canonical["storyboard_id"], later.id]
    episodes[0] = {**episodes[0], "canonical_ids": canonical}
    run.episodes = episodes
    await db_session.commit()

    result = await prepare_story_locks(db_session, run, native_audio=True)

    assert result["status"] == "locked"


@pytest.mark.asyncio
async def test_ambiguous_required_fact_blocks_with_zero_writes(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    run, shots = await _persisted_owner_chain_fixture(db_session, monkeypatch)
    StoryLockPreparationBlocked, _, _, prepare_story_locks, _ = _public_api()
    required_prop_id = shots[0].extra_data["entity_refs"]["props"][0]["entity_id"]
    required_prop = await db_session.get(StoryEntity, required_prop_id)
    required_prop.attributes = {
        **(required_prop.attributes or {}),
        "evidence_contract": {
            **((required_prop.attributes or {}).get("evidence_contract") or {}),
            "status": "ambiguous",
            "conflicting_values": ["完整", "破损"],
        },
    }
    await db_session.commit()
    before = await _database_snapshot(db_session)

    with pytest.raises(StoryLockPreparationBlocked) as raised:
        await prepare_story_locks(db_session, run)

    assert raised.value.code == "story_lock_source_invalid"
    assert await _database_snapshot(db_session) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["malformed", "unknown", "wrong_type", "missing_chapter", "foreign"])
async def test_invalid_required_reference_fails_closed_with_zero_writes(
    db_session: AsyncSession,
    failure: str,
) -> None:
    run, shots = await _production_shaped_fixture(db_session)
    _, _, _, prepare_story_locks, _ = _public_api()
    shot = shots[0]
    extra = dict(shot.extra_data or {})
    references = dict(extra.get("entity_refs") or {})
    if failure == "malformed":
        references["props"] = ["not-an-object"]
    elif failure == "unknown":
        references["props"] = [{"entity_id": str(uuid4())}]
    elif failure == "wrong_type":
        references["scenes"] = list(references["props"])
    elif failure == "missing_chapter":
        extra.pop("chapter_id", None)
    else:
        foreign = StoryEntity(
            id=str(uuid4()), user_id=str(uuid4()), novel_id=str(uuid4()), entity_type="prop",
            name="foreign", canonical_name="foreign", source="deterministic", is_approved=False,
            attributes={}, extra_data={"lifecycle": {"status": "candidate"}},
        )
        db_session.add(foreign)
        references["props"] = [{"entity_id": foreign.id}]
    extra["entity_refs"] = references
    shot.extra_data = extra
    await db_session.commit()
    before = await _database_snapshot(db_session)

    with pytest.raises(ValueError):
        await prepare_story_locks(db_session, run)

    assert await _database_snapshot(db_session) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("conflict", ["identity", "relation", "state", "tag"])
async def test_required_compatibility_conflict_has_zero_writes(
    db_session: AsyncSession,
    conflict: str,
) -> None:
    run, shots = await _production_shaped_fixture(db_session)
    StoryLockPreparationBlocked, _, _, prepare_story_locks, _ = _public_api()
    entity_id = shots[0].extra_data["entity_refs"]["props"][0]["entity_id"]
    entity = await db_session.get(StoryEntity, entity_id)
    if conflict == "identity":
        entity.attributes = {**(entity.attributes or {}), "identity_facts": {"role": ["lead", "villain"]}}
    elif conflict == "relation":
        entity.relations = [
            {"chapter_id": entity.chapter_id, "entity_id": "target", "type": "ally"},
            {"chapter_id": entity.chapter_id, "entity_id": "target", "type": "enemy"},
        ]
    elif conflict == "state":
        entity.state_changes = [
            {"chapter_id": entity.chapter_id, "state": "alive"},
            {"chapter_id": entity.chapter_id, "state": "dead"},
        ]
    else:
        entity.tags = ["protagonist", "antagonist"]
    await db_session.commit()
    before = await _database_snapshot(db_session)

    with pytest.raises(StoryLockPreparationBlocked) as raised:
        await prepare_story_locks(db_session, run)

    assert raised.value.code == "story_lock_source_invalid"
    assert await _database_snapshot(db_session) == before


@pytest.mark.asyncio
async def test_same_canonical_character_conflict_has_zero_writes(db_session: AsyncSession) -> None:
    run, shots = await _production_shaped_fixture(db_session)
    StoryLockPreparationBlocked, _, _, prepare_story_locks, _ = _public_api()
    first_id = shots[0].extra_data["entity_refs"]["characters"][0]["entity_id"]
    second_id = shots[3].extra_data["entity_refs"]["characters"][0]["entity_id"]
    first, second = await db_session.get(StoryEntity, first_id), await db_session.get(StoryEntity, second_id)
    first.canonical_name = second.canonical_name = "shared-speaker"
    first.attributes = {**(first.attributes or {}), "role": "protagonist"}
    second.attributes = {**(second.attributes or {}), "role": "antagonist"}
    await db_session.commit()
    before = await _database_snapshot(db_session)

    with pytest.raises(StoryLockPreparationBlocked) as raised:
        await prepare_story_locks(db_session, run)

    assert raised.value.code == "story_lock_source_invalid"
    assert await _database_snapshot(db_session) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("order", list(permutations(("x", "y", "bridge"))))
async def test_bridged_character_identity_conflict_is_order_independent_and_zero_write(
    db_session: AsyncSession,
    order: tuple[str, str, str],
) -> None:
    run, shots = await _production_shaped_fixture(db_session)
    StoryLockPreparationBlocked, _, _, prepare_story_locks, _ = _public_api()
    characters = list((await db_session.scalars(select(StoryEntity).where(
        StoryEntity.entity_type == "character", StoryEntity.user_id == run.user_id,
    ).order_by(StoryEntity.name))).all())[:3]
    by_label = dict(zip(("x", "y", "bridge"), characters))
    by_label["x"].canonical_name = "identity-x"
    by_label["x"].attributes = {**(by_label["x"].attributes or {}), "role": "protagonist"}
    by_label["y"].canonical_name = "identity-y"
    by_label["y"].attributes = {**(by_label["y"].attributes or {}), "role": "antagonist", "speaker_ref": "shared"}
    by_label["bridge"].canonical_name = "identity-x"
    by_label["bridge"].attributes = {**(by_label["bridge"].attributes or {}), "role": "protagonist", "speaker_ref": "shared"}
    first_extra, last_extra = dict(shots[0].extra_data or {}), dict(shots[3].extra_data or {})
    first_extra["entity_refs"] = {**first_extra["entity_refs"], "characters": []}
    last_extra["entity_refs"] = {
        **last_extra["entity_refs"],
        "characters": [{"entity_id": by_label[label].id} for label in order],
    }
    shots[0].extra_data, shots[3].extra_data = first_extra, last_extra
    await db_session.commit()
    before = await _database_snapshot(db_session)

    with pytest.raises(StoryLockPreparationBlocked) as raised:
        await prepare_story_locks(db_session, run)

    assert raised.value.code == "story_lock_source_invalid"
    assert await _database_snapshot(db_session) == before


@pytest.mark.asyncio
@pytest.mark.parametrize(("missing", "code"), [
    ("selection", "anchor_selection_required"),
    ("references", "anchor_entity_closure_required"),
])
async def test_persisted_anchor_closure_is_required_with_zero_writes(
    db_session: AsyncSession,
    missing: str,
    code: str,
) -> None:
    run, shots = await _production_shaped_fixture(db_session)
    StoryLockPreparationBlocked, _, _, prepare_story_locks, _ = _public_api()
    if missing == "selection":
        run.run_metadata = {**(run.run_metadata or {}), "selected_anchor_shot_ids": []}
    else:
        for shot in (shots[0], shots[3]):
            extra = dict(shot.extra_data or {})
            extra.pop("entity_refs", None)
            shot.extra_data = extra
    await db_session.commit()
    before = await _database_snapshot(db_session)

    with pytest.raises(StoryLockPreparationBlocked) as raised:
        await prepare_story_locks(db_session, run)

    assert raised.value.code == code
    assert await _database_snapshot(db_session) == before


@pytest.mark.asyncio
async def test_actual_409_and_runner_capture_are_strictly_redacted_and_rereadable(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    StoryLockPreparationBlocked, _, capture_response, _, _ = _public_api()
    run, _ = await _production_shaped_fixture(db_session)
    secrets = [
        "沈砚", "第4章隔离测试内容", "第4章锚点", "ally", "enemy",
        "voice-secret", "credential-secret", "provider_payload",
    ]
    error = StoryLockPreparationBlocked(
        code="required_entity_evidence_ambiguous",
        blocker_category="prop_state",
        field="state",
        values=secrets,
        required_counts={kind: 2 for kind in ENTITY_COUNTS},
    )

    response = await _post_actual_story_lock_route(db_session, run, monkeypatch, error)
    body = response.json()
    detail = body["detail"]
    capture = await capture_response(
        db_session,
        run,
        status_code=response.status_code,
        response_body=body,
    )
    await db_session.commit()
    await db_session.refresh(run)

    expected_hashes = sorted({
        hashlib.sha256(json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode()).hexdigest()
        for value in secrets
    })
    serialized = json.dumps(body, ensure_ascii=False, sort_keys=True)
    assert response.status_code == 409 and set(body) == {"detail"}
    assert set(detail) == {"code", "blocker_category", "field", "required_counts", "value_hashes"}
    assert detail == {
        "code": "required_entity_evidence_ambiguous",
        "blocker_category": "prop_state",
        "field": "state",
        "required_counts": {kind: 2 for kind in ENTITY_COUNTS},
        "value_hashes": expected_hashes,
    }
    assert all(secret not in serialized for secret in secrets)
    assert not any(token in serialized for token in ["prompt", "credential", "provider_payload"])
    expected_body_hash = hashlib.sha256(json.dumps(
        body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()
    assert set(capture) == {"status_code", "body", "body_sha256", "captured_at"}
    assert capture["status_code"] == 409 and capture["body"] == body
    assert capture["body_sha256"] == expected_body_hash
    assert run.run_metadata["story_lock_response_capture"] == capture
    for category, field in (("provider_payload", "state"), ("prop_state", "Secret-Field")):
        unsafe_error = StoryLockPreparationBlocked(
            code="required_entity_evidence_ambiguous",
            blocker_category=category,
            field=field,
            values=["must-not-leak"],
            required_counts={kind: 2 for kind in ENTITY_COUNTS},
        )
        unsafe_response = await _post_actual_story_lock_route(db_session, run, monkeypatch, unsafe_error)
        assert unsafe_response.status_code == 409
        assert unsafe_response.json() == {"detail": {"code": "story_lock_preparation_blocked"}}
        assert "must-not-leak" not in unsafe_response.text
