"""Lifecycle and visibility helpers for StoryEntity records.

The first rollout keeps legacy StoryEntity rows production-visible while new
AI extraction candidates can be reviewed without leaking into prompts, assets,
or production packs.
"""

from __future__ import annotations

from typing import Any, Iterable, List, Optional

from sqlalchemy import and_, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.models import StoryEntity

LEGACY_ACTIVE = "legacy_active"
CANDIDATE = "candidate"
APPROVED = "approved"
REJECTED = "rejected"
ARCHIVED = "archived"

PRODUCTION_VISIBLE_STATUSES = {LEGACY_ACTIVE, APPROVED}
REVIEW_VISIBLE_STATUSES = {LEGACY_ACTIVE, CANDIDATE, APPROVED}
HIDDEN_STATUSES = {REJECTED, ARCHIVED}


def _json_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _lifecycle(entity: StoryEntity) -> dict[str, Any]:
    extra = _json_dict(getattr(entity, "extra_data", None))
    return _json_dict(extra.get("lifecycle"))


def get_entity_review_status(entity: StoryEntity) -> str:
    """Return the normalized lifecycle status for a StoryEntity."""
    status = str(_lifecycle(entity).get("status") or "").strip()
    if status in {CANDIDATE, APPROVED, REJECTED, ARCHIVED}:
        return status
    if bool(getattr(entity, "is_approved", False)):
        return APPROVED
    return LEGACY_ACTIVE


def set_entity_review_status(
    entity: StoryEntity,
    status: str,
    *,
    changed_by: Optional[str] = None,
    reason: Optional[str] = None,
) -> None:
    """Set review lifecycle metadata without losing unrelated extra_data."""
    if status not in {CANDIDATE, APPROVED, REJECTED, ARCHIVED, LEGACY_ACTIVE}:
        raise ValueError(f"Unsupported StoryEntity lifecycle status: {status}")

    previous_status = get_entity_review_status(entity)
    extra = dict(_json_dict(getattr(entity, "extra_data", None)))
    lifecycle = dict(_json_dict(extra.get("lifecycle")))
    lifecycle.update(
        {
            "status": status,
            "previous_status": previous_status,
            "changed_at": utc_now().isoformat(),
        }
    )
    if changed_by:
        lifecycle["changed_by"] = changed_by
    if reason:
        lifecycle["reason"] = reason
    extra["lifecycle"] = lifecycle
    entity.extra_data = extra
    entity.is_approved = status == APPROVED
    entity.updated_at = utc_now()


def is_entity_reviewable(entity: StoryEntity) -> bool:
    return get_entity_review_status(entity) in REVIEW_VISIBLE_STATUSES


def is_entity_production_visible(entity: StoryEntity) -> bool:
    return get_entity_review_status(entity) in PRODUCTION_VISIBLE_STATUSES


def is_entity_asset_generation_allowed(
    entity: StoryEntity,
    *,
    allow_candidate_assets: bool = False,
) -> bool:
    status = get_entity_review_status(entity)
    return status in PRODUCTION_VISIBLE_STATUSES or (allow_candidate_assets and status == CANDIDATE)


def filter_story_entities_for_production(entities: Iterable[StoryEntity]) -> List[StoryEntity]:
    return [entity for entity in entities if is_entity_production_visible(entity)]


def filter_story_entities_for_review(entities: Iterable[StoryEntity]) -> List[StoryEntity]:
    return [entity for entity in entities if is_entity_reviewable(entity)]


def _base_query(user_id: str):
    return select(StoryEntity).where(StoryEntity.user_id == user_id)


def _apply_scope_filters(
    query,
    *,
    novel_id: Optional[str] = None,
    chapter_id: Optional[str] = None,
    script_id: Optional[str] = None,
    include_global_novel_entities: bool = True,
):
    if novel_id:
        if include_global_novel_entities:
            query = query.where(or_(StoryEntity.novel_id == novel_id, StoryEntity.novel_id.is_(None)))
        else:
            query = query.where(StoryEntity.novel_id == novel_id)
    if chapter_id:
        query = query.where(or_(StoryEntity.chapter_id == chapter_id, StoryEntity.chapter_id.is_(None)))
    if script_id:
        query = query.where(or_(StoryEntity.script_id == script_id, StoryEntity.script_id.is_(None)))
    return query


async def query_story_entities_for_review(
    db: AsyncSession,
    *,
    user_id: str,
    novel_id: Optional[str] = None,
    chapter_id: Optional[str] = None,
    script_id: Optional[str] = None,
    entity_types: Optional[Iterable[str]] = None,
    limit: Optional[int] = None,
) -> List[StoryEntity]:
    """Load entities for review/admin surfaces, including candidates."""
    query = _apply_scope_filters(
        _base_query(user_id),
        novel_id=novel_id,
        chapter_id=chapter_id,
        script_id=script_id,
    )
    if entity_types:
        query = query.where(StoryEntity.entity_type.in_(list(entity_types)))
    query = query.order_by(StoryEntity.created_at)
    if limit:
        query = query.limit(limit)
    result = await db.execute(query)
    return filter_story_entities_for_review(result.scalars().all())


async def query_story_entities_for_production(
    db: AsyncSession,
    *,
    user_id: str,
    novel_id: Optional[str] = None,
    chapter_id: Optional[str] = None,
    script_id: Optional[str] = None,
    include_global_novel_entities: bool = False,
    entity_types: Optional[Iterable[str]] = None,
    limit: Optional[int] = None,
    order_recent: bool = False,
) -> List[StoryEntity]:
    """Load entities that are safe for prompts, assets, and production packs."""
    query = _apply_scope_filters(
        _base_query(user_id),
        novel_id=novel_id,
        chapter_id=chapter_id,
        script_id=script_id,
        include_global_novel_entities=include_global_novel_entities or not novel_id,
    )
    if entity_types:
        query = query.where(StoryEntity.entity_type.in_(list(entity_types)))
    if order_recent:
        query = query.order_by(desc(StoryEntity.updated_at))
    else:
        query = query.order_by(StoryEntity.created_at)
    if limit:
        query = query.limit(limit)
    result = await db.execute(query)
    return filter_story_entities_for_production(result.scalars().all())


async def query_story_entity_for_production(
    db: AsyncSession,
    *,
    user_id: str,
    entity_id: str,
) -> Optional[StoryEntity]:
    """Load one entity only when it is safe for production consumers."""
    result = await db.execute(
        _base_query(user_id).where(StoryEntity.id == entity_id)
    )
    entity = result.scalar_one_or_none()
    if entity is None or not is_entity_production_visible(entity):
        return None
    return entity


async def query_story_entities_for_prompt_context(
    db: AsyncSession,
    *,
    user_id: str,
    novel_id: Optional[str] = None,
    chapter_id: Optional[str] = None,
    script_id: Optional[str] = None,
    include_global_novel_entities: bool = False,
    limit: Optional[int] = None,
) -> List[StoryEntity]:
    return await query_story_entities_for_production(
        db,
        user_id=user_id,
        novel_id=novel_id,
        chapter_id=chapter_id,
        script_id=script_id,
        include_global_novel_entities=include_global_novel_entities,
        limit=limit,
        order_recent=True,
    )


async def query_story_entities_for_assets(
    db: AsyncSession,
    *,
    user_id: str,
    novel_id: Optional[str] = None,
    chapter_id: Optional[str] = None,
    script_id: Optional[str] = None,
    include_global_novel_entities: bool = False,
    entity_types: Optional[Iterable[str]] = None,
    allow_candidate_assets: bool = False,
    limit: Optional[int] = None,
) -> List[StoryEntity]:
    query = _apply_scope_filters(
        _base_query(user_id),
        novel_id=novel_id,
        chapter_id=chapter_id,
        script_id=script_id,
        include_global_novel_entities=include_global_novel_entities or not novel_id,
    )
    if entity_types:
        query = query.where(StoryEntity.entity_type.in_(list(entity_types)))
    query = query.order_by(StoryEntity.entity_type, StoryEntity.name)
    if limit:
        query = query.limit(limit)
    result = await db.execute(query)
    return [
        entity
        for entity in result.scalars().all()
        if is_entity_asset_generation_allowed(entity, allow_candidate_assets=allow_candidate_assets)
    ]
