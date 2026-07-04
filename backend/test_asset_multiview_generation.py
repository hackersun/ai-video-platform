from __future__ import annotations

import base64
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from init_db import init_db
from main import app
from app.services.asset_generation_service import AssetGenerationService, style_keywords_for


@pytest.fixture(scope="module", autouse=True)
def _init_database() -> None:
    init_db()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DEV_MODE", "true")
    return TestClient(app)


def auth_headers(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


def _tiny_png_base64() -> str:
    return base64.b64encode(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
        )
    ).decode("ascii")


def _png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as file:
        header = file.read(24)
    assert header[:8] == b"\x89PNG\r\n\x1a\n", path
    return int.from_bytes(header[16:20], "big"), int.from_bytes(header[20:24], "big")


def _create_novel(client: TestClient, user_id: str) -> str:
    response = client.post(
        "/api/v1/novels",
        json={"title": f"多视图资产小说-{uuid4()}", "genre": "玄幻", "description": "少年携古剑进入秘境。"},
        headers=auth_headers(user_id),
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _create_entity(client: TestClient, user_id: str, novel_id: str, entity_type: str, name: str) -> str:
    response = client.post(
        "/api/v1/story-bibles/entities",
        json={
            "novel_id": novel_id,
            "entity_type": entity_type,
            "name": name,
            "description": "黑衣少年，银色发带，背负古剑。" if entity_type == "character" else "幽蓝灵气环绕，石阶通向秘境深处。",
            "attributes": {"appearance": "黑衣，古剑，冷峻眉眼"} if entity_type == "character" else {"mood": "神秘"},
        },
        headers=auth_headers(user_id),
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _create_character(client: TestClient, user_id: str, novel_id: str, name: str) -> str:
    response = client.post(
        "/api/v1/characters",
        json={
            "novel_id": novel_id,
            "name": name,
            "description": "黑衣少年剑修，银色发带，背负古剑。",
            "appearance": "少年男性，黑衣，银色发带，背负古剑，冷峻眉眼。",
            "tags": ["主角", "剑修"],
        },
        headers=auth_headers(user_id),
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _create_asset(
    client: TestClient,
    user_id: str,
    *,
    name: str,
    category: str = "character",
    novel_id: str | None = None,
    entity_id: str | None = None,
    entity_type: str | None = None,
    generation_params: dict | None = None,
) -> dict:
    response = client.post(
        "/api/v1/assets",
        json={
            "category": category,
            "asset_type": "image",
            "name": name,
            "url": f"/static/dev/{name}.png",
            "thumbnail_url": f"/static/dev/{name}.png",
            "novel_id": novel_id,
            "entity_id": entity_id,
            "entity_type": entity_type,
            "generation_params": generation_params or {},
        },
        headers=auth_headers(user_id),
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_asset_view_presets_are_creator_friendly(client: TestClient) -> None:
    user_id = f"asset-view-preset-user-{uuid4()}"

    response = client.get("/api/v1/assets/view-presets", headers=auth_headers(user_id))

    assert response.status_code == 200, response.text
    data = response.json()
    assert [item["entity_type"] for item in data["presets"]] == ["character", "scene", "prop"]
    character = next(item for item in data["presets"] if item["entity_type"] == "character")
    assert character["title"] == "角色三视图"
    assert [view["key"] for view in character["views"]] == ["front", "side", "back"]
    assert all(view["label"] and view["prompt_hint"] for view in character["views"])
    assert "9:16" in character["recommended_aspect_ratios"]
    assert any(example["style"] == "xianxia" and example["prompt"] for example in character["style_examples"])
    scene = next(item for item in data["presets"] if item["entity_type"] == "scene")
    assert scene["title"] == "场景四视图"
    assert len(scene["views"]) == 4
    assert any(example["style"] == "wuxia" and example["sample_url"] for example in scene["style_examples"])
    prop = next(item for item in data["presets"] if item["entity_type"] == "prop")
    assert prop["title"] == "道具多视图"
    assert len(prop["views"]) >= 4
    assert "1:1" in prop["recommended_aspect_ratios"]


def test_image_style_templates_are_shared_for_image_generation_entries(client: TestClient) -> None:
    user_id = f"asset-style-template-user-{uuid4()}"

    response = client.get("/api/v1/assets/style-templates", headers=auth_headers(user_id))

    assert response.status_code == 200, response.text
    data = response.json()
    styles = {item["style"]: item for item in data["templates"]}
    assert len(data["templates"]) >= 30
    assert {"anime", "xianxia", "wuxia", "fantasy", "urban", "q-3d", "pixel-2d", "clay-stopmotion"} <= set(styles)
    assert styles["xianxia"]["label"] == "修仙仙侠"
    assert styles["q-3d"]["label"] == "3DQ版"
    assert styles["pixel-2d"]["label"] == "2D像素"
    assert styles["xianxia"]["sample_url"].startswith("/static/starter/")
    assert "提示词" not in styles["xianxia"]["label"]
    assert styles["xianxia"]["prompt"]
    assert "character" in styles["xianxia"]["recommended_for"]
    assert "scene" in styles["wuxia"]["recommended_for"]
    assert data["default_style"] == "anime"


def test_asset_style_and_view_preset_sample_images_exist(client: TestClient) -> None:
    user_id = f"asset-sample-image-user-{uuid4()}"
    static_dir = Path(__file__).resolve().parent / "static"

    style_response = client.get("/api/v1/assets/style-templates", headers=auth_headers(user_id))
    preset_response = client.get("/api/v1/assets/view-presets", headers=auth_headers(user_id))

    assert style_response.status_code == 200, style_response.text
    assert preset_response.status_code == 200, preset_response.text

    sample_urls = [
        item.get("sample_url")
        for item in style_response.json()["templates"]
        if item.get("sample_url")
    ]
    for preset in preset_response.json()["presets"]:
        sample_urls.extend(
            example.get("sample_url")
            for example in preset.get("style_examples", [])
            if example.get("sample_url")
        )

    missing = []
    for url in sample_urls:
        assert url.startswith("/static/"), url
        if not (static_dir / url.removeprefix("/static/")).exists():
            missing.append(url)

    assert missing == []


def test_asset_style_reference_images_are_real_cards(client: TestClient) -> None:
    user_id = f"asset-style-card-user-{uuid4()}"
    static_dir = Path(__file__).resolve().parent / "static"

    response = client.get("/api/v1/assets/style-templates", headers=auth_headers(user_id))

    assert response.status_code == 200, response.text
    checked = 0
    for item in response.json()["templates"]:
        url = item.get("sample_url")
        if not url or not url.endswith(".png"):
            continue
        path = static_dir / url.removeprefix("/static/")
        width, height = _png_dimensions(path)
        assert width >= 600
        assert height >= 330
        assert path.stat().st_size > 4_000
        checked += 1

    assert checked >= 30


def test_extended_style_prompts_drive_asset_generation() -> None:
    service = AssetGenerationService(db=None, user_id="style-prompt-test")  # type: ignore[arg-type]

    gongbi_prompt = style_keywords_for("gongbi-2d")
    avatar_prompt = service._build_avatar_prompt("云璃", "女性仙门弟子，白衣金饰，温柔坚定。", "gongbi-2d")
    prop_prompt = service._build_prop_prompt("青玉令", "半透明玉牌，刻有云纹，淡青灵光。", "q-3d")

    assert "工笔" in gongbi_prompt
    assert gongbi_prompt in avatar_prompt
    assert "3D Q版" in prop_prompt
    assert "anime style" not in avatar_prompt
    assert "通用负面约束" in avatar_prompt
    assert "单个核心道具" in prop_prompt


def test_unknown_style_falls_back_to_anime_not_realistic() -> None:
    prompt = style_keywords_for("玄幻")

    assert "2D日系动画" in prompt
    assert "真人写实" not in prompt


def test_asset_entity_filter_does_not_mix_global_assets(client: TestClient) -> None:
    user_id = f"asset-filter-user-{uuid4()}"
    novel_id = _create_novel(client, user_id)
    entity_id = _create_entity(client, user_id, novel_id, "character", "单人角色")
    _create_asset(
        client,
        user_id,
        name="全局角色参考",
        category="character",
        generation_params={"source": "starter"},
    )
    scoped_asset = _create_asset(
        client,
        user_id,
        name="单人角色正面",
        category="character",
        novel_id=novel_id,
        entity_id=entity_id,
        entity_type="character",
        generation_params={"source": "entity_multiview", "view_key": "front"},
    )

    response = client.get(
        f"/api/v1/assets?novel_id={novel_id}&entity_id={entity_id}&category=character&include_public=false&limit=20",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    ids = [item["id"] for item in response.json()]
    assert scoped_asset["id"] in ids
    assert len(ids) == 1


def test_composite_character_entity_is_rejected_for_single_character_views(client: TestClient) -> None:
    user_id = f"asset-composite-user-{uuid4()}"
    novel_id = _create_novel(client, user_id)
    entity_id = _create_entity(client, user_id, novel_id, "character", "孙剑（逆天至尊）、外门弟子们")

    response = client.post(
        "/api/v1/assets/generate-entity-views",
        json={"entity_id": entity_id, "view_keys": ["front"], "style": "xianxia"},
        headers=auth_headers(user_id),
    )

    assert response.status_code == 422, response.text
    assert "单一角色" in response.json()["detail"]


def test_generate_entity_views_rejects_mismatched_novel_scope(client: TestClient) -> None:
    user_id = f"asset-scope-mismatch-user-{uuid4()}"
    entity_novel_id = _create_novel(client, user_id)
    requested_novel_id = _create_novel(client, user_id)
    entity_id = _create_entity(client, user_id, entity_novel_id, "character", "顾寒霜")

    response = client.post(
        "/api/v1/assets/generate-entity-views",
        json={
            "entity_id": entity_id,
            "novel_id": requested_novel_id,
            "view_keys": ["front"],
            "style": "anime",
        },
        headers=auth_headers(user_id),
    )

    assert response.status_code == 400, response.text
    assert "实体不属于指定小说" in response.json()["detail"]


def test_generate_entity_views_rejects_script_inferred_novel_scope_mismatch(client: TestClient) -> None:
    user_id = f"asset-script-scope-mismatch-user-{uuid4()}"
    entity_novel_id = _create_novel(client, user_id)
    script_novel_id = _create_novel(client, user_id)
    entity_id = _create_entity(client, user_id, entity_novel_id, "character", "顾寒霜")
    script_response = client.post(
        "/api/v1/scripts",
        json={
            "novel_id": script_novel_id,
            "title": "异书剧本",
            "content": "角色：陌生人。场景：另一座山门。",
        },
        headers=auth_headers(user_id),
    )
    assert script_response.status_code == 201, script_response.text

    response = client.post(
        "/api/v1/assets/generate-entity-views",
        json={
            "entity_id": entity_id,
            "script_id": script_response.json()["id"],
            "view_keys": ["front"],
            "style": "anime",
        },
        headers=auth_headers(user_id),
    )

    assert response.status_code == 400, response.text
    assert "实体不属于指定小说" in response.json()["detail"]


def test_standard_entity_view_generation_requires_novel_scope(client: TestClient) -> None:
    user_id = f"asset-standard-scope-user-{uuid4()}"
    response = client.post(
        "/api/v1/story-bibles/entities",
        json={
            "entity_type": "character",
            "name": "无小说角色",
            "description": "没有绑定小说的测试角色。",
            "attributes": {"appearance": "灰色外套"},
        },
        headers=auth_headers(user_id),
    )
    assert response.status_code == 201, response.text
    entity_id = response.json()["id"]

    generate_response = client.post(
        "/api/v1/assets/generate-entity-views",
        json={
            "entity_id": entity_id,
            "view_keys": ["front"],
            "style": "anime",
            "consistency_mode": "standard",
        },
        headers=auth_headers(user_id),
    )

    assert generate_response.status_code == 422, generate_response.text
    assert "标准/严格一致性模式需要绑定小说" in generate_response.json()["detail"]


def test_generate_entity_views_persists_novel_linked_assets(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = f"asset-view-generate-user-{uuid4()}"
    novel_id = _create_novel(client, user_id)
    entity_id = _create_entity(client, user_id, novel_id, "character", "顾寒霜")
    calls: list[dict] = []

    async def _fake_image_config(*args, **kwargs):
        return "fake-image-key", "minimax", "image-01", "https://api.minimax.test/v1"

    class _FakeImageService:
        async def generate_image(self, **kwargs) -> dict:
            calls.append(kwargs)
            return {"data": {"image_base64": [_tiny_png_base64()]}, "task_id": f"multiview-task-{len(calls)}"}

    def _fake_create_service(*args, **kwargs):
        return _FakeImageService()

    monkeypatch.setattr("app.services.asset_generation_service.get_user_image_model_config", _fake_image_config, raising=False)
    monkeypatch.setattr("app.services.asset_generation_service.create_image_generation_service", _fake_create_service, raising=False)

    skill_response = client.post(
        "/api/v1/prompt-skills",
        json={
            "name": "角色多视图强约束",
            "task": "character_image",
            "stage": "image",
            "content": "用户角色图模板：{entity_name}所有视图保持银色发带和古剑。",
            "is_active": True,
        },
        headers=auth_headers(user_id),
    )
    assert skill_response.status_code == 201, skill_response.text

    response = client.post(
        "/api/v1/assets/generate-entity-views",
        json={"entity_id": entity_id, "view_keys": ["front", "side", "back"], "style": "anime"},
        headers=auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["entity_id"] == entity_id
    assert payload["entity_type"] == "character"
    assert payload["total"] == 3
    assert set(payload["assets"]) == {"front", "side", "back"}
    assert len(calls) == 3
    assert all("用户角色图模板：顾寒霜所有视图保持银色发带和古剑。" in call["prompt"] for call in calls)
    for view_key, asset in payload["assets"].items():
        assert asset["url"].startswith("/static/generated/images/")
        assert asset["generation_params"]["view_key"] == view_key
        assert asset["generation_params"]["view_label"]
        assert asset["generation_params"]["entity_type"] == "character"
        assert asset["novel_id"] == novel_id
        assert asset["entity_id"] == entity_id
        assert asset["entity_type"] == "character"
        assert asset["source_prompt"]
        assert "用户角色图模板：顾寒霜所有视图保持银色发带和古剑。" in asset["source_prompt"]

    list_response = client.get(
        f"/api/v1/assets?novel_id={novel_id}&entity_id={entity_id}&category=character&include_public=false&limit=20",
        headers=auth_headers(user_id),
    )
    assert list_response.status_code == 200
    listed_view_keys = {
        item["generation_params"]["view_key"]
        for item in list_response.json()
        if item.get("generation_params", {}).get("view_key")
    }
    assert {"front", "side", "back"} <= listed_view_keys

    front_id = payload["assets"]["front"]["id"]
    side_id = payload["assets"]["side"]["id"]
    assert client.post(f"/api/v1/assets/{front_id}/lock", headers=auth_headers(user_id)).status_code == 200
    assert client.post(f"/api/v1/assets/{side_id}/lock", headers=auth_headers(user_id)).status_code == 200

    entity_assets = client.get(
        f"/api/v1/assets/entity/{entity_id}?entity_type=character",
        headers=auth_headers(user_id),
    )
    assert entity_assets.status_code == 200
    locked_view_keys = {
        item["generation_params"]["view_key"]
        for item in entity_assets.json()["locked_assets"]
        if item.get("generation_params", {}).get("view_key")
    }
    assert {"front", "side"} <= locked_view_keys


def test_generate_character_entity_views_are_linked_to_character_records_for_video_consistency(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = f"asset-view-character-link-user-{uuid4()}"
    novel_id = _create_novel(client, user_id)
    character_id = _create_character(client, user_id, novel_id, "孙剑")
    entity_id = _create_entity(client, user_id, novel_id, "character", "孙剑")

    async def _fake_image_config(*args, **kwargs):
        return "fake-image-key", "minimax", "image-01", "https://api.minimax.test/v1"

    class _FakeImageService:
        async def generate_image(self, **kwargs) -> dict:
            return {"data": {"image_base64": [_tiny_png_base64()]}, "task_id": "linked-character-view"}

    monkeypatch.setattr("app.services.asset_generation_service.get_user_image_model_config", _fake_image_config, raising=False)
    monkeypatch.setattr("app.services.asset_generation_service.create_image_generation_service", lambda *args, **kwargs: _FakeImageService(), raising=False)

    response = client.post(
        "/api/v1/assets/generate-entity-views",
        json={"entity_id": entity_id, "view_keys": ["front", "side", "back"], "style": "xianxia"},
        headers=auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    for view_key, asset in response.json()["assets"].items():
        assert asset["entity_id"] == entity_id
        assert asset["character_id"] == character_id
        assert asset["generation_params"]["reference_role"] == "character_multiview"
        assert asset["generation_params"]["view_angle"] == view_key


def test_video_multiview_collection_accepts_legacy_entity_linked_character_assets() -> None:
    from app.api.v1.endpoints.video import _collect_character_multiview_refs

    legacy_asset = SimpleNamespace(
        id="legacy-back-asset",
        category="character",
        character_id=None,
        entity_id="entity-sunjian",
        name="孙剑 · 背面",
        url="/static/generated/images/sunjian-back.png",
        thumbnail_url=None,
        version=3,
        is_locked=True,
        is_final=False,
        generation_params={
            "source": "entity_multiview",
            "reference_role": "character_multiview",
            "view_angle": "back",
        },
    )

    refs = _collect_character_multiview_refs(
        [legacy_asset],
        [{"entity_id": "entity-sunjian", "character_id": "character-sunjian", "name": "孙剑"}],
    )

    assert refs == [
        {
            "asset_id": "legacy-back-asset",
            "character_id": "character-sunjian",
            "character_name": "孙剑",
            "name": "孙剑 · 背面",
            "view_angle": "back",
            "url": "/static/generated/images/sunjian-back.png",
            "thumbnail_url": None,
            "version": 3,
            "is_locked": True,
            "is_final": False,
            "reference_role": "character_multiview",
        }
    ]


def test_regenerate_entity_view_asset_keeps_view_lineage_and_front_reference(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = f"asset-regenerate-user-{uuid4()}"
    novel_id = _create_novel(client, user_id)
    character_id = _create_character(client, user_id, novel_id, "孙剑")
    entity_id = _create_entity(client, user_id, novel_id, "character", "孙剑")
    front = _create_asset(
        client,
        user_id,
        name="孙剑正面定稿",
        category="character",
        novel_id=novel_id,
        entity_id=entity_id,
        entity_type="character",
        generation_params={
            "source": "entity_multiview",
            "view_key": "front",
            "view_angle": "front",
            "reference_role": "character_multiview",
            "style": "xianxia",
        },
    )
    side = _create_asset(
        client,
        user_id,
        name="孙剑侧面旧版本",
        category="character",
        novel_id=novel_id,
        entity_id=entity_id,
        entity_type="character",
        generation_params={
            "source": "entity_multiview",
            "view_key": "side",
            "view_angle": "side",
            "reference_role": "character_multiview",
            "style": "xianxia",
        },
    )
    assert client.post(f"/api/v1/assets/{front['id']}/lock", headers=auth_headers(user_id)).status_code == 200

    calls: list[dict] = []

    async def _fake_image_config(*args, **kwargs):
        return "fake-image-key", "minimax", "image-01", "https://api.minimax.test/v1"

    class _FakeImageService:
        async def generate_image(self, **kwargs) -> dict:
            calls.append(kwargs)
            return {"data": {"image_base64": [_tiny_png_base64()]}, "task_id": "regenerate-view"}

    monkeypatch.setattr("app.services.asset_generation_service.get_user_image_model_config", _fake_image_config, raising=False)
    monkeypatch.setattr("app.services.asset_generation_service.create_image_generation_service", lambda *args, **kwargs: _FakeImageService(), raising=False)

    response = client.post(
        f"/api/v1/assets/{side['id']}/regenerate",
        json={"style": "xianxia"},
        headers=auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    regenerated = response.json()
    assert regenerated["id"] != side["id"]
    assert regenerated["entity_id"] == entity_id
    assert regenerated["character_id"] == character_id
    assert regenerated["generation_params"]["view_key"] == "side"
    assert regenerated["generation_params"]["view_angle"] == "side"
    assert regenerated["generation_params"]["reference_role"] == "character_multiview"
    assert regenerated["generation_params"]["reference_view_key"] == "front"
    assert regenerated["generation_params"]["reference_asset_id"] == front["id"]
    assert regenerated["version"] == 2
    assert calls and "/static/dev/孙剑正面定稿.png" in calls[0]["prompt"]


def test_character_view_generation_uses_single_character_contract_and_prompt_policy(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = f"asset-view-contract-user-{uuid4()}"
    novel_id = _create_novel(client, user_id)
    entity_id = _create_entity(client, user_id, novel_id, "character", "孙剑")
    calls: list[dict] = []

    async def _fake_image_config(*args, **kwargs):
        return "fake-image-key", "minimax", "image-01", "https://api.minimax.test/v1"

    class _FakeImageService:
        async def generate_image(self, **kwargs) -> dict:
            calls.append(kwargs)
            return {"data": {"image_base64": [_tiny_png_base64()]}, "task_id": f"contract-task-{len(calls)}"}

    monkeypatch.setattr("app.services.asset_generation_service.get_user_image_model_config", _fake_image_config, raising=False)
    monkeypatch.setattr("app.services.asset_generation_service.create_image_generation_service", lambda *args, **kwargs: _FakeImageService(), raising=False)

    response = client.post(
        "/api/v1/assets/generate-entity-views",
        json={"entity_id": entity_id, "view_keys": ["front", "side", "back"], "style": "xianxia"},
        headers=auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    contracts = {
        asset["generation_params"]["visual_contract"]["id"]
        for asset in payload["assets"].values()
    }
    assert len(contracts) == 1
    assert payload["assets"]["front"]["generation_params"]["visual_contract"]["single_subject"] is True
    assert payload["assets"]["side"]["generation_params"]["reference_view_key"] == "front"
    assert payload["assets"]["back"]["generation_params"]["reference_view_key"] == "front"
    assert payload["assets"]["side"]["generation_params"]["visual_consistency"]["score"] >= 80

    prompts = "\n".join(call["prompt"] for call in calls)
    assert "孙剑" in prompts
    assert "单人" in prompts
    assert "禁止拼接图" in prompts
    assert "禁止多宫格" in prompts
    assert "禁止多人" in prompts
    assert "不要改变性别" in prompts
    assert "背对镜头" in prompts
    assert "脸部不可见" in prompts
    assert "禁止正面视角" in prompts
    assert "单张设定图" in prompts


def test_failed_entity_view_generation_is_recorded_and_retryable(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = f"asset-view-failure-user-{uuid4()}"
    novel_id = _create_novel(client, user_id)
    entity_id = _create_entity(client, user_id, novel_id, "character", "沈青岚")

    async def _fake_image_config(*args, **kwargs):
        return "fake-image-key", "minimax", "image-01", "https://api.minimax.test/v1"

    class _FailingImageService:
        async def generate_image(self, **kwargs) -> dict:
            raise RuntimeError("provider timeout")

    monkeypatch.setattr("app.services.asset_generation_service.get_user_image_model_config", _fake_image_config, raising=False)
    monkeypatch.setattr("app.services.asset_generation_service.create_image_generation_service", lambda *args, **kwargs: _FailingImageService(), raising=False)

    response = client.post(
        "/api/v1/assets/generate-entity-views",
        json={"entity_id": entity_id, "view_keys": ["front"], "style": "xianxia"},
        headers=auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total"] == 0
    assert len(payload["failures"]) == 1
    failure = payload["failures"][0]
    assert failure["asset_type"] == "text"
    assert failure["generation_params"]["status"] == "failed"
    assert failure["generation_params"]["view_key"] == "front"
    assert "provider timeout" in failure["generation_params"]["error_message"]

    class _SuccessfulImageService:
        async def generate_image(self, **kwargs) -> dict:
            return {"data": {"image_base64": [_tiny_png_base64()]}, "task_id": "retry-task-1"}

    monkeypatch.setattr("app.services.asset_generation_service.create_image_generation_service", lambda *args, **kwargs: _SuccessfulImageService(), raising=False)

    retry_response = client.post(
        f"/api/v1/assets/{failure['id']}/retry-generation",
        headers=auth_headers(user_id),
    )

    assert retry_response.status_code == 200, retry_response.text
    retry_payload = retry_response.json()
    assert retry_payload["total"] == 1
    assert retry_payload["assets"]["front"]["url"].startswith("/static/generated/images/")
    assert retry_payload["assets"]["front"]["generation_params"]["view_key"] == "front"


def test_visual_consistency_score_is_written_to_asset_history(client: TestClient) -> None:
    user_id = f"asset-visual-score-user-{uuid4()}"
    novel_id = _create_novel(client, user_id)
    entity_id = _create_entity(client, user_id, novel_id, "character", "洛云")
    create_response = client.post(
        "/api/v1/assets",
        json={
            "category": "character",
            "asset_type": "image",
            "name": "洛云 正面",
            "url": "/static/dev/luoyun-front.png",
            "thumbnail_url": "/static/dev/luoyun-front.png",
            "novel_id": novel_id,
            "entity_id": entity_id,
            "entity_type": "character",
            "generation_params": {"source": "entity_multiview", "view_key": "front", "view_label": "正面"},
        },
        headers=auth_headers(user_id),
    )
    assert create_response.status_code == 201, create_response.text
    asset_id = create_response.json()["id"]

    score_response = client.post(
        f"/api/v1/assets/{asset_id}/visual-consistency",
        json={
            "score": 87,
            "model": "manual-review",
            "reference_asset_ids": ["ref-front", "ref-side"],
            "issues": ["发带颜色略浅"],
            "notes": "人工复核通过，可继续用于视频生成。",
        },
        headers=auth_headers(user_id),
    )

    assert score_response.status_code == 200, score_response.text
    params = score_response.json()["generation_params"]
    assert params["visual_consistency"]["score"] == 87
    assert params["visual_consistency"]["model"] == "manual-review"
    assert params["visual_consistency"]["reference_asset_ids"] == ["ref-front", "ref-side"]
    assert params["visual_consistency_history"][0]["score"] == 87
