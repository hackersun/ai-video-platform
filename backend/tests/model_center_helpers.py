from sqlalchemy import create_engine

from app.core.database import Base
from app.db_migrations.runner import register_production_models
from app.models.model_center import ModelProfileVersion, ProductionRecipeVersion


def create_model_center_engine(tmp_path, name: str):
    engine = create_engine(f"sqlite:///{tmp_path / name}")
    register_production_models()
    Base.metadata.create_all(engine)
    return engine


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
