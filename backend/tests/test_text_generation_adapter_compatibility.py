import pytest

from app.core import api_key_utils


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
    async def fake_model_config(_db, _user_id):
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
