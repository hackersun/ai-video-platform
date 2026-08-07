from __future__ import annotations

import json

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.core.database import get_db
from app.core.security import get_current_user_id
from app.features.model_config.domain import ModelProfileContract, ResolvedModelBinding
from app.features.model_config.api import prompt_usage as prompt_usage_api
from app.features.model_config import prompt_usage
from app.features.model_config.prompt_usage_repository import PromptUsageModelIdentity
from app.features.prompt_profiles.versioning import canonical_prompt_version_checksum
from app.models.prompt_profile import PromptProfile, PromptProfileVersion


USER_ID = "prompt-map-user"


@pytest_asyncio.fixture()
async def prompt_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


def _prompt_version(profile_id: str, version_id: str, *, status: str = "published"):
    row = PromptProfileVersion(
        id=version_id,
        profile_id=profile_id,
        version=1,
        stage=None,
        content="保持角色外观一致并生成镜头。",
        variables={"style": "3D修仙"},
        routing={},
        output_contract=None,
        evaluation={"quality_gate": "commercial"},
        status=status,
        checksum="pending",
    )
    row.checksum = canonical_prompt_version_checksum(row)
    return row


def _binding(task: str, capability: str, profile_version_id: str = "model-version-1"):
    return ResolvedModelBinding(
        task=task,
        capability=capability,
        profile=ModelProfileContract(
            profile_version_id=profile_version_id,
            provider_id="provider-1",
            api_model_id=f"{task}-model",
            driver_key="test-driver",
            capabilities=frozenset({capability}),
            input_contract={},
            output_contract={},
            parameter_schema={},
            default_params={},
            limits={},
            pricing={},
            prompt_profile_key=None,
            contract_version="v1",
        ),
        connection_id="connection-1",
        binding_version=1,
        source_scope="system",
    )


@pytest.fixture()
def routed_dependencies(monkeypatch):
    model_calls: list[tuple[str, str, str | None]] = []

    async def resolve_binding(_db, *, task, capability, explicit_profile_version_id=None, **_):
        model_calls.append((task, capability, explicit_profile_version_id))
        return _binding(task, capability, explicit_profile_version_id or "model-version-1")

    async def load_identity(_db, binding):
        return PromptUsageModelIdentity(
            profile_version_id=binding.profile.profile_version_id,
            provider_code="volcengine",
            provider_name="火山方舟",
            api_model_id=binding.profile.api_model_id,
            model_name="测试模型",
            capabilities=tuple(sorted(binding.profile.capabilities)),
            prompt_profile_key=None,
        )

    async def select_prompt(_db, *, task, **_):
        if task == "entity_extraction":
            return {
                "used_prompt_skill": False,
                "prompt_skill_id": None,
                "prompt_skill_name": None,
                "prompt_skill_version": None,
                "prompt_profile_version_id": None,
                "routing_reason": "no_active_template",
                "fallback_reason": "internal_prompt_fallback",
            }
        return {
            "used_prompt_skill": True,
            "prompt_skill_id": f"profile-{task}",
            "prompt_skill_name": "标准分镜创建" if task == "storyboard_generation" else "标准模板",
            "prompt_skill_version": 3,
            "prompt_profile_version_id": f"version-{task}",
            "routing_reason": "exact_model_match" if task == "storyboard_generation" else "task_generic_match",
            "fallback_reason": None,
        }

    monkeypatch.setattr(prompt_usage, "resolve_model_binding", resolve_binding)
    monkeypatch.setattr(prompt_usage, "load_prompt_usage_model_identity", load_identity)
    monkeypatch.setattr(prompt_usage, "select_prompt_skill_for_model", select_prompt)
    return model_calls


@pytest.mark.asyncio
async def test_usage_map_reports_canonical_template_fallback_and_non_prompt_stages(
    routed_dependencies,
):
    body = await prompt_usage.get_prompt_usage_map(object(), user_id=USER_ID)
    stages = {item["id"]: item for group in body["groups"] for item in group["stages"]}

    assert stages["storyboard_generation"]["template"]["name"] == "标准分镜创建"
    assert stages["storyboard_generation"]["routing"]["source_label"] == "模型专用覆盖"
    assert stages["character_extraction"]["status"] == "internal_fallback"
    assert stages["character_extraction"]["message"] == "尚未配置模板，将使用代码内置提示词。"
    assert stages["subtitle"]["status"] == "not_applicable"
    assert stages["synthesis"]["message"] == "此环节不使用提示词模板。"
    assert "api_key" not in json.dumps(body)

    unique_model_calls = {(task, capability) for task, capability, _ in routed_dependencies}
    assert unique_model_calls == {
        ("script_generation", "text_generation"),
        ("entity_extraction", "text_generation"),
        ("shot_image", "image_generation"),
        ("shot_video", "video_generation"),
        ("shot_speech", "speech_generation"),
    }
    assert len(routed_dependencies) == 5


@pytest.mark.asyncio
async def test_stage_preview_uses_requested_model_without_changing_the_default_binding(
    routed_dependencies,
):
    result = await prompt_usage.resolve_prompt_usage_stage(
        object(),
        user_id=USER_ID,
        stage_id="shot_video",
        profile_version_id="profile-video-v2",
    )

    assert result["model"]["profile_version_id"] == "profile-video-v2"
    assert routed_dependencies == [
        ("shot_video", "video_generation", "profile-video-v2")
    ]


@pytest.mark.asyncio
async def test_prompt_usage_http_route_returns_the_application_contract(
    monkeypatch, routed_dependencies,
):
    async def override_db():
        yield object()

    app = FastAPI()
    app.include_router(prompt_usage_api.router, prefix="/model-center")
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_id] = lambda: USER_ID
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/model-center/prompt-usage-map")

    assert response.status_code == 200
    assert response.json()["summary"]["total"] == 12


@pytest.mark.asyncio
async def test_unknown_prompt_usage_stage_returns_a_chinese_404(monkeypatch):
    async def override_db():
        yield object()

    app = FastAPI()
    app.include_router(prompt_usage_api.router, prefix="/model-center")
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_id] = lambda: USER_ID
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/model-center/prompt-usage-map/stages/missing/resolve")

    assert response.status_code == 404
    assert response.json()["detail"] == "未找到这个生产环节。"


@pytest.mark.asyncio
async def test_candidates_only_include_published_templates_for_the_same_prompt_task(prompt_db):
    prompt_db.add_all([
        PromptProfile(id="video-profile", user_id=USER_ID, key="video", name="镜头模板", task="shot_video"),
        _prompt_version("video-profile", "video-published"),
        PromptProfile(id="script-profile", user_id=USER_ID, key="script", name="剧本模板", task="script_generation"),
        _prompt_version("script-profile", "script-published"),
        PromptProfile(id="draft-profile", user_id=USER_ID, key="draft", name="未发布模板", task="shot_video"),
        _prompt_version("draft-profile", "video-draft", status="draft"),
    ])
    await prompt_db.commit()

    result = await prompt_usage.list_prompt_usage_candidates(
        prompt_db, user_id=USER_ID, stage_id="shot_video",
    )

    assert [(item["id"], item["task"], item["status"]) for item in result["items"]] == [
        ("video-published", "shot_video", "published")
    ]


@pytest.mark.asyncio
async def test_assignment_creates_current_model_draft_without_mutating_the_source(
    prompt_db, monkeypatch, routed_dependencies,
):
    source = _prompt_version("video-profile", "video-published")
    prompt_db.add_all([
        PromptProfile(id="video-profile", user_id=USER_ID, key="video", name="镜头模板", task="shot_video"),
        source,
    ])
    await prompt_db.commit()

    result = await prompt_usage.create_prompt_usage_assignment_draft(
        prompt_db,
        user_id=USER_ID,
        stage_id="shot_video",
        prompt_version_id=source.id,
        reason="用于当前默认镜头视频模型",
    )

    assert result["status"] == "draft"
    assert result["routing"] == {
        "provider_filter": ["volcengine"],
        "model_filter": ["shot_video-model"],
    }
    created = await prompt_db.get(PromptProfileVersion, result["version_id"])
    assert created.profile_id != source.profile_id
    assert created.content == source.content
    assert created.variables == source.variables
    assert created.evaluation["quality_gate"] == "commercial"
    assert created.evaluation["release_notes"] == "用于当前默认镜头视频模型"
    assert source.status == "published"
    assert source.routing == {}


@pytest.mark.asyncio
async def test_assignment_rejects_a_template_from_another_prompt_task(
    prompt_db, routed_dependencies,
):
    prompt_db.add_all([
        PromptProfile(id="script-profile", user_id=USER_ID, key="script", name="剧本模板", task="script_generation"),
        _prompt_version("script-profile", "script-published"),
    ])
    await prompt_db.commit()

    with pytest.raises(prompt_usage.PromptUsageError) as error:
        await prompt_usage.create_prompt_usage_assignment_draft(
            prompt_db,
            user_id=USER_ID,
            stage_id="shot_video",
            prompt_version_id="script-published",
            reason="错误任务",
        )

    assert error.value.message == "所选模板不属于这个生产环节。"


@pytest.mark.asyncio
async def test_candidate_and_assignment_http_routes_are_operator_safe(
    prompt_db, routed_dependencies,
):
    prompt_db.add_all([
        PromptProfile(id="video-profile", user_id=USER_ID, key="video", name="镜头模板", task="shot_video"),
        _prompt_version("video-profile", "video-published"),
    ])
    await prompt_db.commit()

    async def override_db():
        yield prompt_db

    app = FastAPI()
    app.include_router(prompt_usage_api.router, prefix="/model-center")
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_id] = lambda: USER_ID
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        candidates = await client.get(
            "/model-center/prompt-usage-map/stages/shot_video/candidates"
        )
        assignment = await client.post(
            "/model-center/prompt-usage-map/stages/shot_video/assignment-drafts",
            json={
                "prompt_version_id": "video-published",
                "reason": "用于当前默认镜头视频模型",
            },
        )

    assert candidates.status_code == 200
    assert candidates.json()["items"][0]["name"] == "镜头模板"
    assert assignment.status_code == 200
    assert assignment.json()["status"] == "draft"
    assert "model_filter" in assignment.json()["routing"]
