from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.model_center import ModelConfigAuditEvent
from app.models.llm_config import LLMConfig, LLMModel, LLMProvider
from tests.model_binding_test_support import make_binding, seed_profile


@pytest_asyncio.fixture()
async def db_session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


def test_read_mode_defaults_to_legacy_and_parses_explicit_shadow(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.features.model_config.settings import ModelCenterReadMode, model_center_read_mode

    monkeypatch.delenv("MODEL_CENTER_READ_MODE", raising=False)
    assert model_center_read_mode() is ModelCenterReadMode.LEGACY

    monkeypatch.setenv("MODEL_CENTER_READ_MODE", "shadow")
    assert model_center_read_mode() is ModelCenterReadMode.SHADOW


def test_shadow_difference_is_sanitized_and_blocks_high_severity_cutover() -> None:
    from app.features.model_config.shadow_compare import compare_resolutions

    comparison = compare_resolutions(
        legacy={
            "provider_id": "provider-a", "api_model_id": "legacy-video",
            "connection_id": "legacy-connection", "capability": "video_generation",
            "native_audio": False, "output_contract": {"video_url": "string"},
        },
        canonical={
            "provider_id": "provider-a", "api_model_id": "canonical-video",
            "connection_id": "canonical-connection", "capability": "video_generation",
            "native_audio": False, "output_contract": {"video_url": "string"},
        },
    )

    assert comparison.has_high_severity is True
    assert comparison.sanitized_dict()["high_severity_fields"] == ["api_model_id", "connection_id"]
    assert "legacy-connection" not in repr(comparison.sanitized_dict())


@pytest.mark.asyncio
async def test_shadow_audit_persists_only_sanitized_difference(
    db_session: AsyncSession,
) -> None:
    from app.features.model_config.shadow_compare import compare_resolutions, record_shadow_difference

    comparison = compare_resolutions(
        legacy={"connection_id": "legacy-secret-like-id"},
        canonical={"connection_id": "canonical-secret-like-id"},
    )
    event = await record_shadow_difference(
        db_session, user_id="shadow-user", resource_id="binding-1", comparison=comparison,
    )

    persisted = await db_session.get(ModelConfigAuditEvent, event.id)
    assert persisted is not None
    assert persisted.sanitized_change_summary == comparison.sanitized_dict()
    assert "secret-like" not in repr(persisted.sanitized_change_summary)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "expected_source", "audit_count"),
    [("legacy", "legacy", 0), ("shadow", "legacy", 1), ("canonical", "user", 0)],
)
async def test_read_mode_controls_real_binding_resolution(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    expected_source: str,
    audit_count: int,
) -> None:
    from app.core.time_utils import utc_now
    from app.features.model_config.bindings import resolve_model_binding

    profile, connection = await seed_profile(db_session, "mode-canonical")
    db_session.add(make_binding(
        "mode-canonical", profile, connection, scope_type="user", scope_id="user-1",
    ))
    provider = LLMProvider(id="legacy-mode-provider", name="volcano", is_active=True)
    model = LLMModel(
        id="legacy-mode-model", provider_id=provider.id, model_id="legacy-mode-video",
        model_name="Legacy mode video", model_type="video", capabilities=["text-to-video"],
        is_active=True,
    )
    config = LLMConfig(
        id="legacy-mode-config", user_id="user-1", model_id=model.id,
        name="legacy", is_active=True, is_default=True, test_status="success", tested_at=utc_now(),
    )
    db_session.add_all([provider, model, config])
    await db_session.commit()
    monkeypatch.setenv("MODEL_CENTER_READ_MODE", mode)

    resolved = await resolve_model_binding(
        db_session, user_id="user-1", task="shot_video", capability="video_generation",
    )

    assert resolved.source_scope == expected_source
    assert int(await db_session.scalar(select(func.count()).select_from(ModelConfigAuditEvent))) == audit_count


@pytest.mark.asyncio
async def test_shadow_mode_treats_backfilled_legacy_identity_as_equivalent(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.time_utils import utc_now
    from app.features.model_config.backfill import backfill_model_center
    from app.features.model_config.bindings import resolve_model_binding

    provider = LLMProvider(id="shadow-provider", name="volcano", is_active=True)
    model = LLMModel(
        id="shadow-model", provider_id=provider.id, model_id="shadow-video",
        model_name="Shadow Video", model_type="video", capabilities=["text-to-video"],
        is_active=True,
    )
    config = LLMConfig(
        id="shadow-config", user_id="shadow-user", model_id=model.id, name="shadow",
        is_active=True, is_default=True, test_status="success", tested_at=utc_now(),
    )
    db_session.add_all([provider, model, config])
    await db_session.commit()
    await backfill_model_center(db_session, apply=True, user_id=config.user_id)
    monkeypatch.setenv("MODEL_CENTER_READ_MODE", "shadow")

    resolved = await resolve_model_binding(
        db_session, user_id=config.user_id, task="shot_video", capability="video_generation",
    )

    assert resolved.source_scope == "legacy"
    assert int(await db_session.scalar(select(func.count()).select_from(ModelConfigAuditEvent))) == 0


@pytest.mark.asyncio
async def test_canonical_mode_never_falls_back_to_legacy(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.time_utils import utc_now
    from app.features.model_config.bindings import ModelBindingError, resolve_model_binding

    provider = LLMProvider(id="canonical-mode-provider", name="volcano", is_active=True)
    model = LLMModel(
        id="canonical-mode-model", provider_id=provider.id, model_id="canonical-mode-video",
        model_name="legacy only", model_type="video", capabilities=["text-to-video"], is_active=True,
    )
    config = LLMConfig(
        id="canonical-mode-config", user_id="canonical-mode-user", model_id=model.id,
        name="legacy", is_active=True, test_status="success", tested_at=utc_now(),
    )
    db_session.add_all([provider, model, config])
    await db_session.commit()
    monkeypatch.setenv("MODEL_CENTER_READ_MODE", "canonical")

    with pytest.raises(ModelBindingError, match="model_binding_not_found"):
        await resolve_model_binding(
            db_session, user_id=config.user_id, task="shot_video", capability="video_generation",
        )


@pytest.mark.asyncio
async def test_legacy_mode_uses_canonical_only_with_explicit_gate(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.features.model_config.bindings import ModelBindingError, resolve_model_binding

    profile, connection = await seed_profile(db_session, "legacy-gate")
    db_session.add(make_binding("legacy-gate", profile, connection, scope_type="user", scope_id="user-1"))
    await db_session.commit()
    monkeypatch.setenv("MODEL_CENTER_READ_MODE", "legacy")

    with pytest.raises(ModelBindingError, match="model_binding_not_found"):
        await resolve_model_binding(
            db_session, user_id="user-1", task="shot_video", capability="video_generation",
        )
    monkeypatch.setenv("MODEL_CENTER_LEGACY_CANONICAL_FALLBACK", "true")
    resolved = await resolve_model_binding(
        db_session, user_id="user-1", task="shot_video", capability="video_generation",
    )
    assert resolved.source_scope == "user"


@pytest.mark.asyncio
async def test_shadow_audit_failure_does_not_block_legacy_resolution(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.time_utils import utc_now
    from app.features.model_config import bindings

    profile, connection = await seed_profile(db_session, "audit-failure")
    db_session.add(make_binding("audit-failure", profile, connection, scope_type="user", scope_id="user-1"))
    provider = LLMProvider(id="audit-provider", name="volcano", is_active=True)
    model = LLMModel(
        id="audit-model", provider_id=provider.id, model_id="audit-video",
        model_name="legacy", model_type="video", capabilities=["text-to-video"], is_active=True,
    )
    config = LLMConfig(
        id="audit-config", user_id="user-1", model_id=model.id, name="legacy",
        is_active=True, test_status="success", tested_at=utc_now(),
    )
    db_session.add_all([provider, model, config])
    await db_session.commit()
    monkeypatch.setenv("MODEL_CENTER_READ_MODE", "shadow")

    async def fail_audit(*_args, **_kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(bindings, "record_shadow_difference", fail_audit)
    resolved = await bindings.resolve_model_binding(
        db_session, user_id="user-1", task="shot_video", capability="video_generation",
    )
    assert resolved.source_scope == "legacy"


@pytest.mark.asyncio
async def test_shadow_audit_integrity_error_keeps_session_usable(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.time_utils import utc_now
    from app.features.model_config import shadow_compare
    from app.features.model_config.bindings import resolve_model_binding

    profile, connection = await seed_profile(db_session, "audit-integrity")
    binding = make_binding("audit-integrity", profile, connection, scope_type="user", scope_id="user-1")
    provider = LLMProvider(id="audit-integrity-provider", name="volcano", is_active=True)
    model = LLMModel(
        id="audit-integrity-model", provider_id=provider.id, model_id="audit-integrity-video",
        model_name="legacy", model_type="video", capabilities=["text-to-video"], is_active=True,
    )
    config = LLMConfig(
        id="audit-integrity-config", user_id="user-1", model_id=model.id, name="legacy",
        is_active=True, test_status="success", tested_at=utc_now(),
    )
    db_session.add_all([binding, provider, model, config])
    await db_session.flush()
    duplicate_id = "audit-duplicate-id"
    db_session.add(ModelConfigAuditEvent(
        id=duplicate_id, user_id="user-1", resource_type="model_binding", resource_id=binding.id,
        action="shadow_difference", reason="existing", sanitized_change_summary={},
    ))
    await db_session.commit()
    monkeypatch.setenv("MODEL_CENTER_READ_MODE", "shadow")
    monkeypatch.setattr(shadow_compare, "uuid4", lambda: duplicate_id)

    resolved = await resolve_model_binding(
        db_session, user_id="user-1", task="shot_video", capability="video_generation",
    )

    assert resolved.source_scope == "legacy"
    assert await db_session.scalar(select(func.count()).select_from(ModelConfigAuditEvent)) == 1
