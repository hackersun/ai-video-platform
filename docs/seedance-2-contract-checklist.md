# Seedance 2.0 Official Contract Checklist

Date opened: 2026-07-06
Current status: experimental
Owner: production-platform

## Official Sources To Check

| Source | URL | Required evidence |
| --- | --- | --- |
| Volcano Ark video generation docs | https://www.volcengine.com/docs/82379/1520757 | request schema, content item fields, role values |
| Volcano Ark model catalog or console | record exact URL used during verification | Seedance 2.0 and Seedance 2.0 fast model IDs |
| Volcano pricing or billing page | record exact URL used during verification | official unit price and billing formula |
| Agent Plan docs or console | record exact URL used during verification | whether Agent Plan supports multi-image/video/audio references |

## Contract Fields

| Field | Current implementation | Official evidence status | Decision |
| --- | --- | --- | --- |
| image role | `reference_image` | unconfirmed | Keep experimental metadata until official docs confirm or replacement is tested. |
| video role | `reference_video` | unconfirmed | Keep experimental metadata until official docs confirm or replacement is tested. |
| audio role | `reference_audio` | unconfirmed | Keep experimental metadata until official docs confirm or replacement is tested. |
| prompt reference syntax | `@image{index}` | unconfirmed | Keep generated prompt text isolated in `reference_package_builder.py`. |
| max images | `9` for Volcano Seedance 2.x | unconfirmed | Continue enforcing by model capability matrix. |
| max videos | `3` for Volcano Seedance 2.x | unconfirmed | Continue enforcing by model capability matrix. |
| max audios | `3` for Volcano Seedance 2.x | unconfirmed | Continue enforcing by model capability matrix. |
| pricing formula | duration/resolution/frame token estimate | unconfirmed | Do not hardcode official price until source is recorded. |
| Agent Plan multi-reference | disabled | unconfirmed | Keep `images=1`, `videos=0`, `audios=0` for Agent Plan. |

## Promotion Rule

The contract can move from `experimental` to `confirmed` only after all items below are true:

- Official source URL and access date are recorded for request schema.
- A local provider payload test proves the recorded role values are submitted.
- A live canary response proves the provider accepts the payload.
- Pricing source URL and access date are recorded.
- Agent Plan support is either confirmed and tested, or explicitly recorded as unsupported.

## Change Log

| Date | Change | Evidence |
| --- | --- | --- |
| 2026-07-06 | Opened checklist. | Current code keeps Seedance 2.x multi-reference as experimental. |
