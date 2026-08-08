"""Private media registry and append-only delivery/lifecycle evidence."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint

from app.core.database import Base
from app.core.time_utils import utc_now


class MediaObject(Base):
    __tablename__ = "media_objects"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    project_id = Column(String(36), nullable=True, index=True)
    media_kind = Column(String(20), nullable=False, index=True)
    lifecycle_class = Column(String(20), nullable=False, index=True)
    storage_provider = Column(String(30), nullable=False)
    storage_config_id = Column(String(36), nullable=True, index=True)
    object_key = Column(String(700), nullable=False)
    canonical_url = Column(Text, nullable=True)
    delivery_fingerprint = Column(String(64), nullable=True, index=True)
    sha256 = Column(String(64), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    content_type = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False, default="active", index=True)
    retention_until = Column(DateTime, nullable=True, index=True)
    legal_hold = Column(Boolean, nullable=False, default=False)
    media_metadata = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    __table_args__ = (
        UniqueConstraint("storage_provider", "object_key", name="uq_media_object_storage_key"),
    )


class ProviderMediaInput(Base):
    __tablename__ = "provider_media_inputs"

    id = Column(String(36), primary_key=True)
    media_object_id = Column(String(36), ForeignKey("media_objects.id", ondelete="RESTRICT"), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    project_id = Column(String(36), nullable=True, index=True)
    submission_id = Column(String(100), nullable=False, index=True)
    provider_task_id = Column(String(200), nullable=True, index=True)
    purpose = Column(String(100), nullable=False)
    input_order = Column(Integer, nullable=False)
    delivery_method = Column(String(50), nullable=False)
    canonical_url = Column(Text, nullable=False)
    url_fingerprint = Column(String(64), nullable=False)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)

    __table_args__ = (
        UniqueConstraint(
            "media_object_id", "submission_id", "purpose", "input_order",
            name="uq_provider_media_input_slot",
        ),
    )


class MediaDeletionRequest(Base):
    __tablename__ = "media_deletion_requests"

    id = Column(String(36), primary_key=True)
    media_object_id = Column(String(36), ForeignKey("media_objects.id", ondelete="RESTRICT"), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    idempotency_key = Column(String(200), nullable=False)
    reason = Column(String(300), nullable=False)
    status = Column(String(20), nullable=False, default="queued", index=True)
    requested_at = Column(DateTime, nullable=False, default=utc_now)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_media_deletion_idempotency"),
    )


class MediaDeletionReceipt(Base):
    __tablename__ = "media_deletion_receipts"

    id = Column(String(36), primary_key=True)
    media_object_id = Column(String(36), ForeignKey("media_objects.id", ondelete="RESTRICT"), nullable=False, index=True)
    request_id = Column(String(36), nullable=False, unique=True, index=True)
    outcome = Column(String(30), nullable=False)
    object_key_sha256 = Column(String(64), nullable=False)
    detail = Column(String(300), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)
