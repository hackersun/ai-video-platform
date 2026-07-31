from types import SimpleNamespace

import pytest

from app.features.video_generation.schemas import VideoGenerateRequest
from app.features.video_generation.application.consistency_package import _prompt_skill_task
from app.features.series_anchor_generation.generation import _activate, _generation_groups, _generation_key
from app.features.workflow_media.adapters.video_submission import (
    PreparedVideoSubmission,
    VideoSubmissionCommand,
    VideoSubmissionRuntime,
    _build_extra_data,
    _build_job,
    _build_provider_content,
    _create_kwargs,
    _validate_seedance_first_frame,
)
from app.features.workflow_media.application.prepare_separate_media import (
    _append_dialogue_prompt,
    _dialogue_contract,
    _validate_dialogue,
)
from app.features.workflow_media.errors import WorkflowMediaError
from app.features.workflow_media.schemas import WorkflowMediaBatchRequest
from app.services.series_run_orchestrator import SeriesRunOrchestrator
from app.services.provider_prompt_safety import sanitize_provider_video_prompt


def _command(*, native_audio: bool = True, model_id: str = "doubao-seedance-1-5-pro-251215"):
    request = WorkflowMediaBatchRequest(
        strategy="separate_video_tts",
        native_audio=native_audio,
        audio_mode="model_audio",
        resolution="720p",
    )
    video_request = VideoGenerateRequest(
        prompt="沈砚在雾港开口说话",
        model=model_id,
        duration=4,
        resolution="720p",
        image_url="https://cdn.example.com/reference.png",
    )
    contract = _dialogue_contract(
        SimpleNamespace(),
        "沈砚：所有人立刻撤离灯塔。",
        4.0,
        video_native_audio=native_audio,
    )
    prepared = PreparedVideoSubmission(
        video_request=video_request,
        lineage={},
        consistency_package={"metadata": {}, "context": {}, "reference_image_source": "shot_image"},
        reference_package={"reference_image_source": "shot_image"},
        final_video_prompt=_append_dialogue_prompt("动漫镜头", contract),
        effective_image_url="https://cdn.example.com/reference.png",
        video_seed=7,
        audio_route={"route": "video_native_audio"},
        dialogue_sync_contract=contract,
        video_preflight_package=None,
        lock_snapshot={},
    )
    runtime = VideoSubmissionRuntime(
        selected_model={
            "api_model_id": model_id,
            "model_name": "Seedance 1.5 Pro",
        },
        reference_limits={"images": 1},
        selected_model_id=model_id,
        selected_provider="volcano",
        api_key="sk-test",
        use_dev_video=False,
    )
    context = SimpleNamespace(
        user_id="native-audio-user",
        workflow=SimpleNamespace(id="workflow-1"),
        effective_video_config_id="video-config-1",
        strategy_video_routing={"routing": "saved_config", "matched_api_model_id": model_id},
        series_run=None,
    )
    shot = SimpleNamespace(id="shot-1", shot_number=1, extra_data={})
    return VideoSubmissionCommand(context, request, shot, prepared, runtime)


def test_seedance_native_audio_request_carries_dialogue_and_does_not_use_reference_as_cover() -> None:
    command = _command()
    kwargs = _create_kwargs(command, {"content": []})
    extra = _build_extra_data(command, {})
    job = _build_job(
        command,
        {
            "provider_prompt": command.prepared.final_video_prompt,
            "provider_image_url": command.prepared.effective_image_url,
            "extra_data": extra,
        },
        "video-job-1",
        "provider-task-1",
        None,
        None,
    )

    assert kwargs["generate_audio"] is True
    assert kwargs["watermark"] is False
    assert "沈砚" in command.prepared.final_video_prompt
    assert "所有人立刻撤离灯塔" in command.prepared.final_video_prompt
    assert "不得增删或改写台词" in command.prepared.final_video_prompt
    assert "口型" in command.prepared.final_video_prompt
    assert extra["video_native_audio"] is True
    assert extra["dialogue_sync_contract"]["audio_source"] == "video_native_audio"
    assert job.shot_id == "shot-1"
    assert job.image_url == "https://cdn.example.com/reference.png"
    assert job.cover_url is None


def test_native_audio_rejects_non_seedance_15_model() -> None:
    command = _command(model_id="doubao-seedance-1-0-pro-250528")

    with pytest.raises(WorkflowMediaError) as caught:
        _create_kwargs(command, {"content": []})

    assert caught.value.detail["code"] == "native_audio_model_unsupported"


def test_seedance_15_blocks_native_audio_without_shot_owned_first_frame() -> None:
    command = _command()
    command = VideoSubmissionCommand(
        command.context,
        command.request,
        command.shot,
        PreparedVideoSubmission(
            **{
                **command.prepared.__dict__,
                "reference_package": {"reference_image_source": "locked_asset"},
                "consistency_package": {
                    **command.prepared.consistency_package,
                    "reference_image_source": "locked_asset",
                },
            }
        ),
        command.runtime,
    )

    data = {"provider_prompt": command.prepared.final_video_prompt,
            "provider_image_url": command.prepared.effective_image_url,
            "prompt_parameters": {}, "extra_data": {}}
    with pytest.raises(WorkflowMediaError) as caught:
        _build_provider_content(command, data)

    assert caught.value.detail["code"] == "native_audio_shot_first_frame_required"
    assert caught.value.detail["shot_id"] == "shot-1"


def test_seedance_15_accepts_persisted_shot_first_frame_when_legacy_source_is_request() -> None:
    command = _command()
    command.shot.image_url = command.prepared.video_request.image_url
    command = VideoSubmissionCommand(
        command.context,
        command.request,
        command.shot,
        PreparedVideoSubmission(
            **{
                **command.prepared.__dict__,
                "reference_package": {"reference_image_source": "request"},
                "consistency_package": {
                    **command.prepared.consistency_package,
                    "reference_image_source": "request",
                },
            }
        ),
        command.runtime,
    )

    _validate_seedance_first_frame(command, image_count=1)


def test_native_audio_canonicalizes_speaker_and_removes_other_dialogue_from_prompt() -> None:
    shot = SimpleNamespace(
        id="shot-4",
        shot_number=1,
        character_refs=[],
        extra_data={},
        visual_description=(
            '影潮使低声说：“星灯一亮，我的影潮就会消失。”'
            '苏澜回答：“那就让雾海看见黎明。”'
            '顾言接回能量核心，喊道：“能源接通，转动密钥！”'
        ),
    )

    contract = _dialogue_contract(
        shot, "喊道：能源接通，转动密钥！", 4.0, video_native_audio=True,
    )
    prompt = _append_dialogue_prompt(shot.visual_description, contract)

    assert contract["speaker"] == "顾言"
    assert contract["subtitle_text"] == "顾言：能源接通，转动密钥！"
    assert prompt.count("能源接通，转动密钥") == 1
    assert "星灯一亮，我的影潮就会消失" not in prompt
    assert "那就让雾海看见黎明" not in prompt


def test_native_audio_preserves_multi_speaker_dialogue_constraints() -> None:
    shot = SimpleNamespace(id="shot-2", shot_number=2)
    subtitle = "沈砚：别回头。\n林澜：我听见铜铃了。"
    contract = _dialogue_contract(shot, subtitle, 4.0, video_native_audio=True)

    _validate_dialogue(shot, subtitle, contract)
    prompt = _append_dialogue_prompt("雾港双人对话", contract)

    assert "沈砚：别回头" in prompt
    assert "林澜：我听见铜铃了" in prompt
    assert "不得串词" in prompt


def test_native_audio_safety_rewrite_preserves_canonical_spoken_text() -> None:
    prompt = (
        "画面表现失踪船队留下的空港。\n"
        "原生有声视频约束（硬性）：唯一说话人：沈砚；"
        "必须完整、清晰地说：『我会查清失踪船队的去向。』；"
        "画面不得生成字幕、标题或其他文字。"
    )

    result = sanitize_provider_video_prompt(
        prompt,
        protected_texts=["我会查清失踪船队的去向。"],
    )

    assert "画面表现待查船队留下的空港" in result["prompt"]
    assert "『我会查清失踪船队的去向。』" in result["prompt"]


def test_native_audio_prompt_delegates_subtitles_to_post_processing_only() -> None:
    contract = _dialogue_contract(
        SimpleNamespace(), "沈砚：所有人立刻撤离灯塔。", 4.0,
        video_native_audio=True,
    )

    prompt = _append_dialogue_prompt("3D灯塔镜头", contract)

    assert "画面不得生成字幕" in prompt
    assert "字幕由后处理统一添加" in prompt


def test_native_audio_uses_the_audio_video_prompt_skill() -> None:
    native = VideoGenerateRequest(prompt="有对白", native_audio=True)
    silent = VideoGenerateRequest(prompt="无对白")

    assert _prompt_skill_task(native) == "shot_audio_video"
    assert _prompt_skill_task(silent) == "shot_video"


def test_native_audio_prompt_preserves_visual_and_locked_asset_constraints() -> None:
    from app.services.prompt_composer import compose_generation_prompt

    prompt = compose_generation_prompt(
        task="shot_audio_video",
        locked_assets=[{"type": "角色", "name": "沈砚定稿"}],
    )

    assert "视频一致性约束" in prompt
    assert "锁定资产一致性约束" in prompt
    assert "沈砚定稿" in prompt


def test_native_audio_job_produces_sanitized_series_skill_evidence() -> None:
    from app.features.series_anchor_generation.skill_evidence import job_skill_evidence

    job = SimpleNamespace(id="video-job-1", extra_data={
        "shot_id": "shot-1",
        "consistency": {
            "task": "shot_audio_video",
            "rendered_prompt_sha256": "prompt-sha256",
            "prompt_skills": [{
                "id": "builtin-shot-audio-video-standard", "name": "标准音视频直生技能",
                "version": 2, "prompt_profile_version_id": "profile-v2",
            }],
        },
    })

    evidence = job_skill_evidence(job)

    assert evidence["task"] == "shot_audio_video"
    assert evidence["artifact_id"] == "video-job-1"
    assert evidence["shot_id"] == "shot-1"
    assert evidence["execution_mode"] == "provider_model"
    assert evidence["rendered_prompt_sha256"] == "prompt-sha256"
    assert "content" not in evidence


def test_native_audio_is_part_of_series_generation_idempotency_key() -> None:
    run = SimpleNamespace(
        id="run-1",
        episodes=[{"input_hash": "chapter-hash"}],
        run_metadata={
            "anchor_selection_revision": 1,
            "story_locks": {"source_hash": "source", "snapshot_hash": "story"},
            "reference_preparation": {"evidence_hash": "reference"},
        },
    )

    silent_key = _generation_key(run, ["shot-1"], "smoke", False)
    native_key = _generation_key(run, ["shot-1"], "smoke", True)

    assert native_key != silent_key


def test_shot_first_frame_and_subtitle_are_part_of_series_generation_idempotency_key() -> None:
    run = SimpleNamespace(
        id="run-1",
        episodes=[{"input_hash": "chapter-hash"}],
        run_metadata={
            "anchor_selection_revision": 1,
            "story_locks": {"source_hash": "source", "snapshot_hash": "story"},
            "reference_preparation": {"evidence_hash": "reference"},
        },
    )
    first = SimpleNamespace(
        id="shot-1", prompt="scene", visual_description=None, dialogue="旁白：旧台词",
        image_url="/static/old.jpg", extra_data={"subtitle_text": "旧字幕"},
    )
    changed = SimpleNamespace(
        id="shot-1", prompt="scene", visual_description=None, dialogue="旁白：新台词",
        image_url="/static/clean-first-frame.jpg", extra_data={"subtitle_text": "新字幕"},
    )

    assert _generation_key(run, ["shot-1"], "smoke", True, [first]) != _generation_key(
        run, ["shot-1"], "smoke", True, [changed],
    )


@pytest.mark.asyncio
async def test_generation_group_reuse_compares_the_fresh_shot_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DETERMINISTIC_PROVIDER_FAKE", raising=False)
    latest = SimpleNamespace(
        id="old-job", status="succeeded",
        extra_data={
            "episode_number": 1,
            "episode_contract_version": "episode-v1",
            "canonical_reference_id": "reference-1",
            "canonical_reference_version": 1,
            "as_of_chapter_id": "chapter-1",
            "as_of_chapter_hash": "chapter-hash",
            "shot_input_fingerprint": "old-shot-input",
        },
    )

    class FakeDb:
        async def scalar(self, _statement):
            return latest

    shot = SimpleNamespace(id="shot-1", extra_data={"production_context": latest.extra_data})
    current_contexts = {
        "shot-1": {**latest.extra_data, "shot_input_fingerprint": "new-shot-input"},
    }

    groups, reused = await _generation_groups(
        FakeDb(), user_id="user-1", selected=["shot-1"],
        workflow_for_shot={"shot-1": "workflow-1"}, selected_by_id={"shot-1": shot},
        contexts=current_contexts,
    )

    assert groups == {"workflow-1": ["shot-1"]}
    assert reused == []


@pytest.mark.asyncio
async def test_generation_activation_persists_the_native_audio_preflight_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeDb:
        async def commit(self):
            return None

    observed: dict[str, bool] = {}

    async def enter_media(_self, _db, run, *, native_audio=False):
        observed["native_audio"] = native_audio
        run.status = "media_running"
        return run

    monkeypatch.setattr(SeriesRunOrchestrator, "enter_media_running", enter_media)
    run = SimpleNamespace(status="shots_ready", gate_summary={"other": True})
    submission = SimpleNamespace(status=None)

    await _activate(
        FakeDb(), run=run, submission=submission, contexts={}, selected_by_id={}, is_new=False,
        media_preflight={"ready": True, "snapshot_hash": "native-snapshot"},
        native_audio=True,
    )

    assert run.gate_summary["media_preflight"] == {
        "ready": True, "snapshot_hash": "native-snapshot",
    }
    assert submission.status == "pending"
    assert observed["native_audio"] is True
