# Continuous Anime Series Studio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a unified Series Studio that lowers the barrier from full novel to multi-episode anime while preserving production-grade continuity for style, characters, scenes, props, events, supporting roles, voices, shots, and render output.

**Architecture:** Keep the current FastAPI + Next.js system, but turn scattered expert modules into one orchestration console backed by explicit contracts: `ProductionBible`, `SeriesPlan`, `EpisodeContract`, `ConsistencyLedger`, and `FrontendE2EReport`. P0 uses existing JSON fields (`StoryBible.extra_data`, `StoryEntity.attributes`, `Novel.extra_data`, `Workflow.extra_data`) plus focused services so the change is reversible before any schema migration.

**Tech Stack:** FastAPI, async SQLAlchemy, SQLite/PostgreSQL, Next.js 14, React 18, TypeScript, Tailwind CSS, pytest, Playwright, Volcano Engine, DashScope/Qianlian, FFmpeg.

---

## Baseline And Assumptions

- Stable baseline commit before this plan: `983f335 feat: stabilize story bible video reference workflow`.
- The July 4 frontend audit proved the DEV draft flow can create a novel, chapter, Story Bible, storyboard, workflow, 4 video jobs, 3 TTS jobs, and 1 synthesis job from `/quick-start`.
- The same audit found the main product gap: the draft can be generated, but continuity inputs are weak. Story Bible had props but no strong character, scene, voice, or state coverage; shots were generated with unbound characters and fallback single-image references.
- The current architecture already contains useful pieces: `backend/app/services/production_bible.py`, `studio_snapshot.py`, `production_card_service.py`, `series_production.py`, `production_strategy_routing.py`, `video_reference_adapter.py`, and `/studio` pages.
- P0 must not introduce a database migration unless a task explicitly proves JSON fields are insufficient.
- Existing expert pages remain available during rollout. The new Series Studio becomes the default path, while `/producer`, `/workflow`, `/story-bibles`, `/studio/cards`, `/studio/shot-review`, `/video-generation`, `/assets`, and `/tts` become drill-down surfaces.
- Generated media, `.next`, `tsconfig.tsbuildinfo`, `.logs`, `.playwright-cli`, `.superpowers`, and static DEV outputs are not part of planned commits.

## Benchmark Takeaways

- Runway Gen-4 References shows the value of reusable visual references for characters, locations, objects, and styles: [Runway Gen-4 Image References](https://help.runwayml.com/hc/en-us/articles/40042718905875-Creating-with-Gen-4-Image-References).
- Runway's long-video guidance emphasizes reference plates, scene organization, side-by-side review, and environment plates: [Runway longer videos and films](https://help.runwayml.com/hc/en-us/articles/26871350018835-How-to-create-longer-videos-and-films).
- Kling Element Library turns characters, items, and scenes into reusable multi-angle elements with voice binding: [Kling Element Library](https://app.klingai.com/global/quickstart/klingai-element-library-3-user-guide).
- Kling Elements and Omni references point toward a business abstraction that users understand: create once, reuse consistently, and let models handle element memory: [Kling Elements](https://app.klingai.com/global/quickstart/ai-video-character-consistency) and [Kling Video 3.0 Omni](https://app.klingai.com/global/quickstart/klingai-video-3-omni-model-user-guide).
- LTX Studio's main lesson is workspace unification: script/storyboard/generation/timeline belong in one production space, not in disconnected tools: [LTX Studio AI Storyboard Generator](https://ltx.studio/platform/ai-storyboard-generator).
- Vyond's lesson is lowering the learning curve with character, scene template, voiceover, lip sync, and editing controls inside the same studio mental model: [Vyond voiceover and lip sync](https://www.vyond.com/blog/add-voice-over-in-vyond/) and [Vyond video creation overview](https://www.vyond.com/blog/everything-you-need-make-a-video-in-vyond/).

## Target Product Shape

The user should see one default operating console:

```text
Series Studio
  Overview: series readiness, next best action, model strategy, latest episode
  Bible: style, characters, scenes, props, events, voices, prompt skills
  Episodes: novel/chapter split, episode contract, carry-over state, batch status
  Assets: required cards, generated candidates, approved references, voice samples
  Production: script, storyboard, shots, video/TTS/subtitle/synthesis jobs
  Review: consistency scores, fallback reasons, regeneration, export package
```

The simplified user path should be:

```text
Import or select novel
  -> AI builds Production Bible
  -> user approves key characters/style/voices
  -> AI creates multi-episode Series Plan
  -> user opens Episode 1
  -> AI locks Episode Contract
  -> one click creates draft episode
  -> Studio shows consistency findings and repair actions
  -> user regenerates selected shots for final quality
  -> export preview package
```

## Success Metrics

- A first-time user can produce a draft episode from a novel with 3 primary decisions: choose novel, approve Production Bible, generate Episode 1.
- The Series Studio first viewport shows series readiness, missing requirements, current episode state, and next best action without sending the user to another page.
- Before any final-quality generation, every generated shot has an `episode_contract_id` or equivalent snapshot key in `Workflow.extra_data.episode_contract`.
- Every video job records model strategy, reference package mode, fallback reason, and continuity inputs in `VideoJob.extra_data`.
- Characters, scenes, props, voices, and events each have a visible readiness state and a repair action when incomplete.
- Full frontend-initiated Playwright flow passes: quick start, Studio, Bible review, production cards, shot review, producer/workflow drill-down, generation history, and export readiness.
- Regression gates pass after each task: backend target pytest, frontend typecheck, frontend build, and task-specific Playwright specs.

## File Structure Map

Backend service contracts:

- Modify: `backend/app/services/production_bible.py` - becomes the canonical read/write helper for Production Bible summaries and validation.
- Create: `backend/app/services/series_plan_service.py` - builds and updates `Novel.extra_data.series_plan`.
- Create: `backend/app/services/episode_contract_service.py` - freezes per-episode style/entity/voice/model state into `Workflow.extra_data.episode_contract`.
- Create: `backend/app/services/consistency_ledger_service.py` - records shot/job continuity evidence and scores into workflow/job metadata.
- Modify: `backend/app/services/studio_snapshot.py` - aggregates Series Studio state and next actions.
- Modify: `backend/app/services/studio_actions.py` - executes repair actions from the unified console.
- Modify: `backend/app/services/series_production.py` - orchestrates multi-episode production without duplicating workflow code.
- Modify: `backend/app/services/production_strategy_routing.py` - exposes strategy/fallback state for UI and tests.
- Modify: `backend/app/services/video_reference_adapter.py` - keeps reference package behavior deterministic and visible.

Backend endpoints:

- Modify: `backend/app/api/v1/endpoints/studio.py` - add series-level snapshot and action endpoints.
- Modify: `backend/app/api/v1/endpoints/story_bible.py` - add Production Bible review/approve/repair APIs.
- Modify: `backend/app/api/v1/endpoints/workflow.py` - lock Episode Contract during generation and expose export readiness.
- Modify: `backend/app/api/v1/endpoints/video.py` - surface model strategy, reference mode, and fallback in job responses.
- Modify: `backend/app/api/v1/router.py` - include new series endpoints when created.

Frontend default experience:

- Modify: `frontend/src/app/quick-start/page.tsx` - send successful generation to Series Studio with stable params.
- Modify: `frontend/src/app/studio/page.tsx` - remains route wrapper.
- Modify: `frontend/src/components/studio/studio-shell.tsx` - becomes unified Series Studio shell.
- Create: `frontend/src/components/studio/series-overview-panel.tsx` - first viewport global control panel.
- Create: `frontend/src/components/studio/production-bible-panel.tsx` - Bible review and approval.
- Create: `frontend/src/components/studio/episode-plan-panel.tsx` - multi-episode plan and status.
- Create: `frontend/src/components/studio/episode-contract-panel.tsx` - locked episode contract and drift warnings.
- Create: `frontend/src/components/studio/consistency-ledger-panel.tsx` - shot/job consistency findings.
- Modify: `frontend/src/components/studio/studio-production-board.tsx` - turn existing production board into an episode panel.
- Modify: `frontend/src/components/studio/studio-agent-panel.tsx` - next best actions from backend action contract.
- Modify: `frontend/src/lib/api-client.ts` - add typed API methods.
- Modify: `frontend/src/lib/studio-api.ts` and `frontend/src/lib/studio-types.ts` - add Series Studio types.

Tests:

- Create: `backend/tests/test_series_plan_service.py`.
- Create: `backend/tests/test_episode_contract_service.py`.
- Create: `backend/tests/test_consistency_ledger_service.py`.
- Modify: `backend/test_workflow_routes.py`.
- Modify: `backend/test_novel_import_story_bible.py`.
- Modify: `backend/test_story_bible_auto_build.py`.
- Modify: `backend/tests/test_reference_package.py`.
- Create: `frontend/e2e/series-studio-full-flow.spec.ts`.
- Create: `frontend/e2e/series-studio-production-bible.spec.ts`.
- Create: `frontend/e2e/series-studio-multi-episode.spec.ts`.
- Create: `frontend/e2e/series-studio-consistency-ledger.spec.ts`.
- Modify: `frontend/e2e/quick-start-series-plan.spec.ts`.
- Modify: `frontend/e2e/studio-full-flow.spec.ts`.

## Data Contracts

### Production Bible Projection

Store in `StoryBible.extra_data.production_bible` and `StoryEntity.attributes` during P0.

```ts
type ProductionBibleSummary = {
  novel_id: string;
  story_bible_id: string | null;
  readiness_score: number;
  style: {
    visual_style: string | null;
    color_palette: string[];
    camera_language: string[];
    negative_prompt: string | null;
  };
  entities: {
    characters: ProductionEntityCard[];
    scenes: ProductionEntityCard[];
    props: ProductionEntityCard[];
    events: ProductionEntityCard[];
    supporting_roles: ProductionEntityCard[];
  };
  voices: VoiceProfileCard[];
  missing_requirements: ProductionRequirement[];
  next_actions: StudioAction[];
};
```

### Episode Contract

Store in `Workflow.extra_data.episode_contract`.

```ts
type EpisodeContract = {
  contract_id: string;
  novel_id: string;
  chapter_ids: string[];
  episode_index: number;
  locked_at: string;
  production_bible_hash: string;
  style_lock: Record<string, unknown>;
  entity_locks: Array<{
    entity_id: string;
    entity_type: 'character' | 'scene' | 'prop' | 'event' | 'supporting_role';
    name: string;
    approved_asset_ids: string[];
    voice_profile_id?: string;
    state_before?: Record<string, unknown>;
    state_after_expected?: Record<string, unknown>;
  }>;
  model_strategy: {
    draft_video: string;
    final_video: string;
    image: string;
    tts: string;
    fallback_policy: 'visible_fallback' | 'block_final';
  };
  required_checks: string[];
};
```

### Consistency Ledger

Store a summary in `Workflow.extra_data.consistency_ledger` and detailed job evidence in job `extra_data`.

```ts
type ConsistencyLedger = {
  workflow_id: string;
  overall_score: number;
  dimensions: {
    style: number;
    character_visual: number;
    scene: number;
    prop_state: number;
    voice: number;
    event_continuity: number;
    subtitle_timing: number;
  };
  findings: Array<{
    code: string;
    severity: 'blocking' | 'warning' | 'info';
    shot_id?: string;
    entity_id?: string;
    message: string;
    repair_action?: StudioAction;
  }>;
};
```

## Change Control

- Each task below is a separate commit unless a task explicitly says it is documentation-only.
- Every backend behavior change starts with a failing pytest or route test.
- Every frontend behavior change starts with either a Playwright spec or a typed component contract test by running `pnpm --dir frontend typecheck`.
- No task may delete existing pages. Pages can be linked as expert drill-downs after the Series Studio path is verified.
- Any external model call must have DEV_MODE/mock behavior so Playwright can run without paid provider calls.
- If a task touches `workflow.py`, run the workflow route tests before and after the change.

## Verification Commands

Use these commands after every backend/frontend integration task:

```bash
cd backend && DEV_MODE=true PYTHONPATH=. python3 -m pytest -q test_model_registry_story_bible.py test_novel_import_story_bible.py test_story_bible_auto_build.py test_workflow_routes.py tests/test_reference_package.py test_video_model_catalog.py
PATH="/Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH" /Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/pnpm --dir frontend typecheck
PATH="/Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH" /Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/pnpm --dir frontend build
git diff --check
```

## Task 1: Series Studio Feature Flag And Snapshot Contract

**Purpose:** Add a controlled entry point for the new console without breaking current `/studio`.

**Files:**
- Create: `backend/app/services/series_studio_flags.py`
- Modify: `backend/app/api/v1/endpoints/studio.py`
- Modify: `backend/app/services/studio_snapshot.py`
- Modify: `frontend/src/lib/studio-types.ts`
- Modify: `frontend/src/lib/studio-api.ts`
- Modify: `frontend/src/components/studio/studio-shell.tsx`
- Test: `backend/test_workflow_routes.py`
- Test: `frontend/e2e/studio-full-flow.spec.ts`

- [ ] **Step 1: Write the backend failing route test**

Add this test to `backend/test_workflow_routes.py`:

```python
def test_studio_snapshot_exposes_series_studio_contract(client, auth_headers, seeded_workflow):
    response = client.get(
        f"/api/v1/studio/workflows/{seeded_workflow.id}/snapshot?mode=production",
        headers=auth_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert "series_studio" in payload
    assert payload["series_studio"]["enabled"] is True
    assert payload["series_studio"]["primary_console"] == "series_studio"
    assert payload["series_studio"]["expert_drilldowns"] == [
        "/story-bibles",
        "/studio/cards",
        "/studio/shot-review",
        "/workflow",
        "/producer",
        "/video-generation",
    ]
```

- [ ] **Step 2: Run the failing backend test**

Run:

```bash
cd backend && DEV_MODE=true PYTHONPATH=. python3 -m pytest -q test_workflow_routes.py::test_studio_snapshot_exposes_series_studio_contract
```

Expected: FAIL because `series_studio` is not present.

- [ ] **Step 3: Add the flag helper**

Create `backend/app/services/series_studio_flags.py`:

```python
from __future__ import annotations

import os
from typing import Any, Dict


def series_studio_enabled() -> bool:
    return os.getenv("SERIES_STUDIO_V2", "true").lower() not in {"0", "false", "off", "no"}


def series_studio_contract() -> Dict[str, Any]:
    return {
        "enabled": series_studio_enabled(),
        "primary_console": "series_studio",
        "expert_drilldowns": [
            "/story-bibles",
            "/studio/cards",
            "/studio/shot-review",
            "/workflow",
            "/producer",
            "/video-generation",
        ],
    }
```

- [ ] **Step 4: Merge the contract into studio snapshots**

Modify `backend/app/services/studio_snapshot.py` where the final snapshot dict is assembled:

```python
from app.services.series_studio_flags import series_studio_contract

snapshot["series_studio"] = series_studio_contract()
```

- [ ] **Step 5: Add frontend types**

Add to `frontend/src/lib/studio-types.ts`:

```ts
export type SeriesStudioContract = {
  enabled: boolean;
  primary_console: 'series_studio';
  expert_drilldowns: string[];
};

export type StudioSnapshot = {
  [key: string]: unknown;
  series_studio?: SeriesStudioContract;
};
```

If `frontend/src/lib/studio-types.ts` already exports `StudioSnapshot`, add only the `series_studio?: SeriesStudioContract` property to that existing type.

- [ ] **Step 6: Render a small expert drill-down group**

Modify `frontend/src/components/studio/studio-shell.tsx` so the first viewport can show expert links only when `snapshot.series_studio?.enabled` is true. Use existing `Button`, `Badge`, or link styles from the file. The visible labels must be:

```ts
const expertLinks = [
  { href: '/story-bibles', label: 'Story Bible' },
  { href: '/studio/cards', label: '生产卡' },
  { href: '/studio/shot-review', label: '镜头审阅' },
  { href: '/workflow', label: '工作流' },
  { href: '/producer', label: 'AI 制片' },
  { href: '/video-generation', label: '视频生成' },
];
```

- [ ] **Step 7: Verify and commit**

Run:

```bash
cd backend && DEV_MODE=true PYTHONPATH=. python3 -m pytest -q test_workflow_routes.py::test_studio_snapshot_exposes_series_studio_contract
PATH="/Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH" /Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/pnpm --dir frontend typecheck
git add backend/app/services/series_studio_flags.py backend/app/api/v1/endpoints/studio.py backend/app/services/studio_snapshot.py frontend/src/lib/studio-types.ts frontend/src/lib/studio-api.ts frontend/src/components/studio/studio-shell.tsx backend/test_workflow_routes.py frontend/e2e/studio-full-flow.spec.ts
git commit -m "feat: add series studio snapshot contract"
```

## Task 2: Production Bible Extraction Quality Gate

**Purpose:** Ensure novel/chapter analysis produces minimum viable continuity coverage: protagonist, supporting roles, scenes, props, events, style, and voices.

**Files:**
- Modify: `backend/app/services/entity_extraction_service.py`
- Modify: `backend/app/api/v1/endpoints/story_bible.py`
- Modify: `backend/app/services/production_bible.py`
- Modify: `backend/test_novel_import_story_bible.py`
- Modify: `backend/test_story_bible_auto_build.py`

- [ ] **Step 1: Add extraction coverage tests**

Add this expectation to the existing novel import Story Bible test:

```python
def assert_minimum_production_bible_coverage(payload: dict) -> None:
    summary = payload["production_bible_summary"]
    assert summary["counts"]["characters"] >= 1
    assert summary["counts"]["scenes"] >= 1
    assert summary["counts"]["props"] >= 1
    assert summary["state_machine"]["current_state_counts"]["events"] >= 1
    codes = {item["code"] for item in summary["missing_requirements"]}
    assert "characters_missing" not in codes
    assert "style_missing" not in codes
```

- [ ] **Step 2: Run the failing extraction tests**

Run:

```bash
cd backend && DEV_MODE=true PYTHONPATH=. python3 -m pytest -q test_novel_import_story_bible.py test_story_bible_auto_build.py
```

Expected: FAIL on stories that currently produce only prop fragments or no character/scene coverage.

- [ ] **Step 3: Normalize entity names before saving**

Modify `backend/app/services/entity_extraction_service.py` with a deterministic normalizer:

```python
def normalize_entity_name(name: str, entity_type: str) -> str:
    text = " ".join(str(name or "").replace("：", ":").split())
    for sep in ["，", ",", "。", ".", "；", ";", "、", " - ", " -- "]:
        if sep in text:
            text = text.split(sep)[0]
    text = text.strip(" \"'《》[]()（）")
    if not text:
        return {"character": "未命名角色", "scene": "未命名场景", "prop": "未命名道具", "event": "未命名事件"}.get(entity_type, "未命名实体")
    return text[:40]
```

Apply this before creating or updating `StoryEntity.name` and `canonical_name`.

- [ ] **Step 4: Add fallback protagonist/scene/event extraction**

In `entity_extraction_service.py`, after model/local extraction, add deterministic fallback rules:

```python
def ensure_minimum_story_entities(entities: list[dict], source_text: str) -> list[dict]:
    types = {item.get("entity_type") for item in entities}
    if "character" not in types:
        entities.append({"entity_type": "character", "name": infer_first_person_or_title_subject(source_text), "confidence": 0.55, "evidence": source_text[:160]})
    if "scene" not in types:
        entities.append({"entity_type": "scene", "name": infer_first_location(source_text), "confidence": 0.5, "evidence": source_text[:160]})
    if "event" not in types:
        entities.append({"entity_type": "event", "name": infer_first_event(source_text), "confidence": 0.5, "evidence": source_text[:160]})
    return entities
```

Define `infer_first_person_or_title_subject`, `infer_first_location`, and `infer_first_event` in the same file with deterministic regexes and defaults used only in DEV/test fallback paths.

- [ ] **Step 5: Extend `build_production_bible_summary` readiness**

Modify `backend/app/services/production_bible.py` so it returns:

```python
"counts": {
    "characters": len(characters),
    "scenes": len(scenes),
    "props": len(props),
    "events": len(events),
    "voices": len(voices),
},
"readiness_score": round((ready_dimensions / total_dimensions) * 100),
```

Use dimensions: style, characters, scenes, props, events, voices, assets.

- [ ] **Step 6: Verify and commit**

Run:

```bash
cd backend && DEV_MODE=true PYTHONPATH=. python3 -m pytest -q test_novel_import_story_bible.py test_story_bible_auto_build.py
git add backend/app/services/entity_extraction_service.py backend/app/api/v1/endpoints/story_bible.py backend/app/services/production_bible.py backend/test_novel_import_story_bible.py backend/test_story_bible_auto_build.py
git commit -m "feat: improve production bible extraction coverage"
```

## Task 3: Production Bible Review And Approval API

**Purpose:** Give users one place to approve or repair continuity facts instead of editing disconnected entities and assets.

**Files:**
- Modify: `backend/app/api/v1/endpoints/story_bible.py`
- Modify: `backend/app/services/production_bible.py`
- Test: `backend/tests/test_production_bible_review.py`

- [ ] **Step 1: Create review route tests**

Create `backend/tests/test_production_bible_review.py`:

```python
def test_review_endpoint_returns_bible_sections(client, auth_headers, seeded_novel_with_story_bible):
    response = client.get(
        f"/api/v1/story-bibles/novel/{seeded_novel_with_story_bible.novel_id}/production-bible/review",
        headers=auth_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["sections"] == ["style", "characters", "scenes", "props", "events", "voices"]
    assert payload["approval_state"] in {"draft", "needs_review", "approved"}


def test_approve_character_updates_entity_attributes(client, auth_headers, seeded_character_entity):
    response = client.post(
        f"/api/v1/story-bibles/entities/{seeded_character_entity.id}/approve",
        headers=auth_headers,
        json={"approved": True, "approval_note": "主角设定确认"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["entity_id"] == seeded_character_entity.id
    assert payload["approved"] is True
```

- [ ] **Step 2: Run the failing route tests**

Run:

```bash
cd backend && DEV_MODE=true PYTHONPATH=. python3 -m pytest -q tests/test_production_bible_review.py
```

Expected: FAIL because routes do not exist.

- [ ] **Step 3: Add Pydantic request models**

Add to `backend/app/api/v1/endpoints/story_bible.py`:

```python
class EntityApprovalRequest(BaseModel):
    approved: bool
    approval_note: Optional[str] = None


class ProductionBiblePatchRequest(BaseModel):
    style: Optional[Dict[str, Any]] = None
    voices: Optional[List[Dict[str, Any]]] = None
    state_machine: Optional[Dict[str, Any]] = None
```

- [ ] **Step 4: Add service helpers**

Add to `backend/app/services/production_bible.py`:

```python
async def approve_story_entity(db: AsyncSession, user_id: str, entity_id: str, approved: bool, note: str | None = None) -> Dict[str, Any]:
    result = await db.execute(select(StoryEntity).where(StoryEntity.id == entity_id, StoryEntity.user_id == user_id))
    entity = result.scalar_one_or_none()
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="实体不存在")
    attrs = _json_dict(entity.attributes)
    attrs["approval_note"] = note
    attrs["approved_at"] = utc_now().isoformat() if approved else None
    entity.attributes = attrs
    entity.is_approved = approved
    await db.commit()
    return {"entity_id": entity.id, "approved": entity.is_approved, "attributes": attrs}
```

- [ ] **Step 5: Add routes**

Add routes under the existing Story Bible router:

```python
@router.get("/novel/{novel_id}/production-bible/review", response_model=Dict[str, Any])
async def review_production_bible(novel_id: str, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    summary = await build_production_bible_summary(db, user_id, novel_id)
    return {"sections": ["style", "characters", "scenes", "props", "events", "voices"], "approval_state": infer_approval_state(summary), "summary": summary}


@router.post("/entities/{entity_id}/approve", response_model=Dict[str, Any])
async def approve_entity(entity_id: str, request: EntityApprovalRequest, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return await approve_story_entity(db, user_id, entity_id, request.approved, request.approval_note)
```

Define `infer_approval_state(summary)` in the endpoint module:

```python
def infer_approval_state(summary: Dict[str, Any]) -> str:
    missing = summary.get("missing_requirements") or []
    if missing:
        return "needs_review"
    return "approved" if summary.get("readiness_score", 0) >= 80 else "draft"
```

- [ ] **Step 6: Verify and commit**

Run:

```bash
cd backend && DEV_MODE=true PYTHONPATH=. python3 -m pytest -q tests/test_production_bible_review.py test_novel_import_story_bible.py
git add backend/app/api/v1/endpoints/story_bible.py backend/app/services/production_bible.py backend/tests/test_production_bible_review.py
git commit -m "feat: add production bible review api"
```

## Task 4: Series Plan Service For Full Novels

**Purpose:** Convert full novels/chapters into visible, editable multi-episode plans.

**Files:**
- Create: `backend/app/services/series_plan_service.py`
- Modify: `backend/app/api/v1/endpoints/novels.py`
- Modify: `backend/app/api/v1/router.py` if a new endpoint file is preferred.
- Test: `backend/tests/test_series_plan_service.py`
- Modify: `frontend/e2e/quick-start-series-plan.spec.ts`

- [ ] **Step 1: Write service tests**

Create `backend/tests/test_series_plan_service.py`:

```python
@pytest.mark.asyncio
async def test_build_series_plan_groups_chapters_into_episodes(db_session, seeded_novel_with_chapters):
    plan = await build_series_plan(
        db_session,
        seeded_novel_with_chapters.user_id,
        seeded_novel_with_chapters.id,
        target_episode_count=3,
    )
    assert len(plan["episodes"]) == 3
    assert plan["episodes"][0]["episode_index"] == 1
    assert plan["episodes"][0]["chapter_ids"]
    assert plan["episodes"][0]["status"] == "planned"
    assert "carry_over_state" in plan["episodes"][0]
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
cd backend && DEV_MODE=true PYTHONPATH=. python3 -m pytest -q tests/test_series_plan_service.py
```

Expected: FAIL because `series_plan_service.py` does not exist.

- [ ] **Step 3: Implement deterministic plan builder**

Create `backend/app/services/series_plan_service.py`:

```python
from __future__ import annotations

from math import ceil
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.models import Chapter, Novel


async def build_series_plan(db: AsyncSession, user_id: str, novel_id: str, target_episode_count: Optional[int] = None) -> Dict[str, Any]:
    novel = (await db.execute(select(Novel).where(Novel.id == novel_id, Novel.user_id == user_id))).scalar_one_or_none()
    if novel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="小说不存在")
    chapters = list((await db.execute(select(Chapter).where(Chapter.novel_id == novel_id, Chapter.user_id == user_id).order_by(Chapter.chapter_number))).scalars().all())
    if not chapters:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="小说没有章节，无法拆集")
    episode_count = target_episode_count or max(1, ceil(len(chapters) / 3))
    chunk_size = max(1, ceil(len(chapters) / episode_count))
    episodes: List[Dict[str, Any]] = []
    for index in range(episode_count):
        chunk = chapters[index * chunk_size : (index + 1) * chunk_size]
        if not chunk:
            continue
        episodes.append({
            "episode_index": len(episodes) + 1,
            "title": f"第 {len(episodes) + 1} 集",
            "chapter_ids": [chapter.id for chapter in chunk],
            "chapter_range": [chunk[0].chapter_number, chunk[-1].chapter_number],
            "status": "planned",
            "summary": chunk[0].summary or chunk[0].title or "",
            "carry_over_state": {"characters": [], "props": [], "events": []},
            "workflow_id": None,
        })
    plan = {"novel_id": novel.id, "generated_at": utc_now().isoformat(), "episodes": episodes}
    extra = novel.extra_data if isinstance(novel.extra_data, dict) else {}
    extra["series_plan"] = plan
    novel.extra_data = extra
    await db.commit()
    return plan
```

- [ ] **Step 4: Add route**

Add to `backend/app/api/v1/endpoints/novels.py`:

```python
class SeriesPlanRequest(BaseModel):
    target_episode_count: Optional[int] = Field(default=None, ge=1, le=100)


@router.post("/{novel_id}/series-plan", response_model=Dict[str, Any])
async def create_series_plan(novel_id: str, request: SeriesPlanRequest, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return await build_series_plan(db, user_id, novel_id, request.target_episode_count)
```

- [ ] **Step 5: Update quick-start Playwright expectation**

Modify `frontend/e2e/quick-start-series-plan.spec.ts` so a completed quick start asserts that the Studio route shows an episode plan region:

```ts
await expect(page.getByText('多集计划')).toBeVisible();
await expect(page.getByText(/第 1 集|Episode 1/)).toBeVisible();
```

- [ ] **Step 6: Verify and commit**

Run:

```bash
cd backend && DEV_MODE=true PYTHONPATH=. python3 -m pytest -q tests/test_series_plan_service.py test_workflow_routes.py
PATH="/Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH" /Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/pnpm --dir frontend typecheck
git add backend/app/services/series_plan_service.py backend/app/api/v1/endpoints/novels.py backend/tests/test_series_plan_service.py frontend/e2e/quick-start-series-plan.spec.ts
git commit -m "feat: add novel series plan service"
```

## Task 5: Episode Contract Snapshot

**Purpose:** Freeze the continuity state used by an episode so later edits do not silently change already generated shots.

**Files:**
- Create: `backend/app/services/episode_contract_service.py`
- Modify: `backend/app/api/v1/endpoints/workflow.py`
- Modify: `backend/app/services/series_production.py`
- Test: `backend/tests/test_episode_contract_service.py`
- Modify: `backend/test_workflow_routes.py`

- [ ] **Step 1: Write contract service tests**

Create `backend/tests/test_episode_contract_service.py`:

```python
@pytest.mark.asyncio
async def test_lock_episode_contract_stores_snapshot(db_session, seeded_workflow):
    contract = await lock_episode_contract(db_session, seeded_workflow.user_id, seeded_workflow.id)
    assert contract["contract_id"]
    assert contract["workflow_id"] == seeded_workflow.id
    assert contract["production_bible_hash"]
    assert "style_lock" in contract
    assert isinstance(contract["entity_locks"], list)
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
cd backend && DEV_MODE=true PYTHONPATH=. python3 -m pytest -q tests/test_episode_contract_service.py
```

Expected: FAIL because `lock_episode_contract` does not exist.

- [ ] **Step 3: Implement snapshot helper**

Create `backend/app/services/episode_contract_service.py`:

```python
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.models import Workflow
from app.services.production_bible import build_production_bible_summary


def stable_hash(value: Dict[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def lock_episode_contract(db: AsyncSession, user_id: str, workflow_id: str) -> Dict[str, Any]:
    workflow = (await db.execute(select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user_id))).scalar_one_or_none()
    if workflow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工作流不存在")
    if not workflow.novel_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="工作流没有绑定小说")
    bible = await build_production_bible_summary(db, user_id, workflow.novel_id)
    contract = {
        "contract_id": f"contract-{uuid4()}",
        "workflow_id": workflow.id,
        "novel_id": workflow.novel_id,
        "chapter_id": workflow.chapter_id,
        "locked_at": utc_now().isoformat(),
        "production_bible_hash": stable_hash(bible),
        "style_lock": bible.get("style") or {},
        "entity_locks": [
            {"entity_id": item["entity_id"], "entity_type": key[:-1], "name": item["name"], "asset_ids": item.get("asset_ids", [])}
            for key in ("characters", "scenes", "props", "events")
            for item in bible.get(key, [])
        ],
        "required_checks": ["style", "characters", "scenes", "props", "voices", "reference_package"],
    }
    extra = workflow.extra_data if isinstance(workflow.extra_data, dict) else {}
    extra["episode_contract"] = contract
    workflow.extra_data = extra
    await db.commit()
    return contract
```

- [ ] **Step 4: Add workflow route**

Add to `backend/app/api/v1/endpoints/workflow.py`:

```python
@router.post("/{workflow_id}/episode-contract/lock", response_model=Dict[str, Any])
async def lock_workflow_episode_contract(workflow_id: str, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return await lock_episode_contract(db, user_id, workflow_id)
```

- [ ] **Step 5: Lock before media generation**

In the media generation path inside `workflow.py` or `series_production.py`, call `lock_episode_contract()` when `workflow.extra_data.episode_contract` is missing and the request is for draft or final episode production.

- [ ] **Step 6: Verify and commit**

Run:

```bash
cd backend && DEV_MODE=true PYTHONPATH=. python3 -m pytest -q tests/test_episode_contract_service.py test_workflow_routes.py
git add backend/app/services/episode_contract_service.py backend/app/api/v1/endpoints/workflow.py backend/app/services/series_production.py backend/tests/test_episode_contract_service.py backend/test_workflow_routes.py
git commit -m "feat: lock episode production contracts"
```

## Task 6: Series Studio Overview Panel

**Purpose:** Replace scattered next steps with a first-viewport operating panel that shows readiness, current episode, missing requirements, model strategy, and next action.

**Files:**
- Create: `frontend/src/components/studio/series-overview-panel.tsx`
- Modify: `frontend/src/components/studio/studio-shell.tsx`
- Modify: `frontend/src/lib/studio-types.ts`
- Test: `frontend/e2e/series-studio-full-flow.spec.ts`

- [ ] **Step 1: Write Playwright smoke assertion**

Create `frontend/e2e/series-studio-full-flow.spec.ts`:

```ts
import { expect, test } from '@playwright/test';

test('series studio overview shows global control state', async ({ page }) => {
  await page.goto('/studio?mode=test');
  await expect(page.getByText('系列动漫工作室')).toBeVisible();
  await expect(page.getByText('连续性状态')).toBeVisible();
  await expect(page.getByText('下一步')).toBeVisible();
  await expect(page.getByText(/草稿|终稿|模型策略/)).toBeVisible();
});
```

- [ ] **Step 2: Run the failing spec**

Run:

```bash
PATH="/Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH" /Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/pnpm --dir frontend exec playwright test e2e/series-studio-full-flow.spec.ts --project=chromium --workers=1
```

Expected: FAIL until the overview panel exists.

- [ ] **Step 3: Create `SeriesOverviewPanel`**

Create `frontend/src/components/studio/series-overview-panel.tsx`:

```tsx
'use client';

import { AlertTriangle, CheckCircle2, Film, Gauge, Wand2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import type { StudioSnapshot } from '@/lib/studio-types';

export function SeriesOverviewPanel({ snapshot, onPrimaryAction }: { snapshot: StudioSnapshot | null; onPrimaryAction?: () => void }) {
  const score = snapshot?.production_bible_summary?.readiness_score ?? 0;
  const currentEpisode = snapshot?.series_plan?.current_episode?.title || '第 1 集';
  const issueCount = snapshot?.issues?.length || 0;
  const strategy = snapshot?.metadata?.latest_production_strategy_label || 'Draft Fast';
  return (
    <Card className="border-white/10 bg-white/5">
      <CardContent className="grid gap-4 p-4 lg:grid-cols-[1.2fr_1fr_1fr_auto] lg:items-center">
        <div>
          <div className="flex items-center gap-2 text-base font-semibold text-white">
            <Film className="h-5 w-5 text-cyan-300" />
            系列动漫工作室
          </div>
          <p className="mt-1 text-sm text-white/60">{currentEpisode} · 连续性状态 {score}%</p>
        </div>
        <div className="flex items-center gap-2 text-sm text-white/70">
          <Gauge className="h-4 w-4 text-emerald-300" />
          模型策略：{strategy}
        </div>
        <div className="flex items-center gap-2">
          {issueCount > 0 ? <AlertTriangle className="h-4 w-4 text-amber-300" /> : <CheckCircle2 className="h-4 w-4 text-emerald-300" />}
          <Badge variant="outline" className="border-white/15 text-white/70">问题 {issueCount}</Badge>
        </div>
        <Button onClick={onPrimaryAction} className="gap-2">
          <Wand2 className="h-4 w-4" />
          下一步
        </Button>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 4: Mount panel in `StudioShell`**

Import and render `SeriesOverviewPanel` above the existing continuity board. Wire `onPrimaryAction` to the existing safe action runner when a backend `next_actions[0]` exists; otherwise navigate to `/studio/cards`.

- [ ] **Step 5: Verify and commit**

Run:

```bash
PATH="/Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH" /Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/pnpm --dir frontend typecheck
PATH="/Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH" /Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/pnpm --dir frontend exec playwright test e2e/series-studio-full-flow.spec.ts --project=chromium --workers=1
git add frontend/src/components/studio/series-overview-panel.tsx frontend/src/components/studio/studio-shell.tsx frontend/src/lib/studio-types.ts frontend/e2e/series-studio-full-flow.spec.ts
git commit -m "feat: add series studio overview panel"
```

## Task 7: Production Bible Panel In Studio

**Purpose:** Make style, characters, scenes, props, events, and voices visible and approvable from the unified console.

**Files:**
- Create: `frontend/src/components/studio/production-bible-panel.tsx`
- Modify: `frontend/src/components/studio/studio-shell.tsx`
- Modify: `frontend/src/lib/api-client.ts`
- Modify: `frontend/src/lib/studio-types.ts`
- Test: `frontend/e2e/series-studio-production-bible.spec.ts`

- [ ] **Step 1: Write Playwright test**

Create `frontend/e2e/series-studio-production-bible.spec.ts`:

```ts
import { expect, test } from '@playwright/test';

test('production bible panel exposes required continuity sections', async ({ page }) => {
  await page.goto('/studio?mode=test');
  await expect(page.getByText('Production Bible')).toBeVisible();
  await expect(page.getByText('风格')).toBeVisible();
  await expect(page.getByText('角色')).toBeVisible();
  await expect(page.getByText('场景')).toBeVisible();
  await expect(page.getByText('道具')).toBeVisible();
  await expect(page.getByText('事件')).toBeVisible();
  await expect(page.getByText('声线')).toBeVisible();
});
```

- [ ] **Step 2: Add API methods**

Modify `frontend/src/lib/api-client.ts`:

```ts
async getProductionBibleReview(novelId: string) {
  return this.request(`/story-bibles/novel/${novelId}/production-bible/review`);
}

async approveProductionEntity(entityId: string, approved: boolean, approvalNote?: string) {
  return this.request(`/story-bibles/entities/${entityId}/approve`, {
    method: 'POST',
    body: JSON.stringify({ approved, approval_note: approvalNote }),
  });
}
```

- [ ] **Step 3: Build the panel**

Create `frontend/src/components/studio/production-bible-panel.tsx` using existing `Card`, `Badge`, and `Button`. The panel must render six section headers exactly: `风格`, `角色`, `场景`, `道具`, `事件`, `声线`. Each entity row must have one approve button with text `确认`.

- [ ] **Step 4: Mount the panel**

Render `ProductionBiblePanel` in `studio-shell.tsx` after the overview panel. Pass `snapshot.production_bible_summary` directly to avoid duplicate loading.

- [ ] **Step 5: Verify and commit**

Run:

```bash
PATH="/Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH" /Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/pnpm --dir frontend typecheck
PATH="/Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH" /Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/pnpm --dir frontend exec playwright test e2e/series-studio-production-bible.spec.ts --project=chromium --workers=1
git add frontend/src/components/studio/production-bible-panel.tsx frontend/src/components/studio/studio-shell.tsx frontend/src/lib/api-client.ts frontend/src/lib/studio-types.ts frontend/e2e/series-studio-production-bible.spec.ts
git commit -m "feat: surface production bible in studio"
```

## Task 8: Episode Plan And Contract Panels

**Purpose:** Make multi-episode continuity visible: what each episode covers, what it inherits, and what is locked.

**Files:**
- Create: `frontend/src/components/studio/episode-plan-panel.tsx`
- Create: `frontend/src/components/studio/episode-contract-panel.tsx`
- Modify: `frontend/src/components/studio/studio-shell.tsx`
- Modify: `frontend/src/lib/api-client.ts`
- Modify: `frontend/src/lib/studio-types.ts`
- Test: `frontend/e2e/series-studio-multi-episode.spec.ts`

- [ ] **Step 1: Write Playwright test**

Create `frontend/e2e/series-studio-multi-episode.spec.ts`:

```ts
import { expect, test } from '@playwright/test';

test('multi episode plan and contract are visible', async ({ page }) => {
  await page.goto('/studio?mode=test');
  await expect(page.getByText('多集计划')).toBeVisible();
  await expect(page.getByText('剧集合约')).toBeVisible();
  await expect(page.getByRole('button', { name: /锁定|重新锁定/ })).toBeVisible();
});
```

- [ ] **Step 2: Add API client method**

Modify `frontend/src/lib/api-client.ts`:

```ts
async createSeriesPlan(novelId: string, targetEpisodeCount?: number) {
  return this.request(`/novels/${novelId}/series-plan`, {
    method: 'POST',
    body: JSON.stringify({ target_episode_count: targetEpisodeCount }),
  });
}

async lockEpisodeContract(workflowId: string) {
  return this.request(`/workflow/${workflowId}/episode-contract/lock`, { method: 'POST' });
}
```

The route prefix must be `/workflow` because existing `api-client.ts` workflow methods use `/workflow/${workflowId}/...`.

- [ ] **Step 3: Create `EpisodePlanPanel`**

The component must render each episode with: episode index, chapter range, status, workflow link when present, and one button labeled `打开本集`.

- [ ] **Step 4: Create `EpisodeContractPanel`**

The component must render: `production_bible_hash`, lock time, entity lock count, required checks, and a button labeled `锁定剧集合约` when missing.

- [ ] **Step 5: Verify and commit**

Run:

```bash
PATH="/Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH" /Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/pnpm --dir frontend typecheck
PATH="/Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH" /Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/pnpm --dir frontend exec playwright test e2e/series-studio-multi-episode.spec.ts --project=chromium --workers=1
git add frontend/src/components/studio/episode-plan-panel.tsx frontend/src/components/studio/episode-contract-panel.tsx frontend/src/components/studio/studio-shell.tsx frontend/src/lib/api-client.ts frontend/src/lib/studio-types.ts frontend/e2e/series-studio-multi-episode.spec.ts
git commit -m "feat: show episode plan and contract in studio"
```

## Task 9: Model Strategy And Visible Fallbacks

**Purpose:** Hide provider complexity from users while making model routing and fallback states auditable.

**Files:**
- Modify: `backend/app/services/production_strategy_routing.py`
- Modify: `backend/app/api/v1/endpoints/video.py`
- Modify: `backend/app/services/video_reference_adapter.py`
- Modify: `backend/app/services/studio_snapshot.py`
- Modify: `frontend/src/components/studio/studio-production-board.tsx`
- Modify: `frontend/src/app/video-generation/page.tsx`
- Test: `backend/test_video_model_catalog.py`
- Test: `backend/tests/test_reference_package.py`
- Test: `frontend/e2e/video-generation-preflight.spec.ts`

- [ ] **Step 1: Add backend assertions**

Extend `backend/tests/test_reference_package.py`:

```python
def test_video_job_metadata_exposes_strategy_and_fallback():
    metadata = build_video_job_metadata(
        production_strategy="draft_fast",
        selected_model_id="volcano.seedance.2_0_fast",
        fallback_model_id=None,
        reference_package_mode="multi_reference",
    )
    assert metadata["production_strategy"] == "draft_fast"
    assert metadata["selected_model_id"] == "volcano.seedance.2_0_fast"
    assert metadata["reference_package_mode"] == "multi_reference"
    assert metadata["fallback_visible"] is False
```

- [ ] **Step 2: Run the failing backend tests**

Run:

```bash
cd backend && DEV_MODE=true PYTHONPATH=. python3 -m pytest -q test_video_model_catalog.py tests/test_reference_package.py
```

- [ ] **Step 3: Add metadata helper**

Add to `backend/app/services/production_strategy_routing.py`:

```python
def build_video_job_metadata(production_strategy: str, selected_model_id: str | None, fallback_model_id: str | None, reference_package_mode: str | None) -> dict:
    return {
        "production_strategy": production_strategy,
        "selected_model_id": selected_model_id,
        "fallback_model_id": fallback_model_id,
        "fallback_visible": bool(fallback_model_id and fallback_model_id != selected_model_id),
        "reference_package_mode": reference_package_mode or "single_image",
    }
```

- [ ] **Step 4: Persist metadata on video jobs**

In `backend/app/api/v1/endpoints/video.py`, merge `build_video_job_metadata(...)` into `VideoJob.extra_data` for every generate path.

- [ ] **Step 5: Show model strategy in frontend**

In `frontend/src/components/studio/studio-production-board.tsx` and `frontend/src/app/video-generation/page.tsx`, render badges with labels:

```ts
const strategyLabels: Record<string, string> = {
  draft_fast: '草稿快速',
  final_quality: '终稿质量',
  low_cost: '低成本',
  direct_av_first: '音画直生',
  separate_video_tts: '视频+配音分步',
};
```

If `fallback_visible` is true, show text `已降级` and the fallback model id.

- [ ] **Step 6: Verify and commit**

Run:

```bash
cd backend && DEV_MODE=true PYTHONPATH=. python3 -m pytest -q test_video_model_catalog.py tests/test_reference_package.py
PATH="/Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH" /Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/pnpm --dir frontend typecheck
git add backend/app/services/production_strategy_routing.py backend/app/api/v1/endpoints/video.py backend/app/services/video_reference_adapter.py backend/app/services/studio_snapshot.py frontend/src/components/studio/studio-production-board.tsx frontend/src/app/video-generation/page.tsx backend/test_video_model_catalog.py backend/tests/test_reference_package.py frontend/e2e/video-generation-preflight.spec.ts
git commit -m "feat: expose production model strategy"
```

## Task 10: Consistency Ledger And Shot Repair Actions

**Purpose:** Turn vague quality risk into measurable findings and actionable regeneration controls.

**Files:**
- Create: `backend/app/services/consistency_ledger_service.py`
- Modify: `backend/app/services/shot_quality_service.py`
- Modify: `backend/app/services/studio_actions.py`
- Modify: `backend/app/services/studio_snapshot.py`
- Create: `frontend/src/components/studio/consistency-ledger-panel.tsx`
- Modify: `frontend/src/components/studio/studio-shell.tsx`
- Test: `backend/tests/test_consistency_ledger_service.py`
- Test: `frontend/e2e/series-studio-consistency-ledger.spec.ts`

- [ ] **Step 1: Write backend score tests**

Create `backend/tests/test_consistency_ledger_service.py`:

```python
def test_build_consistency_ledger_flags_unbound_character():
    ledger = build_consistency_ledger(
        shots=[{"id": "shot-1", "character_refs": [], "scene_refs": ["scene-1"], "video_status": "succeeded"}],
        episode_contract={"entity_locks": [{"entity_id": "char-1", "entity_type": "character", "name": "孙剑"}]},
        jobs=[],
    )
    assert ledger["overall_score"] < 80
    assert ledger["findings"][0]["code"] == "shot_character_unbound"
    assert ledger["findings"][0]["repair_action"]["code"] == "bind_character_reference"
```

- [ ] **Step 2: Implement pure scoring function**

Create `backend/app/services/consistency_ledger_service.py`:

```python
from __future__ import annotations

from typing import Any, Dict, List


def build_consistency_ledger(shots: List[Dict[str, Any]], episode_contract: Dict[str, Any], jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
    findings: List[Dict[str, Any]] = []
    for shot in shots:
        if not shot.get("character_refs"):
            findings.append({
                "code": "shot_character_unbound",
                "severity": "blocking",
                "shot_id": shot.get("id"),
                "message": "镜头没有绑定角色参考，人物一致性不可控",
                "repair_action": {"code": "bind_character_reference", "label": "绑定角色参考", "risk": "safe"},
            })
    blocking_count = len([item for item in findings if item["severity"] == "blocking"])
    score = max(0, 100 - blocking_count * 25 - len(findings) * 5)
    return {
        "overall_score": score,
        "dimensions": {
            "style": 100,
            "character_visual": 0 if blocking_count else 100,
            "scene": 100,
            "prop_state": 100,
            "voice": 100,
            "event_continuity": 100,
            "subtitle_timing": 100,
        },
        "findings": findings,
    }
```

- [ ] **Step 3: Merge ledger into studio snapshot**

In `backend/app/services/studio_snapshot.py`, build a ledger from current snapshot shot/job data and add:

```python
snapshot["consistency_ledger"] = ledger
```

- [ ] **Step 4: Add frontend panel**

Create `frontend/src/components/studio/consistency-ledger-panel.tsx`. It must show `一致性评分`, each dimension, each finding message, and a repair button for findings with `repair_action`.

- [ ] **Step 5: Write Playwright assertion**

Create `frontend/e2e/series-studio-consistency-ledger.spec.ts`:

```ts
import { expect, test } from '@playwright/test';

test('consistency ledger shows score and repair actions', async ({ page }) => {
  await page.goto('/studio?mode=test');
  await expect(page.getByText('一致性评分')).toBeVisible();
  await expect(page.getByText(/绑定角色参考|重新生成|修复/)).toBeVisible();
});
```

- [ ] **Step 6: Verify and commit**

Run:

```bash
cd backend && DEV_MODE=true PYTHONPATH=. python3 -m pytest -q tests/test_consistency_ledger_service.py test_workflow_routes.py
PATH="/Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH" /Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/pnpm --dir frontend typecheck
PATH="/Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH" /Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/pnpm --dir frontend exec playwright test e2e/series-studio-consistency-ledger.spec.ts --project=chromium --workers=1
git add backend/app/services/consistency_ledger_service.py backend/app/services/shot_quality_service.py backend/app/services/studio_actions.py backend/app/services/studio_snapshot.py frontend/src/components/studio/consistency-ledger-panel.tsx frontend/src/components/studio/studio-shell.tsx backend/tests/test_consistency_ledger_service.py frontend/e2e/series-studio-consistency-ledger.spec.ts
git commit -m "feat: add consistency ledger and repair actions"
```

## Task 11: Quick Start To Series Studio Handoff

**Purpose:** Remove the broken-feeling handoff where quick-start success sends users to many tools or intermittent empty Studio states.

**Files:**
- Modify: `frontend/src/app/quick-start/page.tsx`
- Modify: `frontend/src/lib/episode-preview-production.ts`
- Modify: `frontend/src/components/studio/studio-shell.tsx`
- Modify: `frontend/e2e/quick-start-series-plan.spec.ts`
- Modify: `frontend/e2e/studio-full-flow.spec.ts`

- [ ] **Step 1: Add Playwright regression**

Extend `frontend/e2e/quick-start-series-plan.spec.ts`:

```ts
await page.getByRole('button', { name: /生成第一集|开始生成/ }).click();
await expect(page.getByText(/生成完成|已生成/)).toBeVisible({ timeout: 120_000 });
await page.getByRole('link', { name: /进入工作室|打开工作室/ }).click();
await expect(page).toHaveURL(/\/studio\?.*workflow_id=/);
await expect(page.getByText('系列动漫工作室')).toBeVisible();
await expect(page.getByText('Failed to fetch')).toHaveCount(0);
```

- [ ] **Step 2: Add stable success URL**

In `frontend/src/app/quick-start/page.tsx`, build the Studio link with all known IDs:

```ts
const studioHref = `/studio?workflow_id=${workflowId}&novel_id=${novelId}&chapter_id=${chapterId}&source=quick_start`;
```

- [ ] **Step 3: Add snapshot retry with visible state**

In `frontend/src/components/studio/studio-shell.tsx`, wrap the initial snapshot fetch with 3 attempts and a user-facing retry state:

```ts
const retryDelays = [400, 1000, 1800];
for (const delay of retryDelays) {
  try {
    return await getStudioSnapshot(workflowId, mode);
  } catch (error) {
    await new Promise((resolve) => setTimeout(resolve, delay));
  }
}
```

When all attempts fail, show a retry button labeled `重新加载工作台` and keep query params intact.

- [ ] **Step 4: Verify and commit**

Run:

```bash
PATH="/Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH" /Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/pnpm --dir frontend typecheck
PATH="/Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH" /Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/pnpm --dir frontend exec playwright test e2e/quick-start-series-plan.spec.ts e2e/studio-full-flow.spec.ts --project=chromium --workers=1
git add frontend/src/app/quick-start/page.tsx frontend/src/lib/episode-preview-production.ts frontend/src/components/studio/studio-shell.tsx frontend/e2e/quick-start-series-plan.spec.ts frontend/e2e/studio-full-flow.spec.ts
git commit -m "feat: stabilize quick start studio handoff"
```

## Task 12: Information Architecture Simplification

**Purpose:** Make the product feel like one anime production platform instead of a toolbox.

**Files:**
- Modify: `frontend/src/components/layout/top-navigation.tsx`
- Modify: `frontend/src/components/layout/main-layout.tsx`
- Modify: `frontend/src/app/studio/page.tsx`
- Modify: `frontend/src/app/producer/page.tsx`
- Modify: `frontend/src/app/workflow/page.tsx`
- Modify: `frontend/src/app/story-bibles/page.tsx`
- Modify: `frontend/src/app/video-generation/page.tsx`
- Test: `frontend/e2e/top-navigation.spec.ts`
- Test: `frontend/e2e/onboarding-simplification.spec.ts`

- [ ] **Step 1: Define navigation groups**

Use this exact grouping in `top-navigation.tsx`:

```ts
const primaryNav = [
  { href: '/studio', label: '工作室' },
  { href: '/quick-start', label: '快速开始' },
  { href: '/novels', label: '小说' },
  { href: '/assets', label: '资产' },
];

const expertNav = [
  { href: '/story-bibles', label: 'Story Bible' },
  { href: '/producer', label: 'AI 制片' },
  { href: '/workflow', label: '工作流' },
  { href: '/video-generation', label: '视频生成' },
  { href: '/tts', label: '配音' },
  { href: '/synthesis', label: '合成' },
  { href: '/llm-config', label: '模型配置' },
];
```

- [ ] **Step 2: Write navigation test**

Modify `frontend/e2e/top-navigation.spec.ts`:

```ts
await page.goto('/studio');
await expect(page.getByRole('navigation').getByText('工作室')).toBeVisible();
await expect(page.getByRole('navigation').getByText('快速开始')).toBeVisible();
await page.getByRole('button', { name: /专家工具|更多/ }).click();
await expect(page.getByRole('menuitem', { name: '工作流' })).toBeVisible();
await expect(page.getByRole('menuitem', { name: '视频生成' })).toBeVisible();
```

- [ ] **Step 3: Add drill-down banners**

On `/producer`, `/workflow`, `/story-bibles`, and `/video-generation`, add a top banner with text:

```text
这是专家工具。连续动漫制作建议从工作室统一管控。
```

Add a button labeled `回到工作室`.

- [ ] **Step 4: Verify and commit**

Run:

```bash
PATH="/Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH" /Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/pnpm --dir frontend typecheck
PATH="/Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH" /Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/pnpm --dir frontend exec playwright test e2e/top-navigation.spec.ts e2e/onboarding-simplification.spec.ts --project=chromium --workers=1
git add frontend/src/components/layout/top-navigation.tsx frontend/src/components/layout/main-layout.tsx frontend/src/app/studio/page.tsx frontend/src/app/producer/page.tsx frontend/src/app/workflow/page.tsx frontend/src/app/story-bibles/page.tsx frontend/src/app/video-generation/page.tsx frontend/e2e/top-navigation.spec.ts frontend/e2e/onboarding-simplification.spec.ts
git commit -m "feat: simplify studio information architecture"
```

## Task 13: Full Frontend-Initiated Scenario Suite

**Purpose:** Prove the whole production path works from the user's browser, not only through direct API tests.

**Files:**
- Create: `frontend/e2e/series-studio-end-to-end.spec.ts`
- Modify: `frontend/playwright.config.ts`
- Create: `frontend/e2e/helpers/series-studio-fixtures.ts`
- Create: `frontend/e2e/helpers/console-health.ts`
- Test output: save screenshots/traces outside the repo under `/tmp/ai-video-platform-series-studio-e2e/`.

- [ ] **Step 1: Add fixture helper**

Create `frontend/e2e/helpers/series-studio-fixtures.ts`:

```ts
export const sampleNovel = {
  title: '雾城机甲师',
  genre: '热血科幻动漫',
  style: '赛璐璐动画，清晰线稿，冷暖对比，电影感分镜',
  content: '第一章 雾城少年林澈在旧车站发现会发光的核心钥匙。机械少女阿岚出现，提醒他黑塔追兵正在靠近。第二章 两人穿过雨夜集市，钥匙唤醒沉睡机甲。第三章 黑塔首领派出银面猎手，阿岚暴露自己曾是黑塔实验体。',
};

export const expectedSections = ['系列动漫工作室', 'Production Bible', '多集计划', '剧集合约', '一致性评分'];
```

- [ ] **Step 2: Add console health helper**

Create `frontend/e2e/helpers/console-health.ts`:

```ts
import type { Page } from '@playwright/test';

export function collectConsoleHealth(page: Page) {
  const errors: string[] = [];
  page.on('console', (message) => {
    if (['error', 'warning'].includes(message.type())) errors.push(`${message.type()}: ${message.text()}`);
  });
  page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`));
  return {
    errors,
    assertHealthy() {
      const relevant = errors.filter((line) => !line.includes('favicon') && !line.includes('ResizeObserver'));
      if (relevant.length) throw new Error(`Console health failed:\n${relevant.join('\n')}`);
    },
  };
}
```

- [ ] **Step 3: Create full browser flow spec**

Create `frontend/e2e/series-studio-end-to-end.spec.ts`:

```ts
import { expect, test } from '@playwright/test';
import { collectConsoleHealth } from './helpers/console-health';
import { expectedSections, sampleNovel } from './helpers/series-studio-fixtures';

test('full novel to episode production is controlled from the frontend', async ({ page }) => {
  const consoleHealth = collectConsoleHealth(page);
  await page.goto('/quick-start');
  await page.getByLabel(/标题|作品名/).fill(sampleNovel.title);
  await page.getByLabel(/类型|题材/).fill(sampleNovel.genre);
  await page.getByLabel(/风格/).fill(sampleNovel.style);
  await page.getByLabel(/内容|故事|小说/).fill(sampleNovel.content);
  await page.getByRole('button', { name: /生成第一集|开始生成/ }).click();
  await expect(page.getByText(/生成完成|已生成/)).toBeVisible({ timeout: 120_000 });
  await page.getByRole('link', { name: /进入工作室|打开工作室/ }).click();

  for (const section of expectedSections) {
    await expect(page.getByText(section)).toBeVisible({ timeout: 30_000 });
  }

  await expect(page.getByText(/角色/)).toBeVisible();
  await expect(page.getByText(/场景/)).toBeVisible();
  await expect(page.getByText(/道具/)).toBeVisible();
  await expect(page.getByText(/声线/)).toBeVisible();
  await expect(page.getByText(/模型策略|草稿快速|终稿质量/)).toBeVisible();
  await expect(page.getByText('Failed to fetch')).toHaveCount(0);

  await page.screenshot({ path: '/tmp/ai-video-platform-series-studio-e2e/series-studio-overview.png', fullPage: true });
  consoleHealth.assertHealthy();
});
```

- [ ] **Step 4: Add all-scenario matrix spec**

In the same file, add separate tests for:

```ts
test('production bible approval path works from studio', async ({ page }) => {});
test('episode contract can be locked from studio', async ({ page }) => {});
test('shot review exposes fallback and reference package evidence', async ({ page }) => {});
test('expert workflow page links back to studio', async ({ page }) => {});
test('video generation history shows strategy and fallback badges', async ({ page }) => {});
test('mobile viewport keeps first screen usable', async ({ page }) => {});
```

Each test must navigate through the UI first. Direct API setup can seed DEV data, but the assertion path must be browser driven.

- [ ] **Step 5: Verify full frontend scenario suite**

Run backend and frontend servers, then:

```bash
mkdir -p /tmp/ai-video-platform-series-studio-e2e
PATH="/Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH" /Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/pnpm --dir frontend exec playwright test e2e/series-studio-end-to-end.spec.ts --project=chromium --workers=1 --trace=retain-on-failure
```

Expected: PASS with screenshots in `/tmp/ai-video-platform-series-studio-e2e/`.

- [ ] **Step 6: Verify and commit**

Run:

```bash
PATH="/Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH" /Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/pnpm --dir frontend typecheck
PATH="/Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH" /Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/pnpm --dir frontend exec playwright test e2e/series-studio-end-to-end.spec.ts --project=chromium --workers=1
git add frontend/e2e/series-studio-end-to-end.spec.ts frontend/e2e/helpers/series-studio-fixtures.ts frontend/e2e/helpers/console-health.ts frontend/playwright.config.ts
git commit -m "test: add series studio end-to-end browser suite"
```

## Task 14: Final Integration Gate

**Purpose:** Confirm the optimized system is usable, production-controllable, and regression-safe.

**Files:**
- Modify: `docs/continuous-anime-production-optimization.md`
- Modify: `docs/superpowers/plans/2026-07-04-continuous-anime-series-studio.md`
- Test: all backend/frontend commands below.

- [x] **Step 1: Run backend regression**

Run:

```bash
cd backend && DEV_MODE=true PYTHONPATH=. python3 -m pytest -q
```

Expected: PASS. If full suite is too broad because of external provider tests, record the failing external tests and run the controlled target suite:

```bash
cd backend && DEV_MODE=true PYTHONPATH=. python3 -m pytest -q test_model_registry_story_bible.py test_novel_import_story_bible.py test_story_bible_auto_build.py test_workflow_routes.py tests/test_reference_package.py test_video_model_catalog.py tests/test_series_plan_service.py tests/test_episode_contract_service.py tests/test_consistency_ledger_service.py tests/test_production_bible_review.py
```

- [x] **Step 2: Run frontend static verification**

Run:

```bash
PATH="/Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH" /Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/pnpm --dir frontend typecheck
PATH="/Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH" /Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/pnpm --dir frontend build
```

Expected: both commands exit 0.

- [x] **Step 3: Run frontend all-scenario browser tests**

Run:

```bash
PATH="/Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH" /Users/sunqinyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/pnpm --dir frontend exec playwright test e2e/quick-start-series-plan.spec.ts e2e/series-studio-full-flow.spec.ts e2e/series-studio-production-bible.spec.ts e2e/series-studio-multi-episode.spec.ts e2e/series-studio-consistency-ledger.spec.ts e2e/series-studio-end-to-end.spec.ts e2e/studio-shot-review.spec.ts e2e/video-generation-preflight.spec.ts e2e/workflow-production-guidance.spec.ts e2e/top-navigation.spec.ts --project=chromium --workers=1
```

Expected: PASS. Store screenshots and traces outside the repo.

- [x] **Step 4: Run manual browser audit from frontend**

Use the frontend only. Do not call backend APIs directly except for health checks.

```text
1. Open /quick-start.
2. Fill a full-novel sample with at least 3 chapters, 2 characters, 2 scenes, 2 props, and dialogue.
3. Generate Episode 1.
4. Enter /studio through the success link.
5. Confirm first viewport shows Series Studio, readiness, next action, model strategy, and missing requirements.
6. Confirm Production Bible sections have style, characters, scenes, props, events, and voices.
7. Approve one character and one scene.
8. Lock Episode Contract.
9. Open shot review and confirm each shot shows bound/unbound entities, model strategy, fallback state, and reference package evidence.
10. Open workflow/producer drill-down and return to Studio.
11. Confirm console has no relevant error or framework overlay.
12. Capture desktop and mobile screenshots under /tmp/ai-video-platform-series-studio-e2e/.
```

- [x] **Step 5: Update outcome doc**

Append to `docs/continuous-anime-production-optimization.md`:

```md
## Series Studio V2 Verification

- Backend regression:
- Frontend typecheck:
- Frontend build:
- Playwright all-scenario suite:
- Manual browser audit screenshots:
- Known limitations:
```

Fill each line with actual command, date, and result from this task.

- [x] **Step 6: Final commit**

Run:

```bash
git add docs/continuous-anime-production-optimization.md docs/superpowers/plans/2026-07-04-continuous-anime-series-studio.md
git commit -m "docs: record series studio verification"
```

**Actual results, 2026-07-04:**

- Backend regression: `DEV_MODE=true PYTHONPATH=. python3 -m pytest -q` -> `637 passed, 2 skipped, 17 warnings in 32.80s`.
- Frontend typecheck: `pnpm --dir frontend typecheck` -> exit 0.
- Frontend build: `pnpm --dir frontend build` -> exit 0.
- Focused preflight regression: `e2e/video-generation-preflight.spec.ts --project=chromium --workers=1` -> `2 passed`.
- Frontend all-scenario browser suite: 10 spec matrix -> `22 passed`.
- Screenshots: `/tmp/ai-video-platform-series-studio-e2e/series-studio-overview.png`, `/tmp/ai-video-platform-series-studio-e2e/series-studio-mobile.png`.
- Known limitation: deterministic browser suite uses mocked backend/external model responses; real provider video/TTS/image calls were not invoked in this gate.

## Expected Outcomes

- **User threshold drops:** creators operate from one Studio, with expert pages hidden behind contextual drill-downs.
- **Consistency becomes tangible:** each character, scene, prop, event, and voice has a visible status, owner action, and production impact.
- **Multi-episode continuity becomes manageable:** Series Plan and Episode Contract show what each episode inherits and locks.
- **Professional quality becomes controllable:** draft/final model strategy, reference package mode, fallback state, and consistency scoring are visible before export.
- **Changes stay reversible:** P0 stores contracts in existing JSON fields and can be rolled back by disabling `SERIES_STUDIO_V2`.
- **Testing becomes user-realistic:** the final gate is browser-driven from `/quick-start`, with screenshots, console health, and all major production surfaces covered.

## Execution Options

Plan complete and saved to `docs/superpowers/plans/2026-07-04-continuous-anime-series-studio.md`. Two execution options:

1. **Subagent-Driven (recommended)** - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** - execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints.
