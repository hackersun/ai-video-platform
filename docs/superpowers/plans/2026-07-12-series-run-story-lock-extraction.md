# Series Run Story Lock Extraction Plan

## Execution Contract

**Intent Lock:** prepare Story Locks from the persisted anchor-required entity closure instead of blocking on every extracted novel candidate.

**Scope:** focused backend feature extraction, compatibility adapters, closure-aware UI evidence, deterministic acceptance, and one review-gated Wave 1 rerun.

**Out of scope:** Wave 2, budget increases, provider substitution, broad entity-schema redesign, and unrelated cleanup.

**Compatibility constraints:** preserve existing routes, response fields, persisted IDs/statuses, ownership, voice/model/reference snapshots, Task4/Task6/Task7 gates, append-only audit history, and no-future-leakage.

**Hotspot constraints:** no net line growth in `series_runs.py`, `series_run_live_preflight.py`, or `frontend/src/lib/api-client.ts`; Story Lock responsibilities must move out of the first two files. New production files <=500 lines, functions <=80 lines, routes <=60 lines, no endpoint-to-endpoint or service-to-endpoint imports.

**Acceptance:** required closure is smaller than the full candidate set; unrelated candidates do not block; ambiguous required facts return a redacted 409 with zero partial writes; deterministic UI reaches Story Lock and Task4 ready; full no-live runner passes; independent review approves before a capped live rerun.

**Decision point:** implementation and deterministic review are approved by the user's 2026-07-12 instruction. A live rerun is allowed only after all deterministic gates pass. Wave 2 remains prohibited.

## Task 1: Baseline And Characterization

- Record hashes, line counts, imports, Story Lock functions, and relevant test commands.
- Add failing characterization tests for the production-shaped 46-candidate extraction set:
  - two selected anchors produce a required closure smaller than all candidates;
  - unrelated candidates remain candidates and do not block;
  - ambiguous required facts block with zero writes;
  - response capture preserves only safe hashed detail.
- Verify RED for missing closure API/behavior.

## Task 2: Extract Domain And Repository

- Create `backend/app/features/series_run_story_locks/domain/` for closure and approval rules.
- Create a focused repository for owned run/chapter/shot/entity reads and atomic persistence.
- Domain code must be SQLAlchemy/FastAPI/provider independent.
- Preserve entity evidence, chapter provenance, identity compatibility, state/tag taxonomy, and no-future projection.
- Make Task 1 tests GREEN; run existing dialogue/timeline tests.

## Task 3: Extract Application Use Case And Compatibility Facade

- Create `application/prepare_story_locks.py` and `public.py`.
- Move transaction/versioning/orchestration from `series_run_live_preflight.py` into the feature.
- Keep existing endpoint and service imports compatible through thin delegation.
- Capture safe Story Lock response details for the runner before cleanup.
- `series_runs.py` and `series_run_live_preflight.py` must shrink in net lines.
- Run Story Lock, Task4, Task6, Task7, and Series Run regression groups.

## Task 4: Closure-Aware Workbench Evidence

- Add feature-scoped frontend types/API/hook/component rather than growing `api-client.ts` or the existing 300+ line panel.
- Display required versus unrelated candidate counts, auto-approved/unresolved/manual-review counts, closure hash, Story version, and safe blockers.
- Existing panel only composes the extracted component and may not grow in net lines.
- Add real FastAPI/SQLite Playwright coverage with no API interception.

## Task 5: Governance And Independent Review

- Run targeted backend tests, typecheck/build, Playwright, and `npm run verify:four-chapter`.
- Record before/after hashes and line counts, function sizes, dependency-direction checks, and `git diff --check`.
- Independent reviewer checks spec and quality; fix every Critical/Important finding and re-review.

## Task 6: Capped Live Re-entry

- Fresh Task6 staging, fake disabled, RMB10, two cross-episode anchors.
- Persist the exact Story Lock response status/redacted body before cleanup.
- Stop without retry on any provider-uncertain state or hard gate.
- Collect provider operations/tasks, costs, artifacts, evaluations, screenshots, and protected-baseline evidence.
- Wave 2 remains disabled.
