from types import SimpleNamespace

import pytest

from app.features.model_drivers import VideoCommand
from app.features.model_drivers.adapters.volcano_ark_video import VolcanoArkVideoDriver
from app.services.video_reference_adapter import build_video_provider_content


@pytest.mark.asyncio
async def test_volcano_video_driver_matches_production_multireference_submission(monkeypatch):
    captured = {}

    def fake_submit_ark_video_task(*, api_key, base_url, create_kwargs, client=None):
        captured.update(api_key=api_key, base_url=base_url, create_kwargs=create_kwargs, client=client)
        return SimpleNamespace(id="video-task-1")

    monkeypatch.setattr(
        "app.features.video_generation.adapters.ark.submit_ark_video_task",
        fake_submit_ark_video_task,
    )
    command = VideoCommand(
        prompt="多模态测试",
        reference_images=("https://cdn.example.com/a.png", "https://cdn.example.com/b.png"),
        reference_videos=("https://cdn.example.com/motion.mp4",),
        reference_audios=("https://cdn.example.com/voice.wav",),
        native_audio=True,
        dialogue_contract={"spoken_text": "你好", "speaker": "阿青"},
        params={"duration": 8, "resolution": "1080p", "seed": 42},
    )
    limits = {"images": 2, "videos": 1, "audios": 1}
    context = SimpleNamespace(
        api_key="not-a-real-key", base_url="https://ark.example.test/api/v3",
        profile=SimpleNamespace(
            api_model_id="doubao-seedance-2-0-260128", provider_id="volcano", limits=limits,
        ),
    )

    submission = await VolcanoArkVideoDriver().submit(command, context)

    reference_package = {
        "images": [{"url": url} for url in command.reference_images],
        "videos": [{"url": url} for url in command.reference_videos],
        "audios": [{"url": url} for url in command.reference_audios],
    }
    production_content = build_video_provider_content(
        final_prompt=command.prompt, duration=8, resolution="1080p",
        reference_package=reference_package, model_limits=limits,
        model_id=context.profile.api_model_id, provider="volcano",
    )
    create_kwargs = captured["create_kwargs"]
    assert create_kwargs["content"] == production_content["content"]
    assert [item["type"] for item in create_kwargs["content"]] == [
        "image_url", "image_url", "video_url", "audio_url", "text",
    ]
    assert create_kwargs["generate_audio"] is True
    assert create_kwargs["seed"] == 42
    assert submission.status == "accepted"
    assert submission.provider_task_id == "video-task-1"
    assert submission.output["dialogue_contract"] == command.dialogue_contract
