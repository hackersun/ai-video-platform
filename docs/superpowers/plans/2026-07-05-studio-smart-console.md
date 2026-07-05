# Studio Smart Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a simpler, guided Studio command console so users can start from Novel Management and progress through continuous anime production with clear next actions, confirmations, contextual jumps, and full-flow verification.

**Architecture:** Add lightweight backend guidance contracts instead of hard-coding business decisions in React. The backend exposes novel-level production entry state and workflow-level Studio guidance; the frontend renders a command bar, staged workflow, guided action confirmation, and collapsible expert areas while keeping existing panels and APIs compatible.

**Tech Stack:** FastAPI, async SQLAlchemy, Pydantic, pytest, Next.js 14 App Router, React 18, TypeScript, Tailwind CSS, Radix Dialog, Playwright for browser smoke testing.

---

## Scope And Assumptions

- This plan does not remove existing Producer, Storyboard, Prompt Skills, asset card, or review pages. It makes Studio the main command surface and keeps expert pages reachable through contextual links.
- The first implementation should preserve current URLs: `/novels`, `/novels/[id]`, `/studio`, `/producer`, `/studio/cards`, `/studio/continuity-review`, `/studio/shot-review`.
- Backend response fields are additive. Existing clients that ignore `guidance` and `production_entry` continue to work.
- The UI remains an operational tool: compact, scannable, no landing-page hero, no nested decorative cards.
- `frontend/tsconfig.tsbuildinfo` and generated media/static files are local artifacts and must not be staged.

## Success Criteria

- From `/novels`, every novel card shows one primary production action derived from backend state.
- From `/novels/[id]`, the top area shows a clear route: content -> series plan -> Studio -> draft -> review/export.
- `/studio?workflow_id=...&novel_id=...&chapter_id=...` shows a sticky command bar with current novel, episode, readiness, blockers, mode, and one recommended next action.
- Studio main area shows five production stages: 内容准备, 设定锁定, 本集工程, 草片生产, 复审出片.
- Risky actions show a confirmation dialog with reason, impact scope, expected output, and mode rules.
- Navigation actions preserve `workflow_id`, `novel_id`, `chapter_id`, `shot_id`, and issue/action source where available.
- Existing Studio repair actions still pass: asset locks, contract refresh, quality check, media audit, test bypass.
- Backend tests pass for changed APIs. Frontend `npm run typecheck` passes. Browser smoke test verifies the Novel -> Studio path and Studio guided action UI.

## File Map

### Backend

- Create `backend/app/services/novel_production_entry.py`
  - Computes novel-level production stage, primary action, metrics, and contextual Studio/Quick Start URLs.
- Modify `backend/app/api/v1/endpoints/novels.py`
  - Adds production-entry endpoints before dynamic `/{novel_id}` routes.
- Create `backend/test_novel_production_entry.py`
  - Verifies entry states for no chapters, no series plan, workflow available, and blocker handling.
- Create `backend/app/services/studio_guidance.py`
  - Computes workflow-level guidance stages, recommended action, confirmation copy, and contextual links.
- Modify `backend/app/services/studio_snapshot.py`
  - Injects `guidance` into the existing snapshot response.
- Modify `backend/app/services/studio_actions.py`
  - Adds action metadata needed by confirmation UI without changing existing action execution semantics.
- Modify `backend/test_studio_snapshot.py`
  - Verifies `guidance` is present and consistent with existing issues/actions.
- Modify `backend/test_studio_actions.py`
  - Verifies confirmable/production action metadata and current repair actions.

### Frontend

- Modify `frontend/src/lib/studio-types.ts`
  - Adds `StudioGuidance`, `StudioGuidanceStage`, `StudioGuidedAction`, and `NovelProductionEntry` types.
- Modify `frontend/src/lib/studio-api.ts`
  - Keeps Studio calls typed against the enriched snapshot.
- Modify `frontend/src/lib/api-client.ts`
  - Adds novel production entry methods.
- Create `frontend/src/lib/studio-guidance.ts`
  - Provides fallback guidance helpers when older snapshots do not include backend `guidance`.
- Create `frontend/src/lib/studio-context-links.ts`
  - Builds URLs that preserve workflow, novel, chapter, shot, and source issue context.
- Create `frontend/src/components/novels/novel-production-entry-card.tsx`
  - Renders novel-level production status and primary CTA.
- Modify `frontend/src/app/novels/page.tsx`
  - Loads production entries and replaces scattered production actions with one primary action per novel.
- Modify `frontend/src/app/novels/[id]/page.tsx`
  - Adds top production route and improves series-plan CTA consistency.
- Create `frontend/src/components/studio/studio-command-bar.tsx`
  - Sticky command bar with next action and high-level status.
- Create `frontend/src/components/studio/studio-stage-flow.tsx`
  - Five-stage production stepper.
- Create `frontend/src/components/studio/studio-action-confirmation-dialog.tsx`
  - Confirmation dialog for confirm/production risk actions.
- Create `frontend/src/components/studio/studio-action-progress.tsx`
  - Shows running/succeeded/failed action progress and retry affordances.
- Create `frontend/src/components/studio/studio-expert-sections.tsx`
  - Collapses current detailed panels into tabs/sections.
- Modify `frontend/src/components/studio/studio-shell.tsx`
  - Wires command bar, stage flow, guided action execution, confirmation, progress, and expert sections.
- Modify `frontend/src/components/studio/studio-agent-panel.tsx`
  - Keeps issue details but defers the main recommendation to the command bar.
- Modify `frontend/src/components/studio/studio-issue-card.tsx`
  - Passes through source issue context and uses confirmation where needed.
- Modify `frontend/src/app/studio/continuity-review/page.tsx`
  - Reads query filters and preserves return context to Studio.
- Modify `frontend/src/app/studio/shot-review/page.tsx`
  - Highlights deep-linked shot and shows passed repair note when present.
- Add `frontend/e2e/studio-smart-console.spec.ts`
  - Browser smoke coverage for Novel -> Studio entry and Studio guided UI.
- Modify `frontend/package.json`
  - Adds `e2e` script and Playwright dev dependency if no local test harness exists.

---

## Task 1: Backend Novel Production Entry Contract

**Files:**
- Create: `backend/app/services/novel_production_entry.py`
- Modify: `backend/app/api/v1/endpoints/novels.py`
- Modify: `frontend/src/lib/api-client.ts`
- Modify: `frontend/src/lib/studio-types.ts`
- Test: `backend/test_novel_production_entry.py`

- [ ] **Step 1: Write failing backend tests**

Add `backend/test_novel_production_entry.py`:

```python
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from init_db import init_db
from main import app
from test_short_video_production import _auth_headers, _create_short_video_fixture


@pytest.fixture(scope="module", autouse=True)
def _init_database() -> None:
    init_db()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DEV_MODE", "true")
    return TestClient(app)


def _create_novel(client: TestClient, user_id: str, title: str = "入口测试小说") -> str:
    response = client.post(
        "/api/v1/novels",
        json={"title": title, "description": "入口测试", "genre": "悬疑"},
        headers=_auth_headers(user_id),
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_novel_production_entry_no_chapters_points_to_content_prepare(client: TestClient) -> None:
    user_id = f"novel-entry-no-chapters-{uuid4()}"
    novel_id = _create_novel(client, user_id)

    response = client.get(f"/api/v1/novels/{novel_id}/production-entry", headers=_auth_headers(user_id))

    assert response.status_code == 200
    payload = response.json()
    assert payload["novel_id"] == novel_id
    assert payload["stage"] == "content_prepare"
    assert payload["primary_action"]["code"] == "open_chapters"
    assert payload["primary_action"]["href"] == f"/novels/{novel_id}?tab=chapters"
    assert payload["metrics"]["chapter_count"] == 0


def test_novel_production_entry_with_fixture_points_to_studio(client: TestClient) -> None:
    user_id = f"novel-entry-studio-{uuid4()}"
    fixture = _create_short_video_fixture(client, user_id)

    response = client.get(
        f"/api/v1/novels/{fixture['novel_id']}/production-entry",
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["stage"] in {"studio_fix", "studio_ready"}
    assert payload["primary_action"]["code"] == "open_studio"
    assert f"workflow_id={fixture['workflow_id']}" in payload["primary_action"]["href"]
    assert payload["metrics"]["workflow_count"] >= 1


def test_novel_production_entries_batch_returns_map(client: TestClient) -> None:
    user_id = f"novel-entry-batch-{uuid4()}"
    first_id = _create_novel(client, user_id, "批量入口 A")
    second_id = _create_novel(client, user_id, "批量入口 B")

    response = client.get(
        "/api/v1/novels/production-entries",
        params={"novel_ids": f"{first_id},{second_id}"},
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 2
    assert payload["entries"][first_id]["stage"] == "content_prepare"
    assert payload["entries"][second_id]["stage"] == "content_prepare"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd backend
pytest test_novel_production_entry.py -q
```

Expected: failures for missing routes or missing `production_entry` service.

- [ ] **Step 3: Implement novel production entry service**

Create `backend/app/services/novel_production_entry.py`:

```python
"""Novel-level production entry guidance for the Studio command console."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chapter, Novel, Workflow
from app.services.series_production import get_series_plan


def _query_params(params: Dict[str, Optional[str]]) -> str:
    pairs = [(key, value) for key, value in params.items() if value]
    return "&".join(f"{key}={value}" for key, value in pairs)


def _action(code: str, label: str, href: str, description: str, risk: str = "navigation") -> Dict[str, Any]:
    return {
        "code": code,
        "label": label,
        "href": href,
        "description": description,
        "risk": risk,
    }


async def _chapter_count(db: AsyncSession, user_id: str, novel_id: str) -> int:
    result = await db.execute(select(Chapter.id).where(Chapter.user_id == user_id, Chapter.novel_id == novel_id))
    return len(result.scalars().all())


async def _latest_workflow(db: AsyncSession, user_id: str, novel_id: str) -> Optional[Workflow]:
    result = await db.execute(
        select(Workflow)
        .where(Workflow.user_id == user_id, Workflow.novel_id == novel_id)
        .order_by(desc(Workflow.updated_at), desc(Workflow.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _workflow_count(db: AsyncSession, user_id: str, novel_id: str) -> int:
    result = await db.execute(select(Workflow.id).where(Workflow.user_id == user_id, Workflow.novel_id == novel_id))
    return len(result.scalars().all())


async def build_novel_production_entry(db: AsyncSession, user_id: str, novel_id: str) -> Dict[str, Any]:
    novel = await db.get(Novel, novel_id)
    if novel is None or novel.user_id != user_id:
        return {
            "novel_id": novel_id,
            "stage": "not_found",
            "label": "小说不存在",
            "description": "无法读取该小说的制作入口。",
            "primary_action": _action("open_novels", "返回小说管理", "/novels", "回到小说管理列表。"),
            "metrics": {},
        }

    chapter_count = await _chapter_count(db, user_id, novel_id)
    plan = await get_series_plan(db, user_id, novel_id)
    episodes = plan.get("episodes") if isinstance(plan, dict) else []
    latest_workflow = await _latest_workflow(db, user_id, novel_id)
    workflow_count = await _workflow_count(db, user_id, novel_id)

    metrics = {
        "chapter_count": chapter_count,
        "episode_count": len(episodes or []),
        "workflow_count": workflow_count,
    }

    if chapter_count <= 0:
        return {
            "novel_id": novel_id,
            "stage": "content_prepare",
            "label": "待补章节",
            "description": "先导入或拆分章节，再生成整书多集计划。",
            "primary_action": _action("open_chapters", "补齐章节", f"/novels/{novel_id}?tab=chapters", "进入小说章节管理。"),
            "metrics": metrics,
        }

    if not episodes:
        return {
            "novel_id": novel_id,
            "stage": "series_plan",
            "label": "待生成整书计划",
            "description": "已有章节，下一步生成多集制作计划。",
            "primary_action": _action("open_series_plan", "生成整书计划", f"/novels/{novel_id}?tab=series-plan", "进入整书生产计划。"),
            "metrics": metrics,
        }

    if latest_workflow is None:
        return {
            "novel_id": novel_id,
            "stage": "workflow_create",
            "label": "待创建本集工程",
            "description": "整书计划已就绪，下一步创建或继续第一个本集工程。",
            "primary_action": _action("open_series_plan", "创建本集工程", f"/novels/{novel_id}?tab=series-plan", "在多集计划中创建本集工程。"),
            "metrics": metrics,
        }

    params = _query_params({
        "workflow_id": latest_workflow.id,
        "novel_id": novel_id,
        "chapter_id": latest_workflow.chapter_id,
    })
    return {
        "novel_id": novel_id,
        "stage": "studio_fix" if latest_workflow.status != "completed" else "studio_ready",
        "label": "进入工作室",
        "description": "本集工程已创建，进入 Studio 按推荐步骤处理。",
        "primary_action": _action("open_studio", "继续制作", f"/studio?{params}", "带小说、章节和工作流上下文进入工作室。"),
        "metrics": metrics,
        "workflow_id": latest_workflow.id,
        "chapter_id": latest_workflow.chapter_id,
    }


async def build_novel_production_entries(
    db: AsyncSession,
    user_id: str,
    novel_ids: Iterable[str],
) -> Dict[str, Any]:
    entries: Dict[str, Dict[str, Any]] = {}
    for novel_id in [value for value in novel_ids if value]:
        entries[novel_id] = await build_novel_production_entry(db, user_id, novel_id)
    return {"entries": entries, "count": len(entries)}
```

- [ ] **Step 4: Add novel entry routes before dynamic routes**

Modify `backend/app/api/v1/endpoints/novels.py` imports:

```python
from app.services.novel_production_entry import build_novel_production_entries, build_novel_production_entry
```

Add these routes before `@router.get("/{novel_id}"...)`:

```python
@router.get("/production-entries", response_model=dict)
async def read_novel_production_entries(
    novel_ids: str = Query("", description="逗号分隔的小说 ID 列表"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    ids = [item.strip() for item in novel_ids.split(",") if item.strip()]
    return await build_novel_production_entries(db, user_id, ids)


@router.get("/{novel_id}/production-entry", response_model=dict)
async def read_novel_production_entry(
    novel_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return await build_novel_production_entry(db, user_id, novel_id)
```

- [ ] **Step 5: Add frontend types and API methods**

In `frontend/src/lib/studio-types.ts`, add:

```ts
export type StudioActionRisk = 'safe' | 'navigation' | 'confirm' | 'production' | string;

export type StudioGuidedAction = StudioAction & {
  description?: string;
  reason?: string;
  scope?: string[];
  expected_outputs?: string[];
  confirmation?: {
    required?: boolean;
    title?: string;
    description?: string;
    impact?: string[];
    confirm_label?: string;
  };
  params?: Record<string, any>;
  source_issue_code?: string | null;
};

export type NovelProductionEntry = {
  novel_id: string;
  stage: 'content_prepare' | 'series_plan' | 'workflow_create' | 'studio_fix' | 'studio_ready' | 'not_found' | string;
  label: string;
  description: string;
  primary_action: StudioGuidedAction;
  metrics?: {
    chapter_count?: number;
    episode_count?: number;
    workflow_count?: number;
  };
  workflow_id?: string | null;
  chapter_id?: string | null;
};
```

In `frontend/src/lib/api-client.ts`, add:

```ts
async getNovelProductionEntries(novelIds: string[]) {
  const searchParams = new URLSearchParams();
  searchParams.set('novel_ids', novelIds.join(','));
  return this.request<{ entries: Record<string, NovelProductionEntry>; count: number }>(
    `/novels/production-entries?${searchParams.toString()}`
  );
}

async getNovelProductionEntry(novelId: string) {
  return this.request<NovelProductionEntry>(`/novels/${novelId}/production-entry`);
}
```

Import `NovelProductionEntry` from `frontend/src/lib/studio-types.ts`.

- [ ] **Step 6: Verify backend and frontend compile**

Run:

```bash
cd backend
pytest test_novel_production_entry.py -q
cd ../frontend
npm run typecheck
```

Expected: pytest passes; typecheck passes.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/novel_production_entry.py backend/app/api/v1/endpoints/novels.py backend/test_novel_production_entry.py frontend/src/lib/api-client.ts frontend/src/lib/studio-types.ts
git commit -m "feat: add novel production entry guidance"
```

---

## Task 2: Backend Studio Guidance Contract

**Files:**
- Create: `backend/app/services/studio_guidance.py`
- Modify: `backend/app/services/studio_snapshot.py`
- Modify: `backend/app/services/studio_actions.py`
- Test: `backend/test_studio_snapshot.py`
- Test: `backend/test_studio_actions.py`

- [ ] **Step 1: Add failing snapshot guidance tests**

Append to `backend/test_studio_snapshot.py`:

```python
def test_studio_snapshot_includes_guidance_stages_and_next_action(client: TestClient) -> None:
    user_id = f"studio-guidance-user-{uuid4()}"
    fixture = _create_short_video_fixture(client, user_id)

    response = client.get(
        f"/api/v1/studio/workflows/{fixture['workflow_id']}/snapshot",
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    guidance = response.json()["guidance"]
    assert guidance["current_stage"] in {"content", "bible", "episode", "draft", "review"}
    assert [stage["id"] for stage in guidance["stages"]] == ["content", "bible", "episode", "draft", "review"]
    assert guidance["next_action"]["code"]
    assert guidance["next_action"]["reason"]
    assert guidance["next_action"]["risk"] in {"safe", "navigation", "confirm", "production"}
```

Append to `backend/test_studio_actions.py`:

```python
def test_studio_safe_actions_include_confirmation_metadata(client: TestClient) -> None:
    user_id = f"studio-action-meta-user-{uuid4()}"
    fixture = _create_short_video_fixture(client, user_id)

    response = client.post(
        f"/api/v1/studio/workflows/{fixture['workflow_id']}/actions/apply_asset_locks/execute",
        json={"mode": "production"},
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["risk"] == "safe"
    assert payload["result"]["applied_shot_count"] == 3
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd backend
pytest test_studio_snapshot.py::test_studio_snapshot_includes_guidance_stages_and_next_action test_studio_actions.py::test_studio_safe_actions_include_confirmation_metadata -q
```

Expected: guidance test fails because `guidance` is missing.

- [ ] **Step 3: Implement guidance helper**

Create `backend/app/services/studio_guidance.py`:

```python
"""Workflow-level Studio guidance for the smart command console."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _json_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _stage(stage_id: str, label: str, status: str, description: str, action: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "id": stage_id,
        "label": label,
        "status": status,
        "description": description,
        "action": action,
    }


def _guided_action(
    code: str,
    label: str,
    *,
    reason: str,
    risk: str = "safe",
    href: Optional[str] = None,
    scope: Optional[List[str]] = None,
    expected_outputs: Optional[List[str]] = None,
    source_issue_code: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    confirmation_required = risk in {"confirm", "production"}
    return {
        "code": code,
        "label": label,
        "reason": reason,
        "risk": risk,
        "href": href,
        "scope": scope or [],
        "expected_outputs": expected_outputs or [],
        "source_issue_code": source_issue_code,
        "params": params or {},
        "confirmation": {
            "required": confirmation_required,
            "title": label,
            "description": reason,
            "impact": scope or [],
            "confirm_label": "确认执行" if confirmation_required else "执行",
        },
    }


def _issue_by_code(issues: List[Dict[str, Any]], code: str) -> Optional[Dict[str, Any]]:
    return next((issue for issue in issues if issue.get("code") == code), None)


def build_studio_guidance(
    *,
    workflow: Dict[str, Any],
    story_context: Dict[str, Any],
    story_bible: Dict[str, Any],
    production_bible_summary: Dict[str, Any],
    production: Dict[str, Any],
    timeline: Dict[str, Any],
    issues: List[Dict[str, Any]],
    actions: List[Dict[str, Any]],
    mode_policy: Dict[str, Any],
) -> Dict[str, Any]:
    novel = story_context.get("novel") or {}
    chapter = story_context.get("chapter") or {}
    shot_count = int(production.get("shot_count") or 0)
    asset_coverage = float(production.get("asset_lock_coverage") or 0)
    readiness_score = int(production_bible_summary.get("readiness_score") or 0)
    blockers = int(mode_policy.get("blocking_issue_count") or 0)
    has_bible = bool(story_bible.get("id") or production_bible_summary.get("story_bible_id"))
    has_timeline = bool(timeline.get("preview_url") or timeline.get("clip_count"))

    missing_story_bible = _issue_by_code(issues, "missing_story_bible")
    missing_shots = _issue_by_code(issues, "missing_shots")
    missing_locks = _issue_by_code(issues, "missing_asset_locks")

    if not workflow.get("novel_id") or not workflow.get("chapter_id"):
        next_action = _guided_action(
            "open_novel_context",
            "补齐小说和章节",
            reason="工作流缺少小说或章节上下文，无法保证连续制作一致性。",
            risk="navigation",
            href="/workflow",
            scope=["当前工作流"],
            expected_outputs=["绑定小说", "绑定章节"],
        )
        current_stage = "content"
    elif missing_story_bible:
        next_action = _guided_action(
            "open_story_bible",
            "生成 Story Bible",
            reason=missing_story_bible.get("message") or "缺少小说级设定本。",
            risk="navigation",
            href=f"/novels/{workflow.get('novel_id')}?tab=story-bible",
            scope=[str(novel.get("title") or workflow.get("novel_id"))],
            expected_outputs=["风格规则", "角色规则", "场景规则", "道具规则"],
            source_issue_code="missing_story_bible",
        )
        current_stage = "bible"
    elif missing_shots:
        next_action = _guided_action(
            "open_storyboard",
            "生成或编辑分镜镜头",
            reason=missing_shots.get("message") or "缺少镜头，无法生成草片。",
            risk="navigation",
            href="/storyboards",
            scope=[str(chapter.get("title") or workflow.get("chapter_id"))],
            expected_outputs=["分镜", "镜头列表"],
            source_issue_code="missing_shots",
        )
        current_stage = "episode"
    elif missing_locks:
        next_action = _guided_action(
            "apply_asset_locks",
            "应用资产锁",
            reason=missing_locks.get("message") or "镜头缺少资产锁。",
            risk="safe",
            scope=[f"{shot_count} 个镜头", "角色/场景/道具资产"],
            expected_outputs=["镜头资产锁", "生产上下文刷新"],
            source_issue_code="missing_asset_locks",
        )
        current_stage = "episode"
    elif not has_timeline:
        next_action = _guided_action(
            "open_producer",
            "生成本集草片",
            reason="设定与镜头已具备基础条件，下一步进入草片生产。",
            risk="navigation",
            href=f"/producer?workflow_id={workflow.get('id')}",
            scope=[str(chapter.get("title") or "当前章节")],
            expected_outputs=["镜头音视频任务", "可审阅草片"],
        )
        current_stage = "draft"
    elif blockers:
        next_action = _guided_action(
            "create_review",
            "运行出片检查",
            reason="仍存在阻断项，需要复审或修复后再出片。",
            risk="confirm",
            scope=[f"{blockers} 个阻断项"],
            expected_outputs=["复审记录", "修复建议"],
        )
        current_stage = "review"
    else:
        next_action = _guided_action(
            "quality_check",
            "运行质量检查",
            reason="当前工作流没有硬阻断，终稿前执行质量检查。",
            risk="safe",
            scope=["当前工作流", f"{shot_count} 个镜头"],
            expected_outputs=["质量报告", "出片建议"],
        )
        current_stage = "review"

    stages = [
        _stage("content", "内容准备", "ready" if workflow.get("novel_id") and workflow.get("chapter_id") else "blocked", "小说、章节和整书计划上下文。"),
        _stage("bible", "设定锁定", "ready" if has_bible else "blocked", "Story Bible、风格、角色、场景、道具和声线。"),
        _stage("episode", "本集工程", "ready" if shot_count > 0 and asset_coverage >= 1 else "working" if shot_count > 0 else "blocked", "剧本、分镜、镜头、实体引用和资产锁。"),
        _stage("draft", "草片生产", "ready" if has_timeline else "working" if shot_count > 0 else "blocked", "视频、配音、字幕、合成和时间线。"),
        _stage("review", "复审出片", "blocked" if blockers else "ready", "连续性复审、质量检查和成片验证。"),
    ]

    return {
        "readiness_score": readiness_score,
        "current_stage": current_stage,
        "next_action": next_action,
        "stages": stages,
        "blocker_count": blockers,
        "mode": mode_policy.get("mode") or "production",
        "breadcrumbs": {
            "novel_id": workflow.get("novel_id"),
            "chapter_id": workflow.get("chapter_id"),
            "workflow_id": workflow.get("id"),
        },
        "secondary_actions": actions[:6],
    }
```

- [ ] **Step 4: Inject guidance into snapshot**

Modify `backend/app/services/studio_snapshot.py`:

```python
from app.services.studio_guidance import build_studio_guidance
```

Refactor the final return into a `payload` variable and add:

```python
payload["guidance"] = build_studio_guidance(
    workflow=payload["workflow"],
    story_context=payload["story_context"],
    story_bible=payload["story_bible"],
    production_bible_summary=payload["production_bible_summary"] or {},
    production=payload["production"],
    timeline=payload["timeline"],
    issues=payload["issues"],
    actions=payload["actions"],
    mode_policy=payload["mode_policy"],
)
return payload
```

- [ ] **Step 5: Keep action execution compatible**

In `backend/app/services/studio_actions.py`, keep `ACTION_REGISTRY` codes unchanged. Add no new behavior for `apply_asset_locks`, `refresh_contracts`, `quality_check`, or `media_audit` in this task. This task only verifies their returned `risk` values still support the new confirmation rules.

- [ ] **Step 6: Verify backend tests**

Run:

```bash
cd backend
pytest test_studio_snapshot.py test_studio_actions.py -q
```

Expected: all Studio snapshot and action tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/studio_guidance.py backend/app/services/studio_snapshot.py backend/app/services/studio_actions.py backend/test_studio_snapshot.py backend/test_studio_actions.py
git commit -m "feat: add studio workflow guidance contract"
```

---

## Task 3: Frontend Guidance Types And Context Link Helpers

**Files:**
- Modify: `frontend/src/lib/studio-types.ts`
- Create: `frontend/src/lib/studio-guidance.ts`
- Create: `frontend/src/lib/studio-context-links.ts`
- Modify: `frontend/src/lib/studio-api.ts`

- [ ] **Step 1: Extend Studio types**

In `frontend/src/lib/studio-types.ts`, add:

```ts
export type StudioGuidanceStage = {
  id: 'content' | 'bible' | 'episode' | 'draft' | 'review' | string;
  label: string;
  status: 'ready' | 'working' | 'blocked' | string;
  description?: string;
  action?: StudioGuidedAction | null;
};

export type StudioGuidance = {
  readiness_score?: number;
  current_stage?: string;
  next_action?: StudioGuidedAction | null;
  stages?: StudioGuidanceStage[];
  blocker_count?: number;
  mode?: StudioRunMode | string;
  breadcrumbs?: {
    novel_id?: string | null;
    chapter_id?: string | null;
    workflow_id?: string | null;
  };
  secondary_actions?: StudioAction[];
};
```

Add `guidance?: StudioGuidance | null;` to `StudioSnapshot`.

- [ ] **Step 2: Create context link helper**

Create `frontend/src/lib/studio-context-links.ts`:

```ts
import type { StudioSnapshot } from './studio-types';

export function studioContextParams(snapshot: StudioSnapshot | null, extra: Record<string, string | undefined | null> = {}) {
  const params = new URLSearchParams();
  const workflowId = snapshot?.workflow?.id || snapshot?.guidance?.breadcrumbs?.workflow_id || '';
  const novelId = snapshot?.workflow?.novel_id || snapshot?.story_context?.novel?.id || snapshot?.guidance?.breadcrumbs?.novel_id || '';
  const chapterId = snapshot?.workflow?.chapter_id || snapshot?.story_context?.chapter?.id || snapshot?.guidance?.breadcrumbs?.chapter_id || '';
  if (workflowId) params.set('workflow_id', workflowId);
  if (novelId) params.set('novel_id', novelId);
  if (chapterId) params.set('chapter_id', chapterId);
  Object.entries(extra).forEach(([key, value]) => {
    if (value) params.set(key, value);
  });
  return params;
}

export function withStudioContext(path: string, snapshot: StudioSnapshot | null, extra: Record<string, string | undefined | null> = {}) {
  const params = studioContextParams(snapshot, extra);
  const qs = params.toString();
  if (!qs) return path;
  return `${path}${path.includes('?') ? '&' : '?'}${qs}`;
}
```

- [ ] **Step 3: Create fallback guidance helper**

Create `frontend/src/lib/studio-guidance.ts`:

```ts
import type { StudioGuidance, StudioGuidedAction, StudioSnapshot } from './studio-types';

const fallbackStages = [
  { id: 'content', label: '内容准备', status: 'working', description: '小说、章节和整书计划上下文。' },
  { id: 'bible', label: '设定锁定', status: 'working', description: '风格、角色、场景、道具和声线。' },
  { id: 'episode', label: '本集工程', status: 'working', description: '剧本、分镜、镜头和资产锁。' },
  { id: 'draft', label: '草片生产', status: 'working', description: '视频、配音、字幕和合成。' },
  { id: 'review', label: '复审出片', status: 'working', description: '复审、质量检查和成片验证。' },
];

export function getStudioGuidance(snapshot: StudioSnapshot | null): StudioGuidance {
  if (snapshot?.guidance) return snapshot.guidance;
  const issue = snapshot?.issues?.[0];
  const action = issue?.repair_action || snapshot?.actions?.[0] || snapshot?.production_bible_summary?.next_actions?.[0] || null;
  return {
    readiness_score: snapshot?.production_bible_summary?.readiness_score ?? 0,
    blocker_count: snapshot?.mode_policy?.blocking_issue_count ?? snapshot?.issues?.length ?? 0,
    current_stage: 'episode',
    stages: fallbackStages,
    next_action: action
      ? {
          ...action,
          reason: issue?.message || '继续处理当前工作流的下一步。',
          scope: ['当前工作流'],
          expected_outputs: ['刷新工作台状态'],
          confirmation: { required: action.risk === 'confirm' || action.risk === 'production' },
        }
      : null,
    secondary_actions: snapshot?.actions || [],
  };
}

export function getPrimaryGuidedAction(snapshot: StudioSnapshot | null): StudioGuidedAction | null {
  return getStudioGuidance(snapshot).next_action || null;
}

export function requiresConfirmation(action: StudioGuidedAction | null | undefined) {
  return Boolean(action?.confirmation?.required || action?.risk === 'confirm' || action?.risk === 'production');
}
```

- [ ] **Step 4: Typecheck**

Run:

```bash
cd frontend
npm run typecheck
```

Expected: TypeScript passes.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/studio-types.ts frontend/src/lib/studio-guidance.ts frontend/src/lib/studio-context-links.ts frontend/src/lib/studio-api.ts
git commit -m "feat: add studio guidance frontend helpers"
```

---

## Task 4: Novel Management Fast Entry UI

**Files:**
- Create: `frontend/src/components/novels/novel-production-entry-card.tsx`
- Modify: `frontend/src/app/novels/page.tsx`
- Modify: `frontend/src/app/novels/[id]/page.tsx`

- [ ] **Step 1: Create reusable novel entry component**

Create `frontend/src/components/novels/novel-production-entry-card.tsx`:

```tsx
'use client';

import Link from 'next/link';
import { ArrowRight, CheckCircle2, CircleAlert, Film, ListChecks } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type { NovelProductionEntry } from '@/lib/studio-types';

const STAGE_LABELS: Record<string, string> = {
  content_prepare: '内容准备',
  series_plan: '整书计划',
  workflow_create: '本集工程',
  studio_fix: '工作室处理',
  studio_ready: '可继续生产',
  not_found: '不可用',
};

function tone(entry?: NovelProductionEntry | null) {
  if (!entry) return 'border-white/10 bg-white/[0.04] text-white/60';
  if (entry.stage === 'studio_ready') return 'border-emerald-400/25 bg-emerald-500/10 text-emerald-50';
  if (entry.stage === 'studio_fix') return 'border-amber-400/25 bg-amber-500/10 text-amber-50';
  return 'border-cyan-400/20 bg-cyan-500/10 text-cyan-50';
}

export function NovelProductionEntryCard({ entry }: { entry?: NovelProductionEntry | null }) {
  const action = entry?.primary_action;
  return (
    <div className={`rounded-lg border p-3 ${tone(entry)}`}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            {entry?.stage === 'studio_ready' ? <CheckCircle2 className="h-4 w-4" /> : <CircleAlert className="h-4 w-4" />}
            <Badge variant="outline" className="border-current text-current">
              {STAGE_LABELS[entry?.stage || ''] || entry?.label || '制作入口'}
            </Badge>
            {entry?.metrics ? (
              <span className="text-xs text-white/55">
                {entry.metrics.chapter_count || 0} 章 · {entry.metrics.episode_count || 0} 集 · {entry.metrics.workflow_count || 0} 工程
              </span>
            ) : null}
          </div>
          <div className="mt-1 line-clamp-2 text-sm text-white/70">
            {entry?.description || '正在读取制作入口状态'}
          </div>
        </div>
        {action?.href ? (
          <Button asChild size="sm" className="shrink-0 bg-cyan-600 hover:bg-cyan-700">
            <Link href={action.href}>
              {entry?.stage === 'series_plan' ? <ListChecks className="mr-1.5 h-4 w-4" /> : <Film className="mr-1.5 h-4 w-4" />}
              {action.label}
              <ArrowRight className="ml-1.5 h-4 w-4" />
            </Link>
          </Button>
        ) : null}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Wire entries into `/novels` list**

In `frontend/src/app/novels/page.tsx`:

Add imports:

```tsx
import { NovelProductionEntryCard } from '@/components/novels/novel-production-entry-card';
import type { NovelProductionEntry } from '@/lib/studio-types';
```

Add state:

```tsx
const [productionEntries, setProductionEntries] = useState<Record<string, NovelProductionEntry>>({});
```

After converted novels are loaded, call:

```tsx
const ids = convertedNovels.map((item) => item.id);
if (ids.length) {
  apiClient.getNovelProductionEntries(ids)
    .then((response) => setProductionEntries(response.entries || {}))
    .catch(() => setProductionEntries({}));
}
```

Inside each novel card, under the metadata row and before the action icon group, render:

```tsx
<div className="mt-3">
  <NovelProductionEntryCard entry={productionEntries[novel.id]} />
</div>
```

Keep existing view/edit/delete actions as secondary icon actions.

- [ ] **Step 3: Add detail-page production route**

In `frontend/src/app/novels/[id]/page.tsx`, add `productionEntry` state using `apiClient.getNovelProductionEntry(novelId)` in the existing data-loading path. Render `NovelProductionEntryCard` near the top of the detail page, above tabs, so the route is visible regardless of active tab.

Use this exact loading pattern:

```tsx
const [productionEntry, setProductionEntry] = useState<NovelProductionEntry | null>(null);

const loadProductionEntry = async () => {
  try {
    setProductionEntry(await apiClient.getNovelProductionEntry(novelId));
  } catch {
    setProductionEntry(null);
  }
};
```

Call `loadProductionEntry()` after `loadNovelData()` completes and after `handleGenerateSeriesPlan()` or `handleContinueEpisode()` changes production state.

- [ ] **Step 4: Typecheck**

Run:

```bash
cd frontend
npm run typecheck
```

Expected: TypeScript passes.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/novels/novel-production-entry-card.tsx frontend/src/app/novels/page.tsx 'frontend/src/app/novels/[id]/page.tsx'
git commit -m "feat: guide novels into studio production"
```

---

## Task 5: Studio Command Bar And Stage Flow

**Files:**
- Create: `frontend/src/components/studio/studio-command-bar.tsx`
- Create: `frontend/src/components/studio/studio-stage-flow.tsx`
- Modify: `frontend/src/components/studio/studio-shell.tsx`

- [ ] **Step 1: Create command bar component**

Create `frontend/src/components/studio/studio-command-bar.tsx`:

```tsx
'use client';

import { AlertTriangle, CheckCircle2, Gauge, Wand2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type { StudioGuidedAction, StudioRunMode, StudioSnapshot } from '@/lib/studio-types';
import { getStudioGuidance } from '@/lib/studio-guidance';

export function StudioCommandBar({
  snapshot,
  mode,
  loading,
  onPrimaryAction,
}: {
  snapshot: StudioSnapshot | null;
  mode: StudioRunMode;
  loading?: boolean;
  onPrimaryAction: (action: StudioGuidedAction) => void;
}) {
  const guidance = getStudioGuidance(snapshot);
  const action = guidance.next_action || null;
  const novelTitle = snapshot?.story_context?.novel?.title || '未绑定小说';
  const episodeTitle = snapshot?.series_plan?.current_episode?.title || snapshot?.story_context?.chapter?.title || '当前本集';
  const blockers = guidance.blocker_count ?? snapshot?.mode_policy?.blocking_issue_count ?? 0;
  const score = guidance.readiness_score ?? snapshot?.production_bible_summary?.readiness_score ?? 0;

  return (
    <div className="sticky top-3 z-20 rounded-lg border border-cyan-400/20 bg-slate-950/95 p-4 shadow-xl backdrop-blur">
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2 text-sm text-white/70">
            <span className="truncate text-white">{novelTitle}</span>
            <span className="text-white/35">/</span>
            <span className="truncate">{episodeTitle}</span>
            <Badge variant="outline" className="border-white/15 text-white/70">
              {mode === 'production' ? '生产出片' : '测试验证'}
            </Badge>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <span className="inline-flex items-center gap-1.5 text-sm text-white/70">
              <Gauge className="h-4 w-4 text-emerald-300" />
              连续性 {score}%
            </span>
            <span className="inline-flex items-center gap-1.5 text-sm text-white/70">
              {blockers ? <AlertTriangle className="h-4 w-4 text-amber-300" /> : <CheckCircle2 className="h-4 w-4 text-emerald-300" />}
              阻断项 {blockers}
            </span>
            {action?.reason ? <span className="line-clamp-1 text-sm text-white/55">建议：{action.reason}</span> : null}
          </div>
        </div>
        {action ? (
          <Button onClick={() => onPrimaryAction(action)} disabled={loading} className="gap-2 bg-cyan-600 hover:bg-cyan-700">
            <Wand2 className="h-4 w-4" />
            {action.label}
          </Button>
        ) : null}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create stage flow component**

Create `frontend/src/components/studio/studio-stage-flow.tsx`:

```tsx
'use client';

import { CheckCircle2, Circle, CircleAlert } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import type { StudioSnapshot } from '@/lib/studio-types';
import { getStudioGuidance } from '@/lib/studio-guidance';

function iconFor(status?: string) {
  if (status === 'ready') return CheckCircle2;
  if (status === 'blocked') return CircleAlert;
  return Circle;
}

function classFor(status?: string) {
  if (status === 'ready') return 'border-emerald-400/25 bg-emerald-500/10 text-emerald-50';
  if (status === 'blocked') return 'border-red-400/25 bg-red-500/10 text-red-50';
  return 'border-cyan-400/25 bg-cyan-500/10 text-cyan-50';
}

export function StudioStageFlow({ snapshot }: { snapshot: StudioSnapshot | null }) {
  const stages = getStudioGuidance(snapshot).stages || [];
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.04] p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="text-sm font-medium text-white">制作主线</div>
        <Badge variant="outline" className="border-white/15 text-white/60">5 阶段</Badge>
      </div>
      <div className="grid gap-3 md:grid-cols-5">
        {stages.map((stage, index) => {
          const Icon = iconFor(stage.status);
          return (
            <div key={stage.id} className={`rounded-lg border p-3 ${classFor(stage.status)}`}>
              <div className="flex items-center gap-2">
                <Icon className="h-4 w-4 shrink-0" />
                <div className="text-xs text-white/45">0{index + 1}</div>
              </div>
              <div className="mt-2 text-sm font-medium text-white">{stage.label}</div>
              <div className="mt-1 line-clamp-3 text-xs leading-5 text-white/60">{stage.description}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Wire into StudioShell**

Modify `frontend/src/components/studio/studio-shell.tsx`:

Add imports:

```tsx
import { StudioCommandBar } from './studio-command-bar';
import { StudioStageFlow } from './studio-stage-flow';
import { getPrimaryGuidedAction } from '@/lib/studio-guidance';
```

Replace the direct `SeriesOverviewPanel` render with:

```tsx
{activeSnapshot ? (
  <>
    <StudioCommandBar
      snapshot={activeSnapshot}
      mode={mode}
      loading={loading}
      onPrimaryAction={handleGuidedAction}
    />
    <StudioStageFlow snapshot={activeSnapshot} />
  </>
) : null}
```

Add a temporary handler that delegates to the current primary action path:

```tsx
const handleGuidedAction = useCallback((action: StudioAction) => {
  void handlePrimaryAction(action);
}, [handlePrimaryAction]);
```

Update `handlePrimaryAction` signature to accept an optional action:

```tsx
const handlePrimaryAction = useCallback(async (preferredAction?: StudioAction) => {
  const actionCandidates = [
    ...(preferredAction ? [preferredAction] : []),
    ...(activeSnapshot?.actions || []),
    ...(activeSnapshot?.production_bible_summary?.next_actions || []),
  ];
```

- [ ] **Step 4: Typecheck**

Run:

```bash
cd frontend
npm run typecheck
```

Expected: TypeScript passes.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/studio/studio-command-bar.tsx frontend/src/components/studio/studio-stage-flow.tsx frontend/src/components/studio/studio-shell.tsx
git commit -m "feat: add studio command bar and stage flow"
```

---

## Task 6: Guided Action Confirmation And Progress Feedback

**Files:**
- Create: `frontend/src/components/studio/studio-action-confirmation-dialog.tsx`
- Create: `frontend/src/components/studio/studio-action-progress.tsx`
- Modify: `frontend/src/components/studio/studio-shell.tsx`
- Modify: `frontend/src/components/studio/studio-issue-card.tsx`
- Modify: `frontend/src/components/studio/studio-agent-panel.tsx`

- [ ] **Step 1: Create confirmation dialog**

Create `frontend/src/components/studio/studio-action-confirmation-dialog.tsx`:

```tsx
'use client';

import { AlertTriangle, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import type { StudioGuidedAction } from '@/lib/studio-types';

export function StudioActionConfirmationDialog({
  action,
  open,
  loading,
  onOpenChange,
  onConfirm,
}: {
  action: StudioGuidedAction | null;
  open: boolean;
  loading?: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
}) {
  const impact = action?.confirmation?.impact || action?.scope || [];
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-amber-500/10 text-amber-300">
            <AlertTriangle className="h-5 w-5" />
          </div>
          <DialogTitle>{action?.confirmation?.title || action?.label || '确认操作'}</DialogTitle>
          <DialogDescription>{action?.confirmation?.description || action?.reason || '确认执行该操作。'}</DialogDescription>
        </DialogHeader>
        <div className="space-y-3 text-sm text-white/70">
          {impact.length ? (
            <div className="rounded-lg border border-white/10 bg-white/[0.04] p-3">
              <div className="mb-2 font-medium text-white">影响范围</div>
              <ul className="space-y-1">
                {impact.map((item) => <li key={item}>- {item}</li>)}
              </ul>
            </div>
          ) : null}
          {action?.expected_outputs?.length ? (
            <div className="rounded-lg border border-white/10 bg-white/[0.04] p-3">
              <div className="mb-2 font-medium text-white">预期结果</div>
              <ul className="space-y-1">
                {action.expected_outputs.map((item) => <li key={item}>- {item}</li>)}
              </ul>
            </div>
          ) : null}
          {action?.risk === 'production' ? (
            <div className="rounded-lg border border-red-400/25 bg-red-500/10 p-3 text-red-50">
              生产出片操作会执行门禁检查，硬阻断项不能跳过。
            </div>
          ) : null}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={loading}>取消</Button>
          <Button onClick={onConfirm} disabled={loading}>
            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            {loading ? '处理中…' : action?.confirmation?.confirm_label || '确认执行'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 2: Create progress component**

Create `frontend/src/components/studio/studio-action-progress.tsx`:

```tsx
'use client';

import { AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';
import type { StudioActionResult } from '@/lib/studio-types';

export function StudioActionProgress({
  loading,
  lastAction,
  error,
}: {
  loading?: boolean;
  lastAction?: StudioActionResult | null;
  error?: string;
}) {
  if (loading) {
    return (
      <div role="status" className="flex items-center gap-2 rounded-lg border border-cyan-400/20 bg-cyan-500/10 px-4 py-3 text-sm text-cyan-50">
        <Loader2 className="h-4 w-4 animate-spin" />
        正在处理推荐动作，完成后会自动刷新工作台。
      </div>
    );
  }
  if (error) {
    return (
      <div role="alert" className="flex items-center gap-2 rounded-lg border border-red-400/25 bg-red-500/10 px-4 py-3 text-sm text-red-50">
        <AlertCircle className="h-4 w-4" />
        {error}
      </div>
    );
  }
  if (lastAction) {
    return (
      <div role="status" className="flex items-center gap-2 rounded-lg border border-emerald-400/25 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-50">
        <CheckCircle2 className="h-4 w-4" />
        {lastAction.label || lastAction.code}：{lastAction.status || '已完成'}
      </div>
    );
  }
  return null;
}
```

- [ ] **Step 3: Wire confirmation into StudioShell**

In `frontend/src/components/studio/studio-shell.tsx`, add state:

```tsx
const [pendingAction, setPendingAction] = useState<StudioGuidedAction | null>(null);
const [confirmOpen, setConfirmOpen] = useState(false);
```

Add imports:

```tsx
import { StudioActionConfirmationDialog } from './studio-action-confirmation-dialog';
import { StudioActionProgress } from './studio-action-progress';
import { requiresConfirmation } from '@/lib/studio-guidance';
import { withStudioContext } from '@/lib/studio-context-links';
```

Add execution helper:

```tsx
const executeGuidedAction = useCallback(async (action: StudioGuidedAction) => {
  if (action.href || action.risk === 'navigation') {
    router.push(action.href || withStudioContext('/studio/cards', activeSnapshot));
    return;
  }
  if (!workflowId) return;
  setLoading(true);
  setError('');
  try {
    const result = await runStudioAction(workflowId, {
      code: action.code,
      params: action.params,
      mode,
      source_issue_code: action.source_issue_code || undefined,
    });
    setLastAction(result);
    toast({ title: `${result.label || action.label}已执行`, description: '工作台状态已刷新。', type: 'success' });
    await loadSnapshot(workflowId, mode);
  } catch (err: any) {
    setError(err.message || '执行推荐动作失败');
  } finally {
    setLoading(false);
  }
}, [activeSnapshot, loadSnapshot, mode, router, toast, workflowId]);
```

Update `handleGuidedAction`:

```tsx
const handleGuidedAction = useCallback((action: StudioGuidedAction) => {
  if (requiresConfirmation(action)) {
    setPendingAction(action);
    setConfirmOpen(true);
    return;
  }
  void executeGuidedAction(action);
}, [executeGuidedAction]);
```

Render below `StudioStageFlow`:

```tsx
<StudioActionProgress loading={loading} lastAction={lastAction} error={error} />
```

Render dialog near the end of the component:

```tsx
<StudioActionConfirmationDialog
  action={pendingAction}
  open={confirmOpen}
  loading={loading}
  onOpenChange={setConfirmOpen}
  onConfirm={() => {
    if (!pendingAction) return;
    setConfirmOpen(false);
    void executeGuidedAction(pendingAction);
  }}
/>
```

- [ ] **Step 4: Keep issue cards compatible**

Update `StudioIssueCard` props only if it currently assumes `StudioAction`. Accept `StudioGuidedAction` as a subtype by leaving the public prop type as `StudioAction`; no visual change is required in this step.

- [ ] **Step 5: Typecheck**

Run:

```bash
cd frontend
npm run typecheck
```

Expected: TypeScript passes.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/studio/studio-action-confirmation-dialog.tsx frontend/src/components/studio/studio-action-progress.tsx frontend/src/components/studio/studio-shell.tsx frontend/src/components/studio/studio-issue-card.tsx frontend/src/components/studio/studio-agent-panel.tsx
git commit -m "feat: add guided studio action confirmation"
```

---

## Task 7: Collapse Studio Expert Panels Into Scannable Sections

**Files:**
- Create: `frontend/src/components/studio/studio-expert-sections.tsx`
- Modify: `frontend/src/components/studio/studio-shell.tsx`

- [ ] **Step 1: Create expert sections wrapper**

Create `frontend/src/components/studio/studio-expert-sections.tsx`:

```tsx
'use client';

import { ReactNode, useState } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

export function StudioExpertSections({
  overview,
  assets,
  shots,
  review,
  expert,
}: {
  overview: ReactNode;
  assets: ReactNode;
  shots: ReactNode;
  review: ReactNode;
  expert: ReactNode;
}) {
  const [tab, setTab] = useState('overview');
  return (
    <Tabs value={tab} onValueChange={setTab}>
      <TabsList className="h-auto max-w-full flex-wrap justify-start bg-white/5">
        <TabsTrigger value="overview">总览</TabsTrigger>
        <TabsTrigger value="assets">资产声线</TabsTrigger>
        <TabsTrigger value="shots">镜头媒体</TabsTrigger>
        <TabsTrigger value="review">复审出片</TabsTrigger>
        <TabsTrigger value="expert">专家</TabsTrigger>
      </TabsList>
      <TabsContent value="overview" className="mt-4 space-y-5">{overview}</TabsContent>
      <TabsContent value="assets" className="mt-4 space-y-5">{assets}</TabsContent>
      <TabsContent value="shots" className="mt-4 space-y-5">{shots}</TabsContent>
      <TabsContent value="review" className="mt-4 space-y-5">{review}</TabsContent>
      <TabsContent value="expert" className="mt-4 space-y-5">{expert}</TabsContent>
    </Tabs>
  );
}
```

- [ ] **Step 2: Move current panels into tabs without changing child behavior**

In `frontend/src/components/studio/studio-shell.tsx`, import `StudioExpertSections` and replace the long vertical panel list after the new command/stage/progress area with:

```tsx
<StudioExpertSections
  overview={
    <>
      <StudioSeriesBoard snapshot={activeSnapshot} workflowId={workflowId} productionCards={productionCards} />
      <EpisodePlanPanel snapshot={activeSnapshot} />
      <EpisodeContractPanel
        contract={activeSnapshot?.episode_contract || activeSnapshot?.workflow?.metadata?.episode_contract}
        loading={loading}
        onLock={handleLockEpisodeContract}
      />
    </>
  }
  assets={
    <>
      <ProductionBiblePanel snapshot={activeSnapshot} onApproveEntity={handleApproveProductionEntity} />
      <ConsistencyLedgerPanel snapshot={activeSnapshot} onRepair={handleLedgerRepair} />
      <StudioContinuityBoard snapshot={activeSnapshot} />
    </>
  }
  shots={
    <>
      <StudioProductionBoard snapshot={activeSnapshot} workflowId={workflowId} />
    </>
  }
  review={
    <div id="studio-agent-panel">
      <StudioAgentPanel
        snapshot={activeSnapshot}
        mode={mode}
        loading={loading}
        bypassReason={bypassReason}
        lastAction={lastAction}
        onBypassReasonChange={setBypassReason}
        onRefresh={() => loadSnapshot(workflowId, mode)}
        onAction={handleAction}
      />
    </div>
  }
  expert={
    <>
      <PromptSkillPanel />
      <StudioContextPanel snapshot={activeSnapshot} />
    </>
  }
/>
```

- [ ] **Step 3: Keep expert links but relabel them**

Change the expert links label row from `专家工具` to `高级工具` and keep all existing hrefs. This preserves current navigation while making it secondary.

- [ ] **Step 4: Typecheck**

Run:

```bash
cd frontend
npm run typecheck
```

Expected: TypeScript passes.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/studio/studio-expert-sections.tsx frontend/src/components/studio/studio-shell.tsx
git commit -m "feat: organize studio expert sections"
```

---

## Task 8: Contextual Deep Links For Review And Shot Repair

**Files:**
- Modify: `frontend/src/app/studio/continuity-review/page.tsx`
- Modify: `frontend/src/app/studio/shot-review/page.tsx`
- Modify: `frontend/src/lib/api-client.ts`
- Modify: `backend/app/api/v1/endpoints/studio.py`

- [ ] **Step 1: Add workflow filter support to global review API client usage**

In `frontend/src/app/studio/continuity-review/page.tsx`, read query params with `useSearchParams` and initialize:

```tsx
const searchParams = useSearchParams();
const initialNovelId = searchParams.get('novel_id') || '';
const initialWorkflowId = searchParams.get('workflow_id') || '';
const initialEntityId = searchParams.get('entity_id') || '';
const initialEpisode = searchParams.get('episode_index') || '';
```

Set initial state:

```tsx
const [novelFilter, setNovelFilter] = useState(initialNovelId);
const [workflowFilter] = useState(initialWorkflowId);
const [entityFilter, setEntityFilter] = useState(initialEntityId);
const [episodeFilter, setEpisodeFilter] = useState(initialEpisode);
```

Pass `workflow_id: workflowFilter || undefined` to `apiClient.getContinuityReviewTasks`.

- [ ] **Step 2: Extend API client type**

In `frontend/src/lib/api-client.ts`, extend `getContinuityReviewTasks` params:

```ts
workflow_id?: string;
```

Add:

```ts
if (params.workflow_id) searchParams.set('workflow_id', params.workflow_id);
```

- [ ] **Step 3: Backend continuity task endpoint accepts workflow filter**

In the continuity review task endpoint currently used by `apiClient.getContinuityReviewTasks`, add a `workflow_id` query parameter and pass it into `list_continuity_review_tasks`. The service already accepts `workflow_id` because `backend/app/api/v1/endpoints/studio.py` uses it for workflow-level review tasks.

- [ ] **Step 4: Shot review highlights deep-linked shot**

In `frontend/src/app/studio/shot-review/page.tsx`, read `shot_id` and `source_issue_code` from search params. Scroll the selected shot into view after shot data loads:

```tsx
useEffect(() => {
  if (!targetShotId) return;
  const node = document.querySelector(`[data-shot-id="${targetShotId}"]`);
  node?.scrollIntoView({ block: 'center', behavior: 'smooth' });
}, [targetShotId, shots.length]);
```

Ensure each shot card root includes:

```tsx
data-shot-id={shot.id}
```

Show a small banner when `source_issue_code` is present:

```tsx
{sourceIssueCode ? (
  <div className="rounded-lg border border-amber-400/25 bg-amber-500/10 px-4 py-3 text-sm text-amber-50">
    来自工作室处理意见：{sourceIssueCode}
  </div>
) : null}
```

- [ ] **Step 5: Verify**

Run:

```bash
cd backend
pytest test_studio_actions.py -q
cd ../frontend
npm run typecheck
```

Expected: backend tests pass; frontend typecheck passes.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/studio/continuity-review/page.tsx frontend/src/app/studio/shot-review/page.tsx frontend/src/lib/api-client.ts backend/app/api/v1/endpoints/studio.py
git commit -m "feat: preserve studio context in review links"
```

---

## Task 9: Frontend-Initiated Full Flow Smoke Test

**Files:**
- Modify: `frontend/package.json`
- Add: `frontend/e2e/studio-smart-console.spec.ts`
- Add: `frontend/playwright.config.ts`

- [ ] **Step 1: Add Playwright test harness**

In `frontend/package.json`, add scripts:

```json
"e2e": "playwright test",
"e2e:headed": "playwright test --headed"
```

Add dev dependency:

```json
"@playwright/test": "^1.45.0"
```

Run:

```bash
cd frontend
npm install
```

Expected: lockfile updates and Playwright package is installed.

- [ ] **Step 2: Add Playwright config**

Create `frontend/playwright.config.ts`:

```ts
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://127.0.0.1:3000',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
});
```

- [ ] **Step 3: Add Studio smart console smoke test**

Create `frontend/e2e/studio-smart-console.spec.ts`:

```ts
import { expect, test } from '@playwright/test';

test('novel management exposes production entry and studio exposes guided command console', async ({ page }) => {
  await page.goto('/novels');
  await expect(page.getByRole('heading', { name: '小说管理' })).toBeVisible();

  const firstProductionAction = page.getByRole('link', { name: /补齐章节|生成整书计划|创建本集工程|继续制作/ }).first();
  await expect(firstProductionAction).toBeVisible();

  const href = await firstProductionAction.getAttribute('href');
  expect(href || '').not.toEqual('');

  if ((href || '').startsWith('/studio')) {
    await firstProductionAction.click();
    await expect(page.getByText('制作主线')).toBeVisible();
    await expect(page.getByText(/连续性|阻断项/)).toBeVisible();
    await expect(page.getByRole('button', { name: /应用资产锁|运行质量检查|生成本集草片|生成 Story Bible|下一步|继续制作/ })).toBeVisible();
  } else {
    await firstProductionAction.click();
    await expect(page.getByText(/章节|整书|本集工程|多集计划/)).toBeVisible();
  }
});
```

- [ ] **Step 4: Run full local stack**

Start backend:

```bash
cd backend
uvicorn main:app --reload --port 8000
```

Start frontend in another terminal:

```bash
cd frontend
npm run dev
```

- [ ] **Step 5: Run frontend-initiated smoke**

Run:

```bash
cd frontend
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api/v1 npm run e2e
```

Expected: Playwright opens `/novels`, verifies the production entry CTA, follows it, and verifies either Studio command console or the appropriate preparation page.

- [ ] **Step 6: Run regression checks**

Run:

```bash
cd backend
pytest test_novel_production_entry.py test_studio_snapshot.py test_studio_actions.py -q
cd ../frontend
npm run typecheck
npm run build
```

Expected: all commands pass.

- [ ] **Step 7: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/playwright.config.ts frontend/e2e/studio-smart-console.spec.ts
git commit -m "test: add studio smart console e2e smoke"
```

---

## Task 10: Final Verification, Cleanup, And Release Commit

**Files:**
- Review all files touched by Tasks 1-9.

- [ ] **Step 1: Check working tree**

Run:

```bash
git status --short
```

Expected: only intended source, test, package, and plan files are modified. Do not stage `frontend/tsconfig.tsbuildinfo`, `.logs/`, generated media, or other local artifacts.

- [ ] **Step 2: Run backend regression**

Run:

```bash
cd backend
pytest test_novel_production_entry.py test_studio_snapshot.py test_studio_actions.py test_series_production.py tests/test_production_cards.py -q
```

Expected: all selected backend tests pass.

- [ ] **Step 3: Run frontend checks**

Run:

```bash
cd frontend
npm run typecheck
npm run build
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api/v1 npm run e2e
```

Expected: typecheck, production build, and browser smoke pass.

- [ ] **Step 4: Manual acceptance checklist**

Use a browser against the local services and verify:

- `/novels` shows one primary production action per novel.
- A novel with no chapters points to chapter handling.
- A novel with chapters but no series plan points to the series-plan tab.
- A novel with an existing workflow opens `/studio` with `workflow_id`, `novel_id`, and `chapter_id`.
- Studio top command bar shows novel, episode, mode, readiness, blocker count, and recommendation.
- The stage flow shows five stages and does not push expert details above the fold.
- Safe actions run directly and show progress.
- Confirm/production actions open the confirmation dialog.
- Expert sections contain the existing panels without breaking their actions.
- Continuity review and shot review links preserve context and focus target items.

- [ ] **Step 5: Commit any final fixes**

```bash
git add <intended-files-only>
git commit -m "fix: polish studio smart console flow"
```

Use this commit only if final verification requires small fixes. Skip it if all previous task commits are clean.

- [ ] **Step 6: Prepare handoff summary**

Record:

- backend tests run and results
- frontend checks run and results
- e2e command and result
- screenshots path if Playwright generated any failures
- known residual risks, especially any page still using old expert navigation

---

## Tracking Matrix

| Capability | Task | Verification |
| --- | --- | --- |
| Novel list primary production CTA | Task 1, Task 4 | `test_novel_production_entry.py`, `/novels` browser smoke |
| Novel detail fast route | Task 4 | manual route check, typecheck |
| Studio global command bar | Task 2, Task 5 | `test_studio_snapshot.py`, Playwright smoke |
| Five-stage Studio main line | Task 2, Task 5 | `guidance.stages` test, UI smoke |
| Action confirmation | Task 2, Task 6 | typecheck, manual safe/confirm action run |
| Expert panel simplification | Task 7 | typecheck, manual Studio tab check |
| Contextual repair links | Task 8 | backend route test, manual deep link |
| Full frontend-initiated flow test | Task 9 | `npm run e2e` |

## Self-Review

- Spec coverage: The plan covers Novel Management entry, Studio command console, staged workflow, operation confirmation, contextual repair links, expert tool consolidation, and full-flow frontend testing.
- Placeholder scan: No `TBD`, `TODO`, or undefined future tasks are left in this plan.
- Type consistency: `StudioGuidedAction`, `NovelProductionEntry`, and `StudioGuidance` are introduced before frontend usage. Backend `guidance.next_action` maps to the frontend `StudioGuidedAction` shape.
- Scope check: The plan is large but each task ships working software independently and can be committed separately. The backend contracts are additive and reduce risk before UI changes.
