"""Read-only evidence for linking legacy prompt skills to canonical profiles."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prompt_profile import PromptProfile, PromptProfileVersion
from app.models.prompt_skill import PromptSkill


@dataclass(frozen=True)
class PromptHashEvidence:
    skill_id: str
    legacy_hash: str
    linked_version_id: str | None
    linked_hash: str | None
    matches: bool | None


@dataclass(frozen=True)
class PromptLinkAudit:
    legacy_total: int
    legacy_nonempty: int
    active_total: int
    inactive_total: int
    linked_total: int
    orphan_profile_ids: tuple[str, ...]
    content_conflicts: tuple[str, ...]
    hash_evidence: tuple[PromptHashEvidence, ...]


def stable_prompt_hash(content: str | None) -> str:
    return sha256((content or "").encode("utf-8")).hexdigest()


async def _linked_versions(
    db: AsyncSession,
    skills: list[PromptSkill],
    user_id: str,
) -> dict[str, PromptProfileVersion]:
    version_ids = {
        skill.prompt_profile_version_id
        for skill in skills
        if skill.prompt_profile_version_id
    }
    if not version_ids:
        return {}
    rows = await db.scalars(
        select(PromptProfileVersion)
        .join(PromptProfile, PromptProfile.id == PromptProfileVersion.profile_id)
        .where(
            PromptProfileVersion.id.in_(version_ids),
            PromptProfile.user_id == user_id,
        )
    )
    return {row.id: row for row in rows.all()}


async def audit_prompt_links(db: AsyncSession, user_id: str) -> PromptLinkAudit:
    rows = await db.scalars(
        select(PromptSkill)
        .where(PromptSkill.user_id == user_id)
        .order_by(PromptSkill.id)
    )
    skills = list(rows.all())
    versions = await _linked_versions(db, skills, user_id)
    linked_ids = {
        skill.prompt_profile_version_id
        for skill in skills
        if skill.prompt_profile_version_id
    }
    evidence = tuple(_hash_evidence(skill, versions) for skill in skills)
    return PromptLinkAudit(
        legacy_total=len(skills),
        legacy_nonempty=sum(bool((skill.content or "").strip()) for skill in skills),
        active_total=sum(bool(skill.is_active) for skill in skills),
        inactive_total=sum(not bool(skill.is_active) for skill in skills),
        linked_total=sum(
            skill.prompt_profile_version_id in versions for skill in skills
        ),
        orphan_profile_ids=tuple(sorted(linked_ids - versions.keys())),
        content_conflicts=tuple(
            item.skill_id for item in evidence if item.matches is False
        ),
        hash_evidence=evidence,
    )


def _hash_evidence(
    skill: PromptSkill,
    versions: dict[str, PromptProfileVersion],
) -> PromptHashEvidence:
    version_id = skill.prompt_profile_version_id
    version = versions.get(version_id) if version_id else None
    legacy_hash = stable_prompt_hash(skill.content)
    linked_hash = stable_prompt_hash(version.content) if version else None
    return PromptHashEvidence(
        skill_id=skill.id,
        legacy_hash=legacy_hash,
        linked_version_id=version_id,
        linked_hash=linked_hash,
        matches=legacy_hash == linked_hash if linked_hash else None,
    )
