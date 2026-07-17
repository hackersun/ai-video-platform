from __future__ import annotations

from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.time_utils import utc_now
from app.features.model_config.public import (
    ModelBindingError,
    resolve_model_binding,
    resolve_retry_binding,
    route_policy_for,
)
from app.models.llm_config import LLMConfig, LLMModel, LLMProvider
from app.models.model_center import (
    ModelBinding,
    ModelConnection,
    ModelProfile,
    ModelProfileVersion,
    ModelProvider,
)


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


async def _seed_profile(
    db: AsyncSession,
    key: str,
    *,
    capabilities: tuple[str, ...] = ("video_generation",),
    profile_status: str = "published",
    connection_status: str = "connection_verified",
) -> tuple[ModelProfileVersion, ModelConnection]:
    provider_id = f"provider-{key}"
    model_id = f"model-{key}"
    version = ModelProfileVersion(
        id=f"profile-{key}",
        model_id=model_id,
        version=1,
        api_model_id=f"api-{key}",
        driver_key=f"driver-{key}",
        capabilities=list(capabilities),
        input_contract={},
        output_contract={},
        parameter_schema={},
        default_params={},
        limits={},
        pricing={},
        contract_version="v1",
        status=profile_status,
        checksum=(key[0] if key else "a") * 64,
    )
    connection = ModelConnection(
        id=f"connection-{key}",
        user_id="user-1",
        provider_id=provider_id,
        name=f"connection-{key}",
        status=connection_status,
        tested_at=utc_now(),
    )
    db.add_all(
        [
            ModelProvider(
                id=provider_id,
                code=provider_id,
                display_name=provider_id,
                provider_family="test",
                enabled=True,
            ),
            ModelProfile(
                id=model_id,
                provider_id=provider_id,
                profile_key=key,
                display_name=key,
                enabled=True,
            ),
            version,
            connection,
        ]
    )
    await db.flush()
    return version, connection


def _binding(
    key: str,
    profile: ModelProfileVersion,
    connection: ModelConnection,
    *,
    scope_type: str,
    scope_id: str,
    priority: int = 100,
    version: int = 1,
    route_policy: str = "single",
    fallbacks: list[str] | None = None,
) -> ModelBinding:
    return ModelBinding(
        id=f"binding-{key}",
        user_id="user-1",
        scope_type=scope_type,
        scope_id=scope_id,
        task="shot_video",
        capability="video_generation",
        profile_version_id=profile.id,
        connection_id=connection.id,
        priority=priority,
        route_policy=route_policy,
        fallback_profile_version_ids=fallbacks or [],
        version=version,
        is_active=True,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("scopes", "explicit", "expected_scope"),
    [
        (("series", "project", "user", "system"), True, "request"),
        (("series", "project", "user", "system"), False, "series"),
        (("project", "user", "system"), False, "project"),
        (("user", "system"), False, "user"),
        (("system",), False, "system"),
    ],
)
async def test_binding_precedence_is_request_series_project_user_system(
    db_session: AsyncSession,
    scopes: tuple[str, ...],
    explicit: bool,
    expected_scope: str,
) -> None:
    seeded: dict[str, ModelProfileVersion] = {}
    scope_ids = {"series": "series-1", "project": "project-1", "user": "user-1", "system": ""}
    for scope in scopes:
        profile, connection = await _seed_profile(db_session, scope)
        seeded[scope] = profile
        db_session.add(_binding(scope, profile, connection, scope_type=scope, scope_id=scope_ids[scope]))
    request_profile, _ = await _seed_profile(db_session, "request")
    await db_session.commit()

    resolved = await resolve_model_binding(
        db_session,
        user_id="user-1",
        task="shot_video",
        capability="video_generation",
        explicit_profile_version_id=request_profile.id if explicit else None,
        project_id="project-1",
        series_id="series-1",
    )

    expected = request_profile if explicit else seeded[expected_scope]
    assert resolved.profile.profile_version_id == expected.id
    assert resolved.source_scope == expected_scope


async def _seed_legacy_config(db: AsyncSession, *, config_id: str = "legacy-config") -> LLMConfig:
    provider = LLMProvider(id="legacy-provider", name="legacy-provider", is_active=True)
    model = LLMModel(
        id="legacy-model",
        provider_id=provider.id,
        model_id="legacy-api-model",
        model_name="Legacy Video",
        model_type="video",
        capabilities=["text-to-video"],
        is_active=True,
    )
    config = LLMConfig(
        id=config_id,
        user_id="user-1",
        model_id=model.id,
        name="Legacy verified",
        is_active=True,
        is_default=True,
        test_status="success",
        tested_at=utc_now(),
    )
    db.add_all([provider, model, config])
    await db.commit()
    return config


@pytest.mark.asyncio
async def test_explicit_legacy_config_overrides_scoped_binding(db_session: AsyncSession) -> None:
    profile, connection = await _seed_profile(db_session, "scoped")
    db_session.add(_binding("scoped", profile, connection, scope_type="user", scope_id="user-1"))
    legacy = await _seed_legacy_config(db_session)

    resolved = await resolve_model_binding(
        db_session,
        user_id="user-1",
        task="shot_video",
        capability="video_generation",
        explicit_config_id=legacy.id,
    )

    assert resolved.source_scope == "request"
    assert resolved.connection_id == legacy.id
    assert resolved.profile.profile_version_id == "legacy:legacy-model"
    assert resolved.profile.api_model_id == "legacy-api-model"


@pytest.mark.asyncio
async def test_legacy_fallback_preserves_version_zero_contract(db_session: AsyncSession) -> None:
    legacy = await _seed_legacy_config(db_session)

    resolved = await resolve_model_binding(
        db_session,
        user_id="user-1",
        task="shot_video",
        capability="video_generation",
    )

    assert resolved.task == "shot_video"
    assert resolved.capability == "video_generation"
    assert resolved.source_scope == "legacy"
    assert resolved.binding_version == 0
    assert resolved.connection_id == legacy.id
    assert resolved.profile.api_model_id == "legacy-api-model"


@pytest.mark.asyncio
async def test_binding_with_wrong_profile_capability_fails_closed(db_session: AsyncSession) -> None:
    profile, connection = await _seed_profile(db_session, "speech", capabilities=("speech_generation",))
    db_session.add(_binding("wrong-capability", profile, connection, scope_type="user", scope_id="user-1"))
    await db_session.commit()

    with pytest.raises(ModelBindingError, match="capability_mismatch"):
        await resolve_model_binding(
            db_session, user_id="user-1", task="shot_video", capability="video_generation"
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["draft", "disabled"])
async def test_unverified_or_disabled_connection_fails_closed(
    db_session: AsyncSession, status: str
) -> None:
    profile, connection = await _seed_profile(db_session, status, connection_status=status)
    db_session.add(_binding(status, profile, connection, scope_type="user", scope_id="user-1"))
    await db_session.commit()

    with pytest.raises(ModelBindingError, match="connection_not_verified"):
        await resolve_model_binding(
            db_session, user_id="user-1", task="shot_video", capability="video_generation"
        )


@pytest.mark.asyncio
async def test_binding_ties_use_priority_then_latest_version_deterministically(
    db_session: AsyncSession,
) -> None:
    older, older_connection = await _seed_profile(db_session, "older")
    latest, latest_connection = await _seed_profile(db_session, "latest")
    lower_priority, lower_connection = await _seed_profile(db_session, "lower-priority")
    db_session.add_all(
        [
            _binding("older", older, older_connection, scope_type="user", scope_id="user-1", priority=10, version=1),
            _binding("latest", latest, latest_connection, scope_type="user", scope_id="", priority=10, version=2),
            _binding(
                "lower-priority", lower_priority, lower_connection,
                scope_type="user", scope_id="user-1", priority=20, version=9,
            ),
        ]
    )
    await db_session.commit()

    resolved = await resolve_model_binding(
        db_session, user_id="user-1", task="shot_video", capability="video_generation"
    )

    assert resolved.profile.profile_version_id == latest.id
    assert resolved.binding_version == 2


@pytest.mark.asyncio
async def test_system_binding_can_be_owned_by_the_system_scope(db_session: AsyncSession) -> None:
    profile, connection = await _seed_profile(db_session, "global-system")
    connection.user_id = "system"
    binding = _binding(
        "global-system", profile, connection, scope_type="system", scope_id=""
    )
    binding.user_id = "system"
    db_session.add(binding)
    await db_session.commit()

    resolved = await resolve_model_binding(
        db_session, user_id="user-1", task="shot_video", capability="video_generation"
    )

    assert resolved.source_scope == "system"
    assert resolved.connection_id == connection.id


def test_route_policy_allows_only_confirmed_pre_submit_fallback() -> None:
    assert route_policy_for("pre_submit_fallback") == {
        "allow_pre_submit_fallback": True,
        "allow_post_acceptance_fallback": False,
        "retry_policy": "confirmed_pre_acceptance_only",
    }
    assert route_policy_for("single")["retry_policy"] == "never"


@pytest.mark.asyncio
async def test_media_binding_does_not_auto_fallback_after_provider_acceptance(
    db_session: AsyncSession,
) -> None:
    primary, connection = await _seed_profile(db_session, "primary")
    fallback, _ = await _seed_profile(db_session, "fallback")
    binding = _binding(
        "retry",
        primary,
        connection,
        scope_type="user",
        scope_id="user-1",
        route_policy="pre_submit_fallback",
        fallbacks=[fallback.id],
    )
    db_session.add(binding)
    await db_session.commit()

    operation = SimpleNamespace(status="submitted", provider_task_id="provider-task-1")
    with pytest.raises(ModelBindingError, match="status_only"):
        await resolve_retry_binding(db_session, binding, operation)


@pytest.mark.asyncio
async def test_explicit_provider_acceptance_flag_requires_status_polling(
    db_session: AsyncSession,
) -> None:
    primary, connection = await _seed_profile(db_session, "accepted-primary")
    fallback, _ = await _seed_profile(db_session, "accepted-fallback")
    binding = _binding(
        "accepted",
        primary,
        connection,
        scope_type="user",
        scope_id="user-1",
        route_policy="pre_submit_fallback",
        fallbacks=[fallback.id],
    )
    db_session.add(binding)
    await db_session.commit()

    with pytest.raises(ModelBindingError, match="status_only"):
        await resolve_retry_binding(
            db_session, binding, {"status": "failed", "provider_accepted": True}
        )


@pytest.mark.asyncio
async def test_confirmed_pre_submit_failure_can_resolve_configured_fallback(
    db_session: AsyncSession,
) -> None:
    primary, connection = await _seed_profile(db_session, "pre-primary")
    fallback, _ = await _seed_profile(db_session, "pre-fallback")
    binding = _binding(
        "pre-retry",
        primary,
        connection,
        scope_type="user",
        scope_id="user-1",
        route_policy="pre_submit_fallback",
        fallbacks=[fallback.id],
    )
    db_session.add(binding)
    await db_session.commit()

    resolved = await resolve_retry_binding(
        db_session,
        binding,
        SimpleNamespace(status="pre_submit_failed", provider_task_id=None),
    )

    assert resolved.profile_version_id == fallback.id
