from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.db_migrations.model_center import add_model_center_links_async
from app.features.model_config import recipe_versions as recipe_version_service
from app.features.model_config.public import (
    RecipeBindingContract,
    RecipeValidationError,
    create_recipe_version,
    publish_recipe_version,
    stable_recipe_checksum,
    update_recipe_version,
    validate_recipe,
)
from app.models.model_center import (
    ModelBinding,
    ModelConnection,
    ModelProfile,
    ModelProfileVersion,
    ModelProvider,
    ProductionRecipeVersion,
)


TASKS = {
    "text": ("script_generation", "text_generation"),
    "vision": ("shot_vision", "vision_analysis"),
    "image": ("shot_image", "image_generation"),
    "video": ("shot_video", "video_generation"),
    "audio": ("shot_speech", "speech_generation"),
    "subtitle": ("shot_subtitle", "subtitle_generation"),
    "render": ("workflow_render", "media_render"),
    "storage": ("workflow_storage", "object_storage"),
}


def recipe_spec(
    *,
    audio_mode: str = "video_native_audio",
    tts_binding_id: str | None = None,
    subtitle_source: str | None = "video_dialogue_timeline",
    render_binding_id: str | None = "binding-render",
    storage_binding_id: str | None = "binding-storage",
) -> dict[str, Any]:
    return {
        "text": {"binding_id": "binding-text", "required": True, "params": {}},
        "vision": {"required": False, "params": {}},
        "image": {"binding_id": "binding-image", "required": True, "params": {}},
        "video": {"binding_id": "binding-video", "required": True, "params": {}},
        "audio": {"mode": audio_mode, "binding_id": tts_binding_id},
        "subtitle": {"source": subtitle_source},
        "render": {"binding_id": render_binding_id, "required": True, "params": {}},
        "storage": {"binding_id": storage_binding_id, "required": True, "params": {}},
    }


def binding_contract(
    stage: str,
    *,
    capabilities: frozenset[str] | None = None,
    **changes: Any,
) -> RecipeBindingContract:
    task, capability = TASKS[stage]
    values = {
        "binding_id": f"binding-{stage}",
        "owner_id": "user-1",
        "scope_type": "user",
        "scope_id": "user-1",
        "task": task,
        "capability": capability,
        "is_active": True,
        "profile_status": "published",
        "profile_capabilities": capabilities or frozenset({capability}),
        "model_enabled": True,
        "provider_enabled": True,
        "connection_status": "connection_verified",
        "connection_owner_id": "user-1",
        "connection_matches_profile": True,
    }
    values.update(changes)
    return RecipeBindingContract(**values)


def valid_bindings(*, native_audio: bool = True, separate_tts: bool = False):
    video_caps = {"video_generation"}
    if native_audio:
        video_caps.add("native_audio")
    stages = ("text", "image", "video", "render", "storage")
    bindings = {
        f"binding-{stage}": binding_contract(
            stage,
            capabilities=frozenset(video_caps) if stage == "video" else None,
        )
        for stage in stages
    }
    if separate_tts:
        bindings["binding-audio"] = binding_contract("audio")
    return bindings


def test_native_audio_recipe_requires_native_audio_video_and_forbids_tts() -> None:
    spec = recipe_spec(tts_binding_id="binding-audio")
    bindings = valid_bindings(native_audio=False)

    errors = validate_recipe(spec, bindings, user_id="user-1")

    assert {error.code for error in errors} == {
        "native_audio_capability_required",
        "tts_binding_forbidden_for_native_audio",
    }


def test_native_audio_recipe_can_validate_declared_video_capabilities() -> None:
    spec = recipe_spec(tts_binding_id="binding-audio")
    spec["video"]["capabilities"] = ["video_generation"]

    assert {error.code for error in validate_recipe(spec)} == {
        "native_audio_capability_required",
        "tts_binding_forbidden_for_native_audio",
    }


def test_separate_tts_recipe_requires_tts_subtitles_render_and_storage() -> None:
    spec = recipe_spec(
        audio_mode="separate_tts",
        tts_binding_id=None,
        subtitle_source=None,
        render_binding_id=None,
        storage_binding_id=None,
    )

    assert {error.code for error in validate_recipe(spec)} == {
        "tts_binding_required",
        "subtitle_source_required",
        "render_binding_required",
        "storage_binding_required",
    }


def test_every_referenced_binding_must_exist_and_match_stage_contract() -> None:
    spec = recipe_spec(
        audio_mode="separate_tts",
        tts_binding_id="binding-audio",
        subtitle_source="tts_timeline",
    )
    bindings = valid_bindings(native_audio=False, separate_tts=True)
    bindings.pop("binding-image")
    bindings["binding-video"] = replace(bindings["binding-video"], task="wrong_task")
    bindings["binding-audio"] = replace(
        bindings["binding-audio"], capability="video_generation"
    )

    errors = validate_recipe(spec, bindings, user_id="user-1")

    assert {(error.code, error.stage) for error in errors} == {
        ("binding_missing", "image"),
        ("binding_task_mismatch", "video"),
        ("binding_capability_mismatch", "audio"),
    }


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"is_active": False}, "binding_inactive"),
        ({"profile_status": "draft"}, "binding_profile_not_published"),
        ({"model_enabled": False}, "binding_owner_disabled"),
        ({"provider_enabled": False}, "binding_owner_disabled"),
        ({"connection_status": "draft"}, "binding_connection_not_verified"),
        ({"connection_owner_id": "user-2"}, "binding_owner_mismatch"),
        ({"connection_matches_profile": False}, "binding_connection_mismatch"),
    ],
)
def test_referenced_binding_status_and_ownership_fail_closed(
    changes: dict[str, Any], expected: str,
) -> None:
    spec = recipe_spec()
    bindings = valid_bindings()
    bindings["binding-video"] = replace(bindings["binding-video"], **changes)

    assert expected in {
        error.code for error in validate_recipe(spec, bindings, user_id="user-1")
    }


def test_trusted_system_binding_is_valid_for_tenant_recipe() -> None:
    spec = recipe_spec()
    bindings = valid_bindings()
    bindings["binding-storage"] = replace(
        bindings["binding-storage"],
        owner_id="system",
        scope_type="system",
        scope_id="",
        connection_owner_id="system",
    )

    assert validate_recipe(spec, bindings, user_id="user-1") == []


@pytest_asyncio.fixture()
async def db_session(tmp_path) -> AsyncSession:
    database_path = tmp_path / "production-recipes.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await add_model_center_links_async(engine)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def seed_binding(db: AsyncSession, stage: str, *, native_audio: bool = False) -> None:
    task, capability = TASKS[stage]
    provider_id = f"provider-{stage}"
    model_id = f"model-{stage}"
    profile_id = f"profile-{stage}"
    capabilities = [capability]
    if native_audio:
        capabilities.append("native_audio")
    db.add_all(
        [
            ModelProvider(
                id=provider_id,
                code=provider_id,
                display_name=stage,
                provider_family="test",
                enabled=True,
            ),
            ModelProfile(
                id=model_id,
                provider_id=provider_id,
                profile_key=stage,
                display_name=stage,
                enabled=True,
            ),
            ModelProfileVersion(
                id=profile_id,
                model_id=model_id,
                version=1,
                api_model_id=f"api-{stage}",
                driver_key=f"driver-{stage}",
                capabilities=capabilities,
                input_contract={},
                output_contract={},
                parameter_schema={},
                default_params={},
                limits={},
                pricing={},
                contract_version="v1",
                status="published",
                checksum=stage[0] * 64,
            ),
            ModelConnection(
                id=f"connection-{stage}",
                user_id="user-1",
                provider_id=provider_id,
                name=stage,
                status="connection_verified",
            ),
            ModelBinding(
                id=f"binding-{stage}",
                user_id="user-1",
                scope_type="user",
                scope_id="user-1",
                task=task,
                capability=capability,
                profile_version_id=profile_id,
                connection_id=f"connection-{stage}",
                version=1,
                is_active=True,
            ),
        ]
    )


async def seed_recipe_bindings(db: AsyncSession, *, separate_tts: bool = False) -> None:
    for stage in ("text", "image", "video", "render", "storage"):
        await seed_binding(db, stage, native_audio=stage == "video" and not separate_tts)
    if separate_tts:
        await seed_binding(db, "audio")
    await db.commit()


@pytest.mark.asyncio
async def test_create_recipe_rejects_blank_user_before_loading_bindings(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def binding_lookup_must_not_run(*args: object, **kwargs: object) -> None:
        raise AssertionError("blank user must fail before binding lookup")

    monkeypatch.setattr(
        recipe_version_service,
        "load_recipe_binding_contracts",
        binding_lookup_must_not_run,
    )

    with pytest.raises(ValueError, match="recipe_user_required"):
        await create_recipe_version(
            db_session,
            user_id="",
            recipe_key="anime.tenant-leak",
            name="Tenant Leak",
            spec=recipe_spec(),
        )


@pytest.mark.asyncio
async def test_draft_update_publish_and_next_version_are_deterministic(
    db_session: AsyncSession,
) -> None:
    await seed_recipe_bindings(db_session)
    spec = recipe_spec()

    draft = await create_recipe_version(
        db_session,
        user_id="user-1",
        recipe_key="anime.default",
        name="Anime Default",
        spec=spec,
    )
    assert (draft.version, draft.status, draft.checksum) == (
        1,
        "draft",
        stable_recipe_checksum(spec),
    )

    changed = {
        **spec,
        "subtitle": {"source": "video_dialogue_timeline", "language": "zh-CN"},
    }
    updated = await update_recipe_version(
        db_session, recipe_version_id=draft.id, user_id="user-1", spec=changed
    )
    assert updated.id == draft.id
    assert updated.checksum == stable_recipe_checksum(changed)

    published = await publish_recipe_version(
        db_session, recipe_version_id=draft.id, user_id="user-1"
    )
    original_checksum = published.checksum
    next_draft = await update_recipe_version(
        db_session,
        recipe_version_id=published.id,
        user_id="user-1",
        name="Anime Default v2",
        spec=spec,
    )

    persisted = await db_session.get(ProductionRecipeVersion, published.id)
    assert (persisted.status, persisted.checksum) == ("published", original_checksum)
    assert (next_draft.version, next_draft.status, next_draft.name) == (
        2,
        "draft",
        "Anime Default v2",
    )


def test_recipe_checksum_is_independent_of_mapping_order() -> None:
    first = {"video": {"params": {"resolution": "1080p", "duration": 5}}, "audio": {"mode": "separate_tts"}}
    second = {"audio": {"mode": "separate_tts"}, "video": {"params": {"duration": 5, "resolution": "1080p"}}}

    assert stable_recipe_checksum(first) == stable_recipe_checksum(second)


@pytest.mark.asyncio
async def test_publish_revalidates_current_binding_state(db_session: AsyncSession) -> None:
    await seed_recipe_bindings(db_session)
    draft = await create_recipe_version(
        db_session,
        user_id="user-1",
        recipe_key="anime.invalidated",
        name="Invalidated Recipe",
        spec=recipe_spec(),
    )
    binding = await db_session.get(ModelBinding, "binding-video")
    binding.is_active = False
    await db_session.commit()

    with pytest.raises(RecipeValidationError) as raised:
        await publish_recipe_version(
            db_session, recipe_version_id=draft.id, user_id="user-1"
        )

    assert {error.code for error in raised.value.errors} == {"binding_inactive"}


@pytest.mark.asyncio
async def test_published_recipe_rejects_orm_and_direct_sql_mutation(
    db_session: AsyncSession,
) -> None:
    await seed_recipe_bindings(db_session)
    draft = await create_recipe_version(
        db_session,
        user_id="user-1",
        recipe_key="anime.immutable",
        name="Immutable Recipe",
        spec=recipe_spec(),
    )
    published = await publish_recipe_version(
        db_session, recipe_version_id=draft.id, user_id="user-1"
    )
    await db_session.commit()
    published_id = published.id

    persisted = await db_session.get(ProductionRecipeVersion, published_id)
    persisted.name = "mutated through ORM"
    with pytest.raises(ValueError, match="published version is append-only"):
        await db_session.commit()
    await db_session.rollback()

    with pytest.raises(DBAPIError, match="published version is append-only"):
        await db_session.execute(
            update(ProductionRecipeVersion)
            .where(ProductionRecipeVersion.id == published_id)
            .values(name="mutated through SQL")
        )
    await db_session.rollback()
