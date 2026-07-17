from __future__ import annotations

from uuid import uuid4
import inspect

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.asset import Asset
from app.models.provider_asset_binding import ProviderAssetBinding
from app.services.provider_asset_binding_service import upsert_provider_binding, verify_provider_binding
from app.services.reference_package_builder import bind_reference_package
from app.services.video_reference_adapter import (
    build_reference_package_metadata,
    build_video_provider_content,
    requires_provider_bindings,
)


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_provider_conversion_resolves_verified_binding_after_canonical_selection(
    db_session: AsyncSession,
) -> None:
    asset = Asset(
        id=str(uuid4()),
        user_id="binding-integration-user",
        category="character",
        name="米粒正面定稿",
        asset_type="image",
        url="/static/generated/mili-front.png",
        version=3,
        is_locked=True,
        is_final=True,
        is_active=True,
        generation_params={"checksum": "sha256:mili-v3"},
    )
    db_session.add(asset)
    await db_session.flush()
    binding = await upsert_provider_binding(
        db_session,
        asset_id=asset.id,
        asset_version=3,
        provider_id="volcano",
        model_id="seedance-2.0",
        binding_kind="reference_image",
        provider_asset_id="ark-asset-mili-v3",
        public_url="https://provider.example.com/mili-v3.png",
        checksum="sha256:mili-v3",
        upload_status="ready",
    )
    await verify_provider_binding(db_session, binding.id, expected_checksum="sha256:mili-v3")

    canonical_package = {
        "images": [{
            "canonical_asset_id": asset.id,
            "canonical_asset_version": 3,
            "canonical_checksum": "sha256:mili-v3",
            "role_tag": "protagonist",
            "at_index": 1,
        }],
        "videos": [],
        "audios": [],
        "dropped": [],
        "at_reference_text": "@图1为主角米粒正面形象基准",
    }

    provider_package = await bind_reference_package(
        db_session,
        canonical_package,
        provider_id="volcano",
        model_id="seedance-2.0",
    )

    assert provider_package["images"][0]["url"] == "https://provider.example.com/mili-v3.png"
    assert provider_package["images"][0]["provider_binding_id"] == binding.id
    assert provider_package["images"][0]["canonical_asset_id"] == asset.id

    provider_content = build_video_provider_content(
        final_prompt="米粒站在雨夜屋顶。",
        duration=4,
        resolution="720p",
        reference_package=provider_package,
        model_limits={"images": 2, "videos": 0, "audios": 0},
        model_id="seedance-2.0",
        provider="volcano",
    )
    metadata = build_reference_package_metadata(provider_package, provider_content["metadata"])
    assert metadata["canonical_asset_ids"] == [asset.id]
    assert metadata["provider_binding_ids"] == [binding.id]


@pytest.mark.asyncio
async def test_binding_conversion_drops_unverified_binding_without_mutating_canonical_package(
    db_session: AsyncSession,
) -> None:
    asset_id = str(uuid4())
    binding = await upsert_provider_binding(
        db_session,
        asset_id=asset_id,
        asset_version=1,
        provider_id="volcano",
        model_id="seedance-2.0",
        binding_kind="reference_image",
        public_url="https://provider.example.com/unverified.png",
        checksum="sha256:unverified",
        upload_status="pending",
    )
    package = {
        "images": [{
            "canonical_asset_id": asset_id,
            "canonical_asset_version": 1,
            "canonical_checksum": "sha256:unverified",
            "role_tag": "protagonist",
        }],
        "videos": [],
        "audios": [],
        "dropped": [],
    }

    converted = await bind_reference_package(
        db_session,
        package,
        provider_id="volcano",
        model_id="seedance-2.0",
    )

    assert package["images"][0].get("url") is None
    assert converted["images"] == []
    assert converted["dropped"][0]["canonical_asset_id"] == asset_id
    assert converted["dropped"][0]["reason"] == "provider_binding_not_verified"
    assert binding.verified_at is None


@pytest.mark.asyncio
async def test_provider_asset_id_only_never_falls_back_to_canonical_url(
    db_session: AsyncSession,
) -> None:
    asset_id = str(uuid4())
    binding = await upsert_provider_binding(
        db_session,
        asset_id=asset_id,
        asset_version=2,
        provider_id="volcano",
        model_id="seedance-2.0",
        binding_kind="reference_image",
        provider_asset_id="ark-internal-only",
        public_url=None,
        checksum="sha256:internal",
        upload_status="ready",
    )
    await verify_provider_binding(db_session, binding.id, expected_checksum="sha256:internal")
    package = {
        "images": [{
            "url": "https://canonical.example.com/internal.png",
            "canonical_asset_id": asset_id,
            "canonical_asset_version": 2,
            "canonical_checksum": "sha256:internal",
        }],
        "videos": [],
        "audios": [],
        "dropped": [],
    }

    converted = await bind_reference_package(
        db_session,
        package,
        provider_id="volcano",
        model_id="seedance-2.0",
    )

    assert converted["images"] == []
    assert converted["dropped"][0]["reason"] == "provider_binding_public_url_required"
    assert "url" not in converted["dropped"][0]
    metadata = build_reference_package_metadata(converted, {"mode": "text_only"})
    assert metadata["canonical_asset_ids"] == [asset_id]
    assert metadata["provider_binding_ids"] == []


@pytest.mark.asyncio
async def test_non_final_package_can_use_public_canonical_url_only_when_no_binding_exists(
    db_session: AsyncSession,
) -> None:
    asset_id = str(uuid4())
    package = {
        "images": [{
            "url": "https://cdn.example.com/canonical-front.png",
            "canonical_asset_id": asset_id,
            "canonical_asset_version": 1,
            "role_tag": "protagonist",
        }],
        "videos": [], "audios": [], "dropped": [],
    }

    draft = await bind_reference_package(
        db_session,
        package,
        provider_id="volcano",
        model_id="seedance-2.0",
        allow_canonical_public_fallback=True,
    )
    final = await bind_reference_package(
        db_session,
        package,
        provider_id="volcano",
        model_id="seedance-2.0",
    )

    assert draft["images"][0]["provider_reference_source"] == "canonical_public_fallback"
    assert final["images"] == []
    provider = build_video_provider_content(
        final_prompt="主角转身。", duration=4, resolution="720p",
        reference_package=draft,
        model_limits={"images": 2, "videos": 0, "audios": 0},
        model_id="seedance-2.0", provider="volcano",
    )
    assert [item["type"] for item in provider["content"]] == ["image_url", "text"]
    assert provider["metadata"].get("unbound_canonical_reference_count", 0) == 0


@pytest.mark.asyncio
async def test_assets_api_creates_deterministic_verified_binding_and_reports_model_health(
    db_session: AsyncSession,
) -> None:
    from app.api.v1.endpoints.assets import (
        ProviderBindingCreateRequest,
        create_asset_provider_binding,
        get_asset_binding_health,
        invalidate_asset_provider_binding,
    )

    asset = Asset(
        id=str(uuid4()),
        user_id="binding-api-user",
        category="character",
        name="米粒侧面定稿",
        asset_type="image",
        url="/static/generated/mili-side.png",
        version=4,
        is_locked=True,
        is_final=True,
        is_active=True,
        generation_params={"checksum": "sha256:mili-side-v4"},
    )
    db_session.add(asset)
    await db_session.flush()

    before = await get_asset_binding_health(
        asset_ids=[asset.id],
        provider_id="volcano",
        model_id="doubao-seedance-2-0-260128",
        binding_kind="reference_image",
        db=db_session,
        user_id=asset.user_id,
    )
    assert before.assets[0].canonical_ready is True
    assert before.assets[0].binding_ready is False

    created = await create_asset_provider_binding(
        asset.id,
        ProviderBindingCreateRequest(
            provider_id="volcano",
            model_id="doubao-seedance-2-0-260128",
            binding_kind="reference_image",
            asset_version=4,
            verify=True,
        ),
        db=db_session,
        user_id=asset.user_id,
    )
    assert created.verified is True
    assert created.public_url == f"https://dev.invalid/provider-bindings/{asset.id}/v4"

    after = await get_asset_binding_health(
        asset_ids=[asset.id],
        provider_id="volcano",
        model_id="doubao-seedance-2-0-260128",
        binding_kind="reference_image",
        db=db_session,
        user_id=asset.user_id,
    )
    assert after.assets[0].binding_ready is True
    assert after.assets[0].binding_id == created.id

    await invalidate_asset_provider_binding(
        asset.id,
        created.id,
        db=db_session,
        user_id=asset.user_id,
    )
    invalidated = await get_asset_binding_health(
        asset_ids=[asset.id],
        provider_id="volcano",
        model_id="doubao-seedance-2-0-260128",
        binding_kind="reference_image",
        db=db_session,
        user_id=asset.user_id,
    )
    assert invalidated.assets[0].binding_ready is False


@pytest.mark.asyncio
async def test_assets_api_does_not_trust_client_reported_provider_reference(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.v1.endpoints.assets import (
        ProviderBindingCreateRequest,
        create_asset_provider_binding,
        get_asset_binding_health,
    )

    monkeypatch.setenv("DEV_MODE", "false")
    asset = Asset(
        id=str(uuid4()),
        user_id="binding-untrusted-user",
        category="character",
        name="客户端自报绑定",
        asset_type="image",
        url="/static/generated/untrusted.png",
        version=1,
        is_locked=True,
        is_final=True,
        is_active=True,
        generation_params={"checksum": "sha256:server-owned"},
    )
    db_session.add(asset)
    await db_session.flush()

    created = await create_asset_provider_binding(
        asset.id,
        ProviderBindingCreateRequest(
            provider_id="volcano",
            model_id="doubao-seedance-2-0-260128",
            provider_asset_id="client-claimed-provider-id",
            public_url="https://attacker.example/client-claimed.png",
            checksum="sha256:server-owned",
            verify=True,
        ),
        db=db_session,
        user_id=asset.user_id,
    )

    assert created.verified is False
    assert created.upload_status == "pending"
    health = await get_asset_binding_health(
        asset_ids=[asset.id],
        provider_id="volcano",
        model_id="doubao-seedance-2-0-260128",
        binding_kind="reference_image",
        db=db_session,
        user_id=asset.user_id,
    )
    assert health.assets[0].binding_ready is False


@pytest.mark.asyncio
async def test_assets_api_rejects_client_verification_of_untrusted_binding(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi import HTTPException
    from app.api.v1.endpoints.assets import (
        ProviderBindingCreateRequest,
        create_asset_provider_binding,
        verify_asset_provider_binding,
    )

    monkeypatch.setenv("DEV_MODE", "false")
    asset = Asset(
        id=str(uuid4()),
        user_id="binding-verify-user",
        category="character",
        name="待服务端验证绑定",
        asset_type="image",
        url="/static/generated/pending.png",
        version=1,
        is_locked=True,
        is_final=True,
        is_active=True,
        generation_params={"checksum": "sha256:pending"},
    )
    db_session.add(asset)
    await db_session.flush()
    created = await create_asset_provider_binding(
        asset.id,
        ProviderBindingCreateRequest(
            provider_id="volcano",
            model_id="doubao-seedance-2-0-260128",
            provider_asset_id="client-claimed-provider-id",
            verify=False,
        ),
        db=db_session,
        user_id=asset.user_id,
    )

    with pytest.raises(HTTPException) as exc_info:
        await verify_asset_provider_binding(
            asset.id,
            created.id,
            db=db_session,
            user_id=asset.user_id,
        )

    assert exc_info.value.status_code == 409
    assert "服务端" in str(exc_info.value.detail)


def test_provider_adapter_never_submits_unbound_canonical_reference() -> None:
    result = build_video_provider_content(
        final_prompt="米粒站在雨夜屋顶。",
        duration=4,
        resolution="720p",
        reference_package={
            "images": [{
                "url": "https://canonical.example.com/mili-v3.png",
                "canonical_asset_id": "asset-mili-v3",
                "canonical_asset_version": 3,
                "role_tag": "protagonist",
            }],
        },
        model_limits={"images": 2, "videos": 0, "audios": 0},
        model_id="seedance-2.0",
        provider="volcano",
    )

    assert [item["type"] for item in result["content"]] == ["text"]
    assert result["metadata"]["unbound_canonical_reference_count"] == 1


@pytest.mark.parametrize(
    ("limits", "required"),
    [
        ({"images": 1, "videos": 0, "audios": 0}, False),
        ({"images": 2, "videos": 0, "audios": 0}, True),
        ({"images": 1, "videos": 1, "audios": 0}, True),
        ({"images": 1, "videos": 0, "audios": 1}, True),
    ],
)
def test_provider_binding_requirement_matches_workflow_reference_package_rule(limits: dict, required: bool) -> None:
    assert requires_provider_bindings(limits) is required


def test_video_route_binds_canonical_package_before_provider_adapter() -> None:
    from app.api.v1.endpoints.video import generate_video

    source = inspect.getsource(generate_video)
    build_index = source.index("reference_package = await build_reference_package(")
    bind_index = source.index("reference_package = await bind_reference_package(", build_index)
    adapter_index = source.index("provider_content = build_video_provider_content(", bind_index)
    assert build_index < bind_index < adapter_index


@pytest.mark.asyncio
async def test_workflow_final_quality_blocks_when_selected_model_bindings_are_missing(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.features.workflow_media import public as workflow_media
    from app.features.workflow_media.application import reference_packages
    from app.models import Shot, Workflow

    workflow = Workflow(id=str(uuid4()), user_id="workflow-binding-user", title="绑定门禁")
    shot = Shot(
        id=str(uuid4()),
        user_id=workflow.user_id,
        storyboard_id=str(uuid4()),
        shot_number=1,
        character_refs=[{"name": "米粒"}],
    )
    canonical = {
        "images": [
            {"canonical_asset_id": "front", "canonical_asset_version": 3, "role_tag": "protagonist"},
            {"canonical_asset_id": "side", "canonical_asset_version": 3, "role_tag": "protagonist"},
        ],
        "videos": [], "audios": [], "dropped": [],
    }
    bound = {
        **canonical,
        "images": [],
        "dropped": [
            {"canonical_asset_id": "front", "reason": "provider_binding_not_found"},
            {"canonical_asset_id": "side", "reason": "provider_binding_not_found"},
        ],
    }
    calls: list[tuple[str, str]] = []

    async def fake_build(*_args, **_kwargs):
        return canonical

    async def fake_bind(_db, package, *, provider_id, model_id):
        assert package is canonical
        calls.append((provider_id, model_id))
        return bound

    monkeypatch.setattr(reference_packages, "build_reference_package", fake_build)
    monkeypatch.setattr(reference_packages, "bind_reference_package", fake_bind)

    with pytest.raises(workflow_media.WorkflowMediaError) as exc_info:
        await workflow_media.build_final_quality_reference_packages(
            db_session,
            workflow.user_id,
            workflow,
            [shot],
            model_limits={"images": 9, "videos": 3, "audios": 3},
            resolve_public_url=lambda *_args: None,
            provider_id="volcano",
            model_id="seedance-2.0",
        )

    assert calls == [("volcano", "seedance-2.0")]
    assert exc_info.value.detail["code"] == "provider_binding_required"


@pytest.mark.asyncio
async def test_binding_health_does_not_require_binding_for_text_only_model(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.v1.endpoints import assets as assets_endpoint

    asset = Asset(
        id=str(uuid4()), user_id="text-only-user", category="character", name="文本资产",
        asset_type="image", url="https://cdn.example.com/text-only.png", version=1,
        is_locked=True, is_final=True, is_active=True,
    )
    db_session.add(asset)
    await db_session.flush()
    monkeypatch.setattr(assets_endpoint, "get_model_reference_limits", lambda _model_id: {"images": 0, "videos": 0, "audios": 0})

    result = await assets_endpoint.get_asset_binding_health(
        asset_ids=[asset.id], provider_id="text-provider", model_id="text-only-model",
        binding_kind="reference_image", db=db_session, user_id=asset.user_id,
    )

    assert result.assets[0].binding_required is False
    assert result.assets[0].binding_ready is True
