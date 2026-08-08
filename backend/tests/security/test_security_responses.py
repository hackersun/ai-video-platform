from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from main import app, global_exception_handler


@pytest.mark.anyio
async def test_unhandled_exception_is_hidden_behind_stable_chinese_message() -> None:
    request = Request(
        {"type": "http", "method": "GET", "path": "/secret", "headers": []}
    )

    response = await global_exception_handler(
        request,
        RuntimeError("postgresql://admin:password@database/private"),
    )
    payload = json.loads(response.body)

    assert response.status_code == 500
    assert payload == {
        "code": "INTERNAL_ERROR",
        "detail": "服务暂时不可用，请稍后重试",
    }
    assert response.headers.get("access-control-allow-origin") != "*"


def test_security_headers_are_present_on_normal_responses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DEV_MODE", "true")

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
