from types import SimpleNamespace

import pytest

from app.features.workflow_media.application import generate_separate_media
from app.features.workflow_media.errors import WorkflowMediaError


@pytest.mark.asyncio
async def test_tts_rejection_prevents_video_submission(monkeypatch: pytest.MonkeyPatch) -> None:
    shot = SimpleNamespace(id="shot-1")
    context = SimpleNamespace(shots=[shot])
    request = SimpleNamespace()
    preparation = SimpleNamespace(
        selected_video_model={}, video_reference_limits={}, selected_video_model_id="video-model",
        selected_video_provider="volcano", video_api_key="video-key", use_dev_video=False,
        prepared_shots={
            shot.id: {
                "video_request": {}, "lineage": {}, "package": {}, "reference_package": {},
                "final_video_prompt": "prompt", "effective_image_url": "https://example.invalid/ref.png",
                "video_seed": 1, "audio_route": {}, "dialogue_sync_contract": {},
                "video_preflight_package": {}, "subtitle_text": "对白", "duration": 4.0,
            }
        },
        final_quality_snapshots={},
    )
    video_calls = 0

    async def prepare(_command):
        return preparation

    async def submit_video(_command):
        nonlocal video_calls
        video_calls += 1
        return SimpleNamespace(
            video_job=SimpleNamespace(extra_data={}), sync_succeeded_video=False,
        )

    async def reject_tts(_command):
        raise WorkflowMediaError(422, {"code": "tts_provider_rejected"})

    async def start_record(_session, _record):
        return None

    monkeypatch.setattr(generate_separate_media, "prepare_separate_media", prepare)
    monkeypatch.setattr(generate_separate_media, "submit_video", submit_video)
    monkeypatch.setattr(generate_separate_media, "submit_tts_for_shot", reject_tts)
    monkeypatch.setattr(generate_separate_media, "begin_separate_persist", lambda _command: object())
    monkeypatch.setattr(generate_separate_media, "start_separate_media_record", start_record)

    with pytest.raises(WorkflowMediaError) as caught:
        await generate_separate_media.generate_separate_media_batch(context, request)

    assert caught.value.detail == {"code": "tts_provider_rejected"}
    assert video_calls == 0


@pytest.mark.asyncio
async def test_native_audio_skips_separate_tts_submission(monkeypatch: pytest.MonkeyPatch) -> None:
    shot = SimpleNamespace(id="shot-1")
    context = SimpleNamespace(shots=[shot])
    request = SimpleNamespace(native_audio=True)
    preparation = SimpleNamespace(
        selected_video_model={}, video_reference_limits={}, selected_video_model_id="video-model",
        selected_video_provider="volcano", video_api_key="video-key", use_dev_video=False,
        prepared_shots={
            shot.id: {
                "video_request": {}, "lineage": {}, "package": {}, "reference_package": {},
                "final_video_prompt": "prompt", "effective_image_url": "https://example.invalid/ref.png",
                "video_seed": 1, "audio_route": {"route": "video_native_audio"},
                "dialogue_sync_contract": {"video_native_audio": True},
                "video_preflight_package": {}, "subtitle_text": "对白", "duration": 4.0,
            }
        },
        final_quality_snapshots={},
    )
    calls = {"tts": 0, "video": 0}

    async def prepare(_command):
        return preparation

    async def submit_video(_command):
        calls["video"] += 1
        return SimpleNamespace(
            video_job=SimpleNamespace(extra_data={}), sync_succeeded_video=False,
        )

    async def submit_tts(_command):
        calls["tts"] += 1
        raise AssertionError("native audio must not submit a separate TTS job")

    session = SimpleNamespace(tts_voice_lock_count=0)
    monkeypatch.setattr(generate_separate_media, "prepare_separate_media", prepare)
    monkeypatch.setattr(generate_separate_media, "submit_video", submit_video)
    monkeypatch.setattr(generate_separate_media, "submit_tts_for_shot", submit_tts)
    monkeypatch.setattr(generate_separate_media, "begin_separate_persist", lambda _command: session)
    monkeypatch.setattr(generate_separate_media, "start_separate_media_record", lambda *_args: _async_none())
    monkeypatch.setattr(generate_separate_media, "finish_separate_media_record", lambda *_args: None)
    monkeypatch.setattr(generate_separate_media, "finish_separate_persist", lambda *_args: _async_value("done"))

    result = await generate_separate_media.generate_separate_media_batch(context, request)

    assert result == "done"
    assert calls == {"tts": 0, "video": 1}


async def _async_none():
    return None


async def _async_value(value):
    return value
