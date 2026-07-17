from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import create_engine, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models.production_state_event import ProductionStateEvent
from app.services.production_graph_service import (
    analyze_state_change_impact,
    append_state_event,
    build_episode_state_snapshot,
    project_story_state,
    update_state_event,
)


def _run(coro):
    return asyncio.run(coro)


async def _session() -> tuple[AsyncSession, object]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(ProductionStateEvent.__table__.create)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return factory(), engine


def test_append_state_event_assigns_monotonic_versions_and_hash_chain() -> None:
    async def scenario() -> tuple[ProductionStateEvent, ProductionStateEvent]:
        db, engine = await _session()
        try:
            first = await append_state_event(
                db,
                user_id="user-1",
                novel_id="novel-1",
                chapter_id="chapter-1",
                episode_index=1,
                entity_id="character-lin",
                event_type="costume_changed",
                story_time={"episode_index": 1, "sequence": 1},
                production_time={"stage": "script"},
                before_state={"costume": "校服"},
                after_state={"costume": "黑色风衣"},
                evidence={"quote": "林澈换上黑色风衣"},
                approval_status="approved",
                approved_by="editor-1",
            )
            second = await append_state_event(
                db,
                user_id="user-1",
                novel_id="novel-1",
                episode_index=2,
                entity_id="character-lin",
                event_type="injury_changed",
                story_time={"episode_index": 2, "sequence": 3},
                production_time={"stage": "storyboard"},
                before_state={"injury": None},
                after_state={"injury": "左臂擦伤"},
                approval_status="approved",
                approved_by="editor-1",
            )
            return first, second
        finally:
            await db.close()
            await engine.dispose()

    first, second = _run(scenario())

    assert first.production_version == 1
    assert second.production_version == 2
    assert first.previous_event_hash is None
    assert second.previous_event_hash == first.event_hash
    assert len(first.event_hash) == 64
    assert second.event_hash != first.event_hash
    assert first.approved_at is not None


def test_production_state_event_rejects_orm_update_and_delete() -> None:
    engine = create_engine("sqlite:///:memory:")
    ProductionStateEvent.__table__.create(engine)
    row = ProductionStateEvent(
        id="event-immutable",
        user_id="user-1",
        novel_id="novel-1",
        event_type="weather_changed",
        story_time={},
        production_time={},
        before_state={},
        after_state={"weather": "雨"},
        approval_status="approved",
        production_version=1,
        event_hash="a" * 64,
    )
    with Session(engine) as session:
        session.add(row)
        session.commit()
        row.event_type = "mutated"
        with pytest.raises(ValueError, match="immutable"):
            session.commit()
        session.rollback()
        persisted = session.get(ProductionStateEvent, row.id)
        session.delete(persisted)
        with pytest.raises(ValueError, match="immutable"):
            session.commit()


@pytest.mark.parametrize("statement", [
    update(ProductionStateEvent).where(ProductionStateEvent.id == "event-bulk").values(event_type="mutated"),
    delete(ProductionStateEvent).where(ProductionStateEvent.id == "event-bulk"),
])
def test_production_state_event_rejects_bulk_dml(statement) -> None:
    engine = create_engine("sqlite:///:memory:")
    ProductionStateEvent.__table__.create(engine)
    row = ProductionStateEvent(
        id="event-bulk",
        user_id="user-1",
        novel_id="novel-1",
        event_type="weather_changed",
        story_time={},
        production_time={},
        before_state={},
        after_state={"weather": "雨"},
        approval_status="approved",
        production_version=1,
        event_hash="b" * 64,
    )
    with Session(engine) as session:
        session.add(row)
        session.commit()
        with pytest.raises(ValueError, match="immutable"):
            session.execute(statement)
        session.rollback()
        assert session.get(ProductionStateEvent, row.id) is not None


def test_projection_supports_production_continuity_change_types() -> None:
    async def scenario() -> dict:
        db, engine = await _session()
        try:
            events = [
                ("character-lin", "costume_changed", {"costume": "黑色风衣"}),
                ("character-lin", "injury_changed", {"injury": "左臂擦伤"}),
                ("prop-bell", "prop_owner_changed", {"owner": "character-lin"}),
                ("scene-port", "weather_changed", {"weather": "暴雨"}),
                (
                    "character-lin",
                    "relationship_changed",
                    {"relationships": {"character-shen": "盟友"}},
                ),
            ]
            for sequence, (entity_id, event_type, after_state) in enumerate(events, start=1):
                await append_state_event(
                    db,
                    user_id="user-1",
                    novel_id="novel-1",
                    episode_index=1,
                    entity_id=entity_id,
                    event_type=event_type,
                    story_time={"episode_index": 1, "sequence": sequence},
                    production_time={"stage": "script"},
                    before_state={},
                    after_state=after_state,
                    approval_status="approved",
                )
            return await project_story_state(db, user_id="user-1", novel_id="novel-1")
        finally:
            await db.close()
            await engine.dispose()

    projection = _run(scenario())

    assert projection["state"]["entities"]["character-lin"] == {
        "costume": "黑色风衣",
        "injury": "左臂擦伤",
        "relationships": {"character-shen": "盟友"},
    }
    assert projection["state"]["entities"]["prop-bell"]["owner"] == "character-lin"
    assert projection["state"]["entities"]["scene-port"]["weather"] == "暴雨"
    assert projection["through_version"] == 5


def test_projection_excludes_unapproved_events() -> None:
    async def scenario() -> dict:
        db, engine = await _session()
        try:
            approved = await append_state_event(
                db,
                user_id="user-1",
                novel_id="novel-1",
                episode_index=1,
                entity_id="character-lin",
                event_type="costume_changed",
                story_time={"episode_index": 1},
                production_time={"stage": "script"},
                before_state={},
                after_state={"costume": "黑色风衣"},
                approval_status="approved",
            )
            pending = await append_state_event(
                db,
                user_id="user-1",
                novel_id="novel-1",
                episode_index=2,
                entity_id="character-lin",
                event_type="costume_changed",
                story_time={"episode_index": 2},
                production_time={"stage": "storyboard"},
                before_state={"costume": "黑色风衣"},
                after_state={"costume": "白色外套"},
                approval_status="pending",
            )
            projection = await project_story_state(db, user_id="user-1", novel_id="novel-1")
            return {
                "projection": projection,
                "approved_id": approved.id,
                "pending_id": pending.id,
            }
        finally:
            await db.close()
            await engine.dispose()

    result = _run(scenario())

    assert result["projection"]["state"]["entities"]["character-lin"]["costume"] == "黑色风衣"
    assert result["approved_id"] in result["projection"]["applied_event_ids"]
    assert result["pending_id"] in result["projection"]["ignored_event_ids"]


def test_projection_exposes_canonical_tip_hash_and_deterministic_empty_hash() -> None:
    async def scenario() -> tuple[dict, dict, str]:
        db, engine = await _session()
        try:
            empty = await project_story_state(db, user_id="user-1", novel_id="novel-1")
            event = await append_state_event(
                db,
                user_id="user-1",
                novel_id="novel-1",
                event_type="weather_changed",
                after_state={"weather": "雨"},
                approval_status="approved",
            )
            projected = await project_story_state(db, user_id="user-1", novel_id="novel-1")
            return empty, projected, event.event_hash
        finally:
            await db.close()
            await engine.dispose()

    empty, projected, event_hash = _run(scenario())

    assert len(empty["graph_hash"]) == 64
    assert projected["graph_hash"] == event_hash


def test_restore_appends_compensating_event_without_mutating_history() -> None:
    async def scenario() -> dict:
        db, engine = await _session()
        try:
            first = await append_state_event(
                db,
                user_id="user-1",
                novel_id="novel-1",
                episode_index=1,
                entity_id="character-lin",
                event_type="costume_changed",
                story_time={"episode_index": 1},
                production_time={"stage": "script"},
                before_state={},
                after_state={"costume": "黑色风衣"},
                approval_status="approved",
            )
            original_hash = first.event_hash
            second = await append_state_event(
                db,
                user_id="user-1",
                novel_id="novel-1",
                episode_index=2,
                entity_id="character-lin",
                event_type="costume_changed",
                story_time={"episode_index": 2},
                production_time={"stage": "storyboard"},
                before_state={"costume": "黑色风衣"},
                after_state={"costume": "白色外套"},
                approval_status="approved",
            )
            restore = await append_state_event(
                db,
                user_id="user-1",
                novel_id="novel-1",
                event_type="restore_version",
                story_time={"episode_index": 3},
                production_time={"stage": "review"},
                approval_status="approved",
                restore_version=1,
            )
            projection = await project_story_state(db, user_id="user-1", novel_id="novel-1")
            persisted_first = await db.get(ProductionStateEvent, first.id)
            count = await db.scalar(select(func.count()).select_from(ProductionStateEvent))
            return {
                "first_hash": persisted_first.event_hash,
                "original_hash": original_hash,
                "second_id": second.id,
                "restore": restore,
                "projection": projection,
                "count": count,
            }
        finally:
            await db.close()
            await engine.dispose()

    result = _run(scenario())

    assert result["count"] == 3
    assert result["first_hash"] == result["original_hash"]
    assert result["restore"].production_version == 3
    assert result["restore"].production_time["restored_from_version"] == 1
    assert result["projection"]["state"]["entities"]["character-lin"]["costume"] == "黑色风衣"
    assert result["second_id"] in result["projection"]["applied_event_ids"]


def test_service_rejects_in_place_event_mutation() -> None:
    async def scenario() -> None:
        db, engine = await _session()
        try:
            event = await append_state_event(
                db,
                user_id="user-1",
                novel_id="novel-1",
                entity_id="character-lin",
                event_type="injury_changed",
                story_time={"episode_index": 1},
                production_time={"stage": "script"},
                before_state={},
                after_state={"injury": "左臂擦伤"},
                approval_status="approved",
            )
            with pytest.raises(ValueError, match="append a compensating event"):
                await update_state_event(db, event_id=event.id, after_state={"injury": None})
        finally:
            await db.close()
            await engine.dispose()

    _run(scenario())


def test_episode_snapshot_uses_approved_events_and_reports_conflicts_deterministically() -> None:
    async def scenario() -> dict:
        db, engine = await _session()
        try:
            for sequence, costume in ((1, "黑色风衣"), (1, "白色外套")):
                await append_state_event(
                    db,
                    user_id="user-1",
                    novel_id="novel-1",
                    episode_index=2,
                    entity_id="character-lin",
                    event_type="costume_changed",
                    story_time={"episode_index": 2, "sequence": sequence},
                    production_time={"stage": "script"},
                    before_state={"costume": "校服"},
                    after_state={"costume": costume},
                    approval_status="approved",
                )
            await append_state_event(
                db,
                user_id="user-1",
                novel_id="novel-1",
                episode_index=2,
                entity_id="character-lin",
                event_type="injury_changed",
                story_time={"episode_index": 2, "sequence": 2},
                production_time={"stage": "script"},
                before_state={},
                after_state={"injury": "左臂擦伤"},
                approval_status="pending",
            )
            return await build_episode_state_snapshot(
                db,
                user_id="user-1",
                novel_id="novel-1",
                episode_index=2,
            )
        finally:
            await db.close()
            await engine.dispose()

    snapshot = _run(scenario())

    assert snapshot["status"] == "conflicted"
    assert snapshot["state"]["entities"]["character-lin"]["costume"] == "白色外套"
    assert "injury" not in snapshot["state"]["entities"]["character-lin"]
    assert snapshot["unresolved_conflicts"] == sorted(
        snapshot["unresolved_conflicts"],
        key=lambda item: (item["episode_index"], item["entity_id"] or "", item["field_path"], item["event_id"]),
    )
    assert {item["reason"] for item in snapshot["unresolved_conflicts"]} == {
        "before_state_mismatch",
        "competing_story_time_write",
    }


def test_impact_analysis_is_data_only_and_deterministic() -> None:
    async def scenario() -> tuple[str, dict]:
        db, engine = await _session()
        try:
            source = await append_state_event(
                db,
                user_id="user-1",
                novel_id="novel-1",
                episode_index=2,
                entity_id="character-lin",
                event_type="relationship_changed",
                story_time={"episode_index": 2},
                production_time={"stage": "script"},
                before_state={},
                after_state={
                    "relationships": {"character-shen": "盟友"},
                    "related_entity_ids": ["character-shen"],
                },
                approval_status="approved",
            )
            await append_state_event(
                db,
                user_id="user-1",
                novel_id="novel-1",
                episode_index=4,
                entity_id="character-lin",
                event_type="injury_changed",
                story_time={"episode_index": 4},
                production_time={"stage": "storyboard"},
                before_state={},
                after_state={"injury": "左臂擦伤"},
                approval_status="approved",
            )
            impact = await analyze_state_change_impact(
                db,
                user_id="user-1",
                novel_id="novel-1",
                event_id=source.id,
            )
            return source.id, impact
        finally:
            await db.close()
            await engine.dispose()

    source_id, impact = _run(scenario())

    assert impact["source_event_id"] == source_id
    assert impact["affected_episode_indices"] == [2, 4]
    assert impact["affected_entity_ids"] == ["character-lin", "character-shen"]
    assert impact["affected_event_ids"][0] == source_id
    assert set(impact) == {
        "source_event_id",
        "affected_episode_indices",
        "affected_entity_ids",
        "affected_event_ids",
    }


def test_episode_snapshot_restore_replays_target_version_with_episode_cutoff() -> None:
    async def scenario() -> dict:
        db, engine = await _session()
        try:
            await append_state_event(
                db,
                user_id="user-1",
                novel_id="novel-1",
                episode_index=1,
                entity_id="character-lin",
                event_type="costume_changed",
                story_time={"episode_index": 1},
                after_state={"costume": "黑色风衣"},
                approval_status="approved",
            )
            future = await append_state_event(
                db,
                user_id="user-1",
                novel_id="novel-1",
                episode_index=10,
                entity_id="character-lin",
                event_type="costume_changed",
                story_time={"episode_index": 10},
                before_state={"costume": "黑色风衣"},
                after_state={"costume": "白色外套"},
                approval_status="approved",
            )
            await append_state_event(
                db,
                user_id="user-1",
                novel_id="novel-1",
                episode_index=3,
                event_type="restore_version",
                story_time={"episode_index": 3},
                approval_status="approved",
                restore_version=future.production_version,
            )
            return await build_episode_state_snapshot(
                db,
                user_id="user-1",
                novel_id="novel-1",
                episode_index=3,
            )
        finally:
            await db.close()
            await engine.dispose()

    snapshot = _run(scenario())

    assert snapshot["state"]["entities"]["character-lin"]["costume"] == "黑色风衣"


def test_episode_snapshot_reports_missing_expected_before_state_as_conflict() -> None:
    async def scenario() -> dict:
        db, engine = await _session()
        try:
            event = await append_state_event(
                db,
                user_id="user-1",
                novel_id="novel-1",
                episode_index=2,
                entity_id="character-lin",
                event_type="costume_changed",
                story_time={"episode_index": 2},
                before_state={"costume": "校服"},
                after_state={"costume": "黑色风衣"},
                approval_status="approved",
            )
            snapshot = await build_episode_state_snapshot(
                db,
                user_id="user-1",
                novel_id="novel-1",
                episode_index=2,
            )
            return {"event_id": event.id, "snapshot": snapshot}
        finally:
            await db.close()
            await engine.dispose()

    result = _run(scenario())

    assert result["snapshot"]["status"] == "conflicted"
    assert result["snapshot"]["unresolved_conflicts"] == [
        {
            "episode_index": 2,
            "entity_id": "character-lin",
            "event_id": result["event_id"],
            "field_path": "costume",
            "reason": "before_state_mismatch",
            "expected_before": "校服",
            "actual_before": None,
        }
    ]


def test_impact_analysis_follows_transitive_entity_relationships() -> None:
    async def scenario() -> tuple[list[str], dict]:
        db, engine = await _session()
        try:
            source = await append_state_event(
                db,
                user_id="user-1",
                novel_id="novel-1",
                episode_index=1,
                entity_id="character-a",
                event_type="relationship_changed",
                story_time={"episode_index": 1},
                after_state={"related_entity_ids": ["character-b"]},
                approval_status="approved",
            )
            middle = await append_state_event(
                db,
                user_id="user-1",
                novel_id="novel-1",
                episode_index=2,
                entity_id="character-b",
                event_type="relationship_changed",
                story_time={"episode_index": 2},
                after_state={"related_entity_ids": ["character-c"]},
                approval_status="approved",
            )
            downstream = await append_state_event(
                db,
                user_id="user-1",
                novel_id="novel-1",
                episode_index=4,
                entity_id="character-c",
                event_type="injury_changed",
                story_time={"episode_index": 4},
                after_state={"injury": "左臂擦伤"},
                approval_status="approved",
            )
            await append_state_event(
                db,
                user_id="user-1",
                novel_id="novel-1",
                episode_index=5,
                entity_id="character-unrelated",
                event_type="costume_changed",
                story_time={"episode_index": 5},
                after_state={"costume": "灰色外套"},
                approval_status="approved",
            )
            impact = await analyze_state_change_impact(
                db,
                user_id="user-1",
                novel_id="novel-1",
                event_id=source.id,
            )
            return [source.id, middle.id, downstream.id], impact
        finally:
            await db.close()
            await engine.dispose()

    expected_event_ids, impact = _run(scenario())

    assert impact["affected_episode_indices"] == [1, 2, 4]
    assert impact["affected_entity_ids"] == ["character-a", "character-b", "character-c"]
    assert impact["affected_event_ids"] == expected_event_ids
