"""Product-facing catalog contracts and visibility rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from app.features.model_config.domain import ModelCapability


PRODUCT_VISIBILITY = "product"
_INTERNAL_PREFIXES = ("contract-", "preflight-", "test-", "placeholder-")
_INTERNAL_PROVIDER_PREFIXES = ("preflight-", "test-provider-", "placeholder-provider-", "contract-")
_INTERNAL_PROVIDER_IDS = frozenset({"deterministic-acceptance"})
_INTERNAL_PROVIDER_LABELS = frozenset({"预检供应商", "测试供应商", "占位供应商", "TTS开通供应商"})
_EXTERNAL_PRODUCT_TYPES = frozenset({"audio_video", "workflow", "render", "lip_sync", "storage", "video"})
_EXTERNAL_PROVIDER_ORDER = (
    "openai", "google", "comfyui", "ffmpeg_cloud", "local_ffmpeg",
    "lip_sync", "object_storage", "runway", "qwen",
)


def is_product_visible(identifier: str, visibility: str | None = None) -> bool:
    """Keep seeded acceptance and placeholder records out of product catalogs."""
    if visibility:
        return visibility == PRODUCT_VISIBILITY
    normalized = identifier.strip().lower()
    return not (
        normalized == "deterministic-acceptance"
        or normalized.startswith(_INTERNAL_PREFIXES)
    )


def _field(record, name: str) -> str:
    return str(getattr(record, name, None) or "").strip()


def is_product_visible_provider(provider) -> bool:
    name_cn = _field(provider, "name_cn")
    values = [
        _field(provider, name)
        for name in ("id", "name", "code", "name_en", "name_cn", "display_name", "base_url", "description")
    ]
    normalized = " ".join(values).lower()
    return bool(normalized) and not (
        name_cn in _INTERNAL_PROVIDER_LABELS
        or _field(provider, "id").lower() in _INTERNAL_PROVIDER_IDS
        or any(part.startswith(_INTERNAL_PROVIDER_PREFIXES) for part in normalized.split())
        or "tts-provider-" in normalized
    )


def is_product_visible_model(model) -> bool:
    identifier_values = [_field(model, name) for name in ("id", "provider_id", "model_id", "api_model_id", "model_name")]
    display_values = [_field(model, name) for name in ("model_name_cn", "display_name", "description")]
    identifier_text = " ".join(identifier_values).lower()
    display_text = " ".join(display_values).lower()
    text = f"{identifier_text} {display_text}".strip()
    return bool(text) and not (
        any(marker in text for marker in ("test-video-", "test-audio-", "test-image-", "test-text-"))
        or text.startswith("test-")
        or identifier_text.startswith("tts-model-")
        or any(marker in identifier_text for marker in ("tts-api-model", "tts api model", "video-api-model", "video api model", "image-api-model", "image api model", "audio-api-model", "audio api model"))
        or "api model" in display_text
        or "-test-" in identifier_text
        or identifier_text.endswith("-test")
        or " test " in f" {identifier_text} "
        or "测试" in display_text
        or "preflight-" in text
        or "preflight video model" in text
        or "doubao-seedance-test" in text
        or "doubao-seedance-consistency-test" in text
        or "speech-test" in text
    )


def is_product_visible_external_provider(provider) -> bool:
    values = [_field(provider, name) for name in ("id", "name", "name_cn", "description")]
    normalized = " ".join(values).lower()
    return not (
        "测试供应商" in _field(provider, "name_cn")
        or "test" in normalized
        or "external-provider-" in normalized
    )


def legacy_model_capability_group(model) -> str:
    model_type = _field(model, "model_type").lower()
    capabilities = {str(item).lower() for item in (getattr(model, "capabilities", None) or [])}
    if model_type == "vision" or capabilities.intersection({"vision", "multimodal", "image_understanding"}):
        return "vision"
    if model_type in {"chat", "completion", "text-generation", "text_generation", "llm"}:
        return "text"
    if model_type in {"image", "image-generation", "image_generation"}:
        return "image"
    if model_type in {"tts", "audio", "speech"}:
        return "audio"
    if model_type in {"video", "video-generation", "video_generation"}:
        return "video"
    return "embedding" if model_type == "embedding" else model_type or "other"


def _timestamp(value) -> float:
    return value.timestamp() if value is not None else 0.0


def legacy_config_rank(config) -> tuple:
    return (
        bool(getattr(config, "is_default", False)),
        _timestamp(getattr(config, "updated_at", None)),
        _timestamp(getattr(config, "created_at", None)),
        _field(config, "id"),
    )


def group_legacy_configs(configs: Iterable) -> dict[str, list]:
    grouped: dict[str, list] = {}
    for config in sorted(configs, key=legacy_config_rank, reverse=True):
        grouped.setdefault(_field(config, "model_id"), []).append(config)
    return grouped


def select_primary_legacy_config(configs: Sequence):
    return max(configs, key=legacy_config_rank) if configs else None


def _legacy_model_display_key(model) -> tuple[str, str, str]:
    api_model_id = (_field(model, "model_id") or _field(model, "id")).lower()
    return (_field(model, "provider_id"), api_model_id, legacy_model_capability_group(model))


def _legacy_model_display_rank(model, configs_by_model: dict[str, list]) -> tuple:
    primary = select_primary_legacy_config(configs_by_model.get(_field(model, "id"), []))
    return (
        bool(primary and primary.is_default), bool(primary),
        bool(primary and primary.test_status == "success"),
        "." not in _field(model, "id"), bool(getattr(model, "is_recommended", False)),
        _timestamp(getattr(primary, "updated_at", None)), _field(model, "id"),
    )


def dedupe_legacy_models(models: Sequence, configs_by_model: dict[str, list]) -> list:
    selected: dict[tuple[str, str, str], object] = {}
    order: list[tuple[str, str, str]] = []
    for model in models:
        key = _legacy_model_display_key(model)
        current = selected.get(key)
        if current is None:
            order.append(key)
        if current is None or _legacy_model_display_rank(model, configs_by_model) > _legacy_model_display_rank(current, configs_by_model):
            selected[key] = model
    return [selected[key] for key in order]


def select_legacy_external_providers(providers: Sequence) -> list:
    default_order = {provider_id: index for index, provider_id in enumerate(_EXTERNAL_PROVIDER_ORDER)}
    visible = [
        provider for provider in providers
        if _field(provider, "api_type") in _EXTERNAL_PRODUCT_TYPES
        and is_product_visible_external_provider(provider)
    ]
    return sorted(visible, key=lambda provider: (default_order.get(_field(provider, "id"), len(default_order)), _field(provider, "name_cn") or _field(provider, "name")))


@dataclass(frozen=True)
class ProductCatalogItem:
    provider_id: str
    api_model_id: str
    profile_version_id: str | None
    legacy_model_id: str | None
    legacy_config_id: str | None
    certification_status: str
    capabilities: frozenset[ModelCapability]


@dataclass(frozen=True)
class ProductCatalog:
    models: tuple[ProductCatalogItem, ...]


def catalog_model_keys(items: Iterable[ProductCatalogItem]) -> frozenset[str]:
    return frozenset(f"{item.provider_id}:{item.api_model_id}" for item in items)


__all__ = [
    "PRODUCT_VISIBILITY",
    "ProductCatalog",
    "ProductCatalogItem",
    "catalog_model_keys",
    "dedupe_legacy_models",
    "group_legacy_configs",
    "is_product_visible",
    "is_product_visible_external_provider",
    "is_product_visible_model",
    "is_product_visible_provider",
    "legacy_model_capability_group",
    "select_legacy_external_providers",
    "select_primary_legacy_config",
]
