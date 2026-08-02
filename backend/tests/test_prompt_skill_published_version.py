from __future__ import annotations

import pytest

from app.features.prompt_profiles.public import PromptRouteQuery, resolve_prompt_entries
from app.models import PromptProfileVersion, PromptSkill
from app.services.prompt_skill_service import update_prompt_skill
from tests.model_binding_test_support import db_session as db_session


@pytest.mark.asyncio
async def test_active_skill_edit_creates_draft_without_replacing_published_route(db_session):
    skill = PromptSkill(
        id="active-script-skill", user_id="user-1", name="连续剧本 Skill",
        task="script_generation", stage="content", content="旧版规则",
        variables={}, priority=1, version=1, is_active=True, is_builtin=False,
    )
    db_session.add(skill)
    await db_session.commit()

    result = await update_prompt_skill(
        db_session, "user-1", skill.id,
        {"content": "新版规则：保留对白和资产连续性", "is_active": True},
    )
    routed = await resolve_prompt_entries(
        db_session,
        PromptRouteQuery(
            user_id="user-1", task="script_generation", stage="content", context={},
        ),
    )
    persisted = await db_session.get(PromptSkill, skill.id)
    version = await db_session.get(PromptProfileVersion, persisted.prompt_profile_version_id)

    assert result["version"] == 2
    assert persisted.version == 1
    assert persisted.content == "旧版规则"
    assert version.status == "draft"
    assert routed[0].profile_version_id != version.id
    assert routed[0].version == 1
    assert routed[0].prompt == "旧版规则"
