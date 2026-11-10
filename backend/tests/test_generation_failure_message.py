"""Generation-path failures must map to Chinese actionable repair hints."""

from __future__ import annotations

from app.features.model_drivers.adapters._shared import (
    connection_failure_message,
    generation_failure_message,
)


class _HttpError(Exception):
    def __init__(self, status_code: int, message: str = "err"):
        self.status_code = status_code
        super().__init__(message)


def test_generation_failure_differs_from_connection_copy():
    err = _HttpError(401, "Unauthorized invalid api key")
    conn = connection_failure_message(err)
    gen = generation_failure_message(err, capability="video")
    assert "连接测试" in conn
    assert "连接测试" not in gen
    assert "视频生成失败" in gen
    assert "模型设置" in gen


def test_generation_failure_quota_and_network():
    assert "额度" in generation_failure_message(_HttpError(429), capability="tts")
    assert "网络" in generation_failure_message(TimeoutError(), capability="image") or "连接" in generation_failure_message(
        TimeoutError(), capability="image"
    )


def test_generation_failure_app_id_and_budget():
    assert "App ID" in generation_failure_message(ValueError("missing app_id"), capability="speech_generation")
    assert "费用上限" in generation_failure_message(RuntimeError("spend cap / budget exceeded"), capability="video")


def test_generation_failure_does_not_leak_secrets():
    msg = generation_failure_message(RuntimeError("invalid api key sk-secret-12345"), capability="text")
    assert "sk-secret" not in msg
    assert "文本生成失败" in msg
