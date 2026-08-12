"""Owned Prompt Profile details and user-invoked assistance operations."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.model_config.prompt_management_repository import (
    load_visible_prompt_profile_history,
    load_linked_prompt_skill,
    load_prompt_version_for_user,
    prompt_version_values,
)
from app.services.prompt_skill_service import (
    optimize_prompt_skill_content,
    preview_prompt_skills,
)


def _version_detail(version) -> dict:
    values = prompt_version_values(version)
    return {
        "id": version.id,
        "version": version.version,
        "status": version.status,
        "stage": version.stage,
        "content": values["task_template"],
        **values,
        "checksum": version.checksum,
        "created_at": version.created_at.isoformat() if version.created_at else None,
        "published_at": (
            version.published_at.isoformat() if version.published_at else None
        ),
    }


async def get_prompt_profile_detail(
    db: AsyncSession,
    *,
    user_id: str,
    profile_id: str,
) -> dict | None:
    profile, versions = await load_visible_prompt_profile_history(
        db,
        user_id=user_id,
        profile_id=profile_id,
    )
    if profile is None or not versions:
        return None
    details = [_version_detail(version) for version in versions]
    legacy_skill = await load_linked_prompt_skill(
        db,
        user_id=user_id,
        profile_id=profile.id,
        version_ids=[version.id for version in versions],
    )
    return {
        "id": profile.id,
        "key": profile.key,
        "name": profile.name,
        "task": profile.task,
        "editable": profile.user_id == user_id,
        "head": details[0],
        "versions": details,
        "legacy_skill": ({
            "id": legacy_skill.id,
            "is_active": bool(legacy_skill.is_active),
            "is_builtin": bool(legacy_skill.is_builtin),
        } if legacy_skill else None),
    }


async def optimize_prompt_profile(
    db: AsyncSession,
    *,
    user_id: str,
    profile_id: str,
    version_id: str,
    mode: str,
    model_config_id: str | None,
) -> dict | None:
    row = await load_prompt_version_for_user(
        db,
        version_id=version_id,
        user_id=user_id,
    )
    if row is None or row.profile_id != profile_id:
        return None
    return await optimize_prompt_skill_content(db, user_id, {
        "task": row.task,
        "name": row.name,
        "content": row.values["task_template"],
        "mode": mode,
        "model_config_id": model_config_id,
    })


async def preview_prompt_profile(
    db: AsyncSession,
    *,
    user_id: str,
    profile_id: str,
    version_id: str,
    task_template: str | None,
    context: dict,
) -> dict | None:
    row = await load_prompt_version_for_user(
        db,
        version_id=version_id,
        user_id=user_id,
    )
    if row is None or row.profile_id != profile_id:
        return None
    return await preview_prompt_skills(
        db,
        user_id,
        task=row.task,
        context=context,
        draft_name=row.name,
        draft_content=task_template or row.values["task_template"],
        draft_stage=row.values.get("stage"),
    )
