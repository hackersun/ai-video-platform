"""Helpers for normalizing image provider responses."""

from typing import Any


IMAGE_URL_KEYS = (
    "url",
    "image_url",
    "imageUrl",
    "file_url",
    "download_url",
)

IMAGE_BASE64_KEYS = (
    "image_base64",
    "imageBase64",
    "base64",
    "b64_json",
)

IMAGE_LIST_KEYS = (
    "data",
    "images",
    "image_urls",
    "imageUrls",
    "local_urls",
    "items",
    "outputs",
    "output",
    "result",
    "results",
    "artifacts",
    "payload",
    "image",
    "urls",
)


def _looks_like_image_url(value: str) -> bool:
    text = value.strip()
    return text.startswith(("http://", "https://", "/static/", "data:image/"))


def _looks_like_base64_image(value: str) -> bool:
    text = value.strip()
    return len(text) > 80 and not text.startswith(("http://", "https://", "/static/", "data:"))


def extract_image_urls_from_provider_result(result: Any) -> list[str]:
    """Extract image URLs from common provider response shapes.

    Providers are inconsistent here: OpenAI uses data:[{url}], MiniMax often uses
    data:{image_urls:[...]}, while local dev and some adapters use image_urls or
    local_urls at the top level. This keeps the endpoint code provider-agnostic.
    """
    urls: list[str] = []
    seen: set[str] = set()

    def add(value: Any) -> None:
        if isinstance(value, str) and _looks_like_image_url(value) and value not in seen:
            seen.add(value)
            urls.append(value)

    def add_base64(value: Any) -> None:
        if isinstance(value, str) and _looks_like_base64_image(value):
            data_url = f"data:image/png;base64,{value.strip()}"
            if data_url not in seen:
                seen.add(data_url)
                urls.append(data_url)

    def walk_base64(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                walk_base64(item)
            return
        add_base64(value)

    def walk(value: Any) -> None:
        if isinstance(value, str):
            add(value)
            return
        if isinstance(value, list):
            for item in value:
                walk(item)
            return
        if not isinstance(value, dict):
            return

        for key in IMAGE_URL_KEYS:
            add(value.get(key))
        for key in IMAGE_BASE64_KEYS:
            walk_base64(value.get(key))
        for key in IMAGE_LIST_KEYS:
            nested = value.get(key)
            if nested is not None:
                walk(nested)

    walk(result)
    return urls
