from __future__ import annotations

import asyncio

from app.services.volcano_service import VolcanoService
from app.core.api_key_utils import create_image_generation_service, create_text_generation_service


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload
        self.status = 200

    async def __aenter__(self) -> "_FakeResponse":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def text(self) -> str:
        return "ok"

    async def json(self) -> dict:
        return self._payload


class _FakeSession:
    def __init__(self, payload: dict, captured: dict):
        self._payload = payload
        self._captured = captured

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    def post(self, url, headers=None, json=None, timeout=None):
        self._captured["url"] = url
        self._captured["headers"] = headers
        self._captured["json"] = json
        self._captured["timeout"] = timeout
        return _FakeResponse(self._payload)


def test_text_to_speech_includes_voice_and_speed(monkeypatch) -> None:
    captured: dict = {}

    monkeypatch.setattr(
        "app.services.volcano_service.aiohttp.ClientSession",
        lambda: _FakeSession(
            {
                "task_id": "tts-task-123",
                "status": "succeeded",
                "audio_url": "https://example.com/audio.mp3",
                "duration": 3.5,
                "model": "test-tts-model",
                "message": "done",
            },
            captured,
        ),
    )

    result = asyncio.run(
        VolcanoService("api-key").text_to_speech(
            text="hello",
            model="test-tts-model",
            voice="narrator",
            speed=1.5,
        )
    )

    assert result["task_id"] == "tts-task-123"
    assert captured["json"]["voice"] == "narrator"
    assert captured["json"]["speed"] == 1.5


def test_video_voice_synthesis_uses_requested_model(monkeypatch) -> None:
    captured: dict = {}

    monkeypatch.setattr(
        "app.services.volcano_service.aiohttp.ClientSession",
        lambda: _FakeSession(
            {
                "task_id": "synthesis-task-123",
                "status": "succeeded",
                "output_url": "https://example.com/video.mp4",
                "duration": 10.0,
                "message": "done",
            },
            captured,
        ),
    )

    result = asyncio.run(
        VolcanoService("api-key").video_voice_synthesis(
            video_url="https://example.com/source.mp4",
            audio_url="https://example.com/audio.mp3",
            model="custom-synthesis-model",
        )
    )

    assert result["task_id"] == "synthesis-task-123"
    assert captured["json"]["model"] == "custom-synthesis-model"


def test_generate_video_skips_local_reference_image(monkeypatch) -> None:
    captured: dict = {}

    monkeypatch.setattr(
        "app.services.volcano_service.aiohttp.ClientSession",
        lambda: _FakeSession(
            {"id": "video-task-123", "status": "pending"},
            captured,
        ),
    )

    result = asyncio.run(
        VolcanoService("api-key").generate_video(
            prompt="生成连续动漫镜头",
            model="test-video-model",
            image_url="/static/generated/images/ref.png",
        )
    )

    assert result["id"] == "video-task-123"
    assert captured["json"]["content"][0]["type"] == "text"
    assert "--watermark false" in captured["json"]["content"][0]["text"]
    assert all(item["type"] != "image_url" for item in captured["json"]["content"])
    assert "云端调用不传image_url" in captured["json"]["content"][0]["text"]


def test_generate_video_sends_public_reference_image(monkeypatch) -> None:
    captured: dict = {}

    monkeypatch.setattr(
        "app.services.volcano_service.aiohttp.ClientSession",
        lambda: _FakeSession(
            {"id": "video-task-public-ref", "status": "pending"},
            captured,
        ),
    )

    result = asyncio.run(
        VolcanoService("api-key").generate_video(
            prompt="生成连续动漫镜头",
            model="test-video-model",
            image_url="https://example.com/ref.png",
        )
    )

    assert result["id"] == "video-task-public-ref"
    assert captured["json"]["content"][0]["type"] == "image_url"
    assert captured["json"]["content"][0]["image_url"]["url"] == "https://example.com/ref.png"


def test_volcano_agent_plan_text_factory_uses_plan_base_url(monkeypatch) -> None:
    captured: dict = {}

    monkeypatch.setattr(
        "app.services.volcano_service.aiohttp.ClientSession",
        lambda: _FakeSession(
            {"choices": [{"message": {"content": "ok"}}], "usage": {"total_tokens": 3}},
            captured,
        ),
    )

    service = create_text_generation_service(
        "agent-key",
        "volcano_agent_plan",
        "https://ark.cn-beijing.volces.com/api/plan/v3",
    )
    result = asyncio.run(
        service.chat_completion(
            model="ark-code-latest",
            messages=[{"role": "user", "content": "hello"}],
            max_tokens=16,
        )
    )

    assert result["choices"][0]["message"]["content"] == "ok"
    assert captured["url"] == "https://ark.cn-beijing.volces.com/api/plan/v3/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer agent-key"


def test_volcano_agent_plan_image_factory_uses_plan_base_url(monkeypatch) -> None:
    captured: dict = {}

    monkeypatch.setattr(
        "app.services.volcano_service.aiohttp.ClientSession",
        lambda: _FakeSession(
            {"data": [{"url": "https://example.com/image.png"}]},
            captured,
        ),
    )

    service = create_image_generation_service(
        "agent-key",
        "volcano_agent_plan",
        "https://ark.cn-beijing.volces.com/api/plan/v3",
    )
    result = asyncio.run(
        service.generate_image(
            prompt="cover",
            model="doubao-seedream-5.0-lite",
            size="2K",
        )
    )

    assert result["data"][0]["url"] == "https://example.com/image.png"
    assert captured["url"] == "https://ark.cn-beijing.volces.com/api/plan/v3/images/generations"
    assert captured["json"]["model"] == "doubao-seedream-5.0-lite"


def test_volcano_image_service_passes_seedream_50_flagship_model_id(monkeypatch) -> None:
    captured: dict = {}

    monkeypatch.setattr(
        "app.services.volcano_service.aiohttp.ClientSession",
        lambda: _FakeSession(
            {"data": [{"url": "https://example.com/seedream-5.png"}]},
            captured,
        ),
    )

    service = create_image_generation_service("ark-key", "volcano", None)
    result = asyncio.run(
        service.generate_image(
            prompt="anime character turnaround",
            model="doubao-seedream-5-0-260128",
            size="2048x2048",
        )
    )

    assert result["data"][0]["url"].endswith("seedream-5.png")
    assert captured["url"] == "https://ark.cn-beijing.volces.com/api/v3/images/generations"
    assert captured["json"]["model"] == "doubao-seedream-5-0-260128"
    assert captured["timeout"].total >= 600
