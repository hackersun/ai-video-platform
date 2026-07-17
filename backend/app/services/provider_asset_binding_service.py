"""Create, verify and resolve provider bindings without provider network coupling."""

from __future__ import annotations

import inspect
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.models.provider_asset_binding import ProviderAssetBinding


class ProviderBindingError(RuntimeError):
    """Base error for provider asset binding resolution."""


class ProviderBindingNotFoundError(ProviderBindingError):
    """No active provider binding or direct fallback is available."""


class ProviderBindingNotVerifiedError(ProviderBindingError):
    """The provider binding exists but is not ready for production use."""


class ProviderBindingChecksumMismatchError(ProviderBindingError):
    """The binding was created from a different canonical asset payload."""


class ProviderBindingModelIncompatibleError(ProviderBindingError):
    """Only a binding for a different provider model is available."""


class ProviderBindingUploadError(ProviderBindingError):
    """The provider rejected or failed to ingest the asset."""


def _storage_time(value: Optional[datetime]) -> Optional[datetime]:
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _is_expired(value: Optional[datetime]) -> bool:
    expires_at = _storage_time(value)
    return bool(expires_at and expires_at <= utc_now())


def _has_usable_reference(binding: ProviderAssetBinding) -> bool:
    return bool(
        (binding.provider_asset_id and binding.provider_asset_id.strip())
        or (binding.public_url and binding.public_url.strip())
    )


async def upsert_provider_binding(
    db: AsyncSession,
    *,
    asset_id: str,
    asset_version: int,
    provider_id: str,
    model_id: str,
    binding_kind: str,
    provider_asset_id: Optional[str] = None,
    public_url: Optional[str] = None,
    checksum: Optional[str] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    duration_seconds: Optional[float] = None,
    upload_status: str = "pending",
    upload_error: Optional[str] = None,
    public_url_expires_at: Optional[datetime] = None,
) -> ProviderAssetBinding:
    """Create or update the sole active binding for the complete provider key."""

    result = await db.execute(
        select(ProviderAssetBinding)
        .where(
            ProviderAssetBinding.asset_id == asset_id,
            ProviderAssetBinding.asset_version == asset_version,
            ProviderAssetBinding.provider_id == provider_id,
            ProviderAssetBinding.model_id == model_id,
            ProviderAssetBinding.binding_kind == binding_kind,
            ProviderAssetBinding.is_active.is_(True),
        )
        .order_by(ProviderAssetBinding.created_at.desc())
        .limit(1)
    )
    binding = result.scalar_one_or_none()
    if binding is None:
        binding = ProviderAssetBinding(
            id=str(uuid.uuid4()),
            asset_id=asset_id,
            asset_version=asset_version,
            provider_id=provider_id,
            model_id=model_id,
            binding_kind=binding_kind,
        )
        db.add(binding)
    elif (
        binding.provider_asset_id != provider_asset_id
        or binding.public_url != public_url
        or binding.checksum != checksum
        or binding.upload_status != upload_status
    ):
        binding.verified_at = None

    binding.provider_asset_id = provider_asset_id
    binding.public_url = public_url
    binding.checksum = checksum
    binding.width = width
    binding.height = height
    binding.duration_seconds = duration_seconds
    binding.upload_status = upload_status
    binding.upload_error = upload_error
    binding.public_url_expires_at = _storage_time(public_url_expires_at)
    binding.updated_at = utc_now()
    await db.flush()
    return binding


async def invalidate_provider_binding(
    db: AsyncSession,
    binding_id: str,
    *,
    reason: str,
) -> ProviderAssetBinding:
    """Deactivate a binding while retaining its audit history."""

    binding = await db.get(ProviderAssetBinding, binding_id)
    if binding is None:
        raise ProviderBindingNotFoundError(f"provider binding {binding_id} was not found")
    binding.is_active = False
    binding.invalidated_at = utc_now()
    binding.invalidation_reason = reason
    binding.updated_at = utc_now()
    await db.flush()
    return binding


async def verify_provider_binding(
    db: AsyncSession,
    binding_id: str,
    *,
    expected_checksum: Optional[str] = None,
) -> ProviderAssetBinding:
    """Mark an uploaded binding verified after checking its canonical checksum."""

    binding = await db.get(ProviderAssetBinding, binding_id)
    if binding is None or not binding.is_active:
        raise ProviderBindingNotFoundError(f"active provider binding {binding_id} was not found")
    if binding.upload_status == "failed":
        raise ProviderBindingUploadError(binding.upload_error or "provider asset upload failed")
    if not _has_usable_reference(binding):
        raise ProviderBindingUploadError("provider binding has no usable provider reference")
    if expected_checksum and binding.checksum != expected_checksum:
        await invalidate_provider_binding(db, binding.id, reason="checksum_mismatch")
        raise ProviderBindingChecksumMismatchError(
            f"provider binding checksum {binding.checksum!r} does not match {expected_checksum!r}"
        )
    binding.upload_status = "ready"
    binding.upload_error = None
    binding.verified_at = utc_now()
    binding.updated_at = utc_now()
    await db.flush()
    return binding


async def refresh_expired_public_url(
    db: AsyncSession,
    binding: ProviderAssetBinding,
    refresh_public_url: Callable[[ProviderAssetBinding], Any],
) -> ProviderAssetBinding:
    """Refresh an expired provider URL through an injected, network-free callback boundary."""

    refreshed = refresh_public_url(binding)
    if inspect.isawaitable(refreshed):
        refreshed = await refreshed
    if isinstance(refreshed, str):
        public_url = refreshed
        expires_at = None
    elif isinstance(refreshed, Mapping):
        public_url = refreshed.get("public_url") or refreshed.get("url")
        expires_at = refreshed.get("public_url_expires_at") or refreshed.get("expires_at")
    else:
        public_url = None
        expires_at = None
    public_url_text = str(public_url).strip() if public_url is not None else ""
    if not public_url_text:
        raise ProviderBindingUploadError("provider public URL refresh returned no URL")
    binding.public_url = public_url_text
    binding.public_url_expires_at = _storage_time(expires_at)
    binding.updated_at = utc_now()
    await db.flush()
    return binding


async def resolve_provider_binding(
    db: AsyncSession,
    *,
    asset_id: str,
    asset_version: int,
    provider_id: str,
    model_id: str,
    binding_kind: str,
    asset_checksum: Optional[str] = None,
    direct_public_url: Optional[str] = None,
    refresh_public_url: Optional[Callable[[ProviderAssetBinding], Any]] = None,
) -> ProviderAssetBinding:
    """Resolve a verified exact-model binding, refreshing or creating a safe fallback."""

    result = await db.execute(
        select(ProviderAssetBinding)
        .where(
            ProviderAssetBinding.asset_id == asset_id,
            ProviderAssetBinding.asset_version == asset_version,
            ProviderAssetBinding.provider_id == provider_id,
            ProviderAssetBinding.model_id == model_id,
            ProviderAssetBinding.binding_kind == binding_kind,
            ProviderAssetBinding.is_active.is_(True),
        )
        .order_by(ProviderAssetBinding.created_at.desc())
        .limit(1)
    )
    binding = result.scalar_one_or_none()

    if binding is None and direct_public_url is not None:
        direct_public_url = direct_public_url.strip()
        if not direct_public_url:
            raise ProviderBindingUploadError("direct fallback has no usable public URL")
        binding = await upsert_provider_binding(
            db,
            asset_id=asset_id,
            asset_version=asset_version,
            provider_id=provider_id,
            model_id=model_id,
            binding_kind=binding_kind,
            public_url=direct_public_url,
            checksum=asset_checksum,
            upload_status="ready",
        )
        binding.verified_at = utc_now()
        await db.flush()
        return binding

    if binding is None:
        other_model = await db.scalar(
            select(ProviderAssetBinding.id)
            .where(
                ProviderAssetBinding.asset_id == asset_id,
                ProviderAssetBinding.asset_version == asset_version,
                ProviderAssetBinding.provider_id == provider_id,
                ProviderAssetBinding.binding_kind == binding_kind,
                ProviderAssetBinding.model_id != model_id,
                ProviderAssetBinding.is_active.is_(True),
            )
            .limit(1)
        )
        if other_model:
            raise ProviderBindingModelIncompatibleError(
                f"no {model_id!r} binding exists for provider {provider_id!r}"
            )
        raise ProviderBindingNotFoundError(
            f"no active provider binding exists for asset {asset_id!r} version {asset_version}"
        )

    if binding.upload_status == "failed":
        raise ProviderBindingUploadError(binding.upload_error or "provider asset upload failed")
    if not _has_usable_reference(binding):
        raise ProviderBindingUploadError("provider binding has no usable provider reference")
    if asset_checksum and binding.checksum != asset_checksum:
        await invalidate_provider_binding(db, binding.id, reason="checksum_mismatch")
        raise ProviderBindingChecksumMismatchError(
            f"provider binding checksum {binding.checksum!r} does not match {asset_checksum!r}"
        )
    if binding.verified_at is None or binding.upload_status != "ready":
        raise ProviderBindingNotVerifiedError(
            f"provider binding {binding.id} has not been verified"
        )
    if binding.public_url and _is_expired(binding.public_url_expires_at):
        if refresh_public_url is None:
            raise ProviderBindingUploadError("provider public URL expired and cannot be refreshed")
        await refresh_expired_public_url(db, binding, refresh_public_url)
    return binding


async def inspect_provider_binding_readiness(
    db: AsyncSession,
    *,
    assets: list[Any],
    provider_id: str,
    model_id: str,
    binding_kind: str = "reference_image",
) -> dict[str, Any]:
    """Inspect exact-version bindings without creating fallbacks or touching providers."""

    missing: list[str] = []
    not_ready: list[str] = []
    snapshots: list[dict[str, Any]] = []
    for asset in assets:
        binding = await db.scalar(
            select(ProviderAssetBinding)
            .where(
                ProviderAssetBinding.asset_id == asset.id,
                ProviderAssetBinding.asset_version == int(asset.version or 1),
                ProviderAssetBinding.provider_id == provider_id,
                ProviderAssetBinding.model_id == model_id,
                ProviderAssetBinding.binding_kind == binding_kind,
                ProviderAssetBinding.is_active.is_(True),
            )
            .order_by(ProviderAssetBinding.created_at.desc())
            .limit(1)
        )
        if binding is None:
            missing.append(asset.id)
            continue
        ready = (
            binding.upload_status == "ready"
            and binding.verified_at is not None
            and _has_usable_reference(binding)
            and not (binding.public_url and _is_expired(binding.public_url_expires_at))
        )
        if not ready:
            not_ready.append(asset.id)
            continue
        snapshots.append({
            "asset_id": asset.id,
            "asset_version": int(asset.version or 1),
            "binding_id": binding.id,
            "provider_id": binding.provider_id,
            "model_id": binding.model_id,
            "provider_usable": True,
            "reference_kind": "public_url" if binding.public_url else "provider_asset_id",
            "binding_version": binding.updated_at.isoformat() if binding.updated_at else None,
        })
    return {"ready": not missing and not not_ready, "missing": missing, "not_ready": not_ready, "bindings": snapshots}


__all__ = [
    "ProviderBindingChecksumMismatchError",
    "ProviderBindingError",
    "ProviderBindingModelIncompatibleError",
    "ProviderBindingNotFoundError",
    "ProviderBindingNotVerifiedError",
    "ProviderBindingUploadError",
    "invalidate_provider_binding",
    "inspect_provider_binding_readiness",
    "refresh_expired_public_url",
    "resolve_provider_binding",
    "upsert_provider_binding",
    "verify_provider_binding",
]
