# Series Run Full Skill Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every AI-producing stage in the four-chapter series workflow consume the selected published Prompt Skill and persist truthful stage-to-artifact evidence.

**Architecture:** Keep canonical Prompt Profile routing as the only selector. Add a focused series-stage Skill execution owner that returns the rendered prompt plus immutable evidence; existing series services consume it without importing API endpoints. Deterministic test mode remains provider-free and is explicitly labelled, while provider-backed stages retain their existing model and budget gates.

**Tech Stack:** FastAPI, async SQLAlchemy, Prompt Profiles, Next.js 14, React, pytest, Playwright.

## Global Constraints

- Preserve existing routes, response fields, stored runs, model bindings, budget rules and retry semantics.
- Manual CRUD does not require Prompt Skill execution; AI and automatic-production actions do.
- Never report a Skill as applied unless a rendered prompt is bound to a concrete artifact or provider request.
- Persist only sanitized prompt hashes and version identifiers in run-level evidence; artifact-local records may retain rendered prompts where existing schemas already store source prompts.
- Do not call paid providers in automated tests.
- Do not grow legacy hotspot endpoint files; new rules belong to focused application modules.

---

### Task 1: Published-version activation consistency

**Files:**
- Modify: `backend/app/services/prompt_skill_service.py`
- Modify: `backend/app/features/prompt_profiles/versioning.py`
- Test: `backend/tests/test_prompt_skill_published_version.py`

**Interfaces:**
- Consumes: `edit_legacy_prompt_profile`, `publish_prompt_profile_version`.
- Produces: active legacy Skill rows whose `version`, `content` and `prompt_profile_version_id` match the selected published profile version.

- [x] Write a failing test proving an edit to an active Skill publishes the new draft atomically and routing returns the same version shown by the Skill record.
- [x] Run `pytest -q backend/tests/test_prompt_skill_published_version.py` and confirm the selected version remains stale.
- [x] Publish the newly-created draft when an active Skill is saved as active; apply that version back to the legacy projection.
- [x] Re-run the targeted test and the existing Prompt Profile versioning tests.

### Task 2: Canonical series-stage Skill evidence

**Files:**
- Create: `backend/app/features/series_skill_execution/domain.py`
- Create: `backend/app/features/series_skill_execution/application.py`
- Create: `backend/app/features/series_skill_execution/public.py`
- Modify: `backend/app/services/series_run_skill_routing.py`
- Test: `backend/tests/test_series_skill_execution.py`

**Interfaces:**
- Produces: `bind_series_stage_skill(...) -> dict` containing `rendered_prompt`, `artifact_evidence` and the exact published profile version.
- Evidence fields: `id`, `name`, `version`, `profile_version_id`, `routing_reason`, `execution_mode`, `rendered_prompt_sha256`, `artifact_type`, `artifact_id`.

- [x] Write failing tests for required Skill selection, deterministic rendered-prompt binding, sanitized hash evidence and missing-Skill failure.
- [x] Implement the focused binding owner using `select_prompt_skill_for_model`.
- [x] Keep rendered prompt out of run-level metadata and expose it only to the immediate artifact creator.
- [x] Run the new tests.

### Task 3: Script and entity stages

**Files:**
- Modify: `backend/app/services/episode_production_service.py`
- Modify: `backend/app/services/entity_review_service.py`
- Test: `backend/tests/test_series_run_skill_routing.py`

**Interfaces:**
- Script artifacts store exact Skill version, rendered-prompt hash and deterministic/provider execution mode.
- Entity extraction runs store the rendered-prompt hash and must not claim model execution when using deterministic classification.

- [x] Extend tests to fail unless script and entity evidence is artifact-bound and execution mode is truthful.
- [x] Replace evidence-only routing with the canonical binding owner.
- [x] Preserve deterministic entity extraction but label it `deterministic_skill_contract`; provider candidate input remains `provider_model`.
- [x] Run series Skill and entity-review tests.

### Task 4: Storyboard and shot stages

**Files:**
- Modify: `backend/app/services/episode_production_service.py`
- Modify: `backend/app/services/episode_shot_stage.py`
- Test: `backend/tests/test_series_run_skill_routing.py`

**Interfaces:**
- Storyboard content stores `prompt_skill` evidence for `storyboard_generation`.
- Every new shot stores `prompt_skill` evidence for `shot_prompt`; its production prompt is composed from the rendered Skill and scoped story source.

- [x] Add failing tests for missing storyboard and shot evidence and for the rendered Skill affecting the stored shot prompt.
- [x] Bind `storyboard_generation` when the storyboard artifact is created.
- [x] Bind `shot_prompt` before constructing each canonical shot.
- [x] Aggregate both stages into `run_metadata.skill_evidence`.
- [x] Run the series Skill tests and shot-stage contract tests.

### Task 5: Reference asset and native-audio video stages

**Files:**
- Modify: `backend/app/services/default_prompt_skills.py`
- Modify: `backend/app/services/series_run_reference_preparation.py`
- Modify: `backend/app/features/video_generation/application/consistency_package.py`
- Test: `backend/tests/test_series_run_live_preflight_plan.py`
- Test: `backend/tests/test_seedance_native_audio_submission.py`

**Interfaces:**
- New task `series_reference_board`, stage `asset`, owns multi-character composite layout prompts.
- Native-audio requests select `shot_audio_video`; silent/separate-audio requests select `shot_video`.

- [x] Add failing tests for composite-reference Skill evidence and native-audio task selection.
- [x] Add and route the built-in composite-reference Skill before provider submission.
- [x] Persist its selected profile version and rendered-prompt hash on the Asset and provider operation evidence.
- [x] Select `shot_audio_video` for Seedance native-audio prompt composition while preserving visual continuity blocks.
- [x] Run the targeted reference and native-audio tests.

### Task 6: Workbench evidence and front-end acceptance

**Files:**
- Create: `frontend/src/features/series-runs/components/skill-evidence-grid.tsx`
- Modify: `frontend/src/features/series-runs/series-run-view.tsx`
- Modify: `frontend/e2e/sunqy-skill-routing-acceptance.spec.ts`

**Interfaces:**
- Consumes `run.run_metadata.skill_evidence`.
- Displays script, entity, storyboard, shot, reference asset and video/native-audio stages with version, execution mode and missing-evidence warning.

- [x] Add a failing component/E2E assertion for all six stage cards and a clear missing-evidence state.
- [x] Extract a focused evidence-grid component and keep `series-run-view.tsx` below its task-start size.
- [x] Validate front-end rendering with fixture evidence and the existing four-chapter run.
- [x] Run frontend typecheck/build and browser-facing acceptance.

### Task 7: Integrated verification

**Files:**
- Modify only tests required to align truthful execution-mode assertions.

- [x] Run focused backend Skill, series run, reference and video tests.
- [x] Run `git diff --check` and project code-health checks.
- [x] Run frontend build and browser-facing workflow acceptance.
- [x] Report any pre-existing full-suite failures separately; do not mark them fixed without evidence.
