from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.features.series_anchor_generation.schemas import ValidateLiveBindingsRequest
from app.services import series_run_orchestrator as orchestrator_module
from app.services.series_run_orchestrator import SeriesRunOrchestrator


def test_native_audio_binding_request_excludes_tts() -> None:
    request = ValidateLiveBindingsRequest(
        text="text-config",
        image="image-config",
        video="video-config",
        native_audio=True,
    )

    assert request.required_bindings() == {
        "image": "image-config",
        "video": "video-config",
    }


def test_native_audio_continuation_can_refresh_video_binding_only() -> None:
    request = ValidateLiveBindingsRequest(
        video="video-config",
        native_audio=True,
    )

    assert request.required_bindings() == {"video": "video-config"}


def test_separate_tts_binding_request_still_requires_tts() -> None:
    with pytest.raises(ValidationError):
        ValidateLiveBindingsRequest(
            image="image-config",
            video="video-config",
        )


@pytest.mark.asyncio
async def test_orchestrator_validates_only_requested_native_audio_bindings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    async def fake_validate(db, run, bindings, **constraints):
        observed.update(bindings=bindings, constraints=constraints)
        return {"image": {"config_id": bindings["image"]}}

    monkeypatch.setattr(
        orchestrator_module,
        "validate_required_model_bindings",
        fake_validate,
        raising=False,
    )

    result = await SeriesRunOrchestrator().validate_live_model_bindings(
        None,
        None,
        {"image": "image-config", "video": "video-config"},
        required_tested_at="required-at",
    )

    assert observed["bindings"] == {
        "image": "image-config",
        "video": "video-config",
    }
    assert observed["constraints"]["persist"] is True
    assert result == {"image": {"config_id": "image-config"}}


@pytest.mark.asyncio
async def test_media_continuation_validates_only_remaining_capabilities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}
    savepoint = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    db = SimpleNamespace(
        begin_nested=AsyncMock(return_value=savepoint),
        commit=AsyncMock(),
        rollback=AsyncMock(),
    )
    run = SimpleNamespace(
        id="run-1",
        user_id="user-1",
        status="anchor_ready",
        budget_policy={"live_canary": True},
        run_metadata={},
        gate_summary={},
        episodes=[],
    )

    async def ready_plan(db, run, *, native_audio):
        assert native_audio is True
        return {"required_capabilities": ["video"]}

    async def validate(db, run, *, required_capabilities):
        observed["required_capabilities"] = required_capabilities

    async def ready_media_preflight(db, run, *, native_audio):
        return {
            "ready": True,
            "input_snapshot": {},
            "snapshot_hash": "snapshot-1",
        }

    monkeypatch.setattr(orchestrator_module, "build_live_preflight_plan", ready_plan, raising=False)
    monkeypatch.setattr(orchestrator_module, "validate_persisted_model_bindings", validate)
    monkeypatch.setattr(orchestrator_module, "evaluate_media_preflight", ready_media_preflight)
    monkeypatch.setattr(orchestrator_module, "recover_provider_operations", AsyncMock())

    await SeriesRunOrchestrator().enter_media_running(db, run, native_audio=True)

    assert observed["required_capabilities"] == {"video"}
    assert run.status == "media_running"
