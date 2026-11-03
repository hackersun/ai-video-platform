import json

import pytest

from app.services import publication_pipeline_queue as queue


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

    async def lpush(self, key, *values):
        bucket = self.lists.setdefault(key, [])
        for value in values:
            bucket.insert(0, value)
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

    monkeypatch.setenv("PUBLICATION_PIPELINE_QUEUE_BACKEND", "redis")
    monkeypatch.setenv("REDIS_URL", "redis://test/0")
    monkeypatch.setattr(queue, "get_redis", _get_redis)
    return client


def test_key_prefix_stable():
    assert queue.KEY_PREFIX == "avp:publication_pipeline:"
    assert queue.queue_key() == "avp:publication_pipeline:queue"
    assert queue.lock_key("p1") == "avp:publication_pipeline:lock:p1"


@pytest.mark.asyncio
async def test_start_single_flight(fake_redis):
    assert await queue.start_publication_pipeline_execution("pipe-1", "user-1") is True
    assert len(fake_redis.lists[queue.queue_key()]) == 1
    # Simulate active lock
    await fake_redis.set(queue.lock_key("pipe-1"), "w:token", ex=120)
    assert await queue.start_publication_pipeline_execution("pipe-1", "user-1") is False
    assert len(fake_redis.lists[queue.queue_key()]) == 1


@pytest.mark.asyncio
async def test_reclaim_stale_processing(fake_redis):
    payload = {
        "pipeline_id": "pipe-2",
        "user_id": "u",
        "enqueued_at": "t",
        "attempt": 1,
    }
    raw = json.dumps(payload)
    await fake_redis.lpush(queue.processing_key(), raw)
    reclaimed = await queue.reclaim_stale_processing(fake_redis)
    assert reclaimed == 1
    assert fake_redis.lists.get(queue.processing_key(), []) == []
    assert len(fake_redis.lists[queue.queue_key()]) == 1
    body = json.loads(fake_redis.lists[queue.queue_key()][0])
    assert body["attempt"] == 2
