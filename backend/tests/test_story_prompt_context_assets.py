from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - ensure all SQLAlchemy models are registered
from app.core.database import Base
from app.models import Chapter, Novel, Script
from app.services.story_prompt_context import load_story_prompt_context


@pytest_asyncio.fixture()
async def db_session() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_story_prompt_context_includes_script_content(db_session: AsyncSession) -> None:
    user_id = f"story-context-script-user-{uuid4()}"
    novel = Novel(
        id=f"novel-{uuid4()}",
        user_id=user_id,
        title="雾港邮局",
        genre="悬疑",
        description="角色：沈砚。道具：铜铃。",
    )
    chapter = Chapter(
        id=f"chapter-{uuid4()}",
        novel_id=novel.id,
        user_id=user_id,
        title="第一章 夜色来信",
        content="沈砚收到一封没有署名的信。",
        chapter_number=1,
        word_count=100,
        status="completed",
    )
    script = Script(
        id=f"script-{uuid4()}",
        user_id=user_id,
        novel_id=novel.id,
        title="旧邮局场景剧本",
        description="主角追查一封来自旧邮局的密信。",
        content="角色：沈砚。场景：旧邮局。道具：铜铃。沈砚在旧邮局听见铜铃声。",
        extra_data={"chapter_id": chapter.id},
        status="completed",
    )
    db_session.add_all([novel, chapter, script])
    await db_session.flush()

    context = await load_story_prompt_context(db_session, user_id, script_id=script.id)

    assert context["novel_id"] == novel.id
    assert context["chapter_id"] == chapter.id
    assert context["script_id"] == script.id
    assert context["script_title"] == "旧邮局场景剧本"
    assert "旧邮局" in context["script_summary"]
    assert any(scene["name"] == "旧邮局" for scene in context["scenes"])
