import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import series_run_worker as worker


@pytest.mark.asyncio
async def test_process_one_acks_when_lock_not_acquired(monkeypatch):
    redis = AsyncMock()
    payload = {"run_id": "r1", "user_id": "u1", "enqueued_at": "t", "attempt": 1}
    raw = json.dumps(payload)
    redis.blmove = AsyncMock(return_value=raw)
    redis.lrem = AsyncMock(return_value=1)
    monkeypatch.setattr(worker, "acquire_run_lock", AsyncMock(return_value=None))
    executed = AsyncMock()
    monkeypatch.setattr(worker, "_execute_run", executed)
    assert await worker.process_one(redis, worker_id="w1") is True
    executed.assert_not_awaited()
    redis.lrem.assert_awaited()


@pytest.mark.asyncio
async def test_process_one_returns_false_on_empty_queue(monkeypatch):
    redis = AsyncMock()
    redis.blmove = AsyncMock(return_value=None)
    assert await worker.process_one(redis, worker_id="w1") is False


@pytest.mark.asyncio
async def test_process_one_executes_and_releases(monkeypatch):
    redis = AsyncMock()
    payload = {"run_id": "r2", "user_id": "u2", "enqueued_at": "t", "attempt": 1}
    raw = json.dumps(payload)
    redis.blmove = AsyncMock(return_value=raw)
    redis.lrem = AsyncMock(return_value=1)
    monkeypatch.setattr(worker, "acquire_run_lock", AsyncMock(return_value="lease-1"))
    release = AsyncMock()
    monkeypatch.setattr(worker, "release_run_lock", release)
    executed = AsyncMock()
    monkeypatch.setattr(worker, "_execute_run", executed)
    assert await worker.process_one(redis, worker_id="w1") is True
    executed.assert_awaited_once()
    release.assert_awaited_once_with("r2", "w1", "lease-1")
    redis.lrem.assert_awaited()
