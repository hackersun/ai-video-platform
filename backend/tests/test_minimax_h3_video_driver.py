from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from app.features.model_config.domain import ModelProfileContract
from app.features.model_drivers import (
    DriverContext,
    DriverExecutionError,
    VideoCommand,
    VideoReference,
    build_builtin_driver_registry,
    execute_connection_test,
    execute_generation,
    execute_poll,
)
from app.services.minimax_h3_video_contract import (
    MINIMAX_H3_DRIVER_KEY,
    MINIMAX_H3_MODEL_ID,
    h3_parameter_schema,
)


def _context() -> DriverContext:
    profile = ModelProfileContract(
        profile_version_id="minimax-h3-v1",
        provider_id="minimax",
        api_model_id=MINIMAX_H3_MODEL_ID,
        driver_key=MINIMAX_H3_DRIVER_KEY,
        capabilities=frozenset({"video_generation"}),
        input_contract={},
        output_contract={},
        parameter_schema=h3_parameter_schema(),
        default_params={},
        limits={
            "max_prompt_chars": 7000,
            "max_reference_images": 9,
            "max_reference_videos": 3,
            "max_reference_audios": 3,
        },
        pricing={},
        prompt_profile_key=None,
        contract_version="minimax-h3-v2",
    )
    return DriverContext(
        profile=profile,
        driver_key=MINIMAX_H3_DRIVER_KEY,
        connection_id="minimax-connection",
        secrets={"api_key": "not-a-real-key"},
        base_url="https://api.minimaxi.com/v1",
    )


@dataclass
class _FakeResponse:
    payload: dict[str, Any]
    status: int = 200

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def json(self, **_kwargs):
        return self.payload

    async def text(self):
        return str(self.payload)


class _FakeSession:
    responses: list[_FakeResponse] = []
    calls: list[dict[str, Any]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def post(self, url, **kwargs):
        self.calls.append({"method": "POST", "url": url, **kwargs})
        return self.responses.pop(0)

    def get(self, url, **kwargs):
        self.calls.append({"method": "GET", "url": url, **kwargs})
        return self.responses.pop(0)


@pytest.fixture(autouse=True)
def _fake_http(monkeypatch):
    _FakeSession.responses = []
    _FakeSession.calls = []
    monkeypatch.setattr(
        "app.features.model_drivers.adapters.minimax_h3_video.aiohttp.ClientSession",
        _FakeSession,
    )


@pytest.mark.asyncio
async def test_h3_submit_uses_v2_multimodal_content_and_preserves_roles():
    _FakeSession.responses = [_FakeResponse({"task_id": "h3-task-1"})]
    command = VideoCommand(
        prompt="电影感夜景，人物缓慢回头",
        reference_images=("https://cdn.test/start.png",),
        reference_audios=("https://cdn.test/voice.mp3",),
        references=(
            VideoReference("image", "https://cdn.test/start.png", "first_frame"),
            VideoReference("audio", "https://cdn.test/voice.mp3", "reference_audio"),
        ),
        params={"duration": 5, "resolution": "2K", "ratio": "adaptive"},
    )

    result = await execute_generation(build_builtin_driver_registry(), command, _context())

    assert result.status == "submitted"
    assert result.provider_task_id == "h3-task-1"
    request = _FakeSession.calls[0]
    assert request["url"] == "https://api.minimaxi.com/v2/video_generation"
    assert request["headers"]["Authorization"] == "Bearer not-a-real-key"
    assert request["json"] == {
        "model": "MiniMax-H3",
        "content": [
            {"type": "text", "text": "电影感夜景，人物缓慢回头"},
            {
                "type": "image_url",
                "image_url": {"url": "https://cdn.test/start.png"},
                "role": "first_frame",
            },
            {
                "type": "audio_url",
                "audio_url": {"url": "https://cdn.test/voice.mp3"},
                "role": "reference_audio",
            },
        ],
        "duration": 5,
        "resolution": "2K",
        "ratio": "adaptive",
    }
    assert "--duration" not in request["json"]["content"][0]["text"]


@pytest.mark.asyncio
async def test_h3_poll_extracts_official_success_url_and_usage():
    _FakeSession.responses = [_FakeResponse({
        "task": {
            "id": "h3-task-1",
            "model": "MiniMax-H3",
            "status": "succeeded",
            "content": {"url": "https://cdn.test/h3.mp4"},
            "duration": 5,
            "resolution": "2K",
            "ratio": "16:9",
            "usage": {"total_seconds": 5},
        }
    })]

    result = await execute_poll(build_builtin_driver_registry(), "h3-task-1", _context())

    assert result.status == "completed"
    assert result.output == {
        "video_url": "https://cdn.test/h3.mp4",
        "duration": 5,
        "resolution": "2K",
        "ratio": "16:9",
        "usage": {"total_seconds": 5},
    }
    assert _FakeSession.calls[0]["url"] == (
        "https://api.minimaxi.com/v2/query/video_generation/h3-task-1"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_status", "expected_status"),
    [
        ("pending", "pending"),
        ("preparing", "pending"),
        ("processing", "running"),
        ("failed", "failed"),
        ("cancelled", "cancelled"),
    ],
)
async def test_h3_poll_maps_provider_terminal_and_progress_states(
    provider_status: str, expected_status: str
):
    _FakeSession.responses = [_FakeResponse({
        "task": {"id": "h3-task-1", "status": provider_status}
    })]

    result = await execute_poll(build_builtin_driver_registry(), "h3-task-1", _context())

    assert result.status == expected_status


@pytest.mark.asyncio
async def test_h3_poll_rejects_success_without_download_url():
    _FakeSession.responses = [_FakeResponse({
        "task": {"id": "h3-task-1", "status": "succeeded", "content": {}}
    })]

    with pytest.raises(DriverExecutionError) as error:
        await execute_poll(build_builtin_driver_registry(), "h3-task-1", _context())

    assert type(error.value.cause).__name__ == "DriverResultError"


@pytest.mark.asyncio
async def test_h3_connection_test_is_configuration_only_and_never_spends_generation_quota():
    result = await execute_connection_test(
        build_builtin_driver_registry(), MINIMAX_H3_DRIVER_KEY, _context()
    )

    assert result.status == "connection_configured"
    assert result.sanitized_evidence == {"paid_probe": False}
    assert _FakeSession.calls == []
