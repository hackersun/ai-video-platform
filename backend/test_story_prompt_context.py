from __future__ import annotations

import re
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


def _auth_headers(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


def _create_story_source(client: TestClient, user_id: str) -> tuple[str, str]:
    novel_resp = client.post(
        "/api/v1/novels",
        json={
            "title": "雾港铜铃",
            "genre": "悬疑",
            "description": "角色：沈砚。场景：雾港旧码头。道具：铜铃。事件：密信失踪。",
        },
        headers=_auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_resp = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "第一章 雾中来信",
            "chapter_number": 1,
            "content": "角色：沈砚。场景：雾港旧码头。道具：铜铃。事件：密信失踪。沈砚在雾港旧码头听见铜铃声，追查密信失踪的真相。",
        },
        headers=_auth_headers(user_id),
    )
    assert chapter_resp.status_code == 201
    chapter_id = chapter_resp.json()["id"]

    bible_resp = client.post(
        "/api/v1/story-bibles/generate-from-novel",
        json={"novel_id": novel_id, "style": "冷色赛璐璐悬疑动漫"},
        headers=_auth_headers(user_id),
    )
    assert bible_resp.status_code == 201
    return novel_id, chapter_id


def _create_script_context_fixture(client: TestClient, user_id: str) -> tuple[str, str, str]:
    novel_resp = client.post(
        "/api/v1/novels",
        json={
            "title": "雾港铜铃剧本链路",
            "genre": "悬疑",
            "description": "角色：沈砚。角色：林栀。场景：雾港旧码头。道具：铜铃。事件：密信失踪。",
        },
        headers=_auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    first = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "第一章 雾中来信",
            "chapter_number": 1,
            "content": "角色：沈砚。角色：林栀。场景：雾港旧码头。道具：铜铃。事件：密信失踪。林栀把铜铃交给沈砚，两人决定追查密信失踪。",
        },
        headers=_auth_headers(user_id),
    )
    assert first.status_code == 201
    first_id = first.json()["id"]

    second = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "第二章 暗巷回声",
            "chapter_number": 2,
            "content": "角色：沈砚。角色：林栀。场景：雾港暗巷。道具：铜铃。事件：暗巷遭遇。沈砚和林栀在暗巷听见铜铃回声，确认密信被人转移。",
        },
        headers=_auth_headers(user_id),
    )
    assert second.status_code == 201
    second_id = second.json()["id"]

    third = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "第三章 灯塔真相",
            "chapter_number": 3,
            "content": "角色：沈砚。场景：废弃灯塔。道具：密信。事件：灯塔真相。沈砚抵达废弃灯塔，发现密信背后的真相。",
        },
        headers=_auth_headers(user_id),
    )
    assert third.status_code == 201

    bible_resp = client.post(
        "/api/v1/story-bibles/generate-from-novel",
        json={"novel_id": novel_id, "style": "冷色赛璐璐悬疑动漫"},
        headers=_auth_headers(user_id),
    )
    assert bible_resp.status_code == 201
    rel_resp = client.post(
        "/api/v1/story-bibles/entities",
        json={
            "novel_id": novel_id,
            "chapter_id": first_id,
            "entity_type": "character",
            "name": "沈砚",
            "description": "调查密信失踪的主角",
            "attributes": {
                "relationships": [
                    {"target": "林栀", "relation": "同伴", "status": "共同追查密信失踪"}
                ]
            },
        },
        headers=_auth_headers(user_id),
    )
    assert rel_resp.status_code == 201
    return novel_id, first_id, second_id


def test_existing_novel_cover_prompt_uses_story_entities_and_user_prompt(client: TestClient) -> None:
    user_id = f"cover-context-user-{uuid4()}"
    novel_id, _chapter_id = _create_story_source(client, user_id)

    cover_resp = client.post(
        f"/api/v1/novels/{novel_id}/generate-cover",
        json={"prompt": "画面需要有强烈雨雾氛围", "style": "anime"},
        headers=_auth_headers(user_id),
    )
    assert cover_resp.status_code == 200
    job_id = cover_resp.json()["job_id"]

    job_resp = client.get(f"/api/v1/images/jobs/{job_id}", headers=_auth_headers(user_id))
    assert job_resp.status_code == 200
    prompt = job_resp.json()["prompt"]
    assert "雾港铜铃" in prompt
    assert "沈砚" in prompt
    assert "雾港旧码头" in prompt
    assert "铜铃" in prompt
    assert "密信失踪" in prompt
    assert "用户补充要求" in prompt
    assert "强烈雨雾氛围" in prompt


def test_existing_novel_cover_prompt_uses_active_prompt_skill(client: TestClient) -> None:
    user_id = f"cover-prompt-skill-user-{uuid4()}"
    novel_id, _chapter_id = _create_story_source(client, user_id)

    skill_resp = client.post(
        "/api/v1/prompt-skills",
        json={
            "name": "封面强约束",
            "task": "novel_cover",
            "stage": "image",
            "content": "用户封面模板：标题《{title}》，必须突出{genre}质感。",
            "is_active": True,
        },
        headers=_auth_headers(user_id),
    )
    assert skill_resp.status_code == 201, skill_resp.text

    cover_resp = client.post(
        f"/api/v1/novels/{novel_id}/generate-cover",
        json={"prompt": "画面需要有强烈雨雾氛围", "style": "anime"},
        headers=_auth_headers(user_id),
    )
    assert cover_resp.status_code == 200
    job_id = cover_resp.json()["job_id"]

    job_resp = client.get(f"/api/v1/images/jobs/{job_id}", headers=_auth_headers(user_id))
    assert job_resp.status_code == 200
    prompt = job_resp.json()["prompt"]
    assert "用户封面模板：标题《雾港铜铃》，必须突出悬疑质感。" in prompt
    assert "【内部逻辑提示词】" in prompt
    assert "用户补充要求" in prompt


def test_character_avatar_prompt_uses_active_prompt_skill(client: TestClient) -> None:
    user_id = f"avatar-prompt-skill-user-{uuid4()}"
    novel_id, _chapter_id = _create_story_source(client, user_id)
    character_resp = client.post(
        "/api/v1/characters",
        json={
            "novel_id": novel_id,
            "name": "沈砚",
            "description": "调查密信失踪的男主角",
            "appearance": "黑色风衣，冷峻眉眼，手持铜铃线索",
            "tags": ["男主角", "调查者"],
        },
        headers=_auth_headers(user_id),
    )
    assert character_resp.status_code == 201, character_resp.text
    character_id = character_resp.json()["id"]

    skill_resp = client.post(
        "/api/v1/prompt-skills",
        json={
            "name": "头像强约束",
            "task": "character_image",
            "stage": "image",
            "content": "用户头像模板：角色{character_name}必须保持{style}设定图质感。",
            "is_active": True,
        },
        headers=_auth_headers(user_id),
    )
    assert skill_resp.status_code == 201, skill_resp.text

    avatar_resp = client.post(
        f"/api/v1/characters/{character_id}/generate-avatar",
        json={"style": "anime"},
        headers=_auth_headers(user_id),
    )
    assert avatar_resp.status_code == 200, avatar_resp.text
    job_id = avatar_resp.json()["job_id"]

    job_resp = client.get(f"/api/v1/images/jobs/{job_id}", headers=_auth_headers(user_id))
    assert job_resp.status_code == 200
    prompt = job_resp.json()["prompt"]
    assert "用户头像模板：角色沈砚必须保持anime设定图质感。" in prompt
    assert "【内部逻辑提示词】" in prompt
    assert "动漫角色头像生成任务" in prompt


def test_dev_chapter_generation_carries_story_context(client: TestClient) -> None:
    user_id = f"chapter-context-user-{uuid4()}"
    novel_id, _chapter_id = _create_story_source(client, user_id)

    response = client.post(
        "/api/v1/chapters/generate",
        json={
            "novel_id": novel_id,
            "chapter_title": "第二章 铃声回潮",
            "target_word_count": 600,
            "instruction": "继续推进密信失踪调查",
        },
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 201
    content = response.json()["content"]
    assert "小说连续性上下文" in content
    assert "沈砚" in content
    assert "雾港旧码头" in content
    assert "铜铃" in content
    assert "密信失踪" in content


def test_script_generate_context_uses_story_entities_and_neighbors(client: TestClient) -> None:
    user_id = f"script-context-preview-user-{uuid4()}"
    _novel_id, _first_id, second_id = _create_script_context_fixture(client, user_id)

    response = client.get(
        f"/api/v1/scripts/generate-context/{second_id}",
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["chapter_id"] == second_id
    assert payload["previous_chapter"]["title"] == "第一章 雾中来信"
    assert payload["next_chapter"]["title"] == "第三章 灯塔真相"
    assert "沈砚" in payload["summary"]["characters"]
    assert "铜铃" in payload["summary"]["props"]
    assert payload["summary"]["relationships"]


def test_script_generation_uses_text_extracted_entities_without_story_bible(client: TestClient) -> None:
    user_id = f"script-context-text-entity-user-{uuid4()}"
    novel_resp = client.post(
        "/api/v1/novels",
        json={
            "title": "青云试炼",
            "genre": "修仙",
            "description": "角色：云澈。场景：青云宗山门。道具：祖传玉佩。事件：宗门试炼开启。",
        },
        headers=_auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]
    chapter_resp = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "第一章 山门试炼",
            "chapter_number": 1,
            "content": "角色：云澈。场景：青云宗山门。道具：祖传玉佩。事件：宗门试炼开启。云澈握着祖传玉佩踏入山门。",
        },
        headers=_auth_headers(user_id),
    )
    assert chapter_resp.status_code == 201
    chapter_id = chapter_resp.json()["id"]

    context_resp = client.get(f"/api/v1/scripts/generate-context/{chapter_id}", headers=_auth_headers(user_id))
    assert context_resp.status_code == 200
    context = context_resp.json()
    assert "云澈" in context["summary"]["characters"]
    assert "青云宗山门" in context["summary"]["scenes"]
    assert "祖传玉佩" in context["summary"]["props"]
    assert "宗门试炼开启" in context["summary"]["events"]

    script_resp = client.post(
        "/api/v1/scripts/generate",
        json={"chapter_id": chapter_id, "style": "anime", "genre": "修仙短剧"},
        headers=_auth_headers(user_id),
    )
    assert script_resp.status_code == 201
    script = script_resp.json()
    assert "云澈" in script["content"]
    assert "青云宗山门" in script["content"]
    assert "祖传玉佩" in script["content"]
    assert script["chapter_id"] == chapter_id


def test_first_chapter_script_generation_does_not_use_future_chapter_entities(client: TestClient) -> None:
    user_id = f"script-first-chapter-scope-user-{uuid4()}"
    novel_resp = client.post(
        "/api/v1/novels",
        json={"title": "三章前端回归", "genre": "悬疑动漫"},
        headers=_auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapters = [
        (
            "第一章 雾中来信",
            "雨后的雾港像一只沉默的钟。少年林澈在旧邮局门口捡到一封没有邮票的信，信纸上写着铜铃会指向失踪的人。阿岚从巷口追来，提醒他不要碰邮局梁上的铜铃。",
        ),
        (
            "第二章 暗巷回声",
            "星轨线把林澈和阿岚带进一条没有出口的暗巷。墙面反复回放旧邮局失火的影像。",
        ),
        (
            "第三章 灯塔真相",
            "铁门后不是出口，而是海边废弃灯塔。灯塔顶部的镜面正在把全城雾气聚成一个巨大的钟面。林澈冲向控制台，阿岚稳住即将断裂的星轨线。",
        ),
    ]
    chapter_ids: list[str] = []
    for index, (title, content) in enumerate(chapters, start=1):
        chapter_resp = client.post(
            "/api/v1/chapters",
            json={
                "novel_id": novel_id,
                "title": title,
                "chapter_number": index,
                "content": content,
            },
            headers=_auth_headers(user_id),
        )
        assert chapter_resp.status_code == 201
        chapter_ids.append(chapter_resp.json()["id"])

    context_resp = client.get(
        f"/api/v1/scripts/generate-context/{chapter_ids[0]}",
        headers=_auth_headers(user_id),
    )
    assert context_resp.status_code == 200
    summary_text = str(context_resp.json()["summary"])
    assert "废弃灯塔" not in summary_text
    assert "把全城" not in summary_text

    script_resp = client.post(
        "/api/v1/scripts/generate",
        json={"chapter_id": chapter_ids[0], "style": "anime", "genre": "悬疑动漫"},
        headers=_auth_headers(user_id),
    )
    assert script_resp.status_code == 201
    content = script_resp.json()["content"]
    assert "旧邮局" in content
    assert "铜铃" in content
    assert "废弃灯塔" not in content
    assert "把全城" not in content
    assert "上一章留下" not in content
    assert "本章开场" in content

    second_script_resp = client.post(
        "/api/v1/scripts/generate",
        json={"chapter_id": chapter_ids[1], "style": "anime", "genre": "悬疑动漫"},
        headers=_auth_headers(user_id),
    )
    assert second_script_resp.status_code == 201
    second_content = second_script_resp.json()["content"]
    assert "暗巷" in second_content
    assert "林澈" in second_content
    assert "阿岚" in second_content
    assert not re.search(r"人物：[^。；\n]*两人", second_content)
    assert "人物：星轨线" not in second_content
    assert "的人拿走了铜铃" not in second_content
    assert "废弃灯塔" not in second_content

    third_script_resp = client.post(
        "/api/v1/scripts/generate",
        json={"chapter_id": chapter_ids[2], "style": "anime", "genre": "悬疑动漫"},
        headers=_auth_headers(user_id),
    )
    assert third_script_resp.status_code == 201
    third_content = third_script_resp.json()["content"]
    assert "废弃灯塔" in third_content
    assert "林澈" in third_content
    assert "阿岚" in third_content
    assert "失踪者所" not in third_content
    assert "港永远停" not in third_content


def test_dev_script_generation_keeps_middle_chapter_continuity_and_metadata(client: TestClient) -> None:
    user_id = f"script-generate-user-{uuid4()}"
    _novel_id, _first_id, second_id = _create_script_context_fixture(client, user_id)

    response = client.post(
        "/api/v1/scripts/generate",
        json={"chapter_id": second_id, "style": "anime"},
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 201
    script = response.json()
    assert script["chapter_id"] == second_id
    assert script["status"] == "completed"
    assert "沈砚" in script["content"]
    assert "铜铃" in script["content"]

    detail = client.get(f"/api/v1/scripts/{script['id']}", headers=_auth_headers(user_id)).json()
    assert detail["chapter_id"] == second_id

    context_resp = client.get(
        f"/api/v1/scripts/generate-context/{second_id}",
        headers=_auth_headers(user_id),
    ).json()
    assert context_resp["generation_context"]["prev_chapter_id"] == _first_id
    assert context_resp["generation_context"]["next_chapter_id"]
    assert context_resp["generation_context"]["novel_series_seed"]
    assert context_resp["generation_context"]["chapter_seed"]
    assert context_resp["generation_context"]["continuity_lock"]["scope"] == "novel_series"
    assert context_resp["generation_context"]["previous_chapter_context"]["title"] == "第一章 雾中来信"

    check_resp = client.get(
        f"/api/v1/scripts/{script['id']}/check-consistency",
        headers=_auth_headers(user_id),
    )
    assert check_resp.status_code == 200
    check = check_resp.json()
    assert check["summary"]["has_generation_context"] is True
    assert not any(issue["code"] == "placeholder_speaker" for issue in check["issues"])


def test_dev_script_generation_preserves_explicit_dialogue_speakers(client: TestClient) -> None:
    user_id = f"script-dialogue-speaker-user-{uuid4()}"
    novel_resp = client.post(
        "/api/v1/novels",
        json={"title": "星轨列车", "genre": "科幻", "description": "维修舱里的双人对白同步验收。"},
        headers=_auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    chapter_resp = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_resp.json()["id"],
            "title": "第三集 星轨列车维修舱",
            "chapter_number": 3,
            "content": (
                "第一场，林澈单人站在星核计时器前，他低声说：我们只剩四秒。"
                "第二场，阿岚单人扶住稳定杆，阿岚说：别停，我来稳住轨道。"
                "第三场，林澈和阿岚同框争执，林澈说：你退后。阿岚说：不，我和你一起。"
            ),
        },
        headers=_auth_headers(user_id),
    )
    assert chapter_resp.status_code == 201

    script_resp = client.post(
        "/api/v1/scripts/generate",
        json={"chapter_id": chapter_resp.json()["id"], "style": "anime", "genre": "科幻"},
        headers=_auth_headers(user_id),
    )

    assert script_resp.status_code == 201
    content = script_resp.json()["content"]
    assert "林澈：" in content
    assert "我们只剩四秒" in content
    assert "阿岚：" in content
    assert "别停，我来稳住轨道" in content
    assert "- 低声：" not in content


def test_script_versions_can_snapshot_and_restore(client: TestClient) -> None:
    user_id = f"script-version-user-{uuid4()}"
    novel_id, first_id, _second_id = _create_script_context_fixture(client, user_id)
    create_resp = client.post(
        "/api/v1/scripts",
        json={
            "novel_id": novel_id,
            "chapter_id": first_id,
            "title": "初版剧本",
            "content": "初版内容",
        },
        headers=_auth_headers(user_id),
    )
    assert create_resp.status_code == 201
    script_id = create_resp.json()["id"]

    snapshot_resp = client.post(
        f"/api/v1/scripts/{script_id}/versions",
        json={"note": "保存初版"},
        headers=_auth_headers(user_id),
    )
    assert snapshot_resp.status_code == 201
    snapshot_id = snapshot_resp.json()["id"]

    update_resp = client.put(
        f"/api/v1/scripts/{script_id}",
        json={"title": "改后剧本", "content": "改后内容"},
        headers=_auth_headers(user_id),
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["title"] == "改后剧本"

    restore_resp = client.post(
        f"/api/v1/scripts/{script_id}/versions/restore",
        json={"snapshot_id": snapshot_id},
        headers=_auth_headers(user_id),
    )
    assert restore_resp.status_code == 200
    restored = restore_resp.json()
    assert restored["title"] == "初版剧本"
    assert restored["content"] == "初版内容"

    versions = client.get(f"/api/v1/scripts/{script_id}/versions", headers=_auth_headers(user_id))
    assert versions.status_code == 200
    assert len(versions.json()) >= 2


def test_smart_storyboard_dialogue_uses_named_character_and_story_anchors(client: TestClient) -> None:
    user_id = f"storyboard-dialogue-user-{uuid4()}"
    novel_id, chapter_id = _create_story_source(client, user_id)

    response = client.post(
        "/api/v1/storyboards/generate-smart",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "shot_count": 4,
            "style": "anime",
            "use_ai_refine": False,
        },
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 201
    shots = response.json()["shots"]
    dialogues = [shot["dialogue"] for shot in shots if shot.get("dialogue")]
    assert dialogues
    assert any(dialogue.startswith("沈砚：") for dialogue in dialogues)
    assert not any(dialogue.startswith("（角色）") for dialogue in dialogues)
    assert any("铜铃" in dialogue or "密信失踪" in dialogue for dialogue in dialogues)


def test_video_and_direct_av_prompts_include_story_continuity_constraints(client: TestClient) -> None:
    user_id = f"video-context-user-{uuid4()}"
    novel_id, chapter_id = _create_story_source(client, user_id)
    storyboard_resp = client.post(
        "/api/v1/storyboards/generate-smart",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "shot_count": 2,
            "style": "anime",
            "use_ai_refine": False,
        },
        headers=_auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201
    storyboard = storyboard_resp.json()
    shot = storyboard["shots"][0]

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
        headers=_auth_headers(user_id),
    )
    assert video_resp.status_code == 200
    video_job = client.get(
        f"/api/v1/video/jobs/{video_resp.json()['job_id']}",
        headers=_auth_headers(user_id),
    ).json()
    assert "动漫连续性硬约束" in video_job["prompt"]
    assert "沈砚" in video_job["prompt"]
    assert "雾港旧码头" in video_job["prompt"]
    assert "铜铃" in video_job["prompt"]

    media_resp = client.post(
        "/api/v1/media/generate",
        json={
            "task_type": "shot_audio_video",
            "media_type": "audio_video",
            "prompt": "生成带对白音频的动漫镜头。",
            "shot_id": shot["id"],
            "storyboard_id": storyboard["id"],
            "script_id": storyboard["script_id"],
            "chapter_id": chapter_id,
            "novel_id": novel_id,
            "duration": 4,
            "resolution": "720p",
        },
        headers=_auth_headers(user_id),
    )
    assert media_resp.status_code == 200
    media_job = media_resp.json()
    assert "动漫连续性硬约束" in media_job["prompt"]
    assert "沈砚" in media_job["prompt"]
    assert "铜铃" in media_job["extra_data"]["story_continuity_constraints"]
