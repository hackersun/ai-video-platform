from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.database import Base
from app.models import Chapter, Novel, Script, SeriesProductionRun, Shot, Storyboard, Workflow
from app.services.chapter_scene_planner import ChapterScenePlan
from app.services.episode_production_service import (
    create_or_resolve_script_stage,
    create_or_resolve_shots_stage,
    create_or_resolve_storyboard_stage,
)
from app.services.episode_storyboard_stage import _fallback_shots
from app.features.series_run_story_locks.application.production_scoped_inputs import (
    ProductionScopedRefCommand,
    _episode as resolve_production_episode,
    _workflow_storyboard_matches_episode,
)


@pytest_asyncio.fixture()
async def db_session(monkeypatch: pytest.MonkeyPatch) -> AsyncSession:
    monkeypatch.setenv("DEV_MODE", "true")
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_long_episode_creates_multiple_ordered_storyboards(db_session: AsyncSession) -> None:
    user_id, novel_id, run_id = str(uuid4()), str(uuid4()), str(uuid4())
    content = "\n\n".join([
        "【玄霜殿】\n" + "顾清霜检查星盘，沈砚守在门外。" * 45,
        "【断云桥】\n" + "两人穿过风雪，青铜剑匣发出鸣响。" * 45,
        "【归墟塔】\n" + "守塔人拦路，顾清霜拔剑迎战。" * 45,
    ])
    chapter = Chapter(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id, title="第三章", chapter_number=3, content=content,
    )
    script = Script(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id, chapter_id=chapter.id, title="第三集剧本",
        content=content, extra_data={
            "series_run_id": run_id, "episode_number": 3, "input_hash": "hash-3",
            "dialogue_lines": [
                {"speaker": "顾清霜", "spoken_text": "检查星盘", "dialogue": "顾清霜：检查星盘", "chapter_id": chapter.id},
                {"speaker": "沈砚", "spoken_text": "穿过风雪", "dialogue": "沈砚：穿过风雪", "chapter_id": chapter.id},
                {"speaker": "守塔人", "spoken_text": "拔剑迎战", "dialogue": "守塔人：拔剑迎战", "chapter_id": chapter.id},
            ],
        },
    )
    workflow = Workflow(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id, chapter_id=chapter.id, script_id=script.id,
        title="第三集", status="pending",
        metadata_={"series_run_id": run_id, "episode_number": 3, "input_hash": "hash-3"},
    )
    run = SeriesProductionRun(
        id=run_id, user_id=user_id, novel_id=novel_id, series_plan_version="v1",
        idempotency_key=str(uuid4()), status="episodes_building", run_metadata={}, episodes=[],
    )
    db_session.add_all([Novel(id=novel_id, user_id=user_id, title="归墟"), chapter, script, workflow, run])
    await db_session.flush()
    episode = {
        "episode_number": 3, "chapter_ids": [chapter.id], "input_hash": "hash-3",
        "canonical_ids": {"workflow_id": workflow.id, "script_id": script.id},
    }

    result = await create_or_resolve_storyboard_stage(db_session, run=run, episode=episode)

    assert len(result["storyboard_ids"]) >= 3
    assert result["storyboard_id"] == result["storyboard_ids"][0]
    boards = [await db_session.get(Storyboard, board_id) for board_id in result["storyboard_ids"]]
    assert [board.content["scene_index"] for board in boards] == list(range(1, len(boards) + 1))
    assert all(board.content["planned_shot_count"] >= 2 for board in boards)
    assert workflow.storyboard_id == boards[0].id
    for board in boards:
        board.content = {
            **board.content,
            "shots": [{**shot, "dialogue": "幻觉角色：并不存在"} for shot in board.content["shots"]],
        }

    episode["canonical_ids"].update(result)
    shot_result = await create_or_resolve_shots_stage(db_session, run=run, episode=episode)
    shots = list((await db_session.scalars(select(Shot).where(
        Shot.id.in_(shot_result["shot_ids"])
    ))).all())
    expected = sum(board.content["planned_shot_count"] for board in boards)
    assert len(shot_result["shot_ids"]) == expected
    assert len(shots) == expected
    assert all(board.shot_count == board.content["planned_shot_count"] for board in boards)
    shots_by_sequence = sorted(shots, key=lambda shot: int((shot.extra_data or {}).get("episode_shot_number") or 0))
    assert [shot.extra_data["episode_shot_number"] for shot in shots_by_sequence] == list(range(1, expected + 1))
    assert all(shot.extra_data["scene_count"] == len(boards) for shot in shots)
    assert all(shot.extra_data["scene_title"] for shot in shots)
    dialogue_by_scene = {
        board.content["scene_index"]: [
            shot.dialogue for shot in shots
            if shot.storyboard_id == board.id and shot.dialogue
        ]
        for board in boards
    }
    assert dialogue_by_scene == {
        1: ["顾清霜：检查星盘"],
        2: ["沈砚：穿过风雪"],
        3: ["守塔人：拔剑迎战"],
    }
    assert all(
        shot.extra_data["dialogue_source"]["binding_rule"] == "scene_text_unique_v1"
        for shot in shots if shot.dialogue
    )

    second_scene_shot = next(
        shot for shot in shots if shot.storyboard_id == boards[1].id and shot.dialogue
    )
    second_scene_shot.dialogue = "幻觉角色：错误对白"
    second_scene_shot.extra_data = {
        key: value for key, value in second_scene_shot.extra_data.items()
        if key not in {"dialogue_speaker", "parsed_speaker", "dialogue_spoken_text", "dialogue_source"}
    }

    repeated_boards = await create_or_resolve_storyboard_stage(db_session, run=run, episode=episode)
    repeated_shots = await create_or_resolve_shots_stage(db_session, run=run, episode=episode)
    assert repeated_boards == result
    assert repeated_shots["shot_ids"] == shot_result["shot_ids"]
    assert second_scene_shot.dialogue == "沈砚：穿过风雪"
    assert second_scene_shot.extra_data["dialogue_spoken_text"] == "穿过风雪"


@pytest.mark.asyncio
async def test_short_episode_keeps_single_legacy_storyboard(db_session: AsyncSession) -> None:
    user_id, novel_id, run_id = str(uuid4()), str(uuid4()), str(uuid4())
    chapter = Chapter(id=str(uuid4()), user_id=user_id, novel_id=novel_id, title="短章", chapter_number=1,
                      content="顾清霜推门而入。")
    script = Script(id=str(uuid4()), user_id=user_id, novel_id=novel_id, chapter_id=chapter.id, title="短剧本",
                    content=chapter.content,
                    extra_data={"series_run_id": run_id, "episode_number": 1, "input_hash": "hash-1"})
    workflow = Workflow(id=str(uuid4()), user_id=user_id, novel_id=novel_id, chapter_id=chapter.id,
                        script_id=script.id, title="第一集", status="pending",
                        metadata_={"series_run_id": run_id, "episode_number": 1, "input_hash": "hash-1"})
    run = SeriesProductionRun(
        id=run_id, user_id=user_id, novel_id=novel_id, series_plan_version="v1",
        idempotency_key=str(uuid4()), status="episodes_building", run_metadata={}, episodes=[],
    )
    db_session.add_all([Novel(id=novel_id, user_id=user_id, title="短篇"), chapter, script, workflow, run])
    await db_session.flush()
    episode = {"episode_number": 1, "chapter_ids": [chapter.id], "input_hash": "hash-1",
               "canonical_ids": {"workflow_id": workflow.id, "script_id": script.id}}

    result = await create_or_resolve_storyboard_stage(db_session, run=run, episode=episode)

    assert result["storyboard_ids"] == [result["storyboard_id"]]


def test_fallback_shots_use_ordered_distinct_source_slices() -> None:
    scene = ChapterScenePlan(
        scene_index=1,
        title="断云桥",
        source_text="顾清霜踏上断云桥。沈砚发现桥下浮起赤焰。两人拔剑迎向守桥傀儡。",
        shot_count=3,
        continuity={"previous_scene_index": None, "next_scene_index": 2},
    )

    shots = _fallback_shots(scene)

    assert [shot["visual_description"] for shot in shots] == [
        "顾清霜踏上断云桥。",
        "沈砚发现桥下浮起赤焰。",
        "两人拔剑迎向守桥傀儡。",
    ]


def test_production_owner_chain_accepts_every_canonical_scene_board() -> None:
    run = type("Run", (), {"episodes": [{
        "episode_number": 3,
        "chapter_ids": ["chapter-3"],
        "canonical_ids": {
            "workflow_id": "workflow-3",
            "storyboard_id": "board-3-1",
            "storyboard_ids": ["board-3-1", "board-3-2", "board-3-3"],
        },
    }]})()
    command = ProductionScopedRefCommand(
        run_id="run-3", user_id="user-3", novel_id="novel-3",
        workflow_id="workflow-3", storyboard_id="board-3-2", shot_id="shot-3-2-1",
        episode_number=3, episode_input_hash="hash-3", chapter_ids=("chapter-3",),
        chapter_id="chapter-3", script_id="script-3", prompt="", dialogue="",
        visual_description="", source_text="", shot_text="", entity_refs={},
    )

    resolved = resolve_production_episode(run, command)

    assert resolved["episode_number"] == 3


def test_workflow_primary_board_allows_scoped_refs_for_later_scene_board() -> None:
    episode = {
        "canonical_ids": {
            "storyboard_id": "board-1",
            "storyboard_ids": ["board-1", "board-2"],
        },
    }
    workflow = type("Workflow", (), {"storyboard_id": "board-1"})()

    assert _workflow_storyboard_matches_episode(workflow, episode, "board-2") is True


@pytest.mark.asyncio
async def test_legacy_whole_chapter_board_is_preserved_but_replaced_in_workflow(
    db_session: AsyncSession,
) -> None:
    user_id, novel_id, run_id = str(uuid4()), str(uuid4()), str(uuid4())
    content = "\n\n".join([
        "【雪林】\n" + "顾清霜追踪雪地足印。" * 50,
        "【赤焰殿】\n" + "沈砚在火海中夺回星盘。" * 50,
        "【天门】\n" + "众人登上石阶迎战守门人。" * 50,
    ])
    chapter = Chapter(id=str(uuid4()), user_id=user_id, novel_id=novel_id, title="第三章",
                      chapter_number=3, content=content)
    script = Script(id=str(uuid4()), user_id=user_id, novel_id=novel_id, chapter_id=chapter.id,
                    title="第三集剧本", content=content,
                    extra_data={"series_run_id": run_id, "episode_number": 3, "input_hash": "hash-3"})
    legacy = Storyboard(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id, script_id=script.id,
        title="第 3 集分镜草稿", shot_count=1, status="draft",
        content={"series_run_id": run_id, "episode_number": 3, "input_hash": "hash-3",
                 "shots": [{"shot_number": 1, "visual_description": content}]},
    )
    workflow = Workflow(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id, chapter_id=chapter.id,
        script_id=script.id, storyboard_id=legacy.id, title="第三集", status="pending",
        metadata_={"series_run_id": run_id, "episode_number": 3, "input_hash": "hash-3"},
    )
    run = SeriesProductionRun(
        id=run_id, user_id=user_id, novel_id=novel_id, series_plan_version="v1",
        idempotency_key=str(uuid4()), status="episodes_building", run_metadata={}, episodes=[],
    )
    db_session.add_all([Novel(id=novel_id, user_id=user_id, title="天门"), chapter, script,
                        legacy, workflow, run])
    await db_session.flush()
    episode = {"episode_number": 3, "chapter_ids": [chapter.id], "input_hash": "hash-3",
               "canonical_ids": {"workflow_id": workflow.id, "script_id": script.id}}

    result = await create_or_resolve_storyboard_stage(db_session, run=run, episode=episode)

    assert result["storyboard_id"] != legacy.id
    assert workflow.storyboard_id == result["storyboard_id"]
    assert await db_session.get(Storyboard, legacy.id) is legacy
    new_boards = [await db_session.get(Storyboard, item) for item in result["storyboard_ids"]]
    assert len(new_boards) >= 3
    assert all(board.content.get("chapter_id") == chapter.id for board in new_boards)
    assert all(board.content.get("source_text") for board in new_boards)


@pytest.mark.asyncio
async def test_existing_script_backfills_explicit_dialogue_lineage(db_session: AsyncSession) -> None:
    user_id, novel_id, run_id = str(uuid4()), str(uuid4()), str(uuid4())
    content = '沈砚低声提醒：“记住彼此的气息与装束。”众人随后进入赤焰殿。'
    chapter = Chapter(id=str(uuid4()), user_id=user_id, novel_id=novel_id, title="第一章",
                      chapter_number=1, content=content)
    script = Script(id=str(uuid4()), user_id=user_id, novel_id=novel_id, chapter_id=chapter.id,
                    title="第一集剧本", content=content,
                    extra_data={"series_run_id": run_id, "episode_number": 1,
                                "input_hash": "hash-1", "dialogue_lines": []})
    workflow = Workflow(id=str(uuid4()), user_id=user_id, novel_id=novel_id, chapter_id=chapter.id,
                        script_id=script.id, title="第一集", status="pending",
                        metadata_={"series_run_id": run_id, "episode_number": 1,
                                   "input_hash": "hash-1"})
    run = SeriesProductionRun(id=run_id, user_id=user_id, novel_id=novel_id,
                              series_plan_version="v1", idempotency_key=str(uuid4()),
                              status="episodes_building", run_metadata={}, episodes=[])
    db_session.add_all([Novel(id=novel_id, user_id=user_id, title="天门"), chapter, script,
                        workflow, run])
    await db_session.flush()
    episode = {"episode_number": 1, "chapter_ids": [chapter.id], "input_hash": "hash-1",
               "canonical_ids": {"workflow_id": workflow.id}}

    result = await create_or_resolve_script_stage(db_session, run=run, episode=episode)

    assert result["script_id"] == script.id
    assert script.extra_data["dialogue_lines"][0]["speaker"] == "沈砚"
    assert script.extra_data["dialogue_lines"][0]["chapter_id"] == chapter.id
