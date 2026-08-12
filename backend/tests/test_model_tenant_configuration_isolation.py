from __future__ import annotations

import httpx
import pytest
import pytest_asyncio

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.model_center import ModelConnection, ModelProvider, ProductionRecipeVersion
from app.models.prompt_profile import PromptProfile, PromptProfileVersion
from main import app
from tests.model_center_api_database import SessionLocal, dispose_database, reset_database


ADMIN = "catalog-admin"
OTHER = "catalog-reader"


@pytest_asyncio.fixture(scope="module", autouse=True)
async def isolated_database():
    await reset_database()
    yield
    await dispose_database()


@pytest_asyncio.fixture()
async def client(monkeypatch):
    monkeypatch.setenv("MODEL_CATALOG_ADMIN_USER_IDS", ADMIN)

    async def override_db():
        async with SessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_id] = lambda: ADMIN
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
    ) as api_client:
        yield api_client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_catalog_is_shared_but_ordinary_user_cannot_mutate(client):
    async with SessionLocal() as db:
        db.add(ModelProvider(
            id="shared-provider", code="shared-provider", display_name="共享供应商",
            provider_family="test", enabled=True,
        ))
        await db.commit()

    admin_list = await client.get("/api/v1/model-center/providers")
    app.dependency_overrides[get_current_user_id] = lambda: OTHER
    reader_list = await client.get("/api/v1/model-center/providers")
    denied = await client.post("/api/v1/model-center/providers", json={
        "code": "reader-provider", "display_name": "越权供应商", "provider_family": "test",
    })

    assert [row["id"] for row in admin_list.json()["items"]] == [
        row["id"] for row in reader_list.json()["items"]
    ]
    assert denied.status_code == 403
    assert denied.json()["detail"]["message"] == "只有模型目录管理员可以维护共享供应商和模型。"


@pytest.mark.asyncio
async def test_connections_recipes_and_defaults_remain_user_private(client):
    async with SessionLocal() as db:
        db.add_all([
            ModelConnection(
                id="admin-connection", user_id=ADMIN, provider_id="shared-provider",
                name="管理员私有连接", status="draft",
            ),
            ProductionRecipeVersion(
                id="admin-recipe", user_id=ADMIN, recipe_key="private-recipe",
                name="管理员私有方案", version=1, spec={}, checksum="r" * 64,
            ),
        ])
        await db.commit()

    app.dependency_overrides[get_current_user_id] = lambda: ADMIN
    admin_connections = await client.get("/api/v1/model-center/connections")
    admin_recipes = await client.get("/api/v1/model-center/recipes")
    app.dependency_overrides[get_current_user_id] = lambda: OTHER
    reader_connections = await client.get("/api/v1/model-center/connections")
    reader_recipes = await client.get("/api/v1/model-center/recipes")

    assert admin_connections.json()["meta"]["total"] == 1
    assert reader_connections.json()["meta"]["total"] == 0
    assert admin_recipes.json()["meta"]["total"] == 1
    assert reader_recipes.json()["meta"]["total"] == 0


@pytest.mark.asyncio
async def test_system_prompt_is_shared_visible_and_read_only(client):
    async with SessionLocal() as db:
        db.add_all([
            PromptProfile(
                id="system-prompt", user_id="system", key="system.shared.prompt",
                name="系统共享模板", task="chapter_generation",
            ),
            PromptProfileVersion(
                id="system-prompt-v1", profile_id="system-prompt", version=1,
                content="共享模板正文", variables={}, routing={}, evaluation={},
                status="published", checksum="p" * 64,
            ),
        ])
        await db.commit()

    app.dependency_overrides[get_current_user_id] = lambda: ADMIN
    admin_list = await client.get("/api/v1/model-center/prompt-profiles?page_size=100")
    app.dependency_overrides[get_current_user_id] = lambda: OTHER
    reader_list = await client.get("/api/v1/model-center/prompt-profiles?page_size=100")
    detail = await client.get("/api/v1/model-center/prompt-profiles/system-prompt")
    denied = await client.post(
        "/api/v1/model-center/prompt-profiles/system-prompt/versions",
        json={"expected_revision": 1, "task_template": "越权修改"},
    )

    assert any(row["id"] == "system-prompt" for row in admin_list.json()["items"])
    assert any(row["id"] == "system-prompt" for row in reader_list.json()["items"])
    assert detail.json()["editable"] is False
    assert denied.status_code == 403
    assert denied.json()["detail"]["message"] == "系统基础模板为共享只读，请先复制为当前账号模板。"
