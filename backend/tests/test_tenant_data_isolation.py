from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
import pytest_asyncio

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models import Chapter, Novel, Script, Shot, Storyboard
from main import app
from tests.model_center_api_database import (
    SessionLocal as AsyncSessionLocal,
    dispose_database,
    reset_database,
)


OWNER = "tenant-owner"
OTHER = "tenant-other"


@pytest_asyncio.fixture(scope="module", autouse=True)
async def isolated_database():
    await reset_database()
    async with AsyncSessionLocal() as db:
        novel = Novel(id=str(uuid4()), user_id=OWNER, title="租户隔离小说")
        chapter = Chapter(
            id=str(uuid4()), novel_id=novel.id, user_id=OWNER,
            title="第一章", chapter_number=1,
        )
        script = Script(
            id=str(uuid4()), user_id=OWNER, novel_id=novel.id,
            chapter_id=chapter.id, title="隔离剧本",
        )
        storyboard = Storyboard(
            id=str(uuid4()), script_id=script.id, novel_id=novel.id,
            user_id=OWNER, title="隔离分镜",
        )
        shot = Shot(
            id=str(uuid4()), storyboard_id=storyboard.id, user_id=OWNER,
            shot_number=1, visual_description="隔离镜头",
        )
        db.add_all([novel, chapter, script, storyboard, shot])
        await db.commit()
        ids.update({
            "novel": novel.id, "chapter": chapter.id, "script": script.id,
            "storyboard": storyboard.id, "shot": shot.id,
        })
    yield
    await dispose_database()


ids: dict[str, str] = {}


@pytest_asyncio.fixture()
async def client():
    async def override_db():
        async with AsyncSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_id] = lambda: OTHER
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
    ) as api_client:
        yield api_client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_other_user_cannot_list_or_read_owner_story_data(client):
    list_paths = (
        "/api/v1/novels",
        "/api/v1/scripts",
        f"/api/v1/chapters/novel/{ids['novel']}",
        f"/api/v1/storyboards/script/{ids['script']}",
        f"/api/v1/shots/storyboard/{ids['storyboard']}",
    )
    for path in list_paths:
        response = await client.get(path)
        assert response.status_code in {200, 404}, (path, response.text)
        if response.status_code == 200:
            assert response.json() == [], path

    item_paths = (
        f"/api/v1/novels/{ids['novel']}",
        f"/api/v1/chapters/{ids['chapter']}",
        f"/api/v1/scripts/{ids['script']}",
        f"/api/v1/storyboards/{ids['storyboard']}",
        f"/api/v1/shots/{ids['shot']}",
    )
    for path in item_paths:
        response = await client.get(path)
        assert response.status_code == 404, (path, response.text)
