from __future__ import annotations

from types import SimpleNamespace
import asyncio
from uuid import uuid4

import pytest

from app.core.database import AsyncSessionLocal
from app.models import Chapter, Novel, StoryEntity, Workflow
from init_db import init_db


@pytest.fixture(scope="module", autouse=True)
def _init_database() -> None:
    init_db()


def _entity(name: str, chapter_id: str, *, status: str = "approved", **attributes):
    return SimpleNamespace(
        id=f"entity-{name}",
        entity_type="prop",
        name=name,
        canonical_name=name,
        chapter_id=chapter_id,
        first_seen_chapter_id=chapter_id,
        attributes=attributes,
        extra_data={"lifecycle": {"status": status}},
        is_approved=status == "approved",
    )


def test_as_of_projection_excludes_future_and_unapproved_facts() -> None:
    from app.services.chapter_fact_timeline import project_entities_as_of_chapter

    chapters = [
        SimpleNamespace(id=f"chapter-{index}", chapter_number=index)
        for index in range(1, 5)
    ]
    facts = [
        _entity("旧铜铃", "chapter-1"),
        _entity("第四次钟声", "chapter-4"),
        _entity("全书汇总中的第四章密钥", None, source_chapter_index=4),
        _entity("候选罗盘", "chapter-1", status="candidate"),
        _entity("废弃钥匙", "chapter-1", status="rejected"),
    ]

    projected = project_entities_as_of_chapter(facts, chapters, chapter_number=3, strict=True)

    assert [fact.name for fact in projected] == ["旧铜铃"]


def test_projection_separates_current_state_from_future_intent() -> None:
    from app.services.chapter_fact_timeline import project_entity_fact

    fact = _entity(
        "旧铜铃",
        "chapter-1",
        current_state={"owner": "沈砚"},
        known_to_characters=["沈砚"],
        introduced_at=1,
        resolved_at=None,
        future_intent="第四章响起",
        foreshadowing="铃舌有裂纹",
    )

    normal = project_entity_fact(fact, include_foreshadowing=False)
    foreshadowed = project_entity_fact(fact, include_foreshadowing=True)

    assert normal["current_state"] == {"owner": "沈砚"}
    assert normal["known_to_characters"] == ["沈砚"]
    assert normal["introduced_at"] == 1
    assert normal["resolved_at"] is None
    assert "future_intent" not in normal
    assert "foreshadowing" not in normal
    assert foreshadowed["future_intent"] == "第四章响起"
    assert foreshadowed["foreshadowing"] == "铃舌有裂纹"


def test_strict_projection_handles_non_contiguous_numbers_and_unknown_provenance() -> None:
    from app.services.chapter_fact_timeline import project_entities_as_of_chapter

    chapters = [SimpleNamespace(id="c10", chapter_number=10), SimpleNamespace(id="c30", chapter_number=30)]
    global_fact = _entity("世界观规则", None, is_global_fact=True)
    facts = [_entity("第十章钥匙", "c10"), _entity("第三十章钥匙", "c30"), _entity("未知来源", None), global_fact]

    projected = project_entities_as_of_chapter(facts, chapters, chapter_number=10, strict=True)

    assert [fact.name for fact in projected] == ["第十章钥匙", "世界观规则"]


@pytest.mark.asyncio
async def test_production_bible_calls_chapter_projection(monkeypatch) -> None:
    from app.services import production_bible

    called = {}
    chapter = SimpleNamespace(id="chapter-2", chapter_number=2)

    async def fake_load_novel(*args, **kwargs):
        return SimpleNamespace(id="novel-1", title="四章故事", genre="悬疑", description="", extra_data={})

    async def fake_load_entities(*args, **kwargs):
        return []

    async def fake_load_assets(*args, **kwargs):
        return []

    async def fake_load_chapters(*args, **kwargs):
        return [chapter]

    def fake_projection(entities, chapters, *, chapter_number, strict):
        called["chapter_number"] = chapter_number
        called["strict"] = strict
        return []

    monkeypatch.setattr(production_bible, "_load_novel", fake_load_novel)
    monkeypatch.setattr(production_bible, "_load_story_bible", lambda *args, **kwargs: _async_value(None))
    monkeypatch.setattr(production_bible, "_load_entities", fake_load_entities)
    monkeypatch.setattr(production_bible, "_load_assets", fake_load_assets)
    monkeypatch.setattr(production_bible, "_load_chapters", fake_load_chapters)
    monkeypatch.setattr(production_bible, "project_entities_as_of_chapter", fake_projection)
    monkeypatch.setattr(production_bible, "project_story_state", lambda *args, **kwargs: _async_value({}))

    await production_bible.build_production_bible_summary(
        object(), "user-1", "novel-1", as_of_chapter_number=2
    )

    assert called == {"chapter_number": 2, "strict": True}


@pytest.mark.asyncio
async def test_story_state_machine_calls_projection_for_each_chapter_snapshot(monkeypatch) -> None:
    from app.services import story_state_machine

    calls: list[int] = []
    chapters = [SimpleNamespace(id=f"chapter-{i}", chapter_number=i, title=str(i), content="", created_at=i) for i in range(1, 5)]

    monkeypatch.setattr(
        story_state_machine,
        "project_entities_as_of_chapter",
        lambda entities, known_chapters, *, chapter_number, strict: calls.append(chapter_number) or [],
    )

    story_state_machine._chapter_entity_projections([], chapters)

    assert calls == [1, 2, 3, 4]


def test_production_summary_and_episode_contract_exclude_chapter_four_approved_fact() -> None:
    async def scenario():
        from app.services.episode_contract_service import lock_episode_contract
        from app.services.production_bible import build_production_bible_summary
        from app.services.series_production import build_series_plan

        token = uuid4().hex
        user_id, novel_id = f"timeline-user-{token}", f"timeline-novel-{token}"
        chapter_ids = [f"timeline-chapter-{i}-{token}" for i in range(1, 5)]
        workflow_id = f"timeline-workflow-{token}"
        async with AsyncSessionLocal() as db:
            db.add(Novel(id=novel_id, user_id=user_id, title="四章事实投影"))
            db.add_all([
                Chapter(id=chapter_ids[i - 1], user_id=user_id, novel_id=novel_id, title=f"第{i}章", chapter_number=i, content=f"第{i}章")
                for i in range(1, 5)
            ])
            db.add_all([
                StoryEntity(id=f"fact-1-{token}", user_id=user_id, novel_id=novel_id, chapter_id=chapter_ids[0], first_seen_chapter_id=chapter_ids[0], entity_type="prop", name="第一章铜铃", is_approved=True, extra_data={"lifecycle": {"status": "approved"}}),
                StoryEntity(id=f"fact-4-{token}", user_id=user_id, novel_id=novel_id, chapter_id=chapter_ids[3], first_seen_chapter_id=chapter_ids[3], entity_type="prop", name="第四章密钥", is_approved=True, extra_data={"lifecycle": {"status": "approved"}}),
            ])
            db.add(Workflow(id=workflow_id, user_id=user_id, title="第一章", novel_id=novel_id, chapter_id=chapter_ids[0], metadata_={"episode_index": 1}))
            await db.commit()

            summary = await build_production_bible_summary(db, user_id, novel_id, as_of_chapter_id=chapter_ids[0])
            contract = await lock_episode_contract(db, user_id, workflow_id)
            plan = await build_series_plan(db, user_id, novel_id=novel_id, chapters_per_episode=1, persist=False)
            return summary, contract, plan

    summary, contract, plan = asyncio.run(scenario())
    assert "第一章铜铃" in str(summary)
    assert "第四章密钥" not in str(summary)
    assert "第一章铜铃" in str(contract)
    assert "第四章密钥" not in str(contract)
    assert all("第四章密钥" not in str(episode["production_bible_summary"]) for episode in plan["episodes"][:3])
    assert "第四章密钥" in str(plan["episodes"][3]["production_bible_summary"])


async def _async_value(value):
    return value
