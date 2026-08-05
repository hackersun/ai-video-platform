"""Provider-neutral legacy text response normalization."""

import re
from typing import Any, Optional


def normalize_provider_base_url(provider_name: str, base_url: Optional[str]) -> Optional[str]:
    """Normalize legacy provider URLs before constructing service clients."""
    if not base_url:
        return base_url
    normalized = base_url.rstrip("/")
    if provider_name == "qianlian" and normalized.endswith("/apps/anthropic"):
        return f"{normalized}/v1"
    return normalized


def strip_thinking_blocks(content: str) -> str:
    """Remove model reasoning blocks from user-facing text."""
    if not content:
        return content
    cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL | re.IGNORECASE)
    if cleaned.lstrip().lower().startswith("<think>"):
        marker = "</think>"
        end = cleaned.lower().find(marker)
        if end >= 0:
            cleaned = cleaned[end + len(marker):]
    return cleaned.strip()


def _content_to_text(value: Any) -> str:
    """Coerce common multimodal/text content shapes to plain text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            text = _content_to_text(item)
            if text:
                parts.append(text)
        return "\n".join(parts).strip()
    if isinstance(value, dict):
        for key in (
            "text",
            "content",
            "reply",
            "message",
            "output_text",
            "result",
            "value",
        ):
            text = _content_to_text(value.get(key))
            if text:
                return text
    return ""


def extract_chat_content(response: Any) -> str:
    """Extract assistant text from OpenAI-compatible and provider-native responses."""
    if isinstance(response, str):
        return strip_thinking_blocks(response)
    if not isinstance(response, dict):
        return ""

    choices = response.get("choices")
    if isinstance(choices, list):
        for choice in choices:
            if isinstance(choice, dict):
                message = choice.get("message") or choice.get("delta")
                if isinstance(message, dict):
                    text = _content_to_text(message.get("content"))
                    if text:
                        return strip_thinking_blocks(text)
                text = _content_to_text(choice.get("text") or choice.get("content"))
                if text:
                    return strip_thinking_blocks(text)
            else:
                text = _content_to_text(choice)
                if text:
                    return strip_thinking_blocks(text)

    output = response.get("output")
    if isinstance(output, dict):
        output_choices = output.get("choices")
        if isinstance(output_choices, list):
            text = extract_chat_content({"choices": output_choices})
            if text:
                return text
        for key in ("text", "content", "message", "reply"):
            text = _content_to_text(output.get(key))
            if text:
                return strip_thinking_blocks(text)
    elif isinstance(output, str):
        return strip_thinking_blocks(output)

    data = response.get("data")
    if isinstance(data, dict):
        for key in ("text", "content", "message", "reply", "result"):
            text = _content_to_text(data.get(key))
            if text:
                return strip_thinking_blocks(text)
    elif isinstance(data, list):
        text = _content_to_text(data)
        if text:
            return strip_thinking_blocks(text)

    for key in ("reply", "content", "text", "message", "output_text", "result"):
        text = _content_to_text(response.get(key))
        if text:
            return strip_thinking_blocks(text)
    return ""


def sanitize_chat_response(response: dict) -> dict:
    """Strip reasoning markers and normalize common native text responses."""
    try:
        for choice in response.get("choices") or []:
            message = choice.get("message") or {}
            content = message.get("content")
            if isinstance(content, str):
                message["content"] = strip_thinking_blocks(content)
        if not response.get("choices"):
            content = extract_chat_content(response)
            if content:
                response["choices"] = [{"message": {"role": "assistant", "content": content}}]
    except AttributeError:
        return response
    return response
