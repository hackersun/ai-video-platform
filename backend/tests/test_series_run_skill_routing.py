from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chapter, EntityExtractionRun, Novel, PromptSkill, Script, Shot, StoryEntity, Storyboard
from app.models.series_production_run import SeriesProductionRun
from app.services.episode_production_service import (
    create_or_resolve_shots_stage,
    create_or_resolve_script_stage,
    create_or_resolve_storyboard_stage,
    create_or_resolve_workflow_stage,
)
from app.services.story_entity_lifecycle import get_entity_review_status
from app.services.entity_evidence_contract import attach_chapter_evidence_contracts
from tests.model_binding_test_support import db_session as db_session


@pytest.mark.asyncio
async def test_series_script_stage_persists_selected_skill_version(
    db_session: AsyncSession,
) -> None:
    user_id = "series-skill-user"
    novel = Novel(id="series-skill-novel", user_id=user_id, title="星渊遗钥")
    chapter = Chapter(
        id="series-skill-chapter",
        novel_id=novel.id,
        user_id=user_id,
        title="第一章",
        chapter_number=1,
        content="林澈说：“必须关闭星门。”",
        status="completed",
    )
    skills = [PromptSkill(
        id="series-script-skill-v3",
        user_id=user_id,
        name="3D连续剧本技能",
        description="保持3D资产和对白字幕连续",
        task="script_generation",
        stage="content",
        content="剧本必须保留具名对白，并保持3D角色、场景和道具连续。",
        variables={},
        priority=1,
        version=3,
        is_active=True,
        is_builtin=False,
    ), PromptSkill(
        id="series-storyboard-skill-v2", user_id=user_id, name="3D连续分镜技能",
        task="storyboard_generation", stage="content",
        content="分镜保持电影级3D，并保留具名对白。", variables={}, priority=1,
        version=2, is_active=True, is_builtin=False,
    ), PromptSkill(
        id="series-shot-skill-v4", user_id=user_id, name="3D连续镜头技能",
        task="shot_prompt", stage="generation",
        content="镜头必须保持电影级3D角色与资产连续。", variables={}, priority=1,
        version=4, is_active=True, is_builtin=False,
    )]
    run = SeriesProductionRun(
        id="series-skill-run",
        user_id=user_id,
        novel_id=novel.id,
        series_plan_version="1",
        idempotency_key="series-skill-run-1",
        status="episodes_building",
        current_episode_number=1,
        requested_stages=["workflow", "script"],
        model_bindings={},
        budget_policy={},
        cost_summary={},
        gate_summary={},
        run_metadata={},
        episodes=[],
        version=1,
    )
    episode = {
        "episode_number": 1,
        "chapter_ids": [chapter.id],
        "input_hash": "chapter-input-v1",
        "canonical_ids": {},
    }
    db_session.add_all([novel, chapter, *skills, run])
    await db_session.flush()

    episode["canonical_ids"].update(
        await create_or_resolve_workflow_stage(db_session, run=run, episode=episode)
    )
    episode["canonical_ids"].update(
        await create_or_resolve_script_stage(db_session, run=run, episode=episode)
    )
    extracted = list((await db_session.scalars(
        select(StoryEntity).where(StoryEntity.chapter_id == chapter.id)
    )).all())
    extracted_payloads = [
        {"name": entity.name, "evidence_span": entity.name, "attributes": dict(entity.attributes or {})}
        for entity in extracted
    ]
    attach_chapter_evidence_contracts(
        extracted_payloads, content=chapter.content, chapter_id=chapter.id,
    )
    for entity, payload in zip(extracted, extracted_payloads, strict=True):
        entity.attributes = payload["attributes"]
    episode["canonical_ids"].update(
        await create_or_resolve_storyboard_stage(db_session, run=run, episode=episode)
    )
    run.episodes = [episode]
    episode["canonical_ids"].update(
        await create_or_resolve_shots_stage(db_session, run=run, episode=episode)
    )

    script = await db_session.get(Script, episode["canonical_ids"]["script_id"])
    evidence = (script.extra_data or {})["prompt_skill"]
    assert evidence["id"] == skills[0].id
    assert evidence["name"] == skills[0].name
    assert evidence["version"] == 3
    assert evidence["profile_version_id"]
    assert evidence["routing_reason"] == "task_only_template"
    assert evidence["execution_mode"] == "deterministic_fallback"
    assert evidence["model_execution"]["fallback_reason"] == "model_unavailable"
    assert evidence["artifact_type"] == "script"
    assert evidence["artifact_id"] == script.id
    assert len(evidence["rendered_prompt_sha256"]) == 64
    assert run.run_metadata["skill_evidence"]["script_generation"]["1"] == evidence
    entity_runs = (script.extra_data or {})["entity_extraction_runs"]
    assert len(entity_runs) == 1
    extraction_run = await db_session.get(EntityExtractionRun, entity_runs[0]["run_id"])
    assert extraction_run is not None
    assert extraction_run.status == "completed"
    assert extraction_run.extra_data["prompt_routing"]["prompt_skill_id"]
    entity_evidence = run.run_metadata["skill_evidence"]["entity_extraction"]
    assert entity_evidence["execution_mode"] == "deterministic_fallback"
    assert entity_evidence["model_execution"]["fallback_reason"] == "model_unavailable"
    assert entity_evidence["runs"][0]["run_id"] == extraction_run.id
    assert len(entity_evidence["runs"][0]["prompt_skill"]["rendered_prompt_sha256"]) == 64
    storyboard = await db_session.get(Storyboard, episode["canonical_ids"]["storyboard_id"])
    storyboard_evidence = storyboard.content["prompt_skill"]
    assert storyboard_evidence["id"] == skills[1].id
    assert storyboard_evidence["artifact_id"] == storyboard.id
    assert storyboard_evidence["model_execution"]["validation_status"] == "fallback"
    shot = await db_session.get(Shot, episode["canonical_ids"]["shot_ids"][0])
    shot_evidence = shot.extra_data["prompt_skill"]
    assert shot_evidence["id"] == skills[2].id
    assert shot_evidence["artifact_id"] == shot.id
    assert shot_evidence["model_execution"]["fallback_reason"] == "model_unavailable"
    assert "镜头必须保持电影级3D角色与资产连续" in shot.prompt
    assert run.run_metadata["skill_evidence"]["storyboard_generation"]["1"] == storyboard_evidence
    assert run.run_metadata["skill_evidence"]["shot_prompt"]["1"][shot.id] == shot_evidence
    entities = list((await db_session.scalars(
        select(StoryEntity).where(StoryEntity.chapter_id == chapter.id)
    )).all())
    lin_che = next(entity for entity in entities if entity.name == "林澈")
    assert get_entity_review_status(lin_che) == "approved"


@pytest.mark.asyncio
async def test_story_lock_persists_entity_extraction_skill_evidence(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.features.series_run_story_locks.application import story_transaction

    user_id = "entity-skill-user"
    novel = Novel(id="entity-skill-novel", user_id=user_id, title="星渊遗钥")
    chapter = Chapter(
        id="entity-skill-chapter",
        novel_id=novel.id,
        user_id=user_id,
        title="第一章",
        chapter_number=1,
        content="林澈进入蓝晶车站。",
        status="completed",
    )
    skill = PromptSkill(
        id="series-entity-skill-v4",
        user_id=user_id,
        name="连续角色资产抽取技能",
        task="entity_extraction",
        stage="analysis",
        content="只抽取有原文证据且可跨章追踪的角色、场景、道具和事件。",
        variables={},
        priority=1,
        version=4,
        is_active=True,
        is_builtin=False,
    )
    run = SeriesProductionRun(
        id="entity-skill-run",
        user_id=user_id,
        novel_id=novel.id,
        series_plan_version="1",
        idempotency_key="entity-skill-run-1",
        status="shots_ready",
        current_episode_number=1,
        requested_stages=[],
        model_bindings={},
        budget_policy={},
        cost_summary={},
        gate_summary={},
        run_metadata={},
        episodes=[],
        version=1,
    )
    db_session.add_all([novel, chapter, skill, run])
    await db_session.commit()
    expected_skill_id = skill.id

    async def ordered(*_args, **_kwargs):
        return [chapter]

    async def locked(*_args, **_kwargs):
        return {"status": "locked"}

    monkeypatch.setattr(story_transaction, "_ordered_run_chapters", ordered)
    monkeypatch.setattr(story_transaction, "apply_closure_v2_transaction", locked)

    result = await story_transaction.prepare_story_locks(db_session, run)

    assert result["status"] == "locked"
    await db_session.refresh(run)
    evidence = run.run_metadata["skill_evidence"]["entity_extraction"]
    assert evidence["id"] == expected_skill_id
    assert evidence["version"] == 4
    assert evidence["execution_mode"] == "deterministic_contract"


@pytest.mark.asyncio
async def test_series_script_stage_accumulates_entity_skill_runs_across_episodes(
    db_session: AsyncSession,
) -> None:
    user_id = "series-skill-aggregate-user"
    novel = Novel(id="series-skill-aggregate-novel", user_id=user_id, title="星渊遗钥")
    chapters = [
        Chapter(id=f"aggregate-chapter-{index}", novel_id=novel.id, user_id=user_id,
                title=f"第{index}章", chapter_number=index,
                content=f"角色：林澈。场景：第{index}站。林澈说：“第{index}章开始。”", status="completed")
        for index in (1, 2)
    ]
    run = SeriesProductionRun(
        id="series-skill-aggregate-run", user_id=user_id, novel_id=novel.id,
        series_plan_version="1", idempotency_key="series-skill-aggregate-run-1",
        status="episodes_building", current_episode_number=1, requested_stages=[],
        model_bindings={}, budget_policy={}, cost_summary={}, gate_summary={},
        run_metadata={}, episodes=[], version=1,
    )
    db_session.add_all([novel, *chapters, run])
    await db_session.flush()
    for index, chapter in enumerate(chapters, 1):
        episode = {"episode_number": index, "chapter_ids": [chapter.id],
                   "input_hash": f"aggregate-input-{index}", "canonical_ids": {}}
        episode["canonical_ids"].update(
            await create_or_resolve_workflow_stage(db_session, run=run, episode=episode))
        await create_or_resolve_script_stage(db_session, run=run, episode=episode)
    runs = run.run_metadata["skill_evidence"]["entity_extraction"]["runs"]
    assert [item["chapter_id"] for item in runs] == [chapter.id for chapter in chapters]
