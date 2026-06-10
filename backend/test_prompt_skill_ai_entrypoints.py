from __future__ import annotations

import json
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


def test_novel_intro_uses_active_prompt_skill_template(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = f"novel-intro-skill-user-{uuid4()}"
    calls: list[dict] = []

    async def _fake_text_api_key(*args, **kwargs):
        return "fake-key", "qwen", "qwen-plus", None

    class _FakeTextService:
        async def safe_chat_completion(self, **kwargs) -> dict:
            calls.append(kwargs)
            return {"choices": [{"message": {"content": "这是测试简介正文。"}}]}

    monkeypatch.setattr("app.api.v1.endpoints.novels.get_user_text_api_key", _fake_text_api_key)
    monkeypatch.setattr(
        "app.api.v1.endpoints.novels.create_text_generation_service",
        lambda *args, **kwargs: _FakeTextService(),
    )

    skill_resp = client.post(
        "/api/v1/prompt-skills",
        json={
            "name": "小说简介强约束",
            "task": "novel_generation",
            "stage": "intro",
            "content": "用户小说模板：标题《{title}》必须突出{genre}核心钩子。",
            "is_active": True,
        },
        headers=_auth_headers(user_id),
    )
    assert skill_resp.status_code == 201, skill_resp.text

    response = client.post(
        "/api/v1/novels/generate-intro",
        json={"title": "星海试炼", "genre": "科幻冒险", "style": "热血", "description": "少年进入星舰学院。"},
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    assert calls
    user_prompt = calls[0]["messages"][1]["content"]
    assert "用户小说模板：标题《星海试炼》必须突出科幻冒险核心钩子。" in user_prompt
    assert "【内部逻辑提示词】" in user_prompt
    assert "只输出简介正文" in user_prompt


def test_novel_generation_uses_active_prompt_skill_template(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = f"novel-generate-skill-user-{uuid4()}"
    calls: list[dict] = []

    async def _fake_text_api_key(*args, **kwargs):
        return "fake-key", "qwen", "qwen-plus", None

    class _FakeTextService:
        async def chat_completion(self, **kwargs) -> dict:
            calls.append(kwargs)
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "title": "星海试炼",
                                    "description": "少年进入星舰学院，面对失控试炼。",
                                    "chapters": [{"title": "第一章 入学警报", "content": "星舰学院响起警报。"}],
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            }

    monkeypatch.setattr("app.api.v1.endpoints.novels.get_user_text_api_key", _fake_text_api_key)
    monkeypatch.setattr(
        "app.api.v1.endpoints.novels.create_text_generation_service",
        lambda *args, **kwargs: _FakeTextService(),
    )

    skill_resp = client.post(
        "/api/v1/prompt-skills",
        json={
            "name": "小说创建强约束",
            "task": "novel_generation",
            "stage": "draft",
            "content": "用户小说模板：围绕{prompt}生成{chapter_count}章，类型保持{genre}。",
            "is_active": True,
        },
        headers=_auth_headers(user_id),
    )
    assert skill_resp.status_code == 201, skill_resp.text

    response = client.post(
        "/api/v1/novels/generate",
        json={"prompt": "星海试炼", "genre": "科幻冒险", "chapter_count": 1, "style": "热血"},
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 201, response.text
    assert calls
    user_prompt = calls[0]["messages"][1]["content"]
    assert "用户小说模板：围绕星海试炼生成1章，类型保持科幻冒险。" in user_prompt
    assert "【内部逻辑提示词】" in user_prompt
    assert "请以JSON格式输出" in user_prompt


def test_script_ai_assist_uses_active_prompt_skill_template(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = f"script-assist-skill-user-{uuid4()}"
    calls: list[dict] = []

    async def _fake_text_config(*args, **kwargs):
        return "fake-key", "qwen", "qwen-plus", None

    class _FakeTextService:
        async def safe_chat_completion(self, **kwargs) -> dict:
            calls.append(kwargs)
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "title": "雾港铜铃",
                                    "description": "沈砚追查密信失踪。",
                                    "content": "沈砚：铜铃声就在码头尽头。",
                                    "warnings": [],
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            }

    monkeypatch.setattr("app.api.v1.endpoints.scripts.get_user_text_model_config", _fake_text_config)
    monkeypatch.setattr(
        "app.api.v1.endpoints.scripts.create_text_generation_service",
        lambda *args, **kwargs: _FakeTextService(),
    )

    skill_resp = client.post(
        "/api/v1/prompt-skills",
        json={
            "name": "剧本润色强约束",
            "task": "script_generation",
            "stage": "assist",
            "content": "用户剧本模板：标题《{title}》保持{genre}节奏，不新增人物。",
            "is_active": True,
        },
        headers=_auth_headers(user_id),
    )
    assert skill_resp.status_code == 201, skill_resp.text

    response = client.post(
        "/api/v1/scripts/ai-assist",
        json={
            "mode": "polish_content",
            "title": "雾港铜铃",
            "genre": "悬疑",
            "style": "冷色动漫",
            "description": "沈砚追查密信失踪。",
            "content": "沈砚来到旧码头。",
        },
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    assert calls
    user_prompt = calls[0]["messages"][1]["content"]
    assert "用户剧本模板：标题《雾港铜铃》保持悬疑节奏，不新增人物。" in user_prompt
    assert "【内部逻辑提示词】" in user_prompt
    assert "当前剧本" in user_prompt


def test_storyboard_generation_uses_active_prompt_skill_template_without_consistency_context(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = f"storyboard-skill-user-{uuid4()}"
    calls: list[dict] = []

    async def _fake_text_config(*args, **kwargs):
        return "fake-key", "qwen", "qwen-plus", None

    class _FakeTextService:
        async def safe_chat_completion(self, **kwargs) -> dict:
            calls.append(kwargs)
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                [
                                    {
                                        "shot_number": 1,
                                        "duration": 4,
                                        "shot_type": "dialogue",
                                        "prompt": "沈砚在旧码头听见铜铃声",
                                        "dialogue": "沈砚：铜铃又响了。",
                                        "visual_description": "冷色月光下，沈砚停在旧码头木栈道边，神情警觉。",
                                        "camera_angle": "medium",
                                        "camera_movement": "固定",
                                        "sound_effect": "铜铃声、潮水声",
                                        "music_mood": "紧张悬疑",
                                    }
                                ],
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            }

    monkeypatch.setattr("app.api.v1.endpoints.storyboards.get_user_qwen_api_key", _fake_text_config)
    monkeypatch.setattr(
        "app.api.v1.endpoints.storyboards.create_text_generation_service",
        lambda *args, **kwargs: _FakeTextService(),
    )

    skill_resp = client.post(
        "/api/v1/prompt-skills",
        json={
            "name": "分镜对白强约束",
            "task": "storyboard_generation",
            "stage": "storyboard",
            "content": "用户分镜模板：从{source_content}拆成{shot_count}个{style}镜头，必须保留对白。",
            "is_active": True,
        },
        headers=_auth_headers(user_id),
    )
    assert skill_resp.status_code == 201, skill_resp.text

    script_resp = client.post(
        "/api/v1/scripts",
        json={
            "title": "雾港铜铃",
            "genre": "悬疑",
            "style": "冷色动漫",
            "description": "沈砚追查密信失踪。",
            "content": "沈砚来到旧码头。\n沈砚：铜铃又响了。",
        },
        headers=_auth_headers(user_id),
    )
    assert script_resp.status_code == 201, script_resp.text

    response = client.post(
        "/api/v1/storyboards/generate",
        json={
            "script_id": script_resp.json()["id"],
            "shot_count": 3,
            "style": "anime",
            "use_consistency_context": False,
        },
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 201, response.text
    assert calls
    system_prompt = calls[0]["messages"][0]["content"]
    assert "用户分镜模板：从沈砚来到旧码头。" in system_prompt
    assert "拆成3个anime镜头" in system_prompt
    assert "必须保留对白" in system_prompt
    assert "【内部逻辑提示词】" in system_prompt
    assert "dialogue: 台词/配音" in system_prompt


def test_entity_extraction_uses_active_prompt_skill_template(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = f"entity-extraction-skill-user-{uuid4()}"
    calls: list[dict] = []

    async def _fake_text_config(*args, **kwargs):
        return "fake-key", "qwen", "qwen-plus", None

    class _FakeTextService:
        async def safe_chat_completion(self, **kwargs) -> dict:
            calls.append(kwargs)
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                [
                                    {
                                        "entity_type": "character",
                                        "name": "沈砚",
                                        "description": "年轻密探，追查铜铃线索。",
                                        "evidence": "沈砚在旧码头听见铜铃声。",
                                        "confidence": 96,
                                    },
                                    {
                                        "entity_type": "prop",
                                        "name": "铜铃",
                                        "description": "旧码头的关键线索。",
                                        "evidence": "铜铃声从雨幕里传来。",
                                        "confidence": 94,
                                    },
                                ],
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            }

    monkeypatch.setattr("app.api.v1.endpoints.story_bible.get_user_text_model_config", _fake_text_config)
    monkeypatch.setattr(
        "app.api.v1.endpoints.story_bible.create_text_generation_service",
        lambda *args, **kwargs: _FakeTextService(),
    )

    skill_resp = client.post(
        "/api/v1/prompt-skills",
        json={
            "name": "资产抽取强过滤",
            "task": "entity_extraction",
            "stage": "analysis",
            "content": "用户抽取模板：只抽取{entity_types}，群体和情绪词不能进入资产库。来源：{source_content}",
            "is_active": True,
        },
        headers=_auth_headers(user_id),
    )
    assert skill_resp.status_code == 201, skill_resp.text

    response = client.post(
        "/api/v1/story-bibles/entities/extract",
        json={
            "text": "沈砚在旧码头听见铜铃声。路人们围观。",
            "entity_types": ["character", "prop"],
            "persist": False,
            "model_config_id": "text-config-001",
        },
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    assert calls
    user_prompt = calls[0]["messages"][1]["content"]
    assert "用户抽取模板：只抽取character、prop，群体和情绪词不能进入资产库。" in user_prompt
    assert "【内部实体抽取规则】" in user_prompt
    assert "严格输出 JSON 数组" in user_prompt
