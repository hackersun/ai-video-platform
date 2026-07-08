"""
Tests for novel import, entity extraction and Story Bible automation.
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


def test_import_preview_confirm_and_job_detail(client: TestClient) -> None:
    user_id = "novel-import-user"
    content = """# 星港纪事

角色：林舟
场景：星港

第一章 初到星港
林舟握着青铜钥匙抵达星港。他发现旧港口爆发异光。

第二章 暗巷追踪
林舟进入暗巷，遭遇守夜人。
""".encode("utf-8")

    preview_resp = client.post(
        "/api/v1/novels/import/preview",
        files={"file": ("star-port.md", content, "text/markdown")},
        headers=auth_headers(user_id),
    )
    assert preview_resp.status_code == 201
    preview = preview_resp.json()
    assert preview["status"] == "previewed"
    assert preview["title"] == "星港纪事"
    assert preview["chapter_count"] == 2
    assert preview["chapters"][0]["title"] == "第一章 初到星港"
    job_id = preview["id"]

    detail_resp = client.get(f"/api/v1/novels/import/jobs/{job_id}", headers=auth_headers(user_id))
    assert detail_resp.status_code == 200
    assert detail_resp.json()["id"] == job_id

    list_resp = client.get("/api/v1/novels/import/jobs", headers=auth_headers(user_id))
    assert list_resp.status_code == 200
    assert any(item["id"] == job_id for item in list_resp.json())

    confirm_resp = client.post(
        "/api/v1/novels/import/confirm",
        json={"job_id": job_id, "genre": "科幻", "tags": ["星港"]},
        headers=auth_headers(user_id),
    )
    assert confirm_resp.status_code == 201
    novel = confirm_resp.json()
    assert novel["source"] == "imported"
    assert novel["genre"] == "科幻"
    assert len(novel["chapters"]) == 2
    assert novel["chapters"][1]["chapter_number"] == 2

    completed_detail = client.get(f"/api/v1/novels/import/jobs/{job_id}", headers=auth_headers(user_id)).json()
    assert completed_detail["status"] == "completed"
    assert completed_detail["novel_id"] == novel["id"]

    duplicate_resp = client.post(
        "/api/v1/novels/import/confirm",
        json={"job_id": job_id},
        headers=auth_headers(user_id),
    )
    assert duplicate_resp.status_code == 409


def test_novel_responses_expose_chapter_and_production_character_counts(client: TestClient) -> None:
    user_id = "novel-counts-user"
    novel_resp = client.post(
        "/api/v1/novels",
        json={"title": "统计口径测试", "description": "角色：许澜。场景：旧码头。"},
        headers=auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_resp = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "第一章 雨夜",
            "chapter_number": 1,
            "content": "角色：许澜\n场景：雨夜旧码头\n许澜在雨夜旧码头追查海潮钟。",
        },
        headers=auth_headers(user_id),
    )
    assert chapter_resp.status_code == 201

    detail_resp = client.get(f"/api/v1/novels/{novel_id}", headers=auth_headers(user_id))
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["chapter_count"] == 1
    assert detail["total_chapters"] == 1
    assert detail["production_character_count"] >= 1
    assert detail["character_count"] >= 1
    assert detail["story_entity_counts"]["character"] >= 1

    list_resp = client.get("/api/v1/novels", headers=auth_headers(user_id))
    assert list_resp.status_code == 200
    listed = next(item for item in list_resp.json() if item["id"] == novel_id)
    assert listed["chapter_count"] == 1
    assert listed["production_character_count"] >= 1


def test_import_job_update_retry_and_archive(client: TestClient) -> None:
    user_id = "novel-import-manage-user"
    content = """# 雾城来信

第一章 雾灯
角色：许澜
场景：雾城码头
许澜收到一封没有署名的信。
""".encode("utf-8")

    preview_resp = client.post(
        "/api/v1/novels/import/preview",
        files={"file": ("fog-city.md", content, "text/markdown")},
        headers=auth_headers(user_id),
    )
    assert preview_resp.status_code == 201
    job_id = preview_resp.json()["id"]

    update_resp = client.put(
        f"/api/v1/novels/import/jobs/{job_id}",
        json={"title": "雾城来信修订版", "status": "failed", "error_message": "人工标记失败"},
        headers=auth_headers(user_id),
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["title"] == "雾城来信修订版"
    assert updated["status"] == "failed"
    assert updated["error_message"] == "人工标记失败"

    retry_resp = client.post(f"/api/v1/novels/import/jobs/{job_id}/retry", headers=auth_headers(user_id))
    assert retry_resp.status_code == 200
    retried = retry_resp.json()
    assert retried["status"] == "previewed"
    assert retried["error_message"] is None

    delete_resp = client.delete(f"/api/v1/novels/import/jobs/{job_id}", headers=auth_headers(user_id))
    assert delete_resp.status_code == 200
    archived = client.get(f"/api/v1/novels/import/jobs/{job_id}", headers=auth_headers(user_id)).json()
    assert archived["status"] == "archived"


def test_import_preview_rejects_unsupported_extension(client: TestClient) -> None:
    response = client.post(
        "/api/v1/novels/import/preview",
        files={"file": ("story.pdf", b"not supported", "application/pdf")},
        headers=auth_headers("novel-import-invalid-user"),
    )
    assert response.status_code == 400


def test_entity_extraction_persists_without_cloud_keys(client: TestClient) -> None:
    response = client.post(
        "/api/v1/story-bibles/entities/extract",
        json={
            "text": "角色：林舟\n场景：玄都城\n道具：青铜钥匙\n事件：林舟发现城门爆发异光",
            "persist": True,
        },
        headers=auth_headers("entity-user"),
    )
    assert response.status_code == 200
    payload = response.json()
    by_type = {entity["entity_type"]: entity for entity in payload["entities"]}
    assert by_type["character"]["name"] == "林舟"
    assert by_type["scene"]["name"] == "玄都城"
    assert by_type["prop"]["name"] == "青铜钥匙"
    assert by_type["event"]["name"] == "林舟发现城门爆发异光"
    assert all(entity["source"] == "deterministic" for entity in payload["entities"])


def test_entity_extraction_persists_production_metadata_for_consistency(client: TestClient) -> None:
    user_id = "entity-production-metadata-user"
    novel_resp = client.post(
        "/api/v1/novels",
        json={"title": "生产元数据测试", "description": "用于验证实体契约。"},
        headers=auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    response = client.post(
        "/api/v1/story-bibles/entities/extract",
        json={
            "novel_id": novel_id,
            "text": (
                "角色：许澜\n"
                "场景：雨夜旧码头\n"
                "道具：银色工具包\n"
                "许澜握紧银色工具包，在雨夜旧码头追查失控的海潮钟。"
            ),
            "persist": True,
        },
        headers=auth_headers(user_id),
    )

    assert response.status_code == 200
    entities = response.json()["entities"]
    by_type = {entity["entity_type"]: entity for entity in entities}

    character_attrs = by_type["character"]["attributes"]
    assert character_attrs["visual_dna"]["identity_anchor"] == "许澜"
    assert character_attrs["reference_requirements"]["character_multiview"] == ["front", "side", "back"]

    scene_attrs = by_type["scene"]["attributes"]
    assert "室外" in scene_attrs["scene_tags"]
    assert scene_attrs["scene_dna"]["weather"]
    assert scene_attrs["scene_dna"]["lighting"]

    prop_entity = next(entity for entity in entities if entity["entity_type"] == "prop" and entity["name"] == "银色工具包")
    prop_attrs = prop_entity["attributes"]
    assert prop_attrs["prop_dna"]["identity_anchor"] == "银色工具包"
    assert prop_attrs["reference_requirements"]["prop_multiview"] == ["main", "detail", "scale"]

    consistency_resp = client.post(
        "/api/v1/story-bibles/entities/check-consistency",
        json={"novel_id": novel_id},
        headers=auth_headers(user_id),
    )
    assert consistency_resp.status_code == 200
    issue_codes = {issue["code"] for issue in consistency_resp.json()["issues"]}
    assert "missing_character_views" not in issue_codes
    assert "missing_scene_tags" not in issue_codes
    assert "missing_prop_dna" not in issue_codes


def test_story_entity_crud_management(client: TestClient) -> None:
    user_id = "entity-crud-user"
    novel_resp = client.post(
        "/api/v1/novels",
        json={"title": "实体管理测试", "description": "用于验证实体 CRUD"},
        headers=auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_resp = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "第一章",
            "chapter_number": 1,
            "content": "场景：旧图书馆\n道具：银色书签",
        },
        headers=auth_headers(user_id),
    )
    assert chapter_resp.status_code == 201
    chapter_id = chapter_resp.json()["id"]

    create_resp = client.post(
        "/api/v1/story-bibles/entities",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "entity_type": "scene",
            "name": "旧图书馆",
            "description": "藏有禁书的城市图书馆",
            "aliases": ["老馆"],
            "attributes": {"lighting": "warm"},
            "evidence": "场景：旧图书馆",
        },
        headers=auth_headers(user_id),
    )
    assert create_resp.status_code == 201
    entity = create_resp.json()
    entity_id = entity["id"]
    assert entity["entity_type"] == "scene"

    list_resp = client.get(
        f"/api/v1/story-bibles/entities?novel_id={novel_id}&entity_type=scene",
        headers=auth_headers(user_id),
    )
    assert list_resp.status_code == 200
    assert any(item["id"] == entity_id for item in list_resp.json())

    update_resp = client.put(
        f"/api/v1/story-bibles/entities/{entity_id}",
        json={"name": "旧城图书馆", "entity_type": "prop", "attributes": {"material": "paper"}},
        headers=auth_headers(user_id),
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["name"] == "旧城图书馆"
    assert updated["entity_type"] == "prop"
    assert updated["attributes"]["material"] == "paper"

    delete_resp = client.delete(f"/api/v1/story-bibles/entities/{entity_id}", headers=auth_headers(user_id))
    assert delete_resp.status_code == 200
    missing_resp = client.get(f"/api/v1/story-bibles/entities/{entity_id}", headers=auth_headers(user_id))
    assert missing_resp.status_code == 404


def test_story_bible_generate_sync_and_consistency(client: TestClient) -> None:
    user_id = "story-bible-automation-user"
    novel_resp = client.post(
        "/api/v1/novels",
        json={"title": "玄都纪", "description": "灵气复苏后的山海城邦"},
        headers=auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_resp = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "第一章",
            "chapter_number": 1,
            "content": "角色：林舟\n场景：玄都城\n道具：玉佩\n林舟发现玄都城爆发灵潮。",
        },
        headers=auth_headers(user_id),
    )
    assert chapter_resp.status_code == 201
    chapter_id = chapter_resp.json()["id"]

    generate_resp = client.post(
        "/api/v1/story-bibles/generate-from-novel",
        json={"novel_id": novel_id, "style": "赛璐璐动画"},
        headers=auth_headers(user_id),
    )
    assert generate_resp.status_code == 201
    bible = generate_resp.json()
    story_bible_id = bible["id"]
    assert bible["novel_id"] == novel_id
    assert any(item["name"] == "林舟" for item in bible["character_rules"])
    assert any(item["name"] == "玄都城" for item in bible["scene_rules"])
    assert bible["extra_data"]["state_machine"]["summary"]["characters"] >= 1
    assert bible["extra_data"]["state_machine"]["summary"]["scenes"] >= 1

    second_chapter = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "第二章",
            "chapter_number": 2,
            "content": "角色：沈眠\n场景：寒鸦谷\n道具：黑铁剑\n沈眠遭遇伏击。",
        },
        headers=auth_headers(user_id),
    )
    assert second_chapter.status_code == 201
    second_chapter_id = second_chapter.json()["id"]

    sync_resp = client.post(
        "/api/v1/story-bibles/sync-from-chapter",
        json={"story_bible_id": story_bible_id, "chapter_id": second_chapter_id},
        headers=auth_headers(user_id),
    )
    assert sync_resp.status_code == 200
    synced = sync_resp.json()
    assert any(item["name"] == "沈眠" for item in synced["character_rules"])
    assert synced["extra_data"]["last_synced_chapter_id"] == second_chapter_id

    consistent_resp = client.post(
        "/api/v1/story-bibles/check-consistency",
        json={"story_bible_id": story_bible_id, "chapter_id": chapter_id},
        headers=auth_headers(user_id),
    )
    assert consistent_resp.status_code == 200
    assert consistent_resp.json()["issue_count"] == 0

    drift_resp = client.post(
        "/api/v1/story-bibles/check-consistency",
        json={"story_bible_id": story_bible_id, "text": "角色：顾北\n场景：废都\n顾北抵达废都。"},
        headers=auth_headers(user_id),
    )
    assert drift_resp.status_code == 200
    drift = drift_resp.json()
    assert drift["issue_count"] >= 1
    assert any(issue["name"] == "顾北" for issue in drift["issues"])

    drift_issue = next(issue for issue in drift["issues"] if issue["name"] == "顾北")
    assert drift_issue["code"]

    resolve_resp = client.post(
        "/api/v1/story-bibles/resolve-conflict",
        json={
            "story_bible_id": story_bible_id,
            "issue_code": drift_issue["code"],
            "resolution": "reject_incoming",
        },
        headers=auth_headers(user_id),
    )
    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["resolved"] is True

    ignored_resp = client.post(
        "/api/v1/story-bibles/check-consistency",
        json={"story_bible_id": story_bible_id, "text": "角色：顾北\n场景：废都\n顾北抵达废都。"},
        headers=auth_headers(user_id),
    )
    assert ignored_resp.status_code == 200
    ignored = ignored_resp.json()
    assert all(issue["code"] != drift_issue["code"] for issue in ignored["issues"])
