from __future__ import annotations

from hashlib import sha256
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models import PromptSkill
from tests.model_binding_test_support import db_session as db_session


@pytest.mark.asyncio
async def test_series_stage_binding_returns_rendered_prompt_and_artifact_evidence(db_session):
    from app.features.series_skill_execution.public import bind_series_stage_skill

    db_session.add(PromptSkill(
        id="series-storyboard-skill", user_id="user-1", name="3D 分镜 Skill",
        task="storyboard_generation", stage="content",
        content="保持{style}，输出{shot_count}个镜头。", variables={"style": "2D", "shot_count": 1},
        priority=1, version=3, is_active=True, is_builtin=False,
    ))
    await db_session.flush()

    bound = await bind_series_stage_skill(
        db_session, user_id="user-1", task="storyboard_generation", stage="content",
        context={"style": "电影级3D", "shot_count": 2}, internal_prompt="章节正文",
        artifact_type="storyboard", artifact_id="board-1",
        execution_mode="deterministic_skill_contract",
    )

    assert "保持电影级3D，输出2个镜头" in bound.rendered_prompt
    assert "章节正文" in bound.rendered_prompt
    assert bound.evidence["id"] == "series-storyboard-skill"
    assert bound.evidence["version"] == 3
    assert bound.evidence["artifact_type"] == "storyboard"
    assert bound.evidence["artifact_id"] == "board-1"
    assert bound.evidence["rendered_prompt_sha256"] == sha256(
        bound.rendered_prompt.encode("utf-8")
    ).hexdigest()
    assert "rendered_prompt" not in bound.evidence


@pytest.mark.asyncio
async def test_required_series_stage_binding_fails_when_task_has_no_skill(db_session):
    from app.features.series_skill_execution.public import (
        SeriesStageSkillMissing,
        bind_series_stage_skill,
    )

    with pytest.raises(SeriesStageSkillMissing, match="missing_series_task"):
        await bind_series_stage_skill(
            db_session, user_id="user-1", task="missing_series_task", stage="content",
            context={}, internal_prompt="source", artifact_type="script",
        )


@pytest.mark.asyncio
async def test_series_stage_binding_keeps_nested_transaction_usable(db_session):
    from app.features.series_skill_execution.public import bind_series_stage_skill

    async with db_session.begin_nested():
        bound = await bind_series_stage_skill(
            db_session, user_id="nested-series-user", task="entity_extraction",
            stage="analysis", context={"entity_types": "character"},
            internal_prompt="source", artifact_type="entity_extraction_run",
        )
        skill_id = await db_session.scalar(
            select(PromptSkill.id).where(PromptSkill.id == bound.evidence["id"])
        )

    assert skill_id == bound.evidence["id"]


@pytest.mark.asyncio
async def test_series_reference_skill_is_rendered_for_the_real_asset(db_session):
    from app.features.series_reference_skill.public import bind_series_reference_skill

    run = SimpleNamespace(
        id="run-1", user_id="user-1", novel_id="novel-1",
        model_bindings={"capabilities": {"image": {
            "provider_id": "volcano", "api_model_id": "seedream-5-0-pro",
        }}},
    )
    bible = SimpleNamespace(title="雾港", style="电影级 3D")
    characters = [
        SimpleNamespace(name="沈砚", canonical_name="沈砚"),
        SimpleNamespace(name="林澜", canonical_name="林澜"),
    ]

    bound = await bind_series_reference_skill(
        db_session, run=run, bible=bible, characters=characters, asset_id="asset-1",
    )

    assert "沈砚、林澜" in bound.rendered_prompt
    assert "电影级 3D" in bound.rendered_prompt
    assert bound.evidence["artifact_type"] == "asset"
    assert bound.evidence["artifact_id"] == "asset-1"
    assert bound.evidence["execution_mode"] == "provider_model"
