"""
Tests for Story Bible auto-build, sync and consistency check.
"""

from __future__ import annotations

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


def auth_headers(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


def test_generate_story_bible_from_novel(client: TestClient) -> None:
    """Test generating Story Bible from novel chapters."""
    user_id = "story-bible-test-user"
    content = """# 星港纪事

角色：林舟
角色：小月
场景：星港
场景：暗巷
道具：青铜钥匙
事件：抵达星港

第一章 初到星港
林舟握着青铜钥匙抵达星港。他发现旧港口爆发异光。
小月在港口等候。

第二章 暗巷追踪
林舟进入暗巷，遭遇守夜人。
""".encode("utf-8")

    # Import novel
    preview_resp = client.post(
        "/api/v1/novels/import/preview",
        files={"file": ("test-novel.md", content, "text/markdown")},
        headers=auth_headers(user_id),
    )
    assert preview_resp.status_code == 201
    job_id = preview_resp.json()["id"]

    confirm_resp = client.post(
        "/api/v1/novels/import/confirm",
        json={"job_id": job_id, "genre": "科幻"},
        headers=auth_headers(user_id),
    )
    assert confirm_resp.status_code == 201
    novel = confirm_resp.json()
    novel_id = novel["id"]

    # Generate Story Bible
    generate_resp = client.post(
        "/api/v1/story-bibles/generate-from-novel",
        json={
            "novel_id": novel_id,
            "title": "星港纪事 Story Bible",
            "style": "anime",
        },
        headers=auth_headers(user_id),
    )
    assert generate_resp.status_code == 201
    story_bible = generate_resp.json()
    assert story_bible["title"] == "星港纪事 Story Bible"
    assert story_bible["novel_id"] == novel_id
    assert "character_rules" in story_bible
    assert "scene_rules" in story_bible
    story_bible_id = story_bible["id"]

    # Check consistency
    check_resp = client.post(
        "/api/v1/story-bibles/check-consistency",
        json={"story_bible_id": story_bible_id},
        headers=auth_headers(user_id),
    )
    assert check_resp.status_code == 200
    result = check_resp.json()
    assert "issues" in result
    assert "checked_entity_count" in result


def test_sync_story_bible_from_chapter(client: TestClient) -> None:
    """Test incremental sync from chapter."""
    user_id = "story-bible-sync-user"
    content = """# 测试小说

角色：张三
场景：城市

第一章
张三来到城市，发现神秘事件。
""".encode("utf-8")

    # Import novel
    preview_resp = client.post(
        "/api/v1/novels/import/preview",
        files={"file": ("sync-test.md", content, "text/markdown")},
        headers=auth_headers(user_id),
    )
    assert preview_resp.status_code == 201
    job_id = preview_resp.json()["id"]

    confirm_resp = client.post(
        "/api/v1/novels/import/confirm",
        json={"job_id": job_id},
        headers=auth_headers(user_id),
    )
    assert confirm_resp.status_code == 201
    novel = confirm_resp.json()
    novel_id = novel["id"]

    # Create Story Bible manually
    create_resp = client.post(
        "/api/v1/story-bibles",
        json={
            "novel_id": novel_id,
            "title": "测试 Story Bible",
            "character_rules": [],
            "scene_rules": [],
        },
        headers=auth_headers(user_id),
    )
    assert create_resp.status_code == 201
    story_bible = create_resp.json()
    story_bible_id = story_bible["id"]

    # Sync from chapter
    chapters = client.get(f"/api/v1/chapters/novel/{novel_id}", headers=auth_headers(user_id)).json()
    assert len(chapters) > 0
    chapter_id = chapters[0]["id"]

    sync_resp = client.post(
        "/api/v1/story-bibles/sync-from-chapter",
        json={
            "story_bible_id": story_bible_id,
            "chapter_id": chapter_id,
        },
        headers=auth_headers(user_id),
    )
    assert sync_resp.status_code == 200
    updated_bible = sync_resp.json()
    # Should have synced entities
    assert "character_rules" in updated_bible or "scene_rules" in updated_bible


def test_resolve_conflict(client: TestClient) -> None:
    """Test conflict resolution endpoint exists and handles requests."""
    user_id = "story-bible-conflict-user"
    content = "# 测试\n\n角色：李四\n\n第一章\n李四出现。".encode("utf-8")

    # Import novel
    preview_resp = client.post(
        "/api/v1/novels/import/preview",
        files={"file": ("conflict-test.md", content, "text/markdown")},
        headers=auth_headers(user_id),
    )
    assert preview_resp.status_code == 201

    confirm_resp = client.post(
        "/api/v1/novels/import/confirm",
        json={"job_id": preview_resp.json()["id"]},
        headers=auth_headers(user_id),
    )
    novel_id = confirm_resp.json()["id"]

    # Generate Story Bible
    generate_resp = client.post(
        "/api/v1/story-bibles/generate-from-novel",
        json={"novel_id": novel_id, "title": "冲突测试 Bible"},
        headers=auth_headers(user_id),
    )
    assert generate_resp.status_code == 201
    story_bible_id = generate_resp.json()["id"]

    # Try to resolve non-existent conflict (should return 404)
    resolve_resp = client.post(
        "/api/v1/story-bibles/resolve-conflict",
        json={
            "story_bible_id": story_bible_id,
            "issue_code": "nonexistent_conflict",
            "resolution": "accept_incoming",
        },
        headers=auth_headers(user_id),
    )
    assert resolve_resp.status_code == 404


def test_story_bible_crud(client: TestClient) -> None:
    """Test basic Story Bible CRUD operations."""
    user_id = "story-bible-crud-user"

    # Create
    create_resp = client.post(
        "/api/v1/story-bibles",
        json={
            "title": "我的 Story Bible",
            "style": "anime",
            "character_rules": [{"name": "测试角色"}],
        },
        headers=auth_headers(user_id),
    )
    assert create_resp.status_code == 201
    bible = create_resp.json()
    assert bible["title"] == "我的 Story Bible"
    story_bible_id = bible["id"]

    # List
    list_resp = client.get("/api/v1/story-bibles", headers=auth_headers(user_id))
    assert list_resp.status_code == 200
    assert any(sb["id"] == story_bible_id for sb in list_resp.json())

    # Get single
    get_resp = client.get(f"/api/v1/story-bibles/{story_bible_id}", headers=auth_headers(user_id))
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == story_bible_id

    # Update
    update_resp = client.put(
        f"/api/v1/story-bibles/{story_bible_id}",
        json={"title": "更新后的标题"},
        headers=auth_headers(user_id),
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["title"] == "更新后的标题"

    # Delete
    delete_resp = client.delete(f"/api/v1/story-bibles/{story_bible_id}", headers=auth_headers(user_id))
    assert delete_resp.status_code == 200

    # Verify deleted
    get_after_delete = client.get(f"/api/v1/story-bibles/{story_bible_id}", headers=auth_headers(user_id))
    assert get_after_delete.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])