# Reference Adapter Stage Evidence And Task Binding Plan

**Goal:** Preserve a recoverable provider task boundary and expose only staged, redacted failure evidence when reference-image generation succeeds or becomes unknown before Qiniu delivery completes.

## Execution contract

- **Intent lock:** Make reference-generation failures diagnosable and manually recoverable without retries, secrets, media URLs, or base64 payloads leaking into UI/API evidence.
- **Scope:** Reference-image provider call, response classification, local persistence, Qiniu upload, operation recovery evidence, and failure-evidence export.
- **Out of scope:** Automatic retry, automatic cost settlement for unknown provider state, TTS behavior, video-provider submission, and broader workflow refactors.
- **Compatibility:** Generic third-party reference adapters retain the existing fail-closed `reference_adapter_exception` behavior.

## Acceptance criteria

1. A provider task ID is bound to the operation before local persistence or Qiniu delivery begins.
2. Failures are classified as `provider_call`, `response_parse`, `local_persistence`, or `qiniu_upload` with fixed, redacted messages.
3. A known task ID and provider-completed flag survive into manual-reconcile evidence; no original exception text, URL, prompt, base64, key, or token is exposed.
4. The failure exporter includes only the allowlisted staged evidence.
5. Existing no-retry and no-TTS safety behavior remains unchanged.

## Tasks and verification

1. Add failing adapter and exporter contract tests.
   - Verify RED: `backend/venv/bin/python -m pytest -q backend/tests/test_series_run_reference_adapter.py backend/tests/test_export_live_canary_failure_evidence.py`
2. Implement typed stage errors, early task binding, and manual-reconcile evidence.
   - Verify: targeted adapter and live-preflight tests.
3. Extend the redacted exporter allowlist for stage evidence.
   - Verify: exporter tests and serialized secret-absence assertions.
4. Run fresh backend tests, frontend typecheck/build, restart services, and validate the frontend workflow safety gates before any new paid live submission.

## Live finding and follow-up

- The 2026-07-17 live attempt reached `provider_call` with no task ID or response evidence. Local read-only diagnostics proved the saved config and MiniMax client construct successfully; the same config's latest successful image test used `response_format=url`, while the reference adapter uniquely forced `base64`.
- Follow-up fix: request the proven URL response mode, then download and re-upload to Qiniu before binding. A typed MiniMax business rejection is treated as a confirmed pre-submit rejection so its reservation can be released; all ambiguous transport failures remain fail-closed and non-retryable.
