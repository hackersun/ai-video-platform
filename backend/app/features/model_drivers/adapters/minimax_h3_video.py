"""MiniMax H3 V2 video submission and polling driver."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import aiohttp

from app.features.model_drivers.domain import (
    DriverParameterError,
    DriverResultError,
    DriverSubmission,
    DriverTestResult,
    VideoCommand,
    VideoReference,
)
from app.services.minimax_h3_video_contract import (
    MINIMAX_H3_DRIVER_KEY,
    MINIMAX_H3_MODEL_ID,
    validate_h3_generation,
)


_PENDING_STATUSES = frozenset({"pending", "waiting", "queued", "preparing"})
_RUNNING_STATUSES = frozenset({"processing", "running"})
_TERMINAL_STATUSES = frozenset({"failed", "cancelled"})


def _api_root(base_url: str | None) -> str:
    root = (base_url or "https://api.minimaxi.com").rstrip("/")
    return root[:-3] if root.endswith("/v1") else root


def _headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def _reference_content(reference: VideoReference) -> dict[str, Any]:
    field = f"{reference.media_type}_url"
    return {
        "type": field,
        field: {"url": reference.url},
        "role": reference.role,
    }


def _legacy_references(command: VideoCommand) -> tuple[VideoReference, ...]:
    return (
        *(VideoReference("image", url, "reference_image") for url in command.reference_images),
        *(VideoReference("video", url, "reference_video") for url in command.reference_videos),
        *(VideoReference("audio", url, "reference_audio") for url in command.reference_audios),
    )


def _references(command: VideoCommand) -> tuple[VideoReference, ...]:
    return command.references or _legacy_references(command)


def _provider_params(command: VideoCommand) -> dict[str, Any]:
    return {
        key: command.params[key]
        for key in ("duration", "resolution", "ratio")
        if key in command.params
    }


async def _response_json(response) -> Mapping[str, Any]:
    if response.status < 200 or response.status >= 300:
        raise DriverResultError("MiniMax H3 request was rejected")
    payload = await response.json(content_type=None)
    if not isinstance(payload, Mapping):
        raise DriverResultError("MiniMax H3 returned an invalid response")
    base_resp = payload.get("base_resp")
    if isinstance(base_resp, Mapping) and base_resp.get("status_code") not in (None, 0):
        raise DriverResultError("MiniMax H3 returned a provider error")
    return payload


def _validate(command: VideoCommand, references: tuple[VideoReference, ...]) -> None:
    params = command.params
    issues = validate_h3_generation(
        prompt=command.prompt,
        duration=params.get("duration"),
        resolution=params.get("resolution"),
        ratio=params.get("ratio"),
        references=tuple({"media_type": item.media_type} for item in references),
    )
    if issues:
        raise DriverParameterError(issues[0]["message"])


def _completed_output(task: Mapping[str, Any]) -> dict[str, Any]:
    content = task.get("content")
    video_url = content.get("url") if isinstance(content, Mapping) else None
    if not isinstance(video_url, str) or not video_url:
        raise DriverResultError("MiniMax H3 succeeded without a video URL")
    output = {"video_url": video_url}
    for key in ("duration", "resolution", "ratio", "usage"):
        if task.get(key) is not None:
            output[key] = task[key]
    return output


class MiniMaxH3VideoDriver:
    key = MINIMAX_H3_DRIVER_KEY
    capabilities = frozenset({"video_generation"})

    async def test_connection(self, context):
        if not context.api_key:
            return DriverTestResult("failed", "缺少 API Key", {"paid_probe": False})
        return DriverTestResult(
            "connection_configured",
            "配置完整；真实 H3 任务提交时验证权限和额度",
            {"paid_probe": False},
        )

    async def submit(self, command, context):
        if not isinstance(command, VideoCommand):
            raise DriverParameterError("MiniMax H3 requires a video command")
        references = _references(command)
        _validate(command, references)
        payload = {
            "model": MINIMAX_H3_MODEL_ID,
            "content": [
                {"type": "text", "text": command.prompt},
                *(_reference_content(item) for item in references),
            ],
            **_provider_params(command),
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{_api_root(context.base_url)}/v2/video_generation",
                headers=_headers(context.api_key),
                json=payload,
                timeout=aiohttp.ClientTimeout(total=300),
            ) as response:
                result = await _response_json(response)
        task_id = result.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise DriverResultError("MiniMax H3 did not return a task ID")
        return DriverSubmission("submitted", task_id, {})

    async def poll(self, provider_task_id, context):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{_api_root(context.base_url)}/v2/query/video_generation/{provider_task_id}",
                headers=_headers(context.api_key),
                timeout=aiohttp.ClientTimeout(total=60),
            ) as response:
                result = await _response_json(response)
        task = result.get("task")
        if not isinstance(task, Mapping):
            raise DriverResultError("MiniMax H3 did not return task state")
        status = str(task.get("status") or "").lower()
        if status in _PENDING_STATUSES:
            return DriverSubmission("pending", provider_task_id, {})
        if status in _RUNNING_STATUSES:
            return DriverSubmission("running", provider_task_id, {})
        if status == "succeeded":
            return DriverSubmission("completed", provider_task_id, _completed_output(task))
        if status in _TERMINAL_STATUSES:
            return DriverSubmission(status, provider_task_id, {"provider_status": status})
        raise DriverResultError("MiniMax H3 returned an unknown task status")


__all__ = ["MiniMaxH3VideoDriver"]
