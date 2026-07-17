"""Prompt Profile persistence queries and legacy Prompt Skill projection."""

from __future__ import annotations

from typing import Any, Iterable

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.prompt_profiles.domain import render_prompt
from app.models.prompt_profile import PromptProfile, PromptProfileVersion
from app.models.prompt_skill import PromptSkill


async def get_profile_version(db: AsyncSession, version_id: str) -> PromptProfileVersion:
    row = await db.get(PromptProfileVersion, version_id)
    if row is None:
        raise ValueError("prompt profile version not found")
    return row


async def get_profile(db: AsyncSession, profile_id: str) -> PromptProfile:
    row = await db.get(PromptProfile, profile_id)
    if row is None:
        raise ValueError("prompt profile not found")
    return row


async def latest_profile_version(db: AsyncSession, profile_id: str) -> PromptProfileVersion | None:
    result = await db.execute(
        select(PromptProfileVersion)
        .where(PromptProfileVersion.profile_id == profile_id)
        .order_by(PromptProfileVersion.version.desc(), PromptProfileVersion.id)
        .limit(1)
    )
    return result.scalar_one_or_none()


async def published_prompt_candidates(
    db: AsyncSession, *, user_id: str, task: str, stage: str | None,
) -> list[tuple[PromptProfile, PromptProfileVersion]]:
    query = (
        select(PromptProfile, PromptProfileVersion)
        .join(PromptProfileVersion, PromptProfileVersion.profile_id == PromptProfile.id)
        .where(
            PromptProfile.task == task,
            PromptProfileVersion.status == "published",
            or_(PromptProfile.user_id == user_id, PromptProfile.user_id == "system"),
        )
    )
    if stage:
        query = query.where(or_(PromptProfileVersion.stage == stage, PromptProfileVersion.stage.is_(None)))
    return list((await db.execute(query)).all())


def legacy_prompt_skill_payload(
    skill: PromptSkill, version: PromptProfileVersion | None = None,
) -> dict[str, Any]:
    return {
        "id": skill.id, "user_id": skill.user_id, "name": skill.name,
        "description": skill.description, "task": skill.task,
        "stage": version.stage if version else skill.stage,
        "content": version.content if version else skill.content,
        "variables": version.variables if version else (skill.variables or {}),
        "priority": skill.priority, "inject_position": skill.inject_position,
        "version": version.version if version else skill.version,
        "is_active": bool(skill.is_active), "is_builtin": bool(skill.is_builtin),
        "tags": skill.tags or [],
        "created_at": skill.created_at.isoformat() if skill.created_at else None,
        "updated_at": skill.updated_at.isoformat() if skill.updated_at else None,
    }


def effective_legacy_prompt_skill_payloads(
    skills: list[PromptSkill], user_id: str,
    versions: dict[str, PromptProfileVersion] | None = None,
) -> list[dict[str, Any]]:
    user_active = {skill.task: skill.id for skill in skills if skill.is_active and not skill.is_builtin and skill.user_id == user_id}
    builtin_active = {skill.task: skill.id for skill in skills if skill.is_active and skill.is_builtin}
    effective_ids = set(user_active.values())
    effective_ids.update(skill_id for task, skill_id in builtin_active.items() if task not in user_active)
    payloads = []
    for skill in skills:
        payload = legacy_prompt_skill_payload(skill, (versions or {}).get(skill.id))
        payload["is_active"] = skill.id in effective_ids
        payloads.append(payload)
    return payloads


async def latest_versions_for_skills(
    db: AsyncSession, skills: Iterable[PromptSkill],
) -> dict[str, PromptProfileVersion]:
    profile_ids = [skill.id for skill in skills]
    if not profile_ids:
        return {}
    rows = list((await db.execute(
        select(PromptProfileVersion)
        .where(PromptProfileVersion.profile_id.in_(profile_ids))
        .order_by(PromptProfileVersion.profile_id, PromptProfileVersion.version.desc())
    )).scalars())
    latest: dict[str, PromptProfileVersion] = {}
    for row in rows:
        latest.setdefault(row.profile_id, row)
    return latest


def render_legacy_prompt_skill(skill: PromptSkill, context: dict[str, Any] | None = None) -> str:
    return render_prompt(skill.content or "", skill.variables or {}, context or {})


def rendered_legacy_prompt_skill_entry(
    skill: PromptSkill, context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": skill.id, "name": skill.name, "task": skill.task, "stage": skill.stage,
        "version": skill.version or 1, "content": render_legacy_prompt_skill(skill, context),
    }
