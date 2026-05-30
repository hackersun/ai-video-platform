"""
Tests for storyboard templates and smart novel/chapter generation.
"""

from __future__ import annotations

from uuid import uuid4

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


def test_storyboard_templates_are_exposed(client: TestClient) -> None:
    response = client.get("/api/v1/storyboards/templates", headers=auth_headers("template-list-user"))

    assert response.status_code == 200
    templates = response.json()
    ids = {template["id"] for template in templates}
    assert "action-sequence" in ids
    assert "anime-dialogue" in ids
    assert "opening-hook" in ids
    assert "character-entrance" in ids
    assert "cliffhanger-ending" in ids
    assert "xianxia-breakthrough" in ids
    assert "xianxia-sect-trial" in ids
    assert "wuxia-jianghu-duel" in ids
    assert "wuxia-night-infiltration" in ids
    assert "xuanhuan-secret-realm" in ids
    assert "xuanhuan-bloodline-awakening" in ids
    assert "urban-power-awakening" in ids
    assert "urban-night-chase" in ids
    assert all(template["shot_count"] >= 1 for template in templates)
    assert all(template["shot_template"]["shots"] for template in templates)


def test_system_template_override_is_listed_matched_and_used_for_generation(client: TestClient) -> None:
    user_id = f"template-override-user-{uuid4()}"
    override_resp = client.post(
        "/api/v1/assets",
        json={
            "category": "template",
            "asset_type": "text",
            "name": "定制强钩子模板",
            "description": "用户定制后的强钩子开场模板",
            "tags": ["定制钩子", "强悬念"],
            "style_tags": ["storyboard", "system_override", "system_template:opening-hook"],
            "prompt_template": "{{主角}}在{{关键场景}}发现{{关键道具}}，必须保持强悬念。",
            "shot_template": {
                "system_template_id": "opening-hook",
                "shot_count": 2,
                "template_type": "storyboard",
                "keywords": ["定制钩子", "强悬念"],
                "shots": [
                    {
                        "duration": 4,
                        "shot_type": "establishing",
                        "camera_angle": "wide",
                        "camera_movement": "zoom_in",
                        "emotion": "tense",
                        "lighting": "dramatic",
                        "color_grading": "cinematic",
                        "visual_focus": "定制钩子开场的危险信号",
                        "dialogue_role": "旁白",
                    },
                    {
                        "duration": 4,
                        "shot_type": "reaction",
                        "camera_angle": "close-up",
                        "camera_movement": "static",
                        "emotion": "surprised",
                        "lighting": "rim",
                        "color_grading": "cool",
                        "visual_focus": "主角确认定制线索后的表情",
                        "dialogue_role": "角色",
                    },
                ],
            },
            "is_public": False,
        },
        headers=auth_headers(user_id),
    )
    assert override_resp.status_code == 201

    templates_resp = client.get("/api/v1/storyboards/templates", headers=auth_headers(user_id))
    assert templates_resp.status_code == 200
    overridden = next(template for template in templates_resp.json() if template["id"] == "opening-hook")
    assert overridden["name"] == "定制强钩子模板"
    assert overridden["is_overridden"] is True
    assert overridden["override_asset_id"] == override_resp.json()["id"]
    assert overridden["shot_count"] == 2
    assert "定制钩子" in overridden["genre_tags"]

    novel_resp = client.post(
        "/api/v1/novels",
        json={"title": "模板覆盖小说", "genre": "悬疑", "description": "开局突然出现倒计时和强悬念。"},
        headers=auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]
    chapter_resp = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "倒计时",
            "chapter_number": 1,
            "content": "林澈醒来后发现墙上出现倒计时，强悬念的符号指向旧城钟楼。",
        },
        headers=auth_headers(user_id),
    )
    assert chapter_resp.status_code == 201
    chapter_id = chapter_resp.json()["id"]

    match_resp = client.post(
        "/api/v1/storyboards/templates/match",
        json={"novel_id": novel_id, "chapter_id": chapter_id, "template_id": "opening-hook"},
        headers=auth_headers(user_id),
    )
    assert match_resp.status_code == 200
    assert match_resp.json()["template"]["name"] == "定制强钩子模板"
    assert match_resp.json()["template"]["shot_count"] == 2

    generate_resp = client.post(
        "/api/v1/storyboards/generate-smart",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "template_id": "opening-hook",
            "use_ai_refine": False,
        },
        headers=auth_headers(user_id),
    )
    assert generate_resp.status_code == 201
    storyboard = generate_resp.json()
    assert storyboard["shot_count"] == 2
    assert storyboard["content"]["template_name"] == "定制强钩子模板"
    assert storyboard["shots"][0]["extra_data"]["template_name"] == "定制强钩子模板"
    assert "定制钩子开场" in storyboard["shots"][0]["visual_description"]


def test_template_match_uses_novel_chapter_content(client: TestClient) -> None:
    user_id = "template-match-user"
    novel_resp = client.post(
        "/api/v1/novels",
        json={"title": "剑影追踪", "genre": "仙侠", "description": "少年剑修追击伏兵"},
        headers=auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_resp = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "伏击",
            "chapter_number": 1,
            "content": "林舟拔剑冲入雨夜，伏兵从屋檐跃下，刀光爆闪，他一路追击敌人。",
        },
        headers=auth_headers(user_id),
    )
    assert chapter_resp.status_code == 201

    match_resp = client.post(
        "/api/v1/storyboards/templates/match",
        json={"novel_id": novel_id, "chapter_id": chapter_resp.json()["id"]},
        headers=auth_headers(user_id),
    )

    assert match_resp.status_code == 200
    payload = match_resp.json()
    assert payload["template"]["id"] == "action-sequence"
    assert payload["score"] > 0


@pytest.mark.parametrize(
    ("genre", "content", "expected_ids"),
    [
        (
            "修仙",
            "少年剑修闭关修炼，丹田灵气旋涡暴涨，本命灵剑轻鸣，雷劫压下，他即将突破境界。",
            {"xianxia-breakthrough"},
        ),
        (
            "武侠",
            "江湖客栈里刀光一闪，门派高手争夺残页秘籍，侠客施展轻功跃上擂台。",
            {"wuxia-jianghu-duel"},
        ),
        (
            "玄幻",
            "秘境入口打开，古碑和祭坛发出金蓝光，异兽守着神器与灵核，血脉继承者踏入遗迹。",
            {"xuanhuan-secret-realm"},
        ),
        (
            "都市异能",
            "城市地铁站台的监控突然失真，手机弹出异常信号，隐藏组织锁定了刚觉醒异能的少年。",
            {"urban-power-awakening"},
        ),
    ],
)
def test_genre_specific_templates_match_common_novel_elements(
    client: TestClient,
    genre: str,
    content: str,
    expected_ids: set[str],
) -> None:
    user_id = f"genre-template-user-{uuid4()}"
    novel_resp = client.post(
        "/api/v1/novels",
        json={"title": f"{genre}模板匹配", "genre": genre, "description": content[:80]},
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
            "content": content,
        },
        headers=auth_headers(user_id),
    )
    assert chapter_resp.status_code == 201

    match_resp = client.post(
        "/api/v1/storyboards/templates/match",
        json={"novel_id": novel_id, "chapter_id": chapter_resp.json()["id"]},
        headers=auth_headers(user_id),
    )

    assert match_resp.status_code == 200
    payload = match_resp.json()
    assert payload["template"]["id"] in expected_ids
    assert payload["score"] > 0


def test_smart_generation_creates_reviewable_storyboard_and_precise_shots(client: TestClient) -> None:
    user_id = "smart-storyboard-user"
    novel_resp = client.post(
        "/api/v1/novels",
        json={"title": "玄都旧梦", "genre": "仙侠", "description": "灵气复苏后的山海城邦"},
        headers=auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_resp = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "夜入玄都",
            "chapter_number": 1,
            "content": "林舟握着玉佩进入玄都城。城门忽然爆发灵潮，守夜人低声警告他立刻离开。",
        },
        headers=auth_headers(user_id),
    )
    assert chapter_resp.status_code == 201
    chapter_id = chapter_resp.json()["id"]

    response = client.post(
        "/api/v1/storyboards/generate-smart",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "shot_count": 4,
            "style": "anime",
            "use_ai_refine": False,
        },
        headers=auth_headers(user_id),
    )

    assert response.status_code == 201
    storyboard = response.json()
    assert storyboard["shot_count"] == 4
    assert storyboard["content"]["source"] == "smart_storyboard_generation"
    assert storyboard["content"]["review_status"] == "pending_review"
    assert storyboard["content"]["template_id"]
    assert len(storyboard["shots"]) == 4
    assert storyboard["shots"][0]["visual_description"]
    assert storyboard["shots"][0]["dialogue"]

    shots_resp = client.get(
        f"/api/v1/shots/storyboard/{storyboard['id']}",
        headers=auth_headers(user_id),
    )
    assert shots_resp.status_code == 200
    shots = shots_resp.json()
    assert len(shots) == 4
    first = shots[0]
    assert first["camera_movement"]
    assert first["emotion"]
    assert first["lighting"]
    assert first["color_grading"]
    assert first["music_cue"]
    assert first["sfx_cue"]
    assert first["keyframes"]
    assert first["extra_data"]["review_status"] == "pending_review"


def test_deleting_storyboard_removes_its_shots(client: TestClient) -> None:
    user_id = f"storyboard-delete-user-{uuid4()}"
    novel_resp = client.post(
        "/api/v1/novels",
        json={"title": "删除分镜测试", "genre": "悬疑", "description": "林澈在旧楼发现线索。"},
        headers=auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_resp = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "旧楼",
            "chapter_number": 1,
            "content": "林澈进入旧楼，发现墙面上的星形标记正在发光。",
        },
        headers=auth_headers(user_id),
    )
    assert chapter_resp.status_code == 201

    script_resp = client.post(
        "/api/v1/scripts/generate",
        json={"chapter_id": chapter_resp.json()["id"], "style": "anime"},
        headers=auth_headers(user_id),
    )
    assert script_resp.status_code == 201

    storyboard_resp = client.post(
        "/api/v1/storyboards/generate-smart",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_resp.json()["id"],
            "shot_count": 3,
            "style": "anime",
            "use_ai_refine": False,
        },
        headers=auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201
    storyboard_id = storyboard_resp.json()["id"]

    shots_resp = client.get(f"/api/v1/shots/storyboard/{storyboard_id}", headers=auth_headers(user_id))
    assert shots_resp.status_code == 200
    assert len(shots_resp.json()) == 3

    delete_resp = client.delete(f"/api/v1/storyboards/{storyboard_id}", headers=auth_headers(user_id))
    assert delete_resp.status_code == 200
    assert delete_resp.json()["deleted_shot_count"] == 3

    get_resp = client.get(f"/api/v1/storyboards/{storyboard_id}", headers=auth_headers(user_id))
    assert get_resp.status_code == 404

    deleted_shots_resp = client.get(f"/api/v1/shots/storyboard/{storyboard_id}", headers=auth_headers(user_id))
    assert deleted_shots_resp.status_code == 404


def test_smart_storyboard_binds_entities_and_video_keeps_context(client: TestClient) -> None:
    user_id = f"smart-video-context-user-{uuid4()}"
    novel_resp = client.post(
        "/api/v1/novels",
        json={"title": "旧城星钥", "genre": "悬疑", "description": "角色：林澈。场景：旧城街口。道具：星钥。事件：失踪记忆重现。"},
        headers=auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_resp = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "雨夜线索",
            "chapter_number": 1,
            "content": "角色：林澈。场景：旧城街口。道具：星钥。事件：失踪记忆重现。林澈握着星钥进入旧城街口，发现墙面映出失踪记忆。",
        },
        headers=auth_headers(user_id),
    )
    assert chapter_resp.status_code == 201
    chapter_id = chapter_resp.json()["id"]

    storyboard_resp = client.post(
        "/api/v1/storyboards/generate-smart",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "shot_count": 2,
            "style": "anime",
            "use_ai_refine": False,
        },
        headers=auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201
    storyboard = storyboard_resp.json()
    shot = storyboard["shots"][0]
    assert shot["character_refs"]
    assert shot["extra_data"]["entity_refs"]["characters"]
    assert shot["extra_data"]["entity_refs"]["scenes"]
    assert shot["extra_data"]["entity_refs"]["props"]
    assert shot["extra_data"]["entity_refs"]["events"]
    assert shot["extra_data"]["subtitle_text"]

    video_resp = client.post(
        "/api/v1/video/generate",
        json={
            "prompt": shot["prompt"],
            "duration": max(4, shot["duration"]),
            "resolution": "720p",
            "shot_id": shot["id"],
            "storyboard_id": storyboard["id"],
            "script_id": storyboard["script_id"],
            "chapter_id": chapter_id,
            "novel_id": novel_id,
        },
        headers=auth_headers(user_id),
    )
    assert video_resp.status_code == 200
    job_id = video_resp.json()["job_id"]

    job_resp = client.get(f"/api/v1/video/jobs/{job_id}", headers=auth_headers(user_id))
    assert job_resp.status_code == 200
    job = job_resp.json()
    assert job["character_refs"]
    assert job["scene_refs"]
    assert job["prop_refs"]
    assert job["event_refs"]
    assert job["subtitle_text"]
    assert isinstance(job["seed"], int)
    assert job["consistency"]["seed"] == job["seed"]
    assert "旧城街口" in job["prompt"]
    assert "星钥" in job["prompt"]
    assert "字幕/对白" in job["prompt"]
    assert "视频一致性约束" in job["prompt"]
