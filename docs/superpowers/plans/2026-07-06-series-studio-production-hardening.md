# Series Studio Production Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining gaps that prevent Series Studio from being treated as a reliable whole-anime-series production control system.

**Architecture:** Keep the current Series Studio flow intact and add four hardening layers: an explicit Seedance 2.0 contract registry, real-novel context acceptance fixtures, opt-in live cloud canaries, and generated media hygiene. All live/cloud checks must be opt-in and budget-gated; default CI remains deterministic and mock-safe.

**Tech Stack:** FastAPI, async SQLAlchemy, pytest, Next.js 14 App Router, Playwright, TypeScript, Tailwind CSS, Volcano Ark/Seedance model configs.

---

## Scope

This plan covers four concrete gaps:

1. Seedance 2.0 multi-reference official contract confirmation: `role`, `@` reference syntax, pricing, and Agent Plan multi-reference support.
2. Stronger manual and automated evidence for workflows that include `novel_id` and `chapter_id`.
3. Opt-in real cloud model validation across multi-episode, multi-character, multi-reference production.
4. Generated media/static file governance so long-running projects do not drown in untracked files.

This plan does not redesign Studio UI, replace existing mock E2E tests, or introduce database migrations. It preserves current JSON-column and metadata-based contracts.

## Success Criteria

- Seedance 2.0 contract status is machine-readable and visible in reference-package metadata.
- Multi-reference submission remains marked `experimental` until official contract evidence is recorded.
- Agent Plan remains single-reference unless a confirmed contract explicitly enables multi-reference.
- A real-context acceptance fixture creates a novel, chapters, Story Bible, series plan, workflow, shots, assets, production cards, and Studio links with `novel_id/chapter_id`.
- Manual acceptance evidence includes at least one workflow with both `novel_id` and `chapter_id`.
- Live cloud canary is opt-in, cost-gated, writes a sanitized artifact, and is skipped by default.
- `.gitignore` and audit scripts classify generated runtime files separately from seed/reference assets.
- `git status --short` is no longer flooded by `backend/static/dev`, generated images/videos, Playwright screenshots, or local cache directories.

## File Map

- Create `backend/app/services/seedance_contract.py`: source-of-truth contract registry for Seedance 2.x reference payloads.
- Create `backend/tests/test_seedance_contract.py`: unit tests for contract state, roles, reference syntax, pricing status, and Agent Plan support.
- Modify `backend/app/services/video_reference_adapter.py`: use the registry instead of hard-coded role constants.
- Modify `backend/tests/test_reference_package.py`: assert provider metadata records contract state and role mapping.
- Create `docs/seedance-2-contract-checklist.md`: manual official-contract verification dossier.
- Create `backend/scripts/create_series_acceptance_fixture.py`: deterministic local fixture builder for real novel context acceptance.
- Create `backend/tests/test_series_acceptance_fixture.py`: dry-run tests for fixture shape and required IDs.
- Create `frontend/e2e/series-studio-real-context.spec.ts`: browser smoke against real local API data with `novel_id/chapter_id`.
- Modify `docs/superpowers/plans/2026-07-06-studio-smart-console-manual-acceptance.md`: append real-context acceptance results.
- Modify `frontend/e2e/live-anime-production-seedance.spec.ts`: convert current single-episode live E2E into a budget-gated canary matrix.
- Create `backend/app/services/generated_artifact_policy.py`: classify generated files and seed assets.
- Create `backend/scripts/audit_generated_artifacts.py`: summarize generated file counts, sizes, and unignored patterns.
- Create `backend/tests/test_generated_artifact_policy.py`: unit tests for artifact classification.
- Modify `.gitignore`: ignore runtime-generated artifacts and local tool caches.
- Modify `package.json`: add hygiene and live-canary command aliases.

---

## Task 1: Seedance 2.0 Contract Registry

**Files:**
- Create: `backend/app/services/seedance_contract.py`
- Test: `backend/tests/test_seedance_contract.py`

- [ ] **Step 1: Write failing contract registry tests**

Create `backend/tests/test_seedance_contract.py`:

```python
from __future__ import annotations

from app.services.seedance_contract import get_seedance_contract


def test_seedance_20_contract_defaults_to_experimental_until_official_evidence_exists() -> None:
    contract = get_seedance_contract("doubao-seedance-2-0-260128", provider="volcano")

    assert contract.model_family == "seedance_2"
    assert contract.provider == "volcano"
    assert contract.status == "experimental"
    assert contract.roles.image == "reference_image"
    assert contract.roles.video == "reference_video"
    assert contract.roles.audio == "reference_audio"
    assert contract.at_reference_syntax == "@image{index}"
    assert contract.pricing_status == "unconfirmed"
    assert contract.agent_plan_multireference is False
    assert contract.official_sources == [
        "https://www.volcengine.com/docs/82379/1520757",
    ]


def test_seedance_fast_uses_same_experimental_contract() -> None:
    contract = get_seedance_contract("doubao-seedance-2-0-fast-260128", provider="volcano")

    assert contract.model_family == "seedance_2"
    assert contract.status == "experimental"
    assert contract.max_images == 9
    assert contract.max_videos == 3
    assert contract.max_audios == 3


def test_agent_plan_contract_stays_single_reference_before_official_confirmation() -> None:
    contract = get_seedance_contract("doubao-seedance-2.0-fast", provider="volcano_agent_plan")

    assert contract.provider == "volcano_agent_plan"
    assert contract.status == "experimental"
    assert contract.agent_plan_multireference is False
    assert contract.max_images == 1
    assert contract.max_videos == 0
    assert contract.max_audios == 0


def test_unknown_model_uses_legacy_single_image_contract() -> None:
    contract = get_seedance_contract("unknown-model", provider="volcano")

    assert contract.model_family == "legacy"
    assert contract.status == "legacy_single_reference"
    assert contract.max_images == 1
    assert contract.max_videos == 0
    assert contract.max_audios == 0
    assert contract.roles.image == "image_url"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd backend
DEV_MODE=true PYTHONPATH=. pytest -q tests/test_seedance_contract.py
```

Expected: fail with `ModuleNotFoundError: No module named 'app.services.seedance_contract'`.

- [ ] **Step 3: Implement minimal registry**

Create `backend/app/services/seedance_contract.py`:

```python
"""Seedance reference payload contract registry.

This module intentionally marks Seedance 2.x multi-reference behavior as
experimental until official Volcano contract evidence is recorded in
docs/seedance-2-contract-checklist.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


OFFICIAL_SEEDANCE_SOURCES = [
    "https://www.volcengine.com/docs/82379/1520757",
]


@dataclass(frozen=True)
class SeedanceReferenceRoles:
    image: str
    video: str
    audio: str


@dataclass(frozen=True)
class SeedanceContract:
    model_id: str
    provider: str
    model_family: str
    status: str
    roles: SeedanceReferenceRoles
    at_reference_syntax: Optional[str]
    max_images: int
    max_videos: int
    max_audios: int
    pricing_status: str
    agent_plan_multireference: bool
    official_sources: List[str]


def _seedance_20_contract(model_id: str, provider: str) -> SeedanceContract:
    is_agent_plan = provider == "volcano_agent_plan"
    return SeedanceContract(
        model_id=model_id,
        provider=provider,
        model_family="seedance_2",
        status="experimental",
        roles=SeedanceReferenceRoles(
            image="reference_image",
            video="reference_video",
            audio="reference_audio",
        ),
        at_reference_syntax="@image{index}",
        max_images=1 if is_agent_plan else 9,
        max_videos=0 if is_agent_plan else 3,
        max_audios=0 if is_agent_plan else 3,
        pricing_status="unconfirmed",
        agent_plan_multireference=False,
        official_sources=OFFICIAL_SEEDANCE_SOURCES,
    )


def _legacy_contract(model_id: str, provider: str) -> SeedanceContract:
    return SeedanceContract(
        model_id=model_id,
        provider=provider,
        model_family="legacy",
        status="legacy_single_reference",
        roles=SeedanceReferenceRoles(
            image="image_url",
            video="unsupported",
            audio="unsupported",
        ),
        at_reference_syntax=None,
        max_images=1,
        max_videos=0,
        max_audios=0,
        pricing_status="not_applicable",
        agent_plan_multireference=False,
        official_sources=[],
    )


def get_seedance_contract(model_id: str | None, provider: str | None = None) -> SeedanceContract:
    normalized_model_id = str(model_id or "")
    normalized_provider = str(provider or "volcano")
    seedance_2_ids = {
        "doubao-seedance-2-0-260128",
        "doubao-seedance-2-0-fast-260128",
        "volcano.seedance.2_0",
        "volcano.seedance.2_0_fast",
        "doubao-seedance-2.0",
        "doubao-seedance-2.0-fast",
    }
    if normalized_model_id in seedance_2_ids:
        return _seedance_20_contract(normalized_model_id, normalized_provider)
    return _legacy_contract(normalized_model_id, normalized_provider)
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
cd backend
DEV_MODE=true PYTHONPATH=. pytest -q tests/test_seedance_contract.py
```

Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/seedance_contract.py backend/tests/test_seedance_contract.py
git commit -m "feat: add seedance reference contract registry"
```

---

## Task 2: Adapter Metadata From Contract Registry

**Files:**
- Modify: `backend/app/services/video_reference_adapter.py`
- Modify: `backend/tests/test_reference_package.py`

- [ ] **Step 1: Write failing adapter metadata test**

Append this test to `backend/tests/test_reference_package.py`:

```python
def test_provider_content_records_seedance_contract_status() -> None:
    adapter = _adapter_module()
    build_content = getattr(adapter, "build_video_provider_content")

    result = build_content(
        final_prompt="米粒举起星灯尾巴，照亮雨夜屋顶。",
        duration=4,
        resolution="720p",
        reference_package={
            "images": [{"url": "https://cdn.example.com/mili-front.png"}],
            "videos": [{"url": "https://cdn.example.com/prev-shot.mp4"}],
            "audios": [{"url": "https://cdn.example.com/voice.wav"}],
            "at_reference_text": "@image1 主角定稿图；@video1 上一镜头；@audio1 角色声线。",
        },
        model_limits={"images": 9, "videos": 3, "audios": 3},
        model_id="doubao-seedance-2-0-260128",
        provider="volcano",
    )

    metadata = result["metadata"]
    assert metadata["contract_status"] == "experimental"
    assert metadata["contract_model_family"] == "seedance_2"
    assert metadata["contract_roles"] == {
        "image": "reference_image",
        "video": "reference_video",
        "audio": "reference_audio",
    }
    assert metadata["contract_pricing_status"] == "unconfirmed"
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
cd backend
DEV_MODE=true PYTHONPATH=. pytest -q tests/test_reference_package.py::test_provider_content_records_seedance_contract_status
```

Expected: fail because `build_video_provider_content()` does not accept `model_id/provider` and metadata does not include contract fields.

- [ ] **Step 3: Update adapter signature and metadata**

Modify `backend/app/services/video_reference_adapter.py`:

```python
from app.services.seedance_contract import get_seedance_contract
```

Change the function signature:

```python
def build_video_provider_content(
    *,
    final_prompt: str,
    duration: int,
    resolution: str,
    provider_image_url: Optional[str] = None,
    reference_package: Optional[Dict[str, Any]] = None,
    model_limits: Optional[Dict[str, Any]] = None,
    model_id: Optional[str] = None,
    provider: Optional[str] = None,
    camera_fixed: bool = False,
    watermark: bool = True,
) -> Dict[str, Any]:
```

Add this near the top of the function after `package = ...`:

```python
    contract = get_seedance_contract(model_id, provider)
    contract_metadata = {
        "contract_status": contract.status,
        "contract_model_family": contract.model_family,
        "contract_roles": {
            "image": contract.roles.image,
            "video": contract.roles.video,
            "audio": contract.roles.audio,
        },
        "contract_pricing_status": contract.pricing_status,
        "contract_agent_plan_multireference": contract.agent_plan_multireference,
    }
```

Replace the hard-coded multimodal roles:

```python
                "role": contract.roles.image,
```

```python
                "role": contract.roles.video,
```

```python
                "role": contract.roles.audio,
```

Merge `contract_metadata` into every returned `metadata` dict:

```python
"metadata": {
    **contract_metadata,
    "mode": "multimodal",
    "image_count": len(images),
    "video_count": len(videos),
    "audio_count": len(audios),
}
```

Apply the same `**contract_metadata` pattern to `text_only` and `single_image` branches.

- [ ] **Step 4: Pass model/provider from workflow**

Modify the call site in `backend/app/api/v1/endpoints/workflow.py` where `build_video_provider_content()` is called:

```python
provider_content = build_video_provider_content(
    final_prompt=final_prompt,
    duration=shot.duration or request.duration,
    resolution=request.resolution,
    provider_image_url=provider_image_url,
    reference_package=reference_package,
    model_limits=video_reference_limits,
    model_id=selected_video_model.get("api_model") or selected_video_model.get("model_id"),
    provider=selected_video_model.get("provider") or selected_video_model.get("provider_name"),
    camera_fixed=request.camera_fixed,
    watermark=request.watermark,
)
```

If the local variable name is not `provider_content`, keep the existing variable name and only add `model_id` and `provider` arguments.

- [ ] **Step 5: Run focused tests**

Run:

```bash
cd backend
DEV_MODE=true PYTHONPATH=. pytest -q tests/test_seedance_contract.py tests/test_reference_package.py test_workflow_routes.py::test_workflow_media_batch_submits_seedance20_reference_package_content
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/video_reference_adapter.py backend/app/api/v1/endpoints/workflow.py backend/tests/test_reference_package.py
git commit -m "feat: record seedance contract status in reference payloads"
```

---

## Task 3: Official Contract Verification Dossier

**Files:**
- Create: `docs/seedance-2-contract-checklist.md`
- Modify: `docs/continuous-anime-production-implementation-plan-v2.md`

- [ ] **Step 1: Create the checklist document**

Create `docs/seedance-2-contract-checklist.md`:

```markdown
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
```

- [ ] **Step 2: Link the checklist from V2 plan**

Modify `docs/continuous-anime-production-implementation-plan-v2.md` in the S2-E section. Replace the current unconfirmed note with:

```markdown
官方契约核对记录统一维护在 `docs/seedance-2-contract-checklist.md`。在该清单满足 promotion rule 前，代码层必须继续把 Seedance 2.x 多参考标记为 `experimental`，Agent Plan 通道保持单参考兼容路径。
```

- [ ] **Step 3: Verify docs references**

Run:

```bash
rg -n "seedance-2-contract-checklist|experimental|Agent Plan 通道保持单参考|@图\{index\}|shot\.audio_url|Access date|Evidence artifact/test" docs
```

Expected: output includes both `docs/seedance-2-contract-checklist.md` and `docs/continuous-anime-production-implementation-plan-v2.md`.

- [ ] **Step 4: Commit**

```bash
git add docs/seedance-2-contract-checklist.md docs/continuous-anime-production-implementation-plan-v2.md
git commit -m "docs: add seedance official contract checklist"
```

---

## Task 4: Real Novel Context Acceptance Fixture

**Files:**
- Create: `backend/scripts/create_series_acceptance_fixture.py`
- Test: `backend/tests/test_series_acceptance_fixture.py`

- [ ] **Step 1: Write failing dry-run fixture tests**

Create `backend/tests/test_series_acceptance_fixture.py`:

```python
from __future__ import annotations

from scripts.create_series_acceptance_fixture import build_fixture_payload


def test_fixture_payload_contains_real_series_context() -> None:
    payload = build_fixture_payload(stamp="unit-test")

    assert payload["novel"]["title"].startswith("Series Studio Acceptance")
    assert len(payload["chapters"]) == 3
    assert payload["series_plan"]["target_episode_count"] == 3
    assert payload["workflow"]["title"].endswith("Episode 1")
    assert payload["workflow"]["novel_id_ref"] == "novel"
    assert payload["workflow"]["chapter_id_ref"] == "chapter-1"
    assert payload["shots"][0]["entity_refs"]["characters"][0]["name"] == "林澈"
    assert payload["assets"][0]["entity_ref"] == "character-main"


def test_fixture_payload_has_acceptance_urls() -> None:
    payload = build_fixture_payload(stamp="unit-test")

    assert payload["acceptance_urls"] == [
        "/novels/{novel_id}",
        "/studio?workflow_id={workflow_id}&novel_id={novel_id}&chapter_id={chapter_id}",
        "/studio/cards?novel_id={novel_id}",
        "/studio/continuity-review?workflow_id={workflow_id}&novel_id={novel_id}&chapter_id={chapter_id}",
        "/studio/shot-review?workflow_id={workflow_id}&novel_id={novel_id}&chapter_id={chapter_id}",
    ]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd backend
DEV_MODE=true PYTHONPATH=. pytest -q tests/test_series_acceptance_fixture.py
```

Expected: fail because `backend/scripts/create_series_acceptance_fixture.py` does not exist.

- [ ] **Step 3: Implement fixture payload builder**

Create `backend/scripts/create_series_acceptance_fixture.py`:

```python
from __future__ import annotations

import argparse
import json
from datetime import datetime
from typing import Any, Dict


def build_fixture_payload(stamp: str | None = None) -> Dict[str, Any]:
    suffix = stamp or datetime.utcnow().strftime("%Y%m%d%H%M%S")
    title = f"Series Studio Acceptance - 星轨少年 - {suffix}"
    return {
        "novel": {
            "title": title,
            "genre": "连续动漫",
            "description": "少年林澈在废城天台发现星轨罗盘，三集内完成觉醒、追踪与第一次对决。",
            "tags": ["series-studio-acceptance", "anime", "multi-episode"],
        },
        "chapters": [
            {
                "ref": "chapter-1",
                "title": "第一章 天台星轨",
                "chapter_number": 1,
                "content": "林澈在雨后的废城天台捡到星轨罗盘，罗盘投出蓝金色星线。",
            },
            {
                "ref": "chapter-2",
                "title": "第二章 旧站追光",
                "chapter_number": 2,
                "content": "林澈带着罗盘穿过旧地铁站，发现反派留下的黑色星尘。",
            },
            {
                "ref": "chapter-3",
                "title": "第三章 月台初战",
                "chapter_number": 3,
                "content": "林澈在月台保护同伴，第一次用星轨罗盘展开护盾。",
            },
        ],
        "story_bible": {
            "title": f"{title} Production Bible",
            "style": "蓝金赛璐璐二维动漫，干净线条，废城冷色和星轨暖光稳定对比。",
            "worldview": "星轨罗盘能读取城市遗留的能量路线。",
            "character_rules": [
                {"name": "林澈", "role": "主角", "appearance": "黑发少年，蓝色短外套，左手腕戴星轨罗盘。", "voice": "male-qn-qingse"},
                {"name": "许眠", "role": "同伴", "appearance": "短发少女，橙色雨衣，携带旧相机。", "voice": "female-shaonv"},
            ],
            "scene_rules": [
                {"name": "废城天台", "visual": "雨后积水、蓝灰楼群、远处霓虹残光。"},
                {"name": "旧地铁站", "visual": "废弃月台、断裂灯箱、黑色星尘。"},
            ],
            "prop_rules": [
                {"name": "星轨罗盘", "visual": "腕带式蓝金罗盘，展开时有环形星线。"},
            ],
        },
        "entities": [
            {"ref": "character-main", "entity_type": "character", "name": "林澈"},
            {"ref": "character-support", "entity_type": "character", "name": "许眠"},
            {"ref": "scene-rooftop", "entity_type": "scene", "name": "废城天台"},
            {"ref": "prop-compass", "entity_type": "prop", "name": "星轨罗盘"},
        ],
        "assets": [
            {"entity_ref": "character-main", "view_key": "front", "name": "林澈正面定稿"},
            {"entity_ref": "character-main", "view_key": "side", "name": "林澈侧面定稿"},
            {"entity_ref": "scene-rooftop", "view_key": "establishing", "name": "废城天台全景定稿"},
            {"entity_ref": "prop-compass", "view_key": "main", "name": "星轨罗盘主视图"},
        ],
        "series_plan": {
            "target_episode_count": 3,
            "chapters_per_episode": 1,
            "target_duration_seconds": 45,
            "style": "蓝金赛璐璐二维动漫",
            "persist": True,
        },
        "workflow": {
            "title": f"{title} Episode 1",
            "novel_id_ref": "novel",
            "chapter_id_ref": "chapter-1",
        },
        "shots": [
            {
                "shot_number": 1,
                "duration": 4,
                "prompt": "林澈站在雨后废城天台，星轨罗盘发出蓝金光。",
                "dialogue": "林澈：这条光线在指路。",
                "entity_refs": {
                    "characters": [{"ref": "character-main", "name": "林澈"}],
                    "scenes": [{"ref": "scene-rooftop", "name": "废城天台"}],
                    "props": [{"ref": "prop-compass", "name": "星轨罗盘"}],
                },
            }
        ],
        "acceptance_urls": [
            "/novels/{novel_id}",
            "/studio?workflow_id={workflow_id}&novel_id={novel_id}&chapter_id={chapter_id}",
            "/studio/cards?novel_id={novel_id}",
            "/studio/continuity-review?workflow_id={workflow_id}&novel_id={novel_id}&chapter_id={chapter_id}",
            "/studio/shot-review?workflow_id={workflow_id}&novel_id={novel_id}&chapter_id={chapter_id}",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--stamp", default=None)
    args = parser.parse_args()
    payload = build_fixture_payload(args.stamp)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Add package import marker if needed**

If `backend/scripts` is not importable, create `backend/scripts/__init__.py`:

```python
"""Backend helper scripts used by tests and manual acceptance."""
```

- [ ] **Step 5: Run tests**

Run:

```bash
cd backend
DEV_MODE=true PYTHONPATH=. pytest -q tests/test_series_acceptance_fixture.py
python3 scripts/create_series_acceptance_fixture.py --dry-run --stamp manual-check | head -40
```

Expected: pytest passes and the dry-run command prints JSON with `Series Studio Acceptance`.

- [ ] **Step 6: Commit**

```bash
git add backend/scripts/create_series_acceptance_fixture.py backend/scripts/__init__.py backend/tests/test_series_acceptance_fixture.py
git commit -m "test: add real series studio acceptance fixture"
```

---

## Task 5: Browser Acceptance With Real Novel Context

**Files:**
- Create: `frontend/e2e/series-studio-real-context.spec.ts`
- Modify: `docs/superpowers/plans/2026-07-06-studio-smart-console-manual-acceptance.md`

- [ ] **Step 1: Write the real-context browser spec**

Create `frontend/e2e/series-studio-real-context.spec.ts`:

```ts
import { expect, test } from '@playwright/test';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1';

test.skip(process.env.REAL_CONTEXT_E2E !== '1', 'Set REAL_CONTEXT_E2E=1 after seeding the acceptance fixture.');

async function api(path: string) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { Authorization: `Bearer ${process.env.REAL_CONTEXT_E2E_TOKEN || ''}` },
  });
  expect(response.ok(), `${path} should return ${response.status}`).toBeTruthy();
  return response.json();
}

test('Series Studio loads a workflow with novel and chapter context', async ({ page }) => {
  const workflowId = process.env.REAL_CONTEXT_WORKFLOW_ID || '';
  const novelId = process.env.REAL_CONTEXT_NOVEL_ID || '';
  const chapterId = process.env.REAL_CONTEXT_CHAPTER_ID || '';
  expect(workflowId, 'REAL_CONTEXT_WORKFLOW_ID is required').not.toBe('');
  expect(novelId, 'REAL_CONTEXT_NOVEL_ID is required').not.toBe('');
  expect(chapterId, 'REAL_CONTEXT_CHAPTER_ID is required').not.toBe('');

  const snapshot = await api(`/studio/workflows/${workflowId}/snapshot`);
  expect(snapshot.workflow.novel_id).toBe(novelId);
  expect(snapshot.workflow.chapter_id).toBe(chapterId);

  await page.addInitScript((token) => {
    localStorage.setItem('auth_token', token as string);
    localStorage.setItem('user', JSON.stringify({ id: 'dev-user-001', username: 'dev-user-001' }));
  }, process.env.REAL_CONTEXT_E2E_TOKEN || '');

  await page.goto(`/studio?workflow_id=${workflowId}&novel_id=${novelId}&chapter_id=${chapterId}`);
  await expect(page.getByTestId('studio-command-bar')).toBeVisible();
  await expect(page.getByTestId('studio-stage-flow')).toBeVisible();
  await expect(page.getByText('Production Bible')).toBeVisible();

  await page.goto(`/studio/cards?novel_id=${novelId}`);
  await expect(page.getByText('定稿卡')).toBeVisible();

  await page.goto(`/studio/shot-review?workflow_id=${workflowId}&novel_id=${novelId}&chapter_id=${chapterId}`);
  await expect(page.getByText(/镜头|复审|重生/)).toBeVisible();
});
```

- [ ] **Step 2: Run spec to verify skip by default**

Run:

```bash
cd frontend
npx playwright test e2e/series-studio-real-context.spec.ts --project=chromium
```

Expected: skipped with `Set REAL_CONTEXT_E2E=1`.

- [ ] **Step 3: Run against seeded local data**

Start backend and frontend, seed the real fixture, then run:

```bash
cd frontend
REAL_CONTEXT_E2E=1 \
REAL_CONTEXT_E2E_TOKEN="$DEV_AUTH_TOKEN" \
REAL_CONTEXT_WORKFLOW_ID="$WORKFLOW_ID" \
REAL_CONTEXT_NOVEL_ID="$NOVEL_ID" \
REAL_CONTEXT_CHAPTER_ID="$CHAPTER_ID" \
npx playwright test e2e/series-studio-real-context.spec.ts --project=chromium --workers=1
```

Expected: `1 passed`.

- [ ] **Step 4: Update manual acceptance evidence**

Append this section after exporting the real fixture IDs:

```bash
cat >> docs/superpowers/plans/2026-07-06-studio-smart-console-manual-acceptance.md <<EOF

## Real Novel Context Follow-up

Date: 2026-07-06

This follow-up validates a workflow that contains both `novel_id` and `chapter_id`.

| Field | Value |
| --- | --- |
| Novel ID | ${NOVEL_ID} |
| Chapter ID | ${CHAPTER_ID} |
| Workflow ID | ${WORKFLOW_ID} |
| Command | `REAL_CONTEXT_E2E=1 npx playwright test e2e/series-studio-real-context.spec.ts --project=chromium --workers=1` |
| Result | 1 passed |

Acceptance coverage:

- `/studio` command bar used the real workflow context.
- `/studio/cards` loaded by `novel_id`.
- `/studio/shot-review` preserved `workflow_id`, `novel_id`, and `chapter_id`.
EOF
```

- [ ] **Step 5: Commit**

```bash
git add frontend/e2e/series-studio-real-context.spec.ts docs/superpowers/plans/2026-07-06-studio-smart-console-manual-acceptance.md
git commit -m "test: add real context series studio browser acceptance"
```

---

## Task 6: Budget-Gated Live Cloud Canary

**Files:**
- Modify: `frontend/e2e/live-anime-production-seedance.spec.ts`
- Modify: `package.json`

- [ ] **Step 1: Add live budget guard test setup**

Modify the top of `frontend/e2e/live-anime-production-seedance.spec.ts`:

```ts
const LIVE_MAX_RMB = Number(process.env.LIVE_ANIME_E2E_MAX_RMB || '0');
const LIVE_EPISODE_COUNT = Number(process.env.LIVE_ANIME_E2E_EPISODES || '3');
const LIVE_SHOTS_PER_EPISODE = Number(process.env.LIVE_ANIME_E2E_SHOTS_PER_EPISODE || '2');

test.skip(process.env.LIVE_ANIME_E2E !== '1', '设置 LIVE_ANIME_E2E=1 后才运行真实动漫制作全流程测试。');
test.skip(LIVE_MAX_RMB <= 0, '设置 LIVE_ANIME_E2E_MAX_RMB 才允许真实云端调用。');
test.skip(LIVE_EPISODE_COUNT < 1 || LIVE_SHOTS_PER_EPISODE < 1, '真实云端 canary 至少需要 1 集和 1 个镜头。');
```

- [ ] **Step 2: Assert the live config is not a legacy-only config**

Update `assertRequiredModelConfigs()` so the video model assertion allows Seedance 2.x and records the actual model:

```ts
const allowedVideoModels = [
  'doubao-seedance-2-0-260128',
  'doubao-seedance-2-0-fast-260128',
  'doubao-seedance-1-5-pro-251215',
];
expect(allowedVideoModels, `视频模型 ${video.model_id} 必须是明确允许的 live canary 模型`).toContain(video.model_id);
```

- [ ] **Step 3: Write sanitized canary artifact**

Add this helper near the API helpers:

```ts
async function writeLiveArtifact(payload: unknown) {
  const fs = await import('fs/promises');
  const path = await import('path');
  const outputDir = path.join(process.cwd(), '..', 'output', 'live-anime');
  await fs.mkdir(outputDir, { recursive: true });
  const filename = `canary-${Date.now()}.json`;
  const sanitized = JSON.stringify(payload, (key, value) => {
    if (/token|key|secret|authorization/i.test(key)) return '[redacted]';
    return value;
  }, 2);
  await fs.writeFile(path.join(outputDir, filename), sanitized, 'utf8');
}
```

At the end of the live test, after workflow status assertions, write:

```ts
await writeLiveArtifact({
  status: 'passed',
  workflowId: fixture.workflowId,
  liveEpisodeCount: LIVE_EPISODE_COUNT,
  liveShotsPerEpisode: LIVE_SHOTS_PER_EPISODE,
  maxRmb: LIVE_MAX_RMB,
  createdAt: new Date().toISOString(),
});
```

- [ ] **Step 4: Add package command**

Modify root `package.json` scripts:

```json
"verify:live:anime": "npm --prefix frontend run e2e -- live-anime-production-seedance.spec.ts --project=chromium --workers=1"
```

Keep `verify:quick` unchanged. Live canary must never run by default.

- [ ] **Step 5: Verify default skip and documented live command**

Run default skip:

```bash
npm run verify:live:anime
```

Expected: skipped because `LIVE_ANIME_E2E` and `LIVE_ANIME_E2E_MAX_RMB` are not set.

Run live canary only when a human has approved cost:

```bash
LIVE_ANIME_E2E=1 \
LIVE_ANIME_E2E_MAX_RMB=50 \
LIVE_ANIME_E2E_EPISODES=3 \
LIVE_ANIME_E2E_SHOTS_PER_EPISODE=2 \
LIVE_ANIME_E2E_VIDEO_CONFIG_ID="$VIDEO_CONFIG_ID" \
LIVE_ANIME_E2E_AUDIO_CONFIG_ID="$AUDIO_CONFIG_ID" \
npm run verify:live:anime
```

Expected: `1 passed` and a sanitized JSON artifact under `output/live-anime/`.

- [ ] **Step 6: Commit**

```bash
git add frontend/e2e/live-anime-production-seedance.spec.ts package.json
git commit -m "test: gate live anime canary by explicit budget"
```

---

## Task 7: Generated Artifact Policy

**Files:**
- Create: `backend/app/services/generated_artifact_policy.py`
- Test: `backend/tests/test_generated_artifact_policy.py`
- Modify: `.gitignore`

- [ ] **Step 1: Write failing artifact policy tests**

Create `backend/tests/test_generated_artifact_policy.py`:

```python
from __future__ import annotations

from pathlib import Path

from app.services.generated_artifact_policy import classify_generated_artifact


def test_runtime_generated_media_is_ignored() -> None:
    assert classify_generated_artifact(Path("backend/static/dev/audio-1.mp3")).bucket == "runtime_generated"
    assert classify_generated_artifact(Path("backend/static/generated/images/shot.png")).bucket == "runtime_generated"
    assert classify_generated_artifact(Path("backend/static/generated/videos/shot.mp4")).bucket == "runtime_generated"
    assert classify_generated_artifact(Path("backend/static/exports/final.json")).bucket == "runtime_generated"


def test_manual_acceptance_outputs_are_ignored() -> None:
    result = classify_generated_artifact(Path("output/playwright/manual-acceptance-20260706/result.json"))

    assert result.bucket == "acceptance_output"
    assert result.should_ignore is True


def test_seed_starter_assets_require_review_not_blanket_ignore() -> None:
    result = classify_generated_artifact(Path("backend/static/starter/style-cyber-anime.svg"))

    assert result.bucket == "seed_asset_review_required"
    assert result.should_ignore is False


def test_source_files_are_not_generated_artifacts() -> None:
    result = classify_generated_artifact(Path("backend/app/api/v1/endpoints/workflow.py"))

    assert result.bucket == "source"
    assert result.should_ignore is False
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd backend
DEV_MODE=true PYTHONPATH=. pytest -q tests/test_generated_artifact_policy.py
```

Expected: fail because `generated_artifact_policy` does not exist.

- [ ] **Step 3: Implement artifact policy**

Create `backend/app/services/generated_artifact_policy.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ArtifactClassification:
    path: str
    bucket: str
    should_ignore: bool


def _posix(path: Path) -> str:
    return path.as_posix().lstrip("./")


def classify_generated_artifact(path: Path) -> ArtifactClassification:
    value = _posix(path)
    runtime_prefixes = (
        "backend/static/dev/",
        "backend/static/generated/",
        "backend/static/exports/",
        "frontend/test-results/",
        "test-results/",
        ".playwright-cli/",
        ".codegraph/",
        ".logs/",
        ".superpowers/",
    )
    acceptance_prefixes = (
        "output/playwright/",
        "output/live-anime/",
    )
    if value.startswith(runtime_prefixes) or value.endswith(".tsbuildinfo"):
        return ArtifactClassification(value, "runtime_generated", True)
    if value.startswith(acceptance_prefixes):
        return ArtifactClassification(value, "acceptance_output", True)
    if value.startswith("backend/static/starter/"):
        return ArtifactClassification(value, "seed_asset_review_required", False)
    return ArtifactClassification(value, "source", False)
```

- [ ] **Step 4: Update `.gitignore`**

Append:

```gitignore

# Local generated media and automation outputs
backend/static/dev/
backend/static/generated/
backend/static/exports/
output/playwright/
output/live-anime/
frontend/test-results/
test-results/
*.tsbuildinfo

# Local tool caches
.codegraph/
.logs/
.playwright-cli/
.superpowers/
```

Do not ignore `backend/static/starter/` in this task. Those files need explicit product review because starter references may be intended seed assets.

- [ ] **Step 5: Run tests and status check**

Run:

```bash
cd backend
DEV_MODE=true PYTHONPATH=. pytest -q tests/test_generated_artifact_policy.py
cd ..
git status --short | sed -n '1,80p'
```

Expected: tests pass, and `backend/static/dev`, `backend/static/generated`, `output/playwright`, `.codegraph`, `.logs`, `.playwright-cli`, `.superpowers`, and `frontend/tsconfig.tsbuildinfo` no longer flood status.

- [ ] **Step 6: Commit**

```bash
git add .gitignore backend/app/services/generated_artifact_policy.py backend/tests/test_generated_artifact_policy.py
git commit -m "chore: classify and ignore generated runtime artifacts"
```

---

## Task 8: Generated Artifact Audit Script

**Files:**
- Create: `backend/scripts/audit_generated_artifacts.py`
- Modify: `package.json`

- [ ] **Step 1: Write the audit script**

Create `backend/scripts/audit_generated_artifacts.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict

from app.services.generated_artifact_policy import classify_generated_artifact


SCAN_ROOTS = [
    Path("backend/static/dev"),
    Path("backend/static/generated"),
    Path("backend/static/exports"),
    Path("backend/static/starter"),
    Path("output/playwright"),
    Path("output/live-anime"),
]


def audit(root: Path) -> Dict[str, Dict[str, int]]:
    summary: Dict[str, Dict[str, int]] = {}
    for scan_root in SCAN_ROOTS:
        absolute = root / scan_root
        if not absolute.exists():
            continue
        for item in absolute.rglob("*"):
            if not item.is_file():
                continue
            rel = item.relative_to(root)
            classification = classify_generated_artifact(rel)
            bucket = summary.setdefault(classification.bucket, {"count": 0, "bytes": 0})
            bucket["count"] += 1
            bucket["bytes"] += item.stat().st_size
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    summary = audit(root)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return
    for bucket, values in sorted(summary.items()):
        size_mb = values["bytes"] / 1024 / 1024
        print(f"{bucket}: {values['count']} files, {size_mb:.2f} MB")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Add package command**

Modify root `package.json` scripts:

```json
"audit:artifacts": "cd backend && PYTHONPATH=. python3 scripts/audit_generated_artifacts.py --root .."
```

- [ ] **Step 3: Run audit**

Run:

```bash
npm run audit:artifacts
```

Expected: prints bucket counts such as `runtime_generated`, `acceptance_output`, and `seed_asset_review_required`.

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/audit_generated_artifacts.py package.json
git commit -m "chore: add generated artifact audit command"
```

---

## Task 9: Full Regression And Decision Gate

**Files:**
- Modify: `docs/superpowers/plans/2026-07-06-series-studio-production-hardening.md`

- [ ] **Step 1: Run deterministic regression**

Run:

```bash
git diff --check
npm run verify:frontend
cd backend && DEV_MODE=true PYTHONPATH=. python3 -m pytest -q
cd ..
npm run verify:e2e
npm run audit:artifacts
```

Expected:

- `git diff --check` passes.
- Frontend typecheck/build passes.
- Backend pytest passes.
- Smoke E2E passes.
- Artifact audit prints a concise summary.

- [ ] **Step 2: Run optional real-context acceptance**

Run only after local fixture IDs are available:

```bash
cd frontend
REAL_CONTEXT_E2E=1 \
REAL_CONTEXT_E2E_TOKEN="$DEV_AUTH_TOKEN" \
REAL_CONTEXT_WORKFLOW_ID="$WORKFLOW_ID" \
REAL_CONTEXT_NOVEL_ID="$NOVEL_ID" \
REAL_CONTEXT_CHAPTER_ID="$CHAPTER_ID" \
npx playwright test e2e/series-studio-real-context.spec.ts --project=chromium --workers=1
```

Expected: `1 passed`.

- [ ] **Step 3: Run optional live canary**

Run only after human cost approval:

```bash
LIVE_ANIME_E2E=1 \
LIVE_ANIME_E2E_MAX_RMB=50 \
LIVE_ANIME_E2E_EPISODES=3 \
LIVE_ANIME_E2E_SHOTS_PER_EPISODE=2 \
LIVE_ANIME_E2E_VIDEO_CONFIG_ID="$VIDEO_CONFIG_ID" \
LIVE_ANIME_E2E_AUDIO_CONFIG_ID="$AUDIO_CONFIG_ID" \
npm run verify:live:anime
```

Expected: `1 passed` and a sanitized artifact under `output/live-anime/`.

- [ ] **Step 4: Record production readiness decision**

Append this section to this plan after execution:

```markdown
## Execution Record

| Check | Result | Evidence |
| --- | --- | --- |
| Deterministic regression | recorded after run | command output summary |
| Real-context acceptance | recorded after run | workflow_id/novel_id/chapter_id |
| Live canary | recorded after run or skipped with reason | output/live-anime artifact path |
| Seedance contract status | experimental or confirmed | docs/seedance-2-contract-checklist.md |
| Artifact hygiene | recorded after run | npm run audit:artifacts summary |

Decision:

- `internal_trial_ready` if deterministic regression and real-context acceptance pass.
- `series_production_candidate` only if live canary passes and Seedance contract checklist is confirmed.
- `commercial_series_ready` only after three consecutive live canaries pass on separate days with no manual database repair.
```

- [ ] **Step 5: Commit execution record**

```bash
git add docs/superpowers/plans/2026-07-06-series-studio-production-hardening.md
git commit -m "docs: record series studio hardening verification"
```

---

## Suggested Commit Order

1. `feat: add seedance reference contract registry`
2. `feat: record seedance contract status in reference payloads`
3. `docs: add seedance official contract checklist`
4. `test: add real series studio acceptance fixture`
5. `test: add real context series studio browser acceptance`
6. `test: gate live anime canary by explicit budget`
7. `chore: classify and ignore generated runtime artifacts`
8. `chore: add generated artifact audit command`
9. `docs: record series studio hardening verification`

## Risk Controls

- Live canary stays skipped unless `LIVE_ANIME_E2E=1` and `LIVE_ANIME_E2E_MAX_RMB` are both set.
- Official pricing is not hardcoded until a source URL and access date are recorded.
- Agent Plan remains single-reference until proven otherwise.
- Generated media directories are ignored, but `backend/static/starter/` is left visible for explicit product review.
- Contract status remains visible in job metadata so reviewers can tell whether a render used experimental reference semantics.
