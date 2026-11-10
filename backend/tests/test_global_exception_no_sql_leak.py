"""Global 500 handler must not echo exception/SQL text to clients."""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse


def test_global_handler_returns_generic_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    from main import global_exception_handler

    app = FastAPI()

    @app.get("/boom")
    async def boom():
        raise RuntimeError("SELECT * FROM users WHERE secret='x'")

    app.add_exception_handler(Exception, global_exception_handler)
    client = TestClient(app, raise_server_exceptions=False)
    res = client.get("/boom")
    assert res.status_code == 500
    body = res.json()
    assert body["detail"] == "Internal server error"
    assert "SELECT" not in str(body)
    assert "secret" not in str(body)
