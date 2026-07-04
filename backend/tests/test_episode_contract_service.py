from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - ensure all SQLAlchemy models are registered
from app.core.database import Base
from app.models import Asset, Novel, StoryBible, StoryEntity, Workflow
from app.services.episode_contract_service import lock_episode_contract


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
