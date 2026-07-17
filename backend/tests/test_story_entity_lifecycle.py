from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest

from app.core.database import AsyncSessionLocal
from app.models import Chapter, Novel, Script, Shot, StoryBible, StoryEntity, Storyboard
from init_db import init_db


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module", autouse=True)
def _init_database() -> None:
    init_db()


def _run(coro):
    return asyncio.run(coro)


def test_critical_production_services_use_lifecycle_story_entity_queries():
    checked_files = [
        "app/services/consistency_context.py",
        "app/services/story_prompt_context.py",
        "app/services/production_control.py",
        "app/services/production_bible.py",
        "app/services/production_card_service.py",
        "app/services/short_video_production.py",
        "app/services/series_production.py",
        "app/services/novel_continuity.py",
        "app/services/story_state_machine.py",
        "app/services/reference_package_builder.py",
        "app/api/v1/endpoints/scripts.py",
        "app/api/v1/endpoints/shots.py",
    ]
    allowed_direct_selects = {
        "app/services/reference_package_builder.py": [
            "select(StoryEntity).where(",
        ],
        "app/api/v1/endpoints/shots.py": [
            "select(StoryEntity).where(StoryEntity.id.in_(entity_ids)",
        ],
    }

    unexpected: list[str] = []
    for relative_path in checked_files:
        text = (PROJECT_ROOT / relative_path).read_text()
        for line_number, line in enumerate(text.splitlines(), start=1):
            if "select(StoryEntity)" not in line:
                continue
            if any(allowed in line for allowed in allowed_direct_selects.get(relative_path, [])):
                continue
            unexpected.append(f"{relative_path}:{line_number}: {line.strip()}")

    assert unexpected == []


def _entity(
    *,
    user_id: str,
    novel_id: str,
    name: str,
    review_status: str | None = None,
    is_approved: bool = False,
    chapter_id: str | None = None,
) -> StoryEntity:
    extra_data = {}
    if review_status:
        extra_data = {"lifecycle": {"status": review_status}}
    return StoryEntity(
        id=f"lifecycle-{uuid4()}",
        user_id=user_id,
        novel_id=novel_id,
        chapter_id=chapter_id,
        entity_type="character",
        name=name,
        is_approved=is_approved,
        extra_data=extra_data,
    )


def _chapter(
    *,
    user_id: str,
    novel_id: str,
    chapter_id: str,
    number: int = 1,
) -> Chapter:
    return Chapter(
        id=chapter_id,
        user_id=user_id,
        novel_id=novel_id,
        title=f"第{number}章",
        chapter_number=number,
        content="林澈在旧邮局追查铜铃。",
    )


def test_lifecycle_status_defaults_preserve_legacy_entities():
    from app.services.story_entity_lifecycle import (
        APPROVED,
        CANDIDATE,
        LEGACY_ACTIVE,
        get_entity_review_status,
        is_entity_production_visible,
        set_entity_review_status,
    )

    legacy = StoryEntity(id="legacy", user_id="u", entity_type="character", name="旧角色")
    approved_flag = StoryEntity(
        id="approved-flag",
        user_id="u",
        entity_type="character",
        name="已确认角色",
        is_approved=True,
    )
    candidate = StoryEntity(
        id="candidate",
        user_id="u",
        entity_type="character",
        name="候选角色",
        extra_data={"lifecycle": {"status": CANDIDATE}},
    )

    assert get_entity_review_status(legacy) == LEGACY_ACTIVE
    assert get_entity_review_status(approved_flag) == APPROVED
    assert get_entity_review_status(candidate) == CANDIDATE
    assert is_entity_production_visible(legacy) is True
    assert is_entity_production_visible(approved_flag) is True
    assert is_entity_production_visible(candidate) is False

    set_entity_review_status(candidate, APPROVED, changed_by="tester", reason="clean evidence")

    assert candidate.is_approved is True
    assert get_entity_review_status(candidate) == APPROVED
    assert candidate.extra_data["lifecycle"]["previous_status"] == CANDIDATE
    assert candidate.extra_data["lifecycle"]["changed_by"] == "tester"
    assert candidate.extra_data["lifecycle"]["reason"] == "clean evidence"


def test_production_query_hides_candidates_rejected_and_archived():
    async def scenario():
        from app.services.story_entity_lifecycle import (
            ARCHIVED,
            CANDIDATE,
            REJECTED,
            query_story_entities_for_production,
            query_story_entities_for_review,
        )

        user_id = f"lifecycle-user-{uuid4().hex[:20]}"
        novel_id = f"lifecycle-novel-{uuid4()}"
        async with AsyncSessionLocal() as db:
            db.add(Novel(id=novel_id, user_id=user_id, title="生命周期测试小说"))
            db.add_all(
                [
                    _entity(user_id=user_id, novel_id=novel_id, name="旧实体"),
                    _entity(user_id=user_id, novel_id=novel_id, name="已确认", is_approved=True),
                    _entity(user_id=user_id, novel_id=novel_id, name="候选", review_status=CANDIDATE),
                    _entity(user_id=user_id, novel_id=novel_id, name="驳回", review_status=REJECTED),
                    _entity(user_id=user_id, novel_id=novel_id, name="归档", review_status=ARCHIVED),
                ]
            )
            await db.commit()

            production = await query_story_entities_for_production(
                db,
                user_id=user_id,
                novel_id=novel_id,
            )
            review = await query_story_entities_for_review(
                db,
                user_id=user_id,
                novel_id=novel_id,
            )

        assert [entity.name for entity in production] == ["旧实体", "已确认"]
        assert [entity.name for entity in review] == ["旧实体", "已确认", "候选"]

    _run(scenario())


def test_production_query_respects_chapter_scope_and_global_novel_entities():
    async def scenario():
        from app.services.story_entity_lifecycle import CANDIDATE, query_story_entities_for_production

        user_id = f"lifecycle-user-{uuid4().hex[:20]}"
        novel_id = f"lifecycle-novel-{uuid4()}"
        chapter_id = f"chapter-{uuid4()}"
        other_chapter_id = f"chapter-{uuid4()}"
        async with AsyncSessionLocal() as db:
            db.add(Novel(id=novel_id, user_id=user_id, title="章节范围生命周期测试"))
            db.add_all(
                [
                    _entity(user_id=user_id, novel_id=novel_id, name="小说级角色"),
                    _entity(user_id=user_id, novel_id=novel_id, chapter_id=chapter_id, name="本章角色"),
                    _entity(user_id=user_id, novel_id=novel_id, chapter_id=other_chapter_id, name="其他章节角色"),
                    _entity(
                        user_id=user_id,
                        novel_id=novel_id,
                        chapter_id=chapter_id,
                        name="本章候选",
                        review_status=CANDIDATE,
                    ),
                ]
            )
            await db.commit()

            entities = await query_story_entities_for_production(
                db,
                user_id=user_id,
                novel_id=novel_id,
                chapter_id=chapter_id,
            )

        assert [entity.name for entity in entities] == ["小说级角色", "本章角色"]

    _run(scenario())


def test_generation_context_excludes_candidate_entities():
    async def scenario():
        from app.services.consistency_context import load_or_extract_story_entities
        from app.services.story_entity_lifecycle import CANDIDATE

        user_id = f"lifecycle-user-{uuid4().hex[:20]}"
        novel_id = f"lifecycle-novel-{uuid4()}"
        async with AsyncSessionLocal() as db:
            db.add(Novel(id=novel_id, user_id=user_id, title="生成上下文生命周期测试"))
            db.add_all(
                [
                    _entity(user_id=user_id, novel_id=novel_id, name="可用角色"),
                    _entity(user_id=user_id, novel_id=novel_id, name="候选角色", review_status=CANDIDATE),
                ]
            )
            await db.commit()

            entities = await load_or_extract_story_entities(
                db,
                user_id,
                novel_id=novel_id,
                persist_missing=False,
            )

        assert [entity.name for entity in entities] == ["可用角色"]

    _run(scenario())


def test_generation_context_persists_new_extractions_as_candidates_with_mentions_but_returns_only_production_entities():
    async def scenario():
        from sqlalchemy import select

        from app.models import StoryEntityMention
        from app.services.consistency_context import load_or_extract_story_entities
        from app.services.story_entity_lifecycle import get_entity_review_status

        user_id = f"lifecycle-user-{uuid4().hex[:20]}"
        novel_id = f"lifecycle-novel-{uuid4()}"
        async with AsyncSessionLocal() as db:
            db.add(Novel(id=novel_id, user_id=user_id, title="上下文候选安全测试"))
            db.add(_entity(user_id=user_id, novel_id=novel_id, name="已有人物"))
            await db.commit()

            returned = await load_or_extract_story_entities(
                db,
                user_id,
                novel_id=novel_id,
                text="角色：林澈。林澈走进旧邮局。",
                persist_missing=True,
            )
            stored = (
                await db.execute(
                    select(StoryEntity).where(
                        StoryEntity.user_id == user_id,
                        StoryEntity.novel_id == novel_id,
                        StoryEntity.name == "林澈",
                    )
                )
            ).scalar_one()
            mentions = (
                await db.execute(
                    select(StoryEntityMention).where(StoryEntityMention.entity_id == stored.id)
                )
            ).scalars().all()

        return {
            "returned_names": [entity.name for entity in returned],
            "stored_status": get_entity_review_status(stored),
            "mention_count": len(mentions),
            "mention_source_ids": [mention.source_id for mention in mentions],
            "novel_id": novel_id,
        }

    result = _run(scenario())

    assert result["returned_names"] == ["已有人物"]
    assert result["stored_status"] == "candidate"
    assert result["mention_count"] >= 1
    assert result["mention_source_ids"] == [result["novel_id"]]


def test_production_pack_does_not_create_assets_for_candidate_entities():
    async def scenario():
        from app.services.production_control import build_novel_production_pack
        from app.services.story_entity_lifecycle import CANDIDATE

        user_id = f"lifecycle-user-{uuid4().hex[:20]}"
        novel_id = f"lifecycle-novel-{uuid4()}"
        async with AsyncSessionLocal() as db:
            db.add(Novel(id=novel_id, user_id=user_id, title="生产包生命周期测试"))
            db.add_all(
                [
                    _entity(user_id=user_id, novel_id=novel_id, name="可锁定角色"),
                    _entity(user_id=user_id, novel_id=novel_id, name="候选角色", review_status=CANDIDATE),
                ]
            )
            await db.commit()

            pack = await build_novel_production_pack(
                db,
                user_id,
                novel_id,
                create_missing_assets=True,
                persist=False,
            )

        assert pack["summary"]["entity_count"] == 1
        assert pack["summary"]["created_asset_count"] == 1
        assert pack["locks"][0]["entity_name"] == "可锁定角色"

    _run(scenario())


def test_story_prompt_context_excludes_candidate_entities():
    async def scenario():
        from app.services.story_prompt_context import load_story_prompt_context
        from app.services.story_entity_lifecycle import CANDIDATE

        user_id = f"lifecycle-user-{uuid4().hex[:20]}"
        novel_id = f"lifecycle-novel-{uuid4()}"
        async with AsyncSessionLocal() as db:
            db.add(Novel(id=novel_id, user_id=user_id, title="提示词上下文生命周期测试"))
            db.add_all(
                [
                    _entity(user_id=user_id, novel_id=novel_id, name="上下文角色"),
                    _entity(user_id=user_id, novel_id=novel_id, name="候选上下文角色", review_status=CANDIDATE),
                ]
            )
            await db.commit()

            context = await load_story_prompt_context(db, user_id, novel_id=novel_id)

        assert [item["name"] for item in context["characters"]] == ["上下文角色"]

    _run(scenario())


def test_production_bible_summary_excludes_candidate_entities():
    async def scenario():
        from app.services.production_bible import build_production_bible_summary
        from app.services.story_entity_lifecycle import CANDIDATE

        user_id = f"lifecycle-user-{uuid4().hex[:20]}"
        novel_id = f"lifecycle-novel-{uuid4()}"
        async with AsyncSessionLocal() as db:
            db.add(Novel(id=novel_id, user_id=user_id, title="生产圣经生命周期测试"))
            db.add_all(
                [
                    _entity(user_id=user_id, novel_id=novel_id, name="生产角色"),
                    _entity(user_id=user_id, novel_id=novel_id, name="候选生产角色", review_status=CANDIDATE),
                ]
            )
            await db.commit()

            summary = await build_production_bible_summary(db, user_id, novel_id)

        assert summary["counts"]["characters"] == 1
        assert [item["name"] for item in summary["characters"]] == ["生产角色"]

    _run(scenario())


def test_production_cards_exclude_candidate_entities():
    async def scenario():
        from app.services.production_card_service import build_production_cards_for_novel
        from app.services.story_entity_lifecycle import CANDIDATE

        user_id = f"lifecycle-user-{uuid4().hex[:20]}"
        novel_id = f"lifecycle-novel-{uuid4()}"
        async with AsyncSessionLocal() as db:
            db.add(Novel(id=novel_id, user_id=user_id, title="定稿卡生命周期测试"))
            db.add_all(
                [
                    _entity(user_id=user_id, novel_id=novel_id, name="定稿卡角色"),
                    _entity(user_id=user_id, novel_id=novel_id, name="候选定稿卡角色", review_status=CANDIDATE),
                ]
            )
            await db.commit()

            cards = await build_production_cards_for_novel(db, user_id, novel_id)

        assert [card["name"] for card in cards["cards"]] == ["定稿卡角色"]

    _run(scenario())


def test_short_video_contract_excludes_candidate_entities():
    async def scenario():
        from app.services.short_video_production import build_shot_production_contract
        from app.services.story_entity_lifecycle import CANDIDATE

        user_id = f"lifecycle-user-{uuid4().hex[:20]}"
        novel_id = f"lifecycle-novel-{uuid4()}"
        chapter_id = f"chapter-{uuid4()}"
        script_id = f"script-{uuid4()}"
        storyboard_id = f"storyboard-{uuid4()}"
        shot_id = f"shot-{uuid4()}"
        async with AsyncSessionLocal() as db:
            db.add(Novel(id=novel_id, user_id=user_id, title="短视频合约生命周期测试"))
            db.add(_chapter(user_id=user_id, novel_id=novel_id, chapter_id=chapter_id))
            db.add(
                Script(
                    id=script_id,
                    user_id=user_id,
                    novel_id=novel_id,
                    chapter_id=chapter_id,
                    title="测试剧本",
                    extra_data={"chapter_id": chapter_id},
                )
            )
            db.add(Storyboard(id=storyboard_id, user_id=user_id, novel_id=novel_id, script_id=script_id, title="测试分镜"))
            db.add(Shot(id=shot_id, user_id=user_id, storyboard_id=storyboard_id, shot_number=1, prompt="林澈看向候选角色。"))
            db.add_all(
                [
                    _entity(user_id=user_id, novel_id=novel_id, chapter_id=chapter_id, name="合约角色"),
                    _entity(user_id=user_id, novel_id=novel_id, chapter_id=chapter_id, name="候选合约角色", review_status=CANDIDATE),
                ]
            )
            await db.commit()

            contract = await build_shot_production_contract(db, user_id, shot_id)

        assert [item["name"] for item in contract["characters"]] == ["合约角色"]

    _run(scenario())


def test_novel_continuity_package_excludes_candidate_entities():
    async def scenario():
        from app.services.novel_continuity import build_novel_continuity_package
        from app.services.story_entity_lifecycle import CANDIDATE

        user_id = f"lifecycle-user-{uuid4().hex[:20]}"
        novel_id = f"lifecycle-novel-{uuid4()}"
        chapter_id = f"chapter-{uuid4()}"
        async with AsyncSessionLocal() as db:
            db.add(Novel(id=novel_id, user_id=user_id, title="连续性包生命周期测试"))
            db.add(_chapter(user_id=user_id, novel_id=novel_id, chapter_id=chapter_id))
            db.add_all(
                [
                    _entity(user_id=user_id, novel_id=novel_id, chapter_id=chapter_id, name="连续性角色"),
                    _entity(user_id=user_id, novel_id=novel_id, chapter_id=chapter_id, name="候选连续性角色", review_status=CANDIDATE),
                ]
            )
            await db.commit()

            package = await build_novel_continuity_package(db, user_id, novel_id=novel_id, chapter_id=chapter_id)

        assert [item["name"] for item in package["entity_locks"]["characters"]] == ["连续性角色"]

    _run(scenario())


def test_series_plan_excludes_candidate_entities_from_episode_keys():
    async def scenario():
        from app.services.series_production import build_series_plan
        from app.services.story_entity_lifecycle import CANDIDATE

        user_id = f"lifecycle-user-{uuid4().hex[:20]}"
        novel_id = f"lifecycle-novel-{uuid4()}"
        chapter_id = f"chapter-{uuid4()}"
        async with AsyncSessionLocal() as db:
            db.add(Novel(id=novel_id, user_id=user_id, title="整书计划生命周期测试"))
            db.add(_chapter(user_id=user_id, novel_id=novel_id, chapter_id=chapter_id))
            db.add_all(
                [
                    _entity(user_id=user_id, novel_id=novel_id, chapter_id=chapter_id, name="整书角色"),
                    _entity(user_id=user_id, novel_id=novel_id, chapter_id=chapter_id, name="候选整书角色", review_status=CANDIDATE),
                ]
            )
            await db.commit()

            plan = await build_series_plan(db, user_id, novel_id=novel_id, chapters_per_episode=1, persist=False)

        assert plan["episodes"][0]["key_characters"] == ["整书角色"]

    _run(scenario())


def test_story_state_machine_excludes_candidate_entities():
    async def scenario():
        from app.services.story_entity_lifecycle import CANDIDATE
        from app.services.story_state_machine import build_story_state_machine

        user_id = f"lifecycle-user-{uuid4().hex[:20]}"
        novel_id = f"lifecycle-novel-{uuid4()}"
        chapter_id = f"chapter-{uuid4()}"
        story_bible_id = f"story-bible-{uuid4()}"
        async with AsyncSessionLocal() as db:
            db.add(Novel(id=novel_id, user_id=user_id, title="状态机生命周期测试"))
            db.add(_chapter(user_id=user_id, novel_id=novel_id, chapter_id=chapter_id))
            db.add(StoryBible(id=story_bible_id, user_id=user_id, novel_id=novel_id, title="状态机 Story Bible"))
            db.add_all(
                [
                    _entity(user_id=user_id, novel_id=novel_id, chapter_id=chapter_id, name="状态机角色"),
                    _entity(user_id=user_id, novel_id=novel_id, chapter_id=chapter_id, name="候选状态机角色", review_status=CANDIDATE),
                ]
            )
            await db.commit()

            state_machine = await build_story_state_machine(
                db,
                user_id,
                story_bible_id=story_bible_id,
                persist=False,
            )

        character_names = list(state_machine["current_state"]["characters"].keys())
        assert "状态机角色" in character_names
        assert "候选状态机角色" not in character_names

    _run(scenario())


def test_script_generation_scope_excludes_candidate_entities():
    async def scenario():
        from app.api.v1.endpoints.scripts import (
            build_production_pack_summary,
            load_story_entities_for_scope,
        )
        from app.services.story_entity_lifecycle import CANDIDATE

        user_id = f"lifecycle-user-{uuid4().hex[:20]}"
        novel_id = f"lifecycle-novel-{uuid4()}"
        chapter_id = f"chapter-{uuid4()}"
        async with AsyncSessionLocal() as db:
            db.add(Novel(id=novel_id, user_id=user_id, title="剧本上下文生命周期测试"))
            db.add(_chapter(user_id=user_id, novel_id=novel_id, chapter_id=chapter_id))
            db.add_all(
                [
                    _entity(user_id=user_id, novel_id=novel_id, chapter_id=chapter_id, name="剧本角色"),
                    _entity(user_id=user_id, novel_id=novel_id, chapter_id=chapter_id, name="候选剧本角色", review_status=CANDIDATE),
                ]
            )
            await db.commit()

            entities = await load_story_entities_for_scope(db, user_id, novel_id, chapter_id)

        summary = build_production_pack_summary(entities)
        assert [item["name"] for item in summary["characters"]] == ["剧本角色"]

    _run(scenario())


def test_shot_production_context_rejects_candidate_entity_bindings():
    async def scenario():
        from fastapi import HTTPException

        from app.api.v1.endpoints.shots import _resolve_entity_reference_bindings
        from app.services.story_entity_lifecycle import CANDIDATE

        user_id = f"lifecycle-user-{uuid4().hex[:20]}"
        novel_id = f"lifecycle-novel-{uuid4()}"
        candidate_id = f"candidate-{uuid4()}"
        async with AsyncSessionLocal() as db:
            db.add(Novel(id=novel_id, user_id=user_id, title="镜头生产上下文生命周期测试"))
            candidate = _entity(
                user_id=user_id,
                novel_id=novel_id,
                name="候选绑定角色",
                review_status=CANDIDATE,
            )
            candidate.id = candidate_id
            db.add(candidate)
            await db.commit()

            with pytest.raises(HTTPException) as exc_info:
                await _resolve_entity_reference_bindings(
                    db,
                    user_id,
                    [{"entity_id": candidate_id}],
                )

        assert exc_info.value.status_code == 422

    _run(scenario())


def test_ai_candidate_requires_persisted_source_evidence_before_approval():
    async def scenario():
        from app.services.entity_review_service import approve_review_entity
        from app.services.story_entity_lifecycle import CANDIDATE, get_entity_review_status

        user_id = f"evidence-user-{uuid4().hex[:20]}"
        novel_id = f"evidence-novel-{uuid4()}"
        entity = _entity(
            user_id=user_id,
            novel_id=novel_id,
            name="无证据候选",
            review_status=CANDIDATE,
        )
        entity.source = "deterministic"
        entity.extra_data = {
            **(entity.extra_data or {}),
            "extraction_run_id": f"run-{uuid4()}",
        }

        async with AsyncSessionLocal() as db:
            db.add(entity)
            await db.commit()

            with pytest.raises(ValueError, match="原文证据"):
                await approve_review_entity(
                    db,
                    user_id=user_id,
                    entity_id=entity.id,
                    reason="尝试绕过证据门禁",
                )

            await db.refresh(entity)
            return get_entity_review_status(entity)

    assert _run(scenario()) == "candidate"


def test_ai_candidate_can_be_approved_with_complete_mention_evidence():
    async def scenario():
        from app.models import StoryEntityMention
        from app.services.entity_review_service import approve_review_entity
        from app.services.story_entity_lifecycle import CANDIDATE, get_entity_review_status

        user_id = f"evidence-user-{uuid4().hex[:20]}"
        novel_id = f"evidence-novel-{uuid4()}"
        run_id = f"run-{uuid4()}"
        entity = _entity(
            user_id=user_id,
            novel_id=novel_id,
            name="证据完整候选",
            review_status=CANDIDATE,
        )
        entity.source = "deterministic"
        entity.extra_data = {**(entity.extra_data or {}), "extraction_run_id": run_id}

        async with AsyncSessionLocal() as db:
            db.add(entity)
            db.add(
                StoryEntityMention(
                    id=f"mention-{uuid4()}",
                    user_id=user_id,
                    run_id=run_id,
                    entity_id=entity.id,
                    novel_id=novel_id,
                    source_type="novel",
                    source_id=novel_id,
                    mention_text="林澈站在旧邮局门口。",
                    evidence="林澈站在旧邮局门口。",
                    confidence=0.92,
                    extractor="deterministic",
                )
            )
            await db.commit()

            approved = await approve_review_entity(
                db,
                user_id=user_id,
                entity_id=entity.id,
                reason="证据完整",
            )
            return get_entity_review_status(approved)

    assert _run(scenario()) == "approved"


def test_manual_entity_approval_records_manual_source_and_approver():
    async def scenario():
        from app.services.entity_review_service import approve_review_entity

        user_id = f"manual-user-{uuid4().hex[:20]}"
        novel_id = f"manual-novel-{uuid4()}"
        entity = _entity(user_id=user_id, novel_id=novel_id, name="人工角色")
        entity.source = "manual"

        async with AsyncSessionLocal() as db:
            db.add(entity)
            await db.commit()
            approved = await approve_review_entity(
                db,
                user_id=user_id,
                entity_id=entity.id,
                reason="人工录入确认",
            )
            lifecycle = (approved.extra_data or {}).get("lifecycle") or {}
            approval_record = (approved.attributes or {}).get("approval_record") or {}
            return {
                "source": approved.source,
                "approver_recorded": lifecycle.get("changed_by") == user_id,
                "production_approver_recorded": approval_record.get("approved_by") == user_id,
                "production_reason": approval_record.get("reason"),
                "production_approved_at_recorded": bool(approval_record.get("approved_at")),
            }

    assert _run(scenario()) == {
        "source": "manual",
        "approver_recorded": True,
        "production_approver_recorded": True,
        "production_reason": "人工录入确认",
        "production_approved_at_recorded": True,
    }
