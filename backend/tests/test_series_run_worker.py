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


@pytest.mark.asyncio
async def test_execute_run_refreshes_heartbeat_on_timer(monkeypatch):
    """Long execute without stage-boundary should_stop must still refresh the lease."""
    from types import SimpleNamespace

    refresh_calls: list[tuple] = []

    async def fake_refresh(run_id, *, worker_id, lease_token):
        refresh_calls.append((run_id, worker_id, lease_token))

    class _ScalarResult:
        def __init__(self, value):
            self._value = value

        def scalar_one_or_none(self):
            return self._value

    class _DB:
        async def scalar(self, _stmt):
            return SimpleNamespace(id="r-hb", user_id="u1", status="episodes_building")

        async def refresh(self, _obj):
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    class _SessionCM:
        async def __aenter__(self):
            return _DB()

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(worker, "AsyncSessionLocal", lambda: _SessionCM())
    monkeypatch.setattr(worker, "refresh_execution_heartbeat", fake_refresh)
    monkeypatch.setattr(worker, "HEARTBEAT_REFRESH_INTERVAL_SECONDS", 0.05)
    monkeypatch.setattr(worker, "pause_signal_present", AsyncMock(return_value=False))

    async def slow_execute(db, run):
        # Stay inside execute longer than one refresh interval without calling should_stop.
        import asyncio as _aio
        await _aio.sleep(0.18)

    class _Orch:
        def __init__(self, should_stop=None):
            self.should_stop = should_stop

        async def execute(self, db, run):
            await slow_execute(db, run)

    monkeypatch.setattr(worker, "SeriesRunOrchestrator", _Orch)
    await worker._execute_run("r-hb", "u1", worker_id="w-hb", lease_token="lease-hb")
    assert len(refresh_calls) >= 2, refresh_calls
    assert all(c == ("r-hb", "w-hb", "lease-hb") for c in refresh_calls)


@pytest.mark.asyncio
async def test_process_one_dead_letters_marks_failed(monkeypatch):
    """attempt > MAX must persist failed + queue_dead_letter blocker, not leave running."""
    from types import SimpleNamespace

    redis = AsyncMock()
    payload = {"run_id": "r-dl", "user_id": "u-dl", "enqueued_at": "t", "attempt": worker.MAX_ATTEMPTS + 1}
    raw = json.dumps(payload)
    redis.blmove = AsyncMock(return_value=raw)
    redis.lrem = AsyncMock(return_value=1)
    monkeypatch.setattr(worker, "acquire_run_lock", AsyncMock(return_value="lease-dl"))
    monkeypatch.setattr(worker, "release_run_lock", AsyncMock())
    executed = AsyncMock()
    monkeypatch.setattr(worker, "_execute_run", executed)

    recorded = {}

    async def fake_record(db, run, *, attempt, reason):
        recorded["attempt"] = attempt
        recorded["reason"] = reason
        recorded["run_id"] = run.id
        run.status = "failed"

    monkeypatch.setattr(worker, "record_queue_dead_letter", fake_record)

    run_obj = SimpleNamespace(id="r-dl", user_id="u-dl", status="episodes_building")

    class _DB:
        async def scalar(self, _stmt):
            return run_obj

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    class _SessionCM:
        async def __aenter__(self):
            return _DB()

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(worker, "AsyncSessionLocal", lambda: _SessionCM())
    assert await worker.process_one(redis, worker_id="w-dl") is True
    executed.assert_not_awaited()
    assert recorded == {"attempt": worker.MAX_ATTEMPTS + 1, "reason": "max_attempts", "run_id": "r-dl"}

