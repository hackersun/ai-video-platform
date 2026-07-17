"""Volcano ARK client construction."""

from typing import Optional


def create_ark_client(api_key: str, base_url: Optional[str] = None):
    from volcenginesdkarkruntime import Ark

    return Ark(
        base_url=base_url or "https://ark.cn-beijing.volces.com/api/v3",
        api_key=api_key,
    )


def build_ark_video_create_kwargs(
    *, model: str, content: list[dict], duration: int, resolution: str,
    camera_fixed: bool, watermark: bool, generate_audio: bool = False,
    seed: int | None = None,
) -> dict:
    values = {
        "model": model, "content": content, "duration": duration, "resolution": resolution,
        "camera_fixed": camera_fixed, "watermark": watermark, "generate_audio": generate_audio,
    }
    if seed is not None:
        values["seed"] = seed
    return values


def submit_ark_video_task(
    *, create_kwargs: dict, api_key: str | None = None,
    base_url: Optional[str] = None, client=None,
):
    active_client = client or create_ark_client(api_key or "", base_url)
    return active_client.content_generation.tasks.create(**create_kwargs)
