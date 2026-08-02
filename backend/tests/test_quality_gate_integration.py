from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1.endpoints.workflow import (
    WorkflowQualityEvaluateRequest,
    WorkflowQualityRepairRequest,
    _build_render_preflight_payload,
    evaluate_workflow_quality,
    get_workflow_shot_review,
    repair_workflow_quality,
)
from app.core.database import Base
from app.models import QualityEvaluation, Shot, Storyboard, SubtitleTrack, TTSJob, VideoJob, Workflow


DB_PATH = Path("/tmp/production-os-task6-integration.db")


def _run(coro):
    return asyncio.run(coro)


def test_workflow_quality_gate_persists_blocks_and_repairs_only_affected_job() -> None:
    async def scenario() -> None:
        DB_PATH.unlink(missing_ok=True)
        engine = create_async_engine(f"sqlite+aiosqlite:///{DB_PATH}")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

        try:
            async with factory() as db:
                workflow = Workflow(
                    id="workflow-quality",
                    user_id="user-quality",
                    title="质量门禁工作流",
                    status="running",
                    storyboard_id="storyboard-quality",
                    video_job_ids=["video-1", "video-2"],
                    tts_job_ids=["tts-1", "tts-2"],
                    synthesis_job_ids=[],
                    metadata_={},
                )
                shot_1 = Shot(
                    id="shot-1",
                    user_id="user-quality",
                    storyboard_id="storyboard-quality",
                    shot_number=1,
                    duration=4,
                    prompt="林澈在雨巷回头",
                    dialogue="林澈：不要回头。",
                    video_status="succeeded",
                    extra_data={"subtitle_text": "不要回头。", "quality_expected": {"speaker_id": "character-lin"}},
                )
                shot_2 = Shot(
                    id="shot-2",
                    user_id="user-quality",
                    storyboard_id="storyboard-quality",
                    shot_number=2,
                    duration=4,
                    prompt="苏晚守在门外",
                    dialogue="苏晚：我在这里。",
                    video_status="succeeded",
                    extra_data={"subtitle_text": "我在这里。", "quality_expected": {"speaker_id": "character-su", "prop_owners": {"prop-key": "character-su"}}},
                )
                foreign_shot = Shot(
                    id="shot-foreign",
                    user_id="user-quality",
                    storyboard_id="storyboard-other",
                    shot_number=1,
                    duration=4,
                    prompt="不属于当前工作流",
                )
                jobs = [
                    VideoJob(
                        id="video-1",
                        user_id="user-quality",
                        workflow_id=workflow.id,
                        task_id="task-video-1",
                        title="镜头1视频",
                        prompt=shot_1.prompt,
                        status="succeeded",
                        progress=100,
                        video_url="/static/video-1.mp4",
                            extra_data={"shot_id": shot_1.id, "media_integrity": {"exists": True, "ffprobe_valid": True}},
                    ),
                    VideoJob(
                        id="video-2",
                        user_id="user-quality",
                        workflow_id=workflow.id,
                        task_id="task-video-2",
                        title="镜头2视频",
                        prompt=shot_2.prompt,
                        status="succeeded",
                        progress=100,
                        video_url="/static/video-2.mp4",
                            extra_data={"shot_id": shot_2.id, "media_integrity": {"exists": True, "ffprobe_valid": True}, "quality_observed": {"prop_owners": {"prop-key": "character-other"}}},
                    ),
                    TTSJob(
                        id="tts-1",
                        user_id="user-quality",
                        workflow_id=workflow.id,
                        shot_id=shot_1.id,
                        task_id="task-tts-1",
                        title="镜头1配音",
                        text="不要回头。",
                        voice="voice-lin",
                        character_id="character-other",
                        status="succeeded",
                        progress=100,
                        audio_url="/static/tts-1.mp3",
                        extra_data={"shot_id": shot_1.id},
                    ),
                    TTSJob(
                        id="tts-2",
                        user_id="user-quality",
                        workflow_id=workflow.id,
                        shot_id=shot_2.id,
                        task_id="task-tts-2",
                        title="镜头2配音",
                        text="我在这里。",
                        voice="voice-su",
                        character_id="character-su",
                        status="succeeded",
                        progress=100,
                        audio_url="/static/tts-2.mp3",
                        extra_data={"shot_id": shot_2.id},
                    ),
                ]
                subtitle_tracks = [
                    SubtitleTrack(id="subtitle-1", user_id=workflow.user_id, workflow_id=workflow.id, storyboard_id=workflow.storyboard_id, shot_id=shot_1.id, status="ready", is_active=True),
                    SubtitleTrack(id="subtitle-2", user_id=workflow.user_id, workflow_id=workflow.id, storyboard_id=workflow.storyboard_id, shot_id=shot_2.id, status="ready", is_active=True),
                ]
                db.add_all([
                    Storyboard(
                        id="storyboard-quality",
                        script_id="script-quality",
                        user_id="user-quality",
                        title="质量门禁分镜",
                        content={},
                    ),
                    workflow,
                    shot_1,
                    shot_2,
                    foreign_shot,
                    *jobs,
                    *subtitle_tracks,
                ])
                await db.commit()

                with pytest.raises(HTTPException) as lineage_error:
                    await evaluate_workflow_quality(
                        workflow.id,
                        WorkflowQualityEvaluateRequest(shot_id=foreign_shot.id),
                        db,
                        "user-quality",
                    )
                assert lineage_error.value.status_code == 404

                evaluation = await evaluate_workflow_quality(
                    workflow.id,
                    WorkflowQualityEvaluateRequest(shot_id=shot_1.id),
                    db,
                    "user-quality",
                )

                rows = (
                    await db.execute(
                        select(QualityEvaluation).where(
                            QualityEvaluation.workflow_id == workflow.id,
                            QualityEvaluation.shot_id == shot_1.id,
                        )
                    )
                ).scalars().all()
                assert len(rows) == 6
                assert evaluation["ready"] is False
                assert evaluation["blockers"][0]["code"] == "wrong_speaker"

                review = await get_workflow_shot_review(workflow.id, db, "user-quality")
                reviewed_shot = next(item for item in review.shots if item["shot_id"] == shot_1.id)
                assert len(reviewed_shot["quality_gate"]["dimensions"]) == 6
                assert reviewed_shot["quality_gate"]["ready"] is False
                assert reviewed_shot["quality_gate"]["suggested_repair"]["actions"] == [
                    "regenerate_tts",
                    "rerun_lipsync",
                    "rerender_audio",
                ]
                assert reviewed_shot["quality_gate"]["suggested_repair"]["cost_risk"] == {
                    "cost": "low",
                    "risk": "low",
                    "scope": "audio_only",
                }

                preflight = await _build_render_preflight_payload(
                    db,
                    workflow,
                    None,
                    "user-quality",
                    use_editable_timeline=False,
                )
                assert "quality_gate_wrong_speaker" in {
                    issue["code"] for issue in preflight["issues"]
                }
                assert "quality_gate_wrong_speaker" in {
                    issue["code"] for issue in preflight["publication_blockers"]
                }
                assert preflight["ready"] is False
                assert preflight["is_publishable"] is False

                # A later passing observation without repair lineage cannot
                # erase the already persisted deterministic blocker.
                jobs[2].character_id = "character-lin"
                await db.commit()
                later_pass = await evaluate_workflow_quality(
                    workflow.id,
                    WorkflowQualityEvaluateRequest(shot_id=shot_1.id),
                    db,
                    "user-quality",
                )
                assert later_pass["ready"] is False
                unresolved_review = await get_workflow_shot_review(workflow.id, db, "user-quality")
                unresolved_shot = next(item for item in unresolved_review.shots if item["shot_id"] == shot_1.id)
                assert unresolved_shot["quality_gate"]["ready"] is False

                repair = await repair_workflow_quality(
                    workflow.id,
                    WorkflowQualityRepairRequest(
                        shot_id=shot_1.id,
                        issue_code="wrong_speaker",
                    ),
                    db,
                    "user-quality",
                )
                assert repair["actions"] == [
                    "regenerate_tts",
                    "rerun_lipsync",
                    "rerender_audio",
                ]
                assert repair["affected_artifact_ids"] == ["tts-1"]
                assert set(repair["unchanged_artifact_ids"]) == {"video-1", "video-2", "tts-2"}
                assert len(repair["created_tts_job_ids"]) == 1
                assert repair["created_video_job_ids"] == []

                unchanged_video_1 = await db.get(VideoJob, "video-1")
                unchanged_video_2 = await db.get(VideoJob, "video-2")
                unchanged_tts_2 = await db.get(TTSJob, "tts-2")
                replaced_tts_1 = await db.get(TTSJob, "tts-1")
                assert unchanged_video_1.extra_data.get("superseded_by_quality_repair") is not True
                assert unchanged_video_2.extra_data.get("superseded_by_quality_repair") is not True
                assert unchanged_tts_2.extra_data.get("superseded_by_quality_repair") is not True
                assert replaced_tts_1.extra_data["superseded_by_quality_repair"] is True
                assert repair["evaluation_ready"] is True
                repaired_review = await get_workflow_shot_review(workflow.id, db, "user-quality")
                repaired_shot = next(item for item in repaired_review.shots if item["shot_id"] == shot_1.id)
                assert repaired_shot["quality_gate"]["ready"] is True
                ordinary_after_repair = await evaluate_workflow_quality(
                    workflow.id,
                    WorkflowQualityEvaluateRequest(shot_id=shot_1.id),
                    db,
                    "user-quality",
                )
                assert ordinary_after_repair["ready"] is True
                still_resolved_review = await get_workflow_shot_review(workflow.id, db, "user-quality")
                still_resolved = next(item for item in still_resolved_review.shots if item["shot_id"] == shot_1.id)
                assert still_resolved["quality_gate"]["ready"] is True
                history_count = len((await db.execute(select(QualityEvaluation).where(QualityEvaluation.shot_id == shot_1.id))).scalars().all())
                assert history_count == 24

                prop_evaluation = await evaluate_workflow_quality(
                    workflow.id,
                    WorkflowQualityEvaluateRequest(shot_id=shot_2.id),
                    db,
                    "user-quality",
                )
                assert {item["code"] for item in prop_evaluation["blockers"]} == {"wrong_prop_owner"}
                prop_repair = await repair_workflow_quality(
                    workflow.id,
                    WorkflowQualityRepairRequest(shot_id=shot_2.id, issue_code="wrong_prop_owner"),
                    db,
                    "user-quality",
                )
                assert prop_repair["actions"] == ["regenerate_shot_video", "rerun_visual_review"]
                assert prop_repair["evaluation_ready"] is True
                assert set(prop_repair["unchanged_artifact_ids"]) == {
                    "video-1", "tts-2", repair["created_tts_job_ids"][0]
                }
                assert await db.get(VideoJob, "video-1") is unchanged_video_1
                assert await db.get(TTSJob, "tts-2") is unchanged_tts_2

                identity_shot = Shot(
                    id="shot-identity-missing",
                    user_id=workflow.user_id,
                    storyboard_id=workflow.storyboard_id,
                    shot_number=3,
                    duration=4,
                    prompt="主角身份观测缺失",
                    extra_data={"quality_expected": {"main_character_id": "character-main", "mp4_required": True}},
                )
                identity_video = VideoJob(
                    id="video-identity-missing",
                    user_id=workflow.user_id,
                    workflow_id=workflow.id,
                    task_id="task-identity-missing",
                    title="身份观测缺失视频",
                    status="succeeded",
                    progress=100,
                    video_url="/static/identity-missing.mp4",
                    extra_data={
                        "shot_id": identity_shot.id,
                        "media_integrity": {"exists": True, "ffprobe_valid": True},
                    },
                )
                db.add_all([identity_shot, identity_video])
                await db.commit()
                identity_evaluation = await evaluate_workflow_quality(
                    workflow.id,
                    WorkflowQualityEvaluateRequest(shot_id=identity_shot.id),
                    db,
                    workflow.user_id,
                )
                assert "main_character_identity_mismatch" in {
                    item["code"] for item in identity_evaluation["blockers"]
                }
        finally:
            await engine.dispose()
            DB_PATH.unlink(missing_ok=True)

    _run(scenario())
