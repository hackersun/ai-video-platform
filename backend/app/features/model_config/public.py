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
from app.features.model_config.legacy_projection import (
    CatalogComparison,
    compare_legacy_and_canonical_catalogs,
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
    "compare_legacy_and_canonical_catalogs",
    "list_product_catalog",
    "normalize_capabilities",
    "project_legacy_external_providers",
    "project_legacy_llm_models",
    "resolve_profile_version",
]
