import asyncio
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.database import AsyncSessionLocal
from app.models import Workflow
from app.services.studio_actions import resume_studio_orchestration
from app.services.studio_guidance import build_studio_guidance
from init_db import init_db


@pytest.fixture(scope="module", autouse=True)
def _init_database():
    init_db()


def _guidance(**overrides):
    payload = {
        "workflow": {"id": "wf-1", "novel_id": "novel-1", "chapter_id": "chapter-1", "metadata": {}},
        "story_context": {"novel": {"title": "雾港"}, "chapter": {"title": "第一集"}},
        "story_bible": {"id": "bible-1"},
        "production_bible_summary": {"readiness_score": 90, "asset_readiness": {"ready": True}},
        "production": {"shot_count": 2, "asset_lock_coverage": 1},
        "timeline": {},
        "issues": [],
        "actions": [{"code": "expert_action", "label": "专家动作"}],
        "mode_policy": {"mode": "production", "blocking_issue_count": 0, "confirmable_issue_count": 0},
        "episode_contract": None,
        "production_graph": {"version": 2, "hash": "graph-hash"},
        "assets": {
            "total_count": 3,
            "locked_count": 3,
            "items": [{"id": "asset-base", "is_locked": True, "is_final": True}],
        },
        "jobs": {"summary": {"video_count": 0, "media_count": 0, "synthesis_count": 0}},
        "consistency_ledger": {"overall_score": 0, "findings": []},
        "orchestration": {},
    }
    payload.update(overrides)
    return build_studio_guidance(**payload)


def test_stage_contract_has_exact_eight_stages_and_one_primary_action():
    guidance = _guidance()

    assert [item["id"] for item in guidance["stages"]] == [
        "facts", "assets", "episode_contract", "draft", "review", "final", "render", "publish"
    ]
    assert guidance["current_stage"] == "episode_contract"
    assert guidance["recommended_action"] == guidance["next_action"]
    assert guidance["recommended_action"]["code"] == "lock_episode_contract"
    assert len([guidance["recommended_action"]]) == 1
    assert guidance["secondary_actions"] == [{"code": "expert_action", "label": "专家动作"}]
    assert guidance["completed_evidence"]
    assert guidance["blockers"] == []
    assert guidance["confirmable_warnings"] == []


def test_failed_orchestration_resumes_with_persisted_task_and_completed_stages():
    guidance = _guidance(
        orchestration={
            "task_id": "task-persisted-7",
            "status": "failed",
            "failed_stage": "draft",
            "completed_stages": ["facts", "assets", "episode_contract"],
            "error_message": "provider timeout",
        },
    )

    assert guidance["current_stage"] == "draft"
    assert guidance["orchestration_resume"]["task_id"] == "task-persisted-7"
    assert guidance["orchestration_resume"]["safe_retry"] is True
    assert guidance["orchestration_resume"]["completed_stages"] == ["facts", "assets", "episode_contract"]
    assert guidance["recommended_action"]["code"] == "retry_orchestration"
    assert guidance["recommended_action"]["params"]["task_id"] == "task-persisted-7"


def test_secondary_actions_exclude_the_single_recommended_action_code():
    guidance = _guidance(actions=[
        {"code": "lock_episode_contract", "label": "重复主动作"},
        {"code": "expert_action", "label": "专家动作"},
    ])

    assert guidance["recommended_action"]["code"] == "lock_episode_contract"
    assert [item["code"] for item in guidance["secondary_actions"]] == ["expert_action"]


def test_resume_consumer_validates_task_and_persists_safe_resume_state():
    async def scenario():
        user_id = f"stage-user-{uuid4()}"
        workflow_id = f"stage-workflow-{uuid4()}"
        task_id = f"stage-task-{uuid4()}"
        async with AsyncSessionLocal() as db:
            db.add(Workflow(
                id=workflow_id,
                user_id=user_id,
                title="失败草片",
                status="running",
                metadata_={"studio_orchestration": {
                    "task_id": task_id,
                    "status": "failed",
                    "failed_stage": "draft",
                    "completed_stages": ["facts", "assets", "episode_contract"],
                }},
            ))
            await db.commit()
            with pytest.raises(HTTPException) as exc_info:
                await resume_studio_orchestration(db, "other-user", workflow_id, task_id=task_id)
            result = await resume_studio_orchestration(db, user_id, workflow_id, task_id=task_id)
            refreshed = await db.get(Workflow, workflow_id)
            return result, refreshed.metadata_["studio_orchestration"], exc_info.value.status_code

    result, persisted, other_status = asyncio.run(scenario())
    assert other_status == 404
    assert result["task_id"] == persisted["task_id"]
    assert result["status"] == "handoff_ready"
    assert result["safe_next_action"]["code"] == "open_producer"
    assert result["safe_next_action"]["href"].startswith("/producer?")
    assert "workflow_id=" in result["safe_next_action"]["href"]
    assert f"resume_task_id={result['task_id']}" in result["safe_next_action"]["href"]
    assert persisted["status"] == "handoff_ready"


def test_failed_jobs_incomplete_quality_and_unpublishable_render_do_not_complete_stages():
    quality = {
        "artifact_id": "artifact-incomplete",
        "evaluation_ids": ["qe-1"],
        "dimensions": ["narrative_truth"],
        "score": 99,
        "blocking": False,
    }
    guidance = _guidance(
        episode_contract={"contract_id": "contract-1", "production_bible_hash": "bible-hash"},
        jobs={
            "summary": {"video_count": 1, "media_count": 0, "synthesis_count": 1},
            "video_jobs": [{"id": "video-failed", "status": "failed", "video_url": "/failed.mp4"}],
            "media_jobs": [],
            "synthesis_jobs": [{"id": "render-running", "status": "running", "output_url": "/draft.mp4", "is_publishable": False}],
        },
        timeline={"clip_count": 1, "preview_url": "/stale-preview.mp4"},
        consistency_ledger={"overall_score": 99, "findings": []},
        quality_evaluation=quality,
    )

    assert guidance["current_stage"] == "draft"
    completed = {item["stage"] for item in guidance["completed_evidence"]}
    assert "draft" not in completed
    assert "review" not in completed
    assert "final" not in completed
    assert "render" not in completed


def test_successful_deliverables_emit_stage_specific_auditable_evidence():
    dimensions = [
        "narrative_truth", "character_visual", "scene_prop_state",
        "motion_camera", "voice_lipsync", "delivery_integrity",
    ]
    guidance = _guidance(
        episode_contract={"contract_id": "contract-1", "production_bible_hash": "bible-hash"},
        assets={"items": [{"id": "asset-locked", "is_locked": True, "is_final": True}]},
        jobs={
            "summary": {"video_count": 1, "media_count": 0, "synthesis_count": 1},
            "video_jobs": [{"id": "video-ok", "status": "succeeded", "video_url": "/video-ok.mp4"}],
            "media_jobs": [],
            "synthesis_jobs": [{"id": "render-ok", "status": "succeeded", "output_url": "/final.mp4", "is_publishable": True}],
        },
        quality_evaluation={
            "artifact_id": "video-ok",
            "evaluation_ids": [f"qe-{index}" for index in range(6)],
            "dimensions": dimensions,
            "score": 96,
            "blocking": False,
        },
        consistency_ledger={"overall_score": 96, "findings": []},
    )

    assert guidance["current_stage"] == "publish"
    evidence = {item["stage"]: item for item in guidance["completed_evidence"]}
    assert evidence["facts"]["hash"] == "graph-hash"
    assert evidence["episode_contract"]["evidence_id"] == "contract-1"
    assert evidence["draft"]["job_id"] == "video-ok"
    assert evidence["review"]["artifact_id"] == "video-ok"
    assert evidence["review"]["score"] == 96
    assert len(evidence["review"]["evaluation_ids"]) == 6
    assert evidence["render"]["job_id"] == "render-ok"
    assert evidence["render"]["artifact_id"] == "/final.mp4"
