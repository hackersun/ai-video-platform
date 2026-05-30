"""
Project member permissions and local publication tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

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

    synthesis_response = client.post(
        "/api/v1/synthesis/create",
        json={
            "project_id": project_id,
            "video_url": "https://example.com/source.mp4",
            "audio_url": "https://example.com/audio.mp3",
            "title": "Local Export Source",
        },
        headers=_auth_headers(owner_id),
    )
    assert synthesis_response.status_code == 200
    synthesis_job_id = synthesis_response.json()["id"]

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
    assert payload["export_url"].startswith("/static/exports/")

    artifact_path = Path(__file__).resolve().parent / payload["export_url"].lstrip("/")
    assert artifact_path.exists()
    assert "local-test" in artifact_path.read_text(encoding="utf-8")


def test_publication_list_update_revoke_and_archive(client: TestClient) -> None:
    owner_id = "publish-manage-owner"
    project_id = _create_project(client, owner_id, "Publication Manage Project")

    synthesis_response = client.post(
        "/api/v1/synthesis/create",
        json={
            "project_id": project_id,
            "video_url": "https://example.com/manage-source.mp4",
            "audio_url": "https://example.com/manage-audio.mp3",
            "title": "Manage Export Source",
        },
        headers=_auth_headers(owner_id),
    )
    assert synthesis_response.status_code == 200
    synthesis_job_id = synthesis_response.json()["id"]

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
