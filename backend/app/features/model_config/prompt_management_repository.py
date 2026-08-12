"""Repository operations for immutable Model Center Prompt Profile versions."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
from uuid import uuid4

from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.models.model_center import ModelBinding, ModelConfigAuditEvent, ModelProfileVersion, ProductionRecipeVersion
from app.models.prompt_profile import PromptProfile, PromptProfileVersion
from app.models.prompt_skill import PromptSkill


@dataclass(frozen=True)
class PromptVersionRow:
    id: str
    profile_id: str
    profile_key: str
    user_id: str
    name: str
    task: str
    version: int
    status: str
    values: dict


def _checksum(values: dict) -> str:
    encoded = json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return sha256(encoded).hexdigest()


def prompt_version_values(row: PromptProfileVersion) -> dict:
    content = _structured_content(row.content)
    return {
        "stage": row.stage,
        "system_contract": content["system_contract"],
        "task_template": content["task_template"],
        "negative_constraints": content.get("negative_constraints", []),
        "input_mapping": deepcopy(row.variables or {}),
        "model_family_overrides": deepcopy(row.routing or {}),
        "output_schema": deepcopy((row.evaluation or {}).get("output_schema", {})),
        "validation_fixtures": deepcopy((row.evaluation or {}).get("validation_fixtures", [])),
        "release_notes": str((row.evaluation or {}).get("release_notes", "")),
    }


def _structured_content(raw_content: str | None) -> dict:
    """Convert pre-Model-Center PromptSkill text without exposing it in errors."""
    try:
        parsed = json.loads(raw_content or "")
    except (TypeError, ValueError):
        parsed = None
    if isinstance(parsed, dict) and all(
        isinstance(parsed.get(field), str) and parsed[field].strip()
        for field in ("system_contract", "task_template")
    ):
        return parsed
    return {
        "system_contract": "Legacy PromptSkill compatibility profile.",
        "task_template": str(raw_content or "").strip() or "Complete the requested task.",
        "negative_constraints": [],
    }


def _row(profile: PromptProfile, version: PromptProfileVersion) -> PromptVersionRow:
    return PromptVersionRow(
        id=version.id, profile_id=profile.id, profile_key=profile.key, user_id=profile.user_id,
        name=profile.name, task=profile.task, version=version.version, status=version.status,
        values=prompt_version_values(version),
    )


def _new_version(profile_id: str, version: int, values: dict) -> PromptProfileVersion:
    content = {
        "system_contract": values["system_contract"],
        "task_template": values["task_template"],
        "negative_constraints": values.get("negative_constraints", []),
    }
    evaluation = {
        "output_schema": values.get("output_schema", {}),
        "validation_fixtures": values.get("validation_fixtures", []),
        "release_notes": values.get("release_notes", ""),
    }
    payload = deepcopy(values)
    return PromptProfileVersion(
        id=str(uuid4()), profile_id=profile_id, version=version, stage=values.get("stage"),
        content=json.dumps(content, ensure_ascii=False, sort_keys=True),
        variables=deepcopy(values.get("input_mapping", {})),
        routing=deepcopy(values.get("model_family_overrides", {})),
        output_contract=str(values.get("output_schema", {}).get("type", "json"))[:120],
        evaluation=evaluation, status="draft", checksum=_checksum(payload),
    )


async def create_prompt_profile(
    db: AsyncSession, *, user_id: str, key: str, name: str, task: str, values: dict,
) -> PromptVersionRow | None:
    existing = await db.scalar(select(PromptProfile.id).where(
        PromptProfile.user_id == user_id, PromptProfile.key == key,
    ).limit(1))
    if existing:
        return None
    profile = PromptProfile(id=str(uuid4()), user_id=user_id, key=key, name=name, task=task)
    version = _new_version(profile.id, 1, values)
    db.add_all([profile, version])
    await db.flush()
    return _row(profile, version)


async def load_prompt_version_for_user(
    db: AsyncSession, *, version_id: str, user_id: str,
) -> PromptVersionRow | None:
    row = await db.execute(select(PromptProfile, PromptProfileVersion).join(
        PromptProfileVersion, PromptProfileVersion.profile_id == PromptProfile.id,
    ).where(PromptProfileVersion.id == version_id, PromptProfile.user_id == user_id))
    pair = row.one_or_none()
    return _row(*pair) if pair else None


async def create_prompt_draft(
    db: AsyncSession, *, profile_id: str, user_id: str, expected_version: int, changes: dict,
) -> PromptVersionRow | None:
    latest_pair = await db.execute(select(PromptProfile, PromptProfileVersion).join(
        PromptProfileVersion, PromptProfileVersion.profile_id == PromptProfile.id,
    ).where(PromptProfile.id == profile_id, PromptProfile.user_id == user_id).order_by(
        desc(PromptProfileVersion.version), desc(PromptProfileVersion.id),
    ).limit(1))
    pair = latest_pair.one_or_none()
    if pair is None:
        return None
    profile, latest = pair
    if latest.version != expected_version:
        return None
    values = prompt_version_values(latest)
    values.update(deepcopy(changes))
    if not values.get("system_contract") or not values.get("task_template"):
        raise ValueError("prompt_profile_fields_required")
    version = _new_version(profile.id, latest.version + 1, values)
    db.add(version)
    await db.flush()
    return _row(profile, version)


async def publish_prompt_draft(
    db: AsyncSession, *, candidate: PromptVersionRow, expected_version: int, reason: str,
    action: str = "publish", previous_version_id: str | None = None,
) -> tuple[PromptVersionRow, str] | None:
    result = await db.execute(update(PromptProfileVersion).where(
        PromptProfileVersion.id == candidate.id,
        PromptProfileVersion.status == "draft",
        PromptProfileVersion.version == expected_version,
    ).values(status="published", published_at=utc_now()).returning(PromptProfileVersion.id))
    if result.scalar_one_or_none() is None:
        return None
    row = await db.get(PromptProfileVersion, candidate.id)
    audit = ModelConfigAuditEvent(
        id=str(uuid4()), user_id=candidate.user_id, resource_type="prompt_profile",
        resource_id=candidate.profile_id, action=action, from_version_id=previous_version_id,
        to_version_id=candidate.id, reason=reason,
        sanitized_change_summary={"version": candidate.version, "profile_key": candidate.profile_key},
    )
    db.add(audit)
    await db.flush()
    profile = await db.get(PromptProfile, candidate.profile_id)
    return _row(profile, row), audit.id


async def load_prompt_rollback_rows(
    db: AsyncSession, *, profile_id: str, user_id: str, target_id: str,
) -> tuple[PromptVersionRow | None, PromptVersionRow | None]:
    rows = await db.execute(select(PromptProfile, PromptProfileVersion).join(
        PromptProfileVersion, PromptProfileVersion.profile_id == PromptProfile.id,
    ).where(PromptProfile.id == profile_id, PromptProfile.user_id == user_id).order_by(
        desc(PromptProfileVersion.version), desc(PromptProfileVersion.id),
    ))
    items = [_row(profile, version) for profile, version in rows.all()]
    return next((item for item in items if item.id == target_id), None), (items[0] if items else None)


async def load_owned_prompt_profile_history(
    db: AsyncSession,
    *,
    user_id: str,
    profile_id: str,
) -> tuple[PromptProfile | None, list[PromptProfileVersion]]:
    profile = await db.scalar(select(PromptProfile).where(
        PromptProfile.id == profile_id,
        PromptProfile.user_id == user_id,
    ))
    if profile is None:
        return None, []
    versions = list((await db.scalars(
        select(PromptProfileVersion)
        .where(PromptProfileVersion.profile_id == profile_id)
        .order_by(desc(PromptProfileVersion.version), desc(PromptProfileVersion.id))
    )).all())
    return profile, versions


async def load_visible_prompt_profile_history(
    db: AsyncSession,
    *,
    user_id: str,
    profile_id: str,
) -> tuple[PromptProfile | None, list[PromptProfileVersion]]:
    profile = await db.scalar(select(PromptProfile).where(
        PromptProfile.id == profile_id,
        PromptProfile.user_id.in_((user_id, "system")),
    ))
    if profile is None:
        return None, []
    versions = list((await db.scalars(
        select(PromptProfileVersion)
        .where(PromptProfileVersion.profile_id == profile_id)
        .order_by(desc(PromptProfileVersion.version), desc(PromptProfileVersion.id))
    )).all())
    return profile, versions


async def load_linked_prompt_skill(
    db: AsyncSession,
    *,
    user_id: str,
    profile_id: str,
    version_ids: list[str],
) -> PromptSkill | None:
    linked = await db.scalar(select(PromptSkill).where(
        PromptSkill.user_id == user_id,
        PromptSkill.prompt_profile_version_id.in_(version_ids),
    ).limit(1))
    if linked is not None:
        return linked
    return await db.scalar(select(PromptSkill).where(
        PromptSkill.user_id == user_id,
        PromptSkill.id == profile_id,
    ).limit(1))


async def prompt_impact(db: AsyncSession, *, user_id: str, profile_id: str | None = None) -> dict:
    profile_key = None
    if profile_id:
        profile_key = await db.scalar(select(PromptProfile.key).where(
            PromptProfile.id == profile_id, PromptProfile.user_id == user_id,
        ))
    profile_versions = select(ModelProfileVersion.id)
    if profile_key:
        profile_versions = profile_versions.where(ModelProfileVersion.prompt_profile_key == profile_key)
    version_ids = list((await db.scalars(profile_versions)).all())
    binding_count = 0
    if version_ids:
        binding_count = int(await db.scalar(select(func.count()).select_from(ModelBinding).where(
            ModelBinding.user_id == user_id, ModelBinding.profile_version_id.in_(version_ids),
        )) or 0)
    recipe_count = int(await db.scalar(select(func.count()).select_from(ProductionRecipeVersion).where(
        ProductionRecipeVersion.user_id == user_id,
    )) or 0)
    return {
        "affected_bindings": binding_count, "affected_profiles": len(version_ids),
        "affected_recipes": recipe_count, "affected_prompts": 1 if profile_key else 0,
        "affected_prompt_profiles": 1 if profile_key else 0,
    }
