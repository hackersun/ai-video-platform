# Story-Linked Asset Consistency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make character, scene, and prop image assets generate from a story-linked visual contract so multi-view assets stay consistent with the novel, chapters, scripts, story bible, and locked production context.

**Architecture:** Add a backend visual contract layer that compacts novel/chapter/script/story-bible/entity context into structured contracts, then make asset generation consume those contracts, model capability policies, reference anchors, and review feedback. Frontend asset management gets a contract/control panel that keeps the simple one-click flow while exposing strict mode, contract issues, and targeted retries for production users.

**Tech Stack:** FastAPI, SQLAlchemy async models, existing `Asset.generation_params` JSON persistence, Next.js 14, React 18, TypeScript, Playwright E2E, pytest.

---

## Non-Negotiable Product Requirements

- Visual contracts must be derived from story context: novel, chapter, script, story bible, story entities, locked assets, and existing production card lineage.
- Contracts must not be generic templates detached from the story. Generic style presets may provide defaults, but story facts override them.
- `standard` and `strict` generation must have a resolved `novel_id`; if the entity or request cannot be tied back to a novel, the API must block with a clear message instead of silently producing a generic asset.
- `chapter_id` and `script_id` are not just metadata. When provided or inferred, their chapter/script content must participate in the contract source text and must be persisted in `story_scope` and `context_sources`.
- The asset endpoint must validate that requested `novel_id/chapter_id/script_id/entity_id` belong together before generation. A mismatched chapter, script, or entity must fail before any model call.
- Generation must support three operating modes:
  - `draft`: fast text-only generation allowed, visibly marked as lower consistency confidence.
  - `standard`: story-linked contract required, anchor/reference used when available.
  - `strict`: story-linked contract and compatible model/reference strategy required; otherwise block with an actionable reason.
- Every generated asset must persist contract id, contract fields, context source ids, anchor/reference lineage, model capability decision, review score, and issue list in `Asset.generation_params`.
- Frontend must keep low barrier operation: users can click one button, see what is being controlled, and retry only failed/low-score views.

## File Structure

- Create `backend/app/services/asset_visual_contract.py`  
  Builds story-linked contracts and prompt blocks for `character`, `scene`, and `prop`.
- Modify `backend/app/services/story_prompt_context.py`  
  Add script-aware context loading and return explicit source ids/summaries used by asset contracts.
- Create `backend/app/services/asset_model_capabilities.py`  
  Normalizes image model capabilities and selects generation strategies for draft/standard/strict.
- Create `backend/app/services/asset_visual_review.py`  
  Produces structured review records and retry advice for generated asset views.
- Modify `backend/app/services/image_prompt_policy.py`  
  Convert current prompt policy into contract-aware prompt blocks.
- Modify `backend/app/services/asset_generation_service.py`  
  Consume contracts, anchors, model strategy, and review feedback during `generate_entity_view_assets`.
- Modify `backend/app/api/v1/endpoints/assets.py`  
  Extend request/response schemas and add contract/review endpoints.
- Modify `frontend/src/app/assets/page.tsx`  
  Add visual contract panel, consistency mode selector, view-level review badges, and targeted retry controls.
- Modify `frontend/src/lib/api-client.ts`  
  Add typed client methods for contracts, reviews, and extended generation options.
- Test `backend/test_asset_multiview_generation.py`  
  Extend backend coverage for story-linked contracts, strict mode, anchors, and review records.
- Create `backend/tests/test_story_prompt_context_assets.py`  
  Unit tests for script-aware story prompt context and story-scope lineage.
- Create `backend/tests/test_asset_visual_contract.py`  
  Unit tests for contract extraction from story context.
- Create `backend/tests/test_asset_model_capabilities.py`  
  Unit tests for model mode decisions and fallback behavior.
- Create `frontend/e2e/assets-consistency-control.spec.ts`  
  End-to-end frontend coverage for contract panel, strict mode, and targeted retries.

---

### Task 0: Story Scope Resolution and Script Context Foundation

**Files:**
- Modify: `backend/app/services/story_prompt_context.py`
- Modify: `backend/app/api/v1/endpoints/assets.py`
- Test: `backend/tests/test_story_prompt_context_assets.py`
- Test: `backend/test_asset_multiview_generation.py`

- [ ] **Step 1: Write failing tests for script-aware context and scope validation**

Create `backend/tests/test_story_prompt_context_assets.py`:

```python
from uuid import uuid4

import pytest

from app.models import Chapter, Novel, Script
from app.services.story_prompt_context import load_story_prompt_context


@pytest.mark.asyncio
async def test_story_prompt_context_includes_script_content(async_session):
    user_id = f"ctx-user-{uuid4()}"
    novel = Novel(id=f"novel-{uuid4()}", user_id=user_id, title="雨巷旧邮局", genre="年代悬疑", description="1980年代小城雨夜。")
    chapter = Chapter(id=f"chapter-{uuid4()}", user_id=user_id, novel_id=novel.id, title="雨夜来信", chapter_number=1, content="旧邮局门外冷蓝雨光。")
    script = Script(
        id=f"script-{uuid4()}",
        user_id=user_id,
        novel_id=novel.id,
        chapter_id=chapter.id,
        title="旧邮局开场",
        description="空间结构和光源说明",
        content="【场景】旧邮局：左侧正门，右侧木柜台，后墙绿色分拣信箱，室内右上方暖黄钨丝灯。",
    )
    async_session.add_all([novel, chapter, script])
    await async_session.commit()

    context = await load_story_prompt_context(
        async_session,
        user_id,
        novel_id=novel.id,
        chapter_id=chapter.id,
        script_id=script.id,
        style="cinematic-2d",
    )

    assert context["novel_id"] == novel.id
    assert context["chapter_id"] == chapter.id
    assert context["script_id"] == script.id
    assert context["script_title"] == "旧邮局开场"
    assert "右侧木柜台" in context["script_summary"]
    assert any(item["name"] == "旧邮局" for item in context["scenes"])
```

Append to `backend/test_asset_multiview_generation.py`:

```python
def test_generate_entity_views_rejects_mismatched_novel_scope(client: TestClient) -> None:
    user_id = f"asset-scope-user-{uuid4()}"
    novel_id = _create_novel(client, user_id)
    other_novel_id = _create_novel(client, user_id)
    scene_id = _create_entity(client, user_id, novel_id, "scene", "旧邮局")

    response = client.post(
        "/api/v1/assets/generate-entity-views",
        json={
            "entity_id": scene_id,
            "novel_id": other_novel_id,
            "view_keys": ["establishing"],
            "style": "cinematic-2d",
            "consistency_mode": "standard",
        },
        headers=auth_headers(user_id),
    )

    assert response.status_code in {400, 422}
    assert "实体不属于指定小说" in response.text


def test_standard_entity_view_generation_requires_novel_scope(client: TestClient) -> None:
    user_id = f"asset-no-novel-user-{uuid4()}"
    scene_id = _create_entity(client, user_id, None, "scene", "游离场景")

    response = client.post(
        "/api/v1/assets/generate-entity-views",
        json={
            "entity_id": scene_id,
            "view_keys": ["establishing"],
            "style": "cinematic-2d",
            "consistency_mode": "standard",
        },
        headers=auth_headers(user_id),
    )

    assert response.status_code == 422
    assert "标准/严格一致性模式需要绑定小说" in response.text
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
pytest backend/tests/test_story_prompt_context_assets.py backend/test_asset_multiview_generation.py::test_generate_entity_views_rejects_mismatched_novel_scope backend/test_asset_multiview_generation.py::test_standard_entity_view_generation_requires_novel_scope -q
```

Expected: fail because `load_story_prompt_context` does not accept `script_id`, and `generate-entity-views` does not accept or validate story-scope request fields.

- [ ] **Step 3: Make `load_story_prompt_context` script-aware**

In `backend/app/services/story_prompt_context.py`:

```python
from app.models import Chapter, Character, Novel, Script, StoryBible, StoryEntity
```

Add the parameter:

```python
async def load_story_prompt_context(
    db: AsyncSession,
    user_id: str,
    *,
    novel_id: Optional[str] = None,
    chapter_id: Optional[str] = None,
    script_id: Optional[str] = None,
    ...
) -> Dict[str, Any]:
```

Load and infer script lineage before building `source_text_parts`:

```python
script: Optional[Script] = None
if script_id:
    script_result = await db.execute(
        select(Script).where(and_(Script.id == script_id, Script.user_id == user_id))
    )
    script = script_result.scalar_one_or_none()
    if script:
        script_extra = script.extra_data if isinstance(script.extra_data, dict) else {}
        novel_id = novel_id or script.novel_id
        chapter_id = chapter_id or script.chapter_id or script_extra.get("chapter_id")
```

Include script text in source extraction:

```python
source_text_parts = [
    title or getattr(novel, "title", None),
    genre or getattr(novel, "genre", None),
    description or getattr(novel, "description", None),
    getattr(chapter, "content", None),
    getattr(script, "title", None),
    getattr(script, "description", None),
    getattr(script, "content", None),
]
```

Return script identifiers and summary:

```python
"script_id": script_id or getattr(script, "id", None),
"script_title": getattr(script, "title", None),
"script_summary": compact_text(getattr(script, "content", None), 800),
```

- [ ] **Step 4: Extend generation request with explicit story scope**

Modify `EntityViewGenerateRequest` in `backend/app/api/v1/endpoints/assets.py`:

```python
class EntityViewGenerateRequest(BaseModel):
    entity_id: str
    novel_id: Optional[str] = Field(None, description="小说ID；标准/严格一致性模式必须能解析到小说")
    chapter_id: Optional[str] = Field(None, description="章节ID，用于章节级连续性契约")
    script_id: Optional[str] = Field(None, description="剧本ID，用于剧本级场景、道具、事件约束")
    view_keys: Optional[List[str]] = Field(None, description="可选视图 key，不传则生成该实体类型全部必备视图")
    style: str = Field("anime", description="anime/xianxia/wuxia/fantasy/urban/cartoon/realistic")
    model_config_id: Optional[str] = None
    consistency_mode: str = Field("standard", pattern="^(draft|standard|strict)$", description="draft/standard/strict")
    force_contract_refresh: bool = False
    anchor_view_key: Optional[str] = Field(None, description="可选锚点视图；场景默认 establishing，角色默认 front，道具默认 main")
```

- [ ] **Step 5: Validate scope before model calls**

At the start of `generate_entity_view_assets` endpoint, after loading the entity:

```python
scope = await validate_asset_scope(
    db,
    user_id,
    novel_id=request.novel_id,
    chapter_id=request.chapter_id,
    script_id=request.script_id,
    entity_id=request.entity_id,
)
if request.consistency_mode in {"standard", "strict"} and not scope.get("novel_id"):
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail="标准/严格一致性模式需要绑定小说，请从小说、章节、剧本或制作卡上下文进入资产生成。",
    )
```

When calling `service.generate_entity_view_assets`, pass resolved scope instead of only the entity fields:

```python
novel_id=scope.get("novel_id"),
chapter_id=scope.get("chapter_id"),
script_id=scope.get("script_id"),
```

- [ ] **Step 6: Run focused tests**

Run:

```bash
pytest backend/tests/test_story_prompt_context_assets.py backend/test_asset_multiview_generation.py::test_generate_entity_views_rejects_mismatched_novel_scope backend/test_asset_multiview_generation.py::test_standard_entity_view_generation_requires_novel_scope -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/story_prompt_context.py backend/app/api/v1/endpoints/assets.py backend/tests/test_story_prompt_context_assets.py backend/test_asset_multiview_generation.py
git commit -m "feat: bind asset generation to story scope"
```

### Task 1: Story-Linked Visual Contract Builder

**Files:**
- Create: `backend/app/services/asset_visual_contract.py`
- Test: `backend/tests/test_asset_visual_contract.py`
- Read existing: `backend/app/services/story_prompt_context.py`
- Read existing: `backend/app/models/story_bible.py`
- Read existing: `backend/app/models/asset.py`

- [ ] **Step 1: Write failing tests for scene, character, and prop contracts**

Create `backend/tests/test_asset_visual_contract.py` with these tests:

```python
import pytest
from types import SimpleNamespace

from app.services.asset_visual_contract import build_visual_contract_from_story, render_contract_prompt_block


class FakeDb:
    pass


@pytest.mark.asyncio
async def test_scene_contract_uses_novel_chapter_story_bible_and_entity(monkeypatch):
    async def fake_load_context(*args, **kwargs):
        return {
            "novel_id": "novel-1",
            "chapter_id": "chapter-1",
            "script_id": "script-1",
            "title": "雨巷旧邮局",
            "genre": "年代悬疑",
            "style": "2D电影",
            "description": "1980年代小城，雨夜，旧邮局里藏着失踪信件。",
            "worldview": "1980年代小城，低饱和灰蓝雨夜，室内暖黄钨丝灯。",
            "negative_prompt": "不要现代快递点，不要欧式大厅，不要多层建筑。",
            "story_bible_id": "bible-1",
            "chapter_title": "第一章 雨夜来信",
            "chapter_summary": "门外冷蓝雨光，邮局内右上方吊灯照亮柜台。",
            "script_title": "旧邮局开场",
            "script_summary": "旧邮局单层砖木结构，左侧正门，右侧木柜台，后墙绿色分拣信箱。",
            "chapters": [
                {"title": "第一章 雨夜来信", "summary": "门外冷蓝雨光，邮局内右上方吊灯照亮柜台。"}
            ],
            "scenes": [
                {"id": "scene-1", "name": "旧邮局", "description": "灰蓝雨夜里的旧邮局，柜台、信箱墙和分拣区清楚。"}
            ],
            "characters": [],
            "props": [],
            "events": [],
        }

    monkeypatch.setattr("app.services.asset_visual_contract.load_story_prompt_context", fake_load_context)
    entity = SimpleNamespace(
        id="scene-1",
        entity_type="scene",
        name="旧邮局",
        description="旧邮局，雨夜，柜台后有绿色分拣信箱。",
        novel_id="novel-1",
        chapter_id="chapter-1",
        script_id="script-1",
        attributes={"weather": "雨夜"},
    )

    contract = await build_visual_contract_from_story(
        FakeDb(),
        "user-1",
        entity=entity,
        style="cinematic-2d",
        chapter_id="chapter-1",
        script_id="script-1",
    )

    assert contract["entity_type"] == "scene"
    assert contract["story_scope"]["novel_id"] == "novel-1"
    assert contract["continuity_axes"]["era"] == "1980年代小城"
    assert contract["continuity_axes"]["weather"] == "雨夜"
    assert contract["continuity_axes"]["lighting_direction"] == "门外冷蓝雨光，室内右上方暖黄灯"
    assert "左侧正门" in contract["spatial_layout"]["fixed_elements"]
    assert "右侧木柜台" in contract["spatial_layout"]["fixed_elements"]
    assert "后墙绿色分拣信箱" in contract["spatial_layout"]["fixed_elements"]
    assert "不要现代快递点" in contract["negative_constraints"]

    prompt_block = render_contract_prompt_block(contract, view_key="layout", view_label="空间布局")
    assert "小说关联视觉契约" in prompt_block
    assert "旧邮局" in prompt_block
    assert "空间布局" in prompt_block
    assert "时代：1980年代小城" in prompt_block
    assert "光源方向：门外冷蓝雨光，室内右上方暖黄灯" in prompt_block


@pytest.mark.asyncio
async def test_character_contract_preserves_story_identity(monkeypatch):
    async def fake_load_context(*args, **kwargs):
        return {
            "novel_id": "novel-1",
            "title": "云海列车",
            "genre": "科幻悬疑",
            "style": "2D动画",
            "description": "少年修理师在云端列车寻找失踪的父亲。",
            "worldview": "云端列车与机械维修工坊。",
            "negative_prompt": "不要改成成年男性，不要换成校服。",
            "characters": [
                {"id": "char-1", "name": "林澈", "description": "17岁少年，银灰短发，蓝色工装夹克，机械手套。"}
            ],
            "scenes": [],
            "props": [],
            "events": [],
        }

    monkeypatch.setattr("app.services.asset_visual_contract.load_story_prompt_context", fake_load_context)
    entity = SimpleNamespace(
        id="char-1",
        entity_type="character",
        name="林澈",
        description="银灰短发，蓝色工装夹克，机械手套。",
        novel_id="novel-1",
        chapter_id=None,
        script_id=None,
        attributes={"appearance": "银灰短发，蓝色工装夹克，机械手套"},
    )

    contract = await build_visual_contract_from_story(FakeDb(), "user-1", entity=entity, style="anime")

    assert contract["identity"]["age"] == "17岁少年"
    assert "银灰短发" in contract["identity"]["appearance"]
    assert "蓝色工装夹克" in contract["identity"]["wardrobe"]
    assert "机械手套" in contract["identity"]["signature_items"]
    assert "不要换成校服" in contract["negative_constraints"]


@pytest.mark.asyncio
async def test_prop_contract_keeps_material_scale_and_usage(monkeypatch):
    async def fake_load_context(*args, **kwargs):
        return {
            "novel_id": "novel-1",
            "title": "铜铃夜行",
            "props": [
                {"id": "prop-1", "name": "裂纹铜铃", "description": "巴掌大小，青铜材质，裂纹中泛青光，系红绳。"}
            ],
            "characters": [],
            "scenes": [],
            "events": [],
        }

    monkeypatch.setattr("app.services.asset_visual_contract.load_story_prompt_context", fake_load_context)
    entity = SimpleNamespace(
        id="prop-1",
        entity_type="prop",
        name="裂纹铜铃",
        description="青铜铃，裂纹发青光，红绳。",
        novel_id="novel-1",
        chapter_id=None,
        script_id=None,
        attributes={},
    )

    contract = await build_visual_contract_from_story(FakeDb(), "user-1", entity=entity, style="xianxia")

    assert contract["prop_dna"]["material"] == "青铜材质"
    assert contract["prop_dna"]["scale"] == "巴掌大小"
    assert "裂纹中泛青光" in contract["prop_dna"]["fixed_marks"]
    assert "红绳" in contract["prop_dna"]["fixed_marks"]
```

- [ ] **Step 2: Run tests and verify they fail for missing module**

Run:

```bash
pytest backend/tests/test_asset_visual_contract.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'app.services.asset_visual_contract'`.

- [ ] **Step 3: Implement `asset_visual_contract.py`**

Create `backend/app/services/asset_visual_contract.py`:

```python
from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.story_prompt_context import compact_text, load_story_prompt_context


def _json_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _json_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(*parts: Any) -> str:
    return " ".join(str(part) for part in parts if part).strip()


def _contains_any(text: str, tokens: list[str]) -> bool:
    return any(token in text for token in tokens)


def _first_match(text: str, patterns: list[tuple[str, str]]) -> str:
    for pattern, value in patterns:
        if re.search(pattern, text):
            return value
    return ""


def _rule_for_name(items: list[Any], name: str) -> str:
    for item in items:
        data = _json_dict(item)
        if data.get("name") == name:
            return _text(data.get("description"), data.get("appearance"), data.get("state"), data.get("rule"))
    return ""


def _items_for_entity_type(context: Dict[str, Any], entity_type: str) -> list[Any]:
    key = {"character": "characters", "scene": "scenes", "prop": "props"}.get(entity_type, "")
    return _json_list(context.get(key)) if key else []


def _contract_id(entity_id: str, entity_type: str, name: str, style: str, source: str) -> str:
    raw = "|".join([entity_id, entity_type, name, style, source])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _scene_axes(source: str) -> Dict[str, str]:
    return {
        "era": _first_match(
            source,
            [
                (r"1980|八十年代|80年代", "1980年代小城"),
                (r"民国", "民国时期"),
                (r"现代|快递", "现代"),
                (r"古代|客栈|衙门", "古代"),
            ],
        ) or "依据小说原文保持，不得自行改变时代",
        "weather": _first_match(
            source,
            [
                (r"雨夜|雨天|雨巷|冷蓝雨光", "雨夜"),
                (r"雪", "雪天"),
                (r"雾", "薄雾"),
                (r"晴|阳光", "晴天"),
            ],
        ) or "依据小说原文保持，不得自行改变天气",
        "lighting_direction": _first_match(
            source,
            [
                (r"门外冷蓝雨光.*右上方.*暖黄|右上方.*暖黄.*门外冷蓝", "门外冷蓝雨光，室内右上方暖黄灯"),
                (r"左侧.*窗光", "左侧窗光"),
                (r"右侧.*窗光", "右侧窗光"),
                (r"吊灯|钨丝灯|暖黄", "室内暖黄顶灯"),
            ],
        ) or "依据小说原文保持，同一场景多视图不得改变光源方向",
        "color_palette": _first_match(
            source,
            [
                (r"灰蓝|冷蓝|雨光", "灰蓝冷雨色 + 暖黄室内灯"),
                (r"低饱和", "低饱和电影色"),
                (r"暖黄", "暖黄旧灯色"),
            ],
        ) or "依据小说原文和风格模板保持统一色彩基调",
    }


def _scene_layout(source: str) -> Dict[str, Any]:
    fixed = []
    for token in ["左侧正门", "右侧木柜台", "后墙绿色分拣信箱", "柜台", "信箱墙", "分拣区", "木门", "砖木结构"]:
        if token in source and token not in fixed:
            fixed.append(token)
    action = []
    for token in ["柜台前", "入口", "通道", "分拣区"]:
        if token in source and token not in action:
            action.append(token)
    return {
        "fixed_elements": fixed or ["从小说/剧本描述中抽取的关键建筑、入口、地标和陈设必须保持"],
        "action_zones": action or ["主要行动区依据小说/剧本保持，不得每张图重新布局"],
        "forbidden_changes": ["不要更换建筑结构", "不要改变入口和柜台相对位置", "不要生成不属于该场景的新地点"],
    }


def _character_identity(name: str, source: str) -> Dict[str, Any]:
    return {
        "name": name,
        "age": _first_match(source, [(r"17岁|十七岁", "17岁少年"), (r"少年", "少年"), (r"少女", "少女")])
        or "按小说角色年龄感保持",
        "appearance": compact_text(source, 260),
        "wardrobe": "、".join(token for token in ["蓝色工装夹克", "黑衣", "白衣", "校服", "斗篷"] if token in source)
        or "按小说服装保持",
        "signature_items": "、".join(token for token in ["机械手套", "古剑", "银色发带", "红绳"] if token in source)
        or "按小说标志物保持",
    }


def _prop_dna(source: str) -> Dict[str, Any]:
    return {
        "material": _first_match(source, [(r"青铜", "青铜材质"), (r"木", "木质"), (r"金属", "金属材质")])
        or "按小说材质保持",
        "scale": _first_match(source, [(r"巴掌大小|掌心|手掌", "巴掌大小"), (r"一人高", "一人高")])
        or "按小说比例保持",
        "fixed_marks": "、".join(token for token in ["裂纹中泛青光", "红绳", "裂纹", "刻印", "磨损"] if token in source)
        or "按小说固定纹理、破损、符号保持",
    }


async def build_visual_contract_from_story(
    db: AsyncSession,
    user_id: str,
    *,
    entity: Any,
    style: str,
    chapter_id: Optional[str] = None,
    script_id: Optional[str] = None,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    context = await load_story_prompt_context(
        db,
        user_id,
        novel_id=getattr(entity, "novel_id", None),
        chapter_id=chapter_id or getattr(entity, "chapter_id", None),
        script_id=script_id or getattr(entity, "script_id", None),
        style=style,
    )
    attributes = _json_dict(getattr(entity, "attributes", None))
    entity_type = str(getattr(entity, "entity_type", ""))
    name = str(getattr(entity, "name", ""))
    story_rule = _rule_for_name(_items_for_entity_type(context, entity_type), name)
    source = _text(
        context.get("title"),
        context.get("genre"),
        context.get("style"),
        context.get("worldview"),
        context.get("description"),
        context.get("chapter_title"),
        context.get("chapter_summary"),
        context.get("script_title"),
        context.get("script_summary"),
        story_rule,
        getattr(entity, "description", None),
        attributes.get("appearance"),
        attributes.get("weather"),
    )
    contract = {
        "id": _contract_id(getattr(entity, "id", ""), entity_type, name, style, source),
        "version": 1,
        "entity_id": getattr(entity, "id", None),
        "entity_type": entity_type,
        "name": name,
        "style": style,
        "story_scope": {
            "novel_id": getattr(entity, "novel_id", None),
            "chapter_id": chapter_id or getattr(entity, "chapter_id", None),
            "script_id": script_id or getattr(entity, "script_id", None),
        },
        "context_sources": {
            "novel_title": context.get("title"),
            "story_bible_id": context.get("story_bible_id"),
            "style": context.get("style"),
            "worldview": context.get("worldview"),
            "chapter_title": context.get("chapter_title"),
            "script_title": context.get("script_title"),
            "negative_prompt": context.get("negative_prompt"),
        },
        "negative_constraints": compact_text(context.get("negative_prompt"), 500),
    }
    if entity_type == "scene":
        contract["continuity_axes"] = _scene_axes(source)
        contract["spatial_layout"] = _scene_layout(source)
    elif entity_type == "character":
        contract["identity"] = _character_identity(name, source)
    elif entity_type == "prop":
        contract["prop_dna"] = _prop_dna(source)
    return contract


def render_contract_prompt_block(contract: Dict[str, Any], *, view_key: str, view_label: str) -> str:
    entity_type = contract.get("entity_type")
    lines = [
        "小说关联视觉契约：以下约束来自小说、章节、剧本、Story Bible 和实体档案，优先级高于通用风格模板。",
        f"契约ID：{contract.get('id')}，实体：{contract.get('name')}，视图：{view_label}（{view_key}）。",
        f"故事范围：novel={contract.get('story_scope', {}).get('novel_id')}，chapter={contract.get('story_scope', {}).get('chapter_id')}，script={contract.get('story_scope', {}).get('script_id')}。",
    ]
    if entity_type == "scene":
        axes = _json_dict(contract.get("continuity_axes"))
        layout = _json_dict(contract.get("spatial_layout"))
        lines.extend(
            [
                f"时代：{axes.get('era')}",
                f"天气：{axes.get('weather')}",
                f"光源方向：{axes.get('lighting_direction')}",
                f"色彩基调：{axes.get('color_palette')}",
                f"固定空间元素：{'、'.join(layout.get('fixed_elements') or [])}",
                f"可行动区域：{'、'.join(layout.get('action_zones') or [])}",
            ]
        )
    elif entity_type == "character":
        identity = _json_dict(contract.get("identity"))
        lines.extend(
            [
                f"身份年龄：{identity.get('age')}",
                f"外貌与服装：{identity.get('appearance')}；{identity.get('wardrobe')}",
                f"标志物：{identity.get('signature_items')}",
            ]
        )
    elif entity_type == "prop":
        prop = _json_dict(contract.get("prop_dna"))
        lines.extend(
            [
                f"材质：{prop.get('material')}",
                f"比例：{prop.get('scale')}",
                f"固定纹理/标记：{prop.get('fixed_marks')}",
            ]
        )
    if contract.get("negative_constraints"):
        lines.append(f"故事负面约束：{contract['negative_constraints']}")
    lines.append("硬规则：同一实体所有视图必须共享以上契约，不得重新发明时代、结构、材质、天气、光源和核心身份。")
    return "\n".join(line for line in lines if line)
```

- [ ] **Step 4: Run tests and verify they pass**

Run:

```bash
pytest backend/tests/test_asset_visual_contract.py -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/asset_visual_contract.py backend/tests/test_asset_visual_contract.py
git commit -m "feat: add story-linked asset visual contracts"
```

---

### Task 2: Contract-Aware Prompt Policy

**Files:**
- Modify: `backend/app/services/image_prompt_policy.py`
- Modify: `backend/app/services/asset_generation_service.py`
- Test: `backend/test_asset_multiview_generation.py`

- [ ] **Step 1: Write failing tests for contract prompt injection**

Append to `backend/test_asset_multiview_generation.py`:

```python
def test_entity_view_prompt_includes_story_contract_for_scene() -> None:
    from app.services.image_prompt_policy import entity_view_prompt

    contract = {
        "id": "contract-scene-1",
        "entity_type": "scene",
        "name": "旧邮局",
        "continuity_axes": {
            "era": "1980年代小城",
            "weather": "雨夜",
            "lighting_direction": "门外冷蓝雨光，室内右上方暖黄灯",
            "color_palette": "灰蓝冷雨色 + 暖黄室内灯",
        },
        "spatial_layout": {
            "fixed_elements": ["左侧正门", "右侧木柜台", "后墙绿色分拣信箱"],
            "action_zones": ["柜台前", "入口通道"],
        },
        "negative_constraints": "不要现代快递点，不要欧式大厅，不要多层建筑。",
    }

    prompt = entity_view_prompt(
        entity_type="scene",
        name="旧邮局",
        description="旧邮局雨夜",
        style_keywords="2D动画电影质感",
        view_label="空间布局",
        prompt_hint="展示人物行动区和遮挡关系。",
        contract=contract,
        view_key="layout",
    )

    assert "小说关联视觉契约" in prompt
    assert "1980年代小城" in prompt
    assert "右侧木柜台" in prompt
    assert "门外冷蓝雨光，室内右上方暖黄灯" in prompt
    assert "不要现代快递点" in prompt
    assert prompt.index("小说关联视觉契约") < prompt.index("视图要求")
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
pytest backend/test_asset_multiview_generation.py::test_entity_view_prompt_includes_story_contract_for_scene -q
```

Expected: fail because current `entity_view_prompt` does not render structured story contract fields.

- [ ] **Step 3: Modify prompt policy**

In `backend/app/services/image_prompt_policy.py`:

- Import `render_contract_prompt_block` from `app.services.asset_visual_contract`.
- In `entity_view_prompt`, replace the simple `视觉契约ID` line with `render_contract_prompt_block(contract, view_key=view_key or "", view_label=view_label)`.
- Keep existing `CHARACTER_VIEW_DIRECTION_CONSTRAINTS`, `SCENE_VIEW_CONSTRAINT`, `PROP_VIEW_CONSTRAINT`, and `GLOBAL_IMAGE_NEGATIVE_CONSTRAINT`.

The target body of `entity_view_prompt` should preserve this order:

```python
contract_block = render_contract_prompt_block(contract, view_key=view_key or "", view_label=view_label)
return "\n".join(
    part
    for part in [
        f"{style_keywords}。",
        contract_block,
        f"生成对象：{entity_labels.get(entity_type, entity_type)}「{name}」的{view_label}参考图。",
        f"设定描述：{description or '保持小说设定一致'}。",
        contract.get("gender_age_hint") or "",
        reference_line,
        f"视图要求：{prompt_hint}。",
        direction_constraint,
        constraints,
        GLOBAL_IMAGE_NEGATIVE_CONSTRAINT,
    ]
    if part
)
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
pytest backend/tests/test_asset_visual_contract.py backend/test_asset_multiview_generation.py::test_entity_view_prompt_includes_story_contract_for_scene -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/image_prompt_policy.py backend/test_asset_multiview_generation.py
git commit -m "feat: inject story contracts into asset prompts"
```

---

### Task 3: Integrate Story Contracts Into Asset Generation

**Files:**
- Modify: `backend/app/services/asset_generation_service.py`
- Modify: `backend/app/api/v1/endpoints/assets.py`
- Test: `backend/test_asset_multiview_generation.py`

- [ ] **Step 1: Write failing API test for story-linked generation params**

Append to `backend/test_asset_multiview_generation.py`:

```python
def test_generate_scene_views_persists_story_linked_contract(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = f"scene-contract-user-{uuid4()}"
    novel_id = _create_novel(client, user_id)
    scene_id = _create_entity(client, user_id, novel_id, "scene", "旧邮局")
    captured_prompts: list[str] = []

    async def _fake_image_config(*args, **kwargs):
        return "key", "volcano", "test-image-model", None

    class _FakeImageService:
        async def generate_image(self, **kwargs):
            captured_prompts.append(kwargs["prompt"])
            return {"data": [{"url": "data:image/png;base64," + _tiny_png_base64()}]}

    monkeypatch.setattr("app.services.asset_generation_service.get_user_image_model_config", _fake_image_config, raising=False)
    monkeypatch.setattr("app.services.asset_generation_service.create_image_generation_service", lambda *args, **kwargs: _FakeImageService(), raising=False)

    response = client.post(
        "/api/v1/assets/generate-entity-views",
        json={
            "entity_id": scene_id,
            "novel_id": novel_id,
            "view_keys": ["establishing", "layout"],
            "style": "cinematic-2d",
            "consistency_mode": "standard",
        },
        headers=auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    establishing = payload["assets"]["establishing"]["generation_params"]
    layout = payload["assets"]["layout"]["generation_params"]
    assert establishing["visual_contract"]["story_scope"]["novel_id"] == novel_id
    assert establishing["visual_contract"]["entity_type"] == "scene"
    assert "context_sources" in establishing["visual_contract"]
    assert layout["reference_view_key"] == "establishing"
    assert layout["reference_asset_id"] == payload["assets"]["establishing"]["id"]
    assert any("小说关联视觉契约" in prompt for prompt in captured_prompts)
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
pytest backend/test_asset_multiview_generation.py::test_generate_scene_views_persists_story_linked_contract -q
```

Expected: fail until asset generation builds a story-linked contract and scene non-anchor views reference `establishing`.

- [ ] **Step 3: Extend request schema**

Modify `EntityViewGenerateRequest` in `backend/app/api/v1/endpoints/assets.py`:

```python
class EntityViewGenerateRequest(BaseModel):
    entity_id: str
    novel_id: Optional[str] = Field(None, description="小说ID；标准/严格一致性模式必须能解析到小说")
    chapter_id: Optional[str] = Field(None, description="章节ID，用于章节级连续性契约")
    script_id: Optional[str] = Field(None, description="剧本ID，用于剧本级场景、道具、事件约束")
    view_keys: Optional[List[str]] = Field(None, description="可选视图 key，不传则生成该实体类型全部必备视图")
    style: str = Field("anime", description="anime/xianxia/wuxia/fantasy/urban/cartoon/realistic")
    model_config_id: Optional[str] = None
    consistency_mode: str = Field("standard", pattern="^(draft|standard|strict)$", description="draft/standard/strict")
    force_contract_refresh: bool = False
    anchor_view_key: Optional[str] = Field(None, description="可选锚点视图；场景默认 establishing，角色默认 front，道具默认 main")
```

- [ ] **Step 4: Resolve story scope and pass it into service**

In `generate_entity_view_assets` endpoint, before calling the service:

```python
scope = await validate_asset_scope(
    db,
    user_id,
    novel_id=request.novel_id,
    chapter_id=request.chapter_id,
    script_id=request.script_id,
    entity_id=request.entity_id,
)

if request.consistency_mode in {"standard", "strict"} and not scope.get("novel_id"):
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail="标准/严格一致性模式需要绑定小说，请从小说、章节、剧本或制作卡上下文进入资产生成。",
    )
```

Inside the `service.generate_entity_view_assets(...)` call, use resolved scope values:

```python
novel_id=scope.get("novel_id"),
chapter_id=scope.get("chapter_id"),
script_id=scope.get("script_id"),
consistency_mode=request.consistency_mode,
force_contract_refresh=request.force_contract_refresh,
anchor_view_key=request.anchor_view_key,
```

- [ ] **Step 5: Update service signature and anchor selection**

In `AssetGenerationService.generate_entity_view_assets`, add parameters:

```python
consistency_mode: str = "standard",
force_contract_refresh: bool = False,
anchor_view_key: Optional[str] = None,
```

Inside the method:

- Add `from types import SimpleNamespace` at the top of `backend/app/services/asset_generation_service.py`.
- Build `visual_contract` with `build_visual_contract_from_story(...)` when `consistency_mode != "draft"`:

```python
if consistency_mode == "draft":
    visual_contract = build_visual_contract(
        entity_id=entity_id,
        entity_type=entity_type,
        name=entity_name,
        description=entity_description,
        style=style,
    )
else:
    visual_contract = await build_visual_contract_from_story(
        self.db,
        self.user_id,
        entity=SimpleNamespace(
            id=entity_id,
            entity_type=entity_type,
            name=entity_name,
            description=entity_description,
            novel_id=novel_id,
            chapter_id=chapter_id,
            script_id=script_id,
            attributes={},
        ),
        style=style,
        chapter_id=chapter_id,
        script_id=script_id,
        force_refresh=force_contract_refresh,
    )
```

- Use current `build_visual_contract(...)` only for draft fallback.
- Determine anchor key:

```python
anchor_key = anchor_view_key or {"character": "front", "scene": "establishing", "prop": "main"}.get(entity_type)
```

- If the anchor key is requested, generate it first by sorting `requested_keys`.
- For every non-anchor view, use `_find_entity_view_asset(entity_type, entity_id, anchor_key)` or the newly generated anchor asset as `reference_asset`.
- Persist:

```python
"consistency_mode": consistency_mode,
"visual_contract": visual_contract,
"anchor_view_key": anchor_key,
"reference_view_key": reference_view_key,
"reference_asset_id": getattr(reference_asset, "id", None) if reference_asset else None,
"reference_asset_url": getattr(reference_asset, "url", None) if reference_asset else None,
```

- [ ] **Step 6: Run focused test**

Run:

```bash
pytest backend/test_asset_multiview_generation.py::test_generate_scene_views_persists_story_linked_contract -q
```

Expected: pass.

- [ ] **Step 7: Run multiview backend suite**

Run:

```bash
pytest backend/test_asset_multiview_generation.py -q
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/v1/endpoints/assets.py backend/app/services/asset_generation_service.py backend/test_asset_multiview_generation.py
git commit -m "feat: generate asset views from story contracts"
```

---

### Task 4: Model Capability Policy and Strict Mode

**Files:**
- Create: `backend/app/services/asset_model_capabilities.py`
- Modify: `backend/app/services/asset_generation_service.py`
- Modify: `backend/app/api/v1/endpoints/assets.py`
- Test: `backend/tests/test_asset_model_capabilities.py`
- Test: `backend/test_asset_multiview_generation.py`

- [ ] **Step 1: Write capability unit tests**

Create `backend/tests/test_asset_model_capabilities.py`:

```python
import pytest

from app.services.asset_model_capabilities import decide_asset_generation_strategy


def test_standard_mode_allows_text_model_with_warning():
    strategy = decide_asset_generation_strategy(
        consistency_mode="standard",
        provider_name="minimax",
        model_id="image-01",
        entity_type="scene",
        has_anchor=True,
        model_limits={"images": 0, "at_reference": False},
    )

    assert strategy["mode"] == "text_contract"
    assert strategy["strict_blocking"] is False
    assert "参考图不会作为模型输入" in strategy["warnings"][0]


def test_strict_mode_requires_reference_capable_model_when_anchor_exists():
    strategy = decide_asset_generation_strategy(
        consistency_mode="strict",
        provider_name="minimax",
        model_id="image-01",
        entity_type="scene",
        has_anchor=True,
        model_limits={"images": 0, "at_reference": False},
    )

    assert strategy["mode"] == "blocked"
    assert strategy["strict_blocking"] is True
    assert strategy["blocking_reason"] == "严格一致模式需要支持参考图输入的图像模型"


def test_strict_mode_accepts_reference_capable_model():
    strategy = decide_asset_generation_strategy(
        consistency_mode="strict",
        provider_name="volcano",
        model_id="doubao-image-reference",
        entity_type="character",
        has_anchor=True,
        model_limits={"images": 1, "at_reference": False},
    )

    assert strategy["mode"] == "reference_image_contract"
    assert strategy["strict_blocking"] is False
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
pytest backend/tests/test_asset_model_capabilities.py -q
```

Expected: fail with missing module.

- [ ] **Step 3: Implement capability policy**

Create `backend/app/services/asset_model_capabilities.py`:

```python
from __future__ import annotations

from typing import Any, Dict

from app.core.model_registry import get_model_reference_limits


def _limits_for(model_id: str, override: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if override is not None:
        return dict(override)
    return get_model_reference_limits(model_id)


def decide_asset_generation_strategy(
    *,
    consistency_mode: str,
    provider_name: str,
    model_id: str,
    entity_type: str,
    has_anchor: bool,
    model_limits: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    limits = _limits_for(model_id, model_limits)
    image_capacity = int(limits.get("images", 0) or 0)
    supports_at_reference = bool(limits.get("at_reference", False))
    can_send_reference = has_anchor and image_capacity > 0

    if consistency_mode == "draft":
        return {
            "mode": "text_contract",
            "strict_blocking": False,
            "warnings": ["草稿模式允许文本契约生成，资产需人工复审后再定稿。"],
            "model_limits": limits,
        }

    if consistency_mode == "strict" and has_anchor and not can_send_reference:
        return {
            "mode": "blocked",
            "strict_blocking": True,
            "blocking_reason": "严格一致模式需要支持参考图输入的图像模型",
            "warnings": [],
            "model_limits": limits,
        }

    if can_send_reference:
        return {
            "mode": "reference_image_contract",
            "strict_blocking": False,
            "warnings": [],
            "model_limits": limits,
            "supports_at_reference": supports_at_reference,
        }

    warning = "当前模型不会把参考图作为模型输入，将仅使用小说视觉契约和文字约束。"
    return {
        "mode": "text_contract",
        "strict_blocking": False,
        "warnings": [warning],
        "model_limits": limits,
    }
```

- [ ] **Step 4: Wire strict mode into generation**

In `AssetGenerationService.generate_entity_view_assets`:

- After resolving `reference_asset`, call `decide_asset_generation_strategy`.
- If `strict_blocking` is true, raise `ValueError(strategy["blocking_reason"])`.
- Persist `model_strategy` into every asset `generation_params`.

Add to success and failure params:

```python
"model_strategy": strategy,
"provider_name": self.provider_name,
"model_id": self.model_id,
```

- [ ] **Step 5: Add API test for strict mode blocking**

Append to `backend/test_asset_multiview_generation.py`:

```python
def test_strict_scene_generation_blocks_without_reference_capable_model(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = f"strict-scene-user-{uuid4()}"
    novel_id = _create_novel(client, user_id)
    scene_id = _create_entity(client, user_id, novel_id, "scene", "旧邮局")

    async def _fake_image_config(*args, **kwargs):
        return "key", "minimax", "image-01", None

    monkeypatch.setattr("app.services.asset_generation_service.get_user_image_model_config", _fake_image_config, raising=False)
    monkeypatch.setattr(
        "app.services.asset_model_capabilities.get_model_reference_limits",
        lambda model_id: {"images": 0, "at_reference": False},
        raising=False,
    )

    response = client.post(
        "/api/v1/assets/generate-entity-views",
        json={"entity_id": scene_id, "view_keys": ["layout"], "style": "anime", "consistency_mode": "strict"},
        headers=auth_headers(user_id),
    )

    assert response.status_code == 422
    assert "严格一致模式需要支持参考图输入" in response.text
```

- [ ] **Step 6: Run tests**

Run:

```bash
pytest backend/tests/test_asset_model_capabilities.py backend/test_asset_multiview_generation.py::test_strict_scene_generation_blocks_without_reference_capable_model -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/asset_model_capabilities.py backend/app/services/asset_generation_service.py backend/app/api/v1/endpoints/assets.py backend/tests/test_asset_model_capabilities.py backend/test_asset_multiview_generation.py
git commit -m "feat: add strict asset model consistency mode"
```

---

### Task 5: Asset Visual Review and Retry Advice

**Files:**
- Create: `backend/app/services/asset_visual_review.py`
- Modify: `backend/app/services/asset_generation_service.py`
- Modify: `backend/app/api/v1/endpoints/assets.py`
- Test: `backend/tests/test_asset_visual_review.py`
- Test: `backend/test_asset_multiview_generation.py`

- [ ] **Step 1: Write visual review service tests**

Create `backend/tests/test_asset_visual_review.py`:

```python
from app.services.asset_visual_review import review_asset_against_contract, retry_prompt_advice


def test_scene_review_flags_missing_contract_axes():
    contract = {
        "entity_type": "scene",
        "continuity_axes": {
            "era": "1980年代小城",
            "weather": "雨夜",
            "lighting_direction": "门外冷蓝雨光，室内右上方暖黄灯",
            "color_palette": "灰蓝冷雨色 + 暖黄室内灯",
        },
        "spatial_layout": {"fixed_elements": ["右侧木柜台", "后墙绿色分拣信箱"]},
    }
    prompt = "生成旧邮局空间布局，雨夜，柜台，信箱墙。"

    review = review_asset_against_contract(contract=contract, view_key="layout", prompt=prompt, provider_result_metadata={})

    assert review["status"] == "needs_review"
    assert review["score"] < 90
    assert "lighting_direction" in review["issues"]
    assert "color_palette" in review["issues"]


def test_retry_advice_strengthens_failed_axes():
    advice = retry_prompt_advice(
        issues=["lighting_direction", "spatial_layout"],
        contract={
            "entity_type": "scene",
            "continuity_axes": {"lighting_direction": "门外冷蓝雨光，室内右上方暖黄灯"},
            "spatial_layout": {"fixed_elements": ["右侧木柜台", "后墙绿色分拣信箱"]},
        },
    )

    assert "必须保持光源方向" in advice
    assert "右侧木柜台" in advice
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
pytest backend/tests/test_asset_visual_review.py -q
```

Expected: fail with missing module.

- [ ] **Step 3: Implement review service**

Create `backend/app/services/asset_visual_review.py`:

```python
from __future__ import annotations

from typing import Any, Dict, List


def _json_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _issue_if_missing(text: str, label: str, expected: str, issues: List[str]) -> None:
    if expected and expected not in text:
        issues.append(label)


def review_asset_against_contract(
    *,
    contract: Dict[str, Any],
    view_key: str,
    prompt: str,
    provider_result_metadata: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    issues: List[str] = []
    text = prompt or ""
    entity_type = contract.get("entity_type")
    if entity_type == "scene":
        axes = _json_dict(contract.get("continuity_axes"))
        layout = _json_dict(contract.get("spatial_layout"))
        _issue_if_missing(text, "era", axes.get("era", ""), issues)
        _issue_if_missing(text, "weather", axes.get("weather", ""), issues)
        _issue_if_missing(text, "lighting_direction", axes.get("lighting_direction", ""), issues)
        _issue_if_missing(text, "color_palette", axes.get("color_palette", ""), issues)
        for element in layout.get("fixed_elements") or []:
            if element not in text:
                issues.append("spatial_layout")
                break
    elif entity_type == "character":
        identity = _json_dict(contract.get("identity"))
        _issue_if_missing(text, "appearance", identity.get("appearance", ""), issues)
        _issue_if_missing(text, "signature_items", identity.get("signature_items", ""), issues)
    elif entity_type == "prop":
        prop = _json_dict(contract.get("prop_dna"))
        _issue_if_missing(text, "material", prop.get("material", ""), issues)
        _issue_if_missing(text, "scale", prop.get("scale", ""), issues)

    unique_issues = list(dict.fromkeys(issues))
    score = max(40, 100 - len(unique_issues) * 12)
    return {
        "score": score,
        "status": "passed" if score >= 90 else "needs_review",
        "issues": unique_issues,
        "view_key": view_key,
        "method": "contract_prompt_coverage",
    }


def retry_prompt_advice(*, issues: List[str], contract: Dict[str, Any]) -> str:
    axes = _json_dict(contract.get("continuity_axes"))
    layout = _json_dict(contract.get("spatial_layout"))
    parts: List[str] = []
    if "lighting_direction" in issues:
        parts.append(f"必须保持光源方向：{axes.get('lighting_direction')}")
    if "color_palette" in issues:
        parts.append(f"必须保持色彩基调：{axes.get('color_palette')}")
    if "era" in issues:
        parts.append(f"必须保持时代：{axes.get('era')}")
    if "weather" in issues:
        parts.append(f"必须保持天气：{axes.get('weather')}")
    if "spatial_layout" in issues:
        parts.append(f"必须保持空间结构：{'、'.join(layout.get('fixed_elements') or [])}")
    if not parts:
        parts.append("必须严格继承当前视觉契约，不得重新设计主体。")
    return "；".join(part for part in parts if part)
```

- [ ] **Step 4: Persist review records during generation**

In `AssetGenerationService.generate_entity_view_assets`, after each successful asset creation:

```python
review = review_asset_against_contract(
    contract=visual_contract,
    view_key=key,
    prompt=prompt,
    provider_result_metadata={"provider": self.provider_name, "model_id": self.model_id},
)
params = dict(asset.generation_params or {})
params["visual_consistency"] = review
if review["status"] != "passed":
    params["retry_prompt_advice"] = retry_prompt_advice(issues=review["issues"], contract=visual_contract)
asset.generation_params = params
await self.db.commit()
await self.db.refresh(asset)
```

- [ ] **Step 5: Add endpoint for explicit asset review**

In `backend/app/api/v1/endpoints/assets.py`, add:

```python
@router.post("/{asset_id}/review-contract", response_model=AssetResponse)
async def review_asset_contract(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    result = await db.execute(select(Asset).where(and_(Asset.id == asset_id, Asset.user_id == user_id)))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")
    params = dict(asset.generation_params) if isinstance(asset.generation_params, dict) else {}
    contract = params.get("visual_contract") if isinstance(params.get("visual_contract"), dict) else {}
    if not contract:
        raise HTTPException(status_code=422, detail="该资产缺少视觉契约，无法复审")
    review = review_asset_against_contract(
        contract=contract,
        view_key=str(params.get("view_key") or params.get("asset_subtype") or ""),
        prompt=asset.source_prompt or "",
        provider_result_metadata={"provider": params.get("provider_name"), "model_id": params.get("model_id")},
    )
    params["visual_consistency"] = review
    params["retry_prompt_advice"] = retry_prompt_advice(issues=review["issues"], contract=contract)
    asset.generation_params = params
    asset.updated_at = utc_now()
    await db.commit()
    await db.refresh(asset)
    return build_asset_response(asset)
```

Ensure imports include:

```python
from app.services.asset_visual_review import review_asset_against_contract, retry_prompt_advice
```

- [ ] **Step 6: Run tests**

Run:

```bash
pytest backend/tests/test_asset_visual_review.py backend/test_asset_multiview_generation.py -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/asset_visual_review.py backend/app/services/asset_generation_service.py backend/app/api/v1/endpoints/assets.py backend/tests/test_asset_visual_review.py backend/test_asset_multiview_generation.py
git commit -m "feat: review generated assets against visual contracts"
```

---

### Task 6: API Client and Frontend Contract Control Panel

**Files:**
- Modify: `frontend/src/lib/api-client.ts`
- Modify: `frontend/src/app/assets/page.tsx`
- Test: `frontend/e2e/assets-consistency-control.spec.ts`

- [ ] **Step 1: Write failing E2E for contract panel**

Create `frontend/e2e/assets-consistency-control.spec.ts`:

```typescript
import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 86400 })).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `asset-contract-user-${Date.now()}`;
  await page.addInitScript(({ token, id }) => {
    localStorage.setItem('auth_token', token);
    localStorage.setItem('user', JSON.stringify({ id, username: id, email: `${id}@example.test` }));
  }, { token: devToken(userId), id: userId });
});

test('asset wizard shows story contract controls and strict-mode review results', async ({ page }) => {
  const novel = { id: 'novel-1', title: '雨巷旧邮局' };
  const entity = { id: 'scene-1', name: '旧邮局', entity_type: 'scene', description: '1980年代雨夜旧邮局' };
  const generatedAsset = {
    id: 'asset-layout',
    category: 'scene',
    asset_type: 'image',
    name: '旧邮局 · 空间布局',
    url: '/static/dev/old-post-office-layout.png',
    thumbnail_url: '/static/dev/old-post-office-layout.png',
    novel_id: novel.id,
    entity_id: entity.id,
    entity_type: 'scene',
    generation_params: {
      source: 'entity_multiview',
      view_key: 'layout',
      view_label: '空间布局',
      consistency_mode: 'strict',
      visual_contract: {
        id: 'contract-old-post-office',
        entity_type: 'scene',
        name: '旧邮局',
        continuity_axes: {
          era: '1980年代小城',
          weather: '雨夜',
          lighting_direction: '门外冷蓝雨光，室内右上方暖黄灯',
          color_palette: '灰蓝冷雨色 + 暖黄室内灯',
        },
        spatial_layout: { fixed_elements: ['左侧正门', '右侧木柜台', '后墙绿色分拣信箱'] },
      },
      visual_consistency: { score: 88, status: 'needs_review', issues: ['lighting_direction'] },
      retry_prompt_advice: '必须保持光源方向：门外冷蓝雨光，室内右上方暖黄灯',
    },
  };
  let generatePayload: any = null;

  await page.route('**/api/v1/novels**', async (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([novel]) }));
  await page.route('**/api/v1/story-bibles/entities**', async (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([entity]) }));
  await page.route('**/api/v1/assets/categories', async (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([{ id: 'scene', name: 'scene', name_cn: '场景' }]) }));
  await page.route('**/api/v1/projects**', async (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) }));
  await page.route('**/api/v1/chapters/**', async (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) }));
  await page.route('**/api/v1/scripts**', async (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) }));
  await page.route('**/api/v1/assets/view-presets', async (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      presets: [{
        entity_type: 'scene',
        category: 'scene',
        title: '场景四视图',
        views: [
          { key: 'establishing', label: '全景定场', aspect_ratio: '16:9' },
          { key: 'layout', label: '空间布局', aspect_ratio: '16:9' },
          { key: 'detail', label: '关键细节', aspect_ratio: '16:9' },
          { key: 'lighting', label: '光影氛围', aspect_ratio: '16:9' },
        ],
      }],
    }),
  }));
  await page.route('**/api/v1/assets/style-templates', async (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ templates: [{ style: 'cinematic-2d', label: '2D电影' }] }) }));
  await page.route('**/api/v1/assets?**', async (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([generatedAsset]) }));
  await page.route('**/api/v1/assets/generate-entity-views', async (route) => {
    generatePayload = route.request().postDataJSON();
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ entity_type: 'scene', entity_id: entity.id, assets: { layout: generatedAsset }, total: 1, failures: [] }) });
  });

  await page.goto('/assets?novel_id=novel-1&entity_type=scene&entity_id=scene-1&view_key=layout&action=generate-missing&source=production-card');
  await expect(page.getByText('视觉契约')).toBeVisible();
  await expect(page.getByText('1980年代小城')).toBeVisible();
  await expect(page.getByText('门外冷蓝雨光，室内右上方暖黄灯')).toBeVisible();
  await expect(page.getByText('一致性 88')).toBeVisible();
  await expect(page.getByText('必须保持光源方向')).toBeVisible();

  await page.getByLabel('一致性模式').selectOption('strict');
  await page.getByRole('button', { name: '生成空间布局缺失视图' }).click();

  expect(generatePayload).toMatchObject({
    entity_id: 'scene-1',
    novel_id: 'novel-1',
    view_keys: ['layout'],
    style: 'cinematic-2d',
    consistency_mode: 'strict',
  });
});
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
cd frontend
npx playwright test e2e/assets-consistency-control.spec.ts --project=chromium --workers=1
```

Expected: fail because the asset wizard lacks a visual contract panel and `consistency_mode` is not sent.

- [ ] **Step 3: Extend API client**

Modify `frontend/src/lib/api-client.ts`:

```typescript
async generateEntityViewAssets(data: {
  entity_id: string;
  novel_id?: string;
  chapter_id?: string;
  script_id?: string;
  view_keys?: string[];
  style?: string;
  model_config_id?: string;
  consistency_mode?: 'draft' | 'standard' | 'strict';
  force_contract_refresh?: boolean;
  anchor_view_key?: string;
}) {
  return this.request<any>('/assets/generate-entity-views', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

async reviewAssetContract(assetId: string) {
  return this.request<any>(`/assets/${assetId}/review-contract`, {
    method: 'POST',
  });
}
```

- [ ] **Step 4: Add frontend state**

In `frontend/src/app/assets/page.tsx`, add state near existing generation state:

```typescript
const [selectedConsistencyMode, setSelectedConsistencyMode] = useState<'draft' | 'standard' | 'strict'>('standard');
```

Update `generateMissingViews` request:

```typescript
const result = await apiClient.generateEntityViewAssets({
  entity_id: selectedEntityId,
  novel_id: selectedNovelId || undefined,
  chapter_id: selectedChapterId || undefined,
  script_id: selectedScriptId || undefined,
  view_keys: keys,
  style: selectedGenerationStyle,
  consistency_mode: selectedConsistencyMode,
});
```

- [ ] **Step 5: Add control UI**

In the AI asset wizard controls, add:

```tsx
<label className="space-y-1 text-sm text-white/70" htmlFor="asset-wizard-consistency-mode">
  <span>一致性模式</span>
  <Select
    id="asset-wizard-consistency-mode"
    value={selectedConsistencyMode}
    onChange={(event) => setSelectedConsistencyMode(event.target.value as 'draft' | 'standard' | 'strict')}
    options={[
      { value: 'standard', label: '标准：故事契约 + 锚点参考' },
      { value: 'strict', label: '严格：必须支持参考图' },
      { value: 'draft', label: '草稿：快速生成后复审' },
    ]}
  />
</label>
```

- [ ] **Step 6: Add visual contract panel**

Derive current contract from selected entity assets:

```typescript
const selectedVisualContract = useMemo(() => {
  const current = Object.values(viewAssetsByKey).find((asset) => asset.generation_params?.visual_contract);
  return current?.generation_params?.visual_contract || null;
}, [viewAssetsByKey]);
```

Render inside `asset-wizard`:

```tsx
{selectedVisualContract && (
  <div data-testid="asset-visual-contract-panel" className="rounded-lg border border-cyan-300/25 bg-cyan-400/10 p-3 text-sm text-cyan-50">
    <div className="font-medium text-white">视觉契约</div>
    <div className="mt-2 grid gap-1 text-xs leading-5 text-cyan-100/80">
      {selectedVisualContract.continuity_axes?.era && <div>时代：{selectedVisualContract.continuity_axes.era}</div>}
      {selectedVisualContract.continuity_axes?.weather && <div>天气：{selectedVisualContract.continuity_axes.weather}</div>}
      {selectedVisualContract.continuity_axes?.lighting_direction && <div>光源：{selectedVisualContract.continuity_axes.lighting_direction}</div>}
      {selectedVisualContract.continuity_axes?.color_palette && <div>色彩：{selectedVisualContract.continuity_axes.color_palette}</div>}
      {selectedVisualContract.spatial_layout?.fixed_elements?.length ? <div>固定空间：{selectedVisualContract.spatial_layout.fixed_elements.join('、')}</div> : null}
    </div>
  </div>
)}
```

- [ ] **Step 7: Render review records on view cards**

Inside each view card, after existing badges:

```tsx
const review = matchedAsset?.generation_params?.visual_consistency;
const retryAdvice = matchedAsset?.generation_params?.retry_prompt_advice;
```

Render:

```tsx
{review?.score !== undefined && (
  <Badge variant="outline" className={review.score >= 90 ? 'border-emerald-400/40 text-emerald-200' : 'border-amber-400/40 text-amber-100'}>
    一致性 {review.score}
  </Badge>
)}
{retryAdvice && (
  <div className="rounded-md border border-amber-400/20 bg-amber-500/10 p-2 text-xs leading-5 text-amber-100">
    {retryAdvice}
  </div>
)}
```

- [ ] **Step 8: Run E2E and typecheck**

Run:

```bash
cd frontend
npm run typecheck
npx playwright test e2e/assets-consistency-control.spec.ts --project=chromium --workers=1
```

Expected: typecheck passes and E2E passes.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/lib/api-client.ts frontend/src/app/assets/page.tsx frontend/e2e/assets-consistency-control.spec.ts
git commit -m "feat: add asset visual contract controls"
```

---

### Task 7: Feedback-Driven Targeted Retry

**Files:**
- Modify: `backend/app/api/v1/endpoints/assets.py`
- Modify: `backend/app/services/asset_generation_service.py`
- Modify: `frontend/src/app/assets/page.tsx`
- Modify: `frontend/src/lib/api-client.ts`
- Test: `backend/test_asset_multiview_generation.py`
- Test: `frontend/e2e/assets-consistency-control.spec.ts`

- [ ] **Step 1: Add backend failing test for retry feedback**

Append to `backend/test_asset_multiview_generation.py`:

```python
def test_regenerate_view_carries_consistency_feedback_into_prompt(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = f"retry-feedback-user-{uuid4()}"
    novel_id = _create_novel(client, user_id)
    scene_id = _create_entity(client, user_id, novel_id, "scene", "旧邮局")
    asset = _create_asset(
        client,
        user_id,
        name="old-post-office-layout",
        category="scene",
        novel_id=novel_id,
        entity_id=scene_id,
        entity_type="scene",
        generation_params={
            "source": "entity_multiview",
            "view_key": "layout",
            "view_label": "空间布局",
            "style": "cinematic-2d",
            "visual_contract": {
                "id": "contract-old-post-office",
                "entity_type": "scene",
                "continuity_axes": {"lighting_direction": "门外冷蓝雨光，室内右上方暖黄灯"},
                "spatial_layout": {"fixed_elements": ["右侧木柜台", "后墙绿色分拣信箱"]},
            },
            "visual_consistency": {"score": 72, "issues": ["lighting_direction", "spatial_layout"]},
            "retry_prompt_advice": "必须保持光源方向：门外冷蓝雨光，室内右上方暖黄灯；必须保持空间结构：右侧木柜台、后墙绿色分拣信箱",
        },
    )
    captured_prompts: list[str] = []

    async def _fake_image_config(*args, **kwargs):
        return "key", "volcano", "test-image-model", None

    class _FakeImageService:
        async def generate_image(self, **kwargs):
            captured_prompts.append(kwargs["prompt"])
            return {"data": [{"url": "data:image/png;base64," + _tiny_png_base64()}]}

    monkeypatch.setattr("app.services.asset_generation_service.get_user_image_model_config", _fake_image_config, raising=False)
    monkeypatch.setattr("app.services.asset_generation_service.create_image_generation_service", lambda *args, **kwargs: _FakeImageService(), raising=False)

    response = client.post(
        f"/api/v1/assets/{asset['id']}/regenerate",
        json={"style": "cinematic-2d"},
        headers=auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    assert any("必须保持光源方向" in prompt for prompt in captured_prompts)
    assert any("右侧木柜台" in prompt for prompt in captured_prompts)
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
pytest backend/test_asset_multiview_generation.py::test_regenerate_view_carries_consistency_feedback_into_prompt -q
```

Expected: fail because retry advice is not appended to regeneration prompt.

- [ ] **Step 3: Pass retry advice through service**

In `AssetGenerationService.generate_entity_view_assets`, add optional parameter:

```python
retry_prompt_advice: Optional[str] = None
```

When building `prompt`, append:

```python
if retry_prompt_advice:
    prompt = f"{prompt}\n一致性复修要求：{retry_prompt_advice}"
```

In the regenerate endpoint, read from original asset params:

```python
retry_prompt_advice = params.get("retry_prompt_advice")
```

Pass to service:

```python
retry_prompt_advice=retry_prompt_advice,
```

- [ ] **Step 4: Add frontend retry action**

In `frontend/src/lib/api-client.ts`, existing `regenerateAsset` can be reused. No new method is required.

In `frontend/src/app/assets/page.tsx`, next to retry advice, render:

```tsx
{retryAdvice && matchedAsset && (
  <Button
    type="button"
    size="sm"
    variant="outline"
    className="border-amber-300/40 text-amber-100"
    disabled={regeneratingAssetId === matchedAsset.id}
    onClick={() => regenerateAsset(matchedAsset)}
  >
    {regeneratingAssetId === matchedAsset.id ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <RefreshCw className="mr-1 h-3 w-3" />}
    按问题重生成
  </Button>
)}
```

- [ ] **Step 5: Extend frontend E2E**

In `frontend/e2e/assets-consistency-control.spec.ts`, add to the existing test:

```typescript
await expect(page.getByRole('button', { name: '按问题重生成' })).toBeVisible();
```

Mock `POST /api/v1/assets/asset-layout/regenerate` and assert it is called after clicking.

- [ ] **Step 6: Run tests**

Run:

```bash
pytest backend/test_asset_multiview_generation.py::test_regenerate_view_carries_consistency_feedback_into_prompt -q
cd frontend
npm run typecheck
npx playwright test e2e/assets-consistency-control.spec.ts --project=chromium --workers=1
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/asset_generation_service.py backend/app/api/v1/endpoints/assets.py backend/test_asset_multiview_generation.py frontend/src/app/assets/page.tsx frontend/e2e/assets-consistency-control.spec.ts
git commit -m "feat: retry asset views with consistency feedback"
```

---

### Task 8: Full Regression and Production Readiness Gate

**Files:**
- Modify only if tests reveal defects:
  - `backend/app/services/asset_generation_service.py`
  - `backend/app/api/v1/endpoints/assets.py`
  - `frontend/src/app/assets/page.tsx`

- [ ] **Step 1: Run backend asset suites**

Run:

```bash
pytest backend/test_asset_multiview_generation.py backend/tests/test_asset_visual_contract.py backend/tests/test_asset_model_capabilities.py backend/tests/test_asset_visual_review.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run related backend production suites**

Run:

```bash
pytest backend/tests/test_production_cards.py backend/test_workflow_routes.py::test_studio_snapshot_exposes_series_studio_contract -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Run frontend typecheck**

Run:

```bash
cd frontend
npm run typecheck
```

Expected: `tsc --noEmit` exits with code 0.

- [ ] **Step 4: Run focused frontend E2E**

Run:

```bash
cd frontend
npx playwright test e2e/assets-consistency-control.spec.ts e2e/assets-low-barrier-management.spec.ts e2e/studio-production-cards.spec.ts --project=chromium --workers=1
```

Expected: all selected tests pass.

- [ ] **Step 5: Run rendered browser QA**

Use the Browser plugin or Playwright fallback to verify:

- `/assets?novel_id=<novel>&entity_type=scene&entity_id=<old-post-office>&view_key=layout&action=generate-missing&source=production-card`
- Page is not blank.
- No Next.js/framework overlay.
- Console has no relevant errors.
- Visual contract panel shows story-linked axes.
- Strict mode selector exists.
- Targeted retry button appears when review score is below 90.

Expected evidence: screenshot plus console error count.

- [ ] **Step 6: Check whitespace and staged scope**

Run:

```bash
git diff --check
git status --short --untracked-files=no
```

Expected:

- `git diff --check` exits with code 0.
- Only intended files are modified.
- `frontend/tsconfig.tsbuildinfo`, if modified by typecheck, remains unstaged unless intentionally requested.

- [ ] **Step 7: Final commit**

```bash
git add backend/app/services/story_prompt_context.py backend/app/services/asset_visual_contract.py backend/app/services/asset_model_capabilities.py backend/app/services/asset_visual_review.py backend/app/services/image_prompt_policy.py backend/app/services/asset_generation_service.py backend/app/api/v1/endpoints/assets.py backend/tests/test_story_prompt_context_assets.py backend/tests/test_asset_visual_contract.py backend/tests/test_asset_model_capabilities.py backend/tests/test_asset_visual_review.py backend/test_asset_multiview_generation.py frontend/src/lib/api-client.ts frontend/src/app/assets/page.tsx frontend/e2e/assets-consistency-control.spec.ts
git commit -m "feat: enforce story-linked asset consistency"
```

---

## Acceptance Criteria

- Scene assets generated for the same entity persist a story-linked contract containing story scope, continuity axes, and spatial layout.
- Standard and strict asset generation reject requests that cannot resolve to a `novel_id`.
- Requests that provide mismatched `novel_id/chapter_id/script_id/entity_id` fail before any image provider call.
- If a `script_id` is provided or inferred, script title/content summary contributes to the contract source and appears in `context_sources`.
- Frontend asset generation requests carry the current novel/chapter/script scope from production-card deep links and asset filters.
- The old post office case can represent era, building structure, weather, light direction, color palette, fixed elements, and action zones in the contract.
- Scene non-anchor views reference the anchor view, defaulting to `establishing`.
- Character non-anchor views reference `front`.
- Prop non-anchor views reference `main`.
- Strict mode blocks when a selected model cannot support the required reference strategy.
- Standard mode proceeds with a visible warning when only text contract generation is available.
- Every generated asset persists `visual_contract`, `consistency_mode`, `model_strategy`, `visual_consistency`, and retry advice when needed.
- Frontend asset management shows the contract, mode selector, review score, issue advice, and targeted retry.
- Existing low-barrier asset wizard and production-card completion flows continue to work.

## Risk Controls

- Store first-version contracts in `Asset.generation_params` and existing entity/story metadata; avoid a new persistence table in the first implementation batch.
- Keep strict mode opt-in so current users are not blocked by providers that lack reference-image support.
- Use deterministic unit tests for contract extraction and review logic; do not require real AI provider calls in CI.
- Preserve existing prompt skill hooks so users can still customize provider-specific wording.
- Keep frontend controls compact: default `standard` mode, advanced details visible but not mandatory.

## Follow-Up Work After This Plan

- Replace prompt-coverage review with a true multimodal vision evaluator when a configured vision model is available.
- Add optional structure references for scenes: line sketch, depth map, or layout mask.
- Add a contract version history UI for comparing old and new scene/character/prop contracts.
- Add analytics by model/provider: consistency pass rate, average retries, common issue types.
