# Multi-Provider Generation Compatibility And Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add versioned model-execution contracts, one MiniMax TTS request builder, secret-safe recovery descriptors, and a clear Series Run recovery UI before rerunning the four-chapter live canary.

**Architecture:** A new provider-neutral contract feature composes existing registry facts without replacing provider adapters. MiniMax configuration tests and production TTS share one request builder. A separate Series Run recovery feature derives safe actions from persisted provider operations; the existing Series Run endpoint and view stay compatibility shells.

**Tech Stack:** FastAPI, async SQLAlchemy, Pydantic/dataclasses, Next.js 14, React 18, TypeScript, Playwright, pytest.

## Global Constraints

- Preserve the RMB 10, two-anchor, zero-automatic-retry live-canary boundary.
- Never retry `accepted`, `reserved`, or `unknown_manual_reconcile` provider operations.
- Preserve existing routes, state strings, stored data, reference assets, provider bindings and response fields.
- Do not add a database table in this batch.
- Do not export prompts, dialogue text, provider response bodies, media bytes, URLs, headers or credentials.
- Do not grow `backend/app/api/v1/endpoints/series_runs.py`, `frontend/src/lib/api-client.ts`, or any listed legacy hotspot.
- New production files stay below 300 lines; functions stay below 80 lines and route handlers below 60 lines.
- No paid provider call until deterministic tests, typecheck, build and frontend acceptance pass.
- Do not commit unrelated dirty-worktree files.

---

### Task 1: Versioned model-execution contract registry

**Files:**
- Create: `backend/app/features/model_execution_contract/domain.py`
- Create: `backend/app/features/model_execution_contract/registry.py`
- Create: `backend/app/features/model_execution_contract/public.py`
- Test: `backend/tests/test_model_execution_contract.py`

**Interfaces:**
- Produces: `resolve_model_execution_contract(provider_id: str, api_model_id: str, capability: str) -> ModelExecutionContract`.
- Consumes: existing model registry and Seedance contract facts only; it does not import API endpoints or provider SDKs.

- [x] **Step 1: Write failing contract tests**

```python
def test_known_versions_get_stable_contracts():
    cases = [
        ("minimax", "MiniMax-M3", "text", "minimax.text.m3.v1"),
        ("minimax", "image-01", "image", "minimax.image.image01.v1"),
        ("minimax", "speech-2.6-hd", "tts", "minimax.tts.v2.v1"),
        ("volcano", "doubao-seedance-1-5-pro-251215", "video", "volcano.seedance15.v1"),
        ("alibaba", "happyhorse-1.1-r2v", "video", "alibaba.happyhorse11.r2v.v1"),
    ]
    for provider, model, capability, version in cases:
        assert resolve_model_execution_contract(provider, model, capability).contract_version == version

def test_unknown_model_is_fail_closed():
    contract = resolve_model_execution_contract("new-provider", "future-model", "video")
    assert contract.verification_status == "unverified"
    assert contract.retry_policy == "never"
    assert contract.reference_limits == {"images": 0, "videos": 0, "audios": 0}
```

- [x] **Step 2: Run RED**

Run: `cd backend && python3 -m pytest -q tests/test_model_execution_contract.py`

Expected: import failure because the feature does not exist.

- [x] **Step 3: Implement immutable domain values and explicit registry entries**

```python
@dataclass(frozen=True)
class ModelExecutionContract:
    provider_id: str
    api_model_id: str
    capability: str
    contract_version: str
    supported_inputs: tuple[str, ...]
    response_mode: str
    polling_mode: str
    prompt_profile: str
    reference_limits: dict[str, int]
    retry_policy: str
    verification_status: str
```

Unknown combinations return a conservative contract with no references and no retry.

- [x] **Step 4: Run GREEN**

Run: `cd backend && python3 -m pytest -q tests/test_model_execution_contract.py`

Expected: all tests pass.

---

### Task 2: Shared MiniMax TTS request contract and safe failure details

**Files:**
- Create: `backend/app/services/minimax_tts_request.py`
- Modify: `backend/app/services/minimax_service.py`
- Modify: `backend/app/api/v1/endpoints/llm_config.py`
- Modify: `backend/app/features/workflow_media/adapters/tts_submission.py`
- Test: `backend/tests/test_minimax_tts_request_contract.py`
- Test: `backend/tests/test_tts_provider_rejection.py`

**Interfaces:**
- Produces: `build_minimax_tts_request(...) -> MiniMaxTTSRequest` with `contract_version`, `url_path`, `payload`, and `safe_evidence()`.
- Consumes: normalized API model id and the approved voice chosen by the run.

- [x] **Step 1: Write failing parity and redaction tests**

```python
def test_config_and_production_use_identical_tts_payload_contract():
    request = build_minimax_tts_request(
        model_id="minimax-speech-2-6-hd", text="你好", voice_id="male-qn-qingse", speed=1.0,
    )
    assert request.payload["model"] == "speech-2.6-hd"
    assert request.payload["voice_setting"]["voice_id"] == "male-qn-qingse"
    assert set(request.safe_evidence()) == {
        "request_contract_version", "api_model_id", "voice_id", "payload_fields",
    }
    assert "text" not in request.safe_evidence()
```

Extend the provider-rejection test to require `stage`, `cost_state`, `safe_retry`, `retry_scope`, and allowed actions.

- [x] **Step 2: Run RED**

Run: `cd backend && python3 -m pytest -q tests/test_minimax_tts_request_contract.py tests/test_tts_provider_rejection.py`

Expected: missing request builder and missing recovery fields.

- [x] **Step 3: Implement one request builder and replace both hand-built payloads**

```python
request = build_minimax_tts_request(
    model_id=model,
    text=text,
    voice_id=voice_id,
    speed=speed,
)
response = await client.post(f"{base_url}{request.url_path}", json=request.payload, headers=headers)
```

The LLM configuration test passes the exact approved voice and uses the same builder. Production catches `MiniMaxProviderRejected`, releases confirmed pre-acceptance reservation, and returns a secret-safe recovery descriptor.

- [x] **Step 4: Run GREEN and related TTS regression**

Run: `cd backend && python3 -m pytest -q tests/test_minimax_tts_request_contract.py tests/test_tts_provider_rejection.py tests/test_separate_media_submission_order.py test_minimax_service.py`

Expected: all tests pass and video submission remains blocked after TTS rejection.

---

### Task 3: Series Run recovery domain and API

**Files:**
- Create: `backend/app/features/series_run_recovery/domain.py`
- Create: `backend/app/features/series_run_recovery/application.py`
- Create: `backend/app/features/series_run_recovery/api.py`
- Create: `backend/app/features/series_run_recovery/public.py`
- Modify: `backend/app/api/v1/router.py`
- Modify: `backend/app/features/series_anchor_generation/schemas.py`
- Test: `backend/tests/test_series_run_recovery.py`

**Interfaces:**
- Produces: `GET /series-runs/{run_id}/recovery` and `POST /series-runs/{run_id}/recovery/actions/{action_code}`.
- Consumes: owned run, provider operations, cost summary and current model-binding snapshots.

- [x] **Step 1: Write failing recovery-policy tests**

```python
def test_confirmed_rejection_allows_failed_stage_retry():
    descriptor = recovery_for_operation(operation(status="confirmed_rejected_before_acceptance", capability="tts"))
    assert descriptor.safe_retry is True
    assert descriptor.retry_scope == "failed_stage"
    assert {item.code for item in descriptor.actions} >= {"edit_voice", "retest_config", "retry_failed_stage"}

@pytest.mark.parametrize("status", ["accepted", "reserved", "unknown_manual_reconcile"])
def test_uncertain_operation_never_offers_resubmit(status):
    descriptor = recovery_for_operation(operation(status=status, capability="video"))
    assert descriptor.safe_retry is False
    assert {item.code for item in descriptor.actions} <= {"refresh_status", "manual_reconcile"}
```

Add API ownership and stale-binding tests. `retry_failed_stage` initially returns a validated retry intent and updates no provider state; actual resubmission remains the existing Generate Selected action after the user changes/revalidates bindings.

- [x] **Step 2: Run RED**

Run: `cd backend && python3 -m pytest -q tests/test_series_run_recovery.py`

Expected: missing recovery feature/routes.

- [x] **Step 3: Implement pure recovery policy, read aggregation and validated action acknowledgement**

The API handler stays below 60 lines and calls the application service. It returns only identifiers, stages, accounting values and allowed actions.

- [x] **Step 4: Run GREEN and budget regressions**

Run: `cd backend && python3 -m pytest -q tests/test_series_run_recovery.py tests/test_live_canary_budget.py tests/test_tts_provider_rejection.py`

Expected: all tests pass; no operation is submitted by recovery tests.

---

### Task 4: Prompt-routing evidence and binding snapshots

**Files:**
- Modify: `backend/app/services/live_canary_bindings.py`
- Modify: `backend/app/services/prompt_template_router.py`
- Modify: focused image/video/TTS adapter call sites selected during implementation
- Test: `backend/tests/test_model_execution_contract.py`
- Test: `backend/tests/test_prompt_template_router.py`

**Interfaces:**
- Binding snapshots add `contract_version`, `prompt_profile`, and `verification_status` without removing existing fields.
- Prompt routing returns the existing result plus `model_contract_version` and persists no prompt text in recovery evidence.

- [x] **Step 1: Write failing additive snapshot and routing tests**

```python
assert snapshot["tts"]["contract_version"] == "minimax.tts.v2.v1"
assert routing["model_contract_version"] == "minimax.text.m3.v1"
assert routing["fallback_reason"] in {None, "internal_prompt_fallback", "task_only_template"}
```

- [x] **Step 2: Run RED**

Run: `cd backend && python3 -m pytest -q tests/test_model_execution_contract.py tests/test_prompt_template_router.py tests/test_series_run_live_preflight_plan.py`

Expected: additive fields absent.

- [x] **Step 3: Compose the contract registry into bindings and prompt routing**

Do not copy model capability rules into frontend or endpoints. Keep current response fields intact.

- [x] **Step 4: Run GREEN**

Run the same command and expect all tests to pass.

---

### Task 5: Clear recovery card and truthful costs in the frontend

**Files:**
- Create: `frontend/src/features/series-runs/types/recovery.ts`
- Create: `frontend/src/features/series-runs/hooks/use-series-run-recovery.ts`
- Create: `frontend/src/features/series-runs/components/recovery-card.tsx`
- Create: `frontend/src/features/series-runs/api.ts`
- Modify: `frontend/src/features/series-runs/series-run-view.tsx`
- Modify: `frontend/src/features/series-runs/use-anchor-generation.ts`
- Modify: `frontend/src/components/novels/series-run-panel.tsx`
- Modify: `frontend/e2e/four-chapter-series-run.spec.ts`

**Interfaces:**
- `useSeriesRunRecovery(runId)` loads the backend descriptor and executes only returned actions.
- `RecoveryCard` receives data/actions and owns no retry-policy rules.

- [x] **Step 1: Add failing Playwright assertions**

The deterministic failure fixture must render:

```text
声音生成未受理
失败阶段：配音提交
本次 TTS 未扣费，预留已释放
参考图已锁定，不会重新生成
修改声线
重新测试声音模型
修改后重试失败阶段
```

It must not render a resubmit button for `unknown_manual_reconcile`. Add an assertion that displayed spent cost uses `spent_rmb` even when legacy `actual_rmb` is `0`.

- [x] **Step 2: Run RED**

Run: `cd frontend && npm run e2e:four-chapter:direct -- --grep "recovery"`

Expected: recovery card and truthful cost assertions fail.

- [x] **Step 3: Implement feature-local API/hook/component and integrate the compatibility view**

The cost badges read `spent_rmb`, `reserved_rmb`, and preflight projected increment. Paid retry confirmation states capability, shot and estimated new cost.

- [x] **Step 4: Run GREEN, typecheck and build**

Run:

```bash
cd frontend
npm run e2e:four-chapter:direct -- --grep "recovery"
npm run typecheck
NEXT_DIST_DIR=.next-provider-recovery npm run build
```

Expected: all commands pass.

---

### Task 6: Deterministic integration and front-end live canary

**Files:**
- Modify: `frontend/e2e/four-chapter-live-canary.spec.ts`
- Modify: `scripts/run-four-chapter-acceptance.mjs`
- Modify: `docs/operations/four-chapter-live-canary.md`
- Verify only after deterministic gates pass.

**Interfaces:**
- The live manifest records contract versions and prompt-routing metadata, never prompt text.
- A confirmed TTS rejection proves the recovery card and stops without video submission; it is not automatically retried.

- [x] **Step 1: Run complete deterministic gates**

```bash
cd backend && python3 -m pytest -q \
  tests/test_model_execution_contract.py \
  tests/test_minimax_tts_request_contract.py \
  tests/test_tts_provider_rejection.py \
  tests/test_series_run_recovery.py \
  tests/test_prompt_template_router.py \
  tests/test_series_run_live_preflight_plan.py \
  tests/test_live_canary_budget.py
cd ../frontend && npm run typecheck && NEXT_DIST_DIR=.next-provider-recovery npm run build
```

- [x] **Step 2: Run deterministic four-chapter frontend acceptance**

Run: `npm run verify:four-chapter`

Expected: four chapters, two cross-episode anchors, reference evidence, recovery UI and no external provider calls.

- [x] **Step 3: Re-read the live authorization and run one live Wave 1**

Use `sunqy`, RMB 10, two anchors, no automatic retries, isolated DB and Qiniu public delivery. A new paid retry after any fail-closed stop requires a new explicit authorization.

- [x] **Step 4: Export and report evidence**

Report per capability: provider/model/contract version, task/operation status, cost, prompt routing mode, reference binding, media artifacts and six-dimensional evaluation boundary. Mark unconfigured providers as “adapter-ready, live-unverified”.
