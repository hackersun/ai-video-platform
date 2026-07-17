from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models import EntityFeedback, StoryEntity
from init_db import init_db


@pytest.fixture(scope="module", autouse=True)
def _init_database() -> None:
    init_db()


def _run(coro):
    return asyncio.run(coro)


def test_targeted_enrichment_only_updates_requested_entity_type_and_name() -> None:
    async def scenario() -> dict:
        from app.services.entity_targeted_enrichment_service import enrich_target_entity
        from app.services.story_entity_lifecycle import CANDIDATE, get_entity_review_status

        user_id = f"enrich-user-{uuid4().hex[:20]}"
        novel_id = f"enrich-novel-{uuid4()}"
        async with AsyncSessionLocal() as db:
            result = await enrich_target_entity(
                db,
                user_id=user_id,
                novel_id=novel_id,
                text="沈砚戴着裂纹银面具，站在旧邮局门口，手里没有铜铃。场景：旧邮局。道具：铜铃。",
                entity_type="character",
                entity_name="沈砚",
                fields=["description", "appearance", "evidence"],
                mode="merge_candidate",
            )
            entities = (
                await db.execute(select(StoryEntity).where(StoryEntity.user_id == user_id, StoryEntity.novel_id == novel_id))
            ).scalars().all()
            return {
                "result": result,
                "entities": [(entity.entity_type, entity.name, get_entity_review_status(entity)) for entity in entities],
                "description": entities[0].description,
                "appearance": entities[0].appearance,
                "status": get_entity_review_status(entities[0]),
            }

    result = _run(scenario())

    assert result["entities"] == [("character", "沈砚", "candidate")]
    assert "沈砚" in result["description"]
    assert result["appearance"] is not None
    assert result["result"]["prompt_routing"]["task"] == "entity_extraction"


def test_targeted_enrichment_does_not_overwrite_approved_scalar_fields_without_confirmation() -> None:
    async def scenario() -> dict:
        from app.services.entity_targeted_enrichment_service import enrich_target_entity
        from app.services.story_entity_lifecycle import APPROVED, get_entity_review_status, set_entity_review_status

        user_id = f"enrich-user-{uuid4().hex[:20]}"
        novel_id = f"enrich-novel-{uuid4()}"
        async with AsyncSessionLocal() as db:
            entity = StoryEntity(
                id=f"enrich-entity-{uuid4()}",
                user_id=user_id,
                novel_id=novel_id,
                entity_type="character",
                name="沈砚",
                description="人工定稿描述",
                aliases=["沈少爷"],
                relations=[{"target": "林澈", "type": "同伴"}],
                evidence="人工审核",
                is_approved=True,
            )
            set_entity_review_status(entity, APPROVED, changed_by=user_id, reason="fixture")
            db.add(entity)
            await db.commit()

            result = await enrich_target_entity(
                db,
                user_id=user_id,
                novel_id=novel_id,
                target_entity_id=entity.id,
                text="沈砚又名阿砚，与林澈在旧邮局结盟。沈砚戴着裂纹银面具。",
                entity_type="character",
                entity_name="沈砚",
                fields=["description", "appearance", "aliases", "relations", "evidence"],
                mode="merge_candidate",
            )
            refreshed = await db.get(StoryEntity, entity.id)
            feedback = (
                await db.execute(select(EntityFeedback).where(EntityFeedback.user_id == user_id, EntityFeedback.entity_id == entity.id))
            ).scalars().all()
            return {
                "description": refreshed.description,
                "appearance": refreshed.appearance,
                "aliases": refreshed.aliases,
                "relations": refreshed.relations,
                "status": get_entity_review_status(refreshed),
                "pending": (refreshed.extra_data or {}).get("pending_enrichment"),
                "feedback_actions": [item.action for item in feedback],
                "merge_policy": result["merge_policy"],
            }

    result = _run(scenario())

    assert result["description"] == "人工定稿描述"
    assert result["appearance"] is None
    assert "沈少爷" in result["aliases"]
    assert result["status"] == "approved"
    assert result["pending"]["proposed_patch"]["appearance"]
    assert result["feedback_actions"] == ["targeted_enrichment"]
    assert result["merge_policy"] == "pending_for_approved"
