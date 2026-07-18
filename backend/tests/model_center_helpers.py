from contextlib import asynccontextmanager
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.db_migrations.runner import register_production_models
from app.models.model_center import ModelProfileVersion, ProductionRecipeVersion
from app.models.prompt_skill import PromptSkill


def create_model_center_engine(tmp_path, name: str):
    engine = create_engine(f"sqlite:///{tmp_path / name}")
    register_production_models()
    Base.metadata.create_all(engine)
    return engine


@asynccontextmanager
async def isolated_model_center_session(tmp_path):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / f'model-center-{uuid4()}.db'}"
    )
    register_production_models()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            yield session
    finally:
        await engine.dispose()


async def seed_prompt_skill(
    db,
    *,
    id: str,
    user_id: str,
    version: int,
    active: bool,
    content: str,
) -> PromptSkill:
    skill = PromptSkill(
        id=id,
        user_id=user_id,
        name=id,
        task="shot_video",
        content=content,
        version=version,
        is_active=active,
    )
    db.add(skill)
    await db.flush()
    return skill


def profile_version(**overrides) -> ModelProfileVersion:
    values = {
        "id": "profile-version-1", "model_id": "model-1", "version": 1,
        "api_model_id": "api-model-v1", "driver_key": "driver-1",
        "capabilities": ["video_generation"], "input_contract": {"prompt": "string"},
        "output_contract": {"video_url": "string"}, "parameter_schema": {},
        "default_params": {}, "limits": {}, "pricing": {},
        "prompt_profile_key": "video.default", "contract_version": "v1",
        "status": "draft", "checksum": "a" * 64,
    }
    values.update(overrides)
    return ModelProfileVersion(**values)


def recipe_version(**overrides) -> ProductionRecipeVersion:
    values = {
        "id": "recipe-version-1", "user_id": "user-1", "recipe_key": "anime.default",
        "name": "Anime Default", "version": 1, "status": "draft",
        "spec": {"stages": ["storyboard"]}, "checksum": "a" * 64,
    }
    values.update(overrides)
    return ProductionRecipeVersion(**values)
