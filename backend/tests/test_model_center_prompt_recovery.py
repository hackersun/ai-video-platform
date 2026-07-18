from __future__ import annotations

import pytest

from tests.model_center_helpers import (
    isolated_model_center_session,
    seed_prompt_skill,
)


@pytest.mark.asyncio
async def test_prompt_link_audit_reports_active_inactive_and_unlinked_rows(
    tmp_path,
) -> None:
    from app.features.model_config.prompt_recovery import audit_prompt_links

    async with isolated_model_center_session(tmp_path) as db:
        user_id = "user-1"
        await seed_prompt_skill(
            db,
            id="active",
            user_id=user_id,
            version=3,
            active=True,
            content="ACTIVE",
        )
        await seed_prompt_skill(
            db,
            id="inactive",
            user_id=user_id,
            version=2,
            active=False,
            content="INACTIVE",
        )

        audit = await audit_prompt_links(db, user_id)

    assert audit.legacy_total == 2
    assert audit.legacy_nonempty == 2
    assert audit.active_total == 1
    assert audit.inactive_total == 1
    assert audit.linked_total == 0
    assert audit.orphan_profile_ids == ()
    assert audit.content_conflicts == ()


@pytest.mark.asyncio
async def test_prompt_link_audit_rejects_version_owned_by_another_user(
    tmp_path,
) -> None:
    from app.features.model_config.prompt_recovery import (
        audit_prompt_links,
        stable_prompt_hash,
    )
    from app.models.prompt_profile import PromptProfile, PromptProfileVersion

    async with isolated_model_center_session(tmp_path) as db:
        skill = await seed_prompt_skill(
            db,
            id="skill-1",
            user_id="user-1",
            version=1,
            active=True,
            content="PRIVATE",
        )
        db.add(
            PromptProfile(
                id="profile-2",
                user_id="user-2",
                key="legacy.skill-1",
                name="Foreign",
                task="shot_video",
            )
        )
        db.add(
            PromptProfileVersion(
                id="version-2",
                profile_id="profile-2",
                version=1,
                content="PRIVATE",
                variables={},
                routing={},
                evaluation={},
                status="published",
                checksum=stable_prompt_hash("PRIVATE"),
            )
        )
        skill.prompt_profile_version_id = "version-2"
        await db.flush()

        audit = await audit_prompt_links(db, "user-1")

    assert audit.linked_total == 0
    assert audit.orphan_profile_ids == ("version-2",)
