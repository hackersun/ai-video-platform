from __future__ import annotations

from dataclasses import replace
import inspect
from pathlib import Path

import pytest

from app.features.model_config import bindings as binding_module
from app.features.model_config.public import RecipeBindingContract, validate_recipe


def recipe_spec(*, audio_mode: str, subtitle_source: str) -> dict[str, object]:
    return {
        "video": {"binding_id": "video", "required": True},
        "audio": {"mode": audio_mode},
        "subtitle": {"source": subtitle_source},
        "render": {"binding_id": "render", "required": True},
        "storage": {"binding_id": "storage", "required": True},
    }


def binding(stage: str, *, scope_type: str = "user", scope_id: str = "user-1") -> RecipeBindingContract:
    task, capability = {
        "video": ("shot_video", "video_generation"),
        "render": ("workflow_render", "media_render"),
        "storage": ("workflow_storage", "object_storage"),
    }[stage]
    capabilities = {capability}
    if stage == "video":
        capabilities.add("native_audio")
    return RecipeBindingContract(
        binding_id=stage,
        owner_id="user-1",
        scope_type=scope_type,
        scope_id=scope_id,
        task=task,
        capability=capability,
        is_active=True,
        profile_status="published",
        profile_capabilities=frozenset(capabilities),
        model_enabled=True,
        provider_enabled=True,
        connection_status="connection_verified",
        connection_owner_id="user-1",
        connection_matches_profile=True,
    )


def valid_bindings() -> dict[str, RecipeBindingContract]:
    return {stage: binding(stage) for stage in ("video", "render", "storage")}


@pytest.mark.parametrize(
    ("stage", "changes"),
    [
        ("video", {"scope_id": "user-2"}),
        ("storage", {"scope_type": "system", "scope_id": ""}),
        ("render", {"scope_type": "system", "scope_id": "not-empty"}),
    ],
)
def test_recipe_rejects_binding_scopes_that_task8_would_not_trust(
    stage: str, changes: dict[str, str],
) -> None:
    bindings = valid_bindings()
    bindings[stage] = binding(stage, **changes)

    errors = validate_recipe(
        recipe_spec(audio_mode="video_native_audio", subtitle_source="video_dialogue_timeline"),
        bindings,
        user_id="user-1",
    )

    assert {(error.code, error.stage) for error in errors} == {
        ("binding_scope_invalid", stage),
    }


def test_recipe_rejects_system_binding_without_the_empty_system_scope() -> None:
    bindings = valid_bindings()
    bindings["storage"] = replace(
        bindings["storage"],
        owner_id="system",
        scope_type="system",
        scope_id="other-system-scope",
        connection_owner_id="system",
    )

    errors = validate_recipe(
        recipe_spec(audio_mode="video_native_audio", subtitle_source="video_dialogue_timeline"),
        bindings,
        user_id="user-1",
    )

    assert {(error.code, error.stage) for error in errors} == {
        ("binding_scope_invalid", "storage"),
    }


@pytest.mark.parametrize(
    ("audio_mode", "subtitle_source"),
    [
        ("video_native_audio", "tts_timeline"),
        ("separate_tts", "video_dialogue_timeline"),
        ("video_native_audio", "script_dialogue"),
        ("separate_tts", "arbitrary"),
    ],
)
def test_recipe_rejects_subtitle_source_not_owned_by_audio_route(
    audio_mode: str, subtitle_source: str,
) -> None:
    errors = validate_recipe(
        recipe_spec(audio_mode=audio_mode, subtitle_source=subtitle_source),
        valid_bindings(),
        user_id="user-1",
    )

    expected = {("subtitle_source_invalid_for_audio_mode", "subtitle")}
    if audio_mode == "separate_tts":
        expected.add(("tts_binding_required", "audio"))
    assert {(error.code, error.stage) for error in errors} == expected


@pytest.mark.parametrize(
    ("audio_mode", "subtitle_source"),
    [
        ("video_native_audio", "video_dialogue_timeline"),
        ("separate_tts", "tts_timeline"),
    ],
)
def test_recipe_accepts_only_the_subtitle_source_owned_by_its_audio_route(
    audio_mode: str, subtitle_source: str,
) -> None:
    bindings = valid_bindings()
    spec = recipe_spec(audio_mode=audio_mode, subtitle_source=subtitle_source)
    if audio_mode == "separate_tts":
        spec["audio"] = {"mode": audio_mode, "binding_id": "audio"}
        bindings["audio"] = replace(
            binding("render"),
            binding_id="audio",
            task="shot_speech",
            capability="speech_generation",
            profile_capabilities=frozenset({"speech_generation"}),
        )

    assert validate_recipe(spec, bindings, user_id="user-1") == []


def test_recipe_scope_safety_is_shared_with_task8_resolution() -> None:
    assert "is_safe_model_binding_scope" in inspect.getsource(binding_module)


def test_recipe_accepts_task8_compatible_unscoped_user_binding() -> None:
    bindings = valid_bindings()
    bindings["video"] = replace(bindings["video"], scope_id="")

    assert validate_recipe(
        recipe_spec(
            audio_mode="video_native_audio",
            subtitle_source="video_dialogue_timeline",
        ),
        bindings,
        user_id="user-1",
    ) == []


def test_recipe_version_application_does_not_construct_or_return_orm_models() -> None:
    source = Path("app/features/model_config/recipe_versions.py").read_text()

    assert "from app.models" not in source
    assert "ProductionRecipeVersion" not in source
    assert ".add(" not in source
