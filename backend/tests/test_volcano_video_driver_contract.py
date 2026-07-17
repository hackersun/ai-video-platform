from types import SimpleNamespace

import pytest

from app.features.model_config import ModelProfileContract
from app.features.model_drivers import (
    DriverContext,
    DriverExecutionError,
    VideoCommand,
    build_builtin_driver_registry,
    execute_generation,
)
from app.features.video_generation.adapters.ark import build_ark_video_create_kwargs


def _context(*, model_id: str, limits: dict, parameter_schema: dict | None = None) -> DriverContext:
    profile = ModelProfileContract(
        profile_version_id=f"profile:{model_id}", provider_id="volcano",
        api_model_id=model_id, driver_key="volcano_ark_video_v3",
        capabilities=frozenset({"video_generation"}), input_contract={}, output_contract={},
        parameter_schema=parameter_schema or {}, default_params={}, limits=limits, pricing={},
        prompt_profile_key=None, contract_version="v1",
    )
    return DriverContext(
        profile, "volcano_ark_video_v3", "connection-1", {"api_key": "not-a-real-key"},
        base_url="https://ark.example.test/api/v3",
    )


@pytest.mark.asyncio
async def test_volcano_video_executor_preserves_canonical_multireferences(monkeypatch):
    captured = {}

    def fake_submit_ark_video_task(*, api_key, base_url, create_kwargs, client=None):
        captured.update(api_key=api_key, base_url=base_url, create_kwargs=create_kwargs, client=client)
        return SimpleNamespace(id="video-task-1")

    monkeypatch.setattr(
        "app.features.video_generation.public.submit_ark_video_task",
        fake_submit_ark_video_task,
    )
    command = VideoCommand(
        prompt="多模态测试",
        reference_images=("https://cdn.example.com/a.png", "https://cdn.example.com/b.png"),
        reference_videos=("https://cdn.example.com/motion.mp4",),
        reference_audios=("https://cdn.example.com/voice.wav",),
        dialogue_contract={"spoken_text": "你好", "speaker": "阿青"},
    )
    context = _context(
        model_id="doubao-seedance-2-0-260128",
        limits={
            "max_prompt_chars": 1000, "max_reference_images": 2,
            "max_reference_videos": 1, "max_reference_audios": 1,
        },
    )

    submission = await execute_generation(build_builtin_driver_registry(), command, context)

    create_kwargs = captured["create_kwargs"]
    assert [item["type"] for item in create_kwargs["content"]] == [
        "image_url", "image_url", "video_url", "audio_url", "text",
    ]
    assert "generate_audio" not in create_kwargs
    assert submission.status == "accepted"
    assert submission.provider_task_id == "video-task-1"
    assert submission.output["dialogue_contract"] == command.dialogue_contract


@pytest.mark.asyncio
async def test_volcano_video_executor_rejects_seedance_2_native_audio(monkeypatch):
    submitted = []

    def fake_submit_ark_video_task(**kwargs):
        submitted.append(kwargs)
        return SimpleNamespace(id="must-not-submit")

    monkeypatch.setattr(
        "app.features.video_generation.public.submit_ark_video_task",
        fake_submit_ark_video_task,
    )
    command = VideoCommand(prompt="不要启用原生音频", native_audio=True)
    context = _context(
        model_id="doubao-seedance-2-0-260128",
        limits={
            "max_prompt_chars": 1000, "max_reference_images": 0,
            "max_reference_videos": 0, "max_reference_audios": 0,
        },
    )

    with pytest.raises(DriverExecutionError) as caught:
        await execute_generation(build_builtin_driver_registry(), command, context)

    assert caught.value.sanitized_evidence["provider_error_type"] == "DriverResultError"
    assert submitted == []


@pytest.mark.asyncio
async def test_volcano_video_executor_keeps_seedance_15_native_audio(monkeypatch):
    submitted = []

    def fake_submit_ark_video_task(**kwargs):
        submitted.append(kwargs["create_kwargs"])
        return SimpleNamespace(id="native-audio-task")

    monkeypatch.setattr(
        "app.features.video_generation.public.submit_ark_video_task",
        fake_submit_ark_video_task,
    )
    context = _context(
        model_id="doubao-seedance-1-5-pro-251215",
        limits={
            "max_prompt_chars": 1000, "max_reference_images": 0,
            "max_reference_videos": 0, "max_reference_audios": 0,
        },
    )

    submission = await execute_generation(
        build_builtin_driver_registry(),
        VideoCommand(prompt="Seedance 1.5 原生音频", native_audio=True),
        context,
    )

    assert submission.provider_task_id == "native-audio-task"
    assert submitted[0]["generate_audio"] is True


def test_ark_video_kwargs_omit_false_native_audio_for_legacy_route():
    base = {
        "model": "doubao-seedance-1-0-pro-250528", "content": [],
        "duration": 4, "resolution": "720p", "camera_fixed": False, "watermark": False,
    }

    assert "generate_audio" not in build_ark_video_create_kwargs(**base)
    assert "generate_audio" not in build_ark_video_create_kwargs(**base, generate_audio=False)
    assert build_ark_video_create_kwargs(**base, generate_audio=True)["generate_audio"] is True
