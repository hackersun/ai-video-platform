# Series Run Redis Queue and Tail FSM Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace in-process Series Run `_tasks` with a Redis-backed durable queue + worker, and close the Run FSM tail `media_running → evaluating → completed` only when real media succeeds and the quality gate passes (Submission completed must never imply Run completed).

**Architecture:** API `execute-async` enqueues JSON jobs to Redis (`avp:series_run:*` keys) under `REDIS_URL`. A dedicated `series-run-worker` process consumes via `BLMOVE`, acquires a per-`run_id` lock, runs `SeriesRunOrchestrator.execute`, and cooperates with pause via DB status + Redis pause signal. Media generation calls a new idempotent `close_media_tail` after Submission updates so quality-fail/incomplete paths land in `blocked`/`failed` without forging Run `completed`.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy async, `redis[hiredis]>=5.0.0` (asyncio client), pytest/pytest-asyncio, Docker Compose (`compose.production.yml`).

## Global Constraints

- Keep `POST /series-runs/{run_id}/execute-async` 202 semantics and `execution_status` ∈ {`queued`, `already_running`, `not_required`}.
- Do not change `ACTIVE_STATES` / `RECOVERY_STATES` contents or `transition_run` forward +1 rule.
- Redis keys must use prefix `avp:series_run:`; DB remains progress authority.
- Fail-closed on Redis: no silent fallback to in-process `asyncio.Task` in production (`SERIES_RUN_QUEUE_BACKEND=redis` default; missing `REDIS_URL` fails closed).
- Lock TTL 120s with ~30s heartbeat refresh; heartbeat key TTL 60s; pause signal TTL 300s; reclaim every 15s; dead-letter after attempt > 25 into `run_metadata.queue_dead_letter` without auto-`failed`.
- Do not expand into Seedance six-evidence, billing/G6, or large `series_runs.py` splits.
- Prefer existing code style; TDD where practical; commit locally; do not push/PR unless asked.
- Work only under the local repo / feature branch for this slice.

## File map

| Path | Role |
|---|---|
| `backend/app/core/redis_client.py` | Async Redis factory from `REDIS_URL`, key prefix helpers |
| `backend/app/services/series_run_execution_queue.py` | Rewrite: enqueue / active / pause signal / reclaim helpers; export same public names |
| `backend/app/services/series_run_worker.py` | New: consumer loop + reclaim coroutine + `__main__` |
| `backend/app/services/series_run_orchestrator.py` | Pause checkpoints in `build_episodes`; add `close_media_tail` + pure gate helpers |
| `backend/app/features/series_anchor_generation/generation.py` | After media/quality path, call tail closer; return `run_status` |
| `backend/app/api/v1/endpoints/series_runs.py` | Pause sets Redis pause signal; propagate Redis enqueue errors as HTTP 503 |
| `backend/requirements.txt` | Add `redis[hiredis]>=5.0.0` |
| `compose.production.yml` | Add `series-run-worker` service |
| `backend/tests/test_series_run_execution_queue.py` | Queue/single-flight/reclaim/pause |
| `backend/tests/test_series_run_media_tail_fsm.py` | Tail FSM honesty |
| `backend/tests/test_series_run_orchestrator.py` | Pause checkpoint + illegal jump still fails |
| `backend/tests/test_production_deployment_contract.py` | Worker service + REDIS_URL |

---

### Task 1: Redis client + dependency

**Files:**
- Create: `backend/app/core/redis_client.py`
- Modify: `backend/requirements.txt`
- Test: `backend/tests/test_series_run_redis_client.py`

**Interfaces:**
- Produces: `get_redis_url() -> str`, `async def get_redis() -> redis.asyncio.Redis`, `KEY_PREFIX = "avp:series_run:"`, `queue_key()`, `processing_key()`, `lock_key(run_id)`, `heartbeat_key(run_id)`, `pause_key(run_id)`

- [x] **Step 1: Write the failing test**

```python
# backend/tests/test_series_run_redis_client.py
import os
import pytest

from app.core import redis_client


def test_key_helpers_use_stable_prefix(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    assert redis_client.KEY_PREFIX == "avp:series_run:"
    assert redis_client.queue_key() == "avp:series_run:queue"
    assert redis_client.processing_key() == "avp:series_run:processing"
    assert redis_client.lock_key("run-1") == "avp:series_run:lock:run-1"
    assert redis_client.heartbeat_key("run-1") == "avp:series_run:heartbeat:run-1"
    assert redis_client.pause_key("run-1") == "avp:series_run:pause:run-1"


def test_get_redis_url_fail_closed_when_missing(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    with pytest.raises(RuntimeError, match="REDIS_URL"):
        redis_client.get_redis_url()
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd backend && ./venv/bin/pytest tests/test_series_run_redis_client.py -v`
Expected: FAIL with import error / module missing.

- [x] **Step 3: Add dependency and implement client**

Append to `backend/requirements.txt`:

```
redis[hiredis]>=5.0.0
```

```python
# backend/app/core/redis_client.py
"""Async Redis helpers for Series Run durable queue."""

from __future__ import annotations

import os
from functools import lru_cache

from redis.asyncio import Redis

KEY_PREFIX = "avp:series_run:"


def get_redis_url() -> str:
    url = (os.getenv("REDIS_URL") or "").strip()
    if not url:
        raise RuntimeError("REDIS_URL is required for Series Run queue backend")
    return url


def queue_key() -> str:
    return f"{KEY_PREFIX}queue"


def processing_key() -> str:
    return f"{KEY_PREFIX}processing"


def lock_key(run_id: str) -> str:
    return f"{KEY_PREFIX}lock:{run_id}"


def heartbeat_key(run_id: str) -> str:
    return f"{KEY_PREFIX}heartbeat:{run_id}"


def pause_key(run_id: str) -> str:
    return f"{KEY_PREFIX}pause:{run_id}"


@lru_cache(maxsize=1)
def _client_for(url: str) -> Redis:
    return Redis.from_url(url, decode_responses=True)


async def get_redis() -> Redis:
    return _client_for(get_redis_url())


def reset_redis_client_cache() -> None:
    _client_for.cache_clear()


__all__ = [
    "KEY_PREFIX",
    "get_redis",
    "get_redis_url",
    "heartbeat_key",
    "lock_key",
    "pause_key",
    "processing_key",
    "queue_key",
    "reset_redis_client_cache",
]
```

Install: `./venv/bin/pip install 'redis[hiredis]>=5.0.0'`

- [x] **Step 4: Run test to verify it passes**

Run: `cd backend && ./venv/bin/pytest tests/test_series_run_redis_client.py -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add backend/requirements.txt backend/app/core/redis_client.py backend/tests/test_series_run_redis_client.py
git commit -m "$(cat <<'EOF'
feat(series-run): add Redis client helpers and redis dependency

EOF
)"
```

---

### Task 2: Rewrite execution queue (enqueue / active / pause / reclaim)

**Files:**
- Modify: `backend/app/services/series_run_execution_queue.py`
- Test: `backend/tests/test_series_run_execution_queue.py`

**Interfaces:**
- Consumes: redis_client key helpers; optional injected Redis-like object
- Produces: `start_series_run_execution(run_id, user_id) -> bool` (async-capable sync wrapper that schedules enqueue OR async `await enqueue_series_run_execution`); keep sync signature used by endpoint if possible by using `asyncio.get_event_loop().create_task` only for memory backend tests — **preferred:** make `start_series_run_execution` async and update the endpoint to `await` it (minimal endpoint change allowed by spec).
- Also: `series_run_execution_active(run_id) -> bool` (async preferred: `await`), `signal_series_run_pause(run_id)`, `reclaim_stale_processing(redis)`, constants for TTLs.

Because the current endpoint calls sync `start_series_run_execution`, convert both queue functions to **async** and update the one call site in `series_runs.py` (Task 5 can also do endpoint wiring; for Task 2 keep queue module async and temporarily wrap if needed). Plan decision: **async API** `async def start_series_run_execution` / `async def series_run_execution_active` / `async def signal_series_run_pause`.

- [x] **Step 1: Write failing queue tests with in-memory fake Redis**

```python
# backend/tests/test_series_run_execution_queue.py
import json
import pytest

from app.services import series_run_execution_queue as queue


class FakeRedis:
    def __init__(self):
        self.lists = {}
        self.kv = {}

    async def exists(self, key):
        return 1 if key in self.kv else 0

    async def get(self, key):
        return self.kv.get(key)

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.kv:
            return False
        self.kv[key] = value
        return True

    async def delete(self, *keys):
        for key in keys:
            self.kv.pop(key, None)
        return len(keys)

    async def lpush(self, key, *values):
        self.lists.setdefault(key, [])
        for value in reversed(values):
            self.lists[key].insert(0, value)
        return len(self.lists[key])

    async def rpush(self, key, *values):
        bucket = self.lists.setdefault(key, [])
        bucket.extend(values)
        return len(bucket)

    async def lrange(self, key, start, end):
        data = self.lists.get(key, [])
        if end == -1:
            end = len(data) - 1
        return data[start:end + 1]

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
    monkeypatch.setenv("SERIES_RUN_QUEUE_BACKEND", "redis")
    monkeypatch.setenv("REDIS_URL", "redis://test/0")
    monkeypatch.setattr(queue, "get_redis", lambda: _awaitable(client))
    return client


async def _awaitable(value):
    return value


@pytest.mark.asyncio
async def test_enqueue_returns_true_and_pushes_payload(fake_redis):
    ok = await queue.start_series_run_execution("run-1", "user-1")
    assert ok is True
    items = await fake_redis.lrange(queue.QUEUE_KEY, 0, -1)
    assert len(items) == 1
    payload = json.loads(items[0])
    assert payload["run_id"] == "run-1"
    assert payload["user_id"] == "user-1"
    assert payload["attempt"] == 1
    assert "enqueued_at" in payload


@pytest.mark.asyncio
async def test_enqueue_single_flight_when_lock_present(fake_redis):
    await fake_redis.set(queue.lock_key("run-1"), "worker:token", ex=120)
    assert await queue.start_series_run_execution("run-1", "user-1") is False
    assert await queue.series_run_execution_active("run-1") is True


@pytest.mark.asyncio
async def test_reclaim_moves_stale_processing_back_to_queue(fake_redis):
    payload = json.dumps({
        "run_id": "run-2", "user_id": "u", "enqueued_at": "2026-11-03T00:00:00+08:00", "attempt": 1,
    })
    await fake_redis.rpush(queue.PROCESSING_KEY, payload)
    reclaimed = await queue.reclaim_stale_processing(fake_redis)
    assert reclaimed == 1
    items = await fake_redis.lrange(queue.QUEUE_KEY, 0, -1)
    assert json.loads(items[0])["attempt"] == 2
    assert await fake_redis.lrange(queue.PROCESSING_KEY, 0, -1) == []


@pytest.mark.asyncio
async def test_signal_pause_sets_ttl_key(fake_redis):
    await queue.signal_series_run_pause("run-9")
    assert await fake_redis.get(queue.pause_key("run-9")) == "1"
```

- [x] **Step 2: Run tests — expect FAIL** (old module still uses `_tasks`)

Run: `cd backend && ./venv/bin/pytest tests/test_series_run_execution_queue.py -v`

- [x] **Step 3: Rewrite queue module**

Implement `backend/app/services/series_run_execution_queue.py` with:

- Constants: `LOCK_TTL_SECONDS=120`, `HEARTBEAT_TTL_SECONDS=60`, `PAUSE_TTL_SECONDS=300`, `MAX_ATTEMPTS=25`, `QUEUE_KEY`/`PROCESSING_KEY` aliases from redis_client
- `async def start_series_run_execution(run_id, user_id) -> bool`: if lock or fresh heartbeat → False; else LPUSH JSON; return True. On Redis errors, re-raise (endpoint maps to 503 later).
- `async def series_run_execution_active(run_id) -> bool`: lock exists OR heartbeat exists
- `async def signal_series_run_pause(run_id) -> None`
- `async def refresh_execution_heartbeat(run_id, *, worker_id, lease_token) -> None` (SET heartbeat + EXPIRE lock)
- `async def acquire_run_lock(run_id, worker_id, lease_token) -> bool`
- `async def release_run_lock(run_id, worker_id, lease_token) -> None` (compare-and-del)
- `async def reclaim_stale_processing(redis) -> int` per spec (no lock + missing/expired heartbeat → attempt+=1, LPUSH queue, LREM processing; attempt>25 → dead letter metadata helper optional in worker)
- Support `SERIES_RUN_QUEUE_BACKEND=memory` using module-level structures **only for unit tests**, never as production default when Redis missing.

Remove `_tasks` entirely.

- [x] **Step 4: Make tests pass** (adjust FakeRedis helpers if needed so `get_redis` monkeypatch returns the fake)

- [x] **Step 5: Commit**

```bash
git add backend/app/services/series_run_execution_queue.py backend/tests/test_series_run_execution_queue.py
git commit -m "$(cat <<'EOF'
feat(series-run): replace in-process tasks with Redis execution queue

EOF
)"
```

---

### Task 3: Worker process

**Files:**
- Create: `backend/app/services/series_run_worker.py`
- Test: `backend/tests/test_series_run_worker.py`

**Interfaces:**
- Consumes: queue lock/heartbeat/reclaim; `SeriesRunOrchestrator.execute`; `AsyncSessionLocal`
- Produces: `async def process_one(redis, worker_id) -> bool`, `async def run_worker(stop_event)`, `main()`

- [x] **Step 1: Failing test — lock failure acks without execute; pause skips**

```python
# backend/tests/test_series_run_worker.py
import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services import series_run_worker as worker


@pytest.mark.asyncio
async def test_process_one_acks_when_lock_not_acquired(monkeypatch):
    redis = AsyncMock()
    payload = {"run_id": "r1", "user_id": "u1", "enqueued_at": "t", "attempt": 1}
    redis.blmove = AsyncMock(return_value=json.dumps(payload))
    monkeypatch.setattr(worker, "acquire_run_lock", AsyncMock(return_value=False))
    rem = AsyncMock(return_value=1)
    redis.lrem = rem
    executed = AsyncMock()
    monkeypatch.setattr(worker, "_execute_run", executed)
    assert await worker.process_one(redis, worker_id="w1") is True
    executed.assert_not_awaited()
    rem.assert_awaited()
```

- [x] **Step 2: Run — FAIL (module missing)**

- [x] **Step 3: Implement worker**

Behavior:
1. `BLMOVE queue LEFT processing RIGHT` with timeout 5s
2. Parse JSON; `acquire_run_lock`; on failure `LREM processing` and return
3. Open DB; load run by id+user; if missing or status in `{shots_ready, completed, paused}` → ack+unlock
4. Else `SeriesRunOrchestrator().execute`; always ack+unlock in `finally`
5. Background reclaim every 15s
6. SIGTERM/SIGINT set stop event; exit after current job boundary
7. `if __name__ == "__main__": asyncio.run(main())` so `python -m app.services.series_run_worker` works (ensure package runnable; may need empty path — module under `app.services` is fine when cwd=`backend`)

- [x] **Step 4: Tests pass**

- [x] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(series-run): add Redis-backed series-run-worker consumer

EOF
)"
```

---

### Task 4: Compose worker + deployment contract

**Files:**
- Modify: `compose.production.yml`
- Modify: `backend/tests/test_production_deployment_contract.py`

- [x] **Step 1: Update test expectations first**

Change service set to include `series-run-worker`. Add assertions:

```python
assert set(services) == {"proxy", "frontend", "api", "postgres", "redis", "series-run-worker"}
worker = services["series-run-worker"]
assert worker["command"] == ["python", "-m", "app.services.series_run_worker"]
assert worker["environment"]["REDIS_URL"] == "redis://redis:6379/0"
assert worker["environment"]["DATABASE_URL"].startswith("postgresql://")
assert "redis" in worker["depends_on"]
assert "postgres" in worker["depends_on"]
assert "healthcheck" in worker
# private — no ports
assert not worker.get("ports")
```

Also keep redis AOF assertion (`--appendonly yes` already present via command).

- [x] **Step 2: Run test — FAIL**

- [x] **Step 3: Add compose service** mirroring api env/volumes (media + tmp), `restart: unless-stopped`, healthcheck via python ping redis + `SELECT 1` or simpler redis PING + import check:

```yaml
  series-run-worker:
    build: ./backend
    restart: unless-stopped
    command: ["python", "-m", "app.services.series_run_worker"]
    environment:
      DATABASE_URL: postgresql://ai_video:${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}@postgres:5432/ai_video_platform
      REDIS_URL: redis://redis:6379/0
      DEV_MODE: "false"
      MODEL_CENTER_READ_MODE: canonical
      SERIES_STAGE_MODEL_TIMEOUT_SECONDS: ${SERIES_STAGE_MODEL_TIMEOUT_SECONDS:-90}
      JWT_SECRET_KEY: ${JWT_SECRET_KEY:?JWT_SECRET_KEY is required}
      FERNET_KEY: ${FERNET_KEY:?FERNET_KEY is required}
      VOLCENGINE_API_KEY: ${VOLCENGINE_API_KEY:-}
      OPENAI_API_KEY: ${OPENAI_API_KEY:-}
    volumes:
      - ${AI_VIDEO_DATA_ROOT:-/srv/ai-video-platform/data}/media:/app/static
      - ${AI_VIDEO_RUNTIME_ROOT:-/srv/ai-video-platform/runtime}/api-tmp:/tmp/ai-video-platform
      - ${AI_VIDEO_FONT_ROOT:-/usr/share/fonts/opentype/noto}:/usr/share/fonts/opentype/noto:ro
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import os,redis; redis.from_url(os.environ['REDIS_URL']).ping()"]
      interval: 15s
      timeout: 5s
      retries: 12
      start_period: 20s
```

Update the loop that asserts no ports for private services to include `series-run-worker`.

- [x] **Step 4: Tests pass**

- [x] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
chore(deploy): add series-run-worker to production compose

EOF
)"
```

---

### Task 5: Wire execute-async / pause to async queue + HTTP 503

**Files:**
- Modify: `backend/app/api/v1/endpoints/series_runs.py`
- Modify: `backend/tests/test_series_run_orchestrator.py` (keep execute-async mock contract)

- [x] **Step 1: Adjust existing execute-async test if signature becomes async**

Existing test patches `start_series_run_execution` — ensure AsyncMock if awaited.

- [x] **Step 2: Update endpoint**

```python
@router.post("/series-runs/{run_id}/execute-async")
async def execute_series_run_async(...):
    run = await _owned_run(db, user_id, run_id)
    if run.status in {"shots_ready", "anchor_ready", "completed", "paused"}:
        queued = False
    else:
        try:
            queued = await start_series_run_execution(run.id, user_id)
        except Exception as error:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="series run queue unavailable") from error
    active = await series_run_execution_active(run.id) if not queued else False
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            **_payload(run),
            "execution_status": "queued" if queued else "already_running" if active else "not_required",
        },
    )
```

Pause endpoint after successful commit:

```python
await signal_series_run_pause(run_id)
```

(catch Redis errors: log warning; DB pause remains authoritative)

- [x] **Step 3: Run** `pytest tests/test_series_run_orchestrator.py::test_execute_async_returns_immediately_and_queues_owned_run -v`

- [x] **Step 4: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(series-run): await Redis enqueue and signal pause from API

EOF
)"
```

---

### Task 6: Orchestrator pause checkpoints

**Files:**
- Modify: `backend/app/services/series_run_orchestrator.py`
- Modify: `backend/tests/test_series_run_orchestrator.py`

**Interfaces:**
- Produces: pause check helper used inside `build_episodes` between stages

- [x] **Step 1: Failing test**

```python
@pytest.mark.asyncio
async def test_build_episodes_stops_at_stage_boundary_when_paused(db_session, monkeypatch):
    run = # create episodes_building run with one episode stage created
    calls = []
    async def builder(db, run, episode, stage):
        calls.append(stage)
        if stage == "workflow_ready":
            run.status = "paused"
            await db.commit()
        return {"workflow_id": "wf-1"}
    orch = SeriesRunOrchestrator(stage_builder=builder)
    result = await orch.build_episodes(db_session, run)
    assert "script_ready" not in calls
    assert result.status == "paused"
```

(Adapt to real test fixtures used in `test_series_run_orchestrator.py`.)

- [x] **Step 2: Implement** — after each successful stage commit, `await db.refresh(run)`; if `run.status == "paused"` return run early. Also optionally accept `pause_checker: Callable[[str], Awaitable[bool]]` injected by worker that reads Redis pause key; if True, treat as pause stop without requiring DB already paused (DB is still authority for durable pause; Redis is acceleration — worker should refresh run from DB). Worker sets nothing into orchestrator beyond DB; orchestrator reads DB. Worker may also call a small `async def should_stop(run_id)` before each stage via optional callback:

```python
class SeriesRunOrchestrator:
    def __init__(self, stage_builder=..., should_stop: Callable[[], Awaitable[bool]] | None = None):
        self._should_stop = should_stop
```

In loop: if `self._should_stop and await self._should_stop(): return run`.

- [x] **Step 3: Tests pass; illegal `media_running→completed` still raises**

- [x] **Step 4: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(series-run): honor pause at episode stage boundaries

EOF
)"
```

---

### Task 7: `close_media_tail` + quality gate pure helpers

**Files:**
- Modify: `backend/app/services/series_run_orchestrator.py`
- Create tests in `backend/tests/test_series_run_media_tail_fsm.py`

**Interfaces:**
- Produces:
  - `real_media_success(jobs_by_shot: dict[str, MediaGenerationJob], selected: list[str]) -> bool`
  - `quality_gate_passed(run, selected, jobs_by_shot) -> tuple[bool, str | None]`  # (ok, blocker_code)
  - `SeriesRunOrchestrator.close_media_tail(db, run, *, selected_shot_ids, submission_id, quality_results=None, media_failed=False) -> SeriesProductionRun`

Rules from spec §8.2–8.3:
- media success: each selected shot has active job status in `{succeeded, completed}` with artifact id (`extra_data.artifact_id` or URL fallback)
- quality pass: every selected artifact has `run_metadata.anchor_quality_reports[artifact_id].ready is True`
- unevaluated / ready false → blocked with `quality_gate_incomplete`
- media_failed → failed
- success → evaluating then completed (two commits), write `gate_summary.media_tail`
- idempotent: already completed → no-op; status evaluating + gate still pass → only completed

- [x] **Step 1: Write failing FSM tests**

```python
@pytest.mark.asyncio
async def test_close_media_tail_completes_when_quality_ready(db_session):
    ...
    await SeriesRunOrchestrator().close_media_tail(db_session, run, selected_shot_ids=["s1"], submission_id="sub-1")
    assert run.status == "completed"
    assert (run.gate_summary or {}).get("media_tail", {}).get("result") == "passed"


@pytest.mark.asyncio
async def test_submission_completed_without_quality_does_not_complete_run(db_session):
    # run stays media_running; close_media_tail with unevaluated reports → blocked
    ...
    assert run.status == "blocked"
    assert run.status != "completed"


@pytest.mark.asyncio
async def test_media_failure_marks_run_failed(db_session):
    await SeriesRunOrchestrator().close_media_tail(..., media_failed=True)
    assert run.status == "failed"


@pytest.mark.asyncio
async def test_close_media_tail_resumes_from_evaluating(db_session):
    run.status = "evaluating"
    ...
    await SeriesRunOrchestrator().close_media_tail(...)
    assert run.status == "completed"
```

- [x] **Step 2: Implement helpers + `close_media_tail`**

- [x] **Step 3: Tests pass**

- [x] **Step 4: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(series-run): close media tail FSM with honest quality gate

EOF
)"
```

---

### Task 8: Wire `generate_selected` to tail closer; return `run_status`

**Files:**
- Modify: `backend/app/features/series_anchor_generation/generation.py`
- Extend: `backend/tests/test_series_run_media_tail_fsm.py` (or generation-focused test)

- [x] **Step 1: Failing test — after generate_selected with unevaluated quality, response includes run_status blocked/media_running and submission completed**

Use existing generation test patterns / lightweight monkeypatches for media batch + jobs.

- [x] **Step 2: In `generate_selected`**

After media batch failure commit → call `close_media_tail(..., media_failed=True)` then re-raise or return with `run_status`.

After quality evaluation + submission completed commit:
```python
await SeriesRunOrchestrator().close_media_tail(
    db, run, selected_shot_ids=selected, submission_id=submission.id, quality_results=quality,
)
await db.refresh(run)
response = {**response, "run_status": run.status}
return response
```

For pending provider path, include `run_status` without closing.

Ensure Submission commit happens **before** tail close attempt so tests can observe Submission completed + Run not completed if close blocked (close itself transitions run).

- [x] **Step 3: Tests pass**

- [x] **Step 4: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(series-run): wire generate-selected to media tail closure

EOF
)"
```

---

### Task 9: Spec + plan docs on branch + verification suite

**Files:**
- Add: `docs/superpowers/specs/2026-11-03-series-run-redis-queue-and-tail-fsm-design.md` (already present untracked)
- Add: this plan file
- Run focused pytest modules

- [x] **Step 1: Run verification**

```bash
cd backend && ./venv/bin/pytest \
  tests/test_series_run_redis_client.py \
  tests/test_series_run_execution_queue.py \
  tests/test_series_run_worker.py \
  tests/test_series_run_media_tail_fsm.py \
  tests/test_production_deployment_contract.py \
  tests/test_series_run_orchestrator.py \
  -v --tb=short
```

- [x] **Step 2: Commit docs if not already**

```bash
git add docs/superpowers/specs/2026-11-03-series-run-redis-queue-and-tail-fsm-design.md \
        docs/superpowers/plans/2026-11-03-series-run-redis-queue-and-tail-fsm.md
git commit -m "$(cat <<'EOF'
docs(series-run): add Redis queue and tail FSM spec and plan

EOF
)"
```

- [x] **Step 3: Self-review checklist**
  - Spec §5–§8 covered by Tasks 2–8
  - No Seedance/billing/endpoint mega-split
  - `_tasks` gone
  - compose includes worker
  - Submission ≠ Run completed tested

---

## Self-review (plan author)

1. **Spec coverage:** Queue/single-flight/reclaim/pause/worker/compose/tail FSM/503/execute-async contract — mapped to Tasks 1–8. Manual §11 scripts left as operator steps (not CI).
2. **Placeholders:** None intentional; FakeRedis and fixture details may need adapting to local test helpers during execution — implementer must inspect `tests/conftest.py` and existing orchestrator fixtures before copying blindly.
3. **Type consistency:** Async queue API; endpoint awaits; worker uses same lock helpers.

## Execution note

User already approved implementation after design. Prefer **inline executing-plans** on branch `feat/series-run-redis-queue-and-tail-fsm` (local commits only; no push/PR unless requested).
