from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - ensure all SQLAlchemy models are registered
from app.core.database import Base
from app.models import Asset, Novel, StoryBible, StoryEntity, Workflow
from app.services.episode_contract_service import lock_episode_contract, stable_hash
from app.services.production_graph_service import append_state_event


@pytest_asyncio.fixture()
async def db_session() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture()
async def seeded_workflow(db_session: AsyncSession) -> Workflow:
    user_id = f"user-{uuid4()}"
    novel_id = f"novel-{uuid4()}"
    workflow_id = f"workflow-{uuid4()}"
    character_id = f"character-{uuid4()}"
    scene_id = f"scene-{uuid4()}"
    prop_id = f"prop-{uuid4()}"

    db_session.add(
        Novel(
            id=novel_id,
            user_id=user_id,
            title="雾港铜铃",
            description="近未来港口悬疑故事",
        )
    )
    db_session.add(
        StoryBible(
            id=f"story-bible-{uuid4()}",
            user_id=user_id,
            novel_id=novel_id,
            title="雾港铜铃 Story Bible",
            style="冷色悬疑动漫风格",
            worldview="潮湿雾港与旧工业区",
            extra_data={
                "state_machine": {
                    "generated_at": "2026-01-01T00:00:00+00:00",
                    "current_state": {
                        "characters": {"沈砚": {"state": "追查中"}},
                        "scenes": {"旧码头": {"weather": "冷雾"}},
                        "props": {"铜铃": {"state": "线索"}},
                        "events": [{"name": "追查铜铃"}],
                    },
                }
            },
        )
    )
    db_session.add_all(
        [
            StoryEntity(
                id=character_id,
                user_id=user_id,
                novel_id=novel_id,
                entity_type="character",
                name="沈砚",
                attributes={"visual_dna": {"costume": "灰蓝长衫"}, "voice": "calm_male"},
                is_approved=True,
            ),
            StoryEntity(
                id=scene_id,
                user_id=user_id,
                novel_id=novel_id,
                entity_type="scene",
                name="旧码头",
                attributes={"scene_dna": {"weather": "冷雾"}},
                is_approved=True,
            ),
            StoryEntity(
                id=prop_id,
                user_id=user_id,
                novel_id=novel_id,
                entity_type="prop",
                name="铜铃",
                attributes={"prop_dna": {"material": "旧铜"}},
                is_approved=True,
            ),
        ]
    )
    db_session.add_all(
        [
            Asset(
                id=f"asset-{uuid4()}",
                user_id=user_id,
                novel_id=novel_id,
                category="character",
                asset_type="image",
                entity_id=character_id,
                entity_type="character",
                name="沈砚定稿",
                url="https://cdn.example.com/shen-yan.png",
                is_active=True,
                is_final=True,
            ),
            Asset(
                id=f"asset-{uuid4()}",
                user_id=user_id,
                novel_id=novel_id,
                category="scene",
                asset_type="image",
                entity_id=scene_id,
                entity_type="scene",
                name="旧码头定稿",
                url="https://cdn.example.com/dock.png",
                is_active=True,
                is_final=True,
            ),
            Asset(
                id=f"asset-{uuid4()}",
                user_id=user_id,
                novel_id=novel_id,
                category="prop",
                asset_type="image",
                entity_id=prop_id,
                entity_type="prop",
                name="铜铃定稿",
                url="https://cdn.example.com/bell.png",
                is_active=True,
                is_final=True,
            ),
        ]
    )
    workflow = Workflow(
        id=workflow_id,
        user_id=user_id,
        title="第一集生产工作流",
        status="running",
        novel_id=novel_id,
        metadata_={"existing": "kept"},
    )
    db_session.add(workflow)
    await db_session.commit()
    return workflow


@pytest.mark.asyncio
async def test_lock_episode_contract_stores_snapshot(
    db_session: AsyncSession,
    seeded_workflow: Workflow,
) -> None:
    contract = await lock_episode_contract(db_session, seeded_workflow.user_id, seeded_workflow.id)

    assert contract["contract_id"]
    assert contract["workflow_id"] == seeded_workflow.id
    assert contract["production_bible_hash"]
    assert "style_lock" in contract
    assert isinstance(contract["entity_locks"], list)

    refreshed = (
        await db_session.execute(select(Workflow).where(Workflow.id == seeded_workflow.id))
    ).scalar_one()
    assert refreshed.metadata_["existing"] == "kept"
    assert refreshed.metadata_["episode_contract"] == contract


def test_stable_hash_ignores_volatile_fields() -> None:
    assert stable_hash({"name": "A", "generated_at": "t1"}) == stable_hash(
        {"name": "A", "generated_at": "t2"}
    )


def test_stable_hash_ignores_top_level_entity_order() -> None:
    assert stable_hash({"characters": [{"entity_id": "b"}, {"entity_id": "a"}]}) == stable_hash(
        {"characters": [{"entity_id": "a"}, {"entity_id": "b"}]}
    )


def test_stable_hash_ignores_entity_asset_id_order() -> None:
    assert stable_hash({"characters": [{"entity_id": "a", "asset_ids": ["b", "a"]}]}) == stable_hash(
        {"characters": [{"entity_id": "a", "asset_ids": ["a", "b"]}]}
    )


def test_stable_hash_ignores_missing_requirement_item_order() -> None:
    assert stable_hash(
        {"missing_requirements": [{"code": "missing", "items": [{"entity_id": "b"}, {"entity_id": "a"}]}]}
    ) == stable_hash(
        {"missing_requirements": [{"code": "missing", "items": [{"entity_id": "a"}, {"entity_id": "b"}]}]}
    )


def test_stable_hash_changes_when_content_changes() -> None:
    assert stable_hash({"name": "A"}) != stable_hash({"name": "B"})


def test_stable_hash_changes_when_list_content_changes() -> None:
    assert stable_hash({"characters": [{"entity_id": "a"}, {"entity_id": "b"}]}) != stable_hash(
        {"characters": [{"entity_id": "a"}, {"entity_id": "c"}]}
    )


def test_stable_hash_preserves_ordered_timeline_lists() -> None:
    assert stable_hash({"state_machine": {"latest_events": [{"name": "A"}, {"name": "B"}]}}) != stable_hash(
        {"state_machine": {"latest_events": [{"name": "B"}, {"name": "A"}]}}
    )


@pytest.mark.asyncio
async def test_lock_episode_contract_keeps_production_bible_hash_stable(
    db_session: AsyncSession,
    seeded_workflow: Workflow,
) -> None:
    first_contract = await lock_episode_contract(
        db_session,
        seeded_workflow.user_id,
        seeded_workflow.id,
    )
    second_contract = await lock_episode_contract(
        db_session,
        seeded_workflow.user_id,
        seeded_workflow.id,
    )

    assert (
        second_contract["production_bible_hash"]
        == first_contract["production_bible_hash"]
    )


@pytest.mark.asyncio
async def test_lock_episode_contract_raises_404_when_workflow_missing(db_session: AsyncSession) -> None:
    with pytest.raises(HTTPException) as exc_info:
        await lock_episode_contract(db_session, "user-missing", "workflow-missing")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "工作流不存在"


@pytest.mark.asyncio
async def test_lock_episode_contract_raises_404_for_other_user(
    db_session: AsyncSession,
    seeded_workflow: Workflow,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        await lock_episode_contract(db_session, f"other-{uuid4()}", seeded_workflow.id)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "工作流不存在"


@pytest.mark.asyncio
async def test_lock_episode_contract_raises_400_without_novel_id(db_session: AsyncSession) -> None:
    workflow = Workflow(
        id=f"workflow-{uuid4()}",
        user_id=f"user-{uuid4()}",
        title="未绑定小说工作流",
        status="running",
        metadata_={},
    )
    db_session.add(workflow)
    await db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        await lock_episode_contract(db_session, workflow.user_id, workflow.id)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "工作流没有绑定小说"


@pytest.mark.asyncio
async def test_lock_episode_contract_stores_versioned_graph_opening_and_closing_state(
    db_session: AsyncSession,
    seeded_workflow: Workflow,
) -> None:
    seeded_workflow.metadata_ = {**(seeded_workflow.metadata_ or {}), "episode_index": 2}
    await db_session.commit()
    first = await append_state_event(
        db_session,
        user_id=seeded_workflow.user_id,
        novel_id=seeded_workflow.novel_id,
        episode_index=1,
        entity_id="prop-bell",
        event_type="prop_owner_changed",
        story_time={"episode_index": 1, "sequence": 1},
        production_time={"stage": "script"},
        before_state={},
        after_state={"owner": "character-shen"},
        approval_status="approved",
        approved_by=seeded_workflow.user_id,
    )
    second = await append_state_event(
        db_session,
        user_id=seeded_workflow.user_id,
        novel_id=seeded_workflow.novel_id,
        episode_index=2,
        entity_id="prop-bell",
        event_type="prop_owner_changed",
        story_time={"episode_index": 2, "sequence": 1},
        production_time={"stage": "review"},
        before_state={"owner": "character-shen"},
        after_state={"owner": "character-lin"},
        approval_status="approved",
        approved_by=seeded_workflow.user_id,
    )

    contract = await lock_episode_contract(db_session, seeded_workflow.user_id, seeded_workflow.id)

    assert contract["episode_index"] == 2
    assert contract["production_graph_version"] == 2
    assert len(contract["production_graph_hash"]) == 64
    assert contract["opening_state"]["entities"]["prop-bell"]["owner"] == "character-shen"
    assert contract["expected_closing_state"]["entities"]["prop-bell"]["owner"] == "character-lin"
    assert contract["relevant_event_ids"] == [first.id, second.id]


@pytest.mark.asyncio
async def test_lock_episode_contract_rejects_unresolved_production_graph_conflicts(
    db_session: AsyncSession,
    seeded_workflow: Workflow,
) -> None:
    seeded_workflow.metadata_ = {**(seeded_workflow.metadata_ or {}), "episode_index": 2}
    await db_session.commit()
    await append_state_event(
        db_session,
        user_id=seeded_workflow.user_id,
        novel_id=seeded_workflow.novel_id,
        episode_index=2,
        entity_id="prop-bell",
        event_type="prop_owner_changed",
        story_time={"episode_index": 2, "sequence": 1},
        production_time={"stage": "review"},
        before_state={"owner": "character-missing"},
        after_state={"owner": "character-lin"},
        approval_status="approved",
        approved_by=seeded_workflow.user_id,
    )

    with pytest.raises(HTTPException) as exc_info:
        await lock_episode_contract(db_session, seeded_workflow.user_id, seeded_workflow.id)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "production_graph_conflicted"
    assert exc_info.value.detail["unresolved_conflicts"]
