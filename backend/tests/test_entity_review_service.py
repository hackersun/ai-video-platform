from __future__ import annotations

import asyncio
import hashlib
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models import StoryEntity
from init_db import init_db


@pytest.fixture(scope="module", autouse=True)
def _init_database() -> None:
    init_db()


def _run(coro):
    return asyncio.run(coro)


def test_extraction_tracking_models_are_exported() -> None:
    from app.models import EntityExtractionRun, EntityFeedback, StoryEntityMention

    assert EntityExtractionRun.__tablename__ == "entity_extraction_runs"
    assert StoryEntityMention.__tablename__ == "story_entity_mentions"
    assert EntityFeedback.__tablename__ == "entity_feedback"


def test_v2_candidate_extraction_persists_run_mentions_and_lifecycle_metadata() -> None:
    async def scenario() -> dict:
        from app.models import EntityExtractionRun, StoryEntityMention
        from app.services.entity_review_service import run_candidate_entity_extraction
        from app.services.story_entity_lifecycle import CANDIDATE, REJECTED, get_entity_review_status

        user_id = f"review-user-{uuid4().hex[:20]}"
        novel_id = f"review-novel-{uuid4()}"
        async with AsyncSessionLocal() as db:
            result = await run_candidate_entity_extraction(
                db,
                user_id=user_id,
                novel_id=novel_id,
                source_type="novel",
                source_id=novel_id,
                text="角色：林澈。林澈站在旧邮局门口，握紧铜铃。场景：旧邮局。道具：铜铃。",
                entity_types=["character", "scene", "prop"],
                persist=True,
            )

            run = await db.get(EntityExtractionRun, result["run_id"])
            mentions = (
                await db.execute(
                    select(StoryEntityMention).where(StoryEntityMention.run_id == result["run_id"])
                )
            ).scalars().all()
            entities = (
                await db.execute(
                    select(StoryEntity).where(StoryEntity.user_id == user_id, StoryEntity.novel_id == novel_id)
                )
            ).scalars().all()

            return {
                "run_status": run.status if run else None,
                "run_stats": run.stats if run else {},
                "run_prompt_routing": (run.extra_data or {}).get("prompt_routing") if run else None,
                "mention_count": len(mentions),
                "entity_statuses": {entity.name: get_entity_review_status(entity) for entity in entities},
                "entity_quality": {
                    entity.name: (entity.extra_data or {}).get("quality")
                    for entity in entities
                },
            }

    result = _run(scenario())

    assert result["run_status"] == "completed"
    assert result["run_prompt_routing"]["task"] == "entity_extraction"
    assert result["run_stats"]["created"] >= 3
    assert result["mention_count"] >= 3
    assert result["entity_statuses"]["林澈"] in {"candidate", "approved"}
    assert result["entity_statuses"]["旧邮局"] in {"candidate", "approved"}
    assert result["entity_statuses"]["铜铃"] in {"candidate", "approved"}
    assert result["entity_quality"]["林澈"]["score"] >= 60


def test_auto_approved_extraction_persists_production_approval_record() -> None:
    async def scenario() -> list[StoryEntity]:
        from app.services.entity_review_service import run_candidate_entity_extraction

        token = uuid4().hex
        async with AsyncSessionLocal() as db:
            result = await run_candidate_entity_extraction(
                db,
                user_id=f"review-user-{token[:20]}",
                novel_id=f"review-novel-{token}",
                source_type="chapter",
                source_id=f"chapter-{token}",
                text="角色：林澈。场景：蓝晶车站。道具：黄铜星钥。事件：星门苏醒。",
                entity_types=["character", "scene", "prop", "event"],
                persist=True,
                allow_auto_approve=True,
            )
            return result["entities"]

    approved = [entity for entity in _run(scenario()) if entity.is_approved]

    assert approved
    assert all(
        (entity.attributes or {}).get("approval_record", {}).get("reason")
        == "entity_extraction_v2:auto_approve"
        for entity in approved
    )


def test_verified_deterministic_chapter_candidate_requires_explicit_auto_approval() -> None:
    async def scenario(*, allow_auto_approve: bool) -> str:
        from app.services.entity_review_service import run_candidate_entity_extraction
        from app.services.story_entity_lifecycle import get_entity_review_status

        token = uuid4().hex
        chapter_id = f"chapter-{token}"
        async with AsyncSessionLocal() as db:
            result = await run_candidate_entity_extraction(
                db,
                user_id=f"review-user-{token[:20]}",
                novel_id=f"review-novel-{token}",
                chapter_id=chapter_id,
                source_type="chapter",
                source_id=chapter_id,
                text="林澈说：必须关闭星门。",
                entity_types=["character"],
                persist=True,
                allow_auto_approve=allow_auto_approve,
                candidate_items=[{
                    "entity_type": "character",
                    "name": "林澈",
                    "canonical_name": "林澈",
                    "evidence": "林澈",
                    "evidence_span": "林澈",
                    "confidence": 100,
                    "source": "deterministic",
                    "attributes": {"visual_dna": {"identity_anchor": "林澈"}},
                }],
            )
            return get_entity_review_status(result["entities"][0])

    assert _run(scenario(allow_auto_approve=False)) == "candidate"
    assert _run(scenario(allow_auto_approve=True)) == "approved"


def test_chapter_extraction_persists_scoped_evidence_contract() -> None:
    async def scenario() -> dict:
        from app.services.entity_review_service import run_candidate_entity_extraction

        token = uuid4().hex
        chapter_id = f"chapter-{token}"
        content = "苏澜举起银蓝星灯，顾言守住北塔。"
        async with AsyncSessionLocal() as db:
            result = await run_candidate_entity_extraction(
                db, user_id=f"review-user-{token[:20]}",
                novel_id=f"review-novel-{token}", chapter_id=chapter_id,
                source_type="chapter", source_id=chapter_id, text=content,
                entity_types=["character", "prop"], persist=True,
                allow_auto_approve=True,
                candidate_items=[{
                    "entity_type": "character", "name": "苏澜",
                    "canonical_name": "苏澜", "description": "守灯师",
                    "evidence": "苏澜", "evidence_span": "苏澜",
                    "confidence": 95, "source": "deterministic",
                }],
            )
            return next(
                dict((entity.attributes or {}).get("evidence_contract") or {})
                for entity in result["entities"] if entity.name == "苏澜"
            )

    evidence = _run(scenario())

    assert evidence["status"] == "verified"
    assert evidence["source_excerpt"] == "苏澜"
    assert evidence["parser_version"] == "deterministic-extraction-v2"


def test_chapter_reextraction_refreshes_or_archives_stale_evidence() -> None:
    async def scenario() -> dict:
        from app.services.entity_review_service import run_candidate_entity_extraction
        from app.services.story_entity_lifecycle import (
            APPROVED,
            get_entity_review_status,
            set_entity_review_status,
        )

        token = uuid4().hex
        user_id = f"review-user-{token[:20]}"
        novel_id = f"review-novel-{token}"
        chapter_id = f"chapter-{token}"
        old_content = "旧序章。苏澜看见黑雾。他低声说：星灯会熄灭。"
        new_content = "新的序章内容。苏澜看见黑雾。影潮使低声说：星灯会熄灭。"
        old_hash = hashlib.sha256(old_content.encode("utf-8")).hexdigest()

        async with AsyncSessionLocal() as db:
            entities = []
            for name in ("苏澜", "他低声"):
                start = old_content.index(name)
                entity = StoryEntity(
                    id=f"review-entity-{uuid4()}", user_id=user_id,
                    novel_id=novel_id, chapter_id=chapter_id,
                    entity_type="character", name=name, evidence=name,
                    attributes={"evidence_contract": {
                        "status": "verified", "chapter_id": chapter_id,
                        "source_span": [start, start + len(name)],
                        "content_hash": old_hash, "source_excerpt": name,
                        "parser_version": "deterministic-extraction-v2",
                    }},
                )
                set_entity_review_status(entity, APPROVED, changed_by=user_id, reason="fixture")
                db.add(entity)
                entities.append(entity)
            await db.commit()

            await run_candidate_entity_extraction(
                db, user_id=user_id, novel_id=novel_id, chapter_id=chapter_id,
                source_type="chapter", source_id=chapter_id, text=new_content,
                entity_types=["character"], persist=True, allow_auto_approve=True,
                candidate_items=[{
                    "entity_type": "character", "name": "影潮使",
                    "canonical_name": "影潮使", "description": "反派",
                    "evidence": "影潮使", "evidence_span": "影潮使",
                    "confidence": 95, "source": "deterministic",
                }],
            )
            refreshed = [await db.get(StoryEntity, entity.id) for entity in entities]
            return {
                entity.name: {
                    "status": get_entity_review_status(entity),
                    "content_hash": (entity.attributes or {})["evidence_contract"]["content_hash"],
                }
                for entity in refreshed
            }

    result = _run(scenario())

    assert result["苏澜"]["status"] == "approved"
    assert result["苏澜"]["content_hash"] != result["他低声"]["content_hash"]
    assert result["他低声"]["status"] == "archived"


def test_v2_candidate_extraction_tracks_rejected_noise_without_production_visibility() -> None:
    async def scenario() -> dict:
        from app.services.entity_review_service import run_candidate_entity_extraction
        from app.services.story_entity_lifecycle import get_entity_review_status, query_story_entities_for_production

        user_id = f"review-user-{uuid4().hex[:20]}"
        novel_id = f"review-novel-{uuid4()}"
        async with AsyncSessionLocal() as db:
            result = await run_candidate_entity_extraction(
                db,
                user_id=user_id,
                novel_id=novel_id,
                source_type="novel",
                source_id=novel_id,
                text="道具：视觉钩。镜头序列：推镜、拉镜。",
                entity_types=["prop"],
                persist=True,
                persist_rejected=True,
            )
            entities = (
                await db.execute(
                    select(StoryEntity).where(StoryEntity.user_id == user_id, StoryEntity.novel_id == novel_id)
                )
            ).scalars().all()
            production = await query_story_entities_for_production(db, user_id=user_id, novel_id=novel_id)
            return {
                "rejected": result["stats"]["rejected"],
                "statuses": {entity.name: get_entity_review_status(entity) for entity in entities},
                "production_names": [entity.name for entity in production],
            }

    result = _run(scenario())

    assert result["rejected"] >= 1
    assert all(status == "rejected" for status in result["statuses"].values())
    assert result["production_names"] == []


def test_v2_candidate_extraction_is_non_destructive_on_existing_approved_entity() -> None:
    async def scenario() -> dict:
        from app.services.entity_review_service import run_candidate_entity_extraction
        from app.services.story_entity_lifecycle import APPROVED, get_entity_review_status, set_entity_review_status

        user_id = f"review-user-{uuid4().hex[:20]}"
        novel_id = f"review-novel-{uuid4()}"
        entity_id = f"review-entity-{uuid4()}"
        async with AsyncSessionLocal() as db:
            entity = StoryEntity(
                id=entity_id,
                user_id=user_id,
                novel_id=novel_id,
                entity_type="character",
                name="林澈",
                description="人工确认的主角描述",
                evidence="人工审核",
                is_approved=True,
            )
            set_entity_review_status(entity, APPROVED, changed_by=user_id, reason="manual approval")
            db.add(entity)
            await db.commit()

            await run_candidate_entity_extraction(
                db,
                user_id=user_id,
                novel_id=novel_id,
                source_type="novel",
                source_id=novel_id,
                text="角色：林澈。林澈站在旧邮局门口，握紧铜铃。",
                entity_types=["character"],
                persist=True,
            )
            refreshed = await db.get(StoryEntity, entity_id)
            return {
                "description": refreshed.description,
                "status": get_entity_review_status(refreshed),
                "quality": (refreshed.extra_data or {}).get("quality"),
            }

    result = _run(scenario())

    assert result["description"] == "人工确认的主角描述"
    assert result["status"] == "approved"
    assert result["quality"] is not None


def test_review_actions_write_feedback_and_keep_production_visibility_safe() -> None:
    async def scenario() -> dict:
        from app.models import EntityFeedback
        from app.services.entity_review_service import (
            approve_review_entity,
            get_entity_review_summary,
            reject_review_entity,
            run_candidate_entity_extraction,
        )
        from app.services.story_entity_lifecycle import get_entity_review_status, query_story_entities_for_production

        user_id = f"review-user-{uuid4().hex[:20]}"
        novel_id = f"review-novel-{uuid4()}"
        async with AsyncSessionLocal() as db:
            extraction = await run_candidate_entity_extraction(
                db,
                user_id=user_id,
                novel_id=novel_id,
                source_type="novel",
                source_id=novel_id,
                text="角色：林澈。角色：沈砚。林澈站在旧邮局门口，沈砚握紧铜铃。",
                entity_types=["character"],
                persist=True,
            )
            entities = sorted(extraction["entities"], key=lambda item: item.name)
            approved = await approve_review_entity(db, user_id=user_id, entity_id=entities[0].id, reason="clean evidence")
            rejected = await reject_review_entity(db, user_id=user_id, entity_id=entities[1].id, reason="not needed")
            feedback = (
                await db.execute(
                    select(EntityFeedback).where(EntityFeedback.user_id == user_id, EntityFeedback.entity_id.in_([entities[0].id, entities[1].id]))
                )
            ).scalars().all()
            production = await query_story_entities_for_production(db, user_id=user_id, novel_id=novel_id)
            summary = await get_entity_review_summary(db, user_id=user_id, novel_id=novel_id)
            return {
                "approved_status": get_entity_review_status(approved),
                "rejected_status": get_entity_review_status(rejected),
                "feedback_actions": sorted(item.action for item in feedback),
                "production_names": [item.name for item in production],
                "summary": summary,
            }

    result = _run(scenario())

    assert result["approved_status"] == "approved"
    assert result["rejected_status"] == "rejected"
    assert result["feedback_actions"] == ["approve", "reject"]
    assert len(result["production_names"]) == 1
    assert result["summary"]["counts"]["approved"] == 1
    assert result["summary"]["counts"]["rejected"] == 1


def test_merge_suggestions_group_duplicate_candidates_without_merging() -> None:
    async def scenario() -> dict:
        from app.services.entity_review_service import suggest_entity_merges
        from app.services.story_entity_lifecycle import CANDIDATE, set_entity_review_status

        user_id = f"review-user-{uuid4().hex[:20]}"
        novel_id = f"review-novel-{uuid4()}"
        async with AsyncSessionLocal() as db:
            first = StoryEntity(
                id=f"review-entity-{uuid4()}",
                user_id=user_id,
                novel_id=novel_id,
                entity_type="character",
                name="林澈",
                canonical_name="林澈",
                evidence="林澈站在旧邮局门口",
            )
            second = StoryEntity(
                id=f"review-entity-{uuid4()}",
                user_id=user_id,
                novel_id=novel_id,
                entity_type="character",
                name="林澈少年",
                canonical_name="林澈",
                evidence="少年林澈握紧铜铃",
            )
            for entity in (first, second):
                set_entity_review_status(entity, CANDIDATE, changed_by=user_id, reason="duplicate fixture")
                db.add(entity)
            await db.commit()

            suggestions = await suggest_entity_merges(db, user_id=user_id, novel_id=novel_id)
            count = (
                await db.execute(select(StoryEntity).where(StoryEntity.user_id == user_id, StoryEntity.novel_id == novel_id))
            ).scalars().all()
            return {"suggestions": suggestions, "entity_count": len(count)}

    result = _run(scenario())

    assert result["entity_count"] == 2
    assert result["suggestions"]
    assert result["suggestions"][0]["canonical_key"] == "character:林澈"
