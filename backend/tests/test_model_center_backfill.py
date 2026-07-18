from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.llm_config import LLMConfig, LLMModel, LLMProvider
from app.models.model_center import (
    ModelBinding,
    ModelConnection,
    ModelProfile,
    ModelProfileVersion,
    ModelProvider,
    ProductionRecipeVersion,
)
from app.models.prompt_skill import PromptSkill


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


async def _seed_legacy_catalog(db: AsyncSession) -> LLMConfig:
    provider = LLMProvider(
        id=f"provider-{uuid4()}", name="volcano", name_cn="火山", is_active=True,
    )
    model = LLMModel(
        id=f"model-{uuid4()}", provider_id=provider.id,
        model_id="seedance-test", model_name="Seedance Test", model_type="video",
        capabilities=["text-to-video"], is_active=True,
    )
    config = LLMConfig(
        id=f"config-{uuid4()}", user_id="backfill-user", model_id=model.id,
        name="已验证配置", is_active=True, is_default=True, test_status="success",
    )
    config.set_api_key_encrypted("sk-backfill-secret")
    db.add_all([provider, model, config])
    await db.commit()
    return config


async def _canonical_counts(db: AsyncSession) -> tuple[int, int, int, int, int, int]:
    counts = []
    for model in (
        ModelProvider, ModelProfile, ModelProfileVersion, ModelConnection,
        ModelBinding, ProductionRecipeVersion,
    ):
        counts.append(int(await db.scalar(select(func.count()).select_from(model))))
    return tuple(counts)


def test_prompt_recovery_cli_requires_existing_backup_for_apply(tmp_path) -> None:
    from scripts.backfill_model_center import _validate_prompt_apply_backup

    missing = tmp_path / "missing.db"
    with pytest.raises(SystemExit, match="backup"):
        _validate_prompt_apply_backup(apply_prompts=True, backup_ack=str(missing))

    backup = tmp_path / "backup.db"
    backup.write_bytes(b"sqlite backup evidence")
    _validate_prompt_apply_backup(apply_prompts=True, backup_ack=str(backup))
    _validate_prompt_apply_backup(apply_prompts=False, backup_ack=None)


@pytest.mark.asyncio
async def test_check_mode_reports_plan_without_writing(db_session: AsyncSession) -> None:
    from app.features.model_config.backfill import backfill_model_center

    await _seed_legacy_catalog(db_session)
    before = await _canonical_counts(db_session)

    report = await backfill_model_center(db_session, apply=False)

    assert report.planned_total > 0
    assert report.created_total == 0
    assert await _canonical_counts(db_session) == before
    assert "sk-backfill-secret" not in report.sanitized_dict().__repr__()


@pytest.mark.asyncio
async def test_backfill_copies_only_existing_ciphertext_and_is_idempotent(
    db_session: AsyncSession,
) -> None:
    from app.features.model_config.backfill import (
        backfill_model_center,
        get_connection_for_legacy_config,
    )

    legacy_config = await _seed_legacy_catalog(db_session)

    first = await backfill_model_center(db_session, apply=True)
    connection = await get_connection_for_legacy_config(db_session, legacy_config.id)
    second = await backfill_model_center(db_session, apply=True)

    assert connection is not None
    assert connection.connection_params["legacy_config_id"] == legacy_config.id
    assert connection.api_key == legacy_config.api_key
    assert connection.api_key != "sk-backfill-secret"
    canonical_ids = [
        connection.id,
        *(row[0] for row in (await db_session.execute(select(ModelProvider.id))).all()),
        *(row[0] for row in (await db_session.execute(select(ModelProfile.id))).all()),
        *(row[0] for row in (await db_session.execute(select(ModelProfileVersion.id))).all()),
        *(row[0] for row in (await db_session.execute(select(ModelBinding.id))).all()),
    ]
    assert all(len(identifier) <= 36 for identifier in canonical_ids)
    assert first.connections_created == 1
    assert first.created_total > 0
    assert second.created_total == 0
    assert second.updated_total == 0
    recipes = list((await db_session.scalars(select(ProductionRecipeVersion))).all())
    assert {recipe.recipe_key for recipe in recipes} == {
        "legacy.strategy.draft_fast", "legacy.strategy.final_quality",
        "legacy.strategy.low_cost", "legacy.strategy.separate_video_tts",
        "legacy.strategy.direct_av_first",
    }


@pytest.mark.asyncio
async def test_backfill_requires_credential_reentry_for_undecryptable_legacy_ciphertext(
    db_session: AsyncSession,
) -> None:
    from cryptography.fernet import Fernet

    from app.features.model_config.backfill import (
        backfill_model_center,
        get_connection_for_legacy_config,
    )

    legacy_config = await _seed_legacy_catalog(db_session)
    legacy_config.api_key = Fernet(Fernet.generate_key()).encrypt(b"legacy-secret").decode()
    await db_session.commit()

    report = await backfill_model_center(db_session, apply=True)
    connection = await get_connection_for_legacy_config(db_session, legacy_config.id)

    assert connection is not None
    assert connection.api_key == ""
    assert connection.status == "draft"
    assert connection.tested_at is None
    assert connection.connection_params["credential_reentry_required"] is True
    assert report.connections_created == 1


@pytest.mark.asyncio
async def test_backfill_creates_one_binding_for_duplicate_default_legacy_configs(
    db_session: AsyncSession,
) -> None:
    from app.features.model_config.backfill import backfill_model_center

    db_session.autoflush = False
    legacy_config = await _seed_legacy_catalog(db_session)
    duplicate = LLMConfig(
        id=f"config-{uuid4()}", user_id=legacy_config.user_id, model_id=legacy_config.model_id,
        name="重复默认配置", is_active=True, is_default=True, test_status="success",
    )
    duplicate.set_api_key_encrypted("sk-duplicate-secret")
    db_session.add(duplicate)
    await db_session.commit()

    await backfill_model_center(db_session, apply=True)
    bindings = list((await db_session.scalars(select(ModelBinding))).all())

    assert len(bindings) == 1
    assert bindings[0].capability == "video_generation"


@pytest.mark.asyncio
async def test_backfill_reuses_one_profile_for_duplicate_legacy_models(
    db_session: AsyncSession,
) -> None:
    from app.features.model_config.backfill import backfill_model_center

    db_session.autoflush = False
    legacy_config = await _seed_legacy_catalog(db_session)
    original_model = await db_session.get(LLMModel, legacy_config.model_id)
    db_session.add(LLMModel(
        id=f"model-{uuid4()}", provider_id=original_model.provider_id,
        model_id=original_model.model_id, model_name=original_model.model_name,
        model_name_cn=original_model.model_name_cn, model_type=original_model.model_type,
        capabilities=original_model.capabilities, is_active=True,
    ))
    await db_session.commit()

    await backfill_model_center(db_session, apply=True)

    assert int(await db_session.scalar(select(func.count()).select_from(ModelProfile))) == 1
    assert int(await db_session.scalar(select(func.count()).select_from(ModelProfileVersion))) == 1


@pytest.mark.asyncio
async def test_backfill_keeps_distinct_legacy_model_contracts_separate(
    db_session: AsyncSession,
) -> None:
    from app.features.model_config.backfill import backfill_model_center

    db_session.autoflush = False
    legacy_config = await _seed_legacy_catalog(db_session)
    original_model = await db_session.get(LLMModel, legacy_config.model_id)
    db_session.add(LLMModel(
        id=f"model-{uuid4()}", provider_id=original_model.provider_id,
        model_id=original_model.model_id, model_name=original_model.model_name,
        model_name_cn=original_model.model_name_cn, model_type=original_model.model_type,
        capabilities=original_model.capabilities, context_window=8192, max_tokens=4096,
        is_active=True,
    ))
    await db_session.commit()

    await backfill_model_center(db_session, apply=True)

    assert int(await db_session.scalar(select(func.count()).select_from(ModelProfile))) == 2


@pytest.mark.asyncio
async def test_backfill_projects_active_prompt_without_exposing_prompt_body(
    db_session: AsyncSession,
) -> None:
    from app.features.model_config.backfill import backfill_model_center
    from app.models.prompt_profile import PromptProfileVersion

    db_session.add(PromptSkill(
        id="prompt-backfill", user_id="backfill-user", name="镜头约束",
        task="shot_video", content="仅供模型使用的提示词正文", is_active=True,
    ))
    await db_session.commit()

    report = await backfill_model_center(db_session, apply=True)
    version = await db_session.scalar(select(PromptProfileVersion))

    assert version is not None
    assert version.content == "仅供模型使用的提示词正文"
    assert report.prompt_versions_created == 1
    assert "仅供模型使用的提示词正文" not in repr(report.sanitized_dict())


@pytest.mark.asyncio
async def test_backfill_links_active_and_inactive_prompts_idempotently(
    db_session: AsyncSession,
) -> None:
    from app.features.model_config.backfill import backfill_model_center
    from app.models.prompt_profile import PromptProfileVersion

    db_session.add_all([
        PromptSkill(
            id="active-prompt",
            user_id="backfill-user",
            name="启用提示词",
            task="shot_video",
            content="ACTIVE",
            version=3,
            is_active=True,
        ),
        PromptSkill(
            id="inactive-prompt",
            user_id="backfill-user",
            name="停用提示词",
            task="shot_video",
            content="INACTIVE",
            version=2,
            is_active=False,
        ),
    ])
    await db_session.commit()

    first = await backfill_model_center(
        db_session,
        apply=True,
        user_id="backfill-user",
    )
    skills = list((await db_session.scalars(select(PromptSkill))).all())
    versions = {
        row.id: row
        for row in (await db_session.scalars(select(PromptProfileVersion))).all()
    }
    second = await backfill_model_center(
        db_session,
        apply=True,
        user_id="backfill-user",
    )

    assert first.prompt_profiles_created == 2
    assert first.prompt_versions_created == 2
    assert first.updated_total == 2
    assert {versions[skill.prompt_profile_version_id].status for skill in skills} == {
        "published",
        "disabled",
    }
    assert second.created_total == 0
    assert second.updated_total == 0


@pytest.mark.asyncio
async def test_backfill_reuses_manual_profile_with_the_same_provider_and_profile_key(
    db_session: AsyncSession,
) -> None:
    from app.features.model_config import backfill
    from app.features.model_config.backfill import backfill_model_center

    legacy = await _seed_legacy_catalog(db_session)
    model = await db_session.get(LLMModel, legacy.model_id)
    provider = await db_session.get(LLMProvider, model.provider_id)
    capabilities = sorted(backfill.normalize_capabilities(model.model_type, model.capabilities or []))
    canonical_provider_id = backfill._canonical_id("provider", provider.id)
    profile_key = backfill._profile_key(provider, model, capabilities)
    db_session.add_all([
        ModelProvider(
            id=canonical_provider_id, code=backfill._provider_code(provider), display_name="manual",
            provider_family="manual", enabled=True,
        ),
        ModelProfile(
            id="manual-profile-id", provider_id=canonical_provider_id, profile_key=profile_key,
            display_name="manual", enabled=True,
        ),
    ])
    await db_session.commit()

    report = await backfill_model_center(db_session, apply=True)
    profiles = list((await db_session.scalars(select(ModelProfile))).all())

    assert report.profiles_created == 0
    assert [profile.id for profile in profiles] == ["manual-profile-id"]


@pytest.mark.asyncio
async def test_backfill_reuses_equivalent_manual_profile_version(
    db_session: AsyncSession,
) -> None:
    from app.features.model_config import backfill
    from app.features.model_config.backfill import backfill_model_center
    from app.features.model_drivers.public import select_llm_connection_driver_key

    legacy = await _seed_legacy_catalog(db_session)
    model = await db_session.get(LLMModel, legacy.model_id)
    provider = await db_session.get(LLMProvider, model.provider_id)
    capabilities = sorted(backfill.normalize_capabilities(model.model_type, model.capabilities or []))
    canonical_provider_id = backfill._canonical_id("provider", provider.id)
    profile_key = backfill._profile_key(provider, model, capabilities)
    limits = {"context_window": model.context_window, "max_tokens": model.max_tokens}
    pricing = {"input_cost_per_1k": model.input_cost_per_1k, "output_cost_per_1k": model.output_cost_per_1k}
    db_session.add_all([
        ModelProvider(id=canonical_provider_id, code=backfill._provider_code(provider), display_name="manual", provider_family="manual", enabled=True),
        ModelProfile(id="manual-profile", provider_id=canonical_provider_id, profile_key=profile_key, display_name="manual", enabled=True),
        ModelProfileVersion(
            id="manual-version", model_id="manual-profile", version=1, api_model_id=model.model_id,
            driver_key=select_llm_connection_driver_key(provider.name, model.model_type), capabilities=capabilities,
            input_contract={}, output_contract={}, parameter_schema={}, default_params={}, limits=limits,
            pricing=pricing, prompt_profile_key=None, contract_version="legacy-backfill-v1",
            status="published", checksum="manual-equivalent",
        ),
    ])
    await db_session.commit()

    report = await backfill_model_center(db_session, apply=True)
    binding = await db_session.scalar(select(ModelBinding))

    assert report.profile_versions_created == 0
    assert binding.profile_version_id == "manual-version"
