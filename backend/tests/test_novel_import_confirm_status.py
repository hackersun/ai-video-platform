import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  register all tables
from app.core.database import Base
from app.models import Novel, NovelImportJob
from app.api.v1.endpoints.novels import NovelImportConfirmRequest, confirm_import_novel


@pytest_asyncio.fixture()
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_imported_novel_starts_as_draft_and_keeps_chosen_genre(db):
    db.add(NovelImportJob(
        id="job-1", user_id="u1", filename="n.txt", status="previewed", title="雾港", chapter_count=1, word_count=10,
        metadata_json={}, chapters_preview=[{"title": "第一章", "content": "沈砚说：“走。”", "chapter_number": 1}],
    ))
    await db.commit()
    await confirm_import_novel(NovelImportConfirmRequest(job_id="job-1", title="雾港", genre="悬疑", tags=["悬疑"]), db=db, user_id="u1")
    novel = (await db.execute(Novel.__table__.select())).first()
    assert novel.status == "draft"
    assert novel.genre == "悬疑"
