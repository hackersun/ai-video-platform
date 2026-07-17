# Seedance 2.x Provider Contract Checklist

Last reviewed: 2026-07-11

Contract version: `seedance-2.0-ark-2026-07-11`

Runtime status: `experimental`

Owner: production-platform

## Promotion Gate

`confirmed` is a fail-closed state. It requires all six non-empty evidence keys below; an official page or a deterministic unit test alone is not sufficient.

| Evidence key | Current value | Status |
| --- | --- | --- |
| `official_schema_url` | `https://www.volcengine.com/docs/82379/1520757` | recorded |
| `official_schema_accessed_at` | `2026-07-11` | recorded |
| `payload_contract_test` | `tests/test_reference_package.py::test_provider_content_adapter_submits_multimodal_references` | passing locally |
| `live_canary_job_id` | not recorded; live provider calls were forbidden for this work | missing |
| `pricing_url` | `https://www.volcengine.com/activity/seedance2` | recorded; no price is hardcoded |
| `failure_retry_evidence` | no provider failure/retry artifact has been recorded | missing |

Current `verification_gaps`: `live_canary_job_id`, `failure_retry_evidence`.

## Official Source Record

Only provider-owned pages were used for model/API decisions.

| Official source | Access date | What it supports | Decision |
| --- | --- | --- | --- |
| [Create video generation task API](https://www.volcengine.com/docs/82379/1520757) | 2026-07-11 | Canonical video-task API page and request contract authority; page reported an update on 2026-07-10. | Keep as the schema authority. It does not remove the need for a recorded live canary. |
| [Trusted human asset library](https://www.volcengine.com/docs/82379/2315856?lang=zh) | 2026-07-11 | Official Seedance 2.0 example uses an `image_url` content item with `role: reference_image`; the page links the `doubao-seedance-2-0-260128` experience. | `reference_image` has direct official example evidence. |
| [Seedance 2.0 resource packages](https://www.volcengine.com/activity/seedance2) | 2026-07-11 | Official resource-package page identifies Doubao-Seedance-2.0, token-based packages, 4–15 second duration, multimodal generation and listed output resolutions. | Record the pricing URL only. Do not copy a price or billing formula into runtime code. |
| [List Agent Plan models API](https://www.volcengine.com/docs/82379/2546385?lang=zh) | 2026-07-11 | Official API for discovering models supported by Agent Plan. The public document does not establish multi-reference limits for this contract. | Keep Agent Plan multi-reference disabled. |

## Request and Limit Decisions

| Contract item | Runtime value | Evidence status | Decision |
| --- | --- | --- | --- |
| model IDs | `doubao-seedance-2-0-260128`, `doubao-seedance-2-0-fast-260128` | Standard model ID appears in official provider material; Fast was not independently confirmed in the reviewed technical page. | Keep both aliases experimental. |
| image content/role | `type: image_url`, `role: reference_image` | Official example confirmed. | Preserve exact payload shape and cover it deterministically. |
| video content/role | `type: video_url`, `role: reference_video` | No accessible reviewed official example confirmed the exact role. | Preserve current behavior, but do not promote the contract. |
| audio content/role | `type: audio_url`, `role: reference_audio` | No accessible reviewed official example confirmed the exact role. | Preserve current behavior, but do not promote the contract. |
| prompt reference syntax | runtime prompt text uses `@图{index}` while the contract registry retains `@image{index}` | No reviewed official technical page confirmed one syntax for this API request. | Keep isolated behind the adapter and experimental status. |
| direct-account reference limits | images `9`, videos `3`, audios `3` | Existing runtime matrix; exact 9/3/3 limits were not confirmed by the reviewed official pages. | Continue clamping to preserve behavior; expose limits with experimental status. |
| native audio | `true` for direct Seedance 2.x contract | Multimodal/audio capability is described, but exact API request semantics remain incomplete. | Expose as experimental capability only. |
| Agent Plan reference limits | images `1`, videos `0`, audios `0` | Multi-reference support not established by reviewed official docs. | Fail closed and keep `agent_plan_multireference=false`. |
| pricing status | `unconfirmed` | Official pricing page is recorded, but no stable runtime formula is verified. | Do not hardcode price. |

## Deterministic Verification

No request in this checklist requires or permits a real provider call.

```bash
cd backend
DEV_MODE=true PYTHONPATH=. python3 -m pytest -q \
  tests/test_seedance_contract.py tests/test_reference_package.py
```

The tests cover:

- exact image/video/audio content roles emitted by the existing adapter;
- the six-key fail-closed promotion predicate;
- incomplete evidence remaining `experimental` with explicit gaps;
- a complete injected evidence fixture becoming `confirmed` without changing default runtime evidence;
- additive `contract_status`, `contract_version`, `verified_at`, `reference_limits`, and `verification_gaps` model metadata;
- legacy single-image behavior remaining compatible.

## Promotion Procedure

1. Re-review the official request and pricing pages and update access dates.
2. Record a successful, budget-approved live canary job ID outside deterministic tests.
3. Record a provider failure followed by a successful policy-compliant retry.
4. Verify all six keys are non-empty and rerun deterministic tests.
5. Promote the persisted evidence only through a reviewed change; never infer confirmation from model naming or local payload construction.

## Change Log

| Date | Change | Result |
| --- | --- | --- |
| 2026-07-06 | Opened the contract checklist. | Seedance 2.x remained experimental. |
| 2026-07-11 | Added fail-closed evidence predicate, API metadata and official-source decisions. | Default runtime remains experimental because live canary and failure/retry evidence are missing. |
