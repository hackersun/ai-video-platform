"""
Tests for storyboard templates and smart novel/chapter generation.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import SyncSessionLocal
from app.core.dev_generation import dev_video_url
from app.models import StoryEntity
from app.services.storyboard_template_service import STORYBOARD_TEMPLATES, build_template_shots, extract_raw_story_beats
from app.services.chapter_naming import normalize_duplicate_chapter_label_text
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


def test_duplicate_chapter_label_normalization_handles_bracketed_titles() -> None:
    assert (
        normalize_duplicate_chapter_label_text("逆天至尊 - 第1章《第 2 章 宗门测试》剧本 - 分镜")
        == "逆天至尊 - 第2章《宗门测试》剧本 - 分镜"
    )


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


def test_script_storyboard_generation_uses_template_fallback_without_text_api_key(
    client: TestClient,
) -> None:
    user_id = f"script-storyboard-dev-fallback-{uuid4()}"
    novel_resp = client.post(
        "/api/v1/novels",
        json={"title": "第三集前端验收", "genre": "科幻", "description": "星轨列车维修舱对白同步验收。"},
        headers=auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]
    chapter_resp = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "第三集 星轨列车维修舱",
            "chapter_number": 3,
            "content": "林澈说：我们只剩四秒。阿岚说：别停，我来稳住轨道。两人同框争执。",
        },
        headers=auth_headers(user_id),
    )
    assert chapter_resp.status_code == 201
    chapter_id = chapter_resp.json()["id"]
    script_resp = client.post(
        "/api/v1/scripts",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "title": "第三集脚本",
            "genre": "科幻",
            "style": "anime",
            "content": (
                "【第1场】林澈检查星核计时器\n"
                "林澈：我们只剩四秒。\n"
                "【第2场】阿岚稳住轨道\n"
                "阿岚：别停，我来稳住轨道。\n"
                "【第3场】两人同框\n"
                "林澈：你退后。\n"
                "阿岚：不，我和你一起。"
            ),
        },
        headers=auth_headers(user_id),
    )
    assert script_resp.status_code == 201
    with SyncSessionLocal() as session:
        session.add(
            StoryEntity(
                id=str(uuid4()),
                user_id=user_id,
                novel_id=novel_id,
                chapter_id=chapter_resp.json()["id"],
                entity_type="character",
                name="因果与小",
                description="旧版本误识别出的假角色",
                aliases=[],
                confidence=100,
                source="deterministic",
            )
        )
        session.commit()

    response = client.post(
        "/api/v1/storyboards/generate",
        json={"script_id": script_resp.json()["id"], "style": "anime", "shot_count": 3},
        headers=auth_headers(user_id),
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["shot_count"] == 3
    assert payload["content"]["source"] == "script_storyboard_template_fallback"
    assert payload["content"]["ai_refined"] is False
    assert payload["shots"][0]["extra_data"]["automation_level"] == "template_draft"


def test_script_storyboard_template_fallback_uses_scene_beats_not_format_lines(
    client: TestClient,
) -> None:
    user_id = f"script-scene-beats-user-{uuid4()}"
    novel_resp = client.post(
        "/api/v1/novels",
        json={"title": "星轨列车", "genre": "科幻", "description": "维修舱对白同步验收。"},
        headers=auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]
    chapter_resp = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "第三集 星轨列车维修舱",
            "chapter_number": 3,
            "content": "林澈和阿岚在星轨列车维修舱抢修星核。",
        },
        headers=auth_headers(user_id),
    )
    assert chapter_resp.status_code == 201
    script_resp = client.post(
        "/api/v1/scripts",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_resp.json()["id"],
            "title": "第三集脚本",
            "genre": "科幻",
            "style": "anime",
            "content": (
                "【第1场】开场钩子\n"
                "- 人物：林澈\n"
                "【画面描述】林澈站在星核计时器前，红灯闪烁。\n"
                "【对话/旁白】\n"
                "- 林澈：\"我们只剩四秒。\"\n"
                "【镜头序列】\n"
                "1. 全景 - 固定 - 展示维修舱。\n"
                "【第2场】冲突推进\n"
                "- 人物：阿岚\n"
                "【画面描述】阿岚扶住稳定杆，轨道剧烈震动。\n"
                "【对话/旁白】\n"
                "- 阿岚：\"别停，我来稳住轨道。\"\n"
                "【镜头序列】\n"
                "1. 中景 - 跟拍 - 阿岚动作。\n"
                "【第3场】结尾承接\n"
                "- 人物：林澈、阿岚\n"
                "【画面描述】两人同框站在裂开的能量桥边。\n"
                "【对话/旁白】\n"
                "- 林澈：\"你退后。\"\n"
                "- 阿岚：\"不，我和你一起。\"\n"
                "【镜头序列】\n"
                "1. 近景 - 推镜 - 两人争执。"
            ),
        },
        headers=auth_headers(user_id),
    )
    assert script_resp.status_code == 201
    with SyncSessionLocal() as session:
        for name in ("保留最后一句钩", "成为本场视觉钩", "形成下一集钩", "开场钩", "拉镜", "推镜", "镜"):
            session.add(
                StoryEntity(
                    id=str(uuid4()),
                    user_id=user_id,
                    novel_id=novel_id,
                    chapter_id=chapter_resp.json()["id"],
                    entity_type="prop",
                    name=name,
                    description="旧版本误识别出的生产说明伪道具",
                    aliases=[],
                    confidence=100,
                    source="deterministic",
                )
            )
        session.commit()

    response = client.post(
        "/api/v1/storyboards/generate",
        json={"script_id": script_resp.json()["id"], "style": "anime"},
        headers=auth_headers(user_id),
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["shot_count"] == 3
    dialogues = "\n".join((shot.get("dialogue") or "") for shot in payload["shots"])
    assert "林澈：\"我们只剩四秒。\"" in dialogues
    assert "阿岚：\"别停，我来稳住轨道。\"" in dialogues
    assert "林澈：\"你退后。\"" in dialogues
    assert "阿岚：\"不，我和你一起。\"" in dialogues
    assert "因果与小" not in dialogues
    assert "白并标注" not in dialogues
    character_names = {
        ref.get("name")
        for shot in payload["shots"]
        for ref in (shot.get("character_refs") or [])
    }
    assert {"林澈", "阿岚"}.issubset(character_names)
    assert "因果与小" not in character_names
    assert "白并标注" not in character_names
    prop_names = {
        ref.get("name")
        for shot in payload["shots"]
        for ref in (shot.get("prop_refs") or [])
    } | {
        ref.get("name")
        for shot in payload["shots"]
        for ref in (((shot.get("extra_data") or {}).get("entity_refs") or {}).get("props") or [])
    }
    assert "红灯" in prop_names
    assert "保留最后一句钩" not in prop_names
    assert "成为本场视觉钩" not in prop_names
    assert "形成下一集钩" not in prop_names
    assert "开场钩" not in prop_names
    assert "拉镜" not in prop_names
    assert "推镜" not in prop_names
    assert "镜" not in prop_names


def test_template_dialogue_uses_trusted_story_roles_without_fake_continuity_lines() -> None:
    template = next(item for item in STORYBOARD_TEMPLATES if item["id"] == "anime-dialogue")
    source_content = (
        "她低声说：“江屿，罗盘指向灯塔，不是指向海。”"
        "许澜说：“如果灯塔醒来，雾港会被星潮吞掉。”"
        "江屿回答：“那我更要知道父亲为什么把钥匙留给我。”"
    )
    story_context = {
        "characters": [{"name": "江屿"}, {"name": "许澜"}],
        "scenes": [{"name": "钟楼机房"}],
        "props": [{"name": "星锚罗盘"}, {"name": "铜钥匙"}],
        "events": [{"name": "每一只钟面都映着江屿父亲失踪前的背影"}],
    }

    shots = build_template_shots(
        template=template,
        source_title="雾港星锚",
        source_content=source_content,
        shot_count=3,
        story_context=story_context,
    )

    dialogues = "\n".join(shot.get("dialogue") or "" for shot in shots)
    assert "许澜：如果灯塔醒来，雾港会被星潮吞掉。" in dialogues
    assert "江屿：那我更要知道父亲为什么把钥匙留给我。" in dialogues
    assert "不是指：" not in dialogues
    assert "她低声说：" not in dialogues
    assert "别让" not in dialogues
    assert "断掉" not in dialogues


def test_template_dialogue_keeps_chinese_quotes_and_speaker_hints() -> None:
    template = next(item for item in STORYBOARD_TEMPLATES if item["id"] == "world-establishing")
    source_content = (
        "巡港员许澜戴着红围巾赶来。"
        "她低声说：“江屿，罗盘指向灯塔，不是指向海。”"
        "钥匙柄上刻着“不要让灯塔醒来。”"
        "许澜说：“如果灯塔醒来，雾港会被星潮吞掉。”"
        "江屿回答：“那我更要知道父亲为什么把钥匙留给我。”"
        "许澜握紧红围巾说：“如果拔出它，大家会忘记这座港。”"
        "他们用铜钥匙启动主齿轮。"
    )
    story_context = {
        "characters": [{"name": "江屿"}, {"name": "许澜"}],
        "scenes": [{"name": "钟楼机房"}],
        "props": [{"name": "星锚罗盘"}, {"name": "铜钥匙"}],
        "events": [{"name": "钟楼机房启动"}],
    }

    raw_beats = extract_raw_story_beats(source_content)
    assert "她低声说：“江屿，罗盘指向灯塔，不是指向海。”" in raw_beats
    assert not any(beat.startswith("”") for beat in raw_beats)

    shots = build_template_shots(
        template=template,
        source_title="雾港星锚",
        source_content=source_content,
        shot_count=6,
        story_context=story_context,
    )

    dialogues = "\n".join(shot.get("dialogue") or "" for shot in shots)
    assert "许澜：江屿，罗盘指向灯塔，不是指向海。" in dialogues
    assert "刻着“不要让灯塔醒来。”" in dialogues
    assert "许澜：如果灯塔醒来，雾港会被星潮吞掉。" in dialogues
    assert "江屿：那我更要知道父亲为什么把钥匙留给我。" in dialogues
    assert "许澜：如果拔出它，大家会忘记这座港。" in dialogues
    assert "江屿：如果拔出它" not in dialogues
    assert "（旁白）许澜说" not in dialogues


def test_auto_template_shots_do_not_duplicate_last_story_beat_for_dialogue_hints() -> None:
    template = next(item for item in STORYBOARD_TEMPLATES if item["id"] == "world-establishing")
    source_content = (
        "钟楼机房里挂满停摆的海潮钟，每一只钟面都映着江屿父亲失踪前的背影。"
        "江屿仍穿深蓝夹克，银色工具包没有离身，许澜的红围巾被机房风扇吹得像警示旗。"
        "星锚罗盘开始逆转，蓝焰灯芯照出一枚铜钥匙，钥匙柄上刻着“不要让灯塔醒来”。"
        "许澜说：“如果灯塔醒来，雾港会被星潮吞掉。”"
        "江屿回答：“那我更要知道父亲为什么把钥匙留给我。”"
        "他们用铜钥匙启动主齿轮，钟楼外的海面升起一条通往灯塔的蓝色轨道。"
    )
    raw_beats = extract_raw_story_beats(source_content)

    shots = build_template_shots(
        template=template,
        source_title="雾港星锚",
        source_content=source_content,
        story_context={"characters": [{"name": "江屿"}, {"name": "许澜"}]},
    )
    source_beats = [shot["extra_data"]["source_beat"] for shot in shots]

    assert len(shots) == len(raw_beats)
    assert len(source_beats) == len(set(source_beats))
    assert source_beats[-1] != source_beats[-2]


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


def _create_storyboard_with_shots(
    client: TestClient,
    user_id: str,
    dialogues: tuple[str, ...] = ("林舟：我不能退。", "旁白：灵气如潮水般爆发。"),
) -> tuple[str, list[dict]]:
    headers = auth_headers(user_id)
    novel_resp = client.post(
        "/api/v1/novels",
        json={"title": "分镜合成测试小说", "genre": "修仙", "description": "少年在雨夜破境。"},
        headers=headers,
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_resp = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "雨夜破境",
            "chapter_number": 1,
            "content": "林舟在雨夜拔剑，灵气汇入剑锋，随后冲向山门。",
        },
        headers=headers,
    )
    assert chapter_resp.status_code == 201
    chapter_id = chapter_resp.json()["id"]

    script_resp = client.post(
        "/api/v1/scripts",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "title": "雨夜破境剧本",
            "content": "镜头一：林舟握剑。镜头二：灵气爆发。",
            "genre": "修仙",
            "style": "anime",
        },
        headers=headers,
    )
    assert script_resp.status_code == 201
    script_id = script_resp.json()["id"]

    storyboard_resp = client.post(
        "/api/v1/storyboards",
        json={
            "script_id": script_id,
            "title": "雨夜破境分镜",
            "description": "测试分镜视频合并",
        },
        headers=headers,
    )
    assert storyboard_resp.status_code == 201
    storyboard_id = storyboard_resp.json()["id"]

    shots: list[dict] = []
    for index, dialogue in enumerate(dialogues, start=1):
        shot_resp = client.post(
            "/api/v1/shots",
            json={
                "storyboard_id": storyboard_id,
                "shot_number": index,
                "duration": 4,
                "prompt": f"雨夜破境镜头 {index}",
                "dialogue": dialogue,
                "visual_description": f"镜头 {index} 保持同一角色与雨夜山门场景",
                "camera_angle": "medium",
            },
            headers=headers,
        )
        assert shot_resp.status_code == 201
        shots.append(shot_resp.json())
    return storyboard_id, shots


def _create_storyboard_with_two_shots(client: TestClient, user_id: str) -> tuple[str, list[dict]]:
    return _create_storyboard_with_shots(client, user_id)


def test_storyboard_merge_videos_creates_manifest_srt_and_history_job(client: TestClient) -> None:
    user_id = f"storyboard-merge-user-{uuid4()}"
    storyboard_id, shots = _create_storyboard_with_two_shots(client, user_id)
    headers = auth_headers(user_id)

    for index, shot in enumerate(shots, start=1):
        update_resp = client.put(
            f"/api/v1/shots/{shot['id']}",
            json={
                "video_url": f"/static/dev/video-storyboard-merge-{index}.mp4",
                "audio_url": f"/static/dev/audio-storyboard-merge-{index}.mp3",
                "video_status": "completed",
                "audio_status": "completed",
            },
            headers=headers,
        )
        assert update_resp.status_code == 200

    merge_resp = client.post(
        f"/api/v1/storyboards/{storyboard_id}/merge-videos",
        json={"title": "雨夜破境成片", "include_subtitles": True, "transition_style": "cut"},
        headers=headers,
    )

    assert merge_resp.status_code == 200
    payload = merge_resp.json()
    assert payload["job_id"]
    assert payload["storyboard_id"] == storyboard_id
    assert payload["segment_count"] == 2
    assert payload["output_url"].startswith("/static/dev/final-")
    assert payload["manifest_url"].startswith("/static/exports/")
    assert payload["srt_url"].endswith(".srt")
    assert payload["segments"][0]["shot_number"] == 1
    assert payload["segments"][1]["shot_number"] == 2
    assert payload["segments"][0]["subtitle"]["text"] == "林舟：我不能退。"

    manifest_resp = client.get(payload["manifest_url"])
    assert manifest_resp.status_code == 200
    manifest = manifest_resp.json()
    assert manifest["type"] == "storyboard_final_video_manifest"
    assert manifest["segment_count"] == 2
    assert manifest["tracks"]["subtitle"][0]["text"] == "林舟：我不能退。"

    srt_resp = client.get(payload["srt_url"])
    assert srt_resp.status_code == 200
    assert "林舟：我不能退。" in srt_resp.text
    assert "00:00:04,000 --> 00:00:08,000" in srt_resp.text

    history_resp = client.get(f"/api/v1/synthesis/jobs/{payload['job_id']}", headers=headers)
    assert history_resp.status_code == 200
    history = history_resp.json()
    assert history["output_url"] == payload["output_url"]
    assert history["extra_data"]["storyboard_id"] == storyboard_id
    assert history["extra_data"]["manifest_url"] == payload["manifest_url"]
    assert history["extra_data"]["srt_url"] == payload["srt_url"]
    assert "is_real_merged" in history["extra_data"]


def test_storyboard_merge_videos_can_select_subset_real_merge_and_list_versions(client: TestClient) -> None:
    user_id = f"storyboard-merge-subset-user-{uuid4()}"
    storyboard_id, shots = _create_storyboard_with_shots(
        client,
        user_id,
        ("林舟：今夜入山门。", "旁白：剑光照亮雨幕。", "未选择的第三个镜头。"),
    )
    headers = auth_headers(user_id)

    for index, shot in enumerate(shots[:2], start=1):
        update_resp = client.put(
            f"/api/v1/shots/{shot['id']}",
            json={
                "video_url": dev_video_url(
                    f"storyboard-real-merge-{uuid4()}-{index}",
                    duration_seconds=shot["duration"],
                ),
                "video_status": "completed",
            },
            headers=headers,
        )
        assert update_resp.status_code == 200

    merge_resp = client.post(
        f"/api/v1/storyboards/{storyboard_id}/merge-videos",
        json={
            "title": "只合并前两个镜头",
            "shot_ids": [shots[0]["id"], shots[1]["id"]],
            "render_strategy": "ffmpeg",
            "include_subtitles": True,
        },
        headers=headers,
    )
    assert merge_resp.status_code == 200
    payload = merge_resp.json()
    assert payload["segment_count"] == 2
    assert payload["selected_shot_ids"] == [shots[0]["id"], shots[1]["id"]]
    assert payload["selected_shot_numbers"] == [1, 2]
    assert payload["skipped_shot_numbers"] == []
    assert payload["version_number"] == 1
    assert payload["is_real_merged"] is True
    assert payload["render_backend"] == "ffmpeg"
    assert payload["output_url"].startswith("/static/exports/")
    assert payload["output_url"].endswith(".mp4")
    assert payload["duration_seconds"] >= 8
    assert payload["segments"][0]["duration_seconds"] >= 3.8

    video_resp = client.get(payload["output_url"])
    assert video_resp.status_code == 200
    assert len(video_resp.content) > 1000

    second_merge_resp = client.post(
        f"/api/v1/storyboards/{storyboard_id}/merge-videos",
        json={
            "title": "重新合成第二版",
            "shot_ids": [shots[1]["id"]],
            "render_strategy": "ffmpeg",
            "include_subtitles": True,
            "parent_job_id": payload["job_id"],
        },
        headers=headers,
    )
    assert second_merge_resp.status_code == 200
    second_payload = second_merge_resp.json()
    assert second_payload["version_number"] == 2
    assert second_payload["selected_shot_ids"] == [shots[1]["id"]]

    versions_resp = client.get(f"/api/v1/storyboards/{storyboard_id}/merge-videos", headers=headers)
    assert versions_resp.status_code == 200
    versions = versions_resp.json()
    assert [item["version_number"] for item in versions[:2]] == [2, 1]
    assert versions[0]["job_id"] == second_payload["job_id"]
    assert versions[0]["parent_job_id"] == payload["job_id"]


def test_storyboard_merge_videos_requires_selected_shot_video_url(client: TestClient) -> None:
    user_id = f"storyboard-merge-missing-user-{uuid4()}"
    storyboard_id, shots = _create_storyboard_with_two_shots(client, user_id)
    headers = auth_headers(user_id)

    update_resp = client.put(
        f"/api/v1/shots/{shots[0]['id']}",
        json={"video_url": "/static/dev/video-storyboard-merge-one.mp4", "video_status": "completed"},
        headers=headers,
    )
    assert update_resp.status_code == 200

    merge_resp = client.post(
        f"/api/v1/storyboards/{storyboard_id}/merge-videos",
        json={"include_subtitles": True, "shot_ids": [shots[0]["id"], shots[1]["id"]]},
        headers=headers,
    )

    assert merge_resp.status_code == 422
    assert "镜头 2" in merge_resp.json()["detail"]


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


def test_smart_generation_auto_plans_few_shots_for_short_chapter(client: TestClient) -> None:
    user_id = f"smart-storyboard-auto-short-user-{uuid4()}"
    novel_resp = client.post(
        "/api/v1/novels",
        json={"title": "星钥短验收", "genre": "悬疑", "description": "用于低成本前端闭环验收。"},
        headers=auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_resp = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "雨夜星钥",
            "chapter_number": 1,
            "content": "林澈在雨夜发现星钥。墙面裂开，追兵逼近。",
        },
        headers=auth_headers(user_id),
    )
    assert chapter_resp.status_code == 201

    response = client.post(
        "/api/v1/storyboards/generate-smart",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_resp.json()["id"],
            "style": "anime",
            "use_ai_refine": False,
        },
        headers=auth_headers(user_id),
    )

    assert response.status_code == 201
    storyboard = response.json()
    assert 2 <= storyboard["shot_count"] <= 3
    assert len(storyboard["shots"]) == storyboard["shot_count"]
    assert storyboard["content"]["shot_count_plan"]["source"] == "auto"
    assert storyboard["content"]["shot_count_plan"]["requested_shot_count"] is None


def test_smart_generation_compresses_compact_four_beat_chapter(client: TestClient) -> None:
    user_id = f"smart-storyboard-auto-compact-user-{uuid4()}"
    novel_resp = client.post(
        "/api/v1/novels",
        json={"title": "星轨三段式", "genre": "科幻", "description": "用于验证短章节压缩拆镜。"},
        headers=auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_resp = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "旧钟星门",
            "chapter_number": 1,
            "content": (
                "雨城连续下了七天雨。林澈在旧钟楼发现星盘逆转。"
                "阿岚带着半枚铜钥匙闯进钟楼。全城街灯熄灭，星门即将打开。"
            ),
        },
        headers=auth_headers(user_id),
    )
    assert chapter_resp.status_code == 201

    response = client.post(
        "/api/v1/storyboards/generate-smart",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_resp.json()["id"],
            "style": "anime",
            "use_ai_refine": False,
        },
        headers=auth_headers(user_id),
    )

    assert response.status_code == 201
    storyboard = response.json()
    assert storyboard["content"]["shot_count_plan"]["story_beat_count"] == 4
    assert storyboard["shot_count"] == 3
    assert [shot["duration"] for shot in storyboard["shots"]] == [4, 4, 4]


def test_smart_generation_auto_plans_more_shots_for_multi_beat_chapter(client: TestClient) -> None:
    user_id = f"smart-storyboard-auto-long-user-{uuid4()}"
    novel_resp = client.post(
        "/api/v1/novels",
        json={"title": "星钥多情节点", "genre": "冒险", "description": "用于验证镜头数按剧情复杂度变化。"},
        headers=auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_resp = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "钟楼追击",
            "chapter_number": 2,
            "content": (
                "林澈冲进旧钟楼。守夜人关上铁门。星钥在掌心发烫。"
                "追兵从楼梯逼近。钟摆突然停住。墙后的暗门露出地下轨道。"
            ),
        },
        headers=auth_headers(user_id),
    )
    assert chapter_resp.status_code == 201

    response = client.post(
        "/api/v1/storyboards/generate-smart",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_resp.json()["id"],
            "style": "anime",
            "use_ai_refine": False,
        },
        headers=auth_headers(user_id),
    )

    assert response.status_code == 201
    storyboard = response.json()
    assert storyboard["shot_count"] >= 4
    assert storyboard["content"]["shot_count_plan"]["source"] == "auto"
    assert storyboard["content"]["shot_count_plan"]["story_beat_count"] >= 5


def test_smart_generation_prefers_selected_chapter_title_over_stale_script_title(client: TestClient) -> None:
    user_id = f"smart-storyboard-chapter-title-user-{uuid4()}"
    novel_resp = client.post(
        "/api/v1/novels",
        json={"title": "逆天路", "genre": "玄幻", "description": "少年从宗门废墟重新踏上修行路。"},
        headers=auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    first_chapter_resp = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "旧怨初起",
            "chapter_number": 1,
            "content": "第一章里，少年在宗门废墟前被旧敌围住。",
        },
        headers=auth_headers(user_id),
    )
    assert first_chapter_resp.status_code == 201

    second_chapter_resp = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "破阵取钥",
            "chapter_number": 2,
            "content": "第二章里，少年进入石阵夺回青铜钥，追兵被阵光隔开。",
        },
        headers=auth_headers(user_id),
    )
    assert second_chapter_resp.status_code == 201
    second_chapter_id = second_chapter_resp.json()["id"]

    stale_script_resp = client.post(
        "/api/v1/scripts",
        json={
            "novel_id": novel_id,
            "chapter_id": second_chapter_id,
            "title": "第一章 旧怨初起 - 剧本",
            "content": "第二章剧本：少年进入石阵，夺回青铜钥，并在阵光中摆脱追兵。",
            "genre": "玄幻",
            "style": "anime",
        },
        headers=auth_headers(user_id),
    )
    assert stale_script_resp.status_code == 201

    response = client.post(
        "/api/v1/storyboards/generate-smart",
        json={
            "novel_id": novel_id,
            "chapter_id": second_chapter_id,
            "script_id": stale_script_resp.json()["id"],
            "shot_count": 3,
            "style": "anime",
            "use_ai_refine": False,
        },
        headers=auth_headers(user_id),
    )

    assert response.status_code == 201
    storyboard = response.json()
    assert storyboard["chapter_id"] == second_chapter_id
    assert storyboard["content"]["chapter_id"] == second_chapter_id
    assert "第2章" in storyboard["title"]
    assert "破阵取钥" in storyboard["title"]
    assert "第一章" not in storyboard["title"]


def test_smart_generation_uses_selected_chapter_for_unlinked_script(client: TestClient) -> None:
    user_id = f"smart-storyboard-unlinked-script-user-{uuid4()}"
    novel_resp = client.post(
        "/api/v1/novels",
        json={"title": "星门旧案", "genre": "科幻", "description": "林澈追查星门钥匙。"},
        headers=auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_resp = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "暗巷追击",
            "chapter_number": 2,
            "content": "林澈在暗巷中夺回星门钥匙，追兵从雨幕中逼近。",
        },
        headers=auth_headers(user_id),
    )
    assert chapter_resp.status_code == 201
    chapter_id = chapter_resp.json()["id"]

    script_resp = client.post(
        "/api/v1/scripts",
        json={
            "novel_id": novel_id,
            "title": "旧版无章节绑定剧本",
            "content": "林澈在暗巷中夺回星门钥匙，追兵从雨幕中逼近。",
            "genre": "科幻",
            "style": "anime",
        },
        headers=auth_headers(user_id),
    )
    assert script_resp.status_code == 201

    response = client.post(
        "/api/v1/storyboards/generate-smart",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "script_id": script_resp.json()["id"],
            "shot_count": 2,
            "style": "anime",
            "use_ai_refine": False,
        },
        headers=auth_headers(user_id),
    )

    assert response.status_code == 201
    storyboard = response.json()
    assert storyboard["chapter_id"] == chapter_id
    assert storyboard["content"]["chapter_id"] == chapter_id
    assert "第2章" in storyboard["title"]
    assert "暗巷追击" in storyboard["title"]


def test_smart_generation_normalizes_chapter_title_that_already_contains_number(client: TestClient) -> None:
    user_id = f"smart-storyboard-normalized-chapter-title-user-{uuid4()}"
    novel_resp = client.post(
        "/api/v1/novels",
        json={"title": "逆天至尊", "genre": "玄幻", "description": "宗门试炼引出重生后的第一场危机。"},
        headers=auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_resp = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "第 2 章 宗门测试",
            "chapter_number": 1,
            "content": "青阳宗外门测试开始，主角接上第一章重生后的结果，拔剑应对外门弟子的挑衅。",
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
            "shot_count": 2,
            "style": "anime",
            "use_ai_refine": False,
        },
        headers=auth_headers(user_id),
    )

    assert response.status_code == 201
    storyboard = response.json()
    assert storyboard["title"] == "逆天至尊 - 第2章 宗门测试 - 智能分镜"
    assert "第1章" not in storyboard["title"]
    assert all("第1章" not in shot["prompt"] for shot in storyboard["shots"])
    assert all("第2章 宗门测试" in shot["prompt"] for shot in storyboard["shots"])


def test_script_generation_normalizes_chapter_title_that_already_contains_number(client: TestClient) -> None:
    user_id = f"script-normalized-chapter-title-user-{uuid4()}"
    novel_resp = client.post(
        "/api/v1/novels",
        json={"title": "逆天至尊", "genre": "玄幻", "description": "宗门试炼引出重生后的第一场危机。"},
        headers=auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_resp = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "第 2 章 宗门测试",
            "chapter_number": 1,
            "content": "青阳宗外门测试开始，主角接上第一章重生后的结果，拔剑应对外门弟子的挑衅。",
        },
        headers=auth_headers(user_id),
    )
    assert chapter_resp.status_code == 201
    chapter_id = chapter_resp.json()["id"]

    script_resp = client.post(
        "/api/v1/scripts/generate",
        json={"chapter_id": chapter_id, "style": "anime", "genre": "玄幻"},
        headers=auth_headers(user_id),
    )

    assert script_resp.status_code == 201
    script = script_resp.json()
    assert "第1章" not in script["title"]
    assert script["title"] == "第2章 宗门测试 动漫短剧改编"
    assert "第1章《第 2 章" not in script["description"]


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
