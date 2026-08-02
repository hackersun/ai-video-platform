from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.core.database import AsyncSessionLocal
from app.core.time_utils import utc_now
from app.features.series_anchor_generation.media_reconciliation import (
    _native_subtitle_already_finalized,
    pending_source_response,
    reconcile_selected_media,
)
from app.models import MediaGenerationJob, Novel, Shot, SubtitleTrack, TTSJob, VideoJob, Workflow
from app.models.subtitle import SubtitleSegment
from app.models.live_canary_provider_operation import LiveCanaryProviderOperation
from app.models.series_anchor_generation_submission import SeriesAnchorGenerationSubmission
from app.models.series_production_run import SeriesProductionRun
from init_db import init_db
from main import app


_CREATED_USER_IDS: set[str] = set()


async def _cleanup_seeded_rows() -> None:
    if not _CREATED_USER_IDS:
        return
    models = (
        SubtitleSegment, SubtitleTrack, MediaGenerationJob, TTSJob, VideoJob, LiveCanaryProviderOperation,
        SeriesAnchorGenerationSubmission, Shot, Workflow, SeriesProductionRun, Novel,
    )
    async with AsyncSessionLocal() as db:
        for model in models:
            await db.execute(delete(model).where(model.user_id.in_(_CREATED_USER_IDS)))
        await db.commit()


@pytest.fixture(scope="module", autouse=True)
def _database() -> None:
    init_db()
    yield
    asyncio.run(_cleanup_seeded_rows())
    _CREATED_USER_IDS.clear()


def test_pending_source_response_distinguishes_waiting_and_provider_ready() -> None:
    pending = pending_source_response(
        ["shot-1"],
        [{"video_job_ids": ["video-1"], "tts_job_ids": ["tts-1"],
          "pending_video_job_ids": ["video-1"], "pending_tts_job_ids": []}],
    )
    ready = pending_source_response(
        ["shot-1"],
        [{"video_job_ids": ["video-1"], "tts_job_ids": ["tts-1"],
          "pending_video_job_ids": [], "pending_tts_job_ids": []}],
    )

    assert pending and pending["status"] == "provider_pending"
    assert pending["pending_video_job_ids"] == ["video-1"]
    assert ready and ready["status"] == "provider_ready"
    assert pending_source_response(["shot-1"], [{"media_job_ids": ["media-1"]}]) is None


def test_native_subtitle_finalize_is_idempotent_for_same_track_and_dialogue() -> None:
    digest = "a" * 64
    video = type("Video", (), {
        "video_url": "/static/generated/videos/native-subtitled.mp4",
        "extra_data": {
            "subtitle_burned": True,
            "subtitle_track_id": "track-1",
            "expected_dialogue_sha256": digest,
            "subtitle_timing_contract_version": "native_audio_activity_v9",
            "provider_label_removed": True,
        },
    })()
    track = type("Track", (), {
        "id": "track-1",
        "export_urls": {"burned_video": "/static/generated/videos/native-subtitled.mp4"},
    })()

    assert _native_subtitle_already_finalized(video, track, digest) is True


async def _seed_source_jobs(
    *, video_status: str = "pending", tts_status: str = "succeeded", native_audio: bool = False,
) -> dict[str, str]:
    ids = {name: str(uuid4()) for name in (
        "user", "novel", "workflow", "shot", "run", "submission", "video", "tts", "reference_operation",
        "video_operation", "tts_operation",
    )}
    _CREATED_USER_IDS.add(ids["user"])
    async with AsyncSessionLocal() as db:
        db.add(Novel(id=ids["novel"], user_id=ids["user"], title="async reconciliation"))
        db.add(Workflow(
            id=ids["workflow"], user_id=ids["user"], novel_id=ids["novel"],
            title="async reconciliation", status="active", current_step=8,
            completed_steps=[7, 8], video_job_ids=[ids["video"]],
            tts_job_ids=[] if native_audio else [ids["tts"]],
            synthesis_job_ids=[], metadata_={"series_run_id": ids["run"]},
        ))
        db.add(Shot(
            id=ids["shot"], user_id=ids["user"], storyboard_id=str(uuid4()), shot_number=1,
            duration=4, prompt="关键镜头", dialogue="主角：继续。", extra_data={"production_context": {
                "episode_number": 1, "episode_contract_version": "episode-v1",
                "canonical_reference_id": "reference-asset", "canonical_reference_version": 1,
                "as_of_chapter_id": "chapter-1", "as_of_chapter_hash": "chapter-hash",
                "asset_version_locks": [{"asset_id": "reference-asset", "version": 1}],
            }},
        ))
        run = SeriesProductionRun(
            id=ids["run"], user_id=ids["user"], novel_id=ids["novel"], series_plan_version="v1",
            idempotency_key=str(uuid4()), status="media_running", requested_stages=["media"],
            model_bindings={"capabilities": {}}, budget_policy={"live_canary": True, "max_rmb": "10.00"},
            cost_summary={}, gate_summary={}, run_metadata={
                "selected_anchor_shot_ids": [ids["shot"]], "selected_anchor_mode": "smoke",
                "reference_preparation": {"asset_id": "reference-asset", "asset_version": 1},
            },
            episodes=[{"episode_number": 1, "canonical_ids": {"workflow_id": ids["workflow"]}}], version=1,
        )
        db.add(run)
        video_extra = {
            "provider_id": "volcano", "model_config_id": "video-config",
            "video_native_audio": native_audio,
            "lineage": {"shot_id": ids["shot"]},
            "live_canary_accounting": {"operation_id": ids["video_operation"], "capability": "video"},
        }
        db.add(VideoJob(
            id=ids["video"], user_id=ids["user"], workflow_id=ids["workflow"],
            task_id="provider-video-1", title="video", prompt="关键镜头", model_id="seedance",
            model_name="Seedance", duration=4, resolution="720p", status=video_status,
            progress=100 if video_status == "succeeded" else 20,
            video_url="https://media.example/video.mp4" if video_status == "succeeded" else None,
            extra_data=video_extra,
        ))
        if not native_audio:
            db.add(TTSJob(
                id=ids["tts"], user_id=ids["user"], workflow_id=ids["workflow"], shot_id=ids["shot"],
                task_id="provider-tts-1", title="tts", text="继续。", model_id="speech",
                model_name="Speech", api_provider="minimax", status=tts_status,
                progress=100 if tts_status == "succeeded" else 20,
                audio_url="https://media.example/audio.mp3" if tts_status == "succeeded" else None,
                extra_data={"live_canary_accounting": {
                    "operation_id": ids["tts_operation"], "capability": "tts",
                }},
            ))
        operations = [
            (ids["reference_operation"], "reference", "reference-asset", "provider-reference-1"),
            (ids["video_operation"], "video", ids["video"], "provider-video-1"),
        ]
        if not native_audio:
            operations.append((ids["tts_operation"], "tts", ids["tts"], "provider-tts-1"))
        for operation_id, capability, job_id, task_id in operations:
            db.add(LiveCanaryProviderOperation(
                id=operation_id, run_id=ids["run"], user_id=ids["user"],
                reservation_id=f"reservation:{operation_id}", capability=capability,
                job_type=f"{capability}_job", job_id=job_id,
                artifact_id="reference-asset" if capability == "reference" else None,
                provider_task_id=task_id, status="reconciled" if capability == "reference" else "accepted",
                created_at=utc_now(), updated_at=utc_now(),
            ))
        payload = {
            "status": "provider_pending", "selected_shot_ids": [ids["shot"]],
            "workflow_batches": [{
                "workflow_id": ids["workflow"], "strategy": "separate_video_tts",
                "video_job_ids": [ids["video"]], "tts_job_ids": [] if native_audio else [ids["tts"]],
                "pending_video_job_ids": [ids["video"]] if video_status == "pending" else [],
                "pending_tts_job_ids": [ids["tts"]] if not native_audio and tts_status == "pending" else [],
            }], "quality_results": [],
        }
        db.add(SeriesAnchorGenerationSubmission(
            id=ids["submission"], run_id=ids["run"], user_id=ids["user"],
            generation_key=str(uuid4()).replace("-", ""), status="provider_pending", response_payload=payload,
        ))
        await db.commit()
    return ids


@pytest.mark.asyncio
async def test_reconcile_waits_without_creating_aggregate() -> None:
    ids = await _seed_source_jobs()

    async with AsyncSessionLocal() as db:
        result = await reconcile_selected_media(db, run_id=ids["run"], user_id=ids["user"])
        count = await db.scalar(select(func.count()).select_from(MediaGenerationJob).where(
            MediaGenerationJob.workflow_id == ids["workflow"],
        ))

    assert result["status"] == "provider_pending"
    assert result["pending_video_job_ids"] == [ids["video"]]
    assert count == 0


@pytest.mark.asyncio
async def test_reconcile_aggregates_successful_sources_once() -> None:
    ids = await _seed_source_jobs(video_status="succeeded")

    async with AsyncSessionLocal() as db:
        first = await reconcile_selected_media(db, run_id=ids["run"], user_id=ids["user"])
        second = await reconcile_selected_media(db, run_id=ids["run"], user_id=ids["user"])
        jobs = list((await db.scalars(select(MediaGenerationJob).where(
            MediaGenerationJob.workflow_id == ids["workflow"],
        ))).all())

    assert first == second
    assert first["status"] == "completed"
    assert len(jobs) == 1
    job = jobs[0]
    assert job.source_job_ids == {"video_job_id": ids["video"], "tts_job_id": ids["tts"]}
    assert job.output_video_url == "https://media.example/video.mp4"
    assert job.output_audio_url == "https://media.example/audio.mp3"
    assert {item["capability"] for item in job.extra_data["provider_calls"]} == {"reference", "video", "tts"}
    assert first["quality_results"][0]["overall_readiness"] == "trusted_multimodal_evaluation_required"


@pytest.mark.asyncio
async def test_reconcile_uses_latest_regenerated_video_when_submission_keeps_stale_job_id() -> None:
    ids = await _seed_source_jobs(video_status="succeeded")
    replacement_id = str(uuid4())
    replacement_operation_id = str(uuid4())

    async with AsyncSessionLocal() as db:
        initial = await reconcile_selected_media(db, run_id=ids["run"], user_id=ids["user"])
        assert initial["status"] == "completed"

    async with AsyncSessionLocal() as db:
        original = await db.get(VideoJob, ids["video"])
        original.extra_data = {
            **(original.extra_data or {}),
            "superseded_by_regeneration": True,
            "superseded_at": utc_now().isoformat(),
        }
        db.add(VideoJob(
            id=replacement_id,
            user_id=ids["user"],
            workflow_id=ids["workflow"],
            task_id="provider-video-regenerated",
            title="regenerated video",
            prompt="关键镜头",
            model_id="seedance",
            model_name="Seedance",
            duration=4,
            resolution="720p",
            status="succeeded",
            progress=100,
            video_url="https://media.example/regenerated.mp4",
            extra_data={
                **(original.extra_data or {}),
                "superseded_by_regeneration": False,
                "replaces_job_id": ids["video"],
                "lineage": {"shot_id": ids["shot"]},
                "live_canary_accounting": {
                    "operation_id": replacement_operation_id,
                    "capability": "video",
                },
            },
        ))
        db.add(LiveCanaryProviderOperation(
            id=replacement_operation_id,
            run_id=ids["run"],
            user_id=ids["user"],
            reservation_id=f"reservation:{replacement_operation_id}",
            capability="video",
            job_type="video_job",
            job_id=replacement_id,
            provider_task_id="provider-video-regenerated",
            status="accepted",
            created_at=utc_now(),
            updated_at=utc_now(),
        ))
        await db.commit()

    async with AsyncSessionLocal() as db:
        result = await reconcile_selected_media(db, run_id=ids["run"], user_id=ids["user"])
        aggregate = await db.scalar(select(MediaGenerationJob).where(
            MediaGenerationJob.workflow_id == ids["workflow"],
        ))

    assert result["status"] == "completed"
    assert result["workflow_batches"][0]["video_job_ids"] == [replacement_id]
    assert aggregate.source_job_ids["video_job_id"] == replacement_id
    assert aggregate.output_video_url == "https://media.example/regenerated.mp4"
    assert next(
        item for item in aggregate.extra_data["provider_calls"] if item["capability"] == "video"
    )["provider_task_id"] == "provider-video-regenerated"


@pytest.mark.asyncio
async def test_reconcile_native_audio_without_fabricating_tts_source() -> None:
    ids = await _seed_source_jobs(video_status="succeeded", native_audio=True)

    async with AsyncSessionLocal() as db:
        result = await reconcile_selected_media(db, run_id=ids["run"], user_id=ids["user"])
        job = await db.scalar(select(MediaGenerationJob).where(
            MediaGenerationJob.workflow_id == ids["workflow"],
        ))

    assert result["status"] == "completed"
    assert job is not None
    assert job.capabilities == ["video", "native_audio"]
    assert job.source_job_ids == {"video_job_id": ids["video"], "tts_job_id": None}
    assert job.extra_data["video_native_audio"] is True
    assert {item["capability"] for item in job.extra_data["provider_calls"]} == {"reference", "video"}


@pytest.mark.asyncio
async def test_reconcile_burns_native_audio_subtitle_and_records_public_delivery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ids = await _seed_source_jobs(video_status="succeeded", native_audio=True)
    track_id, segment_id = str(uuid4()), str(uuid4())
    async with AsyncSessionLocal() as db:
        video = await db.get(VideoJob, ids["video"])
        video.extra_data = {**(video.extra_data or {}), "video_delivery": {
            "object_key": "static/generated/videos/provider-local.mp4",
        }}
        db.add(SubtitleTrack(
            id=track_id, user_id=ids["user"], workflow_id=ids["workflow"],
            shot_id=ids["shot"], title="原生有声字幕", source="video_native_audio", status="draft",
        ))
        db.add(SubtitleSegment(
            id=segment_id, track_id=track_id, user_id=ids["user"], shot_id=ids["shot"],
            start_seconds=0.2, end_seconds=3.8, text="主角：继续。", sort_order=1,
        ))
        await db.commit()

    def fake_burn(video_url, segments):
        assert video_url == "/static/generated/videos/provider-local.mp4"
        assert segments[0]["text"] == "主角：继续。"
        return {
            "video_url": "/static/generated/videos/native-subtitled.mp4",
            "local_path": "/tmp/native-subtitled.mp4",
            "subtitle_count": 1,
            "audio_preserved": True,
            "audio_loudness": {
                "input_mean_db": -32.2, "input_max_db": -15.7,
                "output_mean_db": -20.1, "output_max_db": -3.6,
                "normalized": True, "gain_db": 12.2,
            },
            "provider_label_removed": True,
            "provider_label_cleanup": {
                "method": "bottom_safe_crop_and_scale", "x": 36, "y": 0,
                "width": 648, "height": 1152, "output_width": 720, "output_height": 1280,
            },
        }

    async def fake_delivery(*args, **kwargs):
        return {
            "provider_url": "https://cdn.example/native-subtitled.mp4",
            "delivery_method": "qiniu_object_upload",
            "object_key": "static/generated/videos/native-subtitled.mp4",
            "omitted_reason": None,
        }

    monkeypatch.setattr(
        "app.features.series_anchor_generation.media_reconciliation.burn_native_audio_subtitles",
        fake_burn,
    )
    monkeypatch.setattr(
        "app.features.series_anchor_generation.media_reconciliation.resolve_provider_media_url",
        fake_delivery,
    )

    async with AsyncSessionLocal() as db:
        result = await reconcile_selected_media(db, run_id=ids["run"], user_id=ids["user"])
        aggregate = await db.scalar(select(MediaGenerationJob).where(
            MediaGenerationJob.workflow_id == ids["workflow"],
        ))
        track = await db.get(SubtitleTrack, track_id)
        video = await db.get(VideoJob, ids["video"])

    assert result["status"] == "completed"
    assert aggregate.output_video_url == "/static/generated/videos/native-subtitled.mp4"
    assert aggregate.subtitle_track_id == track_id
    assert aggregate.extra_data["subtitle_burned"] is True
    assert aggregate.extra_data["subtitle_public_video_url"] == "https://cdn.example/native-subtitled.mp4"
    assert track.status == "ready"
    assert track.export_urls["public_video"] == "https://cdn.example/native-subtitled.mp4"
    assert video.extra_data["subtitle_audio_preserved"] is True
    assert video.extra_data["native_audio_loudness"]["normalized"] is True
    assert video.extra_data["subtitle_timing_contract_version"] == "native_audio_activity_v9"
    assert video.extra_data["provider_label_removed"] is True
    assert aggregate.extra_data["provider_label_removed"] is True
    assert video.extra_data["subtitle_sync_status"] == "script_aligned_pending_audio_verification"
    assert video.extra_data["audio_verification_required"] is True
    assert len(video.extra_data["expected_dialogue_sha256"]) == 64
    assert aggregate.extra_data["subtitle_sync_status"] == "script_aligned_pending_audio_verification"
    assert aggregate.extra_data["audio_verification_required"] is True
    assert aggregate.extra_data["native_audio_loudness"]["output_mean_db"] == -20.1
    assert track.metadata_["timing_source"] == "script_contract"
    assert track.metadata_["audio_verified"] is False

    async with AsyncSessionLocal() as db:
        stale_aggregate = await db.get(MediaGenerationJob, aggregate.id)
        stale_video = await db.get(VideoJob, ids["video"])
        stale_aggregate.extra_data = {
            **(stale_aggregate.extra_data or {}),
            "subtitle_delivery": {"object_key": "static/generated/videos/stale.mp4"},
        }
        stale_video.extra_data = {
            **(stale_video.extra_data or {}),
            "subtitle_timing_contract_version": "native_audio_activity_v6",
        }
        await db.commit()
        repeated = await reconcile_selected_media(db, run_id=ids["run"], user_id=ids["user"])
        repeated_job = await db.get(MediaGenerationJob, aggregate.id)

    assert repeated["status"] == "completed"
    assert repeated_job.output_video_url == "/static/generated/videos/native-subtitled.mp4"
    assert repeated_job.extra_data["subtitle_delivery"]["object_key"] == (
        "static/generated/videos/native-subtitled.mp4"
    )


@pytest.mark.asyncio
async def test_reconcile_combines_reused_and_new_selected_artifacts() -> None:
    ids = await _seed_source_jobs(video_status="succeeded")
    reused_shot_id, reused_job_id = str(uuid4()), str(uuid4())
    async with AsyncSessionLocal() as db:
        db.add(Shot(
            id=reused_shot_id, user_id=ids["user"], storyboard_id=str(uuid4()), shot_number=2,
            duration=4, prompt="复用镜头", extra_data={"production_context": {
                "episode_number": 1, "episode_contract_version": "episode-v1",
                "canonical_reference_id": "reference-asset", "canonical_reference_version": 1,
                "as_of_chapter_id": "chapter-1", "as_of_chapter_hash": "chapter-hash",
            }},
        ))
        db.add(MediaGenerationJob(
            id=reused_job_id, user_id=ids["user"], workflow_id=ids["workflow"],
            task_type="shot_audio_video", media_type="audio_video", shot_id=reused_shot_id,
            status="succeeded", progress=100, output_video_url="https://media.example/reused.mp4",
        ))
        submission = await db.get(SeriesAnchorGenerationSubmission, ids["submission"])
        submission.response_payload = {
            **submission.response_payload,
            "selected_shot_ids": [ids["shot"], reused_shot_id],
            "workflow_batches": [
                *submission.response_payload["workflow_batches"],
                {"reused": True, "media_job_ids": [reused_job_id]},
            ],
        }
        await db.commit()

    async with AsyncSessionLocal() as db:
        result = await reconcile_selected_media(db, run_id=ids["run"], user_id=ids["user"])

    assert result["status"] == "completed"
    assert reused_job_id in result["media_job_ids"]
    assert len(result["media_job_ids"]) == 2
    assert {item["shot_id"] for item in result["quality_results"]} == {ids["shot"], reused_shot_id}


@pytest.mark.asyncio
async def test_reconcile_uses_video_submission_snapshot_when_shot_context_changes() -> None:
    ids = await _seed_source_jobs(video_status="succeeded")
    async with AsyncSessionLocal() as db:
        video = await db.get(VideoJob, ids["video"])
        video.extra_data = {
            **(video.extra_data or {}),
            "production_context_snapshot": {
                "episode_number": 1,
                "episode_contract_version": "episode-v1",
                "canonical_reference_id": "reference-asset",
                "canonical_reference_version": 1,
                "as_of_chapter_id": "chapter-1",
                "as_of_chapter_hash": "chapter-hash",
                "shot_input_fingerprint": "submitted-shot-input-v1",
            },
        }
        shot = await db.get(Shot, ids["shot"])
        shot.extra_data = {"production_context": {}}
        await db.commit()

    async with AsyncSessionLocal() as db:
        await reconcile_selected_media(db, run_id=ids["run"], user_id=ids["user"])
        aggregate = await db.scalar(select(MediaGenerationJob).where(
            MediaGenerationJob.workflow_id == ids["workflow"],
        ))

    assert aggregate.extra_data["shot_input_fingerprint"] == "submitted-shot-input-v1"
    assert aggregate.extra_data["canonical_reference_id"] == "reference-asset"


@pytest.mark.asyncio
async def test_reconcile_fails_closed_for_failed_source() -> None:
    ids = await _seed_source_jobs(video_status="failed")

    async with AsyncSessionLocal() as db:
        result = await reconcile_selected_media(db, run_id=ids["run"], user_id=ids["user"])
        aggregate = await db.scalar(select(MediaGenerationJob.id).where(
            MediaGenerationJob.workflow_id == ids["workflow"],
        ))

    assert result["status"] == "failed"
    assert result["failed_video_job_ids"] == [ids["video"]]
    assert aggregate is None


def test_reconcile_route_preserves_ownership_and_pending_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEV_MODE", "true")
    ids = __import__("asyncio").run(_seed_source_jobs())
    with TestClient(app) as client:
        foreign = client.post(
            f"/api/v1/series-runs/{ids['run']}/reconcile-selected",
            headers={"Authorization": "Bearer foreign-user"},
        )
        owned = client.post(
            f"/api/v1/series-runs/{ids['run']}/reconcile-selected",
            headers={"Authorization": f"Bearer {ids['user']}"},
        )

    assert foreign.status_code == 404
    assert owned.status_code == 200
    assert owned.json()["status"] == "provider_pending"
    assert owned.json()["pending_video_job_ids"] == [ids["video"]]
