from __future__ import annotations

import math

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.entity_review.schemas import PagedReviewEntities, ReviewEntityItem, ReviewSummary
from app.models import StoryEntity
from app.services.entity_review_service import get_entity_review_summary
from app.services.story_entity_lifecycle import get_entity_review_status


def _status_expression():
    lifecycle_status = StoryEntity.extra_data["lifecycle"]["status"].as_string()
    return func.coalesce(
        lifecycle_status,
        case((StoryEntity.is_approved.is_(True), "approved"), else_="legacy_active"),
    )


def _to_item(entity: StoryEntity) -> ReviewEntityItem:
    return ReviewEntityItem(
        id=entity.id,
        novel_id=entity.novel_id,
        chapter_id=entity.chapter_id,
        script_id=entity.script_id,
        entity_type=entity.entity_type,
        name=entity.name,
        canonical_name=entity.canonical_name,
        aliases=entity.aliases or [],
        description=entity.description,
        appearance=entity.appearance,
        visual_prompt=entity.visual_prompt,
        evidence=entity.evidence,
        confidence=entity.confidence or 0,
        source=entity.source or "deterministic",
        review_status=get_entity_review_status(entity),
        is_approved=bool(entity.is_approved),
        attributes=entity.attributes or {},
        relations=entity.relations or [],
        extra_data=entity.extra_data or {},
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


async def list_review_entities(
    db: AsyncSession,
    *,
    user_id: str,
    novel_id: str,
    page: int,
    page_size: int,
    entity_type: str | None = None,
    review_status: str | None = None,
    query: str | None = None,
    sort: str = "updated_desc",
) -> PagedReviewEntities:
    filters = [StoryEntity.user_id == user_id, StoryEntity.novel_id == novel_id]
    if entity_type:
        filters.append(StoryEntity.entity_type == entity_type)
    if review_status:
        filters.append(_status_expression() == review_status)
    orderings = {
        "updated_asc": (StoryEntity.updated_at.asc(), StoryEntity.id.asc()),
        "name_asc": (StoryEntity.name.asc(), StoryEntity.id.asc()),
        "quality_desc": (StoryEntity.confidence.desc(), StoryEntity.updated_at.desc(), StoryEntity.id.desc()),
    }
    ordering = orderings.get(sort, (StoryEntity.updated_at.desc(), StoryEntity.id.desc()))
    if query and (term := query.strip().casefold()):
        scoped = list((await db.execute(select(StoryEntity).where(*filters).order_by(*ordering))).scalars().all())
        matched = [
            entity for entity in scoped
            if term in " ".join([
                entity.name or "", entity.canonical_name or "", entity.description or "",
                entity.evidence or "", *(entity.aliases or []),
            ]).casefold()
        ]
        total = len(matched)
        entities = matched[(page - 1) * page_size:page * page_size]
    else:
        total = int((await db.execute(select(func.count(StoryEntity.id)).where(*filters))).scalar_one())
        entities = list((await db.execute(
            select(StoryEntity).where(*filters).order_by(*ordering)
            .offset((page - 1) * page_size).limit(page_size)
        )).scalars().all())
    raw_summary = await get_entity_review_summary(db, user_id=user_id, novel_id=novel_id)
    summary = ReviewSummary(total=sum(raw_summary.get("counts", {}).values()), **raw_summary)
    return PagedReviewEntities(
        items=[_to_item(entity) for entity in entities],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=math.ceil(total / page_size) if total else 0,
        summary=summary,
    )
