"""Parse provider reference content without coupling it to submission."""

from typing import Any

from app.features.model_drivers.public import VideoReference


def video_references(content: list[dict[str, Any]]) -> tuple[VideoReference, ...]:
    references: list[VideoReference] = []
    media_types = {"image_url": "image", "video_url": "video", "audio_url": "audio"}
    for item in content:
        item_type = item.get("type") if isinstance(item, dict) else None
        value = item.get(item_type) if item_type in media_types else None
        url = value.get("url") if isinstance(value, dict) else None
        if isinstance(url, str) and url:
            media_type = media_types[item_type]
            references.append(VideoReference(
                media_type, url, str(item.get("role") or f"reference_{media_type}"),
            ))
    return tuple(references)
