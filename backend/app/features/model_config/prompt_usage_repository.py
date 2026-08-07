"""Secret-free reads used by the Prompt Usage Map."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.model_config.domain import ResolvedModelBinding
from app.models.model_center import ModelProfile, ModelProfileVersion, ModelProvider


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


__all__ = ["PromptUsageModelIdentity", "load_prompt_usage_model_identity"]
