"""Persisted, versioned model-center configuration records."""

from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, Numeric, String, Text, UniqueConstraint

from app.core.database import Base
from app.core.time_utils import utc_now


class ModelProvider(Base):
    __tablename__ = "model_providers"

    id = Column(String(36), primary_key=True)
    code = Column(String(80), nullable=False, unique=True, index=True)
    display_name = Column(String(120), nullable=False)
    provider_family = Column(String(80), nullable=False, index=True)
    is_builtin = Column(Boolean, nullable=False, default=False)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)


class ModelProfile(Base):
    __tablename__ = "model_profiles"
    __table_args__ = (UniqueConstraint("provider_id", "profile_key", name="uq_model_profile_key"),)

    id = Column(String(36), primary_key=True)
    provider_id = Column(String(36), nullable=False, index=True)
    profile_key = Column(String(120), nullable=False)
    display_name = Column(String(160), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)


class ModelConnection(Base):
    __tablename__ = "model_connections"
    __table_args__ = (UniqueConstraint("user_id", "provider_id", "name", name="uq_model_connection_name"),)

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    provider_id = Column(String(36), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    api_key = Column(Text)
    api_secret = Column(Text)
    endpoint_overrides = Column(JSON, nullable=False, default=dict)
    connection_params = Column(JSON, nullable=False, default=dict)
    status = Column(String(30), nullable=False, default="draft", index=True)
    tested_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)


class ModelProfileVersion(Base):
    __tablename__ = "model_profile_versions"
    __table_args__ = (UniqueConstraint("model_id", "version", name="uq_model_profile_version"),)

    id = Column(String(36), primary_key=True)
    model_id = Column(String(36), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    api_model_id = Column(String(200), nullable=False, index=True)
    driver_key = Column(String(80), nullable=False, index=True)
    capabilities = Column(JSON, nullable=False, default=list)
    input_contract = Column(JSON, nullable=False, default=dict)
    output_contract = Column(JSON, nullable=False, default=dict)
    parameter_schema = Column(JSON, nullable=False, default=dict)
    default_params = Column(JSON, nullable=False, default=dict)
    limits = Column(JSON, nullable=False, default=dict)
    pricing = Column(JSON, nullable=False, default=dict)
    prompt_profile_key = Column(String(120))
    contract_version = Column(String(100), nullable=False)
    status = Column(String(30), nullable=False, default="draft", index=True)
    checksum = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)


class ModelBinding(Base):
    __tablename__ = "model_bindings"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "scope_type", "scope_id", "task", "capability", "version",
            name="uq_model_binding_version",
        ),
    )

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    scope_type = Column(String(20), nullable=False, index=True)
    scope_id = Column(String(36), nullable=False, default="", index=True)
    task = Column(String(100), nullable=False, index=True)
    capability = Column(String(40), nullable=False, index=True)
    profile_version_id = Column(String(36), nullable=False, index=True)
    connection_id = Column(String(36), nullable=False, index=True)
    priority = Column(Integer, nullable=False, default=100)
    route_policy = Column(String(30), nullable=False, default="single")
    fallback_profile_version_ids = Column(JSON, nullable=False, default=list)
    version = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)


class ProductionRecipeVersion(Base):
    __tablename__ = "production_recipe_versions"
    __table_args__ = (
        UniqueConstraint("user_id", "recipe_key", "version", name="uq_production_recipe_version"),
    )

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    recipe_key = Column(String(100), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    version = Column(Integer, nullable=False)
    status = Column(String(30), nullable=False, default="draft", index=True)
    spec = Column(JSON, nullable=False)
    checksum = Column(String(64), nullable=False, index=True)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    published_at = Column(DateTime)


class ModelCertificationRun(Base):
    __tablename__ = "model_certification_runs"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    profile_version_id = Column(String(36), nullable=False, index=True)
    connection_id = Column(String(36), nullable=False, index=True)
    level = Column(String(20), nullable=False, index=True)
    status = Column(String(30), nullable=False, index=True)
    request_fingerprint = Column(String(64), nullable=False, index=True)
    sanitized_evidence = Column(JSON, nullable=False, default=dict)
    estimated_cost_rmb = Column(Numeric(10, 4), nullable=False, default=0)
    actual_cost_rmb = Column(Numeric(10, 4), nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    completed_at = Column(DateTime)


class ModelExecutionSnapshot(Base):
    __tablename__ = "model_execution_snapshots"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    run_id = Column(String(36), index=True)
    job_id = Column(String(36), index=True)
    task = Column(String(100), nullable=False, index=True)
    capability = Column(String(40), nullable=False, index=True)
    profile_version_id = Column(String(36), nullable=False, index=True)
    connection_id = Column(String(36), nullable=False, index=True)
    binding_id = Column(String(36), nullable=False, index=True)
    binding_version = Column(Integer, nullable=False)
    recipe_version_id = Column(String(36), index=True)
    prompt_profile_version_id = Column(String(36), index=True)
    model_contract_version = Column(String(100), nullable=False)
    sanitized_params = Column(JSON, nullable=False, default=dict)
    checksum = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)


class ModelConfigAuditEvent(Base):
    __tablename__ = "model_config_audit_events"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    resource_type = Column(String(40), nullable=False, index=True)
    resource_id = Column(String(36), nullable=False, index=True)
    action = Column(String(40), nullable=False, index=True)
    from_version_id = Column(String(36))
    to_version_id = Column(String(36))
    reason = Column(String(200), nullable=False)
    sanitized_change_summary = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=utc_now, index=True)
