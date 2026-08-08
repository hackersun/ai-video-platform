from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.database import Base
from app.features.task_execution.shot_image_handler import (
    enqueue_shot_image_poll,
    handle_shot_image_poll,
)
from app.models.asset import Asset
from app.models.shot import Shot
from app.models.task_execution import TaskExecution


@pytest_asyncio.fixture()
async def factory(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr("app.features.task_execution.shot_image_handler.AsyncSessionLocal", session_factory)
    yield session_factory
    await engine.dispose()


async def _seed_shot(factory) -> None:
    async with factory() as db:
        db.add(
            Shot(
                id="shot-1",
                storyboard_id="storyboard-1",
                user_id="user-1",
                shot_number=1,
                image_status="generating",
                extra_data={"image_generation_prompt": "仙侠主角立于云海"},
            )
        )
        await db.commit()


def _execution() -> TaskExecution:
    return TaskExecution(
        id="execution-1",
        user_id="user-1",
        task_type="shot_image.poll",
        idempotency_key="shot-1:provider-task-1",
        provider_task_id="provider-task-1",
        payload={"shot_id": "shot-1", "provider_task_id": "provider-task-1"},
    )


@pytest.mark.asyncio
async def test_shot_image_poll_submission_is_idempotent(factory) -> None:
    async with factory() as db:
        first, created = await enqueue_shot_image_poll(
            db, shot_id="shot-1", provider_task_id="provider-task-1", user_id="user-1"
        )
        second, duplicate = await enqueue_shot_image_poll(
            db, shot_id="shot-1", provider_task_id="provider-task-1", user_id="user-1"
        )
        await db.commit()

    assert created is True and duplicate is False
    assert first.id == second.id
    assert first.max_attempts == 60


@pytest.mark.asyncio
async def test_pending_provider_status_is_a_safe_poll_retry(factory, monkeypatch) -> None:
    await _seed_shot(factory)

    async def pending(*_args):
        return {"status": "processing"}

    monkeypatch.setattr("app.services.image_poll_service.load_shot_image_status", pending)
    outcome = await handle_shot_image_poll(_execution())

    assert outcome.status == "retry_wait"
    assert outcome.error_code == "provider_pending"
    assert outcome.message == "供应商仍在生成参考图，稍后继续查询"


@pytest.mark.asyncio
async def test_successful_poll_persists_one_asset_even_if_handler_replays(factory, monkeypatch) -> None:
    await _seed_shot(factory)

    async def succeeded(*_args):
        return {"status": "succeeded", "image_url": "https://provider.example/image.png"}

    async def persist(url, **_kwargs):
        assert url == "https://provider.example/image.png"
        return "/static/generated/images/shot-1.png"

    monkeypatch.setattr("app.services.image_poll_service.load_shot_image_status", succeeded)
    monkeypatch.setattr("app.services.media_persistence.persist_remote_media_url", persist)

    first = await handle_shot_image_poll(_execution())
    second = await handle_shot_image_poll(_execution())

    async with factory() as db:
        shot = await db.get(Shot, "shot-1")
        asset_count = await db.scalar(select(func.count()).select_from(Asset))
    assert first.status == second.status == "succeeded"
    assert shot.image_url == "/static/generated/images/shot-1.png"
    assert asset_count == 1


@pytest.mark.asyncio
async def test_failed_provider_status_marks_shot_failed(factory, monkeypatch) -> None:
    await _seed_shot(factory)

    async def failed(*_args):
        return {"status": "failed"}

    monkeypatch.setattr("app.services.image_poll_service.load_shot_image_status", failed)
    outcome = await handle_shot_image_poll(_execution())

    async with factory() as db:
        shot = await db.get(Shot, "shot-1")
    assert outcome.status == "failed"
    assert outcome.message == "供应商返回参考图生成失败"
    assert shot.image_status == "failed"


@pytest.mark.asyncio
async def test_poll_exhaustion_stops_automatic_retry_with_chinese_message(factory, monkeypatch) -> None:
    await _seed_shot(factory)

    async def pending(*_args):
        return {"status": "processing"}

    execution = _execution()
    execution.attempt_count = execution.max_attempts = 60
    monkeypatch.setattr("app.services.image_poll_service.load_shot_image_status", pending)
    outcome = await handle_shot_image_poll(execution)

    async with factory() as db:
        shot = await db.get(Shot, "shot-1")
    assert outcome.status == "dead_letter"
    assert outcome.message == "参考图生成等待超时，请检查供应商任务后手动重试"
    assert shot.image_status == "failed"
