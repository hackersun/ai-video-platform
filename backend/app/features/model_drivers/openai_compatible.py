"""Factories for text providers using the OpenAI Chat Completions wire format."""

from typing import Optional

from app.core.deepseek_catalog import DEEPSEEK_API_BASE_URL
from app.services.openai_service import OpenAIService


_DEFAULT_BASE_URLS = {"deepseek": DEEPSEEK_API_BASE_URL}


def create_openai_compatible_service(
    api_key: str, provider_name: str, base_url: Optional[str],
) -> OpenAIService:
    return OpenAIService(api_key, base_url or _DEFAULT_BASE_URLS.get(provider_name))
