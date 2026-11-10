# Publication Pipeline P1 (Post-Tail Publish Glue) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** After a SeriesProductionRun reaches `completed`, automatically render each episode with `ffmpeg_local`, optionally assemble a whole-book mp4, gate with `publication_readiness`, and create one platform Publication with a final mp4 URL via `POST /api/v1/novels/{novel_id}/publication-pipelines`.

**Architecture:** Introduce a parallel NovelPublicationPipeline FSM (DB-authoritative) plus Redis durable queue `avp:publication_pipeline:*` mirroring series-run worker patterns. P1 only advances from a completed Series Run through episode_rendering → book_assembling → publication_gating → publishing → succeeded. Extract Publication creation into a shared service; reuse `ffmpeg_local_renderer` and `evaluate_publication_readiness`. Fail-closed on Redis, preview packages, and readiness failures.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy async, redis.asyncio, pytest-asyncio, ffmpeg concat demuxer, Docker Compose worker service.

## Global Constraints

- Implement **P1 only** — no Douyin/Bilibili, no billing/G6, no P2 front-to-shots, no P3 quality automation, no P4 commercial gates suite.
- Do **not** change Series Run `ACTIVE_STATES` / `transition_run` +1 rules.
- Redis keys prefix: `avp:publication_pipeline:`; DB is progress authority.
- Fail-closed: missing Redis → HTTP 503; readiness fail → `blocked`, no Publication; preview/`local_artifact_package` never succeeds.
- Idempotency: `(user_id, novel_id, series_plan_version, idempotency_key)` unique; one primary Publication per pipeline; single-flight lock per pipeline_id.
- Default delivery mode: `whole_book_single_mp4`.
- Local commits; push only if tests green.
- Branch: continue `feat/series-run-redis-queue-and-tail-fsm` (or child if cleaner).

## File map

| Path | Role |
|---|---|
| `backend/app/models/publication_pipeline.py` | Pipeline row + unique constraint |
| `backend/app/services/publication_export.py` | Shared create-platform-publication service |
| `backend/app/services/publication_pipeline_render.py` | Episode ffmpeg_local ensure + book concat |
| `backend/app/services/publication_pipeline_orchestrator.py` | Layer-B FSM for P1 stages |
| `backend/app/services/publication_pipeline_queue.py` | Enqueue / lock / reclaim |
| `backend/app/services/publication_pipeline_worker.py` | BLMOVE consumer |
| `backend/app/api/v1/endpoints/publication_pipelines.py` | Create/list/get/pause/resume/cancel |
| `backend/app/api/v1/router.py` | include_router |
| `backend/app/models/__init__.py` | export model |
| `backend/app/db_migrations/runner.py` | register model for create_all |
| `backend/app/api/v1/endpoints/synthesis.py` | Thin wrapper → publication_export |
| `compose.production.yml` | publication-pipeline-worker service |
| `backend/tests/test_publication_pipeline_post_tail_glue.py` | Success / readiness block / idempotency / single-flight |
| `backend/tests/test_publication_pipeline_queue.py` | Queue helpers with FakeRedis |
| `docs/superpowers/plans/2026-11-03-publication-pipeline-p1.md` | This plan |

---

### Task 1: Model + registration

**Files:**
- Create: `backend/app/models/publication_pipeline.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/db_migrations/runner.py`

**Interfaces:**
- Produces: `NovelPublicationPipeline` with fields `id, user_id, novel_id, series_run_id, series_plan_version, idempotency_key, status, stage, publication_id, final_video_url, delivery, media_policy, quality_policy, gates, gate_summary, episodes, blocker_code, blocker_detail, pipeline_metadata, version, created_at, updated_at`
- UniqueConstraint: `user_id, novel_id, series_plan_version, idempotency_key`

- [x] **Step 1: Add model**

```python
"""Persistent state for novel → platform Publication pipelines (P1+)."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint

from app.core.database import Base
from app.core.time_utils import utc_now


class NovelPublicationPipeline(Base):
    __tablename__ = "publication_pipelines"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "novel_id",
            "series_plan_version",
            "idempotency_key",
            name="uq_publication_pipeline_idempotency_scope",
        ),
    )

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    novel_id = Column(String(36), ForeignKey("novels.id", ondelete="CASCADE"), nullable=False, index=True)
    series_run_id = Column(String(36), ForeignKey("series_production_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    series_plan_version = Column(String(100), nullable=False)
    idempotency_key = Column(String(200), nullable=False)
    status = Column(String(30), nullable=False, default="queued", index=True)
    stage = Column(String(40), nullable=False, default="accepted", index=True)
    publication_id = Column(String(36), nullable=True, index=True)
    final_video_url = Column(Text, nullable=True)
    delivery = Column(JSON, nullable=False, default=dict)
    media_policy = Column(JSON, nullable=False, default=dict)
    quality_policy = Column(JSON, nullable=False, default=dict)
    gates = Column(JSON, nullable=False, default=dict)
    gate_summary = Column(JSON, nullable=False, default=dict)
    episodes = Column(JSON, nullable=False, default=list)
    blocker_code = Column(String(80), nullable=True)
    blocker_detail = Column(Text, nullable=True)
    pipeline_metadata = Column("metadata", JSON, nullable=False, default=dict)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    __mapper_args__ = {
        "version_id_col": version,
        "version_id_generator": lambda current: (current or 0) + 1,
    }
```

- [x] **Step 2: Register in models/__init__.py and db_migrations/runner.register_production_models**

- [x] **Step 3: Commit** `feat(publication-pipeline): add NovelPublicationPipeline model`

---

### Task 2: Publication export service (extract from synthesis)

**Files:**
- Create: `backend/app/services/publication_export.py`
- Modify: `backend/app/api/v1/endpoints/synthesis.py` (publish_export calls service)
- Test: covered by Task 6

**Interfaces:**
- Produces: `async def create_platform_publication(db, *, user_id, title, video_url, synthesis_job_id=None, project_id=None, visibility="private", status="published", extra_data=None, metadata=None, allow_preview_export=False) -> Publication`
- Fail-closed: if `evaluate_publication_readiness` not publishable and not allow_preview → raise `PublicationNotReadyError`
- Writes local export artifact + Publication row; stamps metadata with pipeline_id/series_run_id when provided

- [x] **Step 1: Implement service with readiness gate (no preview success for pipeline callers)**
- [x] **Step 2: Refactor `publish_export` to call service (preserve preview-export escape hatch for manual API)**
- [x] **Step 3: Commit** `feat(publication): extract create_platform_publication service`

---

### Task 3: Episode render + book assemble helpers

**Files:**
- Create: `backend/app/services/publication_pipeline_render.py`

**Interfaces:**
- `async def ensure_episode_ffmpeg_local(db, *, user_id, workflow_id, force=False) -> dict` returns `{workflow_id, synthesis_job_id, render_status, render_backend, output_url}`
  - Skip if already `render_status=rendered` + `render_backend=ffmpeg_local` + `is_final_video_url`
  - Else load segments from synthesis `extra_data` (`segments` or nested render manifest); call `ffmpeg_local_renderer.render_workflow_package`; persist job fields
  - Missing inputs → raise `PipelineRenderBlocked("episode_render_inputs_missing")`
- `async def assemble_whole_book_mp4(episode_output_urls: list[str], *, output_dir: Path, book_id: str) -> str`
  - One URL → return as-is; else ffmpeg concat demuxer → `/static/exports/book-{id}.mp4` URL

- [x] **Step 1: Implement helpers**
- [x] **Step 2: Commit** `feat(publication-pipeline): add episode render and book assemble helpers`

---

### Task 4: Orchestrator FSM (P1 stages)

**Files:**
- Create: `backend/app/services/publication_pipeline_orchestrator.py`

**Interfaces:**
- Stages (forward only): `accepted → episode_rendering → book_assembling → publication_gating → publishing → succeeded`
- Side: `paused | blocked | failed | cancelled`
- `async def bind_completed_series_run(db, pipeline) -> SeriesProductionRun | None`
- `async def execute(db, pipeline, *, should_stop=None) -> NovelPublicationPipeline`
- On `series_run_not_completed` → `blocked`
- On readiness fail → `blocked` / `publication_not_ready`, no Publication insert
- On success: set `final_video_url`, `publication_id`, `status=succeeded`
- Record `gate_summary` keys: `stage_timings`, `series_run_ref`, `episode_render_refs`, `publication_ref`, `queue`

- [x] **Step 1: Implement transition helpers + execute**
- [x] **Step 2: Commit** `feat(publication-pipeline): add P1 post-tail orchestrator`

---

### Task 5: Redis queue + worker + compose

**Files:**
- Create: `backend/app/services/publication_pipeline_queue.py`
- Create: `backend/app/services/publication_pipeline_worker.py`
- Modify: `compose.production.yml`
- Test: `backend/tests/test_publication_pipeline_queue.py`

**Interfaces:**
- Keys: `avp:publication_pipeline:queue|processing|lock:{id}|heartbeat:{id}|pause:{id}`
- Same TTL/reclaim/attempt semantics as series_run (120/60/300, reclaim 15s, max 25)
- `start_publication_pipeline_execution(pipeline_id, user_id) -> bool`
- Worker runs `PublicationPipelineOrchestrator().execute`

- [x] **Step 1: Queue + FakeRedis tests**
- [x] **Step 2: Worker `__main__`**
- [x] **Step 3: Add `publication-pipeline-worker` to compose (mirror series-run-worker)**
- [x] **Step 4: Commit** `feat(publication-pipeline): add Redis queue and worker`

---

### Task 6: API endpoints

**Files:**
- Create: `backend/app/api/v1/endpoints/publication_pipelines.py`
- Modify: `backend/app/api/v1/router.py`

**Interfaces:**
- `POST /novels/{novel_id}/publication-pipelines` → 202
  - Reject body keys suggesting external platforms (`douyin`, `bilibili`, …) with 400
  - Resolve series_run_id (explicit or unique completed run for plan version)
  - Idempotent create; enqueue if runnable; if run not completed → persist `blocked`/`series_run_not_completed` without enqueue
  - Redis errors → 503
- `GET /publication-pipelines/{pipeline_id}`
- `GET /novels/{novel_id}/publication-pipelines`
- `POST .../pause|resume|cancel`

- [x] **Step 1: Implement endpoint + router include**
- [x] **Step 2: Commit** `feat(publication-pipeline): add publication-pipelines API`

---

### Task 7: Contract tests + green commit

**Files:**
- Create: `backend/tests/test_publication_pipeline_post_tail_glue.py`
- Create: `backend/tests/test_publication_pipeline_queue.py`

**Cases:**
1. Completed run + already-rendered episode URLs → orchestrator succeeds with publication_id + final_video_url
2. Preview package / non-rendered → blocked, zero Publication rows
3. Same idempotency_key → same pipeline_id, single Publication
4. Queue single-flight: second start returns False while lock held
5. External platform field on create → 400 (API unit with TestClient if fixtures allow; else pure validator test)

- [x] **Step 1: Write tests (mock ffmpeg/assemble where needed)**
- [x] **Step 2: Run** `cd backend && ./venv/bin/pytest tests/test_publication_pipeline_*.py -v`
- [x] **Step 3: Commit** `test(publication-pipeline): cover P1 post-tail glue and queue`
- [x] **Step 4: If green, push branch**

---

## Self-review

1. Spec P1 §12.1 / §13 covered by Tasks 1–7.
2. No Douyin, billing, P2–P4 automation in scope.
3. ACTIVE_STATES untouched.
4. Fail-closed readiness + Redis + preview rejection tested.

## Execution

Inline execution in this session (executor subagent): implement tasks in order, run focused pytest, commit locally, push if green.
