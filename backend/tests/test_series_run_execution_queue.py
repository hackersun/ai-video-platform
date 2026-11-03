import json

import pytest

from app.core import redis_client
from app.services import series_run_execution_queue as queue


class FakeRedis:
    def __init__(self):
        self.lists: dict[str, list[str]] = {}
        self.kv: dict[str, str] = {}

    async def exists(self, key):
        return 1 if key in self.kv else 0

    async def get(self, key):
        return self.kv.get(key)

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.kv:
            return False
        self.kv[key] = str(value)
        return True

    async def delete(self, *keys):
        removed = 0
        for key in keys:
            if key in self.kv:
                self.kv.pop(key, None)
                removed += 1
        return removed

    async def expire(self, key, ttl):
        return 1 if key in self.kv else 0

    async def lpush(self, key, *values):
        bucket = self.lists.setdefault(key, [])
        for value in values:
            bucket.insert(0, value)
        return len(bucket)

    async def rpush(self, key, *values):
        bucket = self.lists.setdefault(key, [])
        bucket.extend(values)
        return len(bucket)

    async def lrange(self, key, start, end):
        data = list(self.lists.get(key, []))
        if end == -1:
            end = len(data) - 1
        return data[start : end + 1]

    async def lrem(self, key, count, value):
        data = self.lists.get(key, [])
        removed = 0
        out = []
        for item in data:
            if item == value and (count == 0 or removed < abs(count)):
                removed += 1
                continue
            out.append(item)
        self.lists[key] = out
        return removed


@pytest.fixture
def fake_redis(monkeypatch):
    client = FakeRedis()

    async def _get_redis():
        return client

    monkeypatch.setenv("SERIES_RUN_QUEUE_BACKEND", "redis")
    monkeypatch.setenv("REDIS_URL", "redis://test/0")
    monkeypatch.setattr(queue, "get_redis", _get_redis)
    return client


@pytest.mark.asyncio
async def test_enqueue_returns_true_and_pushes_payload(fake_redis):
    ok = await queue.start_series_run_execution("run-1", "user-1")
    assert ok is True
    items = await fake_redis.lrange(redis_client.queue_key(), 0, -1)
    assert len(items) == 1
    payload = json.loads(items[0])
    assert payload["run_id"] == "run-1"
    assert payload["user_id"] == "user-1"
    assert payload["attempt"] == 1
    assert "enqueued_at" in payload


@pytest.mark.asyncio
async def test_enqueue_single_flight_when_lock_present(fake_redis):
    await fake_redis.set(redis_client.lock_key("run-1"), "worker:token", ex=120)
    assert await queue.start_series_run_execution("run-1", "user-1") is False
    assert await queue.series_run_execution_active("run-1") is True


@pytest.mark.asyncio
async def test_enqueue_single_flight_when_heartbeat_present(fake_redis):
    await fake_redis.set(redis_client.heartbeat_key("run-1"), "2026-11-03T14:00:00+08:00", ex=60)
    assert await queue.start_series_run_execution("run-1", "user-1") is False


@pytest.mark.asyncio
async def test_reclaim_moves_stale_processing_back_to_queue(fake_redis):
    payload = json.dumps({
        "run_id": "run-2",
        "user_id": "u",
        "enqueued_at": "2026-11-03T00:00:00+08:00",
        "attempt": 1,
    })
    await fake_redis.rpush(redis_client.processing_key(), payload)
    reclaimed = await queue.reclaim_stale_processing(fake_redis)
    assert reclaimed == 1
    items = await fake_redis.lrange(redis_client.queue_key(), 0, -1)
    assert json.loads(items[0])["attempt"] == 2
    assert await fake_redis.lrange(redis_client.processing_key(), 0, -1) == []


@pytest.mark.asyncio
async def test_reclaim_skips_when_lock_held(fake_redis):
    payload = json.dumps({
        "run_id": "run-3",
        "user_id": "u",
        "enqueued_at": "2026-11-03T00:00:00+08:00",
        "attempt": 1,
    })
    await fake_redis.rpush(redis_client.processing_key(), payload)
    await fake_redis.set(redis_client.lock_key("run-3"), "w:t", ex=120)
    assert await queue.reclaim_stale_processing(fake_redis) == 0
    assert len(await fake_redis.lrange(redis_client.processing_key(), 0, -1)) == 1


@pytest.mark.asyncio
async def test_signal_pause_sets_ttl_key(fake_redis):
    await queue.signal_series_run_pause("run-9")
    assert await fake_redis.get(redis_client.pause_key("run-9")) == "1"
