"""Public facade for provider-neutral model configuration contracts."""

from app.features.model_config.domain import (
    BindingScope,
    CertificationLevel,
    ModelCapability,
    ModelProfileContract,
    ProfileStatus,
    ResolvedModelBinding,
    normalize_capabilities,
)
from app.features.model_config.catalog import (
    is_product_visible_external_provider,
    is_product_visible_model,
    is_product_visible_provider,
    legacy_model_capability_group,
    select_legacy_external_providers,
)
from app.features.model_config.legacy_projection import (
    CatalogComparison,
    build_legacy_external_provider_response,
    compare_legacy_and_canonical_catalogs,
    maybe_log_shadow_catalog_comparison,
    project_legacy_external_providers,
    project_legacy_llm_models,
)
from app.features.model_config.repository import (
    ModelConfigurationError,
    list_product_catalog,
    resolve_profile_version,
)

__all__ = [
    "BindingScope",
    "CatalogComparison",
    "CertificationLevel",
    "ModelConfigurationError",
    "ModelCapability",
    "ModelProfileContract",
    "ProfileStatus",
    "ResolvedModelBinding",
    "build_legacy_external_provider_response",
    "compare_legacy_and_canonical_catalogs",
    "is_product_visible_external_provider",
    "is_product_visible_model",
    "is_product_visible_provider",
    "legacy_model_capability_group",
    "list_product_catalog",
    "maybe_log_shadow_catalog_comparison",
    "normalize_capabilities",
    "project_legacy_external_providers",
    "project_legacy_llm_models",
    "resolve_profile_version",
    "select_legacy_external_providers",
]
