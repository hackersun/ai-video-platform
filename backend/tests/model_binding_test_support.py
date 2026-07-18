from __future__ import annotations

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.time_utils import utc_now
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


async def seed_profile(
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


def make_binding(
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
