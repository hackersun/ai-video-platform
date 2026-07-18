from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.model_center_helpers import (
    isolated_model_center_session,
    seed_prompt_skill,
)


async def _linked_version(db: AsyncSession, skill_id: str):
    from app.models.prompt_profile import PromptProfileVersion
    from app.models.prompt_skill import PromptSkill

    skill = await db.get(PromptSkill, skill_id)
    return await db.get(PromptProfileVersion, skill.prompt_profile_version_id)


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


@pytest.mark.asyncio
async def test_prompt_recovery_links_every_skill_and_preserves_content_hash(
    tmp_path,
) -> None:
    from app.features.model_config.prompt_recovery import (
        apply_prompt_recovery,
        stable_prompt_hash,
    )

    async with isolated_model_center_session(tmp_path) as db:
        await seed_prompt_skill(
            db,
            id="active",
            user_id="user-1",
            version=3,
            active=True,
            content="ACTIVE",
        )
        await seed_prompt_skill(
            db,
            id="inactive",
            user_id="user-1",
            version=2,
            active=False,
            content="INACTIVE",
        )

        report = await apply_prompt_recovery(db, user_id="user-1")
        active = await _linked_version(db, "active")
        inactive = await _linked_version(db, "inactive")
        second = await apply_prompt_recovery(db, user_id="user-1")

    assert report.skills_linked == 2
    assert report.content_conflicts == ()
    assert stable_prompt_hash(active.content) == stable_prompt_hash("ACTIVE")
    assert stable_prompt_hash(inactive.content) == stable_prompt_hash("INACTIVE")
    assert active.status == "published"
    assert inactive.status == "disabled"
    assert second.created_total == 0
    assert second.updated_total == 0


@pytest.mark.asyncio
async def test_legacy_version_service_reuses_recovered_link(
    tmp_path,
) -> None:
    from sqlalchemy import func, select

    from app.features.model_config.prompt_recovery import apply_prompt_recovery
    from app.features.prompt_profiles.public import ensure_legacy_prompt_profile
    from app.models.prompt_profile import PromptProfile, PromptProfileVersion
    from app.models.prompt_skill import PromptSkill

    async with isolated_model_center_session(tmp_path) as db:
        await seed_prompt_skill(
            db,
            id="skill-1",
            user_id="user-1",
            version=4,
            active=True,
            content="CANONICAL",
        )
        await apply_prompt_recovery(db, user_id="user-1")
        skill = await db.get(PromptSkill, "skill-1")
        linked_id = skill.prompt_profile_version_id

        resolved = await ensure_legacy_prompt_profile(db, skill)

        profile_total = await db.scalar(select(func.count()).select_from(PromptProfile))
        version_total = await db.scalar(
            select(func.count()).select_from(PromptProfileVersion)
        )

    assert resolved.id == linked_id
    assert profile_total == 1
    assert version_total == 1
