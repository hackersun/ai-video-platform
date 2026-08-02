"""Validate and merge operator-supplied multimodal video references."""

from typing import Any, Iterable, Mapping

from app.features.video_generation.errors import VideoGenerationError
from app.services.media_delivery import is_cloud_accessible_http_url


REFERENCE_LABELS = {"images": "图片", "videos": "视频", "audios": "音频"}


def _unique_urls(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if isinstance(value, str) and value.strip()))


def build_manual_reference_package(
    *, image_urls: Iterable[str], video_urls: Iterable[str], audio_urls: Iterable[str],
    limits: Mapping[str, Any],
) -> dict[str, Any]:
    values = {
        "images": _unique_urls(image_urls),
        "videos": _unique_urls(video_urls),
        "audios": _unique_urls(audio_urls),
    }
    for key, urls in values.items():
        limit = max(int(limits.get(key, 0) or 0), 0)
        if len(urls) > limit:
            raise VideoGenerationError(422, f"当前模型最多 {limit} 个{REFERENCE_LABELS[key]}参考。")
        if any(not is_cloud_accessible_http_url(url) for url in urls):
            raise VideoGenerationError(422, f"{REFERENCE_LABELS[key]}参考必须使用公网可访问的 http(s) URL。")
    return {
        key: [{"url": url, "source": "manual_public_url"} for url in urls]
        for key, urls in values.items()
    }


def merge_reference_packages(
    canonical: Mapping[str, Any] | None,
    manual: Mapping[str, Any] | None,
    *,
    limits: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    result = dict(canonical or {})
    for key in REFERENCE_LABELS:
        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in [*(canonical or {}).get(key, []), *(manual or {}).get(key, [])]:
            if not isinstance(item, dict) or not item.get("url") or item["url"] in seen:
                continue
            seen.add(item["url"])
            items.append(dict(item))
        limit = max(int((limits or {}).get(key, len(items)) or 0), 0)
        if limits is not None and len(items) > limit:
            raise VideoGenerationError(
                422,
                f"当前模型最多 {limit} 个{REFERENCE_LABELS[key]}参考；自动资产参考已占用容量，请删除人工参考或更换模型。",
            )
        result[key] = items
    return result


def merge_request_references(
    canonical: Mapping[str, Any] | None,
    request: Any,
    limits: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, int]]:
    manual = build_manual_reference_package(
        image_urls=request.reference_image_urls,
        video_urls=request.reference_video_urls,
        audio_urls=request.reference_audio_urls,
        limits=limits,
    )
    counts = {key: len(manual[key]) for key in REFERENCE_LABELS}
    return merge_reference_packages(canonical, manual, limits=limits), counts


__all__ = ["build_manual_reference_package", "merge_reference_packages", "merge_request_references"]
