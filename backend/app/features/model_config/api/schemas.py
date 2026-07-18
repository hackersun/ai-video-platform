"""Stable HTTP contracts for the versioned Model Center API."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


T = TypeVar("T")


class PageMeta(BaseModel):
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)


class PageResponse(BaseModel, Generic[T]):
    items: list[T]
    meta: PageMeta


class DriverItem(BaseModel):
    key: str
    capabilities: list[str]
    parameter_schema: dict[str, Any] = Field(default_factory=dict)
    contract_version: str = "driver-v1"


class ProviderItem(BaseModel):
    id: str
    code: str
    display_name: str
    provider_family: str
    is_builtin: bool
    enabled: bool
    revision: int


class ConnectionItem(BaseModel):
    id: str
    provider_id: str
    provider_name: str
    provider_code: str
    name: str
    status: str
    base_url: str | None = None
    enabled: bool = False
    has_secret: bool
    secret_hint: str | None
    secret_updated_at: str | None
    revision: int


class CatalogItem(BaseModel):
    provider_id: str
    provider_name: str
    provider_code: str
    model_name: str
    api_model_id: str
    profile_version_id: str | None
    profile_version: int | None
    driver_key: str | None
    legacy_model_id: str | None
    legacy_config_id: str | None
    certification_status: str
    capabilities: list[str]


class ProviderCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    display_name: str = Field(min_length=1, max_length=120)
    provider_family: str = Field(min_length=1, max_length=80)


class ModelProfileItem(BaseModel):
    id: str
    provider_id: str
    profile_key: str
    display_name: str
    enabled: bool
    revision: int


class ModelProfileCreateRequest(BaseModel):
    provider_id: str
    profile_key: str = Field(min_length=1, max_length=120)
    display_name: str = Field(min_length=1, max_length=160)
    enabled: bool = True


class ModelProfileVersionItem(BaseModel):
    id: str
    model_id: str
    version: int
    api_model_id: str
    driver_key: str
    capabilities: list[str]
    contract_version: str
    status: str
    revision: int


class ModelProfileVersionCreateRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    api_model_id: str = Field(min_length=1, max_length=200)
    driver_key: str = Field(min_length=1, max_length=80)
    capabilities: list[str] = Field(min_length=1)
    input_contract: dict[str, Any] = Field(default_factory=dict)
    output_contract: dict[str, Any] = Field(default_factory=dict)
    parameter_schema: dict[str, Any] = Field(default_factory=dict)
    default_params: dict[str, Any] = Field(default_factory=dict)
    limits: dict[str, Any] = Field(default_factory=dict)
    pricing: dict[str, Any] = Field(default_factory=dict)
    prompt_profile_key: str | None = Field(default=None, max_length=120)
    contract_version: str = Field(min_length=1, max_length=100)


class ContractValidationResponse(BaseModel):
    valid: bool
    errors: list[dict[str, Any]]
    audit_event_id: str


class RevisionedUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    changes: dict[str, Any] = Field(default_factory=dict)


class NonblankReasonRequest(BaseModel):
    reason: str = Field(max_length=200)

    @field_validator("reason")
    @classmethod
    def reason_must_be_nonblank(cls, value: str) -> str:
        trimmed = value.strip()
        if len(trimmed) < 2:
            raise ValueError("reason must contain at least two non-whitespace characters")
        return trimmed


class ConnectionCreateRequest(NonblankReasonRequest):
    provider_id: str
    name: str = Field(min_length=1, max_length=120)
    api_key: str | None = Field(default=None, min_length=1, repr=False)
    api_secret: str | None = Field(default=None, min_length=1, repr=False)


class ConnectionMetadataUpdateRequest(RevisionedUpdateRequest):
    """A metadata-only update does not require a secret replacement reason."""

    @field_validator("changes")
    @classmethod
    def only_safe_connection_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        allowed = {"name", "endpoint_overrides", "connection_params"}
        unsupported = set(value) - allowed
        if unsupported:
            raise ValueError(f"unsupported connection metadata: {', '.join(sorted(unsupported))}")
        if _contains_credential_field(value):
            raise ValueError("connection metadata must not contain credentials")
        return value


def _contains_credential_field(value: Any) -> bool:
    credential_markers = ("apikey", "apisecret", "authorization", "token", "password", "secret", "credential", "header")
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = "".join(character for character in str(key).lower() if character.isalnum())
            if any(marker in normalized for marker in credential_markers) or _contains_credential_field(nested):
                return True
    if isinstance(value, list):
        return any(_contains_credential_field(item) for item in value)
    return False


class ConnectionSecretReplacementRequest(NonblankReasonRequest):
    expected_revision: int = Field(ge=1)
    api_key: str | None = Field(default=None, min_length=1, repr=False)
    api_secret: str | None = Field(default=None, min_length=1, repr=False)

    @model_validator(mode="after")
    def require_secret_replacement(self):
        if not (self.api_key or self.api_secret):
            raise ValueError("api_key or api_secret is required for a secret replacement")
        return self


class CreateResourceRequest(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)


class CreateVersionRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    values: dict[str, Any] = Field(default_factory=dict)


class PublishRequest(NonblankReasonRequest):
    expected_revision: int = Field(ge=1)


class RollbackRequest(PublishRequest):
    target_version_id: str


class RecipeCreateRequest(BaseModel):
    recipe_key: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=120)
    spec: dict[str, Any]


class PromptProfileCreateRequest(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=120)
    task: str = Field(min_length=1, max_length=80)
    stage: str | None = Field(default=None, max_length=80)
    system_contract: str = Field(min_length=1)
    task_template: str = Field(min_length=1)
    input_mapping: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    negative_constraints: list[str] = Field(default_factory=list)
    model_family_overrides: dict[str, Any] = Field(default_factory=dict)
    validation_fixtures: list[dict[str, Any]] = Field(default_factory=list)
    release_notes: str = Field(default="", max_length=2000)


class PromptProfileVersionRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    stage: str | None = Field(default=None, max_length=80)
    system_contract: str | None = None
    task_template: str | None = None
    input_mapping: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    negative_constraints: list[str] | None = None
    model_family_overrides: dict[str, Any] | None = None
    validation_fixtures: list[dict[str, Any]] | None = None
    release_notes: str | None = Field(default=None, max_length=2000)
    values: dict[str, Any] = Field(default_factory=dict)

    def changes(self) -> dict[str, Any]:
        values = dict(self.values)
        for key in (
            "stage", "system_contract", "task_template", "input_mapping", "output_schema",
            "negative_constraints", "model_family_overrides", "validation_fixtures", "release_notes",
        ):
            value = getattr(self, key)
            if value is not None:
                values[key] = value
        return values


class PromptProfileOptimizeRequest(BaseModel):
    version_id: str
    mode: str = Field(default="productionize", max_length=80)
    model_config_id: str | None = None


class PromptProfilePreviewRequest(BaseModel):
    version_id: str
    task_template: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class ResourceImpact(BaseModel):
    affected_bindings: int = 0
    affected_profiles: int = 0
    affected_recipes: int = 0
    affected_prompts: int = 0


class PublishResponse(BaseModel):
    published_version_id: str
    previous_version_id: str | None
    impact: ResourceImpact
    audit_event_id: str


class CertificationRequest(NonblankReasonRequest):
    profile_version_id: str
    connection_id: str
    level: Literal["connection", "contract", "live"]
    user_scope: str | None = Field(default=None, max_length=120)
    recipe_version_id: str | None = None
    chapter_id: str | None = Field(default=None, max_length=120)
    run_id: str | None = Field(default=None, max_length=120)
    selected_shot_ids: list[str] = Field(default_factory=list, max_length=100)
    budget_ceiling_rmb: Decimal | None = Field(default=None, ge=0, decimal_places=4)
    retry_policy: str | None = Field(default=None, max_length=80)
    storage_policy: str | None = Field(default=None, max_length=120)
    real_cost_acknowledged: bool = False

    @model_validator(mode="after")
    def require_live_authorization(self):
        if self.level != "live":
            return self
        required = (
            "user_scope", "recipe_version_id", "chapter_id", "run_id",
            "budget_ceiling_rmb", "retry_policy", "storage_policy",
        )
        missing = [field for field in required if getattr(self, field) in (None, "")]
        if not self.selected_shot_ids:
            missing.append("selected_shot_ids")
        if not self.real_cost_acknowledged:
            missing.append("real_cost_acknowledged")
        if missing:
            raise ValueError(f"live certification requires: {', '.join(missing)}")
        return self


class ConnectionTestIntentResponse(BaseModel):
    id: str
    status: str
    execution_mode: Literal["safe_intent_only"]
    connection: ConnectionItem


class EffectiveBindingProfileItem(BaseModel):
    id: str
    api_model_id: str
    version: int
    driver_key: str
    contract_version: str


class SelectedPromptProfileItem(BaseModel):
    id: str
    key: str
    version: int


class LatestCertificationItem(BaseModel):
    level: str
    status: str


class RecipeStageBindingResolutionItem(BaseModel):
    stage: str
    binding_id: str
    resolution_status: Literal["resolved", "unavailable"]
    error_code: str | None = None
    profile: EffectiveBindingProfileItem | None = None
    prompt_profile: SelectedPromptProfileItem | None
    latest_certification: LatestCertificationItem


class RecipeBindingResolutionResponse(BaseModel):
    recipe_version_id: str
    stages: list[RecipeStageBindingResolutionItem]
