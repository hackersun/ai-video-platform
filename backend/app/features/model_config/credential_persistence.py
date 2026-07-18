"""Persist LLM configuration fields through the credential encryption boundary."""

from typing import Any, Optional, Protocol

from app.models.llm_config import LLMConfig


class LLMConfigInput(Protocol):
    model_id: str
    name: str
    api_key: Optional[str]
    api_secret: Optional[str]
    temperature: float
    top_p: float
    max_tokens: Optional[int]
    extra_params: Any
    is_default: bool


def apply_create_or_upsert_config(
    config: LLMConfig,
    request: LLMConfigInput,
    *,
    is_existing: bool,
) -> None:
    existing_plain_key = config.get_api_key_decrypted() if is_existing else ""
    api_key_changed = is_existing and request.api_key != existing_plain_key
    config.name = request.name
    config.set_api_key_encrypted(request.api_key or "")
    if request.api_secret:
        config.set_api_secret_encrypted(request.api_secret)
    config.temperature = request.temperature
    config.top_p = request.top_p
    config.max_tokens = request.max_tokens
    config.extra_params = request.extra_params
    config.is_default = request.is_default
    if not is_existing:
        config.test_status = "pending"
    elif api_key_changed:
        config.test_status = "pending"
        config.test_message = "配置已更新，请重新测试连接"


def apply_config_update(config: LLMConfig, request: LLMConfigInput) -> None:
    existing_plain_key = config.get_api_key_decrypted()
    next_api_key = request.api_key.strip() if isinstance(request.api_key, str) else None
    api_key_changed = bool(next_api_key) and next_api_key != existing_plain_key
    model_changed = request.model_id != config.model_id
    config.name = request.name
    config.model_id = request.model_id
    if next_api_key:
        config.set_api_key_encrypted(next_api_key)
    if request.api_secret:
        config.set_api_secret_encrypted(request.api_secret)
    config.temperature = request.temperature
    config.top_p = request.top_p
    config.max_tokens = request.max_tokens
    config.extra_params = request.extra_params
    config.is_default = request.is_default
    if api_key_changed or model_changed:
        config.test_status = "pending"
        config.test_message = "模型或 API Key 已更新，请重新测试连接"
