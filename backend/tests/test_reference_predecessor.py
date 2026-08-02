from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.database import Base
from app.models import Chapter, Novel, Script, Shot, Storyboard, VideoJob
from app.services.reference_predecessor import find_previous_successful_video
from app.services.reference_package_builder import build_reference_package


@pytest_asyncio.fixture()
async def db_session() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4()}"


@pytest.mark.asyncio
async def test_predecessor_crosses_storyboards_and_chapters_but_not_novels(db_session: AsyncSession) -> None:
    user_id, novel_id, other_novel_id = _id("user"), _id("novel"), _id("other")
    chapter1 = Chapter(id=_id("chapter"), user_id=user_id, novel_id=novel_id, title="一", chapter_number=1)
    chapter2 = Chapter(id=_id("chapter"), user_id=user_id, novel_id=novel_id, title="二", chapter_number=2)
    script1 = Script(id=_id("script"), user_id=user_id, novel_id=novel_id, chapter_id=chapter1.id, title="一")
    script2 = Script(id=_id("script"), user_id=user_id, novel_id=novel_id, chapter_id=chapter2.id, title="二")
    board1 = Storyboard(
        id=_id("board"), user_id=user_id, novel_id=novel_id, script_id=script1.id, title="一-2",
        content={"chapter_id": chapter1.id, "scene_index": 2},
    )
    board2 = Storyboard(
        id=_id("board"), user_id=user_id, novel_id=novel_id, script_id=script2.id, title="二-1",
        content={"chapter_id": chapter2.id, "scene_index": 1},
    )
    previous = Shot(
        id=_id("shot"), user_id=user_id, storyboard_id=board1.id, shot_number=3,
        video_status="succeeded", video_url="https://cdn.example.com/chapter-1-last.mp4",
    )
    current = Shot(id=_id("shot"), user_id=user_id, storyboard_id=board2.id, shot_number=1)
    db_session.add_all([
        Novel(id=novel_id, user_id=user_id, title="本书"),
        Novel(id=other_novel_id, user_id=user_id, title="另一本书"),
        chapter1, chapter2, script1, script2, board1, board2, previous, current,
    ])
    await db_session.flush()

    result = await find_previous_successful_video(db_session, user_id=user_id, shot=current)

    assert result is not None
    assert result.id == previous.id


@pytest.mark.asyncio
async def test_predecessor_prefers_same_storyboard_and_never_uses_future_shot(db_session: AsyncSession) -> None:
    user_id, novel_id = _id("user"), _id("novel")
    chapter = Chapter(id=_id("chapter"), user_id=user_id, novel_id=novel_id, title="一", chapter_number=1)
    script = Script(id=_id("script"), user_id=user_id, novel_id=novel_id, chapter_id=chapter.id, title="一")
    board = Storyboard(
        id=_id("board"), user_id=user_id, novel_id=novel_id, script_id=script.id, title="一-1",
        content={"chapter_id": chapter.id, "scene_index": 1},
    )
    prior = Shot(id=_id("shot"), user_id=user_id, storyboard_id=board.id, shot_number=1,
                 video_status="succeeded", video_url="https://cdn.example.com/one.mp4")
    current = Shot(id=_id("shot"), user_id=user_id, storyboard_id=board.id, shot_number=2)
    future = Shot(id=_id("shot"), user_id=user_id, storyboard_id=board.id, shot_number=3,
                  video_status="succeeded", video_url="https://cdn.example.com/three.mp4")
    db_session.add_all([Novel(id=novel_id, user_id=user_id, title="本书"), chapter, script, board, prior, current, future])
    await db_session.flush()

    result = await find_previous_successful_video(db_session, user_id=user_id, shot=current)

    assert result is not None
    assert result.id == prior.id


@pytest.mark.asyncio
async def test_multimodal_reference_package_includes_cross_chapter_predecessor(db_session: AsyncSession) -> None:
    user_id, novel_id = _id("user"), _id("novel")
    first = Chapter(id=_id("chapter"), user_id=user_id, novel_id=novel_id, title="一", chapter_number=1)
    second = Chapter(id=_id("chapter"), user_id=user_id, novel_id=novel_id, title="二", chapter_number=2)
    first_script = Script(id=_id("script"), user_id=user_id, novel_id=novel_id, chapter_id=first.id, title="一")
    second_script = Script(id=_id("script"), user_id=user_id, novel_id=novel_id, chapter_id=second.id, title="二")
    first_board = Storyboard(id=_id("board"), user_id=user_id, novel_id=novel_id, script_id=first_script.id,
                             title="一", content={"chapter_id": first.id, "scene_index": 1})
    second_board = Storyboard(id=_id("board"), user_id=user_id, novel_id=novel_id, script_id=second_script.id,
                              title="二", content={"chapter_id": second.id, "scene_index": 1})
    previous = Shot(id=_id("shot"), user_id=user_id, storyboard_id=first_board.id, shot_number=2,
                    video_status="succeeded", video_url="https://cdn.example.com/previous.mp4")
    current = Shot(id=_id("shot"), user_id=user_id, storyboard_id=second_board.id, shot_number=1,
                   prompt="顾清霜继续前行", character_refs=[], extra_data={"entity_refs": {}})
    previous_job = VideoJob(
        id=_id("video-job"), user_id=user_id, shot_id=previous.id, status="succeeded",
        video_url=previous.video_url, cover_url="https://cdn.example.com/previous-last-frame.jpg",
    )
    db_session.add_all([
        Novel(id=novel_id, user_id=user_id, title="本书"), first, second, first_script, second_script,
        first_board, second_board, previous, current, previous_job,
    ])
    await db_session.flush()

    async def public_url(_db, _user_id, url):
        return {"provider_url": url}

    package = await build_reference_package(
        db_session, user_id, shot=current, lineage={"novel_id": novel_id},
        model_limits={"images": 9, "videos": 3, "audios": 0, "at_reference": True},
        resolve_public_url=public_url,
    )

    assert package["videos"] == [{
        "url": previous.video_url,
        "role_tag": "previous_shot",
        "source_shot_id": previous.id,
        "at_index": 1,
    }]
    assert package["images"] == [{
        "url": previous_job.cover_url,
        "role_tag": "previous_shot_frame",
        "entity_type": "frame",
        "entity_id": previous.id,
        "view_key": "last_frame",
        "at_index": 1,
    }]
