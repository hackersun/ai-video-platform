from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models import Asset, Novel, StoryEntity
from app.services.story_entity_lifecycle import (
    APPROVED,
    ARCHIVED,
    CANDIDATE,
    REJECTED,
    get_entity_review_status,
    set_entity_review_status,
)
from init_db import init_db


@pytest.fixture(scope="module", autouse=True)
def _init_database() -> None:
    init_db()


def _run(coro):
    return asyncio.run(coro)


def _entity(*, user_id: str, novel_id: str, name: str, lifecycle: str | None = None) -> StoryEntity:
    entity = StoryEntity(
        id=f"asset-entity-{uuid4()}",
        user_id=user_id,
        novel_id=novel_id,
        entity_type="character",
        name=name,
        source="manual",
    )
    if lifecycle:
        set_entity_review_status(entity, lifecycle, changed_by=user_id, reason="test setup")
    return entity


def _asset(*, user_id: str, novel_id: str, entity_id: str, name: str, active: bool = True) -> Asset:
    return Asset(
        id=f"asset-maintenance-{uuid4()}",
        user_id=user_id,
        novel_id=novel_id,
        entity_id=entity_id,
        entity_type="character",
        category="character",
        asset_type="image",
        name=name,
        is_active=active,
    )


def test_asset_entity_options_use_production_visibility_and_count_only_active_assets() -> None:
    async def scenario():
        from app.features.assets.application import list_asset_entity_options

        user_id = f"asset-options-user-{uuid4().hex[:16]}"
        novel_id = f"asset-options-novel-{uuid4()}"
        legacy = _entity(user_id=user_id, novel_id=novel_id, name="旧角色")
        approved = _entity(user_id=user_id, novel_id=novel_id, name="已定稿角色", lifecycle=APPROVED)
        candidate = _entity(user_id=user_id, novel_id=novel_id, name="候选角色", lifecycle=CANDIDATE)
        rejected = _entity(user_id=user_id, novel_id=novel_id, name="驳回角色", lifecycle=REJECTED)
        archived = _entity(user_id=user_id, novel_id=novel_id, name="停用角色", lifecycle=ARCHIVED)

        async with AsyncSessionLocal() as db:
            db.add(Novel(id=novel_id, user_id=user_id, title="资产对象选项测试"))
            db.add_all([legacy, approved, candidate, rejected, archived])
            db.add_all(
                [
                    _asset(user_id=user_id, novel_id=novel_id, entity_id=legacy.id, name="旧角色正面"),
                    _asset(user_id=user_id, novel_id=novel_id, entity_id=legacy.id, name="旧角色历史", active=False),
                    _asset(user_id=user_id, novel_id=novel_id, entity_id=approved.id, name="已定稿角色正面"),
                    _asset(user_id=user_id, novel_id=novel_id, entity_id=approved.id, name="已定稿角色侧面"),
                ]
            )
            await db.commit()

            options = await list_asset_entity_options(
                db,
                user_id=user_id,
                novel_id=novel_id,
                entity_type="character",
                limit=100,
            )

        return options

    options = _run(scenario())

    assert [(item.name, item.lifecycle_status, item.active_asset_count) for item in options] == [
        ("已定稿角色", APPROVED, 2),
        ("旧角色", "legacy_active", 1),
    ]


def test_deactivate_asset_entity_archives_entity_and_all_active_assets_idempotently() -> None:
    async def scenario():
        from app.features.assets.application import deactivate_asset_entity

        user_id = f"asset-deactivate-user-{uuid4().hex[:16]}"
        novel_id = f"asset-deactivate-novel-{uuid4()}"
        entity = _entity(user_id=user_id, novel_id=novel_id, name="待停用角色", lifecycle=APPROVED)
        active_assets = [
            _asset(user_id=user_id, novel_id=novel_id, entity_id=entity.id, name="正面"),
            _asset(user_id=user_id, novel_id=novel_id, entity_id=entity.id, name="侧面"),
        ]
        inactive_asset = _asset(
            user_id=user_id,
            novel_id=novel_id,
            entity_id=entity.id,
            name="历史版本",
            active=False,
        )

        async with AsyncSessionLocal() as db:
            db.add(Novel(id=novel_id, user_id=user_id, title="停用制片对象测试"))
            db.add(entity)
            db.add_all([*active_assets, inactive_asset])
            await db.commit()

            first = await deactivate_asset_entity(
                db,
                user_id=user_id,
                entity_id=entity.id,
                reason="用户从资产工作台停用",
            )
            second = await deactivate_asset_entity(
                db,
                user_id=user_id,
                entity_id=entity.id,
                reason="重复请求",
            )
            stored_entity = await db.get(StoryEntity, entity.id)
            stored_assets = (
                await db.execute(select(Asset).where(Asset.entity_id == entity.id).order_by(Asset.name))
            ).scalars().all()

        return first, second, stored_entity, stored_assets

    first, second, stored_entity, stored_assets = _run(scenario())

    assert first.archived_asset_count == 2
    assert first.already_inactive is False
    assert second.archived_asset_count == 0
    assert second.already_inactive is True
    assert get_entity_review_status(stored_entity) == ARCHIVED
    assert all(asset.is_active is False for asset in stored_assets)


def test_asset_entity_option_limit_is_applied_after_lifecycle_filtering() -> None:
    async def scenario():
        from app.features.assets.application import list_asset_entity_options

        user_id = f"asset-limit-user-{uuid4().hex[:16]}"
        novel_id = f"asset-limit-novel-{uuid4()}"
        async with AsyncSessionLocal() as db:
            db.add(Novel(id=novel_id, user_id=user_id, title="过滤后限额测试"))
            db.add_all(
                [
                    _entity(user_id=user_id, novel_id=novel_id, name="A-已停用", lifecycle=ARCHIVED),
                    _entity(user_id=user_id, novel_id=novel_id, name="Z-可制片", lifecycle=APPROVED),
                ]
            )
            await db.commit()
            return await list_asset_entity_options(
                db,
                user_id=user_id,
                novel_id=novel_id,
                entity_type="character",
                limit=1,
            )

    options = _run(scenario())

    assert [item.name for item in options] == ["Z-可制片"]


def test_asset_maintenance_router_exposes_option_and_deactivation_routes() -> None:
    from app.features.assets.api import router

    routes = {(route.path, tuple(route.methods or [])) for route in router.routes}

    assert ("/asset-maintenance/entity-options", ("GET",)) in routes
    assert ("/asset-maintenance/entities/{entity_id}/deactivate", ("POST",)) in routes
