from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import AsyncSessionLocal
from app.models.workflow import Workflow
from app.models.video_job import VideoJob
from app.services.studio_guidance import build_studio_guidance
from init_db import init_db
from main import app
from test_short_video_production import _auth_headers, _create_short_video_fixture


@pytest.fixture(scope="module", autouse=True)
def _init_database() -> None:
    init_db()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DEV_MODE", "true")
    return TestClient(app)


def _insert_video_job(job: VideoJob) -> None:
    async def _insert() -> None:
        async with AsyncSessionLocal() as session:
            workflow = await session.get(Workflow, job.workflow_id)
            if workflow is not None:
                job.user_id = workflow.user_id
                workflow.video_job_ids = [*list(workflow.video_job_ids or []), job.id]
            session.add(job)
            await session.commit()

    asyncio.run(_insert())


def test_studio_snapshot_reports_workflow_context_and_blockers(client: TestClient) -> None:
    user_id = f"studio-snapshot-user-{uuid4()}"
    fixture = _create_short_video_fixture(client, user_id)

    response = client.get(
        f"/api/v1/studio/workflows/{fixture['workflow_id']}/snapshot",
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow"]["id"] == fixture["workflow_id"]
    assert payload["story_context"]["novel"]["id"] == fixture["novel_id"]
    assert payload["story_context"]["chapter"]["id"] == fixture["chapter_id"]
    assert payload["story_bible"]["title"] == "短剧 Story Bible"
    assert payload["production"]["shot_count"] == 3
    assert payload["production"]["asset_lock_coverage"] == 0
    assert any(issue["code"] == "missing_asset_locks" for issue in payload["issues"])
    assert any(action["code"] == "apply_asset_locks" for action in payload["actions"])
    assert payload["mode_policy"]["mode"] == "production"
    assert payload["mode_policy"]["ready"] is False


def test_studio_snapshot_allows_confirmable_test_mode_bypass(client: TestClient) -> None:
    user_id = f"studio-bypass-user-{uuid4()}"
    fixture = _create_short_video_fixture(client, user_id)

    response = client.get(
        f"/api/v1/studio/workflows/{fixture['workflow_id']}/snapshot",
        params={
            "mode": "test",
            "allow_test_bypass": "true",
            "bypass_reason": "本地验证完整流程",
        },
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    payload = response.json()
    missing_locks = [issue for issue in payload["issues"] if issue["code"] == "missing_asset_locks"]
    assert missing_locks
    assert missing_locks[0]["severity"] == "confirmable"
    assert payload["mode_policy"]["mode"] == "test"
    assert payload["mode_policy"]["bypassed_issue_count"] >= 1
    assert payload["mode_policy"]["bypass_audit"]["reason"] == "本地验证完整流程"
    review_stage = next(stage for stage in payload["guidance"]["stages"] if stage["id"] == "review")
    assert review_stage["status"] == "working"


def test_studio_snapshot_updates_asset_lock_coverage_after_existing_action(client: TestClient) -> None:
    user_id = f"studio-locks-user-{uuid4()}"
    fixture = _create_short_video_fixture(client, user_id)

    lock_response = client.post(
        f"/api/v1/production-control/workflow/{fixture['workflow_id']}/asset-locks",
        json={"create_missing_assets": True, "persist": True},
        headers=_auth_headers(user_id),
    )
    assert lock_response.status_code == 200

    response = client.get(
        f"/api/v1/studio/workflows/{fixture['workflow_id']}/snapshot",
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["production"]["asset_lock_coverage"] == 1
    assert not [issue for issue in payload["issues"] if issue["code"] == "missing_asset_locks"]
    assert payload["assets"]["total_count"] >= 3


def test_studio_snapshot_video_jobs_include_reference_package_summary(client: TestClient) -> None:
    user_id = f"studio-reference-package-user-{uuid4()}"
    fixture = _create_short_video_fixture(client, user_id)
    job_id = f"studio-reference-package-job-{uuid4()}"
    _insert_video_job(
        VideoJob(
            id=job_id,
            user_id=user_id,
            workflow_id=fixture["workflow_id"],
            task_id=f"studio-reference-package-task-{uuid4()}",
            title="带参考包的视频任务",
            prompt="参考包摘要测试",
            model_id="test-model",
            model_name="测试模型",
            status="succeeded",
            progress=100,
            video_url="https://example.com/output.mp4",
            extra_data={
                "reference_package_mode": "character_pack",
                "reference_package": {
                    "images": [
                        {"url": "https://example.com/ref-1.png", "role": "front"},
                        {"url": "https://example.com/ref-2.png", "role": "side"},
                    ],
                    "videos": [{"url": "https://example.com/ref.mp4", "role": "motion"}],
                    "dropped": [
                        {"url": "https://example.com/drop-1.png", "reason": "unsupported_type"},
                        {"url": "https://example.com/drop-2.png", "reason": "duplicate"},
                    ],
                    "items": [
                        {"id": "asset-1", "type": "image", "role": "front", "url": "https://example.com/ref-1.png"},
                        {"id": "asset-2", "type": "video", "role": "motion", "url": "https://example.com/ref.mp4"},
                    ],
                },
            },
        )
    )

    response = client.get(
        f"/api/v1/studio/workflows/{fixture['workflow_id']}/snapshot",
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    video_job = response.json()["jobs"]["video_jobs"][0]
    assert video_job["id"] == job_id
    assert video_job["reference_package_mode"] == "character_pack"
    assert video_job["reference_package"] == {
        "image_count": 2,
        "video_count": 1,
        "dropped_count": 2,
        "items": [
            {"id": "asset-1", "type": "image", "role": "front"},
            {"id": "asset-2", "type": "video", "role": "motion"},
        ],
        "dropped": [
            {"reason": "unsupported_type"},
            {"reason": "duplicate"},
        ],
    }


def test_studio_snapshot_includes_guidance_stages_and_next_action(client: TestClient) -> None:
    user_id = f"studio-guidance-user-{uuid4()}"
    fixture = _create_short_video_fixture(client, user_id)

    response = client.get(
        f"/api/v1/studio/workflows/{fixture['workflow_id']}/snapshot",
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    guidance = response.json()["guidance"]
    assert guidance["current_stage"] == "episode"
    assert [stage["id"] for stage in guidance["stages"]] == ["content", "bible", "episode", "draft", "review"]
    assert guidance["next_action"]["code"] == "apply_asset_locks"
    assert guidance["next_action"]["reason"]
    assert guidance["next_action"]["risk"] in {"safe", "navigation", "confirm", "production"}
    assert guidance["next_action"]["source_issue_code"] == "missing_asset_locks"
    assert guidance["blocker_count"] >= 1


def test_studio_guidance_review_action_uses_review_endpoint_metadata() -> None:
    guidance = build_studio_guidance(
        workflow={"id": "workflow-review", "novel_id": "novel-1", "chapter_id": "chapter-1"},
        story_context={"novel": {"title": "测试小说"}, "chapter": {"title": "第一集"}},
        story_bible={"id": "story-bible-1"},
        production_bible_summary={"readiness_score": 90},
        production={"shot_count": 3, "asset_lock_coverage": 1},
        timeline={"clip_count": 3},
        issues=[],
        actions=[],
        mode_policy={
            "mode": "production",
            "blocking_issue_count": 1,
            "confirmable_issue_count": 0,
            "bypassed_issue_count": 0,
        },
    )

    assert guidance["current_stage"] == "review"
    assert guidance["next_action"]["code"] == "create_review"
    assert guidance["next_action"]["execution"] == "review"
    assert guidance["next_action"]["method"] == "POST"
    assert guidance["next_action"]["endpoint"] == "/studio/workflows/workflow-review/review"


def test_studio_guidance_producer_href_preserves_workflow_context() -> None:
    guidance = build_studio_guidance(
        workflow={"id": "workflow-draft", "novel_id": "novel-1", "chapter_id": "chapter-1"},
        story_context={"novel": {"title": "测试小说"}, "chapter": {"title": "第一集"}},
        story_bible={"id": "story-bible-1"},
        production_bible_summary={"readiness_score": 90},
        production={"shot_count": 3, "asset_lock_coverage": 1},
        timeline={},
        issues=[],
        actions=[],
        mode_policy={
            "mode": "production",
            "blocking_issue_count": 0,
            "confirmable_issue_count": 0,
            "bypassed_issue_count": 0,
        },
    )

    assert guidance["current_stage"] == "draft"
    assert guidance["next_action"]["code"] == "open_producer"
    assert "workflow_id=workflow-draft" in guidance["next_action"]["href"]
    assert "novel_id=novel-1" in guidance["next_action"]["href"]
    assert "chapter_id=chapter-1" in guidance["next_action"]["href"]
