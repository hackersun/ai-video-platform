from types import SimpleNamespace

import pytest

from app.features.model_drivers.domain import DriverTestResult


@pytest.mark.asyncio
async def test_minimax_image_config_test_uses_builtin_driver_and_keeps_legacy_shape(monkeypatch):
    from app.api.v1.endpoints import llm_config

    async def reject_legacy_tester(*_args, **_kwargs):
        raise AssertionError("endpoint-owned legacy tester must not run")

    async def fake_driver_test(_driver, _context):
        return DriverTestResult(
            "connection_verified", "MiniMax API 连接成功！", {"response": "生成图像成功"},
        )

    monkeypatch.setattr(llm_config, "test_minimax_api", reject_legacy_tester)
    monkeypatch.setattr(
        "app.features.model_drivers.adapters.minimax_image.MiniMaxImageDriver.test_connection",
        fake_driver_test,
    )

    result = await llm_config._execute_config_test(
        "minimax", "not-a-real-key", "image-01", "测试",
        model_type="image-generation", driver_key="minimax_image_v1",
    )

    assert result == {
        "success": True,
        "message": "MiniMax API 连接成功！",
        "response": "生成图像成功",
        "response_time_ms": 0,
        "tokens_used": 0,
    }
    assert not hasattr(llm_config, "_CONFIG_TEST_FACTORIES")


@pytest.mark.asyncio
async def test_minimax_image_config_test_preserves_legacy_success_message(monkeypatch):
    from app.api.v1.endpoints import llm_config

    async def fake_generate_image(_service, _prompt, **_kwargs):
        return {"id": "image-task-1", "data": {"image_urls": ["https://cdn.example.com/image.png"]}}

    monkeypatch.setattr("app.services.minimax_service.MiniMaxService.generate_image", fake_generate_image)

    result = await llm_config._execute_config_test(
        "minimax", "not-a-real-key", "image-01", "测试",
        model_type="image-generation", driver_key="minimax_image_v1",
    )

    assert result["message"] == "MiniMax API 连接成功！"
    assert result["response"].startswith("生成图像成功，URL:")


@pytest.mark.asyncio
async def test_qiniu_external_config_test_executes_registered_qiniu_driver(monkeypatch):
    from app.features.model_drivers import execute_external_connection_test

    called = {}

    async def fake_driver_test(_driver, context):
        called["driver_key"] = context.driver_key
        return DriverTestResult("connection_verified", "七牛可用", {})

    monkeypatch.setattr(
        "app.features.model_drivers.adapters.qiniu_kodo.QiniuKodoDriver.test_connection",
        fake_driver_test,
    )
    config = SimpleNamespace(
        id="qiniu-config", custom_base_url="https://cdn.example.com", timeout=60,
        extra_config={"storage_provider": "qiniu", "bucket": "media"},
        get_api_key_decrypted=lambda: "ak", get_api_secret_decrypted=lambda: "sk",
    )
    provider = SimpleNamespace(
        id="object-storage", name="object_storage", base_url="", api_type="storage",
        auth_type="apikey", auth_header="Authorization", name_cn="对象存储",
    )

    status, message = await execute_external_connection_test(
        config, provider, http_client_factory=None, dev_mode=lambda: False,
        which=lambda _binary: None, public_url_check=lambda _url: True,
    )

    assert called == {"driver_key": "qiniu_kodo_v1"}
    assert (status, message) == ("success", "七牛可用")
