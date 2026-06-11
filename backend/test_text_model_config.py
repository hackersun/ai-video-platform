"""
Tests for default text model resolution.
"""

from __future__ import annotations

import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.api_key_utils import (
    create_image_generation_service,
    create_text_generation_service,
    extract_chat_content,
    get_user_image_model_config,
    get_user_text_model_config,
    get_user_vision_model_config,
    sanitize_chat_response,
    strip_thinking_blocks,
)
from app.core.database import AsyncSessionLocal
from app.api.v1.endpoints.coding_plan import resolve_text_service
from app.services.ai_service_base import truncate_context
from app.models.llm_config import LLMConfig, LLMModel, LLMProvider
from app.api.v1.endpoints.llm_config import (
    test_minimax_api as _test_minimax_api,
    test_volcano_agent_plan_api as _test_volcano_agent_plan_api,
)
from init_db import init_db
from main import app


@pytest.fixture(scope="module", autouse=True)
def _init_database() -> None:
    init_db()


@pytest.mark.asyncio
async def test_llm_catalog_hides_preflight_test_provider_data() -> None:
    user_id = f"llm-catalog-user-{uuid4()}"
    provider_id = f"provider-{uuid4()}"
    model_id = f"model-{uuid4()}"
    config_id = f"config-{uuid4()}"

    async with AsyncSessionLocal() as db:
        db.add(
            LLMProvider(
                id=provider_id,
                name=f"preflight-provider-{uuid4()}",
                name_cn="预检供应商",
                base_url="https://example.invalid/preflight",
                is_active=True,
            )
        )
        db.add(
            LLMModel(
                id=model_id,
                provider_id=provider_id,
                model_id="preflight-video-model",
                model_name="Preflight Video Model",
                model_type="video",
                capabilities=["text_to_video", "image_to_video"],
                is_active=True,
            )
        )
        config = LLMConfig(
            id=config_id,
            user_id=user_id,
            model_id=model_id,
            name="预检视频模型配置",
            is_active=True,
            is_default=True,
            test_status="pending",
        )
        config.set_api_key_encrypted("sk-preflight")
        db.add(config)
        await db.commit()

    client = TestClient(app)
    headers = {"Authorization": f"Bearer {user_id}"}

    try:
        providers_response = client.get("/api/v1/llm/providers")
        assert providers_response.status_code == 200
        provider_names = {provider["name_cn"] for provider in providers_response.json()}
        provider_ids = {provider["id"] for provider in providers_response.json()}
        assert "预检供应商" not in provider_names
        assert provider_id not in provider_ids

        models_response = client.get("/api/v1/llm/models", headers=headers)
        assert models_response.status_code == 200
        assert all(model["provider_id"] != provider_id for model in models_response.json())
        assert all(model["model_id"] != "preflight-video-model" for model in models_response.json())

        configs_response = client.get("/api/v1/llm/configs", headers=headers)
        assert configs_response.status_code == 200
        assert all(config["id"] != config_id for config in configs_response.json())
    finally:
        async with AsyncSessionLocal() as db:
            for config in (await db.execute(select(LLMConfig).where(LLMConfig.user_id == user_id))).scalars().all():
                await db.delete(config)
            for model in (await db.execute(select(LLMModel).where(LLMModel.provider_id == provider_id))).scalars().all():
                await db.delete(model)
            provider = await db.get(LLMProvider, provider_id)
            if provider is not None:
                await db.delete(provider)
            await db.commit()


@pytest.mark.asyncio
async def test_default_minimax_chat_model_is_resolved_as_text_config() -> None:
    user_id = "text-default-minimax-user"

    async with AsyncSessionLocal() as db:
        provider = await db.get(LLMProvider, "minimax")
        if provider is None:
            provider = LLMProvider(
                id="minimax",
                name="minimax",
                name_cn="MiniMax",
                base_url="https://api.minimaxi.com/v1",
                is_active=True,
            )
            db.add(provider)

        model = await db.get(LLMModel, "minimax-m2-7")
        if model is None:
            model = LLMModel(
                id="minimax-m2-7",
                provider_id="minimax",
                model_id="MiniMax-M2.7",
                model_name="MiniMax-M2.7",
                model_type="chat",
                capabilities=["chat", "completion", "json_mode"],
                is_active=True,
            )
            db.add(model)

        existing = await db.execute(select(LLMConfig).where(LLMConfig.user_id == user_id))
        for config in existing.scalars().all():
            await db.delete(config)

        config = LLMConfig(
            id="text-default-minimax-config",
            user_id=user_id,
            model_id="minimax-m2-7",
            name="MiniMax default text",
            is_active=True,
            is_default=True,
        )
        config.set_api_key_encrypted("sk-test-minimax")
        db.add(config)
        await db.commit()

        api_key, provider_name, model_id, base_url = await get_user_text_model_config(db, user_id)

    assert api_key == "sk-test-minimax"
    assert provider_name == "minimax"
    assert model_id == "MiniMax-M2.7"
    assert base_url == "https://api.minimaxi.com/v1"


@pytest.mark.asyncio
async def test_default_minimax_m3_model_uses_model_specific_base_url() -> None:
    user_id = "text-default-minimax-m3-user"

    async with AsyncSessionLocal() as db:
        from app.api.v1.endpoints.llm_config import ensure_default_models, ensure_default_providers

        await ensure_default_providers(db)
        await ensure_default_models(db)

        existing = await db.execute(select(LLMConfig).where(LLMConfig.user_id == user_id))
        for config in existing.scalars().all():
            await db.delete(config)

        config = LLMConfig(
            id="text-default-minimax-m3-config",
            user_id=user_id,
            model_id="minimax-m3",
            name="MiniMax M3 default text",
            is_active=True,
            is_default=True,
        )
        config.set_api_key_encrypted("sk-test-minimax-m3")
        db.add(config)
        await db.commit()

        api_key, provider_name, model_id, base_url = await get_user_text_model_config(db, user_id)

    assert api_key == "sk-test-minimax-m3"
    assert provider_name == "minimax"
    assert model_id == "MiniMax-M3"
    assert base_url == "https://api.minimaxi.com/v1"


@pytest.mark.asyncio
async def test_stale_minimax_m3_model_base_url_uses_key_region_route() -> None:
    user_id = "text-stale-minimax-m3-base-url-user"

    async with AsyncSessionLocal() as db:
        provider = await db.get(LLMProvider, "minimax")
        if provider is None:
            provider = LLMProvider(
                id="minimax",
                name="minimax",
                name_cn="MiniMax",
                base_url="https://api.minimaxi.com/v1",
                is_active=True,
            )
            db.add(provider)

        model = await db.get(LLMModel, "stale-minimax-m3-route")
        if model is None:
            model = LLMModel(
                id="stale-minimax-m3-route",
                provider_id="minimax",
                model_id="MiniMax-M3",
                model_name="MiniMax-M3",
                model_type="chat",
                capabilities=["chat", "vision", "multimodal"],
                is_active=True,
                base_url="https://api.minimax.io/v1",
            )
            db.add(model)

        existing = await db.execute(select(LLMConfig).where(LLMConfig.user_id == user_id))
        for config in existing.scalars().all():
            await db.delete(config)

        config = LLMConfig(
            id="text-stale-minimax-m3-base-url-config",
            user_id=user_id,
            model_id="stale-minimax-m3-route",
            name="Stale MiniMax M3 default text",
            is_active=True,
            is_default=True,
        )
        config.set_api_key_encrypted("sk-cp-valid-minimax-m3")
        db.add(config)
        await db.commit()

        api_key, provider_name, model_id, base_url = await get_user_text_model_config(db, user_id)

    assert api_key == "sk-cp-valid-minimax-m3"
    assert provider_name == "minimax"
    assert model_id == "MiniMax-M3"
    assert base_url == "https://api.minimaxi.com/v1"


@pytest.mark.asyncio
async def test_unreadable_encrypted_api_key_requires_reconfiguration() -> None:
    user_id = "text-unreadable-key-user"

    async with AsyncSessionLocal() as db:
        provider = await db.get(LLMProvider, "minimax")
        if provider is None:
            provider = LLMProvider(
                id="minimax",
                name="minimax",
                name_cn="MiniMax",
                base_url="https://api.minimaxi.com/v1",
                is_active=True,
            )
            db.add(provider)

        model = await db.get(LLMModel, "minimax-m2-7")
        if model is None:
            model = LLMModel(
                id="minimax-m2-7",
                provider_id="minimax",
                model_id="MiniMax-M2.7",
                model_name="MiniMax-M2.7",
                model_type="chat",
                capabilities=["chat", "completion", "json_mode"],
                is_active=True,
            )
            db.add(model)

        existing = await db.execute(select(LLMConfig).where(LLMConfig.user_id == user_id))
        for config in existing.scalars().all():
            await db.delete(config)

        config = LLMConfig(
            id="text-unreadable-key-config",
            user_id=user_id,
            model_id="minimax-m2-7",
            name="旧加密配置",
            is_active=True,
            is_default=True,
            api_key="gAAAAABold-unreadable-fernet-token",
        )
        db.add(config)
        await db.commit()

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_user_text_model_config(db, user_id)

    assert exc_info.value.status_code == 400
    assert "重新保存" in exc_info.value.detail


@pytest.mark.asyncio
async def test_default_unreadable_text_config_falls_back_to_verified_available_config() -> None:
    user_id = "text-default-fallback-available-user"

    async with AsyncSessionLocal() as db:
        from app.api.v1.endpoints.llm_config import ensure_default_models, ensure_default_providers

        await ensure_default_providers(db)
        await ensure_default_models(db)

        existing = await db.execute(select(LLMConfig).where(LLMConfig.user_id == user_id))
        for config in existing.scalars().all():
            await db.delete(config)

        stale_default = LLMConfig(
            id="text-stale-default-m3-config",
            user_id=user_id,
            model_id="minimax-m3",
            name="旧 MiniMax-M3 默认",
            is_active=True,
            is_default=True,
            test_status="success",
            api_key="gAAAAABold-unreadable-fernet-token",
        )
        available_fallback = LLMConfig(
            id="text-available-fallback-m27-config",
            user_id=user_id,
            model_id="minimax-m2-7",
            name="可用 MiniMax-2.7",
            is_active=True,
            is_default=False,
            test_status="success",
        )
        available_fallback.set_api_key_encrypted("sk-cp-valid-fallback")
        db.add(stale_default)
        db.add(available_fallback)
        await db.commit()

        api_key, provider_name, model_id, base_url = await get_user_text_model_config(db, user_id)

    assert api_key == "sk-cp-valid-fallback"
    assert provider_name == "minimax"
    assert model_id == "MiniMax-M2.7"
    assert base_url == "https://api.minimaxi.com/v1"


def test_llm_config_list_marks_unreadable_success_config_as_failed() -> None:
    client = TestClient(app)
    user_id = "config-list-unreadable-key-user"
    headers = {"Authorization": f"Bearer {user_id}"}

    async def _setup() -> None:
        async with AsyncSessionLocal() as db:
            from app.api.v1.endpoints.llm_config import ensure_default_models, ensure_default_providers

            await ensure_default_providers(db)
            await ensure_default_models(db)
            existing = await db.execute(select(LLMConfig).where(LLMConfig.user_id == user_id))
            for config in existing.scalars().all():
                await db.delete(config)
            db.add(
                LLMConfig(
                    id="config-list-unreadable-key-config",
                    user_id=user_id,
                    model_id="minimax-m3",
                    name="旧成功配置",
                    is_active=True,
                    is_default=True,
                    test_status="success",
                    test_message="MiniMax API 连接成功！",
                    api_key="gAAAAABold-unreadable-fernet-token",
                )
            )
            await db.commit()

    import asyncio

    asyncio.run(_setup())

    response = client.get("/api/v1/llm/configs", headers=headers)

    assert response.status_code == 200
    config = response.json()[0]
    assert config["test_status"] == "failed"
    assert config["key_available"] is False
    assert "重新保存" in config["test_message"]


def test_llm_config_test_unreadable_key_returns_reconfigure_message() -> None:
    client = TestClient(app)
    user_id = "config-test-unreadable-key-user"
    headers = {"Authorization": f"Bearer {user_id}"}

    async def _setup() -> None:
        async with AsyncSessionLocal() as db:
            from app.api.v1.endpoints.llm_config import ensure_default_models, ensure_default_providers

            await ensure_default_providers(db)
            await ensure_default_models(db)
            existing = await db.execute(select(LLMConfig).where(LLMConfig.user_id == user_id))
            for config in existing.scalars().all():
                await db.delete(config)
            db.add(
                LLMConfig(
                    id="config-test-unreadable-key-config",
                    user_id=user_id,
                    model_id="minimax-m3",
                    name="旧测试配置",
                    is_active=True,
                    is_default=True,
                    test_status="success",
                    api_key="gAAAAABold-unreadable-fernet-token",
                )
            )
            await db.commit()

    import asyncio

    asyncio.run(_setup())

    response = client.post(
        "/api/v1/llm/configs/config-test-unreadable-key-config/test",
        json={"message": "你好"},
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "重新保存" in data["message"]


def test_minimax_text_service_factory_exposes_safe_generation_helpers() -> None:
    service = create_text_generation_service("sk-test-minimax", "minimax", None)

    assert hasattr(service, "chat_completion")
    assert hasattr(service, "safe_chat_completion")
    assert hasattr(service, "generate_novel_with_plan")
    assert hasattr(service, "calculate_request_cost")


def test_llm_model_catalog_backfills_seedance_20_models() -> None:
    client = TestClient(app)
    headers = {"Authorization": "Bearer model-catalog-user"}

    response = client.get("/api/v1/llm/models?provider=volcano", headers=headers)

    assert response.status_code == 200
    models = {item["model_id"]: item for item in response.json()}
    assert models["doubao-seedance-2-0-260128"]["model_type"] in {"video", "video-generation"}
    assert models["doubao-seedance-2-0-fast-260128"]["model_type"] in {"video", "video-generation"}
    assert models["Doubao-Seed-2.0-pro"]["model_type"] == "chat"


def test_llm_model_catalog_backfills_minimax_m3_model() -> None:
    client = TestClient(app)
    headers = {"Authorization": "Bearer minimax-m3-catalog-user"}

    response = client.get("/api/v1/llm/models?provider=minimax", headers=headers)

    assert response.status_code == 200
    models = {item["model_id"]: item for item in response.json()}
    assert "MiniMax-M3" in models
    assert models["MiniMax-M3"]["model_type"] == "chat"
    assert models["MiniMax-M3"]["context_window"] == 1000000
    assert models["MiniMax-M3"]["is_recommended"] is True
    assert "vision" in models["MiniMax-M3"]["capabilities"]


def test_llm_model_catalog_backfills_volcano_agent_plan_models() -> None:
    client = TestClient(app)
    headers = {"Authorization": "Bearer agent-plan-catalog-user"}

    providers_resp = client.get("/api/v1/llm/providers")
    assert providers_resp.status_code == 200
    providers = {item["id"]: item for item in providers_resp.json()}
    assert providers["volcano_agent_plan"]["base_url"].endswith("/api/plan/v3")

    models_resp = client.get("/api/v1/llm/models?provider=volcano_agent_plan", headers=headers)
    assert models_resp.status_code == 200
    models = {item["model_id"]: item for item in models_resp.json()}

    assert models["ark-code-latest"]["model_type"] == "chat"
    assert models["doubao-seed-2.0-pro"]["model_type"] == "chat"
    assert models["doubao-seedream-5.0-lite"]["model_type"] == "image-generation"
    assert models["doubao-seedance-2.0"]["model_type"] == "video-generation"
    assert models["doubao-seedance-2.0-fast"]["model_type"] == "video-generation"
    assert models["doubao-embedding-vision"]["model_type"] == "embedding"


def test_llm_model_catalog_marks_current_user_config_status() -> None:
    client = TestClient(app)
    user_id = "model-status-owner"
    other_user_id = "model-status-other"
    headers = {"Authorization": f"Bearer {user_id}"}
    other_headers = {"Authorization": f"Bearer {other_user_id}"}

    async def _cleanup() -> None:
        async with AsyncSessionLocal() as db:
            existing = await db.execute(
                select(LLMConfig).where(LLMConfig.user_id.in_([user_id, other_user_id]))
            )
            for config in existing.scalars().all():
                await db.delete(config)
            await db.commit()

    import asyncio

    asyncio.run(_cleanup())

    create_resp = client.post(
        "/api/v1/llm/configs",
        json={"model_id": "minimax-m2-7", "name": "我的文本模型", "api_key": "sk-text", "is_default": True},
        headers=headers,
    )
    assert create_resp.status_code == 201
    config_id = create_resp.json()["id"]

    async def _mark_verified() -> None:
        async with AsyncSessionLocal() as db:
            config = await db.get(LLMConfig, config_id)
            assert config is not None
            config.test_status = "success"
            config.test_message = "测试通过"
            await db.commit()

    asyncio.run(_mark_verified())

    owner_models_resp = client.get("/api/v1/llm/models?provider=minimax", headers=headers)
    assert owner_models_resp.status_code == 200
    owner_models = {item["id"]: item for item in owner_models_resp.json()}
    assert owner_models["minimax-m2-7"]["user_configured"] is True
    assert owner_models["minimax-m2-7"]["user_config_id"] == config_id
    assert owner_models["minimax-m2-7"]["user_is_default"] is True
    assert owner_models["minimax-m2-7"]["user_test_status"] == "success"

    other_models_resp = client.get("/api/v1/llm/models?provider=minimax", headers=other_headers)
    assert other_models_resp.status_code == 200
    other_models = {item["id"]: item for item in other_models_resp.json()}
    assert other_models["minimax-m2-7"]["user_configured"] is False
    assert other_models["minimax-m2-7"]["user_config_id"] is None


def test_llm_models_deduplicate_legacy_minimax_aliases_but_keep_configured_alias_visible() -> None:
    client = TestClient(app)
    user_id = "model-alias-dedupe-user"
    headers = {"Authorization": f"Bearer {user_id}"}

    async def _cleanup() -> None:
        async with AsyncSessionLocal() as db:
            existing = await db.execute(select(LLMConfig).where(LLMConfig.user_id == user_id))
            for config in existing.scalars().all():
                await db.delete(config)
            await db.commit()

    import asyncio

    asyncio.run(_cleanup())

    response = client.get("/api/v1/llm/models?provider=minimax", headers=headers)
    assert response.status_code == 200
    models = response.json()
    keys = [(item["provider_id"], item["model_id"], item["model_type"]) for item in models]
    assert len(keys) == len(set(keys))
    ids = {item["id"] for item in models}
    assert "minimax-m2-7" in ids
    assert "minimax-m2.7" not in ids

    create_resp = client.post(
        "/api/v1/llm/configs",
        json={"model_id": "minimax-speech-2.6-hd", "name": "历史语音配置", "api_key": "sk-audio"},
        headers=headers,
    )
    assert create_resp.status_code == 201

    configured_resp = client.get("/api/v1/llm/models?provider=minimax", headers=headers)
    assert configured_resp.status_code == 200
    configured_models = configured_resp.json()
    configured_ids = {item["id"] for item in configured_models}
    assert "minimax-speech-2.6-hd" in configured_ids
    assert "minimax-speech-2-6-hd" not in configured_ids
    speech_model = next(item for item in configured_models if item["id"] == "minimax-speech-2.6-hd")
    assert speech_model["user_configured"] is True
    assert speech_model["user_config_name"] == "历史语音配置"


def test_llm_create_config_updates_same_user_same_model_instead_of_duplicate() -> None:
    client = TestClient(app)
    user_id = "dedupe-config-user"
    headers = {"Authorization": f"Bearer {user_id}"}

    async def _cleanup() -> None:
        async with AsyncSessionLocal() as db:
            existing = await db.execute(select(LLMConfig).where(LLMConfig.user_id == user_id))
            for config in existing.scalars().all():
                await db.delete(config)
            await db.commit()

    import asyncio

    asyncio.run(_cleanup())

    first_resp = client.post(
        "/api/v1/llm/configs",
        json={"model_id": "minimax-m2-7", "name": "第一次配置", "api_key": "sk-old", "is_default": False},
        headers=headers,
    )
    assert first_resp.status_code == 201

    second_resp = client.post(
        "/api/v1/llm/configs",
        json={"model_id": "minimax-m2-7", "name": "更新后的配置", "api_key": "sk-new", "is_default": True},
        headers=headers,
    )
    assert second_resp.status_code == 201
    assert second_resp.json()["id"] == first_resp.json()["id"]
    assert second_resp.json()["name"] == "更新后的配置"
    assert second_resp.json()["is_default"] is True

    configs_resp = client.get("/api/v1/llm/configs", headers=headers)
    assert configs_resp.status_code == 200
    configs = [item for item in configs_resp.json() if item["config_model_id"] == "minimax-m2-7"]
    assert len(configs) == 1


def test_llm_update_config_can_preserve_existing_key_and_verified_status() -> None:
    client = TestClient(app)
    user_id = "llm-config-update-preserve-key-user"
    headers = {"Authorization": f"Bearer {user_id}"}

    async def _setup() -> None:
        async with AsyncSessionLocal() as db:
            from app.api.v1.endpoints.llm_config import ensure_default_models, ensure_default_providers

            await ensure_default_providers(db)
            await ensure_default_models(db)
            existing = await db.execute(select(LLMConfig).where(LLMConfig.user_id == user_id))
            for config in existing.scalars().all():
                await db.delete(config)
            config = LLMConfig(
                id="llm-config-update-preserve-key-config",
                user_id=user_id,
                model_id="minimax-m2-7",
                name="已验证配置",
                is_active=True,
                is_default=True,
                test_status="success",
                test_message="MiniMax API 连接成功！",
            )
            config.set_api_key_encrypted("sk-existing-key")
            db.add(config)
            await db.commit()

    import asyncio

    asyncio.run(_setup())

    response = client.put(
        "/api/v1/llm/configs/llm-config-update-preserve-key-config",
        json={
            "model_id": "minimax-m2-7",
            "name": "只改名称和参数",
            "temperature": 0.6,
            "top_p": 0.8,
            "max_tokens": 4096,
            "is_default": True,
        },
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "只改名称和参数"
    assert data["test_status"] == "success"
    assert data["test_message"] == "MiniMax API 连接成功！"
    assert data["key_available"] is True


def test_llm_defaults_are_scoped_by_model_capability() -> None:
    client = TestClient(app)
    user_id = "capability-default-user"
    headers = {"Authorization": f"Bearer {user_id}"}

    async def _cleanup() -> None:
        async with AsyncSessionLocal() as db:
            existing = await db.execute(select(LLMConfig).where(LLMConfig.user_id == user_id))
            for config in existing.scalars().all():
                await db.delete(config)
            await db.commit()

    import asyncio

    asyncio.run(_cleanup())

    text_resp = client.post(
        "/api/v1/llm/configs",
        json={
            "model_id": "minimax-m2-7",
            "name": "默认文本",
            "api_key": "sk-text",
            "is_default": True,
        },
        headers=headers,
    )
    assert text_resp.status_code == 201

    image_resp = client.post(
        "/api/v1/llm/configs",
        json={
            "model_id": "minimax-image-01",
            "name": "默认图像",
            "api_key": "sk-image",
            "is_default": True,
        },
        headers=headers,
    )
    assert image_resp.status_code == 201

    audio_resp = client.post(
        "/api/v1/llm/configs",
        json={
            "model_id": "minimax-speech-2.6-hd",
            "name": "默认语音",
            "api_key": "sk-audio",
            "is_default": True,
        },
        headers=headers,
    )
    assert audio_resp.status_code == 201

    configs_resp = client.get("/api/v1/llm/configs", headers=headers)
    assert configs_resp.status_code == 200
    defaults = {item["model_type"]: item for item in configs_resp.json() if item["is_default"]}

    assert defaults["chat"]["name"] == "默认文本"
    assert defaults["image-generation"]["name"] == "默认图像"
    assert defaults["tts"]["name"] == "默认语音"


def test_llm_set_default_only_replaces_same_capability() -> None:
    client = TestClient(app)
    user_id = "capability-switch-default-user"
    headers = {"Authorization": f"Bearer {user_id}"}

    async def _cleanup() -> None:
        async with AsyncSessionLocal() as db:
            existing = await db.execute(select(LLMConfig).where(LLMConfig.user_id == user_id))
            for config in existing.scalars().all():
                await db.delete(config)
            await db.commit()

    import asyncio

    asyncio.run(_cleanup())

    text_resp = client.post(
        "/api/v1/llm/configs",
        json={"model_id": "minimax-m2-7", "name": "文本默认", "api_key": "sk-text", "is_default": True},
        headers=headers,
    )
    assert text_resp.status_code == 201
    image_resp = client.post(
        "/api/v1/llm/configs",
        json={"model_id": "minimax-image-01", "name": "图像默认", "api_key": "sk-image", "is_default": True},
        headers=headers,
    )
    assert image_resp.status_code == 201
    second_text_resp = client.post(
        "/api/v1/llm/configs",
        json={"model_id": "qwen-turbo", "name": "文本候选", "api_key": "sk-text-2", "is_default": False},
        headers=headers,
    )
    assert second_text_resp.status_code == 201

    set_resp = client.post(f"/api/v1/llm/configs/{second_text_resp.json()['id']}/set-default", headers=headers)
    assert set_resp.status_code == 200

    configs_resp = client.get("/api/v1/llm/configs", headers=headers)
    assert configs_resp.status_code == 200
    default_names = {item["name"] for item in configs_resp.json() if item["is_default"]}
    assert default_names == {"文本候选", "图像默认"}


def test_llm_visual_default_does_not_replace_text_default() -> None:
    client = TestClient(app)
    user_id = "vision-default-scope-user"
    headers = {"Authorization": f"Bearer {user_id}"}

    async def _cleanup() -> None:
        async with AsyncSessionLocal() as db:
            from app.api.v1.endpoints.llm_config import ensure_default_models, ensure_default_providers

            await ensure_default_providers(db)
            await ensure_default_models(db)
            existing = await db.execute(select(LLMConfig).where(LLMConfig.user_id == user_id))
            for config in existing.scalars().all():
                await db.delete(config)
            await db.commit()

    import asyncio

    asyncio.run(_cleanup())

    text_resp = client.post(
        "/api/v1/llm/configs",
        json={"model_id": "minimax-m2-7", "name": "默认文本", "api_key": "sk-text", "is_default": True},
        headers=headers,
    )
    assert text_resp.status_code == 201

    vision_resp = client.post(
        "/api/v1/llm/configs",
        json={"model_id": "minimax-m3", "name": "默认视觉多模态", "api_key": "sk-vision", "is_default": True},
        headers=headers,
    )
    assert vision_resp.status_code == 201

    configs_resp = client.get("/api/v1/llm/configs", headers=headers)
    assert configs_resp.status_code == 200
    default_names = {item["name"] for item in configs_resp.json() if item["is_default"]}
    assert default_names == {"默认文本", "默认视觉多模态"}

    async def _assert_default_resolution() -> None:
        async with AsyncSessionLocal() as db:
            _, _, text_model_id, _ = await get_user_text_model_config(db, user_id)
            _, _, vision_model_id, _ = await get_user_vision_model_config(db, user_id)
            assert text_model_id == "MiniMax-M2.7"
            assert vision_model_id == "MiniMax-M3"

    asyncio.run(_assert_default_resolution())


@pytest.mark.asyncio
async def test_volcano_agent_plan_video_test_uses_readonly_task_list(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    class _FakeElapsed:
        @staticmethod
        def total_seconds() -> float:
            return 0.01

    class _FakeResponse:
        status_code = 200
        elapsed = _FakeElapsed()
        text = "{}"

        @staticmethod
        def json() -> dict:
            return {"data": []}

    class _FakeClient:
        def __init__(self, timeout: float):
            captured["timeout"] = timeout

        async def __aenter__(self) -> "_FakeClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, url: str, params: dict, headers: dict) -> _FakeResponse:
            captured["method"] = "GET"
            captured["url"] = url
            captured["params"] = params
            captured["headers"] = headers
            return _FakeResponse()

        async def post(self, url: str, json: dict, headers: dict) -> _FakeResponse:
            captured["method"] = "POST"
            return _FakeResponse()

    monkeypatch.setattr("app.api.v1.endpoints.llm_config.httpx.AsyncClient", _FakeClient)

    result = await _test_volcano_agent_plan_api("agent-key", "doubao-seedance-2.0-fast", "测试")

    assert result["success"] is True
    assert captured["method"] == "GET"
    assert captured["url"].endswith("/api/plan/v3/contents/generations/tasks")
    assert captured["params"] == {"page_num": 1, "page_size": 1}
    assert "未提交生成任务" in result["response"]


@pytest.mark.asyncio
async def test_volcano_agent_plan_image_test_does_not_generate_image(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    class _FakeElapsed:
        @staticmethod
        def total_seconds() -> float:
            return 0.01

    class _FakeResponse:
        status_code = 200
        elapsed = _FakeElapsed()
        text = "{}"

        @staticmethod
        def json() -> dict:
            return {"data": []}

    class _FakeClient:
        def __init__(self, timeout: float):
            captured["timeout"] = timeout

        async def __aenter__(self) -> "_FakeClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, url: str, params: dict, headers: dict) -> _FakeResponse:
            captured["method"] = "GET"
            captured["url"] = url
            captured["params"] = params
            captured["headers"] = headers
            return _FakeResponse()

        async def post(self, url: str, json: dict, headers: dict) -> _FakeResponse:
            captured["method"] = "POST"
            return _FakeResponse()

    monkeypatch.setattr("app.api.v1.endpoints.llm_config.httpx.AsyncClient", _FakeClient)

    result = await _test_volcano_agent_plan_api("agent-key", "doubao-seedream-5.0-lite", "测试")

    assert result["success"] is True
    assert captured["method"] == "GET"
    assert captured["url"].endswith("/api/plan/v3/contents/generations/tasks")
    assert "未提交图像生成任务" in result["response"]


@pytest.mark.asyncio
async def test_minimax_m3_test_uses_domestic_endpoint_for_cn_key(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    class _FakeElapsed:
        @staticmethod
        def total_seconds() -> float:
            return 0.01

    class _FakeResponse:
        status_code = 200
        elapsed = _FakeElapsed()
        text = "{}"

        @staticmethod
        def json() -> dict:
            return {"choices": [{"message": {"content": "ok"}}], "usage": {"total_tokens": 1}}

    class _FakeClient:
        def __init__(self, timeout: float):
            captured["timeout"] = timeout

        async def __aenter__(self) -> "_FakeClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url: str, json: dict, headers: dict) -> _FakeResponse:
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return _FakeResponse()

    monkeypatch.setattr("app.api.v1.endpoints.llm_config.httpx.AsyncClient", _FakeClient)

    result = await _test_minimax_api("sk-cp-valid-key", "MiniMax-M3", "你好")

    assert result["success"] is True
    assert captured["url"] == "https://api.minimaxi.com/v1/text/chatcompletion_v2"
    assert captured["json"]["model"] == "MiniMax-M3"


@pytest.mark.asyncio
async def test_default_minimax_image_model_is_resolved_as_image_config() -> None:
    user_id = "image-default-minimax-user"

    async with AsyncSessionLocal() as db:
        provider = await db.get(LLMProvider, "minimax")
        if provider is None:
            provider = LLMProvider(
                id="minimax",
                name="minimax",
                name_cn="MiniMax",
                base_url="https://api.minimaxi.com/v1",
                is_active=True,
            )
            db.add(provider)

        model = await db.get(LLMModel, "minimax-image-01")
        if model is None:
            model = LLMModel(
                id="minimax-image-01",
                provider_id="minimax",
                model_id="image-01",
                model_name="MiniMax-image-01",
                model_type="image-generation",
                capabilities=["text-to-image"],
                is_active=True,
            )
            db.add(model)

        existing = await db.execute(select(LLMConfig).where(LLMConfig.user_id == user_id))
        for config in existing.scalars().all():
            await db.delete(config)

        config = LLMConfig(
            id="image-default-minimax-config",
            user_id=user_id,
            model_id="minimax-image-01",
            name="MiniMax default image",
            is_active=True,
            is_default=True,
        )
        config.set_api_key_encrypted("sk-test-minimax-image")
        db.add(config)
        await db.commit()

        api_key, provider_name, model_id, base_url = await get_user_image_model_config(db, user_id)

    assert api_key == "sk-test-minimax-image"
    assert provider_name == "minimax"
    assert model_id == "image-01"
    assert base_url == "https://api.minimaxi.com/v1"


@pytest.mark.asyncio
async def test_minimax_m3_can_be_selected_as_default_visual_multimodal_config() -> None:
    user_id = "vision-default-minimax-m3-user"

    async with AsyncSessionLocal() as db:
        from app.api.v1.endpoints.llm_config import ensure_default_models, ensure_default_providers

        await ensure_default_providers(db)
        await ensure_default_models(db)

        existing = await db.execute(select(LLMConfig).where(LLMConfig.user_id == user_id))
        for config in existing.scalars().all():
            await db.delete(config)

        config = LLMConfig(
            id="vision-default-minimax-m3-config",
            user_id=user_id,
            model_id="minimax-m3",
            name="MiniMax M3 visual default",
            is_active=True,
            is_default=True,
        )
        config.set_api_key_encrypted("sk-test-minimax-m3-visual")
        db.add(config)
        await db.commit()

        api_key, provider_name, model_id, base_url = await get_user_vision_model_config(db, user_id)

        with pytest.raises(Exception):
            await get_user_image_model_config(db, user_id)

    assert api_key == "sk-test-minimax-m3-visual"
    assert provider_name == "minimax"
    assert model_id == "MiniMax-M3"
    assert base_url == "https://api.minimaxi.com/v1"


@pytest.mark.asyncio
async def test_selected_model_config_overrides_default_with_capability_validation() -> None:
    user_id = "selected-capability-config-user"

    async with AsyncSessionLocal() as db:
        provider = await db.get(LLMProvider, "minimax")
        if provider is None:
            provider = LLMProvider(
                id="minimax",
                name="minimax",
                name_cn="MiniMax",
                base_url="https://api.minimaxi.com/v1",
                is_active=True,
            )
            db.add(provider)

        chat_model = await db.get(LLMModel, "minimax-m2-7")
        if chat_model is None:
            chat_model = LLMModel(
                id="minimax-m2-7",
                provider_id="minimax",
                model_id="MiniMax-M2.7",
                model_name="MiniMax-M2.7",
                model_type="chat",
                capabilities=["chat", "completion"],
                is_active=True,
            )
            db.add(chat_model)

        image_model = await db.get(LLMModel, "minimax-image-01")
        if image_model is None:
            image_model = LLMModel(
                id="minimax-image-01",
                provider_id="minimax",
                model_id="image-01",
                model_name="MiniMax-image-01",
                model_type="image-generation",
                capabilities=["text-to-image"],
                is_active=True,
            )
            db.add(image_model)

        existing = await db.execute(select(LLMConfig).where(LLMConfig.user_id == user_id))
        for config in existing.scalars().all():
            await db.delete(config)

        default_text = LLMConfig(
            id="selected-default-text-config",
            user_id=user_id,
            model_id="minimax-m2-7",
            name="默认文本",
            is_active=True,
            is_default=True,
        )
        default_text.set_api_key_encrypted("sk-default-text")
        selected_text = LLMConfig(
            id="selected-explicit-text-config",
            user_id=user_id,
            model_id="minimax-m2-7",
            name="指定文本",
            is_active=True,
            is_default=False,
        )
        selected_text.set_api_key_encrypted("sk-selected-text")
        image_config = LLMConfig(
            id="selected-image-config",
            user_id=user_id,
            model_id="minimax-image-01",
            name="图像配置",
            is_active=True,
            is_default=True,
        )
        image_config.set_api_key_encrypted("sk-image")
        db.add_all([default_text, selected_text, image_config])
        await db.commit()

        api_key, provider_name, model_id, _ = await get_user_text_model_config(
            db,
            user_id,
            config_id="selected-explicit-text-config",
        )
        image_api_key, _, image_model_id, _ = await get_user_image_model_config(
            db,
            user_id,
            config_id="selected-image-config",
        )

        with pytest.raises(Exception):
            await get_user_text_model_config(db, user_id, config_id="selected-image-config")

    assert api_key == "sk-selected-text"
    assert provider_name == "minimax"
    assert model_id == "MiniMax-M2.7"
    assert image_api_key == "sk-image"
    assert image_model_id == "image-01"


def test_image_service_factory_supports_minimax() -> None:
    service = create_image_generation_service("sk-test-minimax", "minimax", None)

    assert hasattr(service, "generate_image")


@pytest.mark.asyncio
async def test_coding_plan_resolves_selected_text_model_config() -> None:
    user_id = "coding-plan-selected-config-user"

    async with AsyncSessionLocal() as db:
        provider = await db.get(LLMProvider, "minimax")
        if provider is None:
            provider = LLMProvider(
                id="minimax",
                name="minimax",
                name_cn="MiniMax",
                base_url="https://api.minimaxi.com/v1",
                is_active=True,
            )
            db.add(provider)

        model = await db.get(LLMModel, "minimax-m2-7")
        if model is None:
            model = LLMModel(
                id="minimax-m2-7",
                provider_id="minimax",
                model_id="MiniMax-M2.7",
                model_name="MiniMax-M2.7",
                model_type="chat",
                capabilities=["chat", "completion"],
                is_active=True,
            )
            db.add(model)

        existing = await db.execute(select(LLMConfig).where(LLMConfig.user_id == user_id))
        for config in existing.scalars().all():
            await db.delete(config)

        default_text = LLMConfig(
            id="coding-plan-default-text-config",
            user_id=user_id,
            model_id="qwen-turbo",
            name="默认文本",
            is_active=True,
            is_default=True,
        )
        default_text.set_api_key_encrypted("sk-default")
        selected_text = LLMConfig(
            id="coding-plan-selected-text-config",
            user_id=user_id,
            model_id="minimax-m2-7",
            name="指定文本",
            is_active=True,
            is_default=False,
        )
        selected_text.set_api_key_encrypted("sk-selected")
        db.add_all([default_text, selected_text])
        await db.commit()

        service, model_id = await resolve_text_service(
            None,
            None,
            "coding-plan-selected-text-config",
            db,
            user_id,
        )

    assert model_id == "MiniMax-M2.7"
    assert hasattr(service, "safe_chat_completion")


def test_truncate_context_preserves_system_message_order() -> None:
    messages = [
        {"role": "system", "content": "系统提示"},
        {"role": "user", "content": "用户输入"},
    ]

    result = truncate_context(messages, max_tokens=1000, preserve_system=True, system_prompt="系统提示")

    assert [item["role"] for item in result] == ["system", "user"]


def test_sanitize_chat_response_strips_thinking_blocks() -> None:
    assert strip_thinking_blocks("<think>分析过程</think>\n\n简介正文") == "简介正文"

    response = {"choices": [{"message": {"content": "<think>分析过程</think>\n简介正文"}}]}
    sanitized = sanitize_chat_response(response)

    assert sanitized["choices"][0]["message"]["content"] == "简介正文"


def test_extract_chat_content_accepts_provider_native_shapes() -> None:
    assert extract_chat_content({"reply": "<think>分析</think>\n章节正文"}) == "章节正文"
    assert (
        extract_chat_content(
            {"output": {"choices": [{"message": {"content": [{"type": "text", "text": "分镜正文"}]}}]}}
        )
        == "分镜正文"
    )

    sanitized = sanitize_chat_response({"reply": "角色提取结果"})
    assert sanitized["choices"][0]["message"]["content"] == "角色提取结果"


def test_generate_intro_uses_default_text_service_without_creating_novel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeTextService:
        async def safe_chat_completion(self, *args, **kwargs):
            return {"choices": [{"message": {"content": "少年在失落城邦醒来，发现自己掌握着改写命运的古老符印。"}}]}

    async def _fake_config(*args, **kwargs):
        return "sk-test", "minimax", "MiniMax-M2.7", "https://api.minimaxi.com/v1"

    def _fake_factory(api_key: str, provider_name: str, base_url: str | None):
        assert provider_name == "minimax"
        return _FakeTextService()

    monkeypatch.setattr("app.api.v1.endpoints.novels.get_user_text_model_config", _fake_config)
    monkeypatch.setattr("app.api.v1.endpoints.novels.create_text_generation_service", _fake_factory)

    client = TestClient(app)
    headers = {"Authorization": "Bearer intro-test-user"}
    before = client.get("/api/v1/novels", headers=headers)
    assert before.status_code == 200
    before_count = len(before.json())

    response = client.post(
        "/api/v1/novels/generate-intro",
        json={"title": "玄都旧梦", "genre": "仙侠", "style": "热血", "description": "少年成长"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["provider"] == "minimax"
    assert "失落城邦" in response.json()["intro"]

    after = client.get("/api/v1/novels", headers=headers)
    assert after.status_code == 200
    assert len(after.json()) == before_count


def test_generate_standalone_cover_returns_image_without_creating_novel() -> None:
    client = TestClient(app)
    headers = {"Authorization": "Bearer cover-test-user"}
    before = client.get("/api/v1/novels", headers=headers)
    assert before.status_code == 200
    before_count = len(before.json())

    response = client.post(
        "/api/v1/novels/generate-cover",
        json={"title": "玄都旧梦", "genre": "仙侠", "style": "anime", "description": "少年寻找身世真相"},
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["cover_url"].startswith(("/static/generated/images/", "/static/dev/"))
    assert payload["job_id"]
    assert payload["novel_id"] is None

    after = client.get("/api/v1/novels", headers=headers)
    assert after.status_code == 200
    assert len(after.json()) == before_count


def test_generate_cover_uses_default_image_model_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {}

    class _FakeImageService:
        async def generate_image(self, *args, **kwargs):
            calls.update(kwargs)
            return {"data": {"items": [{"url": "https://example.com/generated-cover.png"}]}, "task_id": "img-task"}

    async def _fake_config(*args, **kwargs):
        return "sk-test-image", "minimax", "image-01", "https://api.minimaxi.com/v1"

    def _fake_factory(api_key: str, provider_name: str, base_url: str | None):
        assert api_key == "sk-test-image"
        assert provider_name == "minimax"
        assert base_url == "https://api.minimaxi.com/v1"
        return _FakeImageService()

    monkeypatch.setattr("app.api.v1.endpoints.novels.get_user_image_model_config", _fake_config)
    monkeypatch.setattr("app.api.v1.endpoints.novels.create_image_generation_service", _fake_factory)

    client = TestClient(app)
    headers = {"Authorization": "Bearer cover-default-model-user"}
    before = client.get("/api/v1/novels", headers=headers)
    assert before.status_code == 200
    before_count = len(before.json())

    response = client.post(
        "/api/v1/novels/generate-cover",
        json={"title": "玄都旧梦", "genre": "仙侠", "style": "anime", "description": "少年寻找身世真相"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["cover_url"] == "https://example.com/generated-cover.png"
    assert calls["model"] == "image-01"
    assert calls["aspect_ratio"] == "3:4"
    assert "anime style" in calls["prompt"]

    after = client.get("/api/v1/novels", headers=headers)
    assert after.status_code == 200
    assert len(after.json()) == before_count


def test_create_novel_persists_generated_cover_url() -> None:
    client = TestClient(app)
    headers = {"Authorization": "Bearer cover-save-user"}
    cover_url = "https://example.com/generated-cover.png"

    response = client.post(
        "/api/v1/novels",
        json={"title": "带封面小说", "genre": "仙侠", "cover_url": cover_url},
        headers=headers,
    )

    assert response.status_code == 201
    assert response.json()["cover_url"] == cover_url
