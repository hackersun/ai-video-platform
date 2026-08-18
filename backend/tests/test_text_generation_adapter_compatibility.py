import pytest
from types import SimpleNamespace

from app.core import api_key_utils


@pytest.mark.asyncio
async def test_structured_legacy_text_generation_reserves_enough_output_tokens(monkeypatch) -> None:
    from app.features.model_drivers.adapters import legacy_text
    from app.features.model_drivers.domain import TextCommand
    from app.features.model_drivers import text_execution

    captured = {}

    class FakeService:
        async def safe_chat_completion(self, **kwargs):
            captured.update(kwargs)
            return {"choices": [{"message": {"content": "[]"}}]}

    monkeypatch.setattr(text_execution, "create_text_generation_service", lambda *args: FakeService())
    context = SimpleNamespace(
        api_key="not-a-real-key",
        base_url="https://example.test",
        connection_params={"provider_name": "deepseek"},
        profile=SimpleNamespace(provider_id="deepseek", api_model_id="deepseek-v4-flash"),
    )

    await legacy_text.LegacyTextDriver().submit(
        TextCommand(prompt="extract", output_contract="json_array"), context,
    )

    assert captured["max_tokens"] == 12000
    assert captured["thinking"] == {"type": "disabled"}


def test_deepseek_connection_success_message_is_chinese_and_provider_specific() -> None:
    from app.features.model_drivers.adapters.legacy_text import _SUCCESS_MESSAGES

    assert _SUCCESS_MESSAGES["deepseek"] == "DeepSeek 官方 API 连接成功！"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_name", "expected_service", "base_url", "expected_base_url"),
    [
        (
            "qianlian",
            "QianlianService",
            "https://coding.example.test/apps/anthropic/",
            "https://coding.example.test/apps/anthropic/v1",
        ),
        ("dashscope", "DashScopeService", "https://dashscope.example.test/v1/", "https://dashscope.example.test/v1"),
        ("qwen", "DashScopeService", "https://qwen.example.test/v1/", "https://qwen.example.test/v1"),
        ("minimax", "MiniMaxService", "https://minimax.example.test/v1/", "https://minimax.example.test/v1"),
        ("volcano", "VolcanoService", "https://ark.example.test/v1/", "https://ark.example.test/v1"),
        (
            "volcano_agent_plan",
            "VolcanoService",
            "https://agent.example.test/v1/",
            "https://agent.example.test/v1",
        ),
        ("openai", "OpenAIService", "https://openai.example.test/v1/", "https://openai.example.test/v1"),
        ("deepseek", "OpenAIService", None, "https://api.deepseek.com"),
        ("baidu", "OpenAIService", "https://baidu.example.test/v1/", "https://baidu.example.test/v1"),
    ],
)
async def test_legacy_text_factory_preserves_provider_request_and_response_contract(
    monkeypatch,
    provider_name,
    expected_service,
    base_url,
    expected_base_url,
):
    service = api_key_utils.create_text_generation_service("not-a-real-key", provider_name, base_url)
    captured = {}

    async def fake_safe_chat_completion(**kwargs):
        captured.update(kwargs)
        return {"choices": [{"message": {"content": "<think>private</think>provider reply"}}]}

    monkeypatch.setattr(service._service, "safe_chat_completion", fake_safe_chat_completion, raising=False)
    model_id = f"{provider_name}-api-model"
    response = await service.safe_chat_completion(
        model=model_id,
        messages=[{"role": "user", "content": "hello"}],
        temperature=0.2,
        max_tokens=321,
    )

    assert type(service._service).__name__ == expected_service
    assert service._service.base_url == expected_base_url
    assert captured["model"] == model_id
    assert api_key_utils.extract_chat_content(response) == "provider reply"


@pytest.mark.asyncio
async def test_legacy_user_text_service_tuple_preserves_resolved_model_and_base_url(monkeypatch):
    async def fake_model_config(_db, _user_id, config_id=None):
        return "not-a-real-key", "minimax", "MiniMax-M3", "https://minimax.example.test/v1/"

    monkeypatch.setattr(api_key_utils, "get_user_text_model_config", fake_model_config)

    service, provider_name, model_id, base_url = await api_key_utils.get_user_text_generation_service(
        object(), "user-1"
    )

    assert type(service._service).__name__ == "MiniMaxService"
    assert service._service.base_url == "https://minimax.example.test/v1"
    assert provider_name == "minimax"
    assert model_id == "MiniMax-M3"
    assert base_url == "https://minimax.example.test/v1/"
