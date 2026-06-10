from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import base64
import pytest
from fastapi.testclient import TestClient

from app.core.dev_generation import dev_image_url
from app.core.time_utils import utc_now
from app.api.v1.endpoints.shots import build_shot_response
from app.models.shot import Shot
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


def _create_novel(client: TestClient, user_id: str) -> str:
    response = client.post(
        "/api/v1/novels",
        json={"title": f"影像链路-{uuid4()}", "description": "用于测试图片生成绑定回写"},
        headers=auth_headers(user_id),
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _create_shot(client: TestClient, user_id: str, novel_id: str) -> str:
    chapter_resp = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "第一章",
            "chapter_number": 1,
            "content": "少年在山门前拔剑，云雾翻涌。",
        },
        headers=auth_headers(user_id),
    )
    assert chapter_resp.status_code == 201, chapter_resp.text
    chapter_id = chapter_resp.json()["id"]

    script_resp = client.post(
        "/api/v1/scripts",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "title": "第一章剧本",
            "content": "少年在山门前拔剑。",
        },
        headers=auth_headers(user_id),
    )
    assert script_resp.status_code == 201, script_resp.text
    script_id = script_resp.json()["id"]

    storyboard_resp = client.post(
        "/api/v1/storyboards",
        json={
            "script_id": script_id,
            "title": "山门拔剑",
            "description": "主角亮相",
        },
        headers=auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201, storyboard_resp.text
    storyboard_id = storyboard_resp.json()["id"]

    shot_resp = client.post(
        "/api/v1/shots",
        json={
            "storyboard_id": storyboard_id,
            "shot_number": 1,
            "duration": 4,
            "prompt": "少年在山门前拔剑，云雾翻涌",
            "dialogue": "此剑，今日出鞘。",
        },
        headers=auth_headers(user_id),
    )
    assert shot_resp.status_code == 201, shot_resp.text
    return shot_resp.json()["id"]


def _create_entity(
    client: TestClient,
    user_id: str,
    *,
    novel_id: str,
    chapter_id: str,
    entity_type: str,
    name: str,
    description: str,
) -> str:
    response = client.post(
        "/api/v1/story-bibles/entities",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "entity_type": entity_type,
            "name": name,
            "description": description,
            "confidence": 100,
        },
        headers=auth_headers(user_id),
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _stub_successful_image_provider(monkeypatch: pytest.MonkeyPatch, image_url: str) -> None:
    async def _fake_image_config(*args, **kwargs):
        return "fake-image-key", "minimax", "MiniMax-M3", "https://api.minimax.test/v1"

    class _FakeImageService:
        async def generate_image(self, **kwargs) -> dict:
            return {"task_id": "fake-image-task", "data": [{"url": image_url}]}

    def _fake_create_service(*args, **kwargs):
        return _FakeImageService()

    monkeypatch.setattr("app.api.v1.endpoints.images.get_user_image_model_config", _fake_image_config, raising=False)
    monkeypatch.setattr("app.api.v1.endpoints.images.create_image_generation_service", _fake_create_service, raising=False)


def _tiny_png_base64() -> str:
    return base64.b64encode(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
        )
    ).decode("ascii")


def test_stale_generating_shot_reference_image_is_reported_as_failed() -> None:
    shot = Shot(
        id=str(uuid4()),
        storyboard_id=str(uuid4()),
        user_id="stale-image-user",
        shot_number=1,
        duration=4,
        prompt="旧任务没有返回图片",
        image_status="generating",
        image_url=None,
        updated_at=utc_now() - timedelta(minutes=10),
    )

    response = build_shot_response(shot)

    assert response.image_status == "failed"
    assert "超过 5 分钟未返回图片URL" in response.extra_data["image_generation_error"]


def test_generic_image_generation_updates_linked_character_avatar(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = f"image-character-link-user-{uuid4()}"
    novel_id = _create_novel(client, user_id)
    char_resp = client.post(
        "/api/v1/characters",
        json={
            "novel_id": novel_id,
            "name": "林青岚",
            "description": "女性剑修，青色长袍，冷静坚定",
            "appearance": "青色长袍，黑色长发，眉眼清冷",
        },
        headers=auth_headers(user_id),
    )
    assert char_resp.status_code == 201, char_resp.text
    character_id = char_resp.json()["id"]

    image_url = dev_image_url(f"provider-character-{uuid4()}", "character")
    _stub_successful_image_provider(monkeypatch, image_url)

    response = client.post(
        "/api/v1/images/generate",
        json={"prompt": "林青岚角色头像", "character_id": character_id, "num": 1},
        headers=auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    generated_url = response.json()["image_urls"][0]
    character_resp = client.get(f"/api/v1/characters/{character_id}", headers=auth_headers(user_id))
    assert character_resp.status_code == 200
    assert character_resp.json()["avatar"] == generated_url


def test_generic_image_generation_updates_linked_shot_reference_image(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = f"image-shot-link-user-{uuid4()}"
    novel_id = _create_novel(client, user_id)
    shot_id = _create_shot(client, user_id, novel_id)
    image_url = dev_image_url(f"provider-shot-{uuid4()}", "shot")
    _stub_successful_image_provider(monkeypatch, image_url)

    response = client.post(
        "/api/v1/images/generate",
        json={"prompt": "山门拔剑镜头参考图", "shot_id": shot_id, "num": 1},
        headers=auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    generated_url = response.json()["image_urls"][0]
    shot_resp = client.get(f"/api/v1/shots/{shot_id}", headers=auth_headers(user_id))
    assert shot_resp.status_code == 200
    assert shot_resp.json()["image_url"] == generated_url
    assert shot_resp.json()["image_status"] == "succeeded"


def test_generic_minimax_image_generation_requests_base64_and_persists(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = f"generic-minimax-image-user-{uuid4()}"
    calls: list[dict] = []

    async def _fake_image_config(*args, **kwargs):
        return "fake-image-key", "minimax", "image-01", "https://api.minimax.test/v1"

    class _FakeImageService:
        async def generate_image(self, **kwargs) -> dict:
            calls.append(kwargs)
            return {"data": {"image_base64": [_tiny_png_base64()]}, "task_id": "generic-base64-task"}

    def _fake_create_service(*args, **kwargs):
        return _FakeImageService()

    monkeypatch.setattr("app.api.v1.endpoints.images.get_user_image_model_config", _fake_image_config, raising=False)
    monkeypatch.setattr("app.api.v1.endpoints.images.create_image_generation_service", _fake_create_service, raising=False)

    response = client.post(
        "/api/v1/images/generate",
        json={"prompt": "统一生图链路测试", "model_config_id": "minimax-image-config", "num": 1},
        headers=auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "succeeded"
    assert data["image_urls"][0].startswith("/static/generated/images/")
    assert calls and calls[0]["response_format"] == "base64"
    assert "通用负面约束" in calls[0]["prompt"]
    assert "不要把多个无关画面拼在一起" in calls[0]["prompt"]


def test_generic_image_generation_uses_default_image_model_config(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = f"generic-default-image-user-{uuid4()}"
    calls: list[dict] = []

    async def _fake_image_config(*args, **kwargs):
        assert kwargs.get("config_id") is None
        return "fake-image-key", "minimax", "MiniMax-M3", "https://api.minimax.test/v1"

    async def _fake_volcano_key(*args, **kwargs):
        raise AssertionError("generic image generation should use the configured default image model")

    class _FakeImageService:
        async def generate_image(self, **kwargs) -> dict:
            calls.append(kwargs)
            return {"data": {"image_urls": ["https://cdn.example.com/default-image.png"]}, "task_id": "default-image-task"}

    def _fake_create_service(api_key: str, provider_name: str, base_url: str):
        assert api_key == "fake-image-key"
        assert provider_name == "minimax"
        assert base_url == "https://api.minimax.test/v1"
        return _FakeImageService()

    async def _fake_persist(url: str, **kwargs) -> str:
        return url

    monkeypatch.setattr("app.api.v1.endpoints.images.get_user_image_model_config", _fake_image_config, raising=False)
    monkeypatch.setattr("app.api.v1.endpoints.images.create_image_generation_service", _fake_create_service, raising=False)
    monkeypatch.setattr("app.api.v1.endpoints.images.get_user_volcano_api_key", _fake_volcano_key, raising=False)
    monkeypatch.setattr("app.api.v1.endpoints.images.persist_remote_media_url", _fake_persist, raising=False)

    response = client.post(
        "/api/v1/images/generate",
        json={"prompt": "默认图像模型测试", "num": 1},
        headers=auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "succeeded"
    assert data["image_urls"] == ["https://cdn.example.com/default-image.png"]
    assert calls and calls[0]["model"] == "MiniMax-M3"


def test_generic_image_generation_records_missing_url_failure(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = f"generic-missing-image-user-{uuid4()}"

    async def _fake_image_config(*args, **kwargs):
        return "fake-image-key", "minimax", "image-01", "https://api.minimax.test/v1"

    class _FakeImageService:
        async def generate_image(self, **kwargs) -> dict:
            return {"task_id": "missing-url-task", "status": "submitted"}

    def _fake_create_service(*args, **kwargs):
        return _FakeImageService()

    monkeypatch.setattr("app.api.v1.endpoints.images.get_user_image_model_config", _fake_image_config, raising=False)
    monkeypatch.setattr("app.api.v1.endpoints.images.create_image_generation_service", _fake_create_service, raising=False)

    response = client.post(
        "/api/v1/images/generate",
        json={"prompt": "模型只返回任务ID", "model_config_id": "minimax-image-config", "num": 1},
        headers=auth_headers(user_id),
    )

    assert response.status_code == 500
    assert "未返回图片URL或图片数据" in response.json()["detail"]

    jobs_resp = client.get("/api/v1/images/jobs?status=failed&limit=1", headers=auth_headers(user_id))
    assert jobs_resp.status_code == 200
    jobs = jobs_resp.json()
    assert jobs
    assert jobs[0]["task_id"] == "missing-url-task"
    assert "未返回图片URL或图片数据" in jobs[0]["error_message"]


def test_character_avatar_generation_requests_minimax_base64_and_persists(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = f"avatar-minimax-image-user-{uuid4()}"
    novel_id = _create_novel(client, user_id)
    char_resp = client.post(
        "/api/v1/characters",
        json={
            "novel_id": novel_id,
            "name": "沈月璃",
            "description": "女性医修，温柔坚定，是主角重要同伴",
            "appearance": "白色衣裙，银簪束发，神情温和",
        },
        headers=auth_headers(user_id),
    )
    assert char_resp.status_code == 201, char_resp.text
    character_id = char_resp.json()["id"]
    calls: list[dict] = []

    async def _fake_image_config(*args, **kwargs):
        return "fake-image-key", "minimax", "image-01", "https://api.minimax.test/v1"

    class _FakeImageService:
        async def generate_image(self, **kwargs) -> dict:
            calls.append(kwargs)
            return {"data": {"image_base64": [_tiny_png_base64()]}, "task_id": "avatar-base64-task"}

    def _fake_create_service(*args, **kwargs):
        return _FakeImageService()

    monkeypatch.setattr("app.api.v1.endpoints.characters.get_user_image_model_config", _fake_image_config, raising=False)
    monkeypatch.setattr("app.api.v1.endpoints.characters.create_image_generation_service", _fake_create_service, raising=False)

    response = client.post(
        f"/api/v1/characters/{character_id}/generate-avatar",
        json={"style": "anime", "model_config_id": "minimax-image-config"},
        headers=auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "succeeded"
    assert data["avatar_url"].startswith("/static/generated/images/")
    assert data["character"]["avatar"] == data["avatar_url"]
    assert calls and calls[0]["response_format"] == "base64"
    assert "通用负面约束" in calls[0]["prompt"]
    assert "不要把多个无关画面拼在一起" in calls[0]["prompt"]


def test_novel_cover_generation_requests_minimax_base64_and_persists(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = f"cover-minimax-image-user-{uuid4()}"
    novel_id = _create_novel(client, user_id)
    calls: list[dict] = []

    async def _fake_image_config(*args, **kwargs):
        return "fake-image-key", "minimax", "image-01", "https://api.minimax.test/v1"

    class _FakeImageService:
        async def generate_image(self, **kwargs) -> dict:
            calls.append(kwargs)
            return {"data": {"image_base64": [_tiny_png_base64()]}, "task_id": "cover-base64-task"}

    def _fake_create_service(*args, **kwargs):
        return _FakeImageService()

    monkeypatch.setattr("app.api.v1.endpoints.novels.get_user_image_model_config", _fake_image_config, raising=False)
    monkeypatch.setattr("app.api.v1.endpoints.novels.create_image_generation_service", _fake_create_service, raising=False)

    response = client.post(
        f"/api/v1/novels/{novel_id}/generate-cover",
        json={"style": "anime", "model_config_id": "minimax-image-config"},
        headers=auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "succeeded"
    assert data["cover_url"].startswith("/static/generated/images/")
    assert calls and calls[0]["response_format"] == "base64"
    assert "通用负面约束" in calls[0]["prompt"]
    assert "不要把多个无关画面拼在一起" in calls[0]["prompt"]


def test_asset_character_generation_uses_configured_image_model_and_persists_base64(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = f"asset-character-image-user-{uuid4()}"
    novel_id = _create_novel(client, user_id)
    char_resp = client.post(
        "/api/v1/characters",
        json={
            "novel_id": novel_id,
            "name": "顾寒霜",
            "description": "少年剑修，黑衣，冷峻，背负古剑",
            "appearance": "黑色劲装，银色发带，眉眼锋利",
        },
        headers=auth_headers(user_id),
    )
    assert char_resp.status_code == 201, char_resp.text
    character_id = char_resp.json()["id"]
    calls: list[dict] = []

    async def _fake_image_config(*args, **kwargs):
        return "fake-image-key", "minimax", "image-01", "https://api.minimax.test/v1"

    class _FakeImageService:
        async def generate_image(self, **kwargs) -> dict:
            calls.append(kwargs)
            return {"data": {"image_base64": [_tiny_png_base64()]}, "task_id": f"asset-base64-task-{len(calls)}"}

    def _fake_create_service(*args, **kwargs):
        return _FakeImageService()

    monkeypatch.setattr("app.services.asset_generation_service.get_user_image_model_config", _fake_image_config, raising=False)
    monkeypatch.setattr("app.services.asset_generation_service.create_image_generation_service", _fake_create_service, raising=False)
    monkeypatch.setattr("app.api.v1.endpoints.assets.get_user_image_model_config", _fake_image_config, raising=False)
    monkeypatch.setattr("app.api.v1.endpoints.assets.create_image_generation_service", _fake_create_service, raising=False)

    response = client.post(
        "/api/v1/assets/generate-character",
        json={"character_id": character_id, "style": "anime", "model_config_id": "minimax-image-config"},
        headers=auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] >= 3
    assert data["assets"]["avatar"]["url"].startswith("/static/generated/images/")
    assert calls
    assert all(call["response_format"] == "base64" for call in calls)


def test_shot_generate_image_uses_default_image_model_and_parses_nested_urls(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = f"shot-direct-image-user-{uuid4()}"
    novel_id = _create_novel(client, user_id)
    shot_id = _create_shot(client, user_id, novel_id)
    image_url = f"https://cdn.example.com/generated/{uuid4()}.png"
    calls: list[dict] = []

    async def _fake_image_config(*args, **kwargs):
        assert kwargs.get("config_id") == "shot-style-config"
        return "fake-image-key", "minimax", "MiniMax-M3", "https://api.minimax.test/v1"

    async def _fake_volcano_key(*args, **kwargs):
        raise AssertionError("shot reference image should use the configured image model")

    class _FakeImageService:
        async def generate_image(self, **kwargs) -> dict:
            calls.append(kwargs)
            return {"data": {"image_urls": [image_url]}, "task_id": "m3-shot-image-task"}

    def _fake_create_service(api_key: str, provider_name: str, base_url: str):
        assert api_key == "fake-image-key"
        assert provider_name == "minimax"
        assert base_url == "https://api.minimax.test/v1"
        return _FakeImageService()

    async def _fake_persist(url: str, **kwargs) -> str:
        return url

    monkeypatch.setattr("app.api.v1.endpoints.shots.get_user_image_model_config", _fake_image_config, raising=False)
    monkeypatch.setattr("app.api.v1.endpoints.shots.create_image_generation_service", _fake_create_service, raising=False)
    monkeypatch.setattr("app.api.v1.endpoints.shots.get_user_volcano_api_key", _fake_volcano_key, raising=False)
    monkeypatch.setattr("app.api.v1.endpoints.shots.persist_remote_media_url", _fake_persist, raising=False)

    response = client.post(
        f"/api/v1/shots/{shot_id}/generate-image",
        json={"style": "xianxia", "model_config_id": "shot-style-config"},
        headers=auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "succeeded"
    assert data["image_url"] == image_url
    assert data["message"] == "参考图已生成"
    assert calls and calls[0]["model"] == "MiniMax-M3"
    assert "东方修仙动画设定图" in calls[0]["prompt"]
    assert "通用负面约束" in calls[0]["prompt"]
    assert "不要把多个无关画面拼在一起" in calls[0]["prompt"]
    shot_resp = client.get(f"/api/v1/shots/{shot_id}", headers=auth_headers(user_id))
    assert shot_resp.status_code == 200
    assert shot_resp.json()["image_url"] == image_url
    assert shot_resp.json()["image_status"] == "succeeded"
    asset_resp = client.get(f"/api/v1/assets/{shot_resp.json()['image_asset_id']}", headers=auth_headers(user_id))
    assert asset_resp.status_code == 200
    assert asset_resp.json()["generation_params"]["style"] == "xianxia"
    assert "东方修仙动画设定图" in asset_resp.json()["generation_params"]["style_prompt"]


def test_shot_reference_image_prompt_uses_shot_scene_prop_and_gender_context(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = f"shot-context-image-user-{uuid4()}"
    novel_id = _create_novel(client, user_id)
    chapter_resp = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "青阳宗外门",
            "chapter_number": 2,
            "content": "沈月璃在青阳宗外门石屋醒来，旧铜钩悬在门梁上。",
        },
        headers=auth_headers(user_id),
    )
    assert chapter_resp.status_code == 201, chapter_resp.text
    chapter_id = chapter_resp.json()["id"]
    script_resp = client.post(
        "/api/v1/scripts",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "title": "第二章剧本",
            "content": "沈月璃扶着石墙站起，镜头带到旧铜钩和昏暗石屋。",
        },
        headers=auth_headers(user_id),
    )
    assert script_resp.status_code == 201, script_resp.text
    storyboard_resp = client.post(
        "/api/v1/storyboards",
        json={
            "script_id": script_resp.json()["id"],
            "title": "石屋醒转",
            "description": "交代人物状态、场景和道具",
        },
        headers=auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201, storyboard_resp.text
    storyboard_id = storyboard_resp.json()["id"]
    char_resp = client.post(
        "/api/v1/characters",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "name": "沈月璃",
            "description": "女性剑修，刚醒来，虚弱但警觉",
            "appearance": "女性角色，青白衣裙，黑色长发，脸色苍白，不得改成男性",
        },
        headers=auth_headers(user_id),
    )
    assert char_resp.status_code == 201, char_resp.text
    _create_entity(
        client,
        user_id,
        novel_id=novel_id,
        chapter_id=chapter_id,
        entity_type="character",
        name="沈月璃",
        description="女性剑修，青白衣裙，黑色长发，脸色苍白。",
    )
    _create_entity(
        client,
        user_id,
        novel_id=novel_id,
        chapter_id=chapter_id,
        entity_type="scene",
        name="青阳宗外门石屋",
        description="昏暗石屋，木门半开，冷色晨光从门缝进入。",
    )
    _create_entity(
        client,
        user_id,
        novel_id=novel_id,
        chapter_id=chapter_id,
        entity_type="prop",
        name="旧铜钩",
        description="门梁上生锈的铜钩，是本镜头的关键道具。",
    )
    shot_resp = client.post(
        "/api/v1/shots",
        json={
            "storyboard_id": storyboard_id,
            "shot_number": 1,
            "duration": 4,
            "prompt": "沈月璃扶着青阳宗外门石屋的石墙站起，旧铜钩在前景晃动。",
            "visual_description": "中景，人物在画面右侧，旧铜钩前景虚化，石屋环境必须清楚。",
            "dialogue": "我还不能倒下。",
        },
        headers=auth_headers(user_id),
    )
    assert shot_resp.status_code == 201, shot_resp.text
    shot_id = shot_resp.json()["id"]
    calls: list[dict] = []

    async def _fake_image_config(*args, **kwargs):
        return "fake-image-key", "minimax", "image-01", "https://api.minimax.test/v1"

    class _FakeImageService:
        async def generate_image(self, **kwargs) -> dict:
            calls.append(kwargs)
            return {"data": {"image_urls": [f"https://cdn.example.com/generated/{uuid4()}.png"]}}

    def _fake_create_service(*args, **kwargs):
        return _FakeImageService()

    async def _fake_persist(url: str, **kwargs) -> str:
        return url

    monkeypatch.setattr("app.api.v1.endpoints.shots.get_user_image_model_config", _fake_image_config, raising=False)
    monkeypatch.setattr("app.api.v1.endpoints.shots.create_image_generation_service", _fake_create_service, raising=False)
    monkeypatch.setattr("app.api.v1.endpoints.shots.persist_remote_media_url", _fake_persist, raising=False)

    response = client.post(
        f"/api/v1/shots/{shot_id}/generate-image",
        json={"style": "xianxia"},
        headers=auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    prompt = calls[0]["prompt"]
    assert "镜头参考图" in prompt
    assert "不是角色头像" in prompt
    assert "不是单独人物立绘" in prompt
    assert "沈月璃" in prompt
    assert "女性" in prompt
    assert "不得改成男性" in prompt
    assert "青阳宗外门石屋" in prompt
    assert "旧铜钩" in prompt
    assert "整镜头构图" in prompt
    assert "不要只生成局部身体特写" in prompt


def test_storyboard_batch_generate_images_accepts_style_template_payload(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = f"storyboard-shot-style-user-{uuid4()}"
    novel_id = _create_novel(client, user_id)
    shot_id = _create_shot(client, user_id, novel_id)
    shot_resp = client.get(f"/api/v1/shots/{shot_id}", headers=auth_headers(user_id))
    assert shot_resp.status_code == 200
    storyboard_id = shot_resp.json()["storyboard_id"]
    calls: list[dict] = []

    async def _fake_image_config(*args, **kwargs):
        return "fake-image-key", "minimax", "MiniMax-M3", "https://api.minimax.test/v1"

    class _FakeImageService:
        async def generate_image(self, **kwargs) -> dict:
            calls.append(kwargs)
            return {"data": {"image_urls": [f"https://cdn.example.com/generated/{uuid4()}.png"]}, "task_id": "batch-style-task"}

    def _fake_create_service(*args, **kwargs):
        return _FakeImageService()

    async def _fake_persist(url: str, **kwargs) -> str:
        return url

    monkeypatch.setattr("app.api.v1.endpoints.shots.get_user_image_model_config", _fake_image_config, raising=False)
    monkeypatch.setattr("app.api.v1.endpoints.shots.create_image_generation_service", _fake_create_service, raising=False)
    monkeypatch.setattr("app.api.v1.endpoints.shots.persist_remote_media_url", _fake_persist, raising=False)

    response = client.post(
        f"/api/v1/storyboards/{storyboard_id}/shots/generate-images",
        json={"shot_ids": [shot_id], "style": "wuxia"},
        headers=auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    assert response.json()["results"][0]["status"] == "succeeded"
    assert calls and "武侠动画设定图" in calls[0]["prompt"]


def test_shot_generate_image_marks_non_pollable_missing_url_as_failed(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = f"shot-image-missing-url-user-{uuid4()}"
    novel_id = _create_novel(client, user_id)
    shot_id = _create_shot(client, user_id, novel_id)

    async def _fake_image_config(*args, **kwargs):
        return "fake-image-key", "minimax", "MiniMax-M3", "https://api.minimax.test/v1"

    class _FakeImageService:
        async def generate_image(self, **kwargs) -> dict:
            return {"task_id": "m3-task-without-url", "status": "submitted"}

    def _fake_create_service(*args, **kwargs):
        return _FakeImageService()

    monkeypatch.setattr("app.api.v1.endpoints.shots.get_user_image_model_config", _fake_image_config, raising=False)
    monkeypatch.setattr("app.api.v1.endpoints.shots.create_image_generation_service", _fake_create_service, raising=False)

    response = client.post(f"/api/v1/shots/{shot_id}/generate-image", headers=auth_headers(user_id))

    assert response.status_code == 500
    assert "未返回图片URL" in response.json()["detail"]
    shot_resp = client.get(f"/api/v1/shots/{shot_id}", headers=auth_headers(user_id))
    assert shot_resp.status_code == 200
    assert shot_resp.json()["image_status"] == "failed"
    assert not shot_resp.json()["image_url"]
    assert "未返回图片URL" in shot_resp.json()["extra_data"]["image_generation_error"]


def test_shot_generate_image_persists_minimax_base64_reference_image(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = f"shot-image-base64-user-{uuid4()}"
    novel_id = _create_novel(client, user_id)
    shot_id = _create_shot(client, user_id, novel_id)
    tiny_png_base64 = _tiny_png_base64()
    calls: list[dict] = []

    async def _fake_image_config(*args, **kwargs):
        return "fake-image-key", "minimax", "image-01", "https://api.minimax.test/v1"

    class _FakeImageService:
        async def generate_image(self, **kwargs) -> dict:
            calls.append(kwargs)
            return {"data": {"image_base64": [tiny_png_base64]}, "task_id": "m3-base64-task"}

    def _fake_create_service(*args, **kwargs):
        return _FakeImageService()

    monkeypatch.setattr("app.api.v1.endpoints.shots.get_user_image_model_config", _fake_image_config, raising=False)
    monkeypatch.setattr("app.api.v1.endpoints.shots.create_image_generation_service", _fake_create_service, raising=False)

    response = client.post(f"/api/v1/shots/{shot_id}/generate-image", headers=auth_headers(user_id))

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "succeeded"
    assert data["image_url"].startswith("/static/generated/images/")
    assert calls and calls[0]["response_format"] == "base64"
    shot_resp = client.get(f"/api/v1/shots/{shot_id}", headers=auth_headers(user_id))
    assert shot_resp.status_code == 200
    assert shot_resp.json()["image_url"].startswith("/static/generated/images/")
    assert shot_resp.json()["image_status"] == "succeeded"
