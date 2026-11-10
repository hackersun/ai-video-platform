"""Dead-letter terminal state for publication pipelines."""

from __future__ import annotations

import json
from types import SimpleNamespace

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

    monkeypatch.setenv("PUBLICATION_PIPELINE_QUEUE_BACKEND", "redis")
    monkeypatch.setenv("REDIS_URL", "redis://test/0")
    monkeypatch.setattr(queue, "get_redis", _get_redis)
    return client


@pytest.mark.asyncio
async def test_publication_reclaim_requeues_dead_letter(fake_redis):
    payload = json.dumps({
        "pipeline_id": "p-dl",
        "user_id": "u",
        "enqueued_at": "2026-11-10T00:00:00+08:00",
        "attempt": queue.MAX_ATTEMPTS,
    })
    await fake_redis.rpush(queue.processing_key(), payload)
    assert await queue.reclaim_stale_processing(fake_redis) == 0
    items = await fake_redis.lrange(queue.queue_key(), 0, -1)
    body = json.loads(items[0])
    assert body["attempt"] == queue.MAX_ATTEMPTS + 1
    assert body.get("dead_letter") is True


@pytest.mark.asyncio
async def test_publication_record_dead_letter_marks_failed():
    class _DB:
        def __init__(self):
            self.committed = False

        async def commit(self):
            self.committed = True

    pipeline = SimpleNamespace(
        status="running",
        pipeline_metadata={},
        gate_summary={},
        blocker_code=None,
        blocker_detail=None,
    )
    db = _DB()
    await queue.record_queue_dead_letter(db, pipeline, attempt=26, reason="max_attempts")
    assert db.committed is True
    assert pipeline.status == "failed"
    assert pipeline.blocker_code == "queue_dead_letter"
    assert "重试" in pipeline.blocker_detail
    assert pipeline.gate_summary["blocker_code"] == "queue_dead_letter"
