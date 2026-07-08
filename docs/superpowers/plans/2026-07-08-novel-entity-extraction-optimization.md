# Novel Entity Extraction Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a low-risk, evidence-backed, AI-assisted novel asset analysis pipeline that extracts characters, scenes, props, and events with much less garbage while keeping existing production flows stable.

**Architecture:** Keep the current `StoryEntity -> StoryBible -> ProductionCard -> Asset` path as the production spine. First centralize `StoryEntity` lifecycle state and query access, then add extraction runs, source mentions, feedback logs, quality scoring, model-aware prompt template routing, targeted entity enrichment, and a polished AI review UI around it; new uncertain entities stay in candidate state and do not affect video/storyboard generation until approved or explicitly promoted.

**Tech Stack:** FastAPI, async SQLAlchemy, SQLite/PostgreSQL-compatible models, Pydantic schemas, existing Qwen/DashScope and Volcano text model adapters, Next.js 14, React 18, TypeScript, Tailwind CSS, Radix UI, lucide-react, pytest, npm build.

---

## Intent Lock

Improve extraction quality by changing the workflow from "AI writes directly into production assets" to "AI proposes evidence-backed candidates, the system scores and cleans them, and users approve only what should affect production."

## Assumptions

- Existing character, entity, story bible, asset, storyboard, shot, video, and TTS flows must remain usable during the rollout.
- The first release should prefer additive tables and endpoint behavior flags over destructive schema changes.
- Existing `StoryEntity` records without a candidate marker are treated as active legacy entities so old projects do not suddenly lose context.
- New extracted entities are candidates by default unless they meet strict auto-approval rules.
- AI automation is allowed for low-risk cleanups and suggestions, but deleting or altering approved/referenced production entities requires user confirmation.
- Existing Prompt Skill templates are task-based; this plan upgrades selection to account for provider, model, capability, output contract, and historical quality without breaking the current task-only behavior.
- Every extraction path, including bulk asset extraction, single character extraction, single prop extraction, and targeted enrichment, must pass through Prompt Skill routing when an AI model is used.
- Users need a targeted mode where they can specify entity type and name, then ask AI to fill missing details for that entity without full re-extraction or destructive overwrite.

## Scope Boundaries

In scope:

- Entity extraction quality, evidence grounding, duplicate reduction, review, approval, feedback, and asset-readiness handoff.
- Centralized `StoryEntity` lifecycle, visibility, and query gateway used by all production consumers.
- Model-aware Prompt Skill routing for entity extraction and asset prompt generation.
- Targeted extraction/enrichment by entity type and name, with merge-only updates for selected fields.
- A simple but polished frontend flow for one-click analysis, review, merge, approve, clean, and asset generation.
- Minimal integration with current `characters/extract`, `story-bibles/entities/*`, `production-cards`, and `assets/reextract`.

Out of scope for this plan:

- Rebuilding the full Story Bible model from scratch.
- Replacing all existing prompt generation or video generation flows.
- Training a custom model.
- Introducing Neo4j/Milvus as a hard dependency for this release.
- Changing final video, TTS, or timeline rendering behavior except where entity references are read.

## Success Metrics

- Evidence coverage: at least 95% of newly persisted candidates have chapter/source scope plus quoted evidence.
- Garbage reduction: test fixtures show at least 50% fewer invalid character/scene/prop candidates than the current direct extraction path.
- Duplicate reduction: same-scope duplicate canonical entities stay below 10% on fixture novels.
- Production safety: no candidate entity is used by shot/video generation unless it is approved, legacy-active, or explicitly included for preview.
- Query safety: all production consumers load entities through the shared lifecycle/query helper rather than ad hoc `select(StoryEntity)` calls.
- Targeted enrichment: users can enrich one named character/scene/prop/event without overwriting unrelated entities or running full extraction.
- UX speed: a user can run full novel analysis, review high-risk candidates, approve clean entities, and start asset generation from one page.
- Prompt routing: extraction runs record the selected prompt skill, provider/model, output contract, parse success, and fallback reason when a model-specific template is not used.
- Regression safety: existing character pages, entities page, story bible generation, production cards, and asset generation still pass smoke tests.

## File Impact Map

Backend models:

- Modify `backend/app/models/story_entity.py` to document and consistently use `extra_data.review_status`, `extra_data.quality`, `extra_data.extraction_run_id`, and `extra_data.auto_decision`.
- Create `backend/app/models/entity_extraction_run.py` for run metadata, prompt version, model config, text hash, metrics, status, and summary.
- Create `backend/app/models/story_entity_mention.py` for evidence spans, source scope, raw mention text, offsets, confidence, and run linkage.
- Create `backend/app/models/entity_feedback.py` for user corrections, approvals, deletes, merges, type changes, and prompt-improvement examples.
- Modify `backend/app/models/prompt_skill.py` to add optional routing metadata in a backwards-compatible way: `provider_filter`, `model_filter`, `capability_filter`, `output_contract`, `quality_score`, `parse_success_rate`, and `garbage_rate`.
- Modify `backend/app/models/__init__.py` to export the new models.

Backend services:

- Create `backend/app/services/story_entity_lifecycle.py` for review status constants, visibility checks, lifecycle transitions, and safe query helpers.
- Create `backend/app/services/entity_extraction_schema.py` for canonical Pydantic schemas shared by AI parsing, deterministic extraction, and tests.
- Create `backend/app/services/entity_quality_service.py` for scoring, noise checks, auto-approval decisions, and duplicate-risk flags.
- Create `backend/app/services/entity_review_service.py` for candidate promotion, soft rejection, merge suggestions, feedback persistence, and review summaries.
- Create `backend/app/services/entity_targeted_enrichment_service.py` for type/name-scoped detail enrichment and merge-only updates.
- Create `backend/app/services/prompt_template_router.py` for selecting Prompt Skills by task, provider, model, capabilities, output contract, and historical quality.
- Modify `backend/app/services/entity_extraction_service.py` to return evidence-aware normalized candidates without directly assuming production readiness.
- Modify `backend/app/services/prompt_skill_service.py` so existing task-only selection still works, while extraction and asset generation can opt into model-aware routing.
- Modify `backend/app/services/consistency_context.py` so generation ignores new candidate-only entities unless explicitly requested.
- Modify `backend/app/services/production_card_service.py` only to surface candidate/approved readiness metadata; do not change final asset rules in the first release.

Backend endpoints:

- Modify `backend/app/api/v1/endpoints/story_bible.py` to add run, review, promote, reject, merge-suggestion, feedback, and quality-summary APIs under existing `/story-bibles/entities`.
- Add `POST /story-bibles/entities/enrich-target` for type/name-scoped extraction and non-destructive field enrichment.
- Modify `backend/app/api/v1/endpoints/characters.py` so `/characters/extract` keeps compatibility but can route to the safer candidate pipeline when requested by the frontend.
- Modify `backend/app/api/v1/endpoints/assets.py` to block candidate-only entities from asset generation unless the request explicitly includes `allow_candidate_assets=true` in dev/test flows.
- Modify `backend/app/api/v1/endpoints/prompt_skills.py` to expose routing metadata, routing preview, and template performance fields.

Frontend:

- Modify `frontend/src/lib/api-client.ts` to add methods for analysis runs, review summaries, candidate promotion/rejection, feedback, merge suggestions, and safe character extraction.
- Create `frontend/src/app/novels/[id]/asset-analysis/page.tsx` as the simple one-page AI asset analysis console.
- Modify `frontend/src/app/novels/[id]/page.tsx` to add the primary "AI 分析制作资产" entry point and surface extraction health.
- Modify `frontend/src/app/entities/page.tsx` to reuse review status, quality score, evidence, and one-click approval controls without replacing the existing management page.
- Modify `frontend/src/app/prompt-skills/page.tsx` to show provider/model/capability filters, output contract, parse success rate, garbage rate, and a "preview route for selected model" action.
- Add focused components under `frontend/src/components/entity-review/` for KPI strip, run controls, candidate list, evidence panel, action rail, and asset gap panel.

Tests:

- Create `backend/tests/test_entity_extraction_quality.py`.
- Create `backend/tests/test_entity_review_service.py`.
- Create `backend/tests/test_story_entity_lifecycle.py`.
- Create `backend/tests/test_entity_targeted_enrichment.py`.
- Create `backend/tests/test_prompt_skill_routing.py`.
- Modify existing entity/story bible tests only where new candidate filtering affects behavior.
- Add frontend build verification; add Playwright smoke only if the repo already has a working Playwright setup for this app.

---

## Phase 0: Baseline And Rollout Guardrails

**Goal:** Measure current behavior and create a no-surprises rollout path.

**Impact:** No user-facing behavior change.

- [ ] Record current extraction flows and entry points:
  - `/characters/extract`
  - `/story-bibles/entities/extract`
  - `/story-bibles/entities/reextract`
  - `/assets/reextract`
  - `/production-cards/novel/{novel_id}`
- [ ] Add a feature flag helper named `ENTITY_EXTRACTION_V2_ENABLED`, defaulting to disabled unless the frontend calls the new endpoint or a dev env var enables it.
- [ ] Prepare 3 to 5 fixture texts in tests:
  - named protagonist and supporting characters
  - group words that must not become characters
  - concrete scenes
  - concrete props
  - events with state changes
  - misleading production-copy terms such as "视觉钩", "推镜", "字幕"
- [ ] Add baseline tests that capture the current deterministic extractor output and mark known bad outputs as regression targets for the new scorer.
- [ ] Verification:
  - `cd backend && pytest tests/test_entity_extraction_quality.py -v`
  - Expected before implementation: new tests fail or are skipped only where new service modules do not exist.

## Phase 1: Evidence-Backed Extraction Data Layer

**Goal:** Add run, mention, and feedback tracking without changing existing production entity behavior.

**Impact:** Additive database objects; no existing columns removed or renamed.

- [ ] Create `EntityExtractionRun` with fields:
  - `id`, `user_id`, `novel_id`, `chapter_id`, `script_id`
  - `source_type`, `source_id`, `text_hash`
  - `entity_types`, `model_config_id`, `provider`, `model_id`
  - `prompt_version`, `status`, `started_at`, `completed_at`
  - `stats`, `quality_summary`, `extra_data`
- [ ] Create `StoryEntityMention` with fields:
  - `id`, `user_id`, `run_id`, `entity_id`
  - `novel_id`, `chapter_id`, `script_id`
  - `source_type`, `source_id`
  - `mention_text`, `evidence`, `char_start`, `char_end`
  - `confidence`, `extractor`, `extra_data`
- [ ] Create `EntityFeedback` with fields:
  - `id`, `user_id`, `entity_id`, `run_id`
  - `action`, `before_data`, `after_data`
  - `reason`, `created_at`, `extra_data`
- [ ] Export models from `backend/app/models/__init__.py`.
- [ ] Keep the project’s current table initialization pattern; do not introduce a migration framework in this task.
- [ ] Verification:
  - `cd backend && python - <<'PY'\nfrom app.models import EntityExtractionRun, StoryEntityMention, EntityFeedback\nprint(EntityExtractionRun.__tablename__, StoryEntityMention.__tablename__, EntityFeedback.__tablename__)\nPY`
  - Expected: prints the three table names.

## Phase 1.5: Unified StoryEntity Lifecycle And Query Gateway

**Goal:** Make every production consumer use one lifecycle and visibility contract before extraction quality work expands the number of candidate entities.

**Impact:** Low-to-medium backend behavior change. Existing legacy entities remain visible, while newly introduced candidate/rejected entities are consistently excluded from production contexts.

Lifecycle contract:

- [ ] Define review states in `backend/app/services/story_entity_lifecycle.py`:
  - `legacy_active`: entity has no explicit review state and should behave like current data.
  - `candidate`: newly extracted, reviewable, not production-visible by default.
  - `approved`: accepted for Story Bible, production cards, assets, shots, and prompts.
  - `rejected`: retained for feedback/eval, hidden from production.
  - `archived`: retained for history, hidden from production and review defaults.
- [ ] Add helper functions:
  - `get_entity_review_status(entity) -> str`
  - `set_entity_review_status(entity, status, reason=None) -> None`
  - `is_entity_reviewable(entity) -> bool`
  - `is_entity_production_visible(entity) -> bool`
  - `is_entity_asset_generation_allowed(entity, allow_candidate_assets=False) -> bool`
  - `story_entity_visibility_filter(include_candidates=False, include_rejected=False, include_archived=False)`
- [ ] Treat `StoryEntity.is_approved=True` as approved even if `extra_data.review_status` is missing.
- [ ] Treat missing `extra_data.review_status` plus `is_approved=False` as `legacy_active`, not candidate, to avoid breaking old projects.
- [ ] Update lifecycle transitions to store metadata in `StoryEntity.extra_data.lifecycle`:
  - `status`
  - `changed_at`
  - `changed_by`
  - `reason`
  - `previous_status`

Query gateway:

- [ ] Add safe query helpers:
  - `query_story_entities_for_review(...)`
  - `query_story_entities_for_production(...)`
  - `query_story_entities_for_assets(...)`
  - `query_story_entities_for_prompt_context(...)`
- [ ] Use the query gateway in:
  - `backend/app/services/consistency_context.py`
  - `backend/app/services/story_prompt_context.py`
  - `backend/app/services/production_control.py`
  - `backend/app/services/production_bible.py`
  - `backend/app/services/production_card_service.py`
  - `backend/app/services/series_production.py`
  - `backend/app/services/novel_continuity.py`
  - `backend/app/services/short_video_production.py`
  - `backend/app/api/v1/endpoints/assets.py`
  - `backend/app/api/v1/endpoints/chapters.py`
- [ ] Keep explicit review/admin endpoints able to include candidates.
- [ ] Add a temporary test assertion that scans critical services for direct `select(StoryEntity)` usages and lists allowed exceptions. This can start as a focused test over known files rather than a broad linter.

Verification:

- `cd backend && pytest tests/test_story_entity_lifecycle.py -v`
- Expected:
  - old entities with no status remain production-visible.
  - candidate entities are visible in review queries but hidden in production queries.
  - approved entities are visible everywhere relevant.
  - rejected and archived entities do not appear in prompt, asset, or production-pack queries.

## Phase 2: Canonical Extraction Schema And Quality Scoring

**Goal:** Make every extraction result pass through one schema and one quality gate.

**Impact:** Existing deterministic extraction can continue, but new persistence paths get richer metadata.

- [ ] Define canonical candidate schema in `entity_extraction_schema.py`:
  - `entity_type`
  - `name`
  - `canonical_name`
  - `aliases`
  - `description`
  - `appearance`
  - `visual_prompt`
  - `attributes`
  - `relations`
  - `state_changes`
  - `evidence`
  - `source_scope`
  - `confidence`
  - `source`
- [ ] Define mention schema:
  - source type, source id, chapter id, evidence text, character offsets when known, confidence.
- [ ] Add `entity_quality_service.py` with deterministic scoring:
  - required evidence score
  - name-shape score
  - type-boundary score
  - duplicate risk
  - production usefulness score
  - auto decision: `auto_approve`, `needs_review`, `reject_noise`
- [ ] Use existing negative rules from `entity_extraction_service.py` as first-class scorer rules rather than scattering them only in regex normalization.
- [ ] Never hard-delete noise on extraction; store rejected candidates only when needed for feedback/evals, or omit them from `StoryEntity` and keep them in run stats.
- [ ] Verification:
  - `cd backend && pytest tests/test_entity_extraction_quality.py -v`
  - Expected: fixture noise terms are rejected or marked `reject_noise`; concrete named entities are `needs_review` or `auto_approve`.

## Phase 3: AI Structured Extraction Adapter

**Goal:** Use AI for richer extraction while keeping deterministic fallback and strict validation.

**Impact:** Existing Qwen/DashScope model configuration is reused; no new provider is mandatory.

- [ ] Add an AI extraction adapter inside `entity_extraction_service.py` or a focused helper file.
- [ ] Prompt the model for JSON matching the canonical schema; include explicit negative classification rules and evidence requirements.
- [ ] Parse through Pydantic; invalid records are not persisted and are counted in run stats.
- [ ] Prefer provider structured output when available:
  - Qwen/DashScope JSON mode when configured.
  - Volcano JSON Schema when configured.
  - Existing plain JSON parsing fallback when provider capabilities are unknown.
- [ ] Add one repair retry only when JSON parsing fails; do not loop indefinitely.
- [ ] Merge deterministic and AI outputs by canonical key and evidence, with scorer deciding whether to keep, review, or reject.
- [ ] Verification:
  - `cd backend && pytest tests/test_entity_extraction_quality.py::test_ai_schema_parse_rejects_invalid_records -v`
  - Expected: malformed or evidence-free records do not become production candidates.

## Phase 3.5: Model-Aware Prompt Template Routing

**Goal:** Choose the best active prompt template for the current task and model instead of using only one task-level template.

**Impact:** Backwards-compatible Prompt Skill upgrade. Existing task-only templates continue to work; model-aware routing is opt-in for extraction and asset-generation paths first.

Current state:

- `story-bibles/entities/extract` already wraps its internal entity extraction prompt with the active `entity_extraction` Prompt Skill when a text model config is provided.
- `asset_generation_service.py` already wraps character, scene, and prop image prompts with task-specific Prompt Skills.
- `/characters/extract` still uses hardcoded prompts and should be migrated through safe mode.
- Prompt Skill selection currently prefers one active user template for a task, then one built-in template for that task. It does not inspect provider, model, JSON capability, schema capability, context length, or historical quality.

Routing metadata:

- [ ] Add optional `PromptSkill` metadata fields:
  - `provider_filter`: list such as `["volcano", "dashscope", "minimax", "openai"]`.
  - `model_filter`: list of exact model IDs or simple wildcard strings such as `["qwen-*", "doubao-*"]`.
  - `capability_filter`: list such as `["json_mode", "json_schema", "long_context", "vision_input"]`.
  - `output_contract`: one of `plain_text`, `json_object`, `json_array`, `json_schema`.
  - `quality_score`: numeric score updated from evals and feedback.
  - `parse_success_rate`: numeric ratio from extraction runs.
  - `garbage_rate`: numeric ratio from user rejections and scorer rejects.
- [ ] Store these fields as nullable columns or inside a `routing` JSON object if the project wants minimum schema churn; keep the old `task`, `stage`, `priority`, and `is_active` semantics intact.

Router behavior:

- [ ] Create `select_prompt_skill_for_model(...)` in `backend/app/services/prompt_template_router.py`.
- [ ] Inputs:
  - `task`
  - `provider_name`
  - `model_id`
  - `model_capabilities`
  - `output_contract`
  - `user_id`
  - `context`
- [ ] Selection order:
  - active user-owned template with matching task and strongest provider/model/capability match
  - active built-in template with matching task and strongest provider/model/capability match
  - active task-only user template
  - active task-only built-in template
  - internal prompt fallback
- [ ] Tie-breakers:
  - higher `quality_score`
  - lower `garbage_rate`
  - higher `parse_success_rate`
  - lower `priority`
  - newer `version`
- [ ] Return selected template metadata with every wrapped prompt:
  - `prompt_skill_id`
  - `prompt_skill_name`
  - `prompt_skill_version`
  - `routing_reason`
  - `fallback_reason`
  - `output_contract`

Template families:

- [ ] Built-in `entity_extraction` templates:
  - `entity_extraction.schema.volcano`: optimized for Volcano JSON Schema when available.
  - `entity_extraction.json.dashscope`: optimized for Qwen/DashScope JSON mode.
  - `entity_extraction.generic`: conservative plain JSON fallback.
- [ ] Built-in asset prompt templates:
  - `character_image.provider_safe`: compact visual DNA and reference requirements for providers sensitive to long prompts.
  - `scene_reference_image.provider_safe`: emphasizes layout, lighting, weather, and reusable scene identity.
  - `prop_image.provider_safe`: emphasizes material, scale, state, and in-use constraints.
- [ ] Do not make MiniMax-specific entity extraction templates unless a configured MiniMax text model is actually present in `LLMModel`; MiniMax is currently more relevant to voice/TTS flows in this project.

Integration points:

- [ ] Use model-aware routing in `story_bible.py` entity extraction before calling `safe_chat_completion`.
- [ ] Use model-aware routing in `asset_generation_service.py` before generating character, scene, and prop prompts.
- [ ] Use model-aware routing when `/characters/extract` runs in `safe_mode=true`; legacy mode keeps its existing prompt for compatibility.
- [ ] Use model-aware routing for all entity/asset extraction entry points:
  - `/story-bibles/entities/extract`
  - `/story-bibles/entities/extract-assets`
  - `/story-bibles/entities/reextract`
  - `/story-bibles/entities/enrich-target`
  - `/characters/extract` when `safe_mode=true`
  - asset page single character/scene/prop generation when it asks AI to derive prompt text from story context
- [ ] Add a backend test that fails if new AI extraction code calls `safe_chat_completion` without prompt routing metadata.
- [ ] Record routing metadata on `EntityExtractionRun.extra_data.prompt_routing`.
- [ ] Record routing metadata on generated `Asset.generation_params.prompt_routing`.

Verification:

- `cd backend && pytest tests/test_prompt_skill_routing.py -v`
- Expected:
  - DashScope JSON-mode config selects the DashScope JSON template.
  - Volcano JSON-schema-capable config selects the Volcano schema template.
  - Unknown provider falls back to the generic task template.
  - User-owned matching templates beat built-in templates.
  - Existing task-only templates are still selected when no provider-aware match exists.

## Phase 3.6: Targeted Entity Enrichment

**Goal:** Let users specify an entity type and name, then ask AI to extract or complete only that entity's missing details without full extraction or overwrite.

**Impact:** Additive and low-risk. This feature writes merge-only candidate updates unless the user explicitly promotes or applies them.

Use cases:

- User enters `character + 沈砚` and asks AI to补充外貌、身份、性格、声线、别名、关系、首次出场.
- User enters `prop + 铜铃` and asks AI to补充材质、外形、归属、状态变化、首次出现、相关事件.
- User enters `scene + 旧码头` and asks AI to补充空间布局、天气、光影、常用镜头、关键道具.
- User enters `event + 铜铃响起` and asks AI to补充参与角色、地点、道具、因果、状态变化.

Request contract:

- [ ] Add `TargetedEntityEnrichmentRequest`:
  - `novel_id`
  - `chapter_id`
  - `script_id`
  - `text`
  - `entity_type`
  - `entity_name`
  - `target_entity_id`
  - `fields`: allowed values include `description`, `appearance`, `visual_prompt`, `aliases`, `relations`, `state_changes`, `attributes`, `evidence`, `tags`, `voice_profile`, `visual_dna`.
  - `mode`: `preview`, `merge_candidate`, `apply_to_candidate`, `apply_to_approved_requires_confirmation`.
  - `model_config_id`
- [ ] Add `TargetedEntityEnrichmentResponse`:
  - `target`
  - `matched_entity`
  - `proposed_patch`
  - `evidence_mentions`
  - `quality`
  - `prompt_routing`
  - `merge_policy`
  - `warnings`

Prompt behavior:

- [ ] Always use model-aware Prompt Skill routing with task `entity_extraction` and stage `targeted_enrichment`.
- [ ] Include `entity_type`, `entity_name`, `fields`, existing entity data, and source content in the routing context.
- [ ] Require the model to return only information about the specified entity. Mentions of unrelated entities can appear only as relationships or evidence context.
- [ ] Require quoted evidence for every proposed field when possible.
- [ ] If the model finds that the target name is likely wrong, return `warnings` and do not create a new production entity automatically.

Merge behavior:

- [ ] Default mode is non-destructive:
  - append missing aliases
  - append new relations with evidence
  - append state changes with chapter/source scope
  - fill empty scalar fields
  - never replace existing approved scalar fields without explicit confirmation
- [ ] For approved entities, write proposed changes as a pending patch in `extra_data.pending_enrichment` unless the request explicitly confirms application.
- [ ] For candidate entities, apply safe merge fields directly and keep review status as candidate unless the quality gate auto-approves.
- [ ] For no matched entity:
  - create a candidate with `extra_data.review_status="candidate"` and `extra_data.enrichment_target=true`
  - do not create `Character` or `Asset`
- [ ] Every enrichment writes `EntityFeedback` with action `targeted_enrichment`.

Endpoint:

- [ ] Implement `POST /story-bibles/entities/enrich-target`.
- [ ] Add a companion preview action in the asset-analysis page and entity detail drawer:
  - "补充这个角色"
  - "补充这个场景"
  - "补充这个道具"
  - "补充这个事件"
- [ ] Add a compact field selector so users can ask for only `外貌/关系/状态/视觉DNA/声线` instead of all fields.

Verification:

- `cd backend && pytest tests/test_entity_targeted_enrichment.py -v`
- Expected:
  - enriching `character + 沈砚` does not create scene/prop/event candidates.
  - approved scalar fields are not overwritten without confirmation.
  - aliases, relations, and state changes merge instead of replacing arrays.
  - no matched target creates a candidate, not a production-visible entity.
  - prompt routing metadata is stored for each enrichment run.

## Phase 4: Candidate Persistence And Production Safety

**Goal:** Persist new extraction results without polluting storyboard/video/asset generation.

**Impact:** This is the first behavior-affecting backend change; guard with tests and feature flag.

- [ ] In `_extract_and_optionally_persist`, mark new v2 outputs with:
  - `extra_data.review_status = "candidate"` for uncertain candidates
  - `extra_data.review_status = "approved"` for strict auto-approved candidates
  - `extra_data.extraction_run_id`
  - `extra_data.quality`
  - `extra_data.auto_decision`
- [ ] Treat pre-existing entities without `extra_data.review_status` as `legacy_active`.
- [ ] Update `consistency_context.load_or_extract_story_entities` to exclude only new `candidate` and `rejected` entities from production generation by default.
- [ ] Add an explicit internal option `include_candidates=True` only for preview/review endpoints.
- [ ] Update `/assets/reextract` to skip new candidate-only entities by default and return a clear skipped reason.
- [ ] Verification:
  - `cd backend && pytest tests/test_entity_review_service.py::test_candidate_entities_do_not_enter_generation_context -v`
  - Expected: legacy entities still load; new candidates are excluded until approved.

## Phase 5: Review, Feedback, And Merge APIs

**Goal:** Give the frontend simple operations that generate durable learning signals.

**Impact:** Additive endpoints under existing Story Bible entity namespace.

- [ ] Add `GET /story-bibles/entities/runs/{run_id}` for run summary, stats, and candidate counts.
- [ ] Add `GET /story-bibles/entities/review-summary?novel_id=...` for:
  - candidate count
  - approved count
  - rejected count
  - duplicate-risk count
  - missing-evidence count
  - asset-gap count
  - recommended next action
- [ ] Add `POST /story-bibles/entities/{entity_id}/promote`:
  - sets review status approved
  - sets `is_approved=true`
  - writes feedback action `approve`
  - optionally syncs to Story Bible rules
- [ ] Add `POST /story-bibles/entities/{entity_id}/reject`:
  - sets review status rejected
  - writes feedback action `reject`
  - does not delete referenced assets or existing approved entities
- [ ] Add `POST /story-bibles/entities/merge-suggestions`:
  - returns candidate duplicate groups with reasons
  - does not merge automatically
- [ ] Extend existing merge endpoint to write feedback records for source and target entities.
- [ ] Verification:
  - `cd backend && pytest tests/test_entity_review_service.py -v`
  - Expected: approve, reject, merge, and feedback logs behave atomically.

## Phase 6: Compatibility With Existing Character Extraction

**Goal:** Reduce direct pollution from `/characters/extract` without breaking users who still rely on it.

**Impact:** Controlled compatibility behavior.

- [ ] Keep `/characters/extract` response shape unchanged for legacy callers.
- [ ] Add request flag `safe_mode=true`.
- [ ] When `safe_mode=true`, route extraction through the candidate pipeline and return only promoted/auto-approved character-compatible results.
- [ ] In the frontend character page, change "AI提取角色" to call safe mode by default when a `novel_id` or `chapter_id` is available.
- [ ] Keep a secondary "兼容旧方式提取" action hidden behind an advanced menu for users who need old behavior.
- [ ] Verification:
  - `cd backend && pytest tests/test_entity_review_service.py::test_character_extract_safe_mode_does_not_upsert_noise -v`
  - `cd frontend && npm run build`
  - Expected: character page builds and safe extraction does not create unknown/noise characters.

## Phase 7: AI Asset Analysis Console Frontend

**Goal:** Provide one simple, attractive, low-friction page for analysis and cleanup.

**Impact:** Additive page; existing `/entities`, `/characters`, `/assets`, and `/story-bibles` pages stay available.

Route:

- `frontend/src/app/novels/[id]/asset-analysis/page.tsx`

Design:

- Dense production-tool layout, not a marketing page.
- Top band: novel title, extraction health score, entity counts, asset readiness, last analysis time.
- Primary action: icon button with label "AI 分析制作资产".
- Secondary actions: "智能清理候选", "合并建议", "生成缺失资产", "同步 Story Bible".
- Tabs:
  - 全部
  - 角色
  - 场景
  - 道具
  - 事件
  - 待处理
  - 已定稿
- Main area:
  - left: filterable candidate list with confidence, review status, evidence coverage, asset gaps
  - right: evidence and AI explanation panel with source excerpt, suggested action, merge candidates, asset requirements
- Action rail:
  - approve
  - reject
  - edit
  - merge
  - generate assets
  - mark needs rewrite
- Use lucide icons for action buttons.
- Avoid nested cards; use full-width bands, compact panels, tables, and side drawer behavior.
- Preserve current dark admin style if that is the dominant existing UI pattern.

Components:

- `EntityReviewKpiStrip`
- `EntityAnalysisRunButton`
- `EntityCandidateTable`
- `EntityEvidencePanel`
- `EntityActionRail`
- `EntityMergeSuggestionDialog`
- `EntityAssetGapPanel`

Verification:

- `cd frontend && npm run build`
- Manual desktop check:
  - `/novels/{novel_id}/asset-analysis` loads with no analysis run.
  - "AI 分析制作资产" starts a run.
  - Review actions update counts without page reload.
  - Long names and evidence excerpts do not overflow.

## Phase 8: Novel Detail Integration And Automation

**Goal:** Let users reach the new workflow from where they naturally are.

**Impact:** Small UI changes to existing novel detail page.

- [ ] Add a visible "AI 分析制作资产" action on `frontend/src/app/novels/[id]/page.tsx`.
- [ ] Add extraction health summary:
  - characters/scenes/props/events
  - pending candidates
  - approved production entities
  - missing asset packs
- [ ] Add "recommended next action" from the review summary:
  - run analysis
  - review candidates
  - approve clean entities
  - generate missing assets
  - sync story bible
- [ ] Do not remove existing Story Bible, character, chapter, or asset actions.
- [ ] Verification:
  - `cd frontend && npm run build`
  - Expected: novel detail remains usable and the new action links to the analysis console with the correct novel id.

## Phase 9: Smart Automation Rules

**Goal:** Make the optimized workflow feel automatic while keeping destructive actions explicit.

**Impact:** Backend action behavior and frontend one-click flows.

Automation rules:

- Auto-approve only when:
  - entity has evidence
  - confidence is at or above 90
  - duplicate risk is low
  - type-boundary score is high
  - name is not a group/noise/camera/copy term
  - no conflict with approved entity in same scope
- Auto-reject only for new candidates that are high-confidence noise and have no existing references.
- Auto-merge is never executed without confirmation in the first release.
- Auto-generate assets only for approved entities, or candidate entities in dev/test with explicit override.
- AI assistant suggestions must explain the reason in user-facing text:
  - "有原文证据，出现 6 次，未发现重复"
  - "疑似群体背景，不建议作为角色资产"
  - "与已存在角色名称相近，建议合并"

Verification:

- `cd backend && pytest tests/test_entity_review_service.py::test_auto_approval_requires_evidence_and_low_duplicate_risk -v`
- Expected: only strict clean candidates can auto-approve.

## Phase 10: Evaluation And Continuous Improvement Loop

**Goal:** Make extraction improve with usage instead of relying on one prompt forever.

**Impact:** Adds metrics and feedback visibility; no production flow break.

- [ ] Every extraction run stores:
  - prompt version
  - selected prompt skill id/version
  - prompt routing reason
  - provider/model
  - output contract
  - parse success or parse failure reason
  - text hash
  - candidate count by type
  - rejected-noise count
  - duplicate-risk count
  - missing-evidence count
  - auto-approved count
  - user-corrected count
- [ ] Every user correction writes `EntityFeedback`.
- [ ] Add a backend eval command or pytest fixture group that runs fixed samples through the scorer.
- [ ] Add a lightweight prompt improvement report:
  - top rejected names
  - most common wrong type
  - frequent merge patterns
  - frequent missing production attributes
  - prompt templates with high parse failure rate
  - prompt templates with high garbage rate by provider/model
- [ ] Update Prompt Skill routing metrics from run and feedback data:
  - increment parse success/failure counters
  - estimate garbage rate from scorer rejects and user rejects
  - update quality score from accepted entities, rejected entities, merge corrections, and manual type changes
- [ ] The report is internal/admin-facing in this release; do not expose confusing analytics to casual users.
- [ ] Verification:
  - `cd backend && pytest tests/test_entity_extraction_quality.py tests/test_entity_review_service.py tests/test_prompt_skill_routing.py -v`
  - Expected: feedback and eval stats are deterministic on fixtures.

## Phase 11: Story Bible And Production Card Handoff

**Goal:** Ensure approved entities are useful immediately downstream.

**Impact:** Controlled improvements to existing downstream integrations.

- [ ] On promote/approve, optionally sync entity into Story Bible sections using existing rule structure.
- [ ] Production card readiness includes:
  - review status
  - evidence coverage
  - asset view gaps
  - voice gap for characters
  - state change availability for props/events
- [ ] Asset generation UI uses the approved entity description, visual DNA, and evidence excerpt in prompts.
- [ ] `assets/reextract` skips candidate-only entities and recommends approving or editing first.
- [ ] Verification:
  - `cd backend && pytest tests/test_production_cards.py -v`
  - Expected: existing production card readiness still works and includes new metadata without breaking old cards.

## Phase 12: Rollout, Backout, And QA

**Goal:** Release safely.

Rollout:

- Stage A: Backend data layer and tests only.
- Stage B: New extraction run endpoint hidden behind feature flag.
- Stage C: New asset-analysis page linked only from dev or query param.
- Stage D: Link from novel detail page.
- Stage E: Character page safe mode default.
- Stage F: Consider defaulting `/story-bibles/entities/extract` to v2 for all users.

Backout:

- Disable `ENTITY_EXTRACTION_V2_ENABLED`.
- Hide novel detail link to asset-analysis page.
- Keep new tables untouched; they do not affect legacy production.
- Restore frontend character extraction to legacy mode by toggling request flag.

Full verification before release:

- `cd backend && pytest -q`
- `cd frontend && npm run build`
- Manual flow:
  - create or open a novel
  - run AI asset analysis
  - approve a character, scene, and prop
  - reject a noise candidate
  - merge two duplicates
  - generate missing assets for approved entities
  - open production cards
  - generate or open storyboard/video flow and confirm candidates do not leak into prompts

## Risk And Impact Matrix

| Area | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| Existing characters | Safe mode could confuse users expecting immediate Character records | Medium | Keep legacy endpoint behavior and add safe mode as frontend default only where scoped novel/chapter exists |
| StoryEntity generation context | New candidates could enter prompts too early | High | Add candidate filtering with legacy-active exception and tests |
| Asset generation | Candidate garbage could create useless images | High | Block candidate assets by default; require approval |
| Database | New tables may not be initialized in old environments | Medium | Follow existing `init_db.py` table creation pattern and add import tests |
| Frontend complexity | Review UI could feel like another expert tool | Medium | One primary action, AI recommendations, compact tabs, clear counts, bulk approve/reject |
| AI parsing | Model returns malformed JSON | Medium | Pydantic validation, one repair retry, deterministic fallback, run stats |
| Prompt template mismatch | A generic template may perform poorly on a specific provider/model | Medium | Model-aware Prompt Skill routing with output-contract matching and measured fallback reasons |
| Prompt routing bypass | A new extraction endpoint may call the model directly and skip Prompt Skill routing | High | Centralize AI extraction/enrichment calls and add tests requiring routing metadata for model calls |
| Prompt routing overfitting | Router may choose a template based on too little history | Medium | Start with deterministic provider/capability rules; use quality metrics only as tie-breakers until enough runs exist |
| User trust | Auto clean may remove useful entities | High | First release uses soft reject only; approved/referenced entities are never auto-deleted |
| Performance | Full-novel extraction may be slow | Medium | Run records, progress status, chunking, reuse text hash to avoid repeated work |

## Tracking Board

P0 release tasks:

- [ ] Phase 0 baseline and feature flag
- [ ] Phase 1 data layer
- [ ] Phase 1.5 unified StoryEntity lifecycle and query gateway
- [ ] Phase 2 schema and scoring
- [ ] Phase 3.5 model-aware prompt routing foundation
- [ ] Phase 3.6 targeted entity enrichment preview and merge-only backend
- [ ] Phase 4 production safety filtering
- [ ] Phase 5 review APIs
- [ ] Phase 7 asset-analysis page
- [ ] Phase 8 novel detail entry point
- [ ] Phase 9 smart automation rules
- [ ] Phase 12 QA and rollout

P1 follow-up tasks:

- [ ] Phase 3 provider-specific structured output hardening
- [ ] Phase 3.5 provider-specific built-in template families and routing metrics
- [ ] Phase 3.6 frontend field selector and enrichment drawer polish
- [ ] Phase 6 full character-page safe-mode migration
- [ ] Phase 10 feedback/eval reporting
- [ ] Phase 11 richer Story Bible and production card handoff

P2 later:

- [ ] Cross-novel reusable entity memory
- [ ] Active-learning prompt tuning UI
- [ ] Knowledge graph visualization for relations and event timelines
- [ ] Batch background worker for very long novels

## Decision Points

- After Phase 2: confirm quality thresholds before auto-approval is enabled.
- After Phase 3.5: confirm model-aware routing uses provider/capability rules before enabling metric-based tie-breakers.
- After Phase 3.6: confirm targeted enrichment merge policy protects approved fields from accidental overwrite.
- After Phase 4: confirm candidate filtering does not remove expected legacy entities from generation.
- After Phase 7: review frontend UX before linking it prominently from novel detail.
- Before Phase 6 default safe mode: confirm users no longer rely on immediate legacy `Character` writes as the primary flow.

## Recommended First Sprint

Sprint length: 3 to 5 focused development days.

Deliverables:

- New extraction run, mention, and feedback models.
- Unified StoryEntity lifecycle helper and production query gateway.
- Quality scorer with fixture tests.
- Prompt Skill router skeleton with provider/capability/output-contract selection.
- Targeted enrichment endpoint that can supplement one named entity without full extraction.
- Candidate review status that does not affect existing generation.
- Review summary endpoint.
- Novel asset-analysis page shell with real data, run button, KPI strip, and approve/reject actions.

Expected visible improvement:

- Users stop seeing raw noisy extraction results mixed with production assets.
- The system explains why an entity is recommended, risky, duplicate, or noise.
- Approved entities flow toward assets and production cards; candidates stay harmless.

## Final Acceptance Criteria

- New extraction results are evidence-backed and statused.
- All production consumers use the shared StoryEntity lifecycle/query helper.
- Candidate-only entities do not leak into shot/video generation.
- All AI-backed extraction/enrichment paths use Prompt Skill routing and record routing metadata.
- Users can specify entity type and name to enrich one entity without full overwrite.
- The user can run one-click AI analysis from the novel page.
- The user can approve, reject, edit, and merge from a single clean review UI.
- Approved entities can trigger existing asset generation and production card readiness.
- Entity and asset prompt generation records which model-aware template was selected and why.
- Feedback from user actions is stored for future prompt/rule improvement.
- Existing legacy flows remain available and verified.
