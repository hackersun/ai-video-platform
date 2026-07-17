"""Read-only projections that retain legacy response shapes."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.model_registry import get_model_contract_metadata
from app.features.model_config.catalog import catalog_model_keys, is_product_visible_model, is_product_visible_provider
from app.features.model_config.repository import list_product_catalog
from app.models.external_api import ExternalAPIProvider
from app.models.llm_config import LLMConfig, LLMModel, LLMProvider


_EXTERNAL_PRODUCT_TYPES = frozenset({"audio_video", "workflow", "render", "lip_sync", "storage", "video"})


@dataclass(frozen=True)
class CatalogComparison:
    legacy_provider_ids: frozenset[str]
    canonical_provider_ids: frozenset[str]
    legacy_model_keys: frozenset[str]
    canonical_model_keys: frozenset[str]

    @property
    def equivalent(self) -> bool:
        return self.legacy_provider_ids == self.canonical_provider_ids and self.legacy_model_keys == self.canonical_model_keys

    def sanitized_summary(self) -> dict[str, object]:
        return {
            "equivalent": self.equivalent,
            "legacy_provider_count": len(self.legacy_provider_ids),
            "canonical_provider_count": len(self.canonical_provider_ids),
            "legacy_model_count": len(self.legacy_model_keys),
            "canonical_model_count": len(self.canonical_model_keys),
            "comparison_fingerprint": sha256(repr(self).encode()).hexdigest()[:16],
        }


def _primary_config(configs: list[LLMConfig]) -> LLMConfig | None:
    return next((config for config in configs if config.test_status == "success"), configs[0] if configs else None)


def _legacy_model_response(model: LLMModel, configs: list[LLMConfig]) -> dict:
    primary = _primary_config(configs)
    key_available = bool(primary and primary.get_api_key_decrypted())
    status = primary.test_status if primary else None
    message = primary.test_message if primary else None
    if primary is not None and not key_available:
        status, message = "failed", "API Key 为空或无法解密，请重新保存并验证该配置"
    return {
        "id": model.id, "provider_id": model.provider_id, "model_id": model.model_id,
        "model_name": model.model_name, "model_name_cn": model.model_name_cn, "model_type": model.model_type,
        "capabilities": model.capabilities or [], "context_window": model.context_window, "max_tokens": model.max_tokens,
        "input_cost_per_1k": model.input_cost_per_1k, "output_cost_per_1k": model.output_cost_per_1k,
        "is_active": model.is_active, "is_recommended": model.is_recommended, "description": model.description,
        "base_url": model.base_url, "user_config_id": primary.id if primary else None,
        "user_config_name": primary.name if primary else None, "user_configured": bool(primary),
        "user_config_count": len(configs), "user_is_default": bool(primary and primary.is_default),
        "user_test_status": status, "user_test_message": message, "user_key_available": key_available,
        **get_model_contract_metadata(model.model_id, model.provider_id),
    }


async def project_legacy_llm_models(
    db: AsyncSession, user_id: str, provider_id: str | None = None
) -> list[dict]:
    providers = {item.id: item for item in (await db.scalars(select(LLMProvider).where(LLMProvider.is_active == True))).all()}
    models = list((await db.scalars(select(LLMModel).where(LLMModel.is_active == True))).all())
    configs = list((await db.scalars(select(LLMConfig).where(LLMConfig.user_id == user_id, LLMConfig.is_active == True))).all())
    configs_by_model: dict[str, list[LLMConfig]] = {}
    for config in configs:
        configs_by_model.setdefault(config.model_id, []).append(config)
    return [
        _legacy_model_response(model, configs_by_model.get(model.id, []))
        for model in models
        if (provider_id is None or model.provider_id == provider_id)
        and (provider := providers.get(model.provider_id)) is not None
        and is_product_visible_provider(provider.id, provider.name, provider.name_cn, provider.name_en)
        and is_product_visible_model(model.id, model.model_id, model.model_name, model.model_name_cn)
    ]


def _external_capabilities(provider: ExternalAPIProvider) -> list[str]:
    return list(dict.fromkeys(capability for model in provider.supported_models or [] for capability in model.get("capabilities", [])))


async def project_legacy_external_providers(db: AsyncSession) -> list[dict]:
    providers = list((await db.scalars(select(ExternalAPIProvider).where(ExternalAPIProvider.is_active == True))).all())
    visible = [
        provider for provider in providers
        if provider.api_type in _EXTERNAL_PRODUCT_TYPES
        and is_product_visible_provider(provider.id, provider.name, provider.name_cn, provider.description)
    ]
    return [
        {
            "id": provider.id, "name": provider.name, "name_cn": provider.name_cn,
            "api_type": provider.api_type, "base_url": provider.base_url, "auth_type": provider.auth_type or "bearer",
            "is_active": bool(provider.is_active), "description": provider.description, "doc_url": provider.doc_url,
            "supported_models": provider.supported_models or [], "capabilities": _external_capabilities(provider),
        }
        for provider in visible
    ]


async def compare_legacy_and_canonical_catalogs(db: AsyncSession, user_id: str) -> CatalogComparison:
    legacy_models = await project_legacy_llm_models(db, user_id)
    canonical_catalog = await list_product_catalog(db, user_id)
    legacy_provider_ids = frozenset(item["provider_id"] for item in legacy_models)
    legacy_model_keys = frozenset(f"{item['provider_id']}:{item['model_id']}" for item in legacy_models)
    return CatalogComparison(
        legacy_provider_ids=legacy_provider_ids,
        canonical_provider_ids=frozenset(item.provider_id for item in canonical_catalog.models),
        legacy_model_keys=legacy_model_keys,
        canonical_model_keys=catalog_model_keys(canonical_catalog.models),
    )


__all__ = [
    "CatalogComparison",
    "compare_legacy_and_canonical_catalogs",
    "project_legacy_external_providers",
    "project_legacy_llm_models",
]
