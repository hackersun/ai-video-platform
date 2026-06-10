from __future__ import annotations

import asyncio

from app.services.minimax_service import MiniMaxService


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


def test_tts_parses_data_audio_url(monkeypatch) -> None:
    captured: dict = {}
    monkeypatch.setattr(
        "app.services.minimax_service.aiohttp.ClientSession",
        lambda: _FakeSession(
            {"data": {"audio_url": "https://example.com/preview.mp3", "task_id": "task-1"}},
            captured,
        ),
    )

    result = asyncio.run(
        MiniMaxService("api-key").text_to_speech(
            text="试听文本",
            model="speech-2.6-hd",
            voice_id="female-shaonv",
        )
    )

    assert result["audio_url"] == "https://example.com/preview.mp3"
    assert result["task_id"] == "task-1"


def test_tts_normalizes_builtin_minimax_tts_model_id(monkeypatch) -> None:
    captured: dict = {}
    monkeypatch.setattr(
        "app.services.minimax_service.aiohttp.ClientSession",
        lambda: _FakeSession(
            {"data": {"audio": "https://example.com/voice.mp3"}},
            captured,
        ),
    )

    result = asyncio.run(
        MiniMaxService("api-key").text_to_speech(
            text="试听文本",
            model="MiniMax-speech-2.6-hd",
            voice_id="female-shaonv",
        )
    )

    assert captured["json"]["model"] == "speech-2.6-hd"
    assert result["audio_url"] == "https://example.com/voice.mp3"


def test_chat_completion_routes_minimax_m3_to_chatcompletion_v2(monkeypatch) -> None:
    captured: dict = {}
    monkeypatch.setattr(
        "app.services.minimax_service.aiohttp.ClientSession",
        lambda: _FakeSession({"reply": "ok"}, captured),
    )

    result = asyncio.run(
        MiniMaxService("api-key").chat_completion(
            model="MiniMax-M3",
            messages=[{"role": "user", "content": "你好"}],
            max_tokens=32,
        )
    )

    assert captured["url"].endswith("/text/chatcompletion_v2")
    assert captured["json"]["model"] == "MiniMax-M3"
    assert captured["json"]["messages"][0]["content"] == "你好"
    assert result == {"reply": "ok"}


def test_image_generation_normalizes_builtin_minimax_image_model_id(monkeypatch) -> None:
    captured: dict = {}
    monkeypatch.setattr(
        "app.services.minimax_service.aiohttp.ClientSession",
        lambda: _FakeSession(
            {"data": {"image_base64": ["iVBORw0KGgoAAAANSUhEUgAA"]}, "id": "trace-id"},
            captured,
        ),
    )

    result = asyncio.run(
        MiniMaxService("api-key").generate_image(
            prompt="角色设定图",
            model="MiniMax-image-01",
            response_format="base64",
        )
    )

    assert captured["url"].endswith("/image_generation")
    assert captured["json"]["model"] == "image-01"
    assert captured["json"]["response_format"] == "base64"
    assert result["id"] == "trace-id"


def test_image_generation_raises_base_resp_error(monkeypatch) -> None:
    captured: dict = {}
    monkeypatch.setattr(
        "app.services.minimax_service.aiohttp.ClientSession",
        lambda: _FakeSession(
            {"base_resp": {"status_code": 1004, "status_msg": "invalid model"}},
            captured,
        ),
    )

    try:
        asyncio.run(
            MiniMaxService("api-key").generate_image(
                prompt="角色设定图",
                model="MiniMax-M3",
                response_format="base64",
            )
        )
    except Exception as exc:
        assert "MiniMax 图像生成失败 [1004]: invalid model" in str(exc)
    else:
        raise AssertionError("MiniMax provider error should be raised")
