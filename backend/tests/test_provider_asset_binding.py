from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.models.provider_asset_binding import ProviderAssetBinding
from app.services.provider_asset_binding_service import (
    ProviderBindingChecksumMismatchError,
    ProviderBindingModelIncompatibleError,
    ProviderBindingNotVerifiedError,
    ProviderBindingUploadError,
    invalidate_provider_binding,
    resolve_provider_binding,
    upsert_provider_binding,
    verify_provider_binding,
)


def _run(coro):
    return asyncio.run(coro)


async def _session() -> tuple[AsyncSession, object]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(ProviderAssetBinding.__table__.create)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return factory(), engine


async def _ready_binding(
    db: AsyncSession,
    *,
    asset_id: str = "asset-1",
    asset_version: int = 3,
    provider_id: str = "volcengine",
    model_id: str = "seedance-2",
    binding_kind: str = "reference_image",
    public_url: str = "https://cdn.example.com/asset-1.png",
    checksum: str = "sha256:current",
    expires_at: datetime | None = None,
) -> ProviderAssetBinding:
    binding = await upsert_provider_binding(
        db,
        asset_id=asset_id,
        asset_version=asset_version,
        provider_id=provider_id,
        model_id=model_id,
        binding_kind=binding_kind,
        provider_asset_id="provider-asset-1",
        public_url=public_url,
        checksum=checksum,
        width=1024,
        height=1024,
        duration_seconds=None,
        upload_status="uploaded",
        public_url_expires_at=expires_at,
    )
    return await verify_provider_binding(
        db,
        binding.id,
        expected_checksum=checksum,
    )


def test_upsert_reuses_the_single_active_binding_for_the_full_key() -> None:
    async def scenario() -> tuple[str, int, str]:
        db, engine = await _session()
        try:
            first = await upsert_provider_binding(
                db,
                asset_id="asset-1",
                asset_version=2,
                provider_id="volcengine",
                model_id="seedance-2",
                binding_kind="reference_image",
                provider_asset_id="provider-old",
                upload_status="uploaded",
            )
            second = await upsert_provider_binding(
                db,
                asset_id="asset-1",
                asset_version=2,
                provider_id="volcengine",
                model_id="seedance-2",
                binding_kind="reference_image",
                provider_asset_id="provider-new",
                upload_status="uploaded",
            )
            count = await db.scalar(
                select(func.count(ProviderAssetBinding.id)).where(
                    ProviderAssetBinding.is_active.is_(True)
                )
            )
            return first.id, int(count or 0), second.provider_asset_id
        finally:
            await db.close()
            await engine.dispose()

    binding_id, active_count, provider_asset_id = _run(scenario())

    assert active_count == 1
    assert provider_asset_id == "provider-new"
    assert binding_id


@pytest.mark.parametrize(
    ("changed_field", "changed_value"),
    [
        ("provider_asset_id", "provider-asset-replaced"),
        ("public_url", "https://cdn.example.com/asset-1-replaced.png"),
        ("checksum", "sha256:replaced"),
        ("upload_status", "uploaded"),
    ],
)
def test_upsert_changed_verified_payload_requires_verification_again(
    changed_field: str,
    changed_value: str,
) -> None:
    async def scenario() -> tuple[str, datetime | None]:
        db, engine = await _session()
        try:
            verified = await _ready_binding(db)
            replacement = {
                "provider_asset_id": "provider-asset-1",
                "public_url": "https://cdn.example.com/asset-1.png",
                "checksum": "sha256:current",
                "upload_status": "ready",
            }
            replacement[changed_field] = changed_value
            updated = await upsert_provider_binding(
                db,
                asset_id="asset-1",
                asset_version=3,
                provider_id="volcengine",
                model_id="seedance-2",
                binding_kind="reference_image",
                **replacement,
            )

            assert updated.id == verified.id
            with pytest.raises(ProviderBindingNotVerifiedError):
                await resolve_provider_binding(
                    db,
                    asset_id="asset-1",
                    asset_version=3,
                    provider_id="volcengine",
                    model_id="seedance-2",
                    binding_kind="reference_image",
                    asset_checksum=replacement["checksum"],
                )
            return updated.id, updated.verified_at
        finally:
            await db.close()
            await engine.dispose()

    binding_id, verified_at = _run(scenario())

    assert binding_id
    assert verified_at is None


def test_model_rejects_two_active_bindings_for_the_full_key() -> None:
    async def scenario() -> None:
        db, engine = await _session()
        try:
            common = {
                "asset_id": "asset-unique",
                "asset_version": 1,
                "provider_id": "volcengine",
                "model_id": "seedance-2",
                "binding_kind": "reference_image",
                "upload_status": "uploaded",
                "is_active": True,
            }
            db.add(ProviderAssetBinding(id="binding-1", **common))
            await db.flush()
            db.add(ProviderAssetBinding(id="binding-2", **common))

            with pytest.raises(IntegrityError):
                await db.flush()
        finally:
            await db.rollback()
            await db.close()
            await engine.dispose()

    _run(scenario())


def test_verify_rejects_binding_without_a_usable_provider_reference() -> None:
    async def scenario() -> None:
        db, engine = await _session()
        try:
            binding = await upsert_provider_binding(
                db,
                asset_id="asset-empty",
                asset_version=1,
                provider_id="volcengine",
                model_id="seedance-2",
                binding_kind="reference_image",
                provider_asset_id=" \t ",
                public_url="\n ",
                checksum="sha256:empty",
                upload_status="uploaded",
            )

            with pytest.raises(ProviderBindingUploadError, match="no usable provider reference"):
                await verify_provider_binding(
                    db,
                    binding.id,
                    expected_checksum="sha256:empty",
                )
        finally:
            await db.close()
            await engine.dispose()

    _run(scenario())


def test_resolver_rejects_legacy_verified_binding_without_a_usable_reference() -> None:
    async def scenario() -> None:
        db, engine = await _session()
        try:
            binding = await upsert_provider_binding(
                db,
                asset_id="asset-legacy-empty",
                asset_version=1,
                provider_id="volcengine",
                model_id="seedance-2",
                binding_kind="reference_image",
                checksum="sha256:legacy-empty",
                upload_status="ready",
            )
            binding.verified_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await db.flush()

            with pytest.raises(ProviderBindingUploadError, match="no usable provider reference"):
                await resolve_provider_binding(
                    db,
                    asset_id="asset-legacy-empty",
                    asset_version=1,
                    provider_id="volcengine",
                    model_id="seedance-2",
                    binding_kind="reference_image",
                    asset_checksum="sha256:legacy-empty",
                )
        finally:
            await db.close()
            await engine.dispose()

    _run(scenario())


def test_resolver_reuses_a_verified_cached_binding_without_refresh() -> None:
    async def scenario() -> tuple[str, int]:
        db, engine = await _session()
        refresh_calls = 0

        async def refresh(_binding: ProviderAssetBinding):
            nonlocal refresh_calls
            refresh_calls += 1
            return {"public_url": "https://cdn.example.com/refreshed.png"}

        try:
            binding = await _ready_binding(
                db,
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
            )
            resolved = await resolve_provider_binding(
                db,
                asset_id="asset-1",
                asset_version=3,
                provider_id="volcengine",
                model_id="seedance-2",
                binding_kind="reference_image",
                asset_checksum="sha256:current",
                refresh_public_url=refresh,
            )
            assert resolved is binding
            return resolved.public_url or "", refresh_calls
        finally:
            await db.close()
            await engine.dispose()

    public_url, refresh_calls = _run(scenario())

    assert public_url == "https://cdn.example.com/asset-1.png"
    assert refresh_calls == 0


def test_resolver_refreshes_an_expired_public_url_with_injected_callback() -> None:
    async def scenario() -> tuple[str, datetime | None, int]:
        db, engine = await _session()
        refresh_calls = 0
        refreshed_expiry = datetime.now(timezone.utc) + timedelta(hours=1)

        async def refresh(binding: ProviderAssetBinding):
            nonlocal refresh_calls
            refresh_calls += 1
            assert binding.provider_asset_id == "provider-asset-1"
            return {
                "public_url": "https://cdn.example.com/refreshed.png",
                "public_url_expires_at": refreshed_expiry,
            }

        try:
            await _ready_binding(
                db,
                expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
            )
            resolved = await resolve_provider_binding(
                db,
                asset_id="asset-1",
                asset_version=3,
                provider_id="volcengine",
                model_id="seedance-2",
                binding_kind="reference_image",
                refresh_public_url=refresh,
            )
            return resolved.public_url or "", resolved.public_url_expires_at, refresh_calls
        finally:
            await db.close()
            await engine.dispose()

    public_url, expires_at, refresh_calls = _run(scenario())

    assert public_url == "https://cdn.example.com/refreshed.png"
    assert expires_at is not None
    assert refresh_calls == 1


def test_resolver_rejects_whitespace_only_refreshed_public_url() -> None:
    async def scenario() -> None:
        db, engine = await _session()

        async def refresh(_binding: ProviderAssetBinding):
            return {"public_url": " \n\t "}

        try:
            await _ready_binding(
                db,
                expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
            )
            with pytest.raises(ProviderBindingUploadError, match="returned no URL"):
                await resolve_provider_binding(
                    db,
                    asset_id="asset-1",
                    asset_version=3,
                    provider_id="volcengine",
                    model_id="seedance-2",
                    binding_kind="reference_image",
                    refresh_public_url=refresh,
                )
        finally:
            await db.close()
            await engine.dispose()

    _run(scenario())


def test_checksum_mismatch_invalidates_the_binding() -> None:
    async def scenario() -> tuple[bool, str | None]:
        db, engine = await _session()
        try:
            binding = await _ready_binding(db)
            with pytest.raises(ProviderBindingChecksumMismatchError):
                await resolve_provider_binding(
                    db,
                    asset_id="asset-1",
                    asset_version=3,
                    provider_id="volcengine",
                    model_id="seedance-2",
                    binding_kind="reference_image",
                    asset_checksum="sha256:changed",
                )
            await db.refresh(binding)
            return binding.is_active, binding.invalidation_reason
        finally:
            await db.close()
            await engine.dispose()

    is_active, reason = _run(scenario())

    assert is_active is False
    assert reason == "checksum_mismatch"


def test_resolver_rejects_a_binding_created_for_an_incompatible_model() -> None:
    async def scenario() -> None:
        db, engine = await _session()
        try:
            await _ready_binding(db, model_id="seedance-1.5")
            with pytest.raises(ProviderBindingModelIncompatibleError):
                await resolve_provider_binding(
                    db,
                    asset_id="asset-1",
                    asset_version=3,
                    provider_id="volcengine",
                    model_id="seedance-2",
                    binding_kind="reference_image",
                )
        finally:
            await db.close()
            await engine.dispose()

    _run(scenario())


def test_resolver_surfaces_provider_upload_failure() -> None:
    async def scenario() -> None:
        db, engine = await _session()
        try:
            await upsert_provider_binding(
                db,
                asset_id="asset-1",
                asset_version=3,
                provider_id="volcengine",
                model_id="seedance-2",
                binding_kind="reference_image",
                upload_status="failed",
                upload_error="provider rejected image",
            )
            with pytest.raises(ProviderBindingUploadError, match="provider rejected image"):
                await resolve_provider_binding(
                    db,
                    asset_id="asset-1",
                    asset_version=3,
                    provider_id="volcengine",
                    model_id="seedance-2",
                    binding_kind="reference_image",
                )
        finally:
            await db.close()
            await engine.dispose()

    _run(scenario())


def test_resolver_creates_a_verified_direct_public_url_fallback() -> None:
    async def scenario() -> ProviderAssetBinding:
        db, engine = await _session()
        try:
            resolved = await resolve_provider_binding(
                db,
                asset_id="asset-2",
                asset_version=1,
                provider_id="volcengine",
                model_id="seedance-2",
                binding_kind="reference_image",
                asset_checksum="sha256:direct",
                direct_public_url="https://public.example.com/asset-2.png",
            )
            await db.refresh(resolved)
            db.expunge(resolved)
            return resolved
        finally:
            await db.close()
            await engine.dispose()

    binding = _run(scenario())

    assert binding.public_url == "https://public.example.com/asset-2.png"
    assert binding.provider_asset_id is None
    assert binding.upload_status == "ready"
    assert binding.verified_at is not None
    assert binding.checksum == "sha256:direct"


def test_resolver_rejects_whitespace_only_direct_public_url_fallback() -> None:
    async def scenario() -> None:
        db, engine = await _session()
        try:
            with pytest.raises(ProviderBindingUploadError, match="no usable public URL"):
                await resolve_provider_binding(
                    db,
                    asset_id="asset-whitespace-direct",
                    asset_version=1,
                    provider_id="volcengine",
                    model_id="seedance-2",
                    binding_kind="reference_image",
                    asset_checksum="sha256:direct",
                    direct_public_url=" \n\t ",
                )
        finally:
            await db.close()
            await engine.dispose()

    _run(scenario())


def test_invalidate_then_upsert_creates_a_new_active_binding() -> None:
    async def scenario() -> tuple[str, str, int]:
        db, engine = await _session()
        try:
            first = await _ready_binding(db)
            await invalidate_provider_binding(db, first.id, reason="asset_replaced")
            second = await upsert_provider_binding(
                db,
                asset_id="asset-1",
                asset_version=3,
                provider_id="volcengine",
                model_id="seedance-2",
                binding_kind="reference_image",
                provider_asset_id="provider-asset-2",
                upload_status="uploaded",
            )
            active_count = await db.scalar(
                select(func.count(ProviderAssetBinding.id)).where(
                    ProviderAssetBinding.is_active.is_(True)
                )
            )
            return first.id, second.id, int(active_count or 0)
        finally:
            await db.close()
            await engine.dispose()

    first_id, second_id, active_count = _run(scenario())

    assert first_id != second_id
    assert active_count == 1
