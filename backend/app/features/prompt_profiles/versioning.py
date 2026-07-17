"""Append-only Prompt Profile version workflows."""

from __future__ import annotations

from copy import deepcopy
from hmac import compare_digest
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.features.prompt_profiles.domain import stable_prompt_checksum
from app.features.prompt_profiles.repository import (
    get_profile,
    get_profile_version,
    latest_profile_version,
)
from app.models.prompt_profile import PromptProfile, PromptProfileVersion
from app.models.prompt_skill import PromptSkill


VERSION_FIELDS = ("stage", "content", "variables", "routing", "output_contract")


def _canonical_checksum(values: dict[str, Any], evaluation: dict[str, Any]) -> str:
    return stable_prompt_checksum({
        **{field: deepcopy(values.get(field)) for field in VERSION_FIELDS},
        "evaluation": deepcopy(evaluation),
    })


def canonical_prompt_version_checksum(version: PromptProfileVersion) -> str:
    values = {field: getattr(version, field) for field in VERSION_FIELDS}
    return _canonical_checksum(values, version.evaluation or {})


def _version_payload(source: PromptProfileVersion, changes: dict[str, Any]) -> dict[str, Any]:
    unsupported = set(changes) - set(VERSION_FIELDS)
    if unsupported:
        raise ValueError(f"unsupported prompt version changes: {', '.join(sorted(unsupported))}")
    values = {field: deepcopy(getattr(source, field)) for field in VERSION_FIELDS}
    values.update(deepcopy(changes))
    if not str(values["content"] or "").strip():
        raise ValueError("prompt profile content is required")
    return values


async def edit_prompt_profile(
    db: AsyncSession, version_id: str, changes: dict[str, Any],
) -> PromptProfileVersion:
    source = await get_profile_version(db, version_id)
    latest = await latest_profile_version(db, source.profile_id)
    values = _version_payload(source, changes)
    checksum = _canonical_checksum(values, {})
    draft = PromptProfileVersion(
        id=str(uuid4()), profile_id=source.profile_id,
        version=(latest.version if latest else source.version) + 1,
        **values, evaluation={}, status="draft", checksum=checksum,
    )
    db.add(draft)
    await db.flush()
    return draft


async def publish_prompt_profile_version(
    db: AsyncSession, version_id: str,
) -> PromptProfileVersion:
    version = await get_profile_version(db, version_id)
    if version.status == "published":
        return version
    if version.status != "draft":
        raise ValueError("only a draft prompt profile can be published")
    expected_checksum = canonical_prompt_version_checksum(version)
    if not compare_digest(str(version.checksum or ""), expected_checksum):
        raise ValueError("prompt profile checksum mismatch; recompute before publishing")
    version.status = "published"
    version.published_at = utc_now()
    await db.flush()
    return version


def _legacy_version_values(skill: PromptSkill) -> dict[str, Any]:
    variables = deepcopy(skill.variables or {})
    routing = deepcopy(variables.get("routing") if isinstance(variables.get("routing"), dict) else {})
    return {
        "stage": skill.stage, "content": skill.content, "variables": variables,
        "routing": routing, "output_contract": routing.get("output_contract"),
    }


async def ensure_legacy_prompt_profile(
    db: AsyncSession, skill: PromptSkill,
) -> PromptProfileVersion:
    latest = await latest_profile_version(db, skill.id)
    if latest is not None:
        skill.prompt_profile_version_id = latest.id
        return latest
    db.add(PromptProfile(
        id=skill.id, user_id=skill.user_id, key=f"legacy.{skill.id}",
        name=skill.name, task=skill.task,
    ))
    values = _legacy_version_values(skill)
    version = PromptProfileVersion(
        id=str(uuid4()), profile_id=skill.id, version=int(skill.version or 1),
        **values, evaluation={}, status="published" if skill.is_active else "draft",
        checksum=_canonical_checksum(values, {}),
        published_at=utc_now() if skill.is_active else None,
    )
    db.add(version)
    skill.prompt_profile_version_id = version.id
    await db.flush()
    return version


async def edit_legacy_prompt_profile(
    db: AsyncSession, skill: PromptSkill, data: dict[str, Any],
) -> PromptProfileVersion:
    source = await ensure_legacy_prompt_profile(db, skill)
    merged_variables = deepcopy(data.get("variables", skill.variables or {}))
    routing = merged_variables.get("routing") if isinstance(merged_variables.get("routing"), dict) else {}
    changes = {
        "stage": data.get("stage", skill.stage), "content": data.get("content", skill.content),
        "variables": merged_variables, "routing": deepcopy(routing),
        "output_contract": routing.get("output_contract"),
    }
    draft = await edit_prompt_profile(db, source.id, changes)
    skill.prompt_profile_version_id = draft.id
    return draft


def apply_version_to_legacy_skill(skill: PromptSkill, version: PromptProfileVersion) -> None:
    skill.stage = version.stage
    skill.content = version.content
    skill.variables = deepcopy(version.variables or {})
    skill.version = version.version
    skill.prompt_profile_version_id = version.id


async def disable_legacy_prompt_profile(
    db: AsyncSession, skill: PromptSkill,
) -> PromptProfileVersion:
    source = await ensure_legacy_prompt_profile(db, skill)
    if source.status == "disabled":
        skill.prompt_profile_version_id = source.id
        return source
    values = {field: deepcopy(getattr(source, field)) for field in VERSION_FIELDS}
    disabled = PromptProfileVersion(
        id=str(uuid4()), profile_id=source.profile_id, version=source.version + 1,
        **values, evaluation={}, status="disabled",
        checksum=_canonical_checksum(values, {}),
    )
    db.add(disabled)
    skill.prompt_profile_version_id = disabled.id
    await db.flush()
    return disabled


async def retire_legacy_prompt_profile(db: AsyncSession, skill: PromptSkill) -> None:
    latest = await latest_profile_version(db, skill.id)
    if latest is None:
        return
    published = await db.execute(
        select(PromptProfileVersion.id).where(
            PromptProfileVersion.profile_id == skill.id,
            PromptProfileVersion.status == "published",
        ).limit(1)
    )
    if published.first() is not None:
        await disable_legacy_prompt_profile(db, skill)
        return
    versions = await db.execute(
        select(PromptProfileVersion).where(
            PromptProfileVersion.profile_id == skill.id,
        )
    )
    for version in versions.scalars():
        await db.delete(version)
    await db.flush()
    profile = await get_profile(db, skill.id)
    await db.delete(profile)
