from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import AsyncSessionLocal
from app.models.novel import Novel
from init_db import init_db
from main import app


@pytest.fixture(scope="module", autouse=True)
def _init_database() -> None:
    init_db()


@pytest.mark.asyncio
async def test_create_novel_keeps_intro_and_style(monkeypatch) -> None:
    monkeypatch.setenv("DEV_MODE", "true")
    client = TestClient(app)
    user = f"intro-{uuid4()}"
    res = client.post("/api/v1/novels", headers={"Authorization": f"Bearer {user}"},
                      json={"title": "雾港", "genre": "悬疑", "intro": "世界观：雾港。", "style": "热血"})
    assert res.status_code == 201, res.text
    async with AsyncSessionLocal() as db:
        novel = await db.get(Novel, res.json()["id"])
        assert novel.extra_data["intro"] == "世界观：雾港。"
        assert novel.extra_data["novel_style"] == "热血"
