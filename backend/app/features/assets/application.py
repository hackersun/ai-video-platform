from __future__ import annotations

from typing import Optional

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.features.assets.schemas import AssetEntityOption, DeactivateAssetEntityResponse
from app.models import Asset, StoryEntity
from app.services.story_entity_lifecycle import (
    ARCHIVED,
    get_entity_review_status,
    query_story_entities_for_assets,
    set_entity_review_status,
)


async def list_asset_entity_options(
    db: AsyncSession,
    *,
    user_id: str,
    novel_id: Optional[str] = None,
    chapter_id: Optional[str] = None,
    script_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    limit: int = 200,
) -> list[AssetEntityOption]:
    entities = await query_story_entities_for_assets(
        db,
        user_id=user_id,
        novel_id=novel_id,
        chapter_id=chapter_id,
        script_id=script_id,
        entity_types=[entity_type] if entity_type else None,
        limit=None,
    )
    entities = entities[:limit]
    counts = await _active_asset_counts(db, user_id=user_id, entity_ids=[entity.id for entity in entities])
    return [
        AssetEntityOption(
            id=entity.id,
            name=entity.name,
            entity_type=entity.entity_type,
            novel_id=entity.novel_id,
            chapter_id=entity.chapter_id,
            script_id=entity.script_id,
            description=entity.description,
            appearance=entity.appearance,
            visual_prompt=entity.visual_prompt,
            lifecycle_status=get_entity_review_status(entity),
            active_asset_count=counts.get(entity.id, 0),
        )
        for entity in entities
    ]


async def _active_asset_counts(
    db: AsyncSession,
    *,
    user_id: str,
    entity_ids: list[str],
) -> dict[str, int]:
    if not entity_ids:
        return {}
    result = await db.execute(
        select(Asset.entity_id, func.count(Asset.id))
        .where(
            Asset.user_id == user_id,
            Asset.entity_id.in_(entity_ids),
            Asset.is_active.is_(True),
        )
        .group_by(Asset.entity_id)
    )
    return {str(entity_id): int(count or 0) for entity_id, count in result.all() if entity_id}


async def deactivate_asset_entity(
    db: AsyncSession,
    *,
    user_id: str,
    entity_id: str,
    reason: str,
) -> DeactivateAssetEntityResponse:
    entity = (
        await db.execute(
            select(StoryEntity).where(
                StoryEntity.id == entity_id,
                StoryEntity.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if entity is None:
        raise ValueError("制片对象不存在或无权访问")

    previous_status = get_entity_review_status(entity)
    result = await db.execute(
        update(Asset)
        .where(
            and_(
                Asset.user_id == user_id,
                Asset.entity_id == entity_id,
                Asset.is_active.is_(True),
            )
        )
        .values(is_active=False, updated_at=utc_now())
    )
    archived_count = int(result.rowcount or 0)
    if previous_status != ARCHIVED:
        set_entity_review_status(entity, ARCHIVED, changed_by=user_id, reason=reason)
    await db.commit()

    return DeactivateAssetEntityResponse(
        entity_id=entity.id,
        entity_name=entity.name,
        lifecycle_status=ARCHIVED,
        archived_asset_count=archived_count,
        already_inactive=previous_status == ARCHIVED and archived_count == 0,
    )
