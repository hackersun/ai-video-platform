import pytest
from pathlib import Path

from app.core.deepseek_catalog import DEEPSEEK_MODEL_SEEDS, DEEPSEEK_PROVIDER
from app.models.llm_config import LLMModel, LLMProvider
from app.models.model_center import ModelProfile, ModelProfileVersion, ModelProvider
from tests.model_binding_test_support import db_session as db_session


def test_deepseek_provider_uses_official_openai_compatible_endpoint() -> None:
    assert DEEPSEEK_PROVIDER["id"] == "deepseek"
    assert DEEPSEEK_PROVIDER["name"] == "deepseek"
    assert DEEPSEEK_PROVIDER["base_url"] == "https://api.deepseek.com"
    assert DEEPSEEK_PROVIDER["auth_type"] == "bearer"


def test_deepseek_catalog_contains_only_current_v4_api_model_ids() -> None:
    model_ids = {model["model_id"] for model in DEEPSEEK_MODEL_SEEDS}

    assert model_ids == {"deepseek-v4-flash", "deepseek-v4-pro"}
    assert "deepseek-chat" not in model_ids
    assert "deepseek-reasoner" not in model_ids


def test_deepseek_v4_models_are_publishable_text_generation_profiles() -> None:
    for model in DEEPSEEK_MODEL_SEEDS:
        assert model["provider_id"] == "deepseek"
        assert model["model_type"] == "chat"
        assert {"chat", "completion", "reasoning", "json_mode"}.issubset(model["capabilities"])
        assert model["context_window"] == 1_000_000
        assert model["max_tokens"] == 384_000
        assert model["supports_streaming"] is True
        assert model["supports_function_calling"] is True


def test_legacy_and_runtime_catalogs_include_deepseek_official_rows() -> None:
    from app.api.v1.endpoints.llm_config import DEFAULT_MODELS, DEFAULT_PROVIDERS

    assert any(provider["id"] == "deepseek" for provider in DEFAULT_PROVIDERS)
    assert {
        model["model_id"] for model in DEFAULT_MODELS if model["provider_id"] == "deepseek"
    } == {"deepseek-v4-flash", "deepseek-v4-pro"}


def test_production_bootstrap_projects_text_and_media_providers_into_model_center() -> None:
    source = Path("bootstrap_production.py").read_text(encoding="utf-8")

    assert "backfill_provider_catalog" in source
    assert 'provider_ids={"deepseek", "minimax", "volcano"}' in source


def test_legacy_seed_skips_an_existing_internal_model_id(monkeypatch) -> None:
    """A renamed provider API id must not duplicate the stable catalog row id."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    import init_llm_config
    from app.core.database import Base

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(LLMModel(
            id="volcano-seedance-1-0-pro-fast", provider_id="volcano",
            model_id="Doubao-Seedance-1.0-pro-fast", model_name="legacy Seedance",
            model_type="video", capabilities=["text-to-video"], is_active=True,
        ))
        session.commit()

    monkeypatch.setattr(init_llm_config, "sync_engine", engine)
    init_llm_config.init_llm_providers_and_models()

    with Session(engine) as session:
        rows = session.query(LLMModel).filter_by(id="volcano-seedance-1-0-pro-fast").all()
        assert len(rows) == 1
        assert rows[0].model_id == "Doubao-Seedance-1.0-pro-fast"


@pytest.mark.asyncio
async def test_deepseek_catalog_projection_is_additive_and_idempotent(db_session) -> None:
    from sqlalchemy import select

    from app.features.model_config.shared_catalog_projection import backfill_provider_catalog

    db_session.add(LLMProvider(**DEEPSEEK_PROVIDER))
    db_session.add_all(LLMModel(**model) for model in DEEPSEEK_MODEL_SEEDS)
    await db_session.flush()

    first = await backfill_provider_catalog(db_session, provider_ids={"deepseek"})
    second = await backfill_provider_catalog(db_session, provider_ids={"deepseek"})

    providers = list((await db_session.scalars(select(ModelProvider))).all())
    profiles = list((await db_session.scalars(select(ModelProfile))).all())
    versions = list((await db_session.scalars(select(ModelProfileVersion))).all())
    assert first.providers_created == 1
    assert first.profiles_created == 2
    assert first.profile_versions_created == 2
    assert second.created_total == 0
    assert [provider.code for provider in providers] == ["deepseek"]
    assert {profile.display_name for profile in profiles} == {"DeepSeek V4 Flash", "DeepSeek V4 Pro"}
    assert {version.api_model_id for version in versions} == {"deepseek-v4-flash", "deepseek-v4-pro"}
    assert {version.driver_key for version in versions} == {"legacy_text_v1"}
