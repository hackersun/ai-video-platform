"""Persisted, versioned model-center configuration records."""

from copy import deepcopy
from typing import Any
from uuid import uuid4

from cryptography.fernet import InvalidToken
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    event,
    inspect,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Session, validates

from app.core.database import Base
from app.core.time_utils import utc_now
from app.models.llm_config import _get_fernet, decrypt_key, encrypt_key


_VERSION_TABLE_NAMES = frozenset({"model_profile_versions", "production_recipe_versions"})


def _next_version_values(
    source,
    *,
    copy_fields: tuple[str, ...],
    mutable_fields: frozenset[str],
    checksum: str,
    changes: dict[str, Any],
) -> dict[str, Any]:
    if source.status != "published":
        raise ValueError("only a published version can create its next version")
    if not checksum or checksum == source.checksum:
        raise ValueError("next version requires a fresh checksum")
    unsupported = set(changes) - mutable_fields
    if unsupported:
        raise ValueError(f"unsupported next-version changes: {', '.join(sorted(unsupported))}")
    values = {field: deepcopy(getattr(source, field)) for field in copy_fields}
    values.update(deepcopy(changes))
    values.update(id=str(uuid4()), version=source.version + 1, status="draft", checksum=checksum)
    return values


def _persisted_status(target) -> str:
    state = inspect(target)
    status_history = state.attrs.status.history
    return status_history.deleted[0] if status_history.deleted else target.status


def _reject_published_update(_mapper, _connection, target) -> None:
    state = inspect(target)
    changed = any(state.attrs[column.key].history.has_changes() for column in state.mapper.column_attrs)
    if _persisted_status(target) == "published" and changed:
        raise ValueError("published version is append-only; create the next version instead")


def _reject_published_delete(_mapper, _connection, target) -> None:
    if _persisted_status(target) == "published":
        raise ValueError("published version is append-only; deletion is not allowed")


def _reject_bulk_version_dml(orm_execute_state) -> None:
    if not (orm_execute_state.is_update or orm_execute_state.is_delete):
        return
    table = getattr(orm_execute_state.statement, "table", None)
    if getattr(table, "name", None) in _VERSION_TABLE_NAMES:
        raise ValueError("bulk UPDATE/DELETE is disabled for version tables")


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
    api_key = Column(Text)  # Fernet ciphertext only; write through set_api_key_encrypted().
    api_secret = Column(Text)  # Fernet ciphertext only; write through set_api_secret_encrypted().
    endpoint_overrides = Column(JSON, nullable=False, default=dict)
    connection_params = Column(JSON, nullable=False, default=dict)
    status = Column(String(30), nullable=False, default="draft", index=True)
    tested_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    def get_api_key_decrypted(self) -> str:
        return decrypt_key(self.api_key or "")

    def set_api_key_encrypted(self, plain_key: str) -> None:
        self.api_key = encrypt_key(plain_key) if plain_key else ""

    def get_api_secret_decrypted(self) -> str:
        return decrypt_key(self.api_secret or "")

    def set_api_secret_encrypted(self, plain_secret: str | None) -> None:
        self.api_secret = encrypt_key(plain_secret) if plain_secret else None

    @validates("api_key", "api_secret")
    def _validate_fernet_ciphertext(self, field_name: str, value: str | None) -> str | None:
        if value in {None, ""}:
            return value
        try:
            _get_fernet().decrypt(value.encode())
        except (AttributeError, InvalidToken, TypeError, ValueError) as error:
            raise ValueError(f"{field_name} must be Fernet ciphertext") from error
        return value


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

    def create_next_version(self, *, checksum: str, **changes: Any) -> "ModelProfileVersion":
        copy_fields = (
            "model_id", "api_model_id", "driver_key", "capabilities", "input_contract",
            "output_contract", "parameter_schema", "default_params", "limits", "pricing",
            "prompt_profile_key", "contract_version",
        )
        mutable_fields = frozenset(copy_fields) - {"model_id"}
        return ModelProfileVersion(
            **_next_version_values(
                self,
                copy_fields=copy_fields,
                mutable_fields=mutable_fields,
                checksum=checksum,
                changes=changes,
            )
        )


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

    def create_next_version(self, *, checksum: str, **changes: Any) -> "ProductionRecipeVersion":
        copy_fields = ("user_id", "recipe_key", "name", "spec")
        return ProductionRecipeVersion(
            **_next_version_values(
                self,
                copy_fields=copy_fields,
                mutable_fields=frozenset({"name", "spec"}),
                checksum=checksum,
                changes=changes,
            )
        )


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


event.listen(ModelProfileVersion, "before_update", _reject_published_update)
event.listen(ProductionRecipeVersion, "before_update", _reject_published_update)
event.listen(ModelProfileVersion, "before_delete", _reject_published_delete)
event.listen(ProductionRecipeVersion, "before_delete", _reject_published_delete)
event.listen(Session, "do_orm_execute", _reject_bulk_version_dml)
