# 连续动漫制作平台 · V2 实施方案（可直接开发落地版）

日期：2026-07-02
性质：本文档是 `docs/continuous-anime-production-optimization.md`（V1，P0-P2 已落地）的续篇与细化实施版。每个阶段包含：目标、文件级改动清单、API/数据契约、TDD 测试用例、验收命令。所有文件路径、函数名、字段名均已对照当前代码核实。

约定：
- 所有后端验证命令在 `backend/` 目录下执行，前缀 `DEV_MODE=true PYTHONPATH=.`
- 所有前端验证命令在 `frontend/` 目录下执行
- 每个阶段按 TDD 执行：先写红灯测试 → 实现 → 转绿 → 组合回归 → 独立提交
- 不做数据库迁移是默认约束；确需新列时优先复用 `extra_data` / `metadata_` / `attributes` JSON 字段

---

## 0. 当前基线（已核实的代码事实）

| 事实 | 位置 |
| --- | --- |
| 生产策略仅有"文案提示"，无真实模型路由 | `backend/app/api/v1/endpoints/workflow.py:572` `_production_strategy_metadata()` 只产出 `recommended_model_hint` 字符串 |
| 批量生成不传 `model_config_id` 时回退到 `VIDEO_MODEL_ID = "Doubao-Seedance-1.0-pro-fast"` | `backend/app/api/v1/endpoints/video.py:51`，`workflow.py:1763` 调 `_resolve_video_model_config(db, user_id, None, request.model_config_id)` |
| 视频模型解析器 | `video.py:191` `_resolve_video_model_config()`：config_id → provider/api_model/endpoint/api_key/test_status；无 config 时按 model_key 查目录 |
| 供应商只收 1 张参考图 | Phase 273 已固化 `provider_reference_image_limit=1`；多视图只进 prompt 和 metadata |
| 终稿门禁已存在 | `workflow.py:483` `_final_quality_lock_snapshots()`：缺资产锁/声线锁返回 422 `final_quality_locks_missing` |
| 声线快照 | `workflow.py:449` `_voice_lock_snapshot_for_workflow_shot()` → Story Bible `character_rules.voice` |
| Production Bible 摘要 | `backend/app/services/production_bible.py`：`build_production_bible_summary()` / `build_production_snapshot()` |
| 资产锁服务 | `backend/app/services/asset_lock_service.py`：`AssetLockService.lock_shot_assets/get_locked_asset_prompts/unlock_shot_assets` |
| 多视图预设 | `backend/app/services/asset_generation_service.py:533` `ASSET_VIEW_PRESETS`（character 三视图/scene 四视图/prop 多视图，含 `view_key`） |
| 模型注册表 | `backend/app/core/model_registry.py`：`volcano.seedance.2_0`（api_model_id=`doubao-seedance-2-0-260128`）、`volcano.seedance.2_0_fast`，`limits` 为普通 dict，可加字段 |
| Seedance 2.0 目录/端点映射已就绪 | `backend/app/core/volcano_config.py:36-44`、`llm_config.py:596/619` 种子、`init_llm_config.py:138/156` |
| 前端策略文案 | `frontend/src/lib/production-strategy.ts`：`PRODUCTION_STRATEGY_COPY`（draft_fast/final_quality/low_cost/separate_video_tts/direct_av_first） |
| 一键草片链路 | `frontend/src/lib/episode-preview-production.ts` `runEpisodePreviewProduction()`：已支持 `productionStrategy/audioMode/waiting 状态` |
| 路由前缀 | `/api/v1/assets`、`/api/v1/story-bibles`、`/api/v1/production-control`、`/api/v1/studio` |
| 测试工具 | `backend/test_workflow_routes.py`：`_insert_model_config()`（可插入带 key 的模型配置）、`_set_shot_extra_data()`、`_auth_headers()`、`_create_novel/chapter/script/storyboard/shot` |
| 现有策略追踪测试 | `test_workflow_routes.py:2829` `test_workflow_media_batch_tracks_final_quality_production_strategy`（断言 hint 文案，S1 需同步更新） |

---

## S1：策略真实路由 + 定稿卡聚合视图（1-2 周）

### S1-A 生产策略 → 模型真实路由

#### 目标
`draft_fast` 未显式选模型时真实解析到 Seedance-2.0-fast 已保存配置；`final_quality` 解析到 Seedance-2.0。路由优先级：**用户显式 `model_config_id` > 策略默认模型的用户已验证配置 > 现有回退（VIDEO_MODEL_ID）**。找不到策略默认模型的可用配置时不报错，回退现有行为并在任务里标记 `strategy_routing: "fallback"`。

#### 文件级改动

1. **新增 `backend/app/services/production_strategy_routing.py`**

```python
"""生产策略到模型配置的真实路由。"""
STRATEGY_VIDEO_MODEL_PREFERENCE: dict[str, list[str]] = {
    # 按 LLMModel.model_id（API model id）优先级排列
    "draft_fast":   ["doubao-seedance-2-0-fast-260128", "doubao-seedance-2.0-fast", "Doubao-Seedance-1.0-pro-fast"],
    "final_quality":["doubao-seedance-2-0-260128", "doubao-seedance-2.0", "doubao-seedance-2-0-fast-260128"],
    "low_cost":     ["doubao-seedance-2-0-fast-260128", "Doubao-Seedance-1.0-pro-fast"],
    # separate_video_tts / direct_av_first 不改模型选择，仅决定生成方式
}

async def resolve_strategy_video_config_id(
    db, user_id: str, production_strategy: str | None, explicit_config_id: str | None,
) -> dict:
    """返回 {"model_config_id": str|None, "routing": "explicit"|"strategy"|"fallback",
             "strategy_model_candidates": [...], "matched_api_model_id": str|None}
    - explicit_config_id 存在 → routing=explicit，原样返回
    - 否则按 STRATEGY_VIDEO_MODEL_PREFERENCE 查该用户 is_active 且 test_status='success'
      的 LLMConfig（join LLMModel on model_id in 候选，含 volcano 和 volcano_agent_plan 两个 provider），
      按候选顺序取第一个 → routing=strategy
    - 都没有 → routing=fallback, model_config_id=None（走现有 VIDEO_MODEL_ID 回退）
    """
```

注意：查询需同时匹配 `LLMModel.model_id`（普通火山 `doubao-seedance-2-0-fast-260128`）和 Agent Plan 的 `doubao-seedance-2.0-fast`（`volcano_agent_plan_config.py:265` 已核实两种 ID 格式并存），所以候选表里两种写法都列。

2. **改 `backend/app/api/v1/endpoints/workflow.py` `generate_workflow_media_batch()`**

在 `1763` 行 `_resolve_video_model_config` 之前插入路由：

```python
routing = await resolve_strategy_video_config_id(
    db, user_id, request.production_strategy, request.model_config_id)
effective_video_config_id = routing["model_config_id"] or request.model_config_id
selected_video_model = await _resolve_video_model_config(db, user_id, None, effective_video_config_id)
```

后续所有引用 `request.model_config_id` 的位置（preflight `1821`、extra_data `1901`、metadata `2127`）改为 `effective_video_config_id`，并在每个 video job `extra_data` 加：

```python
extra_data["strategy_routing"] = routing["routing"]          # explicit|strategy|fallback
extra_data["strategy_matched_api_model_id"] = routing["matched_api_model_id"]
```

`direct_av_first` 分支（`2156` 行 `_resolve_saved_video_model`）同样先过路由。

3. **改 `_production_strategy_metadata()`（workflow.py:572）**：保持现有字段不变，新增 `"routing_enabled": True` 标记，前端据此把 hint 文案从"建议"改为"将自动使用"。

4. **`studio_snapshot.py:61` 同步**：hint 文案不动，snapshot 增加 `strategy_routing_enabled: true`。

5. **前端 `frontend/src/lib/production-strategy.ts`**：`draft_fast.modelHint` 改为"未选择模型时将自动使用 Seedance 快速档（如已配置并验证）"；`final_quality.modelHint` 同理。不改结构。

#### TDD 测试（新增 `backend/tests/test_production_strategy_routing.py`）

| # | 用例 | 断言 |
| --- | --- | --- |
| 1 | `test_draft_fast_routes_to_seedance_fast_config`：用 `_insert_model_config(api_model_id="doubao-seedance-2-0-fast-260128", model_type="video")` 插入已验证配置；monkeypatch `_create_ark_client` 捕获 kwargs；POST media-batch `{strategy:"separate_video_tts", production_strategy:"draft_fast"}` **不传 model_config_id** | 捕获的 `create_kwargs["model"]` 为 fast 端点；VideoJob `extra_data.strategy_routing == "strategy"`、`model_config_id` 等于插入的配置 |
| 2 | `test_final_quality_routes_to_seedance_20`：同上插两个配置（2.0 与 fast），production_strategy=final_quality（镜头需先 `_set_shot_extra_data` 补资产锁+Story Bible 声线以过终稿门禁，参照既有 `test_workflow_media_batch_tracks_final_quality_production_strategy` 的准备段） | 实际提交模型为 `doubao-seedance-2-0-260128`；`strategy_routing=="strategy"` |
| 3 | `test_explicit_config_overrides_strategy`：插入 fast 配置 + 一个自定义视频配置，请求带 `model_config_id=自定义` 且 `production_strategy="draft_fast"` | 使用自定义配置；`strategy_routing=="explicit"` |
| 4 | `test_no_strategy_config_falls_back`：不插任何 Seedance 2.0 配置，DEV_MODE，draft_fast | 请求成功（DEV 占位）；`strategy_routing=="fallback"` |
| 5 | 更新既有 `test_workflow_media_batch_tracks_final_quality_production_strategy`（2829 行）：metadata 断言追加 `routing_enabled` | 原断言保持通过 |

#### 验收命令

```bash
cd backend && DEV_MODE=true PYTHONPATH=. pytest -q tests/test_production_strategy_routing.py test_workflow_routes.py
cd frontend && npm run typecheck && npm run build
```

---

### S1-B 定稿卡聚合视图（Character/Scene/Prop Cards）

#### 目标
把散在 Character、StoryEntity、Asset（多视图+锁）、StoryBible（声线+规则+状态机）四处的信息聚合为单实体"定稿卡"只读视图 + 完整度评分。**纯聚合，不迁移表，不新增写路径**（编辑仍跳转各专业页，由卡片带深链）。

#### API 契约（新增 `backend/app/api/v1/endpoints/production_cards.py`，挂 `/api/v1/production-cards`）

```
GET /api/v1/production-cards/novel/{novel_id}
  → { "novel_id", "cards": [ProductionCard], "summary": {"ready": n, "incomplete": n} }

GET /api/v1/production-cards/entity/{entity_id}
  → ProductionCard

ProductionCard = {
  "entity_id": str, "entity_type": "character"|"scene"|"prop",
  "name": str, "novel_id": str,
  "visual": {                                  # 来源: Asset (entity_id 匹配 + view_key)
    "views": [{"view_key","view_label","asset_id","url","is_locked","is_final","version"}],
    "required_views": [...],                   # 来源: ASSET_VIEW_PRESETS[entity_type]
    "missing_views": [...],
    "locked_count": int
  },
  "voice": {                                   # character 独有；来源: StoryBible.character_rules
    "voice": str|None, "voice_speed": float|None,
    "story_bible_id": str|None, "locked": bool
  },
  "profile": {                                 # 来源: StoryEntity.attributes + Character
    "description","visual_dna","personality","relationships","forbidden_changes"
  },
  "state": {...},                              # 来源: StoryBible.extra_data.state_machine 对应实体切片
  "usage": {                                   # 来源: Shot.extra_data.entity_refs 反查（限最近50）
    "shot_count": int, "last_used_at": str|None
  },
  "readiness": {
    "score": 0-100,
    "final_ready": bool,                       # character: 三视图锁齐+有声线; scene: 全景锁; prop: 主视图锁
    "gaps": [{"code","message","fix_url"}]      # fix_url 深链: /assets?novel_id=..&entity_type=..&entity_id=..
  }
}
```

#### 实现要点

- 新增 `backend/app/services/production_card_service.py`：复用 `production_bible.py` 的 `_load_entities/_load_assets/_asset_matches_entity`（已核实存在）与 `asset_generation_service._view_key()`；声线读取复用 `voice_service.get_character_voice_from_story_bible`
- `final_ready` 判定与 `_final_quality_lock_snapshots()` 语义对齐：这样"卡片显示 ready"与"终稿门禁放行"永远一致。**做法：把 workflow.py 中的判定抽为共享函数 `evaluate_entity_final_readiness()` 放进 card service，workflow 门禁改为调用它**（行为不变，仅去重）
- 路由注册：`backend/app/api/v1/router.py` 加 `include_router(production_cards.router, prefix="/production-cards", tags=["定稿卡"])`

#### 前端（Studio 定稿间）

- 新增 `frontend/src/app/studio/cards/page.tsx`（或 Studio 内 tab）：按小说加载卡片列表，三列（角色/场景/道具），卡片显示：首图、完整度环、缺口列表（每条带"去补齐"深链——复用现有 `/assets?novel_id=&entity_type=&entity_id=` 参数协议，已核实资产页支持）
- `frontend/src/lib/api-client.ts` 加 `getProductionCards(novelId)` / `getProductionCard(entityId)`
- `/studio` 首页 P0 看板的"资产/声音锁"卡改为读卡片 summary（数据源统一）

#### TDD 测试

后端（新增 `backend/tests/test_production_cards.py`）：
1. `test_character_card_aggregates_views_voice_and_readiness`：造小说→StoryEntity(character)→2 个视图资产(front 锁定/side 未锁)→StoryBible 带 voice → GET 卡片：`missing_views==["back"]`、`voice.locked==true`、`final_ready==false`、gaps 含 `view_missing:back` 和 `view_unlocked:side`
2. `test_card_final_ready_matches_workflow_gate`：构造"卡片 final_ready==true"的实体与镜头 → final_quality media-batch 必须放行；反之必须 422（**一致性回归，防止两处判定分叉**）
3. `test_scene_and_prop_cards_use_type_specific_required_views`：scene 要求 `ASSET_VIEW_PRESETS["scene"]` 的视图集合；prop 要求主视图
4. `test_novel_cards_summary_counts`

前端（新增 `frontend/e2e/studio-production-cards.spec.ts`，mock API 模式，参照 `onboarding-simplification.spec.ts` 的 route.fulfill 写法）：
5. 卡片列表显示完整度、缺口、"去补齐"链接 href 含 `entity_id`
6. final_ready 卡片显示"终稿就绪"徽标

#### 验收命令

```bash
cd backend && DEV_MODE=true PYTHONPATH=. pytest -q tests/test_production_cards.py test_workflow_routes.py tests/test_p0_consistency_pipeline.py
cd frontend && npm run typecheck && npm run build && npx playwright test e2e/studio-production-cards.spec.ts --project=chromium
```

#### S1 提交切片

1. `feat: route production strategy to real video model configs`
2. `feat: add production card aggregation api`
3. `feat: add studio production cards page`

---

## S2：Seedance 2.0 多模态参考包（2-3 周，外部依赖：火山方舟 Seedance 2.0 API 正式开放）

### 目标
终稿镜头把"角色多视图 + 场景图 + 道具图 + 上一镜头成片"作为多模态参考真实提交给 Seedance 2.0（9 图 + 3 视频 + 3 音频 + @引用）；单参考图模型完全向后兼容。

### S2-A 模型能力矩阵扩展

**改 `backend/app/core/model_registry.py`**：给视频模型 `limits` 增加参考能力字段（`limits` 是普通 dict，无 schema 约束，直接加）：

```python
# volcano.seedance.2_0 / volcano.seedance.2_0_fast 的 limits 增加：
"limits": {
    "durations": [4, 5, 8, 10, 15], "resolutions": ["480p", "720p"],
    "reference_images": 9, "reference_videos": 3, "reference_audios": 3,
    "supports_at_reference": True, "native_audio": True,
},
# volcano.seedance.1_0_pro_fast / 1_5_pro 增加：
"limits": {..., "reference_images": 1, "reference_videos": 0, "reference_audios": 0,
    "supports_at_reference": False, "native_audio": False},
```

新增读取 helper（同文件）：

```python
def get_model_reference_limits(model_id_or_api_id: str) -> dict:
    """返回 {"images": int, "videos": int, "audios": int, "at_reference": bool, "native_audio": bool}
    未登记的模型返回保守默认 {"images": 1, "videos": 0, "audios": 0, ...}"""
```

### S2-B 参考包构建服务

**新增 `backend/app/services/reference_package_builder.py`**：

```python
async def build_reference_package(
    db, user_id: str, *,
    shot,                          # Shot ORM
    lineage: dict,                 # 已有 _resolve_video_lineage 输出
    model_limits: dict,            # get_model_reference_limits 输出
    resolve_public_url,            # 复用 media_delivery.resolve_provider_image_delivery
) -> dict:
    """
    返回 {
      "images": [{"url","role_tag","entity_type","entity_id","view_key","at_index"}],  # ≤limits.images
      "videos": [{"url","role_tag","source_shot_id","at_index"}],                       # ≤limits.videos
      "audios": [],                                                                     # S4 再填
      "at_reference_text": "@图1为主角孙剑正面形象基准；@图2为其侧面…" | None,
      "dropped": [{"reason","entity_name","view_key"}],   # 超上限被裁剪的项，进任务 metadata
    }
    装配优先级（在 limits.images 内取满为止）：
      1. 主角（shot.character_refs[0] 匹配实体）front → side → back 锁定视图
      2. 场景锁定全景视图（entity_refs 中 scene）
      3. 关键道具主视图（entity_refs 中 prop，最多2个）
      4. 其余出镜角色 front 视图各1张
      5. 风格锚点：小说封面或 style 资产（如有）
    videos 装配：同一分镜内上一镜头的成功 video_url（衔接参考），仅当 limits.videos>0
    所有 URL 必须过 resolve_public_url；非公网项跳过并记入 dropped
    limits.images<=1 时：只返回现状的单参考图（复用 package["reference_image"] 语义），
      at_reference_text=None —— 保证旧模型行为完全不变
    """
```

数据来源均已存在：多视图资产按 `Asset.entity_id + generation_params.view_key + is_locked` 查询（S1-B 的 card service 可直接复用其查询函数）。

### S2-C 生成合约升级（火山 SDK 提交层）

**改 `backend/app/api/v1/endpoints/video.py` 与 `workflow.py` 的 SDK 提交段**（workflow.py:1920-1949 已核实当前 content 结构）：

```python
# 当前（单图）：
content = [{"type":"image_url","image_url":{"url":provider_image_url}}, {"type":"text","text":...}]

# 升级后（能力矩阵驱动）：
ref_pkg = prepared["reference_package"]
if model_limits["images"] > 1 and ref_pkg["images"]:
    content = []
    for img in ref_pkg["images"]:
        content.append({"type": "image_url", "image_url": {"url": img["url"]},
                        "role": "reference_image"})          # role 字段以火山正式文档为准，见 S2-E
    for vid in ref_pkg["videos"]:
        content.append({"type": "video_url", "video_url": {"url": vid["url"]},
                        "role": "reference_video"})
    prompt_text = f'{ref_pkg["at_reference_text"]}\n{final_video_prompt} --duration ...'
    content.append({"type": "text", "text": prompt_text})
else:
    # 现有单图路径，零改动
```

任务 metadata 落库（extra_data）：

```python
extra_data["reference_package"] = {
    "image_count": len(ref_pkg["images"]), "video_count": len(ref_pkg["videos"]),
    "items": [...],                        # 完整清单（url+entity+view_key）
    "dropped": ref_pkg["dropped"],
    "mode": "multimodal" | "single_image", # 实际提交模式
}
# 替换掉 Phase 273 的 provider_reference_image_limit=1 常量：
extra_data["provider_reference_image_limit"] = model_limits["images"]
```

### S2-D 终稿+门禁

`_final_quality_lock_snapshots()` 扩展：final_quality 且模型 `limits.images>1` 时，主角必须有 ≥2 个锁定视图能进参考包，否则 422 detail 增加 `{"code":"reference_package_insufficient","entity_name",...}`。

### S2-E 外部契约核对清单（开发前必做，半天）

火山方舟 Seedance 2.0 API 正式文档核对项（当前基于第三方文档，正式开放后逐项确认）：
- [ ] `content[]` 中多图/视频/音频的确切字段名与 `role` 取值（`reference_image` vs `role: first_frame/last_frame`）
- [ ] prompt 内 @引用语法（`@image1` / `@图1`）
- [ ] 请求体 64MB 上限 → 全部走公网 URL（已满足）
- [ ] 计费公式（token × 时长 × 宽 × 高 × 帧率/1024）→ 更新 `budget_estimate` 逻辑
- [ ] Agent Plan `/api/plan/v3` 是否同步支持多参考（若不支持，Agent Plan provider 的 limits 保持 images:1）

当前实现状态（2026-07-03）：
- 多参考提交已集中在 `backend/app/services/video_reference_adapter.py`，`role`、多模态 `content[]` 与 @引用文本均在该适配层收口，正式字段变化时只改一处。
- Seedance 2.0 / 2.0 fast 按能力矩阵允许多图多视频；Seedance 1.x、未知模型和 Agent Plan 通道保持 `images:1` 的单图兼容路径。
- 参考包 metadata 已落到 `VideoJob.extra_data.reference_package`，审阅/历史页面可展示 `image_count`、`video_count` 与 `dropped`。
- 成本 API 已新增 Seedance 2.x 计费 token 明细：`backend/app/services/cost_calculator.py` 按 `时长 × 宽 × 高 × 帧率 / 1024` 估算 `billing_units`，`/api/v1/costs/estimate/video` 可透传可选每百万 token 单价；默认不硬编码供应商价格。
- Agent Plan 通道已用测试锁定为单图兼容路径（`doubao-seedance-2.0-fast` → `images:1`），正式确认支持前不开放多参考。
- 未完成官方核对项仍是 `role` 取值、@引用语法、正式单价和 Agent Plan 多参考支持；在正式文档确认前不把当前适配视为外部契约已稳定。

### TDD 测试（新增 `backend/tests/test_reference_package.py`）

| # | 用例 | 断言 |
| --- | --- | --- |
| 1 | `test_reference_limits_from_registry`：`get_model_reference_limits("doubao-seedance-2-0-260128")` | images==9, at_reference==True；未知模型 images==1 |
| 2 | `test_build_package_prioritizes_protagonist_views`：造 1 主角(3锁定视图)+1 场景(1锁定)+2 道具+1 配角，limits.images=9 | 前3项为主角 front/side/back；package 内每项含 at_index 与 entity_id |
| 3 | `test_build_package_truncates_and_records_dropped`：limits.images=4 | 只留4张，dropped 记录被裁项与原因 |
| 4 | `test_single_image_model_unchanged`：limits.images=1 | 返回单图，at_reference_text 为 None |
| 5 | `test_non_public_urls_skipped`：本地 `/static/` 图且无 CDN 配置 | 项进入 dropped，reason 含"公网" |
| 6 | `test_media_batch_submits_multimodal_content`（放 test_workflow_routes.py）：monkeypatch `_create_ark_client` 捕获 kwargs；插入 Seedance 2.0 配置 + 主角多视图锁定资产 + CDN 配置（复用 `_create_public_storage_config`）；final_quality 批量生成 | `create_kwargs["content"]` 含 ≥3 个 image_url 项 + 1 个 text 项；text 以 @引用文本开头；VideoJob `extra_data.reference_package.mode=="multimodal"` |
| 7 | `test_media_batch_single_image_model_backward_compat`：用 Seedance 1.0 配置跑同样请求 | content 结构与现状完全一致（1图+text）；`mode=="single_image"` |
| 8 | `test_final_quality_blocks_insufficient_reference_package`：主角只有 1 个锁定视图 + Seedance 2.0 | 422 `reference_package_insufficient` |

前端：`/video-generation` 与 `/studio` 任务历史展示"参考包：N图/N视频 + 被裁剪项"（读 `extra_data.reference_package`，复用 `HistoryPreflightEvidence` 组件模式）；新增 e2e 断言历史卡片可见参考包计数。

#### 验收命令

```bash
cd backend && DEV_MODE=true PYTHONPATH=. pytest -q tests/test_reference_package.py test_workflow_routes.py tests/test_p0_consistency_pipeline.py
cd frontend && npm run typecheck && npm run build && npx playwright test e2e/history-preflight-evidence.spec.ts --project=chromium
```

#### S2 提交切片

1. `feat: add model reference capability matrix`
2. `feat: add reference package builder service`
3. `feat: submit multimodal reference package for seedance 2.0`
4. `feat: enforce reference package gate for final quality`

---

## S3：镜头审阅 + 只重生坏镜头（2 周）

### 目标
草片生成后有一个"镜头审阅列表"：每个镜头显示成片、状态、快照证据、失败原因；支持"仅重生选中/失败/某角色镜头"，重生结果自动回填 workflow、manifest、渲染预检，**不重跑整集**。

### 后端

1. **新增 `POST /api/v1/workflow/{workflow_id}/regenerate-shots`**（workflow.py）

```
Request = {
  "shot_ids": [str] | null,
  "filter": "failed" | "all_selected" | null,        # shot_ids 为空时可用 filter=failed
  "character_name": str | null,                       # 只重生某角色出镜镜头（按 character_refs 匹配）
  "production_strategy": str | null,                  # 默认继承 workflow.metadata_.latest_production_strategy
  "model_config_id": str | null,
  "audio_model_config_id": str | null,
  "audio_mode": "model_audio" | "none",
}
Response = {
  "regenerated_shot_ids": [...], "video_job_ids": [...], "tts_job_ids": [...],
  "skipped": [{"shot_id","reason"}],                  # 如：正在生成中、被锁定
  "ready_for_concatenate": bool,
}
```

实现 = 现有 `generate_workflow_media_batch` 的镜头筛选参数化复用（它已支持 `shot_ids`，本接口是其带过滤语义的薄封装 + 旧任务标记）：
- 重生前把该镜头旧 VideoJob/TTSJob `extra_data` 打标 `superseded_by_regeneration: true`（不删除，保留历史）
- 复用 S1 策略路由与 S2 参考包

2. **改 `POST /api/v1/workflow/concatenate/{workflow_id}`**：按 shot 取"最新成功任务"组装 segment（当前已按任务列表组装；需确认取序逻辑为 per-shot 最新，若已是则只补测试）。

3. **镜头审阅数据接口**：`GET /api/v1/workflow/{workflow_id}/shot-review`
返回每镜头：`{shot_id, shot_number, video_url, status, duration, subtitle_text, character_names, evidence:{strategy_routing, reference_package_mode, generation_preflight}, regeneration_count}` —— 全部字段来自现有 Shot/VideoJob extra_data，纯聚合。

### 前端

- `/studio` 本集工作台新增"镜头审阅"区（`frontend/src/app/studio/` 内组件）：镜头卡网格（视频缩略播放 + 状态徽标 + 证据摘要 + 勾选框），底部操作条：`重生选中` / `仅重生失败` / `按角色重生（下拉）`
- 重生进行中的镜头卡显示 waiting 态（复用 episode-preview 的 waiting 语义）
- 重生完成后自动调 concatenate + render preflight（复用 `episode-preview-production.ts` 的后半段，抽出 `resumeFromConcatenate(workflowId, ...)` 导出函数）

### TDD 测试

后端（`backend/tests/test_shot_regeneration.py`）：
1. `test_regenerate_only_failed_shots`：3 镜头（2 成功 1 失败，用 `_set_shot_extra_data`+直接改 VideoJob status 构造）→ filter=failed → 只有失败镜头产生新 VideoJob；成功镜头任务无变化
2. `test_regenerate_by_character`：镜头A含"孙剑"、镜头B不含 → character_name=孙剑 → 只重生A
3. `test_regeneration_marks_superseded_and_concatenate_uses_latest`：重生镜头A → 旧任务 `superseded_by_regeneration==true` → concatenate manifest 中镜头A的 video_url 为新任务产物
4. `test_regenerate_inherits_workflow_strategy`：workflow metadata 有 latest_production_strategy=final_quality，请求不传 → 新任务 extra_data.production_strategy==final_quality（缺锁时 422）
5. `test_shot_review_aggregates_evidence`

前端（`frontend/e2e/studio-shot-review.spec.ts`，mock 模式）：
6. 审阅列表渲染镜头卡与证据；点"仅重生失败"只对失败镜头发起请求（断言请求 payload 的 shot_ids/filter）
7. 重生成功后自动触发 concatenate 请求

#### 验收命令

```bash
cd backend && DEV_MODE=true PYTHONPATH=. pytest -q tests/test_shot_regeneration.py test_workflow_routes.py
cd frontend && npm run typecheck && npm run build && npx playwright test e2e/studio-shot-review.spec.ts --project=chromium
```

#### S3 提交切片

1. `feat: add shot regeneration api with failed and character filters`
2. `feat: concatenate uses latest per-shot media`
3. `feat: add studio shot review board`

---

## S4：声音一致性桥接 + 配角批量定稿（1-2 周）

### S4-A 音频路由规则

**新增 `backend/app/services/audio_route_service.py`**：

```python
def resolve_shot_audio_route(shot, *, model_limits: dict, voice_lock: dict | None) -> dict:
    """返回 {"route": "tts"|"native_audio"|"silent", "reason": str}
    规则（按序）：
      1. 有对白/字幕文本 且 voice_lock 存在      → tts（保声线一致，最高优先）
      2. 有对白 但无 voice_lock：
         a. final_quality → 上游门禁已阻断（不会到这）
         b. draft → tts + 默认音色，reason 标记 voice_lock_missing
      3. 无对白（纯动作/环境镜头）且 model_limits.native_audio → native_audio
      4. 其余 → silent
    """
```

接入点：`generate_workflow_media_batch` 的 TTS 分支（workflow.py:1986 `if request.audio_mode != "none" and subtitle_text`）改为按 route 决策；route 结果写入 VideoJob/TTSJob `extra_data.audio_route`。

**声线命中率统计**：`GET /api/v1/production-control/workflow/{workflow_id}/voice-lock-stats` → `{total_dialogue_shots, voice_locked, hit_rate, misses:[{shot_id, character_name}]}`（聚合 TTSJob.extra_data.voice_source，字段已存在）。

### S4-B 配角批量定稿向导

**新增 `POST /api/v1/production-cards/novel/{novel_id}/batch-finalize-supporting`**：

```
Request = {"min_occurrences": 2, "image_model_config_id": str|null, "voice_pool": [str]|null}
流程（复用现有能力，无新生成逻辑）：
  1. 从 StoryEntity(character) 中筛"非主角"（无锁定视图且出场≥min_occurrences，
     出场数按 Shot.extra_data.entity_refs 反查统计）
  2. 每个配角：调用现有 asset_generation_service 生成【单视图 front】资产并自动锁定
     （配角只要求 1 视图 —— 与 ASSET_VIEW_PRESETS.character 区分，卡片 readiness 判定同步：
      entity attributes 加 "role_tier": "supporting"，evaluate_entity_final_readiness 对
      supporting 只要求 front 锁定 + 声线）
  3. 声线：从 voice_pool（默认取系统音色列表）轮询分配，写入 StoryBible.character_rules
Response = {"finalized": [{"entity_id","name","asset_id","voice"}], "skipped": [...]}
```

前端：定稿间顶部"一键补齐配角"按钮 + 结果清单。

### TDD 测试

后端（`backend/tests/test_audio_route_and_supporting.py`）：
1. `test_dialogue_with_voice_lock_routes_tts`
2. `test_action_shot_routes_native_audio_on_seedance20` / `test_action_shot_silent_on_legacy_model`
3. `test_voice_lock_stats_hit_rate`：3 对白镜头 2 命中 → hit_rate≈0.67，misses 列出未命中角色
4. `test_batch_finalize_supporting_creates_single_view_and_voice`：2 配角 → 各产生 1 锁定 front 资产 + character_rules 写入音色；主角不受影响
5. `test_supporting_tier_readiness_only_requires_front`：配角卡 front 锁定+声线 → final_ready==true

前端 e2e：
6. 定稿间点"一键补齐配角"→ 断言请求与结果清单渲染

#### 验收命令

```bash
cd backend && DEV_MODE=true PYTHONPATH=. pytest -q tests/test_audio_route_and_supporting.py tests/test_production_cards.py test_tts_story_bible.py
cd frontend && npm run typecheck && npm run build
```

#### S4 提交切片

1. `feat: add shot audio route service`
2. `feat: add voice lock stats endpoint`
3. `feat: add supporting character batch finalize`

---

## S5：真实成片与发布包（2-3 周）

### 目标
从"HTML 预览包"到可下载真实 mp4：本地 FFmpeg 渲染为默认路径（个人/小团队），云渲染沿用已有 ffmpeg_cloud 适配。

### 后端

1. **新增 `backend/app/services/ffmpeg_local_renderer.py`**：

```python
async def render_workflow_package(manifest: dict, *, output_dir: Path, burn_subtitles: bool) -> dict:
    """输入：现有 render manifest（segments 含 video_url/audio_url/subtitle/duration/transition）
    步骤：
      1. 逐 segment 下载/定位本地文件（/static 直接用文件路径）
      2. 每段：ffmpeg 合并视频+音轨（无音轨补静音 anullsrc）
      3. concat demuxer 顺序拼接（转场 P后期，先硬切）
      4. burn_subtitles: subtitles filter 烧录 SRT；否则外挂
      5. 输出 /static/exports/final-{workflow_id}-{ts}.mp4 + 时长/分辨率探测(ffprobe)
    返回 {"output_url","duration","width","height","subtitle_url","log_tail"}
    环境检查：shutil.which("ffmpeg") 缺失 → 结构化错误 ffmpeg_not_installed（前端给安装指引）
    """
```

2. **改 `POST /api/v1/workflow/{workflow_id}/render`**：`render_backend` 增加 `"ffmpeg_local"`；成功后 SynthesisJob `render_status="rendered"`、`output_url=真实mp4`、`is_publishable=true`——`publication_readiness`（已有，只认 .mp4/.mov/.webm）自动放行，**发布门禁零改动**。

3. **BGM/混音（本阶段最小版）**：manifest 段级 `music_cue` 存在且资产库有对应音频资产时，以 `-filter_complex amix` 低音量混入；没有则跳过。

### 前端

- workflow/studio 渲染执行器选项加"本地 FFmpeg（真实成片）"；渲染完成显示可下载 mp4 + SRT
- 发行台：发布表单（标题/简介/封面/比例）→ 已有 `/synthesis/publish`

### TDD 测试

后端（`backend/tests/test_ffmpeg_local_render.py`；CI 无 ffmpeg 时 `pytest.mark.skipif(not shutil.which("ffmpeg"))`）：
1. `test_render_two_segment_manifest_produces_playable_mp4`：DEV 占位视频两段 → 输出文件存在、ffprobe 时长≈两段和、有音轨
2. `test_render_burns_subtitles_when_requested`
3. `test_missing_ffmpeg_returns_structured_error`（monkeypatch which→None）
4. `test_rendered_output_passes_publication_readiness`：渲染后 SynthesisJob 可发布；HTML 预览包仍被拒（既有测试回归）

#### 验收命令

```bash
which ffmpeg || brew install ffmpeg
cd backend && DEV_MODE=true PYTHONPATH=. pytest -q tests/test_ffmpeg_local_render.py test_project_permissions_publication.py test_workflow_routes.py
cd frontend && npm run typecheck && npm run build
# 手工验收：DEV_MODE 跑一键草片 → 本地FFmpeg渲染 → 下载 mp4 本机可播放
```

#### S5 提交切片

1. `feat: add local ffmpeg renderer`
2. `feat: wire ffmpeg_local render backend into workflow render`
3. `feat: studio publish flow uses real rendered mp4`

---

## S6：视觉一致性检测（研究项，S2 稳定后启动）

- 接口已预留：`/assets/{asset_id}/visual-consistency`（Phase 244-246 落地）
- 方案：终稿镜头完成后，抽帧（ffmpeg 每秒1帧）→ 与主角锁定 front 视图做相似度（可用图像 embedding 服务或多模态模型打分）→ 分数写回资产版本历史与 shot quality_report
- 不设阻断，只进审阅列表排序（低分优先人审）
- 前置条件：S2 多参考生成质量达标、S3 审阅列表可消费分数

当前启动切片（2026-07-03）：
- 已新增后端非阻断记录骨架：主角 locked front 资产作为参考，结果写入 `Asset.generation_params.visual_consistency_history`、`VideoJob.extra_data.visual_consistency` 与 `Shot.extra_data.quality_report.visual_consistency`。
- 已新增本地抽帧 service：`backend/app/services/video_frame_extractor.py` 支持本地 `/static/` 视频抽帧到 `/static/generated/frames/`，远端 URL 和缺 ffmpeg 走结构化错误。
- 已新增手动触发端点：`POST /api/v1/workflow/{workflow_id}/visual-consistency`，可按镜头检查最新成功视频，默认不抽帧，返回 checked/skipped 明细。
- `final_quality` 的分步视频任务会写入 `VideoJob.extra_data.visual_consistency_auto_check=true`，任务成功同步镜头时自动生成非阻断证据；`draft_fast` 不自动开启。
- 已扩展 shot-review：返回 `quality_report`、`visual_consistency_score` 与 `evidence.visual_consistency`，默认低分镜头优先展示，低分不阻断生成/发布。
- 已新增本地轻量相似度适配器：`backend/app/services/visual_similarity_adapter.py` 会对本地 `/static/` 参考图与抽帧做 RGB 平均差评分，远端或缺失输入保持非阻断占位回退；后续 embedding/多模态相似度服务可替换该适配层。

---

## 里程碑总表

| 阶段 | 内容 | 周期 | 依赖 | 关键验收 |
| --- | --- | --- | --- | --- |
| S1 | 策略真实路由 + 定稿卡 | 1-2 周 | 无 | 不选模型时策略决定实际提交模型；定稿卡 ready 与终稿门禁判定一致 |
| S2 | 多模态参考包 | 2-3 周 | 火山 Seedance 2.0 API 正式开放（S2-E 核对） | mock 断言 content 含多图+@引用；单图模型行为零变化 |
| S3 | 镜头审阅+局部重生 | 2 周 | S1 | 改一个镜头不重跑整集；manifest 取最新 |
| S4 | 声音路由+配角定稿 | 1-2 周 | S1 | 声线命中率可查询；配角单视图定稿即 ready |
| S5 | 真实成片 | 2-3 周 | 无（可与 S2 并行） | 本机可播放 mp4 通过发布门禁 |
| S6 | 视觉检测 | 研究 | S2+S3 | 低分镜头进审阅排序 |

并行建议：S1 与 S5 可并行（互不触碰同文件热区）；S2 等 API 开放期间先做 S2-A/B（矩阵+构建器可用 mock 全测）。

## 全局回归口径（每阶段收尾必跑）

```bash
cd backend && DEV_MODE=true PYTHONPATH=. python3 -m compileall app && DEV_MODE=true PYTHONPATH=. pytest -q
cd frontend && npm run typecheck && npm run build && npx tsc --noEmit
cd frontend && npx playwright test e2e/onboarding-simplification.spec.ts e2e/studio-full-flow.spec.ts e2e/workflow-production-guidance.spec.ts e2e/synthesis-history.spec.ts --project=chromium --workers=1
git diff --check
```

## 风险登记

| 风险 | 缓解 |
| --- | --- |
| Seedance 2.0 API 字段与第三方文档不符 | S2-E 核对清单先行；SDK 提交层 role 字段集中在一个函数内，改一处即可 |
| Agent Plan 通道不支持多参考 | limits 按 provider 分别登记，Agent Plan 保持 images:1 直到确认 |
| 多图公网交付失败率上升（9 图 vs 1 图） | dropped 机制降级不阻断；CDN 配置缺失时回退单图并提示 |
| FFmpeg 环境差异（用户本机无 ffmpeg） | 结构化 ffmpeg_not_installed 错误 + 安装指引；云渲染作为替代路径已存在 |
| 既有测试断言 hint 文案 | S1 同步更新 `test_workflow_media_batch_tracks_final_quality_production_strategy` |
| 定稿卡与门禁判定分叉 | 判定函数唯一化（evaluate_entity_final_readiness）+ 一致性回归测试（S1-B #2） |
