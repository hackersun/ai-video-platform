"""A legacy reset must not leave model-center defaults overriding the next test."""
import pytest
from sqlalchemy import select
from tests.model_binding_test_support import db_session, make_binding, seed_profile
from tests.llm_config_cleanup import clear_user_model_configs
from app.models.llm_config import LLMConfig
from app.models.model_center import ModelBinding


@pytest.mark.asyncio
async def test_reset_removes_defaults_and_legacy_configs_but_preserves_other_scopes(db_session):
    db = db_session
    profile, connection = await seed_profile(db, "reset")
    own = make_binding("own", profile, connection, scope_type="user", scope_id="user-1")
    other = make_binding("other", profile, connection, scope_type="user", scope_id="user-2")
    other.user_id = "user-2"
    project = make_binding("project", profile, connection, scope_type="project", scope_id="project-1")
    db.add_all([own, other, project, LLMConfig(
        id="cleanup-legacy", user_id="user-1", model_id="unused", name="old",
    )])
    await db.commit()
    await clear_user_model_configs(db, "user-1")
    await db.commit()
    remaining = set((await db.scalars(select(ModelBinding.id))).all())
    assert remaining == {other.id, project.id}
    assert await db.scalar(select(LLMConfig.id)) is None
    # Repeated cleanup is harmless.
    await clear_user_model_configs(db, "user-1")
