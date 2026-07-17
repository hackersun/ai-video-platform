"""Product-facing catalog contracts and visibility rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.features.model_config.domain import ModelCapability


PRODUCT_VISIBILITY = "product"
_INTERNAL_PREFIXES = ("contract-", "preflight-", "test-", "placeholder-")
_LEGACY_PLACEHOLDERS = ("tts-api-model", "video-api-model", "image-api-model")


def is_product_visible(identifier: str, visibility: str | None = None) -> bool:
    """Keep seeded acceptance and placeholder records out of product catalogs."""
    if visibility:
        return visibility == PRODUCT_VISIBILITY
    normalized = identifier.strip().lower()
    return not (
        normalized == "deterministic-acceptance"
        or normalized.startswith(_INTERNAL_PREFIXES)
    )


def is_product_visible_provider(*identifiers: str | None) -> bool:
    values = [str(value or "").strip() for value in identifiers]
    normalized = " ".join(values).lower()
    return bool(values) and all(is_product_visible(value) for value in values if value) and not (
        "预检供应商" in normalized
        or "测试供应商" in normalized
        or "占位供应商" in normalized
        or "tts-provider-" in normalized
        or "external-provider-" in normalized
    )


def is_product_visible_model(*identifiers: str | None) -> bool:
    normalized = " ".join(str(value or "").strip().lower() for value in identifiers)
    return bool(normalized) and is_product_visible(normalized) and not (
        "preflight-" in normalized
        or "contract-" in normalized
        or "placeholder-" in normalized
        or any(value in normalized for value in _LEGACY_PLACEHOLDERS)
        or "-test-" in normalized
        or normalized.endswith("-test")
        or "测试" in normalized
        or "speech-test" in normalized
        or "doubao-seedance-test" in normalized
    )


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
    "is_product_visible",
    "is_product_visible_model",
    "is_product_visible_provider",
]
