"""Secret-free reads used by the Prompt Usage Map."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.model_config.domain import ResolvedModelBinding
from app.models.model_center import ModelProfile, ModelProfileVersion, ModelProvider
from app.models.prompt_profile import PromptProfile, PromptProfileVersion
from app.features.prompt_profiles.repository import published_prompt_candidates
from app.features.prompt_profiles.versioning import create_prompt_profile_from_published_version


@dataclass(frozen=True)
class PromptUsageModelIdentity:
    profile_version_id: str
    provider_code: str
    provider_name: str
    api_model_id: str
    model_name: str
    capabilities: tuple[str, ...]
    prompt_profile_key: str | None


async def load_prompt_usage_model_identity(
    db: AsyncSession,
    binding: ResolvedModelBinding,
) -> PromptUsageModelIdentity:
    row = (await db.execute(
        select(ModelProfile.display_name, ModelProvider.code, ModelProvider.display_name)
        .join(ModelProfileVersion, ModelProfileVersion.model_id == ModelProfile.id)
        .join(ModelProvider, ModelProvider.id == ModelProfile.provider_id)
        .where(ModelProfileVersion.id == binding.profile.profile_version_id)
    )).one_or_none()
    if row is None:
        provider = await db.get(ModelProvider, binding.profile.provider_id)
        model_name = binding.profile.api_model_id
        provider_code = provider.code if provider else binding.profile.provider_id
        provider_name = provider.display_name if provider else provider_code
    else:
        model_name, provider_code, provider_name = row
    return PromptUsageModelIdentity(
        profile_version_id=binding.profile.profile_version_id,
        provider_code=provider_code,
        provider_name=provider_name,
        api_model_id=binding.profile.api_model_id,
        model_name=model_name,
        capabilities=tuple(sorted(binding.profile.capabilities)),
        prompt_profile_key=binding.profile.prompt_profile_key,
    )


async def load_prompt_usage_candidates(
    db: AsyncSession,
    *,
    user_id: str,
    task: str,
    stage: str | None,
) -> list[tuple[PromptProfile, PromptProfileVersion]]:
    return await published_prompt_candidates(
        db, user_id=user_id, task=task, stage=stage,
    )


async def load_prompt_usage_source(
    db: AsyncSession,
    *,
    user_id: str,
    version_id: str,
) -> tuple[PromptProfile, PromptProfileVersion] | None:
    row = await db.execute(
        select(PromptProfile, PromptProfileVersion)
        .join(PromptProfileVersion, PromptProfileVersion.profile_id == PromptProfile.id)
        .where(
            PromptProfileVersion.id == version_id,
            PromptProfileVersion.status == "published",
            PromptProfile.user_id.in_((user_id, "system")),
        )
    )
    return row.one_or_none()


async def create_model_prompt_draft(
    db: AsyncSession,
    *,
    user_id: str,
    source_profile: PromptProfile,
    source_version: PromptProfileVersion,
    model: PromptUsageModelIdentity,
    reason: str,
) -> tuple[PromptProfile, PromptProfileVersion]:
    key = f"usage.{source_profile.task}.{model.provider_code}.{model.api_model_id}.{source_version.id[:8]}"
    routing = {
        **dict(source_version.routing or {}),
        "provider_filter": [model.provider_code],
        "model_filter": [model.api_model_id],
    }
    return await create_prompt_profile_from_published_version(
        db, user_id=user_id, key=key,
        name=f"{source_profile.name} · {model.model_name}", task=source_profile.task,
        source=source_version, routing=routing, release_notes=reason,
    )


__all__ = [
    "PromptUsageModelIdentity", "create_model_prompt_draft",
    "load_prompt_usage_candidates", "load_prompt_usage_model_identity",
    "load_prompt_usage_source",
]
