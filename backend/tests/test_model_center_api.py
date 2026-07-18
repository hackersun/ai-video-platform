from __future__ import annotations

import ast
import asyncio
from copy import deepcopy
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
    ModelCertificationRun,
    ModelConfigAuditEvent,
    ModelConnection,
    ModelProfile,
    ModelProfileVersion,
    ModelProvider,
    ProductionRecipeVersion,
)
from app.models.prompt_profile import PromptProfile, PromptProfileVersion
from app.models.prompt_skill import PromptSkill
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
    ("get", "/api/v1/model-center/prompt-profiles/{profile_id}"),
    ("get", "/api/v1/model-center/prompt-profiles/{profile_id}/versions"),
    ("post", "/api/v1/model-center/prompt-profiles"),
    ("post", "/api/v1/model-center/prompt-profiles/{profile_id}/optimize"),
    ("post", "/api/v1/model-center/prompt-profiles/{profile_id}/preview"),
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
async def test_overview_returns_the_frontend_model_center_contract(client):
    response = await client.get("/api/v1/model-center/overview")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"blocking_issues", "connections", "recipes"}
    assert isinstance(body["blocking_issues"], list)
    assert body["connections"][0]["has_secret"] is True
    assert "api_key" not in body["connections"][0]
    assert {item["status"] for item in body["recipes"]} <= {"draft", "published", "disabled"}


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
async def test_prompt_profile_detail_returns_owned_body_and_history(client):
    response = await client.get("/api/v1/model-center/prompt-profiles/prompt-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "prompt-1"
    assert payload["head"]["task_template"] == "Write {{topic}}"
    assert payload["head"]["content"] == "Write {{topic}}"
    assert payload["versions"][0]["checksum"] == "p" * 64
    assert payload["versions"][0]["content"] == "Write {{topic}}"
    assert payload["legacy_skill"] == {
        "id": "prompt-skill-1",
        "is_active": True,
        "is_builtin": False,
    }


@pytest.mark.asyncio
async def test_prompt_profile_optimize_reuses_legacy_optimizer(
    client,
    monkeypatch,
):
    calls = []

    async def fake_optimize(db, user_id, data):
        calls.append((user_id, data))
        return {
            "task": data["task"],
            "source": "local_rules",
            "original_content": data["content"],
            "optimized_content": "Optimized {{topic}}",
            "suggestions": ["keep variables"],
            "warnings": [],
        }

    monkeypatch.setattr(
        "app.features.model_config.prompt_assistance.optimize_prompt_skill_content",
        fake_optimize,
        raising=False,
    )
    response = await client.post(
        "/api/v1/model-center/prompt-profiles/prompt-1/optimize",
        json={
            "version_id": "prompt-v1",
            "mode": "productionize",
            "model_config_id": None,
        },
    )

    assert response.status_code == 200
    assert response.json()["optimized_content"] == "Optimized {{topic}}"
    assert response.json()["source"] == "local_rules"
    assert calls[0][0] == USER_ID
    assert calls[0][1]["content"] == "Write {{topic}}"


@pytest.mark.asyncio
async def test_prompt_profile_preview_does_not_overwrite_saved_version(client):
    preview = await client.post(
        "/api/v1/model-center/prompt-profiles/prompt-1/preview",
        json={
            "version_id": "prompt-v1",
            "task_template": "Draft {topic}",
            "context": {"topic": "harbor"},
        },
    )
    detail = await client.get("/api/v1/model-center/prompt-profiles/prompt-1")

    assert preview.status_code == 200
    assert "Draft harbor" in preview.json()["prompt"]
    assert detail.json()["head"]["task_template"] == "Write {{topic}}"


@pytest.mark.asyncio
async def test_prompt_profile_body_is_not_visible_to_another_user(client):
    app.dependency_overrides[get_current_user_id] = lambda: "other-user"
    try:
        response = await client.get("/api/v1/model-center/prompt-profiles/prompt-1")
    finally:
        app.dependency_overrides[get_current_user_id] = lambda: USER_ID

    assert response.status_code == 404
    assert "Write {{topic}}" not in response.text


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
    assert metadata_only.status_code == 200
    assert metadata_only.json()["revision"] == 2

    blank_reason = await client.put(
        "/api/v1/model-center/connections/connection-1",
        json={"expected_revision": 1, "api_key": "replacement", "reason": "   "},
    )
    assert blank_reason.status_code == 422
    assert "reason" in blank_reason.text


@pytest.mark.asyncio
async def test_audited_actions_reject_whitespace_reason_without_creating_audit(client):
    async with AsyncSessionLocal() as db:
        before_count = await db.scalar(select(func.count()).select_from(ModelConfigAuditEvent))
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
    assert audit_count == before_count


@pytest.mark.asyncio
async def test_connection_test_for_missing_connection_returns_actionable_not_found(client):
    response = await client.post("/api/v1/model-center/connections/missing-connection/test")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "resource_not_found"
    assert response.json()["detail"]["action_code"] == "refresh"


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


@pytest.mark.asyncio
async def test_recipe_management_creates_validates_publishes_and_rolls_back_versions(client):
    spec = _recipe_spec()
    created = await client.post(
        "/api/v1/model-center/recipes",
        json={"recipe_key": "task16-anime", "name": "Task 16 Anime", "spec": spec},
    )
    assert created.status_code == 200
    first = created.json()
    assert first["recipe_key"] == "task16-anime"
    assert first["version"] == 1
    assert first["status"] == "draft"

    validated = await client.post(
        f"/api/v1/model-center/recipe-versions/{first['id']}/validate",
    )
    assert validated.status_code == 200
    assert validated.json() == {"valid": True, "errors": []}

    published = await client.post(
        f"/api/v1/model-center/recipe-versions/{first['id']}/publish",
        json={"expected_revision": 1, "reason": "首版验收通过"},
    )
    assert published.status_code == 200

    second = await client.post(
        "/api/v1/model-center/recipes",
        json={"recipe_key": "task16-anime", "name": "Task 16 Anime v2", "spec": spec},
    )
    assert second.status_code == 200
    second_id = second.json()["id"]
    assert second.json()["version"] == 2
    assert (await client.post(
        f"/api/v1/model-center/recipe-versions/{second_id}/publish",
        json={"expected_revision": 1, "reason": "二版验收通过"},
    )).status_code == 200

    rollback = await client.post(
        "/api/v1/model-center/recipes/task16-anime/rollback",
        json={"expected_revision": 2, "target_version_id": first["id"], "reason": "回退到已验收首版"},
    )
    assert rollback.status_code == 200
    payload = rollback.json()
    assert payload["previous_version_id"] == second_id
    assert payload["published_version_id"] not in {first["id"], second_id}
    assert payload["audit_event_id"]


@pytest.mark.asyncio
async def test_prompt_profiles_use_structured_immutable_versions_and_return_impact_preview(client):
    created = await client.post(
        "/api/v1/model-center/prompt-profiles",
        json={
            "key": "task16.video", "name": "Task 16 Video", "task": "shot_video",
            "stage": "video", "system_contract": "Return a safe storyboard plan.",
            "task_template": "Create {{shot}}.", "input_mapping": {"shot": "shot.description"},
            "output_schema": {"type": "object"}, "negative_constraints": ["no watermark"],
            "model_family_overrides": {"ark": {"tone": "cinematic"}},
            "validation_fixtures": [{"input": {"shot": "rain"}, "expected": "object"}],
            "release_notes": "initial draft",
        },
    )
    assert created.status_code == 200
    profile = created.json()
    assert profile["key"] == "task16.video"
    assert profile["version"] == 1
    assert profile["status"] == "draft"
    assert "task_template" not in profile

    impact = await client.get(
        "/api/v1/model-center/impact",
        params={"resource_type": "prompt_profile", "resource_id": profile["id"]},
    )
    assert impact.status_code == 200
    assert set(impact.json()) >= {"affected_bindings", "affected_recipes", "affected_prompts"}

    published = await client.post(
        f"/api/v1/model-center/prompt-profile-versions/{profile['head_version_id']}/publish",
        json={"expected_revision": 1, "reason": "提示词样例校验通过"},
    )
    assert published.status_code == 200
    assert published.json()["published_version_id"] == profile["head_version_id"]

    draft = await client.post(
        f"/api/v1/model-center/prompt-profiles/{profile['id']}/versions",
        json={
            "expected_revision": 1,
            "values": {
                "task_template": "Create a revised {{shot}}.",
                "release_notes": "revised draft",
            },
        },
    )
    assert draft.status_code == 200
    assert draft.json()["version"] == 2
    assert draft.json()["id"] != profile["head_version_id"]

    rollback = await client.post(
        f"/api/v1/model-center/prompt-profiles/{profile['id']}/rollback",
        json={
            "expected_revision": 2, "target_version_id": profile["head_version_id"],
            "reason": "恢复已验收提示词",
        },
    )
    assert rollback.status_code == 200
    assert rollback.json()["published_version_id"] not in {
        profile["head_version_id"], draft.json()["id"],
    }


@pytest.mark.asyncio
async def test_live_certification_persists_safe_intent_without_provider_execution(client):
    rejected = await client.post(
        "/api/v1/model-center/certifications",
        json={
            "profile_version_id": "profile-video-v1", "connection_id": "connection-1",
            "level": "live", "reason": "验收视频和声音同步",
        },
    )
    assert rejected.status_code == 422
    assert "real_cost_acknowledged" in rejected.text

    response = await client.post(
        "/api/v1/model-center/certifications",
        json={
            "profile_version_id": "profile-video-v1", "connection_id": "connection-1",
            "level": "live", "reason": "验收视频和声音同步", "user_scope": "user",
            "recipe_version_id": "recipe-v1", "chapter_id": "chapter-4", "run_id": "run-4",
            "selected_shot_ids": ["shot-3", "shot-7"], "budget_ceiling_rmb": "10.00",
            "retry_policy": "never", "storage_policy": "qiniu_public", "real_cost_acknowledged": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["actual_cost_rmb"] == "0.0000"
    assert payload["sanitized_evidence"]["execution_mode"] == "safe_intent_only"
    assert payload["sanitized_evidence"]["selected_shot_ids"] == ["shot-3", "shot-7"]
    assert "api_key" not in json.dumps(payload)
    assert "prompt" not in json.dumps(payload).lower()

    loaded = await client.get(f"/api/v1/model-center/certifications/{payload['id']}")
    assert loaded.status_code == 200
    assert loaded.json()["id"] == payload["id"]
    async with AsyncSessionLocal() as db:
        run = await db.get(ModelCertificationRun, payload["id"])
        assert run.status == "queued"
        assert run.actual_cost_rmb == 0


@pytest.mark.asyncio
async def test_legacy_plaintext_prompt_skill_creates_structured_draft_without_echoing_content(client):
    response = await client.post(
        "/api/v1/model-center/prompt-profiles/prompt-1/versions",
        json={"expected_revision": 1, "values": {"release_notes": "migrate legacy skill"}},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == 2
    assert "Write {{topic}}" not in response.text
    async with AsyncSessionLocal() as db:
        draft = await db.get(PromptProfileVersion, payload["head_version_id"])
    stored = json.loads(draft.content)
    assert stored["system_contract"] == "Legacy PromptSkill compatibility profile."
    assert stored["task_template"] == "Write {{topic}}"


@pytest.mark.asyncio
async def test_prompt_publish_is_atomic_and_creates_one_audit_event(client):
    created = await client.post(
        "/api/v1/model-center/prompt-profiles",
        json={
            "key": "task16.race", "name": "Prompt Race", "task": "shot_video",
            "system_contract": "Return structured output.", "task_template": "Create {{shot}}.",
        },
    )
    assert created.status_code == 200
    version_id = created.json()["head_version_id"]

    responses = await asyncio.gather(
        client.post(
            f"/api/v1/model-center/prompt-profile-versions/{version_id}/publish",
            json={"expected_revision": 1, "reason": "并发发布 A"},
        ),
        client.post(
            f"/api/v1/model-center/prompt-profile-versions/{version_id}/publish",
            json={"expected_revision": 1, "reason": "并发发布 B"},
        ),
    )
    assert sorted(item.status_code for item in responses) == [200, 409]
    assert next(item for item in responses if item.status_code == 409).json()["detail"]["code"] == "revision_conflict"
    async with AsyncSessionLocal() as db:
        audit_count = await db.scalar(select(func.count()).select_from(ModelConfigAuditEvent).where(
            ModelConfigAuditEvent.resource_type == "prompt_profile",
            ModelConfigAuditEvent.resource_id == created.json()["id"],
            ModelConfigAuditEvent.action == "publish",
        ))
    assert audit_count == 1


@pytest.mark.asyncio
async def test_connection_mutations_redact_secrets_and_queue_safe_test_intent(client):
    created = await client.post(
        "/api/v1/model-center/connections",
        json={
            "provider_id": "provider-1", "name": "Task 16 Connection", "api_key": "new-secret-key",
            "reason": "保存新连接",
        },
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["status"] == "draft"
    assert payload["has_secret"] is True
    assert payload["revision"] == 1
    assert "new-secret-key" not in created.text

    replacement = await client.put(
        f"/api/v1/model-center/connections/{payload['id']}",
        json={"expected_revision": 1, "api_key": "replacement-secret", "reason": "轮换凭证"},
    )
    assert replacement.status_code == 200
    assert replacement.json()["revision"] == 2
    assert "replacement-secret" not in replacement.text

    unsafe_metadata = await client.put(
        f"/api/v1/model-center/connections/{payload['id']}",
        json={"expected_revision": 2, "changes": {"connection_params": {"x-api-key": "plain-secret"}}},
    )
    assert unsafe_metadata.status_code == 422
    assert "plain-secret" not in unsafe_metadata.text

    metadata = await client.put(
        f"/api/v1/model-center/connections/{payload['id']}",
        json={"expected_revision": 2, "changes": {"name": "Task 16 Connection Updated"}},
    )
    assert metadata.status_code == 200
    assert metadata.json()["revision"] == 3

    tested = await client.post(f"/api/v1/model-center/connections/{payload['id']}/test")
    assert tested.status_code == 200
    assert tested.json()["status"] == "connection_verification_queued"
    assert tested.json()["execution_mode"] == "safe_intent_only"
    assert tested.json()["connection"]["revision"] == 4
    assert "api_key" not in json.dumps(tested.json())


@pytest.mark.asyncio
async def test_recipe_binding_resolution_exposes_safe_effective_model_and_prompt_metadata(client):
    response = await client.get("/api/v1/model-center/recipes/recipe-v1/binding-resolution")
    assert response.status_code == 200
    payload = response.json()
    video = next(item for item in payload["stages"] if item["stage"] == "video")
    assert video["binding_id"] == "binding-video"
    assert video["resolution_status"] == "resolved"
    assert video["profile"] == {
        "id": "profile-video-v1", "api_model_id": "api-video", "version": 1,
        "driver_key": "driver-video", "contract_version": "v1",
    }
    assert video["prompt_profile"] == {
        "id": "prompt-v1", "key": "script", "version": 1,
    }
    assert video["latest_certification"]["status"] in {"none", "queued"}
    serialized = json.dumps(payload)
    assert "secret-value" not in serialized
    assert "Write {{topic}}" not in serialized


@pytest.mark.asyncio
async def test_recipe_binding_resolution_marks_untrusted_system_binding_unavailable(client):
    async with AsyncSessionLocal() as db:
        bad_binding = ModelBinding(
            id="binding-untrusted-system", user_id="other-user", scope_type="system", scope_id="wrong-scope",
            task="shot_video", capability="video_generation", profile_version_id="profile-video-v1",
            connection_id="connection-1", version=1, is_active=True,
        )
        spec = deepcopy(_recipe_spec())
        spec["video"]["binding_id"] = bad_binding.id
        recipe = ProductionRecipeVersion(
            id="recipe-untrusted-system", user_id=USER_ID, recipe_key="untrusted-system", name="Unsafe",
            version=1, status="draft", spec=spec, checksum=stable_recipe_checksum(spec), revision=1,
        )
        db.add_all([bad_binding, recipe])
        await db.commit()

    response = await client.get("/api/v1/model-center/recipes/recipe-untrusted-system/binding-resolution")
    assert response.status_code == 200
    video = next(item for item in response.json()["stages"] if item["stage"] == "video")
    assert video == {
        "stage": "video", "binding_id": "binding-untrusted-system", "resolution_status": "unavailable",
        "error_code": "binding_scope_invalid", "profile": None, "prompt_profile": None,
        "latest_certification": {"level": "none", "status": "none"},
    }


@pytest.mark.asyncio
async def test_recipe_binding_resolution_marks_stage_mismatch_unavailable(client):
    async with AsyncSessionLocal() as db:
        bad_binding = ModelBinding(
            id="binding-stage-mismatch", user_id=USER_ID, scope_type="user", scope_id=USER_ID,
            task="shot_image", capability="image_generation", profile_version_id="profile-video-v1",
            connection_id="connection-1", version=1, is_active=True,
        )
        spec = deepcopy(_recipe_spec())
        spec["video"]["binding_id"] = bad_binding.id
        recipe = ProductionRecipeVersion(
            id="recipe-stage-mismatch", user_id=USER_ID, recipe_key="stage-mismatch", name="Unsafe",
            version=1, status="draft", spec=spec, checksum=stable_recipe_checksum(spec), revision=1,
        )
        db.add_all([bad_binding, recipe])
        await db.commit()

    response = await client.get("/api/v1/model-center/recipes/recipe-stage-mismatch/binding-resolution")
    assert response.status_code == 200
    video = next(item for item in response.json()["stages"] if item["stage"] == "video")
    assert video["resolution_status"] == "unavailable"
    assert video["error_code"] == "binding_task_mismatch"
    assert video["profile"] is None


@pytest.mark.asyncio
async def test_recipe_binding_resolution_marks_profile_capability_mismatch_unavailable(client):
    async with AsyncSessionLocal() as db:
        bad_binding = ModelBinding(
            id="binding-profile-capability-mismatch", user_id=USER_ID, scope_type="user", scope_id=USER_ID,
            task="shot_video", capability="video_generation", profile_version_id="profile-render-v1",
            connection_id="connection-1", version=2, is_active=True,
        )
        spec = deepcopy(_recipe_spec())
        spec["video"]["binding_id"] = bad_binding.id
        recipe = ProductionRecipeVersion(
            id="recipe-profile-capability-mismatch", user_id=USER_ID, recipe_key="profile-capability", name="Unsafe",
            version=1, status="draft", spec=spec, checksum=stable_recipe_checksum(spec), revision=1,
        )
        db.add_all([bad_binding, recipe])
        await db.commit()

    response = await client.get("/api/v1/model-center/recipes/recipe-profile-capability-mismatch/binding-resolution")
    assert response.status_code == 200
    video = next(item for item in response.json()["stages"] if item["stage"] == "video")
    assert video["resolution_status"] == "unavailable"
    assert video["error_code"] == "binding_capability_mismatch"
    assert video["profile"] is None


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
            variables={"topic": "story"}, routing={}, evaluation={}, status="published", checksum="p" * 64,
        ),
        PromptSkill(
            id="prompt-skill-1",
            user_id=USER_ID,
            name="Script",
            task="script_generation",
            content="Write {{topic}}",
            is_active=True,
            is_builtin=False,
            prompt_profile_version_id="prompt-v1",
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
            prompt_profile_key="script" if stage == "video" else None,
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
