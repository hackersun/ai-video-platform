# MiniMax Image Response Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve secret-safe MiniMax image response evidence, accept documented and bounded non-standard result shapes, and retain a recoverable provider ID when no image artifact is returned.

**Architecture:** First extract the configured reference adapter from the 500-line orchestration hotspot without changing behavior. Then add a focused response-contract module that classifies only structural evidence and persists it in `SeriesProductionRun.run_metadata`. The adapter requests MiniMax base64 output, uploads successful bytes through the existing Qiniu path, and returns `accepted` with a provider ID when no artifact exists; no undocumented MiniMax polling endpoint or automatic paid retry is added.

**Tech Stack:** Python 3, FastAPI services, async SQLAlchemy, pytest, existing MiniMax and Qiniu adapters.

## Global Constraints

- Preserve API contracts, RMB reservation semantics, Story Lock behavior, and the failure-without-retry live-canary policy.
- Never persist or log API keys, response URLs, signed query strings, base64 payloads, prompts, or raw provider messages in response-shape evidence.
- Do not grow `backend/app/services/series_run_reference_preparation.py`; extraction and behavior changes remain separate slices.
- Do not invent a MiniMax image polling endpoint: the official image-generation contract documents synchronous `id` plus `data.image_urls` or `data.image_base64`, but no image status query API.
- Every behavior change begins with a failing test and ends with focused plus module-level verification.

---

### Task 1: Extract the configured provider adapter without behavior change

**Files:**
- Create: `backend/app/services/series_reference_provider.py`
- Modify: `backend/app/services/series_run_reference_preparation.py`
- Test: `backend/tests/test_series_run_reference_adapter.py`

**Interfaces:**
- Produces: `ConfiguredReferenceAdapter`, `persist_qiniu_reference(...)`, and signed-URL expiry parsing; `series_run_reference_preparation` re-exports `ConfiguredReferenceAdapter` for compatibility.

- [ ] Run `python3 -m pytest tests/test_series_run_reference_adapter.py -q` as the characterization baseline.
- [ ] Move the configured adapter and Qiniu delivery helpers into the focused provider module; change imports only.
- [ ] Re-run the characterization test and confirm no behavior change.

### Task 2: Add secret-safe response evidence and response classification

**Files:**
- Create: `backend/app/services/image_provider_response_contract.py`
- Modify: `backend/app/services/image_generation_pipeline.py`
- Modify: `backend/app/services/image_result_parser.py`
- Test: `backend/tests/test_image_provider_response_contract.py`
- Test: `backend/tests/test_image_generation_pipeline.py`
- Test: `backend/tests/test_image_result_parser.py`

**Interfaces:**
- Produces: `classify_image_provider_response(result, provider_name) -> dict` with `status`, `provider_task_id`, `image_urls`, and `evidence`.
- Produces: `persist_image_response_evidence(db, run, operation_id, evidence) -> None`.

- [ ] Write failing tests proving official MiniMax top-level `id` is retained only when the response has provider-contract fields, nested bounded result containers are parsed, and evidence contains no raw URL/base64/message/secret.
- [ ] Run the exact tests and verify failures are caused by the missing contract behavior.
- [ ] Implement allowlisted structural evidence: field presence, data kind, image counts, metadata counts, status code, and message hash.
- [ ] Implement bounded non-standard containers (`results`, `artifacts`, `payload`, `image`, `urls`) without unrestricted dictionary crawling.
- [ ] Persist evidence under `run_metadata.provider_response_evidence[operation_id]` and cap retained entries.
- [ ] Re-run the exact tests and confirm they pass.

### Task 3: Integrate base64/Qiniu delivery and recoverable no-artifact state

**Files:**
- Modify: `backend/app/services/series_reference_provider.py`
- Test: `backend/tests/test_series_run_reference_adapter.py`
- Test: `backend/tests/test_series_run_live_preflight_plan.py`

**Interfaces:**
- Consumes: `classify_image_provider_response(...)` and `persist_image_response_evidence(...)`.
- Produces: `completed` only after Qiniu delivery succeeds; `accepted` plus provider ID when the provider accepted the request without an artifact; `unknown` only when neither artifact nor ID exists.

- [ ] Write failing adapter tests for MiniMax base64 request mode, evidence persistence, official top-level ID, non-standard nested image result, and no-artifact accepted state.
- [ ] Write a failing orchestration test proving accepted/no-artifact binds the provider ID, retains the reservation, creates no asset, and performs no second provider submission.
- [ ] Run the exact tests and verify the expected failures.
- [ ] Integrate the contract module; request `response_format=base64` for MiniMax and pass data URLs through existing local persistence plus Qiniu upload.
- [ ] Re-run focused tests, then run `python3 -m pytest tests/test_series_run_reference_adapter.py tests/test_image_provider_response_contract.py tests/test_image_generation_pipeline.py tests/test_image_result_parser.py tests/test_series_run_live_preflight_plan.py tests/test_media_delivery_qiniu.py -q`.
- [ ] Run `npm run typecheck` in `frontend` and `python3 -m py_compile` for changed Python modules.

### Task 4: Document the verified boundary

**Files:**
- Modify: `docs/operations/four-chapter-live-canary.md`

**Interfaces:**
- Produces: an operator rule distinguishing synchronous MiniMax artifacts, accepted/no-artifact recovery, Qiniu delivery, and forbidden automatic retries.

- [ ] Document the response-evidence fields, base64-to-Qiniu path, and the absence of a documented MiniMax image polling endpoint.
- [ ] Run `git diff --check` on this batch's files and inspect the final focused diff for secrets and unrelated edits.
