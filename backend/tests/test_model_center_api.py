from __future__ import annotations

import ast
import asyncio
import json
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, Base, engine, get_db
from app.core.security import get_current_user_id
from app.features.model_config.recipes import stable_recipe_checksum
from app.models.model_center import (
    ModelBinding,
    ModelConfigAuditEvent,
    ModelConnection,
    ModelProfile,
    ModelProfileVersion,
    ModelProvider,
    ProductionRecipeVersion,
)
from app.models.prompt_profile import PromptProfile, PromptProfileVersion
from main import app


USER_ID = "model-center-api-user"
MODEL_CENTER_ROUTES = {
    ("get", "/api/v1/model-center/overview"),
    ("get", "/api/v1/model-center/drivers"),
    ("post", "/api/v1/model-center/providers"),
    ("put", "/api/v1/model-center/providers/{provider_id}"),
    ("get", "/api/v1/model-center/connections"),
    ("post", "/api/v1/model-center/connections"),
    ("put", "/api/v1/model-center/connections/{connection_id}"),
    ("post", "/api/v1/model-center/connections/{connection_id}/test"),
    ("get", "/api/v1/model-center/catalog"),
    ("post", "/api/v1/model-center/profiles"),
    ("post", "/api/v1/model-center/profiles/{profile_id}/versions"),
    ("put", "/api/v1/model-center/profile-versions/{profile_version_id}"),
    ("post", "/api/v1/model-center/profile-versions/{profile_version_id}/publish"),
    ("post", "/api/v1/model-center/profile-versions/{profile_version_id}/disable"),
    ("post", "/api/v1/model-center/profiles/{profile_id}/rollback"),
    ("get", "/api/v1/model-center/bindings"),
    ("post", "/api/v1/model-center/bindings"),
    ("put", "/api/v1/model-center/bindings/{binding_id}"),
    ("get", "/api/v1/model-center/recipes"),
    ("post", "/api/v1/model-center/recipes"),
    ("post", "/api/v1/model-center/recipe-versions/{recipe_version_id}/publish"),
    ("post", "/api/v1/model-center/recipe-versions/{recipe_version_id}/disable"),
    ("post", "/api/v1/model-center/recipes/{recipe_key}/rollback"),
    ("get", "/api/v1/model-center/prompt-profiles"),
    ("post", "/api/v1/model-center/prompt-profiles"),
    ("post", "/api/v1/model-center/prompt-profiles/{profile_id}/versions"),
    ("post", "/api/v1/model-center/prompt-profile-versions/{version_id}/publish"),
    ("post", "/api/v1/model-center/prompt-profile-versions/{version_id}/disable"),
    ("post", "/api/v1/model-center/prompt-profiles/{profile_id}/rollback"),
    ("post", "/api/v1/model-center/certifications"),
    ("get", "/api/v1/model-center/certifications/{run_id}"),
    ("get", "/api/v1/model-center/impact"),
}


@pytest_asyncio.fixture(scope="module", autouse=True)
async def isolated_database():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as db:
        await _seed_collection_rows(db)
    yield
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture()
async def client():
    async def override_db():
        async with AsyncSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_id] = lambda: USER_ID
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as api_client:
        yield api_client
    app.dependency_overrides.clear()


def test_model_center_routes_are_registered():
    registered = {
        (method, path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
        if method in {"get", "post", "put", "patch", "delete"}
    }
    assert MODEL_CENTER_ROUTES <= registered


@pytest.mark.asyncio
async def test_model_center_routes_require_authentication():
    def reject_anonymous():
        raise HTTPException(status_code=401, detail="authentication required")

    app.dependency_overrides[get_current_user_id] = reject_anonymous
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as anonymous:
        response = await anonymous.get("/api/v1/model-center/drivers")
    app.dependency_overrides.pop(get_current_user_id, None)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_collections_are_paginated_and_connection_secrets_are_redacted(client):
    paths = (
        "/api/v1/model-center/drivers",
        "/api/v1/model-center/connections",
        "/api/v1/model-center/catalog",
        "/api/v1/model-center/bindings",
        "/api/v1/model-center/recipes",
        "/api/v1/model-center/prompt-profiles",
    )
    responses = [await client.get(path, params={"page": 1, "page_size": 10}) for path in paths]
    assert [response.status_code for response in responses] == [200] * len(paths)
    for response in responses:
        assert set(response.json()) == {"items", "meta"}
        assert response.json()["meta"]["page"] == 1
        assert response.json()["meta"]["page_size"] == 10
        assert response.json()["meta"]["total"] >= len(response.json()["items"])

    connection = responses[1].json()["items"][0]
    assert connection["has_secret"] is True
    assert connection["secret_hint"].startswith("****")
    assert "api_key" not in connection
    assert "api_secret" not in connection
    assert "encrypted_secret" not in connection

    recipe = next(item for item in responses[4].json()["items"] if item["id"] == "recipe-v1")
    serialized = json.dumps(recipe["spec"], ensure_ascii=False)
    assert "runtime-secret" not in serialized
    assert "runtime-prompt" not in serialized
    assert "runtime-text" not in serialized
    assert "authorization" not in serialized.lower()
    assert recipe["spec"]["video"] == {"binding_id": "binding-video", "required": True}
    assert recipe["spec"]["audio"] == {"mode": "video_native_audio"}


@pytest.mark.asyncio
async def test_updates_require_expected_revision_and_transitions_require_reason(client):
    update_paths = (
        "/api/v1/model-center/providers/provider-1",
        "/api/v1/model-center/connections/connection-1",
        "/api/v1/model-center/profile-versions/profile-video-v1",
        "/api/v1/model-center/bindings/binding-video",
    )
    for path in update_paths:
        response = await client.put(path, json={})
        assert response.status_code == 422
        assert "expected_revision" in response.text

    response = await client.post(
        "/api/v1/model-center/recipe-versions/recipe-v1/publish",
        json={"expected_revision": 1},
    )
    assert response.status_code == 422
    assert "reason" in response.text

    metadata_only = await client.put(
        "/api/v1/model-center/connections/connection-1",
        json={"expected_revision": 1},
    )
    assert metadata_only.status_code == 501

    blank_reason = await client.put(
        "/api/v1/model-center/connections/connection-1",
        json={"expected_revision": 1, "api_key": "replacement", "reason": "   "},
    )
    assert blank_reason.status_code == 422
    assert "reason" in blank_reason.text


@pytest.mark.asyncio
async def test_audited_actions_reject_whitespace_reason_without_creating_audit(client):
    publish = await client.post(
        "/api/v1/model-center/recipe-versions/recipe-v1/publish",
        json={"expected_revision": 1, "reason": "   "},
    )
    rollback = await client.post(
        "/api/v1/model-center/recipes/anime/rollback",
        json={"expected_revision": 1, "target_version_id": "recipe-v1", "reason": "   "},
    )
    assert publish.status_code == rollback.status_code == 422
    assert "reason" in publish.text
    assert "reason" in rollback.text

    async with AsyncSessionLocal() as db:
        audit_count = await db.scalar(select(func.count()).select_from(ModelConfigAuditEvent))
    assert audit_count == 0


@pytest.mark.asyncio
async def test_connection_test_without_body_returns_actionable_not_implemented(client):
    response = await client.post("/api/v1/model-center/connections/connection-1/test")
    assert response.status_code == 501
    assert response.json()["detail"]["code"] == "operation_not_implemented"
    assert response.json()["detail"]["action_code"] == "contact_operator_or_use_legacy_api"


@pytest.mark.asyncio
async def test_concurrent_recipe_publish_has_one_winner_and_one_audit(client):
    responses = await asyncio.gather(
        client.post(
            "/api/v1/model-center/recipe-versions/recipe-race/publish",
            json={"expected_revision": 1, "reason": "并发发布 A"},
        ),
        client.post(
            "/api/v1/model-center/recipe-versions/recipe-race/publish",
            json={"expected_revision": 1, "reason": "并发发布 B"},
        ),
    )
    assert sorted(response.status_code for response in responses) == [200, 409]
    conflict = next(response for response in responses if response.status_code == 409)
    assert conflict.json()["detail"]["code"] == "revision_conflict"

    async with AsyncSessionLocal() as db:
        audits = await db.scalar(select(func.count()).select_from(ModelConfigAuditEvent).where(
            ModelConfigAuditEvent.resource_id == "recipe-race",
            ModelConfigAuditEvent.action == "publish",
        ))
    assert audits == 1


@pytest.mark.asyncio
async def test_recipe_publish_returns_audit_and_impact_envelope(client):
    response = await client.post(
        "/api/v1/model-center/recipe-versions/recipe-v1/publish",
        json={"expected_revision": 1, "reason": "配置复核通过"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["published_version_id"] == "recipe-v1"
    assert payload["impact"]["affected_bindings"] == 3
    assert payload["audit_event_id"]

    async with AsyncSessionLocal() as db:
        audit = await db.get(ModelConfigAuditEvent, payload["audit_event_id"])
        recipe = await db.get(ProductionRecipeVersion, "recipe-v1")
        assert audit.reason == "配置复核通过"
        assert recipe.status == "published"
        assert recipe.revision == 2

    repeated = await client.post(
        "/api/v1/model-center/recipe-versions/recipe-v1/publish",
        json={"expected_revision": 2, "reason": "重复发布"},
    )
    assert repeated.status_code == 409
    assert repeated.json()["detail"]["code"] == "resource_state_conflict"
    assert repeated.json()["detail"]["action_code"] == "create_or_select_draft"


@pytest.mark.asyncio
async def test_missing_service_operation_returns_stable_actionable_error(client):
    response = await client.post(
        "/api/v1/model-center/providers",
        json={"code": "new-provider", "display_name": "New", "provider_family": "openai"},
    )
    assert response.status_code == 501
    detail = response.json()["detail"]
    assert detail["code"] == "operation_not_implemented"
    assert detail["action_code"] == "contact_operator_or_use_legacy_api"
    assert "provider.create" in detail["message"]


def test_feature_api_does_not_import_legacy_endpoint_modules():
    api_root = Path(__file__).parents[1] / "app/features/model_config/api"
    violations = []
    for path in api_root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            module = getattr(node, "module", "") or ""
            if module.startswith("app.api.v1.endpoints"):
                violations.append(f"{path.name}:{node.lineno}:{module}")
    assert violations == []


def test_api_service_contains_no_orm_or_sqlalchemy_ownership():
    path = Path(__file__).parents[1] / "app/features/model_config/api/service.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = [getattr(node, "module", "") or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert not any(module.startswith("sqlalchemy") or module.startswith("app.models") for module in imports)


async def _seed_collection_rows(db: AsyncSession) -> None:
    provider = ModelProvider(
        id="provider-1", code="provider-1", display_name="Provider", provider_family="test"
    )
    connection = ModelConnection(
        id="connection-1", user_id=USER_ID, provider_id=provider.id, name="Primary",
        status="connection_verified",
    )
    connection.set_api_key_encrypted("secret-value")
    db.add_all([provider, connection])
    for stage, capability in (
        ("video", "video_generation"),
        ("render", "media_render"),
        ("storage", "object_storage"),
    ):
        _seed_binding(db, stage, capability)
    spec = _recipe_spec()
    db.add_all([
        ProductionRecipeVersion(
            id="recipe-v1", user_id=USER_ID, recipe_key="anime", name="Anime",
            version=1, status="draft", spec=spec, checksum=stable_recipe_checksum(spec), revision=1,
        ),
        ProductionRecipeVersion(
            id="recipe-race", user_id=USER_ID, recipe_key="race", name="Race",
            version=1, status="draft", spec=spec, checksum=stable_recipe_checksum(spec), revision=1,
        ),
        PromptProfile(id="prompt-1", user_id=USER_ID, key="script", name="Script", task="script_generation"),
        PromptProfileVersion(
            id="prompt-v1", profile_id="prompt-1", version=1, content="Write {{topic}}",
            variables={"topic": "story"}, routing={}, evaluation={}, status="draft", checksum="p" * 64,
        ),
    ])
    await db.commit()


def _seed_binding(db: AsyncSession, stage: str, capability: str) -> None:
    model_id = f"model-{stage}"
    version_id = f"profile-{stage}-v1"
    connection_id = "connection-1"
    db.add_all([
        ModelProfile(
            id=model_id, provider_id="provider-1", profile_key=stage,
            display_name=stage.title(), enabled=True,
        ),
        ModelProfileVersion(
            id=version_id, model_id=model_id, version=1, api_model_id=f"api-{stage}",
            driver_key=f"driver-{stage}", capabilities=[capability, "native_audio"] if stage == "video" else [capability],
            input_contract={}, output_contract={}, parameter_schema={}, default_params={}, limits={}, pricing={},
            contract_version="v1", status="published", checksum=stage[0] * 64,
        ),
        ModelBinding(
            id=f"binding-{stage}", user_id=USER_ID, scope_type="user", scope_id=USER_ID,
            task={"video": "shot_video", "render": "workflow_render", "storage": "workflow_storage"}[stage],
            capability=capability, profile_version_id=version_id, connection_id=connection_id,
            version=1, is_active=True,
        ),
    ])


def _recipe_spec() -> dict:
    return {
        "text": {"required": False}, "vision": {"required": False}, "image": {"required": False},
        "video": {
            "binding_id": "binding-video", "required": True,
            "params": {
                "api_key": "runtime-secret", "authorization": "Bearer runtime-secret",
                "nested": {"prompt": "runtime-prompt", "text": "runtime-text"},
            },
        },
        "audio": {"mode": "video_native_audio"},
        "subtitle": {"source": "video_dialogue_timeline"},
        "render": {"binding_id": "binding-render", "required": True},
        "storage": {"binding_id": "binding-storage", "required": True},
    }
