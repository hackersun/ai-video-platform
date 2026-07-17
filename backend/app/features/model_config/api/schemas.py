"""Stable HTTP contracts for the versioned Model Center API."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

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


class ConnectionItem(BaseModel):
    id: str
    provider_id: str
    name: str
    status: str
    has_secret: bool
    secret_hint: str | None
    secret_updated_at: str | None


class CatalogItem(BaseModel):
    provider_id: str
    api_model_id: str
    profile_version_id: str | None
    legacy_model_id: str | None
    legacy_config_id: str | None
    certification_status: str
    capabilities: list[str]


class ProviderCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    display_name: str = Field(min_length=1, max_length=120)
    provider_family: str = Field(min_length=1, max_length=80)


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
    level: str
