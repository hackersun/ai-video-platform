"""Provider-specific references derived from canonical asset versions."""

from sqlalchemy import Boolean, Column, DateTime, Float, Index, Integer, String, Text, text

from app.core.database import Base
from app.core.time_utils import utc_now


class ProviderAssetBinding(Base):
    """An active provider reference for one immutable canonical asset version."""

    __tablename__ = "provider_asset_bindings"
    __table_args__ = (
        Index(
            "uq_provider_asset_binding_active_key",
            "asset_id",
            "asset_version",
            "provider_id",
            "model_id",
            "binding_kind",
            unique=True,
            sqlite_where=text("is_active = 1"),
            postgresql_where=text("is_active = true"),
        ),
        Index(
            "ix_provider_asset_binding_lookup",
            "asset_id",
            "asset_version",
            "provider_id",
            "model_id",
            "binding_kind",
        ),
    )

    id = Column(String(36), primary_key=True)
    asset_id = Column(String(36), nullable=False, index=True)
    asset_version = Column(Integer, nullable=False)
    provider_id = Column(String(64), nullable=False, index=True)
    model_id = Column(String(128), nullable=False, index=True)
    binding_kind = Column(String(64), nullable=False)

    provider_asset_id = Column(String(255), nullable=True)
    public_url = Column(Text, nullable=True)
    checksum = Column(String(128), nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    duration_seconds = Column(Float, nullable=True)

    upload_status = Column(String(24), nullable=False, default="pending", index=True)
    upload_error = Column(Text, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    public_url_expires_at = Column(DateTime, nullable=True)

    is_active = Column(Boolean, nullable=False, default=True, index=True)
    invalidated_at = Column(DateTime, nullable=True)
    invalidation_reason = Column(String(255), nullable=True)

    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)


__all__ = ["ProviderAssetBinding"]
