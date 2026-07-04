# 连续动漫制作低门槛优化方案

日期：2026-07-02  
目标：把当前“小说、实体、资产、分镜、视频、配音、合成”等独立模块收束为一条可用、可恢复、可审阅的连续动漫生产线，重点解决完整小说、多集制作时的风格、角色、场景、道具、事件、配角、声音一致性。

## 1. 结论摘要

当前系统不是能力不足，而是“能力散”。仓库里已经具备连续动漫生产的关键部件：

| 能力 | 当前基础 | 代表文件/接口 |
| --- | --- | --- |
| 小说与章节 | 小说导入、章节管理、章节生成 | `frontend/src/app/novels/page.tsx`, `backend/app/api/v1/endpoints/novels.py`, `chapters.py` |
| Story Bible / 实体 | 角色、场景、道具、事件抽取，冲突检查，状态机 | `backend/app/api/v1/endpoints/story_bible.py` |
| 资产与多视图 | 角色/场景/道具资产、锁定、默认动漫模板库 | `backend/app/services/default_anime_library.py`, `backend/app/services/asset_lock_service.py` |
| 一致性上下文 | Prompt 组装、生产预检、状态机注入 | `backend/app/services/prompt_composer.py`, `backend/app/services/consistency_preflight.py` |
| 本集工作流 | 剧本、分镜、镜头、媒体、字幕、合成、渲染包 | `backend/app/api/v1/endpoints/workflow.py` |
| AI 制片辅助 | 资产锁、生产包、媒体审计、质量检查、下一步建议 | `backend/app/services/production_control.py` |
| 一键草片链路 | 前端已串起工作流、剧本、分镜、制片检查、媒体生成、合成、渲染预检 | `frontend/src/lib/episode-preview-production.ts` |
| Prompt Skill | 可维护、可版本化、可注入的提示词模板 | `backend/app/models/prompt_skill.py`, `backend/app/services/default_prompt_skills.py` |
| 模型配置 | Seedance 2.0/fast、Seedream、TTS、Agent Plan 等模型目录 | `backend/app/core/volcano_config.py`, `backend/app/core/volcano_agent_plan_config.py` |

核心优化方向：

1. 产品层增加一个“系列动漫工作室 / Series Studio”，把小说到多集成片的路径变成单一入口。
2. 数据层把 Story Bible 升级为“Production Bible”，成为风格、角色、场景、道具、事件、声音和提示词的唯一事实源。
3. 流程层把 `runEpisodePreviewProduction()` 产品化为“生成本集草片”，并把它接到整书/多集计划。
4. 模型层采用“草稿快、终稿准”的路由：Seedance-2.0-fast 用于批量草稿，Seedance-2.0 用于终稿镜头；Seedream/同类图像模型负责多视图资产；TTS 模型绑定角色声线。
5. 质量层把一致性检查从“提示”升级为“可配置门禁”：缺主角定稿图、声线、场景锚点、道具状态、模型验证失败时阻断生产。

## 2. 当前最大问题

### 2.1 入口太多，用户要像工程师一样理解系统

现在顶部入口包含工作台、极速向导、小说、实体、资产、剧本、分镜、镜头、视频生成、TTS、合成、工作流、AI制片、Prompt 技能、模型配置等。能力完整，但普通创作者面对的是“工具集合”，不是“制作流程”。

结果：

- 用户不知道先做 Story Bible、资产，还是直接生成分镜。
- 一致性功能存在，但散在实体、资产、分镜、镜头、视频、TTS 页面里。
- 多集制作时，用户无法从一个地方看到“第 1 集锁定了什么，第 2 集继承了什么，哪里变了”。

### 2.2 Story Bible 还没有成为强约束

系统已有 Story Bible、StoryEntity、状态机、冲突检查和 PromptComposer，但现状仍容易出现：

- 剧本生成、分镜生成、视频生成各自拼上下文。
- 资产锁可以存在，但不是每条生产线的必经项。
- 角色声音配置和视觉资产没有在同一张“角色定稿卡”里收口。
- 事件、道具状态、服装变化没有形成跨集快照。

### 2.3 “多集连续制作”的状态不够显性

已有 `workflow` 适合一集生产，已有小说章节结构，但“整本小说如何拆成季/集/镜头包”的控制台还不够强。

缺少面向用户的：

- 整书拆集计划。
- 每集承接上一集的状态摘要。
- 每集生产状态机。
- 跨集角色/场景/道具/声音继承记录。
- 批量生成与失败恢复总览。

### 2.4 模型能力没有被包装成业务策略

当前模型目录已经包含：

- `Doubao-Seedance-2.0`
- `Doubao-Seedance-2.0-fast`
- `Doubao-Seedream-4.5`
- `Doubao-Seedream-5.0-lite`
- Agent Plan 文本/视频/图像模型
- MiniMax / Volcano TTS 相关模型

但用户不应该直接理解每个模型细节。应该选择的是：

- 快速草稿
- 高质量终稿
- 低成本批量
- 角色一致性优先
- 音画直生优先
- 分步视频+TTS 优先

系统再把这些策略映射到具体模型。

## 3. 目标产品形态：Series Studio

新增或强化一个“系列动漫工作室”，作为小说到连续动漫的主入口。

### 3.1 用户看到的主流程

```text
导入/选择小说
  -> AI 分析整书，生成 Production Bible
  -> AI 拆分季/集/章节范围
  -> 生成并锁定角色、场景、道具、声音资产
  -> 选择某一集，一键生成剧本/分镜/镜头
  -> 一键生成本集草片
  -> AI 检查一致性问题并给出修复动作
  -> 终稿重生关键镜头
  -> 渲染、字幕、导出、发布
```

### 3.2 Series Studio 页面结构

| 区域 | 功能 | 复用现有能力 |
| --- | --- | --- |
| 小说/系列选择 | 选择小说、导入小说、显示拆集状态 | `novels`, `chapters`, `quick-start` |
| Production Bible 概览 | 风格、角色、场景、道具、事件、声音一致性状态 | `story_bible.py`, `default_anime_library.py` |
| 多集计划 | 每集章节范围、剧情钩子、承接状态、生产状态 | `Novel.extra_data.series_plan` 或后续 Episode 表 |
| 本集生产看板 | 剧本、分镜、镜头、资产锁、媒体、合成、渲染 | `workflow.py`, `episode-preview-production.ts` |
| AI 制片助手 | 自动补缺、风险解释、下一步建议 | `production_control.py` |
| 模型策略 | 草稿/终稿/低成本/高一致性策略选择 | `llm_config.py`, `volcano_config.py` |
| 质量门禁 | 缺资产、缺声线、模型未验证、参考图不可用、状态冲突 | `consistency_preflight.py` |

## 4. Production Bible：一致性的唯一事实源

把当前 Story Bible 扩展为 Production Bible，不一定第一阶段新增表，可以先用 `StoryBible.extra_data`、`StoryEntity.attributes`、`Novel.extra_data.series_plan` 轻量落地。

### 4.1 Production Bible 应包含

| 维度 | 必填内容 | 目的 |
| --- | --- | --- |
| 系列风格 | 画风、色彩、镜头语言、比例、负面约束 | 保证不同集不像不同作品 |
| 角色 | canonical_name、别名、外观、服装状态、表情包、三视图、声线、关系 | 保证人物形象和声音稳定 |
| 场景 | 地点、时代、材质、光照、布局图、常用镜头 | 保证场景复用稳定 |
| 道具 | 外观、尺寸、材质、归属、状态流转 | 避免关键道具忽隐忽现或状态错乱 |
| 事件 | 时间线、因果、影响的角色/道具/场景 | 保证多集剧情连续 |
| 配角/群像 | 出场集、身份、外观简卡、声线分组 | 保持配角不乱入、不换脸 |
| 声音 | 角色音色、旁白音色、语速、情绪、禁用音色 | 保证配音连续 |
| Prompt Skill | 当前系列启用的模板与版本 | 保证提示词变更可追溯 |

### 4.2 从 Story Bible 到 Production Bible 的最小实现

P0 不建议大迁移，先做轻量封装：

- `StoryBible.extra_data.production_bible` 保存系列风格、默认模型策略、启用模板版本。
- `StoryEntity.attributes.visual_dna` 保存角色/场景/道具视觉 DNA。
- `StoryEntity.attributes.voice_profile` 保存角色声线。
- `StoryEntity.attributes.asset_pack` 保存多视图要求与定稿资产 ID。
- `StoryBible.extra_data.state_machine` 继续保存人物状态、场景状态、道具流转、事件时间线。
- `Workflow.extra_data.production_snapshot` 保存本集开拍时的 Production Bible 快照，保证后续可追溯。

### 4.3 一致性锁定原则

1. 系列级锁：画风、主角基础外观、世界观、主要场景。
2. 集级锁：本集服装、情绪状态、场景天气、道具状态。
3. 镜头级锁：镜头出场角色、参考图、动作、对白、音色。
4. 任务级快照：每次视频/TTS/图像生成都保存当时使用的锁，不能只引用“最新设定”。

## 5. 目标业务流程

### 5.1 整书初始化

输入：小说文本或已有 Novel/Chapter。

AI 自动执行：

1. 识别章节结构和剧情弧线。
2. 抽取角色、场景、道具、事件、配角。
3. 生成 Production Bible 初稿。
4. 生成多集拆分建议：每集覆盖章节、冲突、高潮、结尾钩子。
5. 生成缺失资产清单。

用户只需要确认：

- 题材/画风。
- 主角/重要配角是否正确。
- 需要先定稿的角色、场景、道具。
- 每集时长或镜头预算。

验收标准：

- 导入一本小说后，用户在一个页面能看到 Production Bible 和多集计划。
- 不要求用户手动进入实体、资产、Story Bible 页面才能继续。

### 5.2 资产定稿

AI 自动生成候选：

- 主角三视图：正面、侧面、背面、全身、表情。
- 重要场景四视图：全景、布局、关键光影、夜/昼状态。
- 关键道具多状态：普通、损坏、发光、觉醒等。
- 角色声音卡：音色、语速、情绪、试听样例。

用户操作应简化成：

- “接受为定稿”
- “再生成 4 个候选”
- “用这张图替换正面视图”
- “给这个角色换声线”

验收标准：

- 生成本集草片前，主角必须至少有一个定稿参考图和声线。
- 缺失资产时，AI 制片助手给出一键补齐动作。

### 5.3 本集生产

复用并产品化 `runEpisodePreviewProduction()`：

```text
确认工作流
  -> 复用/生成剧本
  -> 复用/生成分镜镜头
  -> AI 制片检查
  -> 应用资产锁和镜头生产合约
  -> 批量生成视频/TTS/字幕
  -> 连续成片
  -> 渲染预检
  -> 生成本集预览包
```

当前这条链路已经在 `frontend/src/lib/episode-preview-production.ts` 里存在，应成为 P0 的主按钮：“生成本集草片”。

建议补强：

- 在 Series Studio 中展示每个阶段的失败原因和修复入口。
- 当媒体任务 pending 时，显示“等待云端生成”，不要把它当失败。
- 生成完成后直接跳到 Studio/Timeline 审阅，不让用户去任务历史里找结果。

### 5.4 终稿生产

草片通过后，用户只处理问题镜头：

- 一致性低的镜头。
- 主角脸崩的镜头。
- 声音不合适的镜头。
- 字幕/对白不匹配的镜头。
- 动作不符合剧情的镜头。

AI 给出修复动作：

- 重建镜头提示词。
- 换用终稿模型。
- 替换参考图。
- 重新配音。
- 继承上一镜头最后帧/关键帧。

验收标准：

- 用户可以只重生某些镜头，不需要整集重跑。
- 每次重生仍保留 Production Bible 快照、资产锁和模型路线。

## 6. 模型接入与路由策略

### 6.1 当前可优先落地的火山路线

| 任务 | 推荐模型策略 | 当前仓库基础 |
| --- | --- | --- |
| 整书分析/拆集/剧本 | 长上下文文本模型，如 Agent Plan 文本模型 | `volcano_agent_plan_config.py` |
| 结构化实体/分镜 JSON | 支持 JSON/函数调用的文本模型 | `default_prompt_skills.py`, `llm_config.py` |
| 角色/场景/道具定稿图 | Seedream 4.5 或 Seedream 5.0-lite | `volcano_config.py` |
| 草稿视频 | Seedance-2.0-fast, 720p, 4-5 秒 | `DEFAULT_VIDEO_MODEL = Doubao-Seedance-2.0-fast` |
| 终稿视频 | Seedance-2.0, 720p/1080p, 8-10 秒 | `Doubao-Seedance-2.0` 已在模型表 |
| 配音 | MiniMax 或 Volcano TTS，按角色声线绑定 | `tts.py`, `minimax_config.py`, `volcano_service.py` |
| 合成 | 本地预览包 + 后续 FFmpeg 云渲染 | `workflow.py` render/preflight |

火山 Seedance 2.0 应定位为“终稿质量模式”，Seedance 2.0-fast 应定位为“批量草稿模式”。这样用户不会在模型列表里被淹没，只需要选择质量策略。

### 6.2 多模型适配层

对标 Runway、Kling、Luma、OpenAI Sora、Google Veo/Gemini 视频能力，主流趋势是：

- 支持文生视频和图生视频。
- 支持参考图/角色资产复用。
- 支持起始帧、结束帧、关键帧或视频延展。
- 支持音频或原生音画生成的模型越来越多。
- 支持多轮编辑、局部重绘、元素替换。

本项目不应该为每个供应商写一套业务流程，而应该抽象为统一能力：

| 抽象能力 | 供应商差异 | 平台统一字段 |
| --- | --- | --- |
| 文生视频 | 各模型 prompt、时长、比例不同 | `text_to_video` |
| 图生视频 | 参考图数量不同 | `image_to_video`, `reference_image_limit` |
| 多参考/元素 | 有的支持多图，有的只支持 1 图 | `input_assets`, `provider_reference_image_limit` |
| 首尾帧/关键帧 | Luma/Veo 等更强调关键帧 | `start_frame`, `end_frame`, `keyframes` |
| 角色一致性 | Sora/Runway 等强调资产复用 | `character_assets`, `asset_version_locks` |
| 原生音频 | Veo/Sora 等可选 | `native_audio`, `direct_av_first` |
| 分步视频+TTS | 当前项目最稳 | `separate_video_tts` |

已有 `generate-media-batch` 同时支持 `separate_video_tts` 和 `direct_av_first` 的策略字段，应继续扩展为统一生产协议。

### 6.3 用户层不要暴露测试模型和占位模型

此前已处理 AI 模型配置页混入测试模型、TTS 占位模型的问题。后续还应把模型列表拆成两层：

- 普通用户：只看到“快速草稿 / 高质量终稿 / 低成本 / 声音 / 文本规划”等策略。
- 高级用户：进入模型配置页才看到 provider、model、API Key、验证状态、能力标签。

验收标准：

- Series Studio 不出现 `tts-model-*`、`*-test`、内部 preflight 模型。
- 生产按钮展示“当前策略：草稿视频 Seedance-2.0-fast + MiniMax TTS”，而不是要求用户理解所有模型。

## 7. AI 辅助功能设计

AI 不只用于生成视频，而要贯穿每一步。

| 阶段 | AI 辅助 | 输出 |
| --- | --- | --- |
| 导入小说 | 章节识别、错章检测、标题清洗 | 章节预览和警告 |
| 整书分析 | 角色/场景/道具/事件抽取 | Production Bible 初稿 |
| 拆集 | 章节合并、节奏建议、钩子生成 | Episode Plan |
| 资产 | 多视图提示词、候选图、声线建议 | 可锁定资产卡 |
| 剧本 | 章节改编、对白优化、旁白压缩 | Script |
| 分镜 | 镜头拆分、景别、运镜、SFX/BGM | Storyboard/Shot |
| 生产前 | 缺口检查、风险解释、一键修复 | Preflight Issues + Actions |
| 生成中 | 失败分类、自动重试建议 | Job Recovery |
| 审阅 | 连贯性评分、字幕/音画同步检查 | Fix List |
| 发布 | 标题、简介、封面、平台比例建议 | Publish Package |

Prompt Skill 应从“单独的模板管理页”变成每个阶段的可见能力：

- 每个任务显示当前启用模板版本。
- 允许系列级选择模板包：国漫热血、悬疑、校园、玄幻、短剧竖屏等。
- 生成任务保存 `prompt_skill_ids` 和版本，便于追溯。
- 模板变更后提示会影响哪些未生成镜头。

## 8. 质量门禁

### 8.1 P0 门禁

生成前必须检查：

- 模型配置存在、已验证、API Key 可解密。
- 小说/章节/剧本/分镜/镜头链路一致。
- 主角色至少有视觉描述或定稿资产。
- 视频参考图如果要传给供应商，必须是公网 URL。
- TTS 角色声线存在或可回退到旁白声线。
- 字幕/对白不能为空，或明确标记无对白镜头。

这些当前已有基础在 `consistency_preflight.py`，应在 Series Studio 中强制走。

### 8.2 P1 门禁

- 角色三视图完整度。
- 场景布局/光影参考完整度。
- 道具状态是否符合事件线。
- 本集开头状态是否承接上一集结尾。
- 镜头时长与对白长度是否匹配。
- 成片是否为真实视频文件，不能把本地 HTML 预览包当发布成片。

### 8.3 P2 门禁

本阶段先补强策略/计划契约，不引入视觉模型检测，也不自动判断画面中的脸型、服装、道具、字幕遮挡或多集风格漂移。P2 的落地边界是终稿前的锁定门禁和快照追溯：

- `final_quality` 是终稿模式：生成前必须表达角色/场景/道具资产锁、角色声线锁和模型路线锁要求；缺锁应作为终稿门禁暴露。
- `draft_fast` 是草稿模式：可以先跑批量草片，但结果和阶段文案必须保留未锁定资产、声线或生产合约缺口提示，不能把草稿当作终稿。
- 视频/TTS/直生音视频任务需要能追溯本次使用的 production strategy、资产锁、声线锁和生产快照。
- 不做视觉内容检测；画面一致性评分、缺失角色检测、字幕遮挡检测和风格漂移检测后移到审阅/自动修复阶段。

## 9. 分阶段落地计划

### P0：收束入口，让现有能力可用

目标：用户从小说页或 Series Studio 进入，不再到处找功能。

改动：

- 新增或强化 `/studio` 为 Series Studio，而不是只选择已有 workflow。
- 在小说详情/Quick Start/Producer 中统一导向 Series Studio。
- 把 `runEpisodePreviewProduction()` 做成标准“生成本集草片”按钮。
- 在页面展示 Production Bible 缺口和一键补齐动作。
- 普通模型选择改成“生产策略”。

验收：

- 选择小说和章节后，用户能一键创建/复用 workflow 并生成本集草片。
- 如果缺模型、资产、声线，页面给出结构化原因和修复按钮。
- 不需要用户手动进入视频、TTS、合成三个页面才能得到预览包。

### P1：Production Bible 与多集计划

目标：完整小说变成多集生产计划。

改动：

- 在 `Novel.extra_data.series_plan` 或新 Episode 表中保存集计划。
- 在 `StoryBible.extra_data.production_bible` 中保存风格、模板、模型策略。
- 每个 workflow 保存开拍快照 `production_snapshot`。
- Series Studio 显示每集状态：未开始、Bible 缺口、资产缺口、剧本就绪、分镜就绪、生成中、可审阅、可导出。

验收：

- 一本小说可以拆成多集。
- 第 N 集生成时能继承第 N-1 集结尾状态。
- 修改主角设定后能列出受影响集/镜头。

### P2：资产和声音锁强制化

目标：稳定角色、场景、道具、声音。

改动：

- 角色卡合并视觉、声音、关系、出场集、资产状态。
- 缺主角定稿图或声线时，终稿模式阻断。
- 支持对单个实体生成缺失视图。
- 视频/TTS 任务保存资产锁和声线锁快照。
- 前端生产策略文案明确：`final_quality` 是终稿路径，要求资产/声线锁；`draft_fast` 是草稿路径，可先跑但必须保留缺口提示。
- `runEpisodePreviewProduction()` 不改变后端接口，只在阶段文案和 result metadata 中表达终稿/草稿的锁要求，便于页面展示和任务追溯。

验收：

- 同一角色跨镜头使用同一组锁定资产和声线。
- 用户替换资产后，旧镜头不被隐式改变。
- 可选择“从第 X 集起应用新造型”。
- 选择 `final_quality` 时，页面和结果 metadata 明确提示终稿需要资产锁、声线锁和生产快照。
- 选择 `draft_fast` 时，页面和结果 metadata 明确提示可先生成草稿，但未锁定资产/声线缺口必须保留。
- 本阶段不验收视觉模型检测；只验收终稿前锁/声线门禁表达和快照可追溯。

### P3：模型策略和 Seedance-2.0 终稿模式

目标：模型能力服务业务，而不是暴露复杂列表。

改动：

- 新增 `production_strategy`：draft、final、low_cost、consistency_first、direct_av。
- draft 默认 Seedance-2.0-fast，final 默认 Seedance-2.0。
- 将模型能力矩阵写入 model registry：参考图数量、时长、分辨率、是否原生音频、是否关键帧。
- 若模型只支持单参考图，UI 明确展示“其他资产将进入提示词和 metadata”。

验收：

- 用户选择“高质量终稿”，实际任务使用终稿视频模型。
- 用户选择“快速草稿”，实际任务使用 fast 模型并降低分辨率/时长。
- 任务历史能追踪策略、模型、Prompt Skill、资产锁。

### P4：审阅与自动修复

目标：只修坏镜头，不重跑整集。

改动：

- 每个镜头生成后展示一致性评分、失败原因、重试建议。
- AI 可根据问题重建 prompt 或替换参考图。
- 支持批量重生“仅失败镜头 / 仅低分镜头 / 仅某角色镜头”。

验收：

- 用户能从审阅列表直接重生问题镜头。
- 重生后自动回填 workflow、合成清单和渲染预检。

### P5：真实成片与发布包

目标：从预览包走到可发布作品。

改动：

- 接入本地/云 FFmpeg 渲染，输出真实 mp4/webm/mov。
- 支持字幕外挂/烧录、音轨混音、BGM/SFX、封面。
- 发布包保存标题、简介、封面、比例、平台元数据。

验收：

- `publication_readiness` 只允许真实视频发布。
- 用户可以下载最终视频和字幕文件。

## 10. 预期成效

| 指标 | 当前体验 | 优化后 |
| --- | --- | --- |
| 从小说到本集草片 | 需要跨多个页面理解流程 | Series Studio 一键走完主链路 |
| 多集一致性 | 依赖用户记忆和手动维护 | Production Bible + Episode 状态快照 |
| 角色稳定性 | 资产/提示词/声线散落 | 角色定稿卡统一管理 |
| 失败排查 | 需要看任务历史或 toast | 阶段化原因 + AI 修复动作 |
| 模型选择 | 模型列表复杂，测试/TTS 占位易干扰 | 策略选择，模型路由后台完成 |
| 生产成本 | 容易一上来高质量重跑 | fast 草稿 + 终稿重生关键镜头 |
| 交付质量 | 本地预览包与真实成片边界不清 | 预览、终稿、发布门禁明确区分 |

## 11. 下一轮实现建议

优先做 P0，不建议马上重构所有表。

### 11.1 最小可交付切片

1. `/studio` 改为以小说/集为核心，而不是只选 workflow。
2. 引入“本集草片”主按钮，复用 `runEpisodePreviewProduction()`。
3. 把 Production Bible 缺口卡展示在 Studio 首页。
4. 模型策略先做前端枚举：快速草稿、高质量终稿、分步视频+TTS。
5. 失败原因统一展示 `generation_preflight`、`render_preflight` 和 producer assistant 输出。

### 11.2 推荐测试

- 前端 E2E：从小说选择到创建/复用 workflow，再点击生成本集草片。
- 前端 E2E：缺模型配置时显示预检阻断，不继续合成。
- 后端测试：workflow media batch 按策略解析 Seedance-2.0-fast/Seedance-2.0。
- 后端测试：Production Bible 快照写入 Workflow/VideoJob/TTSJob。
- 后端测试：修改角色资产后，已生成任务仍保留旧 asset lock 快照。

## Series Studio V2 Verification

验证日期：2026-07-04。

- Backend regression: `cd backend && DEV_MODE=true PYTHONPATH=. python3 -m pytest -q`，结果 `637 passed, 2 skipped, 17 warnings in 32.80s`。
- Frontend typecheck: `pnpm --dir frontend typecheck`，结果 exit 0。
- Frontend build: `pnpm --dir frontend build`，结果 exit 0，Next.js production build 完成。
- Playwright all-scenario suite: 从前端发起的 10 个 spec 矩阵通过，覆盖 Quick Start、Series Studio、Production Bible、多集计划、Consistency Ledger、Shot Review、Video Generation Preflight、Workflow Guidance 和顶部导航，结果 `22 passed`。
- Focused preflight regression: `e2e/video-generation-preflight.spec.ts --project=chromium --workers=1`，结果 `2 passed`，验证当前 `/video/models` 视频模型目录夹具与预检阻断文案一致。
- Manual browser audit screenshots: `/tmp/ai-video-platform-series-studio-e2e/series-studio-overview.png`、`/tmp/ai-video-platform-series-studio-e2e/series-studio-mobile.png`。
- Known limitations: 浏览器全流程套件使用 mock 后端和 mock 外部模型响应来保证可重复验证；未在本次验证中调用真实云端视频/TTS/图像生成服务。后端测试仍有既有 `datetime.utcnow()` deprecation warnings，不影响本次功能通过。

## 12. 参考资料

- 火山引擎方舟文档：https://www.volcengine.com/docs/82379/1520757
- Runway API 文档：https://docs.dev.runwayml.com/
- Kling AI API 文档：https://kling.ai/document-api/quickStart/productIntroduction/overview
- Luma API 视频生成文档：https://docs.lumalabs.ai/docs/video-generation
- OpenAI Sora API 视频生成文档：https://developers.openai.com/api/docs/guides/video-generation
- Google Gemini API 视频生成文档：https://ai.google.dev/gemini-api/docs/video
