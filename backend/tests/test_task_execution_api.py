from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.core.database import Base, get_db
from app.core.security import get_current_user_id
from app.features.task_execution.api import router
from app.models.task_execution import TaskExecution


@pytest.fixture()
def task_api(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'tasks.db'}")
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    current_user = {"id": "user-1"}

    async def setup() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as db:
            db.add_all(
                [
                    TaskExecution(
                        id="task-pending",
                        user_id="user-1",
                        task_type="shot_image.poll",
                        idempotency_key="pending",
                        payload={"api_key": "must-not-leak", "shot_id": "shot-1"},
                    ),
                    TaskExecution(
                        id="task-uncertain",
                        user_id="user-1",
                        task_type="series_run.execute",
                        idempotency_key="uncertain",
                        payload={"run_id": "run-1"},
                        status="needs_attention",
                        last_error_message="任务状态不确定，请人工确认",
                    ),
                    TaskExecution(
                        id="other-user-task",
                        user_id="user-2",
                        task_type="series_run.execute",
                        idempotency_key="private",
                        payload={"run_id": "run-private"},
                    ),
                ]
            )
            await db.commit()

    async def override_db():
        async with factory() as db:
            yield db

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_id] = lambda: current_user["id"]
    asyncio.run(setup())
    with TestClient(app) as client:
        yield client, current_user
    asyncio.run(engine.dispose())


def test_list_and_detail_are_user_scoped_and_do_not_expose_payload(task_api) -> None:
    client, current_user = task_api
    response = client.get("/api/v1/task-executions")
    assert response.status_code == 200
    assert {item["id"] for item in response.json()["items"]} == {"task-pending", "task-uncertain"}
    assert all("payload" not in item for item in response.json()["items"])
    assert response.json()["items"][0]["status_label"] in {"等待执行", "需要人工确认"}

    current_user["id"] = "user-2"
    assert client.get("/api/v1/task-executions/task-pending").status_code == 404


def test_cancel_pending_task_returns_chinese_action_state(task_api) -> None:
    client, _current_user = task_api
    response = client.post("/api/v1/task-executions/task-pending/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert response.json()["status_label"] == "已取消"
    assert response.json()["can_cancel"] is False


def test_uncertain_task_requires_explicit_confirmation_before_retry(task_api) -> None:
    client, _current_user = task_api
    blocked = client.post(
        "/api/v1/task-executions/task-uncertain/retry",
        json={"confirm_uncertain": False},
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "请先确认供应商没有重复受理，再手动重试"

    retried = client.post(
        "/api/v1/task-executions/task-uncertain/retry",
        json={"confirm_uncertain": True},
    )
    assert retried.status_code == 200
    assert retried.json()["status"] == "pending"
    assert retried.json()["status_label"] == "等待执行"
