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
from app.features.model_config.bindings import (
    ModelBindingError,
    RoutePolicy,
    resolve_model_binding,
    resolve_retry_binding,
    route_policy_for,
)
from app.features.model_config.legacy_strategy_projection import (
    resolve_legacy_strategy_config_id,
)
from app.features.model_config.recipes import (
    ProductionRecipeSpec,
    RecipeBindingContract,
    RecipeError,
    RecipeStage,
    RecipeValidationError,
    stable_recipe_checksum,
    validate_recipe,
)
from app.features.model_config.recipe_versions import (
    create_recipe_version,
    publish_recipe_version,
    update_recipe_version,
)

__all__ = [
    "BindingScope",
    "CatalogComparison",
    "CertificationLevel",
    "ModelBindingError",
    "ModelConfigurationError",
    "ModelCapability",
    "ModelProfileContract",
    "ProfileStatus",
    "ProductionRecipeSpec",
    "RecipeBindingContract",
    "RecipeError",
    "RecipeStage",
    "RecipeValidationError",
    "ResolvedModelBinding",
    "RoutePolicy",
    "build_legacy_external_provider_response",
    "compare_legacy_and_canonical_catalogs",
    "create_recipe_version",
    "is_product_visible_external_provider",
    "is_product_visible_model",
    "is_product_visible_provider",
    "legacy_model_capability_group",
    "list_product_catalog",
    "maybe_log_shadow_catalog_comparison",
    "normalize_capabilities",
    "project_legacy_external_providers",
    "project_legacy_llm_models",
    "publish_recipe_version",
    "resolve_profile_version",
    "resolve_model_binding",
    "resolve_legacy_strategy_config_id",
    "resolve_retry_binding",
    "route_policy_for",
    "select_legacy_external_providers",
    "stable_recipe_checksum",
    "update_recipe_version",
    "validate_recipe",
]
