# Series Run Story Lock Extraction Design

## Status

- Date: 2026-07-12
- Classification: C/D (business rule and live-provider safety boundary)
- Implementation status: design only
- Live status: Wave 1 blocked before reference/media provider submission

## Intent Lock

Allow the four-chapter workbench to prepare Story Locks for the exact selected-anchor production closure without auto-approving unrelated extracted candidates, while shrinking the current Series Run hotspots and preserving all provider, budget, ownership, provenance, and no-future-leakage gates.

## Current Evidence

The final isolated Wave 1 reached this visible UI sequence:

1. four allowlisted model tests: HTTP 200;
2. binding validation: HTTP 200;
3. explicit voice selection: HTTP 200;
4. whole-book execution: HTTP 200 and `shots_ready`;
5. two cross-episode anchors persisted;
6. the first and only Story Lock request: HTTP 409.

Before cleanup, the isolated database contained 46 extracted, unapproved entities:

- characters: 12;
- scenes: 14;
- props: 13;
- events: 7.

No Story Bible, reference asset, provider binding, provider operation, media job, generation submission, or quality evaluation was created. Generation cost was RMB 0. Configuration-test cost was not reported by the providers and remains unknown.

## Problem Statement

The current Story Lock preparation path treats the broad extraction set as the approval boundary. A four-chapter run can therefore be blocked by unrelated or low-confidence candidates even when the two selected anchors require only a small, provable entity closure.

The rule is currently spread across legacy hotspots:

- `backend/app/api/v1/endpoints/series_runs.py` (over 1,300 lines);
- `backend/app/services/series_run_live_preflight.py` (over 1,200 lines).

Under the code-health ratchet, neither file may receive additional non-trivial behavior or net line growth.

## Proposed Ownership

Create a focused feature with a public facade:

```text
backend/app/features/series_run_story_locks/
├── api_schemas.py
├── public.py
├── application/
│   ├── build_required_entity_closure.py
│   └── prepare_story_locks.py
├── domain/
│   ├── approval_policy.py
│   ├── evidence_contract.py
│   └── errors.py
└── repositories/
    └── story_lock_repository.py
```

Dependency direction:

```text
series_runs endpoint -> feature public facade
feature application -> domain + repository + existing public provider/budget facades
domain -> standard library only
```

No feature module may import an API endpoint. Existing routes and response shapes remain compatible.

## Required Entity Closure

The approval boundary is the transitive closure required by the persisted selection, not every extracted candidate.

For each selected shot, resolve server-side:

- canonical workflow, episode, chapter, and shot ownership;
- speaking character and locked voice;
- character references used by prompts or provider inputs;
- scene and continuity props explicitly referenced by the shot;
- event facts needed to preserve the shot's chapter-local causality;
- global style board and provider-bound reference asset.

Then include dependencies referenced by those facts. A candidate outside this closure remains a candidate and does not block the smoke run.

The closure must be deterministic, ordered, hashable, and persisted with:

- run ID and selection revision;
- selected shot IDs;
- as-of chapter IDs and input hashes;
- entity IDs, versions, evidence hashes, and dependency edges;
- policy and evaluator versions.

## Approval Policy

Only required facts can be automatically approved. Each entity type has one domain policy owner.

### Character

Eligible only with verified owned-chapter dialogue evidence, exact speaker span, content hash, trusted parser version, compatible identity projection, and no manual/rejected/ambiguous state.

### Scene

Eligible only when the selected shot references an unambiguous scene candidate with owned-chapter span evidence and no conflicting topology or location identity.

### Prop

Eligible only when the selected shot or event explicitly references the prop and ownership/state evidence is unambiguous as of that chapter. Damage, ownership, and position conflicts require review.

### Event

Eligible only when the event is directly supported by the selected shot's chapter-local causal evidence. Later-chapter outcomes cannot be used.

Unknown evidence versions, missing spans, conflicting facts, multiple unresolved candidates, or manual states fail closed. Unrelated candidates do not block.

## Transaction And Version Rules

One application transaction must:

1. lock the run and selection revision;
2. recompute the required closure;
3. verify model, voice, Story, and reference snapshots;
4. approve only eligible required facts;
5. build a new Story Bible/state-machine version;
6. enrich selected shots and episode contracts;
7. persist the closure hash and audit evidence;
8. commit atomically.

Any error rolls back all approvals, Story versions, shot enrichment, and contract changes.

Superseded history remains immutable. A changed chapter, selection, voice, model test timestamp, entity version, or evidence hash invalidates the current closure and all dependent locks.

## HTTP And UI Contract

Keep existing route compatibility. The endpoint becomes a thin adapter to the public facade.

Safe failure detail must include:

- stable error code;
- blocker category and field name;
- SHA-256 value hashes only;
- required entity counts by type;
- unresolved required entity IDs only when ownership permits;
- no chapter text, entity values, prompts, credentials, or provider payloads.

The live runner must persist the first Story Lock response status and redacted body before stopping and cleanup.

The workbench must show:

- required closure counts versus unrelated candidates;
- auto-approved, unresolved, and manual-review counts;
- exact blocker codes;
- Story version and closure hash after success.

## Scope Boundaries

In scope:

- extracting Story Lock rules from the two hotspots;
- required-entity closure for persisted anchor selections;
- type-specific evidence-based approval;
- atomic Story/shot/contract versioning;
- redacted Story Lock response capture;
- focused backend and real-browser acceptance.

Out of scope:

- Wave 2 six-anchor paid generation;
- increasing the RMB10 Wave 1 budget;
- broad entity schema redesign;
- auto-approving unrelated novel-wide candidates;
- refactoring other legacy endpoints or pages;
- provider/model substitution.

## Hotspot Ratchet

Implementation is acceptable only if:

- `series_runs.py` has no net line growth and delegates the use case;
- `series_run_live_preflight.py` has no net line growth and loses Story Lock responsibilities;
- no new production file exceeds 500 lines;
- new logic functions stay at or below 80 lines;
- route handlers stay at or below 60 lines;
- no endpoint-to-endpoint or service-to-endpoint imports are added;
- business rules have one owner in the new domain module.

Before implementation, record line-count and import baselines for all touched hotspots.

## Acceptance Criteria

1. The exact four-chapter fixture reproduces the production-shaped extraction set.
2. Two selected anchors compute a smaller required closure than the full 46-candidate set.
3. Unrelated candidates remain unapproved but do not block Story Lock preparation.
4. Required, evidence-complete facts are approved atomically and produce a new locked Story version.
5. Required ambiguous/conflicting facts return a redacted 409 and produce zero partial writes.
6. No future-chapter fact appears in an earlier chapter contract.
7. Repeating the same request is idempotent; selection/input changes invalidate it.
8. The existing Task4 media preflight becomes ready only after the new closure and all reference/voice/provider locks are valid.
9. Real-browser acceptance captures and audits the Story Lock response body.
10. No reference, TTS, image, or video provider call occurs in deterministic verification.
11. Development DB, `tsconfig.json`, ports, and protected counts remain unchanged.
12. Hotspot line counts do not increase and at least one Story Lock responsibility is removed from each touched hotspot.

## Verification Commands

Targeted commands must be finalized after the extraction files exist. The required verification set is:

```bash
cd backend
DATABASE_URL=sqlite+aiosqlite:////tmp/task9-story-lock-extraction.db \
  python3 -m pytest -q \
  tests/test_series_run_live_preflight_plan.py \
  tests/test_dialogue_lineage_service.py \
  tests/test_series_anchor_quality.py \
  tests/test_production_preflight_gates.py

cd ..
npm run verify:four-chapter
```

Also run the repository code-health check when it is introduced. Until then, record manual line counts, function lengths, endpoint dependencies, and hotspot before/after diffs in the implementation report.

## Live Re-entry Gate

Do not run another paid Wave 1 until all acceptance criteria above pass and an independent review approves the extracted feature. The next live run remains capped at RMB10 and two anchors, with Wave 2 disabled.
