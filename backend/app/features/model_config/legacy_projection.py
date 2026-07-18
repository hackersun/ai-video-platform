"""Read-only projections that retain legacy response shapes."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.model_registry import get_model_contract_metadata
from app.features.model_config.catalog import (
    catalog_model_keys,
    dedupe_legacy_models,
    group_legacy_configs,
    is_product_visible_model,
    is_product_visible_provider,
    select_legacy_external_providers,
    select_primary_legacy_config,
)
from app.features.model_config.repository import list_product_catalog
from app.features.model_config.settings import ModelCenterReadMode, model_center_read_mode
from app.models.external_api import ExternalAPIProvider
from app.models.llm_config import LLMConfig, LLMModel, LLMProvider


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
        payload = {
            "canonical_model_keys": sorted(self.canonical_model_keys),
            "canonical_provider_ids": sorted(self.canonical_provider_ids),
            "legacy_model_keys": sorted(self.legacy_model_keys),
            "legacy_provider_ids": sorted(self.legacy_provider_ids),
        }
        fingerprint = sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()[:16]
        return {
            "equivalent": self.equivalent,
            "legacy_provider_count": len(self.legacy_provider_ids),
            "canonical_provider_count": len(self.canonical_provider_ids),
            "legacy_model_count": len(self.legacy_model_keys),
            "canonical_model_count": len(self.canonical_model_keys),
            "comparison_fingerprint": fingerprint,
        }


def _legacy_model_response(model: LLMModel, configs: list[LLMConfig]) -> dict:
    primary = select_primary_legacy_config(configs)
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
    provider_result = await db.execute(select(LLMProvider).where(LLMProvider.is_active == True))
    providers = {item.id: item for item in provider_result.scalars().all()}
    requested_provider = providers.get(provider_id) if provider_id is not None else None
    if requested_provider is not None and not is_product_visible_provider(requested_provider):
        return []
    model_query = select(LLMModel).where(LLMModel.is_active == True)
    if provider_id is not None:
        model_query = model_query.where(LLMModel.provider_id == provider_id)
    models = list((await db.execute(model_query)).scalars().all())
    visible_models = [
        model for model in models
        if (provider := providers.get(model.provider_id)) is not None
        and is_product_visible_provider(provider)
        and is_product_visible_model(model)
    ]
    if not visible_models:
        return []
    configs = list((await db.execute(select(LLMConfig).where(
        LLMConfig.user_id == user_id,
        LLMConfig.is_active == True,
        LLMConfig.model_id.in_([model.id for model in visible_models]),
    ))).scalars().all())
    configs_by_model = group_legacy_configs(configs)
    return [
        _legacy_model_response(model, configs_by_model.get(model.id, []))
        for model in dedupe_legacy_models(visible_models, configs_by_model)
    ]


def external_provider_capabilities(provider: ExternalAPIProvider) -> list[str]:
    return list(dict.fromkeys(capability for model in provider.supported_models or [] for capability in model.get("capabilities", [])))


def build_legacy_external_provider_response(provider: ExternalAPIProvider) -> dict:
    return {
        "id": provider.id, "name": provider.name, "name_cn": provider.name_cn,
        "api_type": provider.api_type, "base_url": provider.base_url, "auth_type": provider.auth_type or "bearer",
        "is_active": bool(provider.is_active), "description": provider.description, "doc_url": provider.doc_url,
        "supported_models": provider.supported_models or [], "capabilities": external_provider_capabilities(provider),
    }


async def project_legacy_external_providers(db: AsyncSession) -> list[dict]:
    providers = list((await db.execute(
        select(ExternalAPIProvider).where(ExternalAPIProvider.is_active == True)
    )).scalars().all())
    visible = select_legacy_external_providers(providers)
    return [build_legacy_external_provider_response(provider) for provider in visible]


async def compare_legacy_and_canonical_catalogs(
    db: AsyncSession,
    user_id: str,
    legacy_models: list[dict] | None = None,
) -> CatalogComparison:
    if legacy_models is None:
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


async def maybe_log_shadow_catalog_comparison(
    db: AsyncSession,
    user_id: str,
    legacy_models: list[dict],
    logger,
) -> None:
    try:
        if model_center_read_mode() is not ModelCenterReadMode.SHADOW:
            return
        comparison = await compare_legacy_and_canonical_catalogs(db, user_id, legacy_models)
        summary = comparison.sanitized_summary()
        summary.pop("equivalent")
        logger.info(
            "model_center_catalog_shadow",
            extra={"model_center_shadow": summary},
        )
    except Exception:
        try:
            logger.warning(
                "model_center_catalog_shadow_failed",
                extra={"model_center_shadow": {"status": "failed"}},
            )
        except Exception:
            pass
        return


__all__ = [
    "CatalogComparison",
    "build_legacy_external_provider_response",
    "compare_legacy_and_canonical_catalogs",
    "maybe_log_shadow_catalog_comparison",
    "project_legacy_external_providers",
    "project_legacy_llm_models",
]
