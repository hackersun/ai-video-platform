from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - ensure all SQLAlchemy models are registered
from app.core.database import Base
from app.models import Chapter, Novel, Script, Shot, StoryBible, StoryEntity, Storyboard
from app.services.entity_impact_service import analyze_entity_change_impact, mark_entity_change_impact_for_review
from app.services.series_production import SERIES_PLAN_KEY, build_series_plan, get_series_plan


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
async def seeded_novel_with_chapters(db_session: AsyncSession) -> Novel:
    user_id = f"user-{uuid4()}"
    novel = Novel(
        id=f"novel-{uuid4()}",
        user_id=user_id,
        title="整书拆集测试",
        description="少年在旧城中追查星光密信。",
        genre="fantasy",
        status="writing",
        extra_data={"existing": "preserved"},
    )
    chapters = [
        Chapter(
            id=f"chapter-{index}",
            novel_id=novel.id,
            user_id=user_id,
            title=f"第{index}章",
            content=f"第{index}章正文",
            chapter_number=index,
            word_count=1000 + index,
            status="completed",
        )
        for index in range(1, 6)
    ]
    db_session.add(novel)
    db_session.add_all(chapters)
    await db_session.flush()
    return novel


@pytest.mark.asyncio
async def test_build_series_plan_groups_chapters_into_episodes(
    db_session: AsyncSession,
    seeded_novel_with_chapters: Novel,
) -> None:
    plan = await build_series_plan(
        db_session,
        seeded_novel_with_chapters.user_id,
        novel_id=seeded_novel_with_chapters.id,
        target_episode_count=3,
    )

    assert len(plan["episodes"]) == 3
    assert plan["episodes"][0]["episode_index"] == 1
    assert plan["episodes"][0]["episode_number"] == 1
    assert plan["episodes"][0]["chapter_ids"] == ["chapter-1", "chapter-2"]
    assert plan["episodes"][0]["status"] == "planned"
    assert plan["episodes"][0]["carry_over_state"] == {"characters": [], "scenes": [], "props": [], "events": []}
    assert plan["episodes"][0]["workflow_id"] is None
    assert "continuity_summary" in plan["episodes"][0]
    assert plan["episodes"][0]["production_readiness"]["next_action"]["code"] == "generate_script"


@pytest.mark.asyncio
async def test_build_series_plan_carries_previous_episode_state(
    db_session: AsyncSession,
    seeded_novel_with_chapters: Novel,
) -> None:
    db_session.add(
        StoryBible(
            id=f"bible-{uuid4()}",
            user_id=seeded_novel_with_chapters.user_id,
            novel_id=seeded_novel_with_chapters.id,
            title="整书 Production Bible",
            style="冷色二维动漫",
            extra_data={
                "state_machine": {
                    "chapter_snapshots": [
                        {
                            "chapter_id": "chapter-1",
                            "chapter_number": 1,
                            "characters": {"沈砚": {"state": "追查铜铃"}},
                            "scenes": {"雾港旧码头": {"weather": "冷雾"}},
                            "props": {"铜铃": {"holder": "沈砚"}},
                            "events": [{"name": "追查铜铃"}],
                        },
                        {
                            "chapter_id": "chapter-2",
                            "chapter_number": 2,
                            "characters": {"沈砚": {"state": "发现旧码头暗号"}},
                            "props": {"铜铃": {"state": "发出异响"}},
                            "events": [{"name": "旧码头暗号出现"}],
                        },
                    ],
                }
            },
        )
    )
    await db_session.flush()

    plan = await build_series_plan(
        db_session,
        seeded_novel_with_chapters.user_id,
        novel_id=seeded_novel_with_chapters.id,
        chapters_per_episode=1,
    )

    assert plan["episodes"][0]["carry_over_state"] == {"characters": [], "scenes": [], "props": [], "events": []}
    assert plan["episodes"][1]["carry_over_state"] == {
        "characters": ["沈砚"],
        "scenes": ["雾港旧码头"],
        "props": ["铜铃"],
        "events": ["追查铜铃"],
    }


@pytest.mark.asyncio
async def test_build_series_plan_persists_on_novel_extra_data(
    db_session: AsyncSession,
    seeded_novel_with_chapters: Novel,
) -> None:
    plan = await build_series_plan(
        db_session,
        seeded_novel_with_chapters.user_id,
        novel_id=seeded_novel_with_chapters.id,
        target_episode_count=3,
    )

    await db_session.refresh(seeded_novel_with_chapters)
    extra_data = seeded_novel_with_chapters.extra_data
    assert extra_data["existing"] == "preserved"
    assert extra_data[SERIES_PLAN_KEY]["novel_id"] == seeded_novel_with_chapters.id
    assert extra_data[SERIES_PLAN_KEY]["episodes"][0]["chapter_ids"] == plan["episodes"][0]["chapter_ids"]

    saved_plan = await get_series_plan(db_session, seeded_novel_with_chapters.user_id, seeded_novel_with_chapters.id)
    assert saved_plan["episodes"][0]["chapter_ids"] == ["chapter-1", "chapter-2"]


@pytest.mark.asyncio
async def test_get_series_plan_normalizes_legacy_saved_episode_contract(
    db_session: AsyncSession,
    seeded_novel_with_chapters: Novel,
) -> None:
    seeded_novel_with_chapters.extra_data = {
        SERIES_PLAN_KEY: {
            "novel_id": seeded_novel_with_chapters.id,
            "episodes": [{"episode_number": 2}],
        }
    }
    await db_session.flush()

    saved_plan = await get_series_plan(db_session, seeded_novel_with_chapters.user_id, seeded_novel_with_chapters.id)

    assert saved_plan["episodes"][0]["episode_index"] == 2
    assert saved_plan["episodes"][0]["episode_number"] == 2
    assert saved_plan["episodes"][0]["carry_over_state"] == {"characters": [], "scenes": [], "props": [], "events": []}


@pytest.mark.asyncio
async def test_entity_change_impact_lists_affected_episodes_and_shots(
    db_session: AsyncSession,
    seeded_novel_with_chapters: Novel,
) -> None:
    entity = StoryEntity(
        id="entity-hero",
        user_id=seeded_novel_with_chapters.user_id,
        novel_id=seeded_novel_with_chapters.id,
        entity_type="character",
        name="沈砚",
        canonical_name="沈砚",
        aliases=["主角"],
        attributes={"role": "protagonist"},
    )
    script_1 = Script(
        id="script-1",
        user_id=seeded_novel_with_chapters.user_id,
        novel_id=seeded_novel_with_chapters.id,
        chapter_id="chapter-1",
        title="第一集剧本",
    )
    script_3 = Script(
        id="script-3",
        user_id=seeded_novel_with_chapters.user_id,
        novel_id=seeded_novel_with_chapters.id,
        chapter_id="chapter-3",
        title="第三集剧本",
    )
    storyboard_1 = Storyboard(
        id="storyboard-1",
        user_id=seeded_novel_with_chapters.user_id,
        novel_id=seeded_novel_with_chapters.id,
        script_id="script-1",
        title="第一集分镜",
    )
    storyboard_3 = Storyboard(
        id="storyboard-3",
        user_id=seeded_novel_with_chapters.user_id,
        novel_id=seeded_novel_with_chapters.id,
        script_id="script-3",
        title="第三集分镜",
    )
    shot_1 = Shot(
        id="shot-1",
        user_id=seeded_novel_with_chapters.user_id,
        storyboard_id="storyboard-1",
        shot_number=1,
        prompt="沈砚在旧城追查密信",
        character_refs=[{"character_id": "entity-hero", "name": "沈砚"}],
        extra_data={
            "novel_id": seeded_novel_with_chapters.id,
            "chapter_id": "chapter-1",
            "entity_refs": {"characters": [{"entity_id": "entity-hero", "name": "沈砚"}]},
        },
    )
    shot_3 = Shot(
        id="shot-3",
        user_id=seeded_novel_with_chapters.user_id,
        storyboard_id="storyboard-3",
        shot_number=2,
        prompt="主角在钟楼前看见星光",
        extra_data={
            "novel_id": seeded_novel_with_chapters.id,
            "chapter_id": "chapter-3",
            "entity_refs": {"characters": [{"entity_id": "entity-hero", "name": "沈砚"}]},
        },
    )
    db_session.add_all([entity, script_1, script_3, storyboard_1, storyboard_3, shot_1, shot_3])
    await db_session.flush()

    await build_series_plan(
        db_session,
        seeded_novel_with_chapters.user_id,
        novel_id=seeded_novel_with_chapters.id,
        chapters_per_episode=1,
    )

    impact = await analyze_entity_change_impact(db_session, seeded_novel_with_chapters.user_id, "entity-hero")

    assert impact["entity"]["id"] == "entity-hero"
    assert impact["affected_episode_count"] == 5
    assert impact["affected_shot_count"] == 2
    assert impact["episodes"][0]["episode_index"] == 1
    assert impact["episodes"][0]["affected_shot_count"] == 1
    assert impact["episodes"][0]["affected_shots"][0]["id"] == "shot-1"
    assert impact["episodes"][2]["episode_index"] == 3
    assert impact["episodes"][2]["affected_shots"][0]["id"] == "shot-3"
    assert impact["apply_options"][0]["episode_index"] == 1
    assert "从第 1 集起应用" in impact["apply_options"][0]["label"]


@pytest.mark.asyncio
async def test_entity_change_impact_uses_storyboard_content_chapter_id(
    db_session: AsyncSession,
    seeded_novel_with_chapters: Novel,
) -> None:
    entity = StoryEntity(
        id="entity-storyboard-chapter",
        user_id=seeded_novel_with_chapters.user_id,
        novel_id=seeded_novel_with_chapters.id,
        entity_type="character",
        name="林晚",
    )
    script = Script(
        id="script-without-chapter",
        user_id=seeded_novel_with_chapters.user_id,
        novel_id=seeded_novel_with_chapters.id,
        title="未绑定章节剧本",
    )
    storyboard = Storyboard(
        id="storyboard-content-chapter",
        user_id=seeded_novel_with_chapters.user_id,
        novel_id=seeded_novel_with_chapters.id,
        script_id=script.id,
        title="分镜内容带章节",
        content={"chapter_id": "chapter-2"},
    )
    shot = Shot(
        id="shot-content-chapter",
        user_id=seeded_novel_with_chapters.user_id,
        storyboard_id=storyboard.id,
        shot_number=1,
        prompt="林晚在庭院中回望",
        extra_data={
            "entity_refs": {"characters": [{"entity_id": entity.id, "name": "林晚"}]},
        },
    )
    db_session.add_all([entity, script, storyboard, shot])
    await db_session.flush()

    await build_series_plan(
        db_session,
        seeded_novel_with_chapters.user_id,
        novel_id=seeded_novel_with_chapters.id,
        chapters_per_episode=1,
    )

    impact = await analyze_entity_change_impact(db_session, seeded_novel_with_chapters.user_id, entity.id)

    assert impact["episodes"][0]["episode_index"] == 2
    assert impact["episodes"][0]["affected_shot_count"] == 1
    assert impact["episodes"][0]["affected_shots"][0]["id"] == shot.id


@pytest.mark.asyncio
async def test_entity_change_impact_accepts_legacy_singular_entity_refs(
    db_session: AsyncSession,
    seeded_novel_with_chapters: Novel,
) -> None:
    entity = StoryEntity(
        id="entity-legacy-ref",
        user_id=seeded_novel_with_chapters.user_id,
        novel_id=seeded_novel_with_chapters.id,
        entity_type="character",
        name="旧引用角色",
    )
    script = Script(
        id="script-legacy-ref",
        user_id=seeded_novel_with_chapters.user_id,
        novel_id=seeded_novel_with_chapters.id,
        chapter_id="chapter-2",
        title="历史引用剧本",
    )
    storyboard = Storyboard(
        id="storyboard-legacy-ref",
        user_id=seeded_novel_with_chapters.user_id,
        novel_id=seeded_novel_with_chapters.id,
        script_id=script.id,
        title="历史引用分镜",
    )
    shot = Shot(
        id="shot-legacy-ref",
        user_id=seeded_novel_with_chapters.user_id,
        storyboard_id=storyboard.id,
        shot_number=1,
        prompt="旧引用角色进入画面",
        extra_data={
            "entity_refs": {"character": [{"entity_id": entity.id, "name": "旧引用角色"}]},
        },
    )
    db_session.add_all([entity, script, storyboard, shot])
    await db_session.flush()

    await build_series_plan(
        db_session,
        seeded_novel_with_chapters.user_id,
        novel_id=seeded_novel_with_chapters.id,
        chapters_per_episode=1,
    )

    impact = await analyze_entity_change_impact(db_session, seeded_novel_with_chapters.user_id, entity.id)

    assert impact["affected_shot_count"] == 1
    assert impact["episodes"][0]["episode_index"] == 2
    assert impact["episodes"][0]["affected_shots"][0]["id"] == shot.id


@pytest.mark.asyncio
async def test_entity_change_review_plan_marks_shots_from_selected_episode(
    db_session: AsyncSession,
    seeded_novel_with_chapters: Novel,
) -> None:
    entity = StoryEntity(
        id="entity-review-plan",
        user_id=seeded_novel_with_chapters.user_id,
        novel_id=seeded_novel_with_chapters.id,
        entity_type="character",
        name="沈砚",
        version=3,
    )
    script_1 = Script(
        id="script-review-1",
        user_id=seeded_novel_with_chapters.user_id,
        novel_id=seeded_novel_with_chapters.id,
        chapter_id="chapter-1",
        title="第一集剧本",
    )
    script_3 = Script(
        id="script-review-3",
        user_id=seeded_novel_with_chapters.user_id,
        novel_id=seeded_novel_with_chapters.id,
        chapter_id="chapter-3",
        title="第三集剧本",
    )
    storyboard_1 = Storyboard(
        id="storyboard-review-1",
        user_id=seeded_novel_with_chapters.user_id,
        novel_id=seeded_novel_with_chapters.id,
        script_id=script_1.id,
        title="第一集分镜",
    )
    storyboard_3 = Storyboard(
        id="storyboard-review-3",
        user_id=seeded_novel_with_chapters.user_id,
        novel_id=seeded_novel_with_chapters.id,
        script_id=script_3.id,
        title="第三集分镜",
    )
    shot_1 = Shot(
        id="shot-review-1",
        user_id=seeded_novel_with_chapters.user_id,
        storyboard_id=storyboard_1.id,
        shot_number=1,
        prompt="沈砚在旧城追查密信",
        character_refs=[{"character_id": entity.id, "name": "沈砚"}],
        extra_data={"production_context": {"review_state": "approved"}},
    )
    shot_3 = Shot(
        id="shot-review-3",
        user_id=seeded_novel_with_chapters.user_id,
        storyboard_id=storyboard_3.id,
        shot_number=2,
        prompt="沈砚在钟楼前看见星光",
        character_refs=[{"character_id": entity.id, "name": "沈砚"}],
        extra_data={"production_context": {"review_state": "approved"}},
    )
    db_session.add_all([entity, script_1, script_3, storyboard_1, storyboard_3, shot_1, shot_3])
    await db_session.flush()

    await build_series_plan(
        db_session,
        seeded_novel_with_chapters.user_id,
        novel_id=seeded_novel_with_chapters.id,
        chapters_per_episode=1,
    )

    plan = await mark_entity_change_impact_for_review(
        db_session,
        seeded_novel_with_chapters.user_id,
        "entity-review-plan",
        episode_index=3,
        change_note="服装主色改为深蓝",
    )

    await db_session.refresh(shot_1)
    await db_session.refresh(shot_3)

    assert plan["status"] == "review_plan_created"
    assert plan["episode_index"] == 3
    assert plan["marked_shot_count"] == 1
    assert plan["shot_ids"] == ["shot-review-3"]
    assert not (shot_1.extra_data or {}).get("needs_review")
    shot_3_extra = shot_3.extra_data or {}
    assert shot_3_extra["needs_review"] is True
    assert "从第 3 集起应用新设定" in shot_3_extra["review_reason"]
    assert shot_3_extra["production_context"]["review_state"] == "changes_requested"
    assert shot_3_extra["production_context"]["continuity_change"]["entity_id"] == entity.id
    assert shot_3_extra["production_context"]["continuity_change"]["change_note"] == "服装主色改为深蓝"


@pytest.mark.asyncio
async def test_entity_change_review_plan_rejects_empty_shot_plan(
    db_session: AsyncSession,
    seeded_novel_with_chapters: Novel,
) -> None:
    entity = StoryEntity(
        id="entity-empty-review-plan",
        user_id=seeded_novel_with_chapters.user_id,
        novel_id=seeded_novel_with_chapters.id,
        entity_type="character",
        name="无镜头角色",
    )
    db_session.add(entity)
    await db_session.flush()

    await build_series_plan(
        db_session,
        seeded_novel_with_chapters.user_id,
        novel_id=seeded_novel_with_chapters.id,
        chapters_per_episode=1,
    )

    with pytest.raises(Exception) as exc_info:
        await mark_entity_change_impact_for_review(
            db_session,
            seeded_novel_with_chapters.user_id,
            "entity-empty-review-plan",
            episode_index=1,
        )

    assert getattr(exc_info.value, "status_code", None) == 404
    assert "镜头" in str(getattr(exc_info.value, "detail", ""))
