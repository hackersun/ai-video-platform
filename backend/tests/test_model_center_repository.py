from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.features.model_config.public import (
    ModelConfigurationError,
    compare_legacy_and_canonical_catalogs,
    list_product_catalog,
    project_legacy_external_providers,
    project_legacy_llm_models,
    resolve_profile_version,
)
from app.models.external_api import ExternalAPIProvider
from app.models.llm_config import LLMConfig, LLMModel, LLMProvider
from app.models.model_center import ModelProfileVersion


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
