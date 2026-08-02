from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
import json
import os
import subprocess
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.time_utils import utc_now
from app.api.v1.endpoints import external_api, llm_config
from app.features.model_config.catalog import (
    is_product_visible_external_provider,
    is_product_visible_model,
    is_product_visible_provider,
)
from app.features.model_config.public import (
    CatalogComparison,
    ModelConfigurationError,
    compare_legacy_and_canonical_catalogs,
    list_product_catalog,
    project_legacy_external_providers,
    project_legacy_llm_models,
    resolve_profile_version,
)
from app.models.external_api import ExternalAPIProvider
from app.models.llm_config import LLMConfig, LLMModel, LLMProvider
from app.models.model_center import ModelProfile, ModelProfileVersion, ModelProvider


@pytest_asyncio.fixture()
async def db_session() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def seed_verified_llm_config(
    db: AsyncSession,
    *,
    provider: str,
    model: str,
) -> LLMConfig:
    provider_id = f"provider-{uuid4()}"
    model_id = f"model-{uuid4()}"
    config = LLMConfig(
        id=f"config-{uuid4()}",
        user_id="catalog-user",
        model_id=model_id,
        name="已验证配置",
        is_active=True,
        test_status="success",
    )
    config.set_api_key_encrypted("sk-catalog-test")
    db.add_all(
        [
            LLMProvider(
                id=provider_id,
                name=provider,
                name_cn=provider.title(),
                base_url="https://example.invalid",
                is_active=True,
            ),
            LLMModel(
                id=model_id,
                provider_id=provider_id,
                model_id=model,
                model_name=model,
                model_type="tts",
                capabilities=["text-to-speech"],
                is_active=True,
            ),
            config,
        ]
    )
    await db.commit()
    return config


async def seed_profile_version(
    db: AsyncSession,
    *,
    model_id: str,
    version: int,
    status: str,
    driver_key: str,
    capabilities: list[str],
) -> ModelProfileVersion:
    profile = ModelProfileVersion(
        id=f"profile-{uuid4()}",
        model_id=model_id,
        version=version,
        api_model_id="seed-tts-2.0",
        driver_key=driver_key,
        capabilities=capabilities,
        input_contract={"text": "string"},
        output_contract={"audio_url": "string"},
        parameter_schema={},
        default_params={},
        limits={},
        pricing={},
        contract_version="v1",
        status=status,
        checksum="a" * 64,
    )
    db.add(profile)
    await db.commit()
    return profile


@pytest.mark.asyncio
async def test_product_catalog_prefers_published_profile_without_losing_legacy_config(
    db_session: AsyncSession,
) -> None:
    legacy = await seed_verified_llm_config(
        db_session, provider="volcano", model="seed-tts-2.0"
    )
    profile = await seed_profile_version(
        db_session,
        model_id=legacy.model_id,
        version=1,
        status="published",
        driver_key="volcano_openspeech_v3",
        capabilities=["speech_generation"],
    )

    catalog = await list_product_catalog(db_session, legacy.user_id)

    item = next(item for item in catalog.models if item.api_model_id == "seed-tts-2.0")
    assert item.profile_version_id == profile.id
    assert item.legacy_config_id == legacy.id
    assert item.certification_status == "connection_verified"


@pytest.mark.asyncio
async def test_projection_hides_internal_rows_and_preserves_legacy_response_fields(
    db_session: AsyncSession,
) -> None:
    legacy = await seed_verified_llm_config(
        db_session, provider="volcano", model="seed-tts-2.0"
    )
    internal = await seed_verified_llm_config(
        db_session, provider="contract-text", model="test-hidden-model"
    )
    db_session.add(
        LLMModel(
            id="extra-hidden-model",
            provider_id=(await db_session.get(LLMModel, legacy.model_id)).provider_id,
            model_id="preflight-video-model",
            model_name="Preflight Video Model",
            model_type="video",
            capabilities=["text-to-video"],
            is_active=True,
        )
    )
    external = ExternalAPIProvider(
        id="external-visible",
        name="ffmpeg_cloud",
        name_cn="云端渲染",
        api_type="render",
        base_url="https://render.example.invalid",
        is_active=True,
        supported_models=[{"id": "render-v1", "capabilities": ["render"]}],
    )
    hidden_external = ExternalAPIProvider(
        id="external-provider-test-hidden",
        name="external-provider-test-hidden",
        name_cn="外部适配测试供应商",
        api_type="render",
        base_url="https://hidden.example.invalid",
        is_active=True,
    )
    db_session.add_all([external, hidden_external])
    await db_session.commit()

    models = await project_legacy_llm_models(db_session, legacy.user_id)
    providers = await project_legacy_external_providers(db_session)

    visible = next(item for item in models if item["id"] == legacy.model_id)
    assert set(visible) == {
        "id", "provider_id", "model_id", "model_name", "model_name_cn", "model_type",
        "capabilities", "context_window", "max_tokens", "input_cost_per_1k",
        "output_cost_per_1k", "is_active", "is_recommended", "description", "base_url",
        "user_config_id", "user_config_name", "user_configured", "user_config_count",
        "user_is_default", "user_test_status", "user_test_message", "user_key_available",
        "contract_status", "contract_version", "verified_at", "reference_limits",
        "verification_gaps",
    }
    assert visible["user_config_id"] == legacy.id
    assert all(item["id"] != internal.model_id for item in models)
    assert all(item["id"] != "extra-hidden-model" for item in models)
    assert {item["id"] for item in providers} == {external.id}
    assert set(providers[0]) == {
        "id", "name", "name_cn", "api_type", "base_url", "auth_type", "is_active",
        "description", "doc_url", "supported_models", "capabilities",
    }


@pytest.mark.asyncio
async def test_resolution_and_shadow_comparison_are_read_only_and_sanitized(
    db_session: AsyncSession,
) -> None:
    legacy = await seed_verified_llm_config(
        db_session, provider="volcano", model="seed-tts-2.0"
    )
    profile = await seed_profile_version(
        db_session,
        model_id=legacy.model_id,
        version=1,
        status="published",
        driver_key="volcano_openspeech_v3",
        capabilities=["speech_generation"],
    )

    resolved = await resolve_profile_version(db_session, profile_version_id=profile.id)
    before = await project_legacy_llm_models(db_session, legacy.user_id)
    comparison = await compare_legacy_and_canonical_catalogs(db_session, legacy.user_id)
    after = await project_legacy_llm_models(db_session, legacy.user_id)

    assert resolved.driver_key == "volcano_openspeech_v3"
    assert resolved.api_model_id == "seed-tts-2.0"
    assert comparison.equivalent is True
    assert comparison.sanitized_summary()["legacy_model_count"] == 1
    assert "sk-catalog-test" not in repr(comparison.sanitized_summary())
    assert before == after


@pytest.mark.parametrize(
    "provider",
    [
        SimpleNamespace(id="deterministic-acceptance", name="ok", name_en="", name_cn="", base_url="", description=""),
        SimpleNamespace(id="visible", name="contract-provider", name_en="", name_cn="", base_url="", description=""),
        SimpleNamespace(id="visible", name="ok", name_en="", name_cn="TTS开通供应商", base_url="", description=""),
        SimpleNamespace(id="visible", name="ok", name_en="test-provider-hidden", name_cn="", base_url="", description=""),
    ],
)
def test_product_provider_visibility_covers_all_legacy_fields(provider) -> None:
    assert is_product_visible_provider(provider) is False


@pytest.mark.parametrize(
    "model",
    [
        SimpleNamespace(id="visible", provider_id="provider", model_id="test-video-one", model_name="ok", model_name_cn="", description=""),
        SimpleNamespace(id="tts-model-one", provider_id="provider", model_id="remote", model_name="ok", model_name_cn="", description=""),
        SimpleNamespace(id="visible", provider_id="provider", model_id="remote", model_name="audio API Model", model_name_cn="", description=""),
        SimpleNamespace(id="visible", provider_id="provider", model_id="remote", model_name="ok", model_name_cn="模型测试", description=""),
        SimpleNamespace(id="visible", provider_id="provider", model_id="preflight-video-model", model_name="ok", model_name_cn="", description=""),
        SimpleNamespace(id="visible", provider_id="provider", model_id="contract-video-api-123", model_name="contract video", model_name_cn="", description=""),
        SimpleNamespace(id="live-video-123", provider_id="provider", model_id="remote", model_name="video api-video live-video-123", model_name_cn="", description=""),
    ],
)
def test_product_model_visibility_covers_all_legacy_fields(model) -> None:
    assert is_product_visible_model(model) is False


@pytest.mark.parametrize(
    "provider",
    [
        SimpleNamespace(id="visible", name="provider-test-row", name_cn="", description=""),
        SimpleNamespace(id="visible", name="provider", name_cn="外部适配测试供应商", description=""),
        SimpleNamespace(id="visible", name="provider", name_cn="", description="test fixture"),
    ],
)
def test_external_provider_visibility_covers_all_legacy_fields(provider) -> None:
    assert is_product_visible_external_provider(provider) is False


@pytest.mark.asyncio
async def test_llm_projection_matches_endpoint_for_aliases_and_multiple_configs(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = LLMProvider(
        id="compat-provider", name="compat-provider", name_cn="兼容供应商",
        base_url="https://example.invalid", is_active=True,
    )
    legacy_alias = LLMModel(
        id="compat.speech", provider_id=provider.id, model_id="speech-2",
        model_name="Speech 2 Legacy", model_type="tts", capabilities=["text-to-speech"],
        is_active=True,
    )
    modern_alias = LLMModel(
        id="compat-speech", provider_id=provider.id, model_id="speech-2",
        model_name="Speech 2", model_type="tts", capabilities=["text-to-speech"],
        is_active=True, is_recommended=True,
    )
    now = utc_now()
    default_failed = LLMConfig(
        id="compat-default-failed", user_id="compat-user", model_id=legacy_alias.id,
        name="默认失败配置", is_active=True, is_default=True, test_status="failed",
        created_at=now, updated_at=now,
    )
    verified_older = LLMConfig(
        id="compat-verified", user_id="compat-user", model_id=legacy_alias.id,
        name="已验证非默认配置", is_active=True, is_default=False, test_status="success",
        created_at=now - timedelta(days=1), updated_at=now - timedelta(days=1),
    )
    default_failed.set_api_key_encrypted("sk-failed")
    verified_older.set_api_key_encrypted("sk-verified")
    db_session.add_all([provider, legacy_alias, modern_alias, default_failed, verified_older])
    await db_session.commit()

    async def skip_default_seed(_db: AsyncSession) -> None:
        return None

    monkeypatch.delenv("MODEL_CENTER_CANONICAL_READS", raising=False)
    monkeypatch.setattr(llm_config, "ensure_default_models", skip_default_seed)
    endpoint_rows = await llm_config.list_models(provider.id, db_session, "compat-user")
    projected_rows = await project_legacy_llm_models(db_session, "compat-user", provider.id)

    assert projected_rows == endpoint_rows
    assert [row["id"] for row in projected_rows] == [legacy_alias.id]
    assert projected_rows[0]["user_config_id"] == default_failed.id
    assert projected_rows[0]["user_test_status"] == "failed"

    default_failed.is_default = False
    modern_verified = LLMConfig(
        id="compat-modern-verified", user_id="compat-user", model_id=modern_alias.id,
        name="现代别名已验证配置", is_active=True, is_default=False, test_status="success",
        created_at=now - timedelta(days=2), updated_at=now - timedelta(days=2),
    )
    modern_verified.set_api_key_encrypted("sk-modern-verified")
    db_session.add(modern_verified)
    await db_session.commit()

    endpoint_rows = await llm_config.list_models(provider.id, db_session, "compat-user")
    projected_rows = await project_legacy_llm_models(db_session, "compat-user", provider.id)

    assert projected_rows == endpoint_rows
    assert [row["id"] for row in projected_rows] == [modern_alias.id]
    assert projected_rows[0]["user_test_status"] == "success"


@pytest.mark.asyncio
async def test_external_projection_matches_endpoint_field_and_order_contract(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    providers = [
        ExternalAPIProvider(id="z-custom", name="z", name_cn="Z供应商", api_type="video", base_url="", is_active=True),
        ExternalAPIProvider(id="openai", name="openai", name_cn="OpenAI / Sora", api_type="audio_video", base_url="https://api.openai.com/v1", is_active=True),
        ExternalAPIProvider(id="a-custom", name="a", name_cn="A供应商", api_type="render", base_url="", is_active=True),
    ]
    db_session.add_all(providers)
    await db_session.commit()

    async def seeded_providers(_db: AsyncSession) -> list[ExternalAPIProvider]:
        return providers

    monkeypatch.setattr(external_api, "_ensure_default_providers", seeded_providers)
    endpoint_rows = [item.model_dump() for item in await external_api.list_providers(db_session)]
    projected_rows = await project_legacy_external_providers(db_session)

    assert projected_rows == endpoint_rows
    assert [row["id"] for row in projected_rows] == ["openai", "a-custom", "z-custom"]


@pytest.mark.asyncio
@pytest.mark.parametrize("insert_order", [(2, 1), (1, 2)])
async def test_canonical_only_catalog_chooses_latest_published_version_deterministically(
    db_session: AsyncSession,
    insert_order: tuple[int, int],
) -> None:
    provider = ModelProvider(
        id="canonical-provider", code="canonical", display_name="Canonical",
        provider_family="test", enabled=True,
    )
    model = ModelProfile(
        id="canonical-model", provider_id=provider.id, profile_key="canonical-model",
        display_name="Canonical Model", enabled=True,
    )
    versions = {
        version: ModelProfileVersion(
            id=f"canonical-version-{version}", model_id=model.id, version=version,
            api_model_id=f"canonical-api-v{version}", driver_key="canonical-driver",
            capabilities=["text_generation"], input_contract={}, output_contract={},
            parameter_schema={}, default_params={}, limits={}, pricing={},
            contract_version=f"v{version}", status="published", checksum=str(version) * 64,
        )
        for version in (1, 2)
    }
    db_session.add_all([provider, model, *(versions[version] for version in insert_order)])
    await db_session.commit()

    catalog = await list_product_catalog(db_session, "canonical-user")

    assert [(item.api_model_id, item.profile_version_id) for item in catalog.models] == [
        ("canonical-api-v2", "canonical-version-2")
    ]


async def _canonical_catalog_query_count(item_count: int) -> int:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        provider = ModelProvider(
            id="query-provider", code="query-provider", display_name="Query Provider",
            provider_family="test", enabled=True,
        )
        db.add(provider)
        for index in range(item_count):
            model_id = f"query-model-{index}"
            db.add(ModelProfile(
                id=model_id, provider_id=provider.id, profile_key=model_id,
                display_name=model_id, enabled=True,
            ))
            db.add(ModelProfileVersion(
                id=f"query-version-{index}", model_id=model_id, version=1,
                api_model_id=f"query-api-{index}", driver_key="query-driver",
                capabilities=["text_generation"], input_contract={}, output_contract={},
                parameter_schema={}, default_params={}, limits={}, pricing={},
                contract_version="v1", status="published", checksum=f"{index:064x}",
            ))
        await db.commit()

    query_count = 0

    def count_query(*_args) -> None:
        nonlocal query_count
        query_count += 1

    event.listen(engine.sync_engine, "before_cursor_execute", count_query)
    async with factory() as db:
        await list_product_catalog(db, "query-user")
    event.remove(engine.sync_engine, "before_cursor_execute", count_query)
    await engine.dispose()
    return query_count


@pytest.mark.asyncio
async def test_catalog_query_count_is_constant_as_canonical_items_grow() -> None:
    small_count = await _canonical_catalog_query_count(1)
    large_count = await _canonical_catalog_query_count(12)

    assert small_count == large_count == 7


@pytest.mark.asyncio
async def test_canonical_catalog_hides_internal_profile_display_names(
    db_session: AsyncSession,
) -> None:
    provider = ModelProvider(
        id="visible-provider", code="visible-provider", display_name="Visible Provider",
        provider_family="test", enabled=True,
    )
    model = ModelProfile(
        id="internal-profile", provider_id=provider.id, profile_key="internal-profile",
        display_name="test-workflow-unverified-video", enabled=True,
    )
    version = ModelProfileVersion(
        id="public-looking-version", model_id=model.id, version=1,
        api_model_id="doubao-seedance-story-bible-voice", driver_key="video-driver",
        capabilities=["video_generation"], input_contract={}, output_contract={},
        parameter_schema={}, default_params={}, limits={}, pricing={},
        contract_version="v1", status="published", checksum="f" * 64,
    )
    label_model = ModelProfile(
        id="internal-label-profile", provider_id=provider.id, profile_key="internal-label-profile",
        display_name="Seedance Test", enabled=True,
    )
    label_version = ModelProfileVersion(
        id="public-looking-label-version", model_id=label_model.id, version=1,
        api_model_id="doubao-seedance-public-looking", driver_key="video-driver",
        capabilities=["video_generation"], input_contract={}, output_contract={},
        parameter_schema={}, default_params={}, limits={}, pricing={},
        contract_version="v1", status="published", checksum="e" * 64,
    )
    db_session.add_all([provider, model, version, label_model, label_version])
    await db_session.commit()

    catalog = await list_product_catalog(db_session, "catalog-user")

    assert catalog.models == ()


@pytest.mark.asyncio
async def test_catalog_without_provider_filter_keeps_all_visible_providers(
    db_session: AsyncSession,
) -> None:
    await seed_verified_llm_config(db_session, provider="volcano", model="seed-tts-2.0")
    provider = ModelProvider(
        id="canonical-provider", code="canonical", display_name="Canonical",
        provider_family="test", enabled=True,
    )
    model = ModelProfile(
        id="canonical-model", provider_id=provider.id, profile_key="canonical-model",
        display_name="Canonical Model", enabled=True,
    )
    version = ModelProfileVersion(
        id="canonical-version", model_id=model.id, version=1, api_model_id="canonical-api",
        driver_key="canonical-driver", capabilities=["text_generation"], input_contract={},
        output_contract={}, parameter_schema={}, default_params={}, limits={}, pricing={},
        contract_version="v1", status="published", checksum="d" * 64,
    )
    db_session.add_all([provider, model, version])
    await db_session.commit()

    catalog = await list_product_catalog(db_session, "catalog-user")

    assert {item.provider_code for item in catalog.models} == {"volcano", "canonical"}


def test_catalog_comparison_fingerprint_is_stable_across_hash_seeds() -> None:
    code = """
from app.features.model_config.public import CatalogComparison
comparison = CatalogComparison(
    legacy_provider_ids=frozenset({'provider-b', 'provider-a'}),
    canonical_provider_ids=frozenset({'provider-a', 'provider-b'}),
    legacy_model_keys=frozenset({'provider-b:model-b', 'provider-a:model-a'}),
    canonical_model_keys=frozenset({'provider-a:model-a', 'provider-b:model-b'}),
)
print(comparison.sanitized_summary()['comparison_fingerprint'])
"""
    outputs = []
    for seed in ("1", "2"):
        environment = {**os.environ, "PYTHONHASHSEED": seed}
        outputs.append(subprocess.check_output([sys.executable, "-c", code], env=environment, text=True).strip())

    canonical_payload = {
        "canonical_model_keys": ["provider-a:model-a", "provider-b:model-b"],
        "canonical_provider_ids": ["provider-a", "provider-b"],
        "legacy_model_keys": ["provider-a:model-a", "provider-b:model-b"],
        "legacy_provider_ids": ["provider-a", "provider-b"],
    }
    expected = sha256(
        json.dumps(canonical_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:16]
    assert outputs == [expected, expected]


@pytest.mark.asyncio
async def test_default_endpoint_mode_adds_no_shadow_comparison_query(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy = await seed_verified_llm_config(db_session, provider="shadow-default", model="shadow-default-model")

    async def skip_default_seed(_db: AsyncSession) -> None:
        return None

    query_count = 0

    def count_query(*_args) -> None:
        nonlocal query_count
        query_count += 1

    monkeypatch.delenv("MODEL_CENTER_CANONICAL_READS", raising=False)
    monkeypatch.setattr(llm_config, "ensure_default_models", skip_default_seed)
    event.listen(db_session.bind.sync_engine, "before_cursor_execute", count_query)
    response = await llm_config.list_models(None, db_session, legacy.user_id)
    event.remove(db_session.bind.sync_engine, "before_cursor_execute", count_query)

    assert response
    assert query_count == 3


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_id", "seed_internal_provider", "expected_query_count"),
    [
        ("missing-provider", False, 2),
        ("test-provider-query-short-circuit", True, 1),
    ],
)
async def test_provider_filter_preserves_legacy_early_return_query_shape(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    provider_id: str,
    seed_internal_provider: bool,
    expected_query_count: int,
) -> None:
    if seed_internal_provider:
        db_session.add(LLMProvider(
            id=provider_id, name=provider_id, name_cn="测试供应商",
            base_url="https://example.invalid", is_active=True,
        ))
        await db_session.commit()

    async def skip_default_seed(_db: AsyncSession) -> None:
        return None

    query_count = 0

    def count_query(*_args) -> None:
        nonlocal query_count
        query_count += 1

    monkeypatch.delenv("MODEL_CENTER_CANONICAL_READS", raising=False)
    monkeypatch.setattr(llm_config, "ensure_default_models", skip_default_seed)
    event.listen(db_session.bind.sync_engine, "before_cursor_execute", count_query)
    try:
        response = await llm_config.list_models(provider_id, db_session, "query-user")
    finally:
        event.remove(db_session.bind.sync_engine, "before_cursor_execute", count_query)

    assert response == []
    assert query_count == expected_query_count


@pytest.mark.asyncio
async def test_shadow_endpoint_logs_only_sanitized_summary_and_keeps_legacy_response(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    legacy = await seed_verified_llm_config(db_session, provider="shadow", model="seed-tts-2.0")
    await seed_profile_version(
        db_session, model_id=legacy.model_id, version=1, status="published",
        driver_key="shadow-driver", capabilities=["speech_generation"],
    )

    async def skip_default_seed(_db: AsyncSession) -> None:
        return None

    monkeypatch.setenv("MODEL_CENTER_CANONICAL_READS", "shadow")
    monkeypatch.setattr(llm_config, "ensure_default_models", skip_default_seed)
    expected = await project_legacy_llm_models(db_session, legacy.user_id)
    with caplog.at_level("INFO"):
        actual = await llm_config.list_models(None, db_session, legacy.user_id)

    record = next(record for record in caplog.records if record.message == "model_center_catalog_shadow")
    summary = record.model_center_shadow
    assert actual == expected
    assert set(summary) == {
        "legacy_provider_count", "canonical_provider_count",
        "legacy_model_count", "canonical_model_count", "comparison_fingerprint",
    }
    assert "sk-catalog-test" not in json.dumps(summary, sort_keys=True)


@pytest.mark.asyncio
async def test_shadow_comparison_failure_is_sanitized_and_does_not_change_response(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from app.features.model_config import legacy_projection

    legacy = await seed_verified_llm_config(db_session, provider="shadow-failure", model="shadow-model")

    async def skip_default_seed(_db: AsyncSession) -> None:
        return None

    async def fail_catalog(*_args, **_kwargs):
        raise RuntimeError("sk-never-log-this")

    monkeypatch.setenv("MODEL_CENTER_CANONICAL_READS", "shadow")
    monkeypatch.setattr(llm_config, "ensure_default_models", skip_default_seed)
    monkeypatch.setattr(legacy_projection, "list_product_catalog", fail_catalog)
    expected = await project_legacy_llm_models(db_session, legacy.user_id)
    with caplog.at_level("WARNING"):
        actual = await llm_config.list_models(None, db_session, legacy.user_id)

    record = next(record for record in caplog.records if record.message == "model_center_catalog_shadow_failed")
    assert actual == expected
    assert record.model_center_shadow == {"status": "failed"}
    assert "sk-never-log-this" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_point", ["summary", "success_log"])
async def test_shadow_side_effect_exceptions_never_escape_legacy_endpoint(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    failure_point: str,
) -> None:
    legacy = await seed_verified_llm_config(
        db_session, provider="shadow-side-effect", model="shadow-side-effect-model",
    )

    async def skip_default_seed(_db: AsyncSession) -> None:
        return None

    def fail_side_effect(*_args, **_kwargs):
        raise RuntimeError(f"{failure_point}-must-not-escape")

    def fail_warning(*_args, **_kwargs):
        raise RuntimeError("warning-must-not-escape")

    monkeypatch.setenv("MODEL_CENTER_CANONICAL_READS", "shadow")
    monkeypatch.setattr(llm_config, "ensure_default_models", skip_default_seed)
    expected = await project_legacy_llm_models(db_session, legacy.user_id)
    monkeypatch.setattr(llm_config.logger, "warning", fail_warning)
    if failure_point == "summary":
        monkeypatch.setattr(CatalogComparison, "sanitized_summary", fail_side_effect)
    else:
        monkeypatch.setattr(llm_config.logger, "info", fail_side_effect)

    actual = await llm_config.list_models(None, db_session, legacy.user_id)

    assert actual == expected
