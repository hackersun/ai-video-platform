from types import SimpleNamespace

import pytest

from app.features.series_anchor_generation.quality_status import unevaluated_quality_results
from app.features.series_anchor_generation.generation import deterministic_quality_identity


class _Db:
    def __init__(self, job):
        self.job = job

    async def scalar(self, _statement):
        return self.job


def _run_and_jobs(*, provider_id="deterministic-acceptance", fake=True):
    capabilities = {name: {
        "provider_id": provider_id, "api_model_id": f"deterministic-{name}",
    } for name in ("text", "image", "tts", "video")}
    run = SimpleNamespace(model_bindings={"capabilities": capabilities})
    jobs = [SimpleNamespace(
        shot_id="shot-1", provider_id=provider_id, model_id="deterministic-video",
        extra_data={"deterministic_provider_fake": fake},
    )]
    return run, jobs


def test_deterministic_quality_requires_acceptance_only_bindings_and_jobs():
    run, jobs = _run_and_jobs()
    assert deterministic_quality_identity(run, jobs, ["shot-1"]) is True

    real_run, _ = _run_and_jobs(provider_id="real-provider")
    assert deterministic_quality_identity(real_run, jobs, ["shot-1"]) is False
    assert deterministic_quality_identity(run, _run_and_jobs(fake=False)[1], ["shot-1"]) is False


@pytest.mark.asyncio
async def test_real_artifact_is_never_presented_as_content_verified_without_evaluator():
    job = SimpleNamespace(
        extra_data={
            "artifact_id": "artifact-1",
            "subtitle_public_video_url": "https://media.invalid/public-subtitled.mp4",
            "subtitle_sync_status": "script_aligned_pending_audio_verification",
            "audio_verification_required": True,
        },
        output_manifest_url=None,
        output_video_url="/static/generated/subtitled.mp4",
        subtitle_track_id="subtitle-track-1",
    )

    result = await unevaluated_quality_results(
        _Db(job), user_id="user-1", selected_shots=[SimpleNamespace(id="shot-1")],
        workflow_for_shot={"shot-1": "workflow-1"},
        episode_by_workflow={"workflow-1": {"episode_number": 4}},
    )

    assert result == [{
        "shot_id": "shot-1", "artifact_id": "artifact-1", "evaluation_ids": [],
        "ready": False, "overall_readiness": "trusted_multimodal_evaluation_required",
        "evidence_source": "not_evaluated", "episode_number": 4,
        "preceding_artifact_id": None,
        "output_video_url": "/static/generated/subtitled.mp4",
        "public_video_url": "https://media.invalid/public-subtitled.mp4",
        "subtitle_track_id": "subtitle-track-1",
        "subtitle_sync_status": "script_aligned_pending_audio_verification",
        "audio_verification_required": True,
    }]
    assert "score" not in result[0] and "dimensions" not in result[0]


@pytest.mark.asyncio
async def test_missing_completed_artifact_fails_closed():
    with pytest.raises(ValueError, match="completed selected-anchor artifact"):
        await unevaluated_quality_results(
            _Db(None), user_id="user-1", selected_shots=[SimpleNamespace(id="shot-1")],
            workflow_for_shot={"shot-1": "workflow-1"},
            episode_by_workflow={},
        )
