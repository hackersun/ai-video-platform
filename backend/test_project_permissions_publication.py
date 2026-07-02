"""
Project member permissions and local publication tests.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import SyncSessionLocal
from app.models.synthesis_job import SynthesisJob
from init_db import init_db
from main import app


@pytest.fixture(scope="module", autouse=True)
def _init_database() -> None:
    init_db()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DEV_MODE", "true")
    return TestClient(app)


def _auth_headers(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


def _create_project(client: TestClient, owner_id: str, name: str) -> str:
    response = client.post(
        "/api/v1/projects",
        json={"name": name, "description": "permission test"},
        headers=_auth_headers(owner_id),
    )
    assert response.status_code == 201
    return response.json()["id"]


def _add_member(client: TestClient, owner_id: str, project_id: str, member_id: str, role: str) -> None:
    response = client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"user_id": member_id, "role": role},
        headers=_auth_headers(owner_id),
    )
    assert response.status_code == 201


def _insert_synthesis_job(job: SynthesisJob) -> None:
    with SyncSessionLocal() as db:
        db.merge(job)
        db.commit()


def test_project_members_can_read_project_and_owner_can_manage_roles(client: TestClient) -> None:
    owner_id = "perm-owner-read"
    viewer_id = "perm-viewer-read"
    editor_id = "perm-editor-read"
    project_id = _create_project(client, owner_id, "Permission Read Project")
    _add_member(client, owner_id, project_id, viewer_id, "viewer")
    _add_member(client, owner_id, project_id, editor_id, "editor")

    detail_response = client.get(f"/api/v1/projects/{project_id}", headers=_auth_headers(viewer_id))
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == project_id

    list_response = client.get("/api/v1/projects", headers=_auth_headers(viewer_id))
    assert list_response.status_code == 200
    assert project_id in {item["id"] for item in list_response.json()}

    members_response = client.get(f"/api/v1/projects/{project_id}/members", headers=_auth_headers(viewer_id))
    assert members_response.status_code == 200
    assert {member["user_id"] for member in members_response.json()} >= {owner_id, viewer_id, editor_id}

    viewer_update = client.put(
        f"/api/v1/projects/{project_id}",
        json={"description": "viewer should not update"},
        headers=_auth_headers(viewer_id),
    )
    assert viewer_update.status_code == 404

    editor_update = client.put(
        f"/api/v1/projects/{project_id}",
        json={"description": "editor can update"},
        headers=_auth_headers(editor_id),
    )
    assert editor_update.status_code == 200
    assert editor_update.json()["description"] == "editor can update"

    role_response = client.put(
        f"/api/v1/projects/{project_id}/members/{viewer_id}",
        json={"role": "editor"},
        headers=_auth_headers(owner_id),
    )
    assert role_response.status_code == 200
    assert role_response.json()["role"] == "editor"

    remove_response = client.delete(
        f"/api/v1/projects/{project_id}/members/{viewer_id}",
        headers=_auth_headers(owner_id),
    )
    assert remove_response.status_code == 204

    removed_detail = client.get(f"/api/v1/projects/{project_id}", headers=_auth_headers(viewer_id))
    assert removed_detail.status_code == 404


def test_project_owner_cannot_be_demoted_or_removed(client: TestClient) -> None:
    owner_id = "perm-owner-protect"
    project_id = _create_project(client, owner_id, "Owner Protected Project")

    demote_response = client.put(
        f"/api/v1/projects/{project_id}/members/{owner_id}",
        json={"role": "editor"},
        headers=_auth_headers(owner_id),
    )
    assert demote_response.status_code == 400

    remove_response = client.delete(
        f"/api/v1/projects/{project_id}/members/{owner_id}",
        headers=_auth_headers(owner_id),
    )
    assert remove_response.status_code == 400


def test_publish_creates_local_export_without_cloud_keys(client: TestClient) -> None:
    owner_id = "publish-owner"
    project_id = _create_project(client, owner_id, "Publish Project")
    synthesis_job_id = f"publish-final-{uuid4()}"

    _insert_synthesis_job(
        SynthesisJob(
            id=synthesis_job_id,
            user_id=owner_id,
            project_id=project_id,
            title="Local Export Source",
            model_id="ffmpeg-local",
            model_name="Local Final Render",
            video_url="https://example.com/source.mp4",
            audio_url="https://example.com/audio.mp3",
            status="succeeded",
            progress=100,
            output_url="/static/exports/local-final.mp4",
            extra_data={
                "render_status": "rendered",
                "render_backend": "ffmpeg_local",
                "output_kind": "final_video",
            },
        )
    )

    publish_response = client.post(
        "/api/v1/synthesis/publish",
        json={
            "synthesis_job_id": synthesis_job_id,
            "metadata": {"channel": "local-test"},
        },
        headers=_auth_headers(owner_id),
    )
    assert publish_response.status_code == 201
    payload = publish_response.json()
    assert payload["provider"] == "local"
    assert payload["synthesis_job_id"] == synthesis_job_id
    assert payload["video_url"] == "/static/exports/local-final.mp4"
    assert payload["visibility"] == "private"
    assert payload["export_url"].startswith("/static/exports/")

    artifact_path = Path(__file__).resolve().parent / payload["export_url"].lstrip("/")
    assert artifact_path.exists()
    assert "local-test" in artifact_path.read_text(encoding="utf-8")


def test_publish_rejects_dev_create_placeholder_without_final_render_status(client: TestClient) -> None:
    owner_id = "publish-dev-placeholder-owner"
    project_id = _create_project(client, owner_id, "Publish Dev Placeholder Project")

    synthesis_response = client.post(
        "/api/v1/synthesis/create",
        json={
            "project_id": project_id,
            "video_url": "https://example.com/source.mp4",
            "audio_url": "https://example.com/audio.mp3",
            "title": "DEV Placeholder Source",
        },
        headers=_auth_headers(owner_id),
    )
    assert synthesis_response.status_code == 200
    assert synthesis_response.json()["output_url"].endswith(".mp4")

    publish_response = client.post(
        "/api/v1/synthesis/publish",
        json={"synthesis_job_id": synthesis_response.json()["id"]},
        headers=_auth_headers(owner_id),
    )

    assert publish_response.status_code == 422
    detail = publish_response.json()["detail"]
    assert detail["code"] == "publication_not_ready"
    assert detail["action"] == "render_final_video"
    assert any(issue["code"] == "render_status_not_rendered" for issue in detail["issues"])


def test_publish_rejects_job_without_final_render_output(client: TestClient) -> None:
    owner_id = "publish-missing-output-owner"
    synthesis_job_id = f"publish-missing-output-{uuid4()}"
    _insert_synthesis_job(
        SynthesisJob(
            id=synthesis_job_id,
            user_id=owner_id,
            title="Source Clip Only",
            model_id="ffmpeg-cloud",
            model_name="Cloud Render",
            video_url="https://example.com/source-only.mp4",
            status="pending",
            progress=20,
            output_url=None,
            extra_data={"render_status": "adapter_ready", "render_backend": "ffmpeg_cloud"},
        )
    )

    response = client.post(
        "/api/v1/synthesis/publish",
        json={"synthesis_job_id": synthesis_job_id},
        headers=_auth_headers(owner_id),
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "publication_not_ready"
    assert "最终成片" in detail["message"]
    assert detail["action"] == "wait_cloud_render"


def test_publish_rejects_local_review_package_preview_output(client: TestClient) -> None:
    owner_id = "publish-preview-package-owner"
    synthesis_job_id = f"publish-preview-package-{uuid4()}"
    _insert_synthesis_job(
        SynthesisJob(
            id=synthesis_job_id,
            user_id=owner_id,
            title="Local Review Package",
            model_id="local-render",
            model_name="Local Review Package",
            video_url="https://example.com/source.mp4",
            audio_url="https://example.com/source.mp3",
            status="succeeded",
            progress=100,
            output_url="/static/exports/render-preview.html",
            extra_data={
                "render_status": "rendered",
                "render_backend": "local_artifact_package",
                "output_kind": "preview_package",
                "is_publishable": False,
                "render_artifacts": {
                    "preview_url": "/static/exports/render-preview.html",
                    "srt_url": "/static/exports/render.srt",
                    "timeline_url": "/static/exports/render-timeline.json",
                    "render_manifest_url": "/static/exports/render-manifest.json",
                },
            },
        )
    )

    response = client.post(
        "/api/v1/synthesis/publish",
        json={"synthesis_job_id": synthesis_job_id},
        headers=_auth_headers(owner_id),
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "publication_not_ready"
    assert detail["action"] == "render_final_video"
    assert detail["render_status"] == "rendered"
    assert any(issue["code"] == "preview_package_not_publishable" for issue in detail["issues"])


def test_publish_rejects_cloud_render_until_final_video_ready(client: TestClient) -> None:
    owner_id = "publish-cloud-pending-owner"
    synthesis_job_id = f"publish-cloud-pending-{uuid4()}"
    _insert_synthesis_job(
        SynthesisJob(
            id=synthesis_job_id,
            user_id=owner_id,
            title="Cloud Render Pending",
            model_id="ffmpeg-cloud",
            model_name="Cloud Render",
            video_url="https://example.com/source.mp4",
            status="pending",
            progress=20,
            output_url=None,
            extra_data={
                "render_status": "cloud_pending",
                "render_backend": "ffmpeg_cloud",
                "output_kind": "cloud_request",
                "is_publishable": False,
                "render_artifacts": {
                    "render_manifest_url": "/static/exports/cloud-render-manifest.json",
                    "srt_url": "/static/exports/cloud-render.srt",
                    "timeline_url": "/static/exports/cloud-render-timeline.json",
                },
            },
        )
    )

    response = client.post(
        "/api/v1/synthesis/publish",
        json={"synthesis_job_id": synthesis_job_id},
        headers=_auth_headers(owner_id),
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "publication_not_ready"
    assert detail["action"] == "wait_cloud_render"
    assert detail["render_status"] == "cloud_pending"
    assert any(issue["code"] == "final_video_missing" for issue in detail["issues"])


def test_publish_rejects_metadata_only_preview_package(client: TestClient) -> None:
    owner_id = "publish-metadata-preview-owner"
    response = client.post(
        "/api/v1/synthesis/publish",
        json={
            "title": "Metadata Preview Package",
            "metadata": {
                "source_output_url": "/static/exports/render-preview.html",
                "render_status": "rendered",
                "render_backend": "local_artifact_package",
                "output_kind": "preview_package",
            },
        },
        headers=_auth_headers(owner_id),
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "publication_not_ready"
    assert detail["render_status"] == "rendered"
    assert detail["output_kind"] == "preview_package"
    assert any(issue["code"] == "preview_package_not_publishable" for issue in detail["issues"])


def test_publish_allows_cloud_render_final_video_and_preserves_provenance(client: TestClient) -> None:
    owner_id = "publish-cloud-final-owner"
    synthesis_job_id = f"publish-cloud-final-{uuid4()}"
    render_artifacts = {
        "render_manifest_url": "/static/exports/cloud-final-manifest.json",
        "srt_url": "/static/exports/cloud-final.srt",
        "timeline_url": "/static/exports/cloud-final-timeline.json",
        "source_manifest_url": "/static/exports/source-sequence.json",
    }
    _insert_synthesis_job(
        SynthesisJob(
            id=synthesis_job_id,
            user_id=owner_id,
            title="Cloud Render Final",
            model_id="ffmpeg-cloud",
            model_name="Cloud Render",
            video_url="https://example.com/source.mp4",
            audio_url="https://example.com/source.mp3",
            status="succeeded",
            progress=100,
            output_url="https://cdn.example.com/final-episode.mp4",
            duration_seconds=18.0,
            extra_data={
                "render_status": "rendered",
                "render_backend": "ffmpeg_cloud",
                "output_kind": "final_video",
                "is_publishable": True,
                "render_artifacts": render_artifacts,
                "cloud_render_task_id": "cloud-task-final",
            },
        )
    )

    publish_response = client.post(
        "/api/v1/synthesis/publish",
        json={"synthesis_job_id": synthesis_job_id, "metadata": {"channel": "cloud-final"}},
        headers=_auth_headers(owner_id),
    )

    assert publish_response.status_code == 201
    payload = publish_response.json()
    assert payload["video_url"] == "https://cdn.example.com/final-episode.mp4"
    assert payload["metadata"]["is_publishable"] is True
    assert payload["metadata"]["output_kind"] == "final_video"
    assert payload["metadata"]["render_backend"] == "ffmpeg_cloud"
    assert payload["metadata"]["render_manifest_url"] == render_artifacts["render_manifest_url"]


def test_publish_export_preserves_render_artifact_provenance(client: TestClient) -> None:
    owner_id = "publish-provenance-owner"
    synthesis_job_id = f"publish-provenance-{uuid4()}"
    render_artifacts = {
        "preview_url": "/static/exports/render-preview.html",
        "srt_url": "/static/exports/render-subtitles.srt",
        "timeline_url": "/static/exports/render-timeline.json",
        "render_manifest_url": "/static/exports/render-manifest.json",
        "source_manifest_url": "/static/exports/source-sequence.json",
    }
    _insert_synthesis_job(
        SynthesisJob(
            id=synthesis_job_id,
            user_id=owner_id,
            title="Rendered Episode",
            model_id="local-render",
            model_name="Local Render",
            video_url="https://example.com/source.mp4",
            audio_url="https://example.com/source.mp3",
            status="succeeded",
            progress=100,
            output_url="/static/exports/final-render.mp4",
            duration_seconds=12.5,
            extra_data={
                "render_status": "rendered",
                "render_backend": "ffmpeg_local",
                "render_source": "timeline",
                "render_timeline_id": "timeline-001",
                "manifest_url": "/static/exports/source-sequence.json",
                "render_artifacts": render_artifacts,
            },
        )
    )

    publish_response = client.post(
        "/api/v1/synthesis/publish",
        json={"synthesis_job_id": synthesis_job_id, "metadata": {"channel": "trace-test"}},
        headers=_auth_headers(owner_id),
    )

    assert publish_response.status_code == 201
    payload = publish_response.json()
    publication_metadata = payload["metadata"]
    assert payload["video_url"] == "/static/exports/final-render.mp4"
    assert publication_metadata["source_output_url"] == "/static/exports/final-render.mp4"
    assert publication_metadata["render_artifacts"] == render_artifacts
    assert publication_metadata["render_manifest_url"] == render_artifacts["render_manifest_url"]
    assert publication_metadata["timeline_url"] == render_artifacts["timeline_url"]
    assert publication_metadata["srt_url"] == render_artifacts["srt_url"]
    assert publication_metadata["preview_url"] == render_artifacts["preview_url"]
    assert publication_metadata["source_manifest_url"] == render_artifacts["source_manifest_url"]
    assert publication_metadata["render_status"] == "rendered"
    assert publication_metadata["render_backend"] == "ffmpeg_local"
    assert publication_metadata["render_source"] == "timeline"
    assert publication_metadata["timeline_id"] == "timeline-001"

    artifact_path = Path(__file__).resolve().parent / payload["export_url"].lstrip("/")
    artifact_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact_payload["render_artifacts"] == render_artifacts
    assert artifact_payload["timeline_url"] == render_artifacts["timeline_url"]


def test_execute_synthesis_persists_source_and_output_video_urls(client: TestClient) -> None:
    owner_id = "publish-execute-owner"
    response = client.post(
        "/api/v1/synthesis/execute",
        json={
            "video_urls": ["https://example.com/input.mp4"],
            "audio_urls": ["https://example.com/input.mp3"],
            "title": "Execute Synthesis Source",
            "output_format": "mp4",
            "quality": "medium",
        },
        headers=_auth_headers(owner_id),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "succeeded"
    assert payload["video_url"].startswith("/static/")

    job_response = client.get(
        f"/api/v1/synthesis/jobs/{payload['job_id']}",
        headers=_auth_headers(owner_id),
    )
    assert job_response.status_code == 200
    job = job_response.json()
    assert job["video_url"] == "https://example.com/input.mp4"
    assert job["output_url"] == payload["video_url"]


def test_publication_list_update_revoke_and_archive(client: TestClient) -> None:
    owner_id = "publish-manage-owner"
    project_id = _create_project(client, owner_id, "Publication Manage Project")
    synthesis_job_id = f"publish-manage-{uuid4()}"

    _insert_synthesis_job(
        SynthesisJob(
            id=synthesis_job_id,
            user_id=owner_id,
            project_id=project_id,
            title="Manage Export Source",
            model_id="ffmpeg-local",
            model_name="Local Final Render",
            video_url="https://example.com/manage-source.mp4",
            audio_url="https://example.com/manage-audio.mp3",
            status="succeeded",
            progress=100,
            output_url="/static/exports/manage-final.mp4",
            extra_data={
                "render_status": "rendered",
                "render_backend": "ffmpeg_local",
                "output_kind": "final_video",
            },
        )
    )

    publish_response = client.post(
        "/api/v1/synthesis/publish",
        json={"synthesis_job_id": synthesis_job_id, "metadata": {"channel": "draft"}},
        headers=_auth_headers(owner_id),
    )
    assert publish_response.status_code == 201
    publication = publish_response.json()
    publication_id = publication["id"]

    list_response = client.get("/api/v1/synthesis/publications", headers=_auth_headers(owner_id))
    assert list_response.status_code == 200
    assert any(item["id"] == publication_id for item in list_response.json())

    detail_response = client.get(
        f"/api/v1/synthesis/publications/{publication_id}",
        headers=_auth_headers(owner_id),
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["synthesis_job_id"] == synthesis_job_id

    update_response = client.put(
        f"/api/v1/synthesis/publications/{publication_id}",
        json={"title": "正式发布版本", "status": "published", "metadata": {"channel": "bilibili"}},
        headers=_auth_headers(owner_id),
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["title"] == "正式发布版本"
    assert updated["status"] == "published"
    assert updated["metadata"]["metadata"]["channel"] == "bilibili"

    revoke_response = client.post(
        f"/api/v1/synthesis/publications/{publication_id}/revoke",
        headers=_auth_headers(owner_id),
    )
    assert revoke_response.status_code == 200
    assert revoke_response.json()["status"] == "revoked"

    delete_response = client.delete(
        f"/api/v1/synthesis/publications/{publication_id}",
        headers=_auth_headers(owner_id),
    )
    assert delete_response.status_code == 200

    default_list = client.get("/api/v1/synthesis/publications", headers=_auth_headers(owner_id))
    assert default_list.status_code == 200
    assert all(item["id"] != publication_id for item in default_list.json())

    archived_list = client.get("/api/v1/synthesis/publications?status=archived", headers=_auth_headers(owner_id))
    assert archived_list.status_code == 200
    assert any(item["id"] == publication_id for item in archived_list.json())

    archived_detail = client.get(
        f"/api/v1/synthesis/publications/{publication_id}",
        headers=_auth_headers(owner_id),
    )
    assert archived_detail.status_code == 200
    assert archived_detail.json()["status"] == "archived"


def test_publish_from_metadata_requires_project_membership(client: TestClient) -> None:
    owner_id = "publish-access-owner"
    other_id = "publish-access-other"
    project_id = _create_project(client, owner_id, "Publish Access Project")

    response = client.post(
        "/api/v1/synthesis/publish",
        json={"project_id": project_id, "title": "Blocked Export", "metadata": {"source_output_url": "/x.mp4"}},
        headers=_auth_headers(other_id),
    )
    assert response.status_code == 404
