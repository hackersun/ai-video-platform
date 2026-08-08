from __future__ import annotations

import inspect
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import get_type_hints

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.features.model_config import bindings as binding_module
from app.features.model_config.public import (
    GenerationContext,
    ModelBindingError,
    resolve_generation_context,
    resolve_legacy_strategy_config_id,
    resolve_model_binding,
    resolve_retry_binding,
    route_policy_for,
)
from app.features.model_config.domain import ModelProfileContract, ResolvedModelBinding
from app.models.llm_config import LLMConfig, LLMModel, LLMProvider
from app.models.model_center import ModelProfileVersion
from tests.model_binding_test_support import (
    db_session as db_session,
    make_binding as _binding,
    seed_profile as _seed_profile,
)


@pytest.fixture(autouse=True)
def _canonical_binding_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_CENTER_READ_MODE", "canonical")


def test_workflow_media_resolves_driver_from_binding_not_provider_name() -> None:
    source = Path(
        "app/features/workflow_media/application/prepare_separate_media.py"
    ).read_text(encoding="utf-8")

    assert 'provider_id == "volcano"' not in source
    assert 'provider_id == "minimax"' not in source
    assert "resolve_generation_context" in source


def test_production_adapters_expose_binding_context_paths_and_keep_legacy_builders() -> None:
    video_source = Path(
        "app/features/video_generation/application/model_config.py"
    ).read_text(encoding="utf-8")
    image_source = Path("app/services/image_generation_pipeline.py").read_text(encoding="utf-8")
    text_source = Path("app/features/model_drivers/text_execution.py").read_text(encoding="utf-8")

    assert "resolve_generation_context" in video_source
    assert "generation_context" in image_source
    assert "execute_generation" in image_source
    assert "resolve_generation_context" in text_source
    assert "create_text_generation_service" in text_source


def test_text_generation_entrypoints_use_unified_service_resolution() -> None:
    paths = [
        "app/api/v1/endpoints/chapters.py",
        "app/api/v1/endpoints/characters.py",
        "app/api/v1/endpoints/coding_plan.py",
        "app/api/v1/endpoints/novels.py",
        "app/api/v1/endpoints/scripts.py",
        "app/api/v1/endpoints/story_bible.py",
        "app/api/v1/endpoints/storyboards.py",
        "app/services/prompt_skill_service.py",
    ]

    for path in paths:
        source = Path(path).read_text(encoding="utf-8")
        assert "get_user_text_model_config" not in source, path
        assert "get_user_text_generation_service" in source, path


def test_legacy_config_projection_exposes_model_center_text_default() -> None:
    from app.api.v1.endpoints.llm_config import canonical_text_default_config

    projected = canonical_text_default_config("user-1", [{
        "id": "project-binding", "scope_type": "project", "scope_id": "project-1",
        "task": "script_generation", "capability": "text_generation", "is_active": True,
        "profile_version_id": "wrong-profile", "api_model_id": "wrong-model",
        "profile_name": "Wrong", "connection_id": "wrong-connection",
        "provider_name": "Wrong", "certification_status": "success", "version": 9,
    }, {
        "id": "binding-1", "scope_type": "user", "scope_id": "user-1",
        "task": "script_generation", "capability": "text_generation",
        "is_active": True, "profile_version_id": "profile-v1", "api_model_id": "ark-code-latest",
        "profile_name": "Ark Code Latest", "connection_id": "connection-1",
        "provider_name": "火山方舟 Agent Plan", "certification_status": "success", "version": 2,
    }])

    assert projected is not None
    assert projected["id"] == ""
    assert projected["api_model_id"] == "ark-code-latest"
    assert projected["is_default"] is True
    assert projected["key_available"] is True


def test_text_catalog_limits_are_normalized_to_driver_command_contract() -> None:
    from app.features.model_config.generation_context import _runtime_execution_binding

    profile = ModelProfileContract(
        profile_version_id="text-v1", provider_id="volcano", api_model_id="ark-code-latest",
        driver_key="legacy_text_v1", capabilities=frozenset({"text_generation"}),
        input_contract={}, output_contract={}, parameter_schema={}, default_params={},
        limits={"context_window": 256000, "max_tokens": 4096}, pricing={},
        prompt_profile_key=None, contract_version="text.v1",
    )
    binding = ResolvedModelBinding(
        task="script_generation", capability="text_generation", profile=profile,
        connection_id="connection-1", binding_version=2, source_scope="user",
    )

    normalized = _runtime_execution_binding(binding)

    assert normalized.profile.limits == {"max_prompt_chars": 256000}


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
        binding = _binding(
            scope, profile, connection, scope_type=scope, scope_id=scope_ids[scope]
        )
        if scope == "system":
            binding.user_id = "system"
            connection.user_id = "system"
        db_session.add(binding)
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
async def test_generation_context_explicit_config_overrides_scoped_binding(
    db_session: AsyncSession,
) -> None:
    profile, connection = await _seed_profile(db_session, "scoped-context")
    db_session.add(_binding(
        "scoped-context", profile, connection, scope_type="user", scope_id="user-1",
    ))
    provider = LLMProvider(id="legacy-volcano-provider", name="volcano", is_active=True)
    model = LLMModel(
        id="legacy-volcano-video", provider_id=provider.id, model_id="legacy-video-api",
        model_name="Legacy Video", model_type="video", capabilities=["text-to-video"],
        is_active=True,
    )
    config = LLMConfig(
        id="explicit-video-config", user_id="user-1", model_id=model.id,
        name="Explicit verified video", is_active=True, is_default=False,
        test_status="success", tested_at=utc_now(),
    )
    config.set_api_key_encrypted("explicit-video-key")
    db_session.add_all([provider, model, config])
    await db_session.commit()

    context = await resolve_generation_context(
        db_session, user_id="user-1", stage="video", explicit_config_id=config.id,
    )

    assert isinstance(context, GenerationContext)
    assert context.binding.source_scope == "request"
    assert context.binding.binding_version == 0
    assert context.driver_context.driver_key == "volcano_ark_video_v3"
    assert context.driver_context.api_key == "explicit-video-key"
    assert context.profile.api_model_id == "legacy-video-api"


@pytest.mark.asyncio
async def test_generation_context_explicit_profile_selects_canonical_video_model(
    db_session: AsyncSession,
) -> None:
    profile, connection = await _seed_profile(db_session, "explicit-profile")
    connection.set_api_key_encrypted("explicit-profile-key")
    await db_session.commit()

    context = await resolve_generation_context(
        db_session,
        user_id="user-1",
        stage="video",
        explicit_profile_version_id=profile.id,
    )

    assert context.binding.source_scope == "request"
    assert context.profile.profile_version_id == profile.id
    assert context.driver_context.api_key == "explicit-profile-key"


@pytest.mark.asyncio
async def test_video_model_config_forwards_explicit_profile_selection(
    db_session: AsyncSession,
) -> None:
    from app.features.video_generation.application.model_config import resolve_video_model_config

    profile, connection = await _seed_profile(db_session, "video-profile-selection")
    connection.set_api_key_encrypted("selected-profile-key")
    await db_session.commit()

    resolved = await resolve_video_model_config(
        db_session,
        "user-1",
        profile.api_model_id,
        profile_version_id=profile.id,
    )

    assert resolved["config_model_id"] == profile.id
    assert resolved["api_model_id"] == profile.api_model_id
    assert resolved["api_key"] == "selected-profile-key"


@pytest.mark.asyncio
async def test_generation_context_uses_binding_driver_and_route_policy(
    db_session: AsyncSession,
) -> None:
    profile, connection = await _seed_profile(db_session, "bound-context")
    connection.set_api_key_encrypted("bound-video-key")
    binding = _binding(
        "bound-context", profile, connection, scope_type="user", scope_id="user-1",
        route_policy="pre_submit_fallback",
    )
    db_session.add(binding)
    await db_session.commit()

    context = await resolve_generation_context(
        db_session, user_id="user-1", stage="video",
    )

    assert context.binding.profile.driver_key == "driver-bound-context"
    assert context.driver_context.driver_key == "driver-bound-context"
    assert context.driver_context.api_key == "bound-video-key"
    assert context.route_policy == route_policy_for("pre_submit_fallback")


@pytest.mark.asyncio
async def test_recipe_stage_binding_preflight_rejects_wrong_task(
    db_session: AsyncSession,
) -> None:
    profile, connection = await _seed_profile(db_session, "recipe-video")
    binding = _binding(
        "recipe-video", profile, connection, scope_type="user", scope_id="user-1",
    )
    db_session.add(binding)
    await db_session.commit()

    with pytest.raises(ModelBindingError, match="binding_task_mismatch"):
        await resolve_generation_context(
            db_session,
            user_id="user-1",
            stage="audio",
            recipe_spec={"audio": {"binding_id": binding.id}},
        )


@pytest.mark.asyncio
async def test_binding_driven_minimax_image_keeps_legacy_prompt_compaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.image_generation_pipeline import call_image_generation_provider

    captured = {}

    async def execute(_registry, command, _context):
        captured["prompt"] = command.prompt
        return SimpleNamespace(output={"image_urls": ["https://example.test/image.png"]}, provider_task_id=None)

    monkeypatch.setattr("app.features.model_drivers.public.execute_generation", execute)
    context = SimpleNamespace(
        profile=SimpleNamespace(default_params={}),
        driver_context=SimpleNamespace(driver_key="minimax_image_v1"),
    )
    prompt = "角色姓名：林青岚\n" + "剧情上下文：" + ("连续章节状态。" * 500)

    await call_image_generation_provider(
        object(), provider_name="volcano", model_id="ignored-by-binding",
        prompt=prompt, generation_context=context,
    )

    assert len(captured["prompt"]) < 1500
    assert "角色姓名：林青岚" in captured["prompt"]


@pytest.mark.asyncio
async def test_image_submitter_executes_selected_non_ark_driver_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import image_generation_pipeline

    context = SimpleNamespace(
        profile=SimpleNamespace(default_params={}),
        driver_context=SimpleNamespace(driver_key="minimax_image_v1"),
    )
    captured = {}

    async def resolve(*_args, **_kwargs):
        return context

    async def execute(_registry, command, driver):
        captured.update(command=command, driver=driver)
        return SimpleNamespace(output={"image_urls": ["https://example.test/image.png"]}, provider_task_id=None)

    monkeypatch.setattr(image_generation_pipeline, "resolve_generation_context", resolve)
    monkeypatch.setattr(image_generation_pipeline.driver_kernel, "execute_generation", execute)

    result = await image_generation_pipeline.call_image_generation_provider(
        object(), provider_name="volcano", model_id="ignored", prompt="driver selected",
        db=object(), user_id="user-1", config_id="image-config",
    )

    assert result["image_urls"] == ["https://example.test/image.png"]
    assert captured["driver"] is context.driver_context
    assert captured["command"].params["response_format"] == "base64"


@pytest.mark.asyncio
async def test_image_submitter_preserves_reference_image_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import image_generation_pipeline

    context = SimpleNamespace(
        profile=SimpleNamespace(default_params={}),
        driver_context=SimpleNamespace(driver_key="volcano_ark_image_v3"),
    )
    captured = {}

    async def execute(_registry, command, _driver):
        captured["command"] = command
        return SimpleNamespace(output={"image_urls": ["https://example.test/frame.png"]}, provider_task_id=None)

    monkeypatch.setattr(image_generation_pipeline.driver_kernel, "execute_generation", execute)
    await image_generation_pipeline.call_image_generation_provider(
        object(), provider_name="volcano", model_id="ignored", prompt="same character",
        generation_context=context,
        reference_images=["https://example.test/character-board.png"],
    )

    assert captured["command"].reference_images == ("https://example.test/character-board.png",)


@pytest.mark.asyncio
async def test_workflow_video_submitter_executes_selected_non_ark_driver_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.features.workflow_media.adapters import video_submission

    generation = SimpleNamespace(
        profile=SimpleNamespace(default_params={}),
        driver_context=SimpleNamespace(driver_key="non_ark_video_v1"),
    )
    command = SimpleNamespace(
        runtime=SimpleNamespace(selected_model={"generation_context": generation}),
        prepared=SimpleNamespace(
            video_request=SimpleNamespace(duration=4), video_seed=7,
            final_video_prompt="driver selected", dialogue_sync_contract=None,
        ),
        request=SimpleNamespace(resolution="720p", native_audio=False),
        context=SimpleNamespace(db=object(), series_run=object()),
    )
    captured = {}

    async def reserve(*_args, **_kwargs):
        return None

    async def execute(_registry, driver_command, driver_context):
        captured.update(command=driver_command, context=driver_context)
        return SimpleNamespace(provider_task_id="non-ark-task")

    monkeypatch.setattr(video_submission, "_reserve", reserve)
    monkeypatch.setattr(video_submission, "execute_generation", execute)
    monkeypatch.setattr(
        video_submission.video_kernel, "create_ark_client",
        lambda *_args: (_ for _ in ()).throw(AssertionError("Ark must not be selected")),
    )

    task_id, reservation, _content = await video_submission._submit_live(
        command, {}, {"content": [{"type": "text", "text": "driver selected"}]}, "job-1",
    )

    assert (task_id, reservation) == ("non-ark-task", None)
    assert captured["context"] is generation.driver_context
    assert captured["command"].params["seed"] == 7


@pytest.mark.asyncio
async def test_direct_video_submitter_executes_selected_non_ark_driver_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.features.video_generation.application import driver_submission

    generation = SimpleNamespace(
        profile=SimpleNamespace(default_params={}),
        driver_context=SimpleNamespace(driver_key="non_ark_video_v1"),
    )
    captured = {}

    async def execute(_registry, command, driver_context):
        captured.update(command=command, context=driver_context)
        return SimpleNamespace(provider_task_id="direct-non-ark-task")

    monkeypatch.setattr(driver_submission, "execute_generation", execute)

    result = await driver_submission.submit_bound_video_task(
        generation, "driver selected",
        {"content": [{"type": "text", "text": "driver selected"}], "duration": 4, "resolution": "720p"},
        object(),
    )

    assert result.id == "direct-non-ark-task"
    assert captured["context"] is generation.driver_context
    assert captured["command"].params == {"duration": 4, "resolution": "720p"}


@pytest.mark.asyncio
async def test_workflow_tts_submitter_executes_selected_non_ark_driver_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.features.workflow_media.adapters import tts_submission

    generation = SimpleNamespace(
        profile=SimpleNamespace(default_params={}),
        driver_context=SimpleNamespace(driver_key="non_ark_speech_v1"),
    )
    command = SimpleNamespace(
        preparation=SimpleNamespace(selected_audio_model={"generation_context": generation}),
    )
    captured = {}

    async def execute(_registry, speech, driver_context):
        captured.update(speech=speech, context=driver_context)
        return SimpleNamespace(output={"audio_url": "https://example.test/audio.mp3"}, provider_task_id=None)

    monkeypatch.setattr(tts_submission, "execute_generation", execute)

    result = await tts_submission._call_provider(command, "你好", "voice-1", 1.2)

    assert result["audio_url"] == "https://example.test/audio.mp3"
    assert captured["context"] is generation.driver_context
    assert captured["speech"].params == {"speed": 1.2}


def test_non_ark_bound_video_driver_is_supported_at_the_endpoint_gate() -> None:
    from app.features.video_generation.application.driver_submission import has_video_generation_driver

    context = SimpleNamespace(driver_context=SimpleNamespace(driver_key="dashscope_video_v1"))

    assert has_video_generation_driver(context) is True
    assert has_video_generation_driver(None) is False


@pytest.mark.asyncio
async def test_asset_generation_routes_through_binding_aware_image_submitter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import asset_generation_service

    service = asset_generation_service.AssetGenerationService(db=object(), user_id="asset-user")
    service.image_service = object()
    service.provider_name = "minimax"
    service.model_id = "image-01"
    service.image_model_config_id = "explicit-asset-image-config"
    captured = {}

    async def submit(_service, **kwargs):
        captured.update(kwargs)
        return {"image_urls": ["https://example.test/asset.png"]}

    async def persist(url, **_kwargs):
        return url

    monkeypatch.setattr(asset_generation_service, "call_image_generation_provider", submit)
    monkeypatch.setattr(asset_generation_service, "persist_remote_media_url", persist)

    assert await service._generate_asset_image_url(
        "asset prompt", size="2K", aspect_ratio="1:1", prefix="asset",
    ) == "https://example.test/asset.png"
    assert captured["db"] is service.db
    assert captured["user_id"] == "asset-user"
    assert captured["config_id"] == "explicit-asset-image-config"


@pytest.mark.asyncio
async def test_video_production_resolution_does_not_bypass_failed_binding_safety(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.features.video_generation.application import model_config

    async def fail_closed(*_args, **_kwargs):
        raise ModelBindingError("connection_not_verified")

    async def forbidden_legacy_fallback(*_args, **_kwargs):
        raise AssertionError("unsafe binding errors must not enter legacy fallback")

    monkeypatch.setattr(model_config, "resolve_generation_context", fail_closed)
    monkeypatch.setattr(model_config, "_legacy_video_model_config", forbidden_legacy_fallback)

    with pytest.raises(model_config.VideoGenerationError, match="connection_not_verified"):
        await model_config.resolve_video_model_config(object(), "user-1", None)


@pytest.mark.asyncio
async def test_unverified_legacy_video_keeps_preflight_envelope_without_runtime_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.features.video_generation.application import model_config

    async def fail_closed(*_args, **_kwargs):
        raise ModelBindingError("legacy_config_not_verified")

    async def forbidden_legacy_reload(*_args, **_kwargs):
        raise AssertionError("unverified configuration must not be reloaded for runtime")

    monkeypatch.setattr(model_config, "resolve_generation_context", fail_closed)
    monkeypatch.setattr(model_config, "_legacy_video_model_config", forbidden_legacy_reload)

    resolved = await model_config.resolve_video_model_config(object(), "user-1", "video-model", "pending-config")

    assert resolved["binding_resolution_error"] == "legacy_config_not_verified"
    assert resolved["model_config_id"] == "pending-config"
    assert resolved["api_key"] is None


@pytest.mark.asyncio
async def test_verified_legacy_video_context_is_not_reloaded_from_active_config(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.features.video_generation.application import model_config

    legacy = await _seed_legacy_config(db_session)
    context = await resolve_generation_context(
        db_session, user_id="user-1", stage="video", explicit_config_id=legacy.id,
    )

    async def resolve_context(*_args, **_kwargs):
        return context

    async def forbidden_legacy_reload(*_args, **_kwargs):
        raise AssertionError("a verified v0 context must be executed as resolved")

    monkeypatch.setattr(model_config, "resolve_generation_context", resolve_context)
    monkeypatch.setattr(model_config, "_legacy_video_model_config", forbidden_legacy_reload)

    resolved = await model_config.resolve_video_model_config(db_session, "user-1", None)

    assert resolved["generation_context"] is context
    assert resolved["model_config_id"] == legacy.id


@pytest.mark.asyncio
async def test_runtime_legacy_projection_requires_successful_connection_test(
    db_session: AsyncSession,
) -> None:
    from app.features.model_config.generation_context_repository import load_legacy_runtime_model

    config = await _seed_legacy_config(db_session, config_id="unverified-legacy")
    config.test_status = "pending"
    await db_session.commit()

    assert await load_legacy_runtime_model(
        db_session, user_id="user-1", config_id=config.id,
    ) is None


@pytest.mark.asyncio
async def test_explicit_tts_binding_error_never_projects_unverified_legacy_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.features.workflow_media.application import prepare_separate_media

    async def fail_closed(*_args, **_kwargs):
        raise ModelBindingError("legacy_config_not_verified")

    async def unsafe_projection(*_args, **_kwargs):
        raise AssertionError("unverified TTS configuration must not reach legacy projection")

    async def preflight_error(*_args, **_kwargs):
        return prepare_separate_media.WorkflowMediaError(422, "legacy_config_not_verified")

    monkeypatch.setattr(prepare_separate_media, "resolve_generation_context", fail_closed)
    monkeypatch.setattr(
        prepare_separate_media, "resolve_legacy_model_projection", unsafe_projection, raising=False,
    )
    monkeypatch.setattr(prepare_separate_media, "_legacy_binding_preflight_error", preflight_error)
    context = SimpleNamespace(db=object(), user_id="user-1")

    with pytest.raises(prepare_separate_media.WorkflowMediaError, match="legacy_config_not_verified"):
        await prepare_separate_media._resolve_saved_tts_model(context, "unverified-tts")


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
async def test_legacy_fallback_preserves_version_zero_contract(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_CENTER_READ_MODE", "legacy")
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
async def test_text_cutover_can_prefer_verified_canonical_binding_in_legacy_mode(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_CENTER_READ_MODE", "legacy")
    profile, connection = await _seed_profile(
        db_session, "preferred-text", capabilities=("text_generation",),
    )
    binding = _binding(
        "preferred-text", profile, connection, scope_type="user", scope_id="user-1",
    )
    binding.task = "script_generation"
    binding.capability = "text_generation"
    db_session.add(binding)
    await _seed_legacy_config(db_session)
    await db_session.commit()

    resolved = await resolve_model_binding(
        db_session,
        user_id="user-1",
        task="script_generation",
        capability="text_generation",
        prefer_canonical_binding=True,
    )

    assert resolved.source_scope == "user"
    assert resolved.profile.api_model_id == "api-preferred-text"


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


@pytest.mark.asyncio
async def test_tenant_owned_system_binding_cannot_override_trusted_system_binding(
    db_session: AsyncSession,
) -> None:
    trusted_profile, trusted_connection = await _seed_profile(db_session, "trusted-system")
    trusted_connection.user_id = "system"
    trusted_binding = _binding(
        "trusted-system",
        trusted_profile,
        trusted_connection,
        scope_type="system",
        scope_id="",
        priority=100,
    )
    trusted_binding.user_id = "system"

    attacker_profile, attacker_connection = await _seed_profile(db_session, "attacker-system")
    attacker_connection.user_id = "attacker-user"
    attacker_binding = _binding(
        "attacker-system",
        attacker_profile,
        attacker_connection,
        scope_type="system",
        scope_id="",
        priority=1,
    )
    attacker_binding.user_id = "attacker-user"
    db_session.add_all([trusted_binding, attacker_binding])
    await db_session.commit()

    resolved = await resolve_model_binding(
        db_session, user_id="victim-user", task="shot_video", capability="video_generation"
    )

    assert resolved.profile.profile_version_id == trusted_profile.id
    assert resolved.connection_id == trusted_connection.id


@pytest.mark.asyncio
async def test_legacy_strategy_preserves_nullable_updated_at_sql_ordering(
    db_session: AsyncSession,
) -> None:
    now = utc_now()
    provider = LLMProvider(id="strategy-provider", name="volcano", is_active=True)
    model = LLMModel(
        id="strategy-model",
        provider_id=provider.id,
        model_id="doubao-seedance-2-0-fast-260128",
        model_name="Strategy Video",
        model_type="video",
        capabilities=["text-to-video"],
        is_active=True,
    )
    nonnull_config = LLMConfig(
        id="nonnull-updated-config",
        user_id="user-1",
        model_id=model.id,
        name="nonnull updated",
        is_active=True,
        is_default=False,
        test_status="success",
        tested_at=now,
        created_at=now - timedelta(days=3),
        updated_at=now - timedelta(days=2),
    )
    null_config = LLMConfig(
        id="null-updated-config",
        user_id="user-1",
        model_id=model.id,
        name="null updated",
        is_active=True,
        is_default=False,
        test_status="success",
        tested_at=now,
        created_at=now,
        updated_at=now,
    )
    db_session.add_all([provider, model, nonnull_config, null_config])
    await db_session.flush()
    null_config.updated_at = None
    await db_session.commit()

    resolved = await resolve_legacy_strategy_config_id(
        db_session,
        user_id="user-1",
        binding_key="video.draft_fast",
        explicit_config_id=None,
    )

    assert resolved["model_config_id"] == nonnull_config.id


def test_bindings_module_does_not_own_orm_queries() -> None:
    source = inspect.getsource(binding_module)

    assert "db.get(" not in source
    assert "from app.models" not in source
    assert "import app.models" not in source


def test_retry_binding_annotations_are_resolvable() -> None:
    hints = get_type_hints(resolve_retry_binding)

    assert hints["operation"] is object


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
