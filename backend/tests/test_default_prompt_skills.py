import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.features.model_config.prompt_recovery import apply_prompt_recovery
from app.features.prompt_profiles.public import PromptRouteQuery, resolve_prompt_entries
from app.models.prompt_profile import PromptProfile, PromptProfileVersion
from app.models.prompt_skill import PromptSkill
from app.services.default_prompt_skills import (
    STANDARD_PROMPT_SKILLS,
    SYSTEM_PROMPT_SKILL_USER_ID,
    ensure_standard_prompt_skills,
)


def test_entity_extraction_has_distinct_chinese_defaults_for_each_usage_stage():
    definitions = {
        item["stage"]: item
        for item in STANDARD_PROMPT_SKILLS
        if item["task"] == "entity_extraction"
    }

    assert {"character", "scene_prop"}.issubset(definitions)
    assert definitions["character"]["id"] != definitions["scene_prop"]["id"]
    assert "角色" in definitions["character"]["name"]
    assert "场景/道具" in definitions["scene_prop"]["name"]
    assert "只输出 JSON 数组" in definitions["character"]["content"]
    assert "只输出 JSON 数组" in definitions["scene_prop"]["content"]


@pytest.mark.asyncio
async def test_entity_stage_defaults_recover_as_published_shared_profiles_idempotently():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as db:
            await ensure_standard_prompt_skills(db, commit=False)
            first = await apply_prompt_recovery(db, user_id=SYSTEM_PROMPT_SKILL_USER_ID)
            await db.commit()
            second = await apply_prompt_recovery(db, user_id=SYSTEM_PROMPT_SKILL_USER_ID)

            skills = list((await db.scalars(select(PromptSkill).where(
                PromptSkill.task == "entity_extraction",
                PromptSkill.stage.in_(("character", "scene_prop")),
            ))).all())
            versions = list((await db.scalars(select(PromptProfileVersion).where(
                PromptProfileVersion.id.in_([skill.prompt_profile_version_id for skill in skills]),
            ))).all())
            profiles = list((await db.scalars(select(PromptProfile).where(
                PromptProfile.id.in_([version.profile_id for version in versions]),
            ))).all())

            assert len(skills) == len(versions) == len(profiles) == 2
            assert {version.stage for version in versions} == {"character", "scene_prop"}
            assert {version.status for version in versions} == {"published"}
            assert {profile.user_id for profile in profiles} == {SYSTEM_PROMPT_SKILL_USER_ID}
            assert first.profiles_created >= 2
            assert second.created_total == 0
            assert second.skills_linked == 0

            for stage in ("character", "scene_prop"):
                selected = await resolve_prompt_entries(db, PromptRouteQuery(
                    user_id="ordinary-user",
                    task="entity_extraction",
                    provider_id="deepseek",
                    model_id="deepseek-v4-flash",
                    capabilities=frozenset({"text_generation"}),
                    output_contract="json_array",
                    stage=stage,
                    context={},
                ))
                assert selected
                assert selected[0].stage == stage
                assert selected[0].routing_reason in {
                    "task_generic_match", "task_only_template", "output_contract_match",
                }
    finally:
        await engine.dispose()
