"""Read-only evidence for linking legacy prompt skills to canonical profiles."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from uuid import UUID, uuid5

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.features.prompt_profiles.versioning import (
    canonical_prompt_values_checksum,
    legacy_prompt_version_values,
)
from app.models.prompt_profile import PromptProfile, PromptProfileVersion
from app.models.prompt_skill import PromptSkill


_RECOVERY_NAMESPACE = UUID("dfebf25c-fd47-5bc4-8235-5d0d11a8897d")


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


@dataclass(frozen=True)
class PromptRecoveryAction:
    skill_id: str
    profile_id: str
    profile_key: str
    target_version_id: str
    target_version: int
    target_status: str
    create_profile: bool
    create_version: bool
    link_skill: bool


@dataclass(frozen=True)
class PromptRecoveryPlan:
    user_id: str
    actions: tuple[PromptRecoveryAction, ...]
    content_conflicts: tuple[str, ...] = ()

    @property
    def profiles_to_create(self) -> int:
        return sum(action.create_profile for action in self.actions)

    @property
    def versions_to_create(self) -> int:
        return sum(action.create_version for action in self.actions)

    @property
    def links_to_update(self) -> int:
        return sum(action.link_skill for action in self.actions)

    def sanitized_dict(self) -> dict[str, object]:
        return {
            "profiles_to_create": self.profiles_to_create,
            "versions_to_create": self.versions_to_create,
            "links_to_update": self.links_to_update,
            "content_conflicts": self.content_conflicts,
        }


@dataclass(frozen=True)
class PromptRecoveryReport:
    profiles_created: int = 0
    versions_created: int = 0
    skills_linked: int = 0
    content_conflicts: tuple[str, ...] = ()

    @property
    def created_total(self) -> int:
        return self.profiles_created + self.versions_created

    @property
    def updated_total(self) -> int:
        return self.skills_linked

    def sanitized_dict(self) -> dict[str, object]:
        return asdict(self) | {
            "created_total": self.created_total,
            "updated_total": self.updated_total,
        }


class PromptRecoveryConflict(ValueError):
    def __init__(self, conflicts: tuple[str, ...]) -> None:
        self.conflicts = conflicts
        super().__init__("prompt recovery conflicts: " + ", ".join(conflicts))


def stable_prompt_hash(content: str | None) -> str:
    return sha256((content or "").encode("utf-8")).hexdigest()


def _recovery_id(kind: str, identity: str) -> str:
    return str(uuid5(_RECOVERY_NAMESPACE, f"{kind}:{identity}"))


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


async def _owned_linked_version(
    db: AsyncSession, *, user_id: str, version_id: str | None,
) -> PromptProfileVersion | None:
    if not version_id:
        return None
    return await db.scalar(
        select(PromptProfileVersion)
        .join(PromptProfile, PromptProfile.id == PromptProfileVersion.profile_id)
        .where(
            PromptProfileVersion.id == version_id,
            PromptProfile.user_id == user_id,
        )
    )


async def _candidate_profile(
    db: AsyncSession, skill: PromptSkill,
) -> tuple[PromptProfile | None, PromptProfileVersion | None]:
    keys = (f"legacy.{skill.id}", f"legacy:{skill.id}")
    profiles = list((await db.scalars(
        select(PromptProfile)
        .where(
            PromptProfile.user_id == skill.user_id,
            or_(PromptProfile.id == skill.id, PromptProfile.key.in_(keys)),
        )
        .order_by(PromptProfile.id)
    )).all())
    for profile in profiles:
        latest = await _latest_version(db, profile.id)
        if latest and stable_prompt_hash(latest.content) == stable_prompt_hash(skill.content):
            return profile, latest
    return None, None


async def _latest_version(
    db: AsyncSession, profile_id: str,
) -> PromptProfileVersion | None:
    return await db.scalar(
        select(PromptProfileVersion)
        .where(PromptProfileVersion.profile_id == profile_id)
        .order_by(PromptProfileVersion.version.desc(), PromptProfileVersion.id)
        .limit(1)
    )


async def _plan_skill_recovery(
    db: AsyncSession, skill: PromptSkill,
) -> tuple[PromptRecoveryAction | None, str | None]:
    desired_status = "published" if skill.is_active else "disabled"
    linked = await _owned_linked_version(
        db,
        user_id=skill.user_id,
        version_id=skill.prompt_profile_version_id,
    )
    if skill.prompt_profile_version_id and linked is None:
        return None, f"{skill.id}:orphan_link"
    if linked and stable_prompt_hash(linked.content) != stable_prompt_hash(skill.content):
        return None, f"{skill.id}:content_mismatch"
    profile = await db.get(PromptProfile, linked.profile_id) if linked else None
    latest = linked
    if profile is None:
        profile, latest = await _candidate_profile(db, skill)
    create_profile = profile is None
    if create_profile:
        profile_id = _recovery_id("profile", f"{skill.user_id}:{skill.id}")
        profile = await db.get(PromptProfile, profile_id)
        if profile is not None:
            latest = await _latest_version(db, profile.id)
            if latest and stable_prompt_hash(latest.content) != stable_prompt_hash(skill.content):
                return None, f"{skill.id}:recovery_profile_conflict"
            create_profile = False
        profile_key = f"legacy.recovered.{skill.id}"
    else:
        profile_id = profile.id
        profile_key = profile.key
    if latest and latest.status == desired_status:
        return PromptRecoveryAction(
            skill.id, profile_id, profile_key, latest.id, latest.version,
            desired_status, create_profile, False,
            skill.prompt_profile_version_id != latest.id,
        ), None
    version_number = (latest.version + 1) if latest else max(int(skill.version or 1), 1)
    version_id = _recovery_id(
        "version",
        f"{profile_id}:{version_number}:{stable_prompt_hash(skill.content)}:{desired_status}",
    )
    return PromptRecoveryAction(
        skill.id, profile_id, profile_key, version_id, version_number,
        desired_status, create_profile, True,
        skill.prompt_profile_version_id != version_id,
    ), None


async def plan_prompt_recovery(
    db: AsyncSession, *, user_id: str,
) -> PromptRecoveryPlan:
    skills = list((await db.scalars(
        select(PromptSkill)
        .where(PromptSkill.user_id == user_id)
        .order_by(PromptSkill.id)
    )).all())
    actions: list[PromptRecoveryAction] = []
    conflicts: list[str] = []
    for skill in skills:
        action, conflict = await _plan_skill_recovery(db, skill)
        if action:
            actions.append(action)
        if conflict:
            conflicts.append(conflict)
    return PromptRecoveryPlan(user_id, tuple(actions), tuple(sorted(conflicts)))


async def apply_prompt_recovery(
    db: AsyncSession, *, user_id: str,
) -> PromptRecoveryReport:
    plan = await plan_prompt_recovery(db, user_id=user_id)
    if plan.content_conflicts:
        raise PromptRecoveryConflict(plan.content_conflicts)
    profiles_created = versions_created = skills_linked = 0
    for action in plan.actions:
        skill = await db.get(PromptSkill, action.skill_id)
        if action.create_profile:
            db.add(PromptProfile(
                id=action.profile_id, user_id=skill.user_id,
                key=action.profile_key, name=skill.name, task=skill.task,
            ))
            profiles_created += 1
        if action.create_version:
            values = legacy_prompt_version_values(skill)
            evaluation = {
                "migration": {
                    "source": "prompt_skill",
                    "skill_id": skill.id,
                    "legacy_version": int(skill.version or 1),
                    "content_hash": stable_prompt_hash(skill.content),
                }
            }
            db.add(PromptProfileVersion(
                id=action.target_version_id,
                profile_id=action.profile_id,
                version=action.target_version,
                **values,
                evaluation=evaluation,
                status=action.target_status,
                checksum=canonical_prompt_values_checksum(values, evaluation),
                published_at=utc_now() if action.target_status == "published" else None,
            ))
            versions_created += 1
        if action.link_skill:
            skill.prompt_profile_version_id = action.target_version_id
            skills_linked += 1
    await db.flush()
    return PromptRecoveryReport(
        profiles_created=profiles_created,
        versions_created=versions_created,
        skills_linked=skills_linked,
    )
