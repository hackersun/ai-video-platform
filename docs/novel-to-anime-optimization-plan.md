# 小说到动漫视频生成完整优化计划

## 目标流程

Project 项目
→ Novel/Chapter 小说与章节
→ Story Bible 世界观、一致性设定
→ Character/Scene/Prop/Costume Assets 角色、场景、道具、服装资产
→ Script 章节改编剧本
→ Storyboard 分镜
→ Shot 镜头
→ ImageJob 参考图
→ VideoJob 镜头视频
→ TTSJob 配音
→ SynthesisJob/Timeline 合成与导出

## 第一阶段：接口闭环和阻断修复

- 挂载前端已调用但未暴露的后端路由：`workflow`、`images`、`assets`、`projects`、`timelines`、`storyboard-ai`。
- 统一合成接口：支持 `/synthesis/create` 和 `/synthesis/generate`，请求可用 `video_job_id/tts_job_id` 或直接 `video_url/audio_url`。
- 统一 TTS 字段：前端使用 `text_content`、`voice_model`、`api_provider`，后端生成结果回写 `Shot.audio_url/audio_status`。
- 统一视频状态：`/video/status/{task_id}` 和 `/video/jobs/{job_id}/refresh` 都持久化 `VideoJob`，并回写 `Shot.video_url/video_status`。
- 修复 `shots/reorder` 静态路由优先级和请求体契约。

## 第二阶段：统一模型规划

### Provider

统一 provider id：

- `volcano`: 火山引擎，文本、图像、视频、TTS。
- `dashscope`: 阿里 DashScope/通义千问，文本。
- `qianlian`: 阿里百炼兼容入口。
- `minimax`: 语音合成。
- `openai`: 文本、视觉、图像等扩展能力。

### Model

模型注册表必须区分：

- `id`: 系统内部稳定 ID，例如 `volcano.seedance.1_0_pro_fast`。
- `provider_id`: 供应商 ID。
- `api_model_id`: 调用第三方 API 时传入的真实模型名或 endpoint id。
- `modality`: `text`、`image`、`video`、`audio`。
- `capabilities`: `text_generation`、`vision_input`、`text_to_image`、`image_to_video`、`text_to_video`、`text_to_speech` 等。
- `endpoint_key`: `chat`、`image_generation`、`video_generation`、`tts`。
- `limits`: 上下文、尺寸、时长、分辨率、比例。

### Task Default

按任务而不是按全局设置默认模型：

- `novel_generation`: 长文本模型。
- `script_generation`: 长文本/结构化输出模型。
- `storyboard_generation`: JSON 稳定输出文本模型。
- `character_image`: 图像模型。
- `scene_reference_image`: 图像模型。
- `shot_video`: 视频模型，支持图生视频优先。
- `tts_dialogue`: TTS 模型。
- `final_synthesis`: 本地 ffmpeg 或云端合成执行器。

## 第三阶段：一致性核心

新增或强化 Story Bible：

- 项目风格：画风、色彩、镜头语言、画幅、负面约束。
- 角色锁定：canonical prompt、头像、全身图、表情、姿态、声线。
- 场景锁定：地点描述、固定构图、时代/材质/光照。
- 道具锁定：名称、外观、归属、首次出现和后续状态。
- 事件时间线：章节事件、角色状态变化、物品流转。

所有生成请求进入统一 Prompt Composer：

`任务目标 + 项目风格 + 角色锁定 + 场景锁定 + 道具锁定 + 当前事件 + 镜头描述 + 负面约束`

## 第四阶段：生产任务编排

- Workflow 后端状态机记录每一步输入、输出、失败原因和可重试点。
- 所有 job 绑定 `project_id/workflow_id/novel_id/chapter_id/script_id/storyboard_id/shot_id`。
- 镜头成为生产中枢：参考图、视频、音频、合成结果都回写 Shot。
- Timeline 使用 clips 组装最终成片，支持字幕、背景音乐、音效。

## 第五阶段：验证任务

- 后端路由导入与路径 smoke test。
- 前端 TypeScript 检查。
- E2E：小说创建、章节生成、角色提取、分镜生成、镜头参考图、视频生成轮询、TTS、合成记录创建。
- 模型配置：每个任务默认模型能从用户配置中解析到有效 API Key。

---

## 2026-05-10 深度分析：达到可用产品的标准

当前工程已经能在 `DEV_MODE` 下跑通一条基础链路：小说、章节、角色、剧本、分镜、镜头、参考图、TTS、视频、合成、任务中心。但它还不是“可用的小说到动漫视频生产系统”。可用标准应定义为：

1. 用户可以导入或创建小说，并得到可审阅的章节结构。
2. 系统能从小说/章节中结构化抽取角色、场景、道具、事件，并支持人工确认、合并、重命名、版本管理。
3. Story Bible 是全流程一致性的权威来源，生成分镜、镜头、图片、配音、视频时都必须引用它。
4. 角色、场景、道具必须有可追溯参考资产，视频生成能稳定使用这些参考资产。
5. 每个章节可以自动生成或再编辑剧本、分镜、镜头，镜头之间有前后逻辑和事件时间线约束。
6. 文本、图像、声音、视频、合成模型必须按任务配置，支持项目级覆盖和用户级默认配置，不能散落硬编码。
7. 权限必须按用户、项目、成员角色隔离，owner/editor/viewer 权限一致应用到所有资源。
8. 合成和发布必须产出真实可下载/可发布的最终作品记录，而不是只创建占位任务。
9. 从前端页面可以完整操作，不依赖手写 API 请求；关键流程必须有 E2E 验证。

## 当前能力与差距矩阵

| 阶段 | 当前能力 | 主要缺口 | 优先级 |
| --- | --- | --- | --- |
| 项目/权限 | 有 Project、ProjectMember、项目风格字段 | 大多数 API 仍只按 `user_id` 校验；团队页是静态数据；成员角色未执行到资源访问 | P0 |
| 小说创建管理 | 支持手动创建、AI生成、章节 CRUD | 无 TXT/MD/DOCX/EPUB/PDF 导入、导入预览、章节切分确认、来源元数据、导入任务 | P0 |
| 章节编辑 | 支持编辑、生成、重生成 | 编辑后不触发实体/Story Bible/分镜一致性重检；章节详情页参数错误会请求 `chapters/undefined` | P0 |
| 实体抽取 | 支持角色抽取 | 无场景、道具、事件抽取；角色无 novel/project 归属、别名、关系、首次出现、状态变化、资产版本 | P0 |
| Story Bible | 有 CRUD 和 prompt compose API | 需手工维护；没有从小说/章节自动构建、增量同步、冲突检测、版本历史 | P0 |
| 资产库 | 支持角色/场景/道具等分类和 CRUD | 资产不会由实体自动生成；参考图没有版本锁；角色头像生成不写 ImageJob/Asset lineage | P0 |
| 剧本/分镜 | 支持从 Script 生成 Storyboard 和 Shots | 无 Chapter -> Script -> Storyboard 一键链路；分镜生成不注入 Story Bible；部分字段生成后未落库 | P0 |
| 镜头 | Shot 已有 prompt、对话、镜头、参考图、音视频回写 | 缺 scene/prop/event refs、consistency_status、review_status、prompt_version、质量评分 | P1 |
| 图像生成 | 有 ImageJob、Shot/Character 关联、DEV_MODE | prompt 未统一经 PromptComposer；真实模型选择硬编码；缺人物/场景/道具定稿资产批量生成 | P0 |
| TTS | 有多角色文本解析、Shot 回写、MiniMax/Volcano | 角色音色不稳定绑定到 Story Bible；状态值前端仍混用 completed/succeeded；没有对白分段审阅 | P1 |
| 视频 | 有 VideoJob、Shot 回写、模型选择 UI | 视频 prompt 不强制引用 Story Bible/资产；批量镜头生成、失败重试、质量验收不足 | P1 |
| 合成/导出 | 有 SynthesisJob 和 workflow concatenate | 非 DEV_MODE 合成只是 pending/占位；拼接只返回第一个视频；缺 ffmpeg 合成、字幕、混音、封面、导出文件 | P0 |
| 发布 | 新建小说页存在“发布小说”文案 | 没有成片发布模型、发布状态、下载包、分享链接、平台元数据、权限控制 | P0 |
| 模型配置 | LLMConfig 加密 Key；有 model_registry | 任务默认模型未贯穿所有生成端点；无项目级/任务级覆盖；调用日志和成本不完整 | P0 |
| 前端流程 | 主要页面可渲染；DEV_MODE E2E 可通过 API 跑通 | 缺导入/实体审阅/Story Bible/资产定稿/一致性检查/真实发布页面；E2E 绕过多数页面操作 | P0 |

## P0 必须先完成的任务

1. 小说导入管线
   - 新增 ImportJob 模型：文件名、格式、状态、错误、解析统计、章节预览、来源 hash。
   - 支持 TXT/Markdown 优先，随后 DOCX/EPUB/PDF。
   - 后端提供上传、预览、确认导入、失败重试接口。
   - 前端提供导入向导：上传、编码/章节识别、章节预览、确认创建小说和章节。
   - 验收：上传外部小说后能生成 Novel + Chapters，并可撤销或重导。

2. 统一实体抽取与审阅
   - 新增 Entity/EntityMention/EntityRelation 或至少扩展 Character 并新增 Scene/Prop/Event 模型。
   - 抽取输出统一 JSON schema：canonical_name、aliases、type、description、first_seen、mentions、state_changes、relations。
   - 前端提供实体审阅台：合并重复、确认归属、编辑描述、写入 Story Bible。
   - 验收：对单章和整本小说可抽取角色、场景、道具、事件，并通过人工确认后入库。

3. Story Bible 自动构建和一致性检查
   - 增加 `story-bibles/generate-from-novel`、`sync-from-chapter`、`check-consistency`。
   - 章节编辑后标记 Story Bible stale，要求重新同步或确认忽略。
   - 记录冲突：人物外观冲突、道具状态冲突、事件顺序冲突、场景设定冲突。
   - 验收：生成分镜前能看到一致性检查结果，严重冲突阻断一键生成。

4. 参考资产生成和版本锁定
   - 为角色/场景/道具生成定稿图，并写入 Asset。
   - Asset 增加 entity_type/entity_id/version/is_locked/source_job_id。
   - Shot 生成参考图和视频时锁定 asset version。
   - 验收：角色定稿图变化不会影响已生成镜头，除非用户明确重新绑定版本。

5. Chapter -> Script -> Storyboard -> Shot 自动链路
   - 剧本生成支持 chapter_id/novel_id，并带 Story Bible 和实体上下文。
   - 分镜生成支持 chapter_id/script_id 两种入口。
   - 落库完整保存 camera_movement、sfx_cue、music_cue、scene_refs、prop_refs、event_refs。
   - 验收：从章节页点击“生成分镜”可创建剧本、分镜、镜头，并保留可编辑中间产物。

6. 统一生成调用入口
   - 所有文本/图像/声音/视频生成都通过 TaskModelResolver + PromptComposer。
   - 禁止在页面和端点里硬编码默认模型，除非来自 model_registry 的 fallback。
   - 记录 provider、model、prompt_version、source_context、usage/cost。
   - 验收：切换任务默认模型后，相应生成端点实际使用新模型。

7. 权限隔离
   - 抽出 `require_project_role(project_id, min_role)` 和 `can_access_resource`。
   - 给 Novel/Chapter/Character/Script/Storyboard/Shot/Asset/Job 补 project_id 或可追踪父链。
   - ProjectMember 支持邀请、角色变更、移除。
   - 前端团队页改为真实接口。
   - 验收：viewer 只能查看不能生成/编辑；editor 可编辑生成；非成员 403。

8. 真实合成、导出、发布
   - 接入本地 ffmpeg 合成：多镜头拼接、音频混合、字幕烧录/外挂、封面生成。
   - 新增 FinalVideo/Publication 模型：文件路径、封面、标题、简介、状态、可见性、分享链接。
   - 前端发布页：成片预览、下载、发布状态、重新导出。
   - 验收：多镜头视频和 TTS 可合成为一个真实 mp4 文件，前端可预览下载。

## P1 强化任务

- 镜头级质量检查：空 prompt、缺参考图、时长不匹配、台词过长、无角色资产、视频失败重试。
- 角色关系图和事件时间线 UI：展示人物关系、道具流转、事件顺序。
- 批量任务编排：按镜头批量生成参考图、配音、视频，支持暂停、重试、跳过。
- 版本管理：Novel/Chapter/Script/Storyboard/Shot 的草稿版本和回滚。
- Timeline 编辑器：可视化轨道、字幕轨、音效轨、BGM 轨。
- 成本预算：按任务估算 token/图片/视频/TTS 成本，生成前提示。

## P2 体验和运营任务

- 模板库：题材模板、镜头模板、角色模板、提示词模板。
- 多语言和字幕翻译。
- 发布平台适配：横屏/竖屏、封面比例、标题简介标签。
- 生成质量评分和人工审核流。
- 素材市场和公共资产复用。

## 2026-05-11 竞品对标后的新增结论

- Runway、Kling、Luma、PixVerse 的共同重点是参考资产、角色/场景一致性、关键帧、多图参考和镜头级控制；本平台已经有小说/章节/Story Bible/实体/镜头链路，后续要把这些参考资产锁定到每个镜头生成任务。
- Animaker、Vyond、Canva、Adobe Firefly 的共同重点是编辑器、模板、配音、字幕、团队协作和导出；本平台后续需要补 Timeline 可视化、字幕审阅、音轨混音、团队审核和多格式发布。
- 本轮已先落地 workflow 级多镜头连续成片清单：`/workflow/concatenate/{workflow_id}` 会按顺序生成 `segments/tracks` manifest，包含视频、配音、字幕、转场、时长、血缘和一致性元数据，并在 DEV_MODE 下提供可验证的本地输出 URL。
- 仍未完成的生产级渲染差距：真实 FFmpeg/云剪辑执行器、音频混音、字幕烧录/外挂、BGM/SFX 轨、封面帧抽取、失败重试和渲染队列资源隔离。

## 2026-05-11 全流程动漫/AI 视频平台功能对比

参考平台与资料：

- Runway Gen-4 / References / Act-One: https://runwayml.com/research/introducing-runway-gen-4
- Kling AI Element Library / Video O1: https://kling.ai/quickstart/klingai-element-library-3-user-guide
- Luma Dream Machine / Ray: https://lumalabs.ai/dream-machine
- Adobe Firefly Image to Video: https://www.adobe.com/products/firefly/features/image-to-video.html
- Canva AI Video Generator: https://www.canva.com/features/ai-video-generator/
- Vyond AI Avatars: https://help.vyond.com/hc/en-us/articles/29772348346900-AI-Avatars
- Animaker Feature / Animation Maker / Lip Sync: https://www.animaker.com/features
- Powtoon Animation Maker / AI Video: https://www.powtoon.com/
- Renderforest Animation Maker: https://www.renderforest.com/animation-maker
- InVideo AI / Kapwing AI Video Generator: https://invideo.io/ai/ 与 https://www.kapwing.com/ai-video-generator

### 平台能力矩阵

| 平台类型 | 代表平台 | 强项 | 弱项 | 本平台应借鉴 |
| --- | --- | --- | --- | --- |
| AI 视频生成工具 | Runway、Kling、Luma、Pika、PixVerse、Adobe Firefly | 文生视频、图生视频、参考图、关键帧、角色/场景一致性、镜头运动控制 | 多数不管理小说、章节、剧情、实体关系；长篇连续剧集管理弱 | 参考资产锁定、多图参考、关键帧、镜头运动参数、生成质量检查、批量重生成 |
| 在线动画制作平台 | Vyond、Animaker、Powtoon、Renderforest | 角色库、场景库、道具库、模板、拖拽编辑、配音、字幕、品牌素材、团队协作 | AI 原生长篇故事理解弱；角色一致性多依赖模板资产 | 预制角色/场景/镜头模板、低门槛向导、时间线编辑器、字幕/配音工作台 |
| 通用视频编辑与发布 | Canva、Kapwing、InVideo | 模板、素材库、字幕、音轨、封面、尺寸适配、社媒发布 | 动漫专业镜头语言和小说改编深度不足 | 封面/标题/标签、横竖屏适配、素材搜索、发布包生成 |
| 数字人/口播平台 | Vyond AI Avatars、HeyGen、Synthesia | 数字人、唇形同步、语音、多语言、品牌一致性 | 动漫分镜、场景调度、剧情镜头较弱 | 角色音色绑定、唇形/口型任务、对白分段和多语言字幕 |
| 本平台 | AI Video Platform | 小说/章节/Story Bible/实体/分镜/镜头的上游结构强，适合长篇动漫连续剧 | 真实渲染、Timeline、模板体系、批量生产、删除/归档和协作审核仍不完整 | 用“长篇叙事一致性 + AI 自动化生产线”形成差异化 |

### 制作流程对比

| 流程阶段 | 常见平台做法 | 本平台现状 | 缺口与优化 |
| --- | --- | --- | --- |
| 立项/项目配置 | 品牌包、画幅、模板、团队权限、素材库 | Project/ProjectMember 已有，项目风格已有雏形 | 增加项目创建向导、动漫类型预设、默认模型方案、权限模板 |
| 剧情输入 | 多数平台从 prompt 或脚本开始 | 支持小说、章节、导入、AI章节 | 增加“新手快速模式”：输入一句故事梗概即可生成小说大纲、角色、章节和首集分镜 |
| 剧本/分镜 | LTX/Runway 类强调 shot/storyboard；动画平台用模板场景 | 已有智能分镜模板和章节生成分镜 | 增加镜头模板库可视化、模板收藏、自定义模板、模板删除/归档 |
| 角色/场景/道具 | 动画平台有内置角色/场景/道具库；AI 平台用参考图 | StoryEntity、Asset、StoryBible 已有基础 | 增加实体审阅台、资产版本锁定、角色三视图/表情包/服装包 |
| 镜头参数 | AI 平台有镜头运动、关键帧、参考图；动画平台有动作/表情 | Shot 已有角度、运镜、情绪、光线、调色、keyframes | 增加中文参数库、参数预览、批量套用、AI 推荐镜头语言 |
| 参考图/一致性 | Runway/Kling/PixVerse 强调 references/elements/character consistency | PromptComposer/一致性上下文已有，尚未全链路强制 | 增加每个镜头的引用检查：角色资产、场景资产、道具资产缺失时阻断或自动生成 |
| 配音/口型 | Vyond/Animaker/HeyGen 注重 TTS、Lip Sync、多语言 | TTS 已有，口型/唇形未成体系 | 增加 dialogue review、角色音色锁定、口型同步任务、字幕自动切分 |
| 合成/剪辑 | Canva/Kapwing/InVideo 强在 timeline、字幕、音轨、导出 | 已有 manifest，真实渲染未完成 | 增加 FFmpeg/云剪辑渲染、Timeline UI、BGM/SFX轨、字幕烧录/外挂 |
| 发布/交付 | 常见平台支持下载、比例适配、标题封面、团队审阅 | Publication 有基础，前端发布弱 | 增加发布中心、版本管理、导出格式、社媒比例、审核流 |

## 可借鉴的动漫预制模板与参数库

### 题材模板

- 热血成长：训练、失败、突破、对战、胜利余韵。
- 悬疑揭示：异常开场、线索特写、误导、反转、危险升级。
- 恋爱日常：建立场景、双人互动、情绪停顿、内心独白、温柔收束。
- 奇幻冒险：世界观建立、目标出现、队伍集结、遭遇危机、进入下一章。
- 都市异能：普通生活、异常触发、能力显现、代价揭示、组织登场。
- 国风仙侠：山门/城镇、法器/灵力、师徒/门派关系、试炼、伏笔。
- 机甲科幻：基地、驾驶舱、警报、出击、战斗损伤、战略复盘。

### 分镜模板

- 建立镜头：远景/航拍/全景，交代地点、时间、氛围。
- 人物登场：中景到近景，锁定服装、脸部、标志性道具。
- 对话推进：双人镜头、过肩镜头、反应镜头、表情特写。
- 动作高潮：跟拍、推拉、手持、快速切换、道具/技能特写。
- 情绪停顿：静态近景、慢推、低饱和或柔光、留白。
- 线索揭示：极近景、焦点转移、道具高亮、环境音降低。
- 转场桥接：天空/门/窗/街道/背影/道具作为前后镜头过渡。

### 镜头参数库

- 镜头角度：远景、全景、中景、近景、特写、极特写、俯拍、仰拍、过肩、双人、航拍。
- 运镜方式：静止、慢推、拉远、横移、摇镜、跟拍、环绕、升降、手持、快速切换。
- 情绪：平静、紧张、悲伤、愤怒、惊讶、期待、恐惧、兴奋、释然。
- 光线：自然光、柔光、逆光、轮廓光、月光、霓虹、黄金时刻、强对比、阴影。
- 调色：电影感、暖色、冷色、低饱和、高饱和、复古、黑色电影、赛博霓虹、国风水墨。
- 音频：环境声、脚步声、衣料摩擦、风声、雨声、心跳、能量声、金属声、低频氛围。
- 字幕：对白字幕、旁白字幕、内心独白、注释字幕、多语言字幕。

### 模板管理要求

- 系统模板：内置、不可删除，但可复制为项目模板。
- 项目模板：支持新增、修改、删除、归档、复制、收藏、版本号。
- 模板适配：按小说题材、章节情绪、事件强度、角色数量、目标时长自动推荐。
- AI 辅助：AI 根据章节内容解释推荐原因，并生成可编辑的镜头初稿。

## AI 智能辅助能力规划

| 模块 | AI 辅助能力 | 人工介入点 |
| --- | --- | --- |
| 新手向导 | 一句话故事生成项目、题材、风格、章节大纲、核心角色 | 确认题材、目标时长、画风 |
| 小说导入 | 自动识别章节、摘要、人物、场景、道具、事件 | 合并章节、修正标题、确认实体 |
| Story Bible | 自动构建世界观、角色规则、场景规则、道具状态、事件线 | 审核冲突、锁定定稿 |
| 剧本改编 | 按章节自动改编脚本，保留前后逻辑 | 调整对白、节奏、旁白 |
| 分镜生成 | 自动匹配模板，生成镜头、视觉描述、镜头参数、音效提示 | 删除/新增镜头、调整镜头语言 |
| 参考资产 | 自动生成角色三视图、场景定稿、道具图、表情包 | 选择定稿版本、锁定资产 |
| 视频生成 | 自动组合 prompt、参考图、关键帧、模型参数，批量提交 | 失败重试、选择最佳版本 |
| 配音字幕 | 自动分角色配音、字幕切分、语速检查、多语言翻译 | 试听、重配、改字幕 |
| 合成发布 | 自动生成 Timeline、字幕、BGM/SFX、封面、标题简介 | 审核成片、导出格式、发布范围 |

## 降低使用门槛的产品设计

- 三种模式：极速模式、专业模式、团队制作模式。
- 极速模式：只输入小说或梗概，系统自动完成实体提取、Story Bible、分镜、参考图、配音、视频和成片草稿。
- 专业模式：开放全部镜头参数、模型选择、关键帧、资产版本、字幕和音轨。
- 团队制作模式：增加任务分工、审核状态、评论、版本回滚和发布审批。
- 页面文案应从“模型参数”优先转成“创作目标”：例如“更紧张”“更温暖”“更像热血番开场”，由系统映射到镜头参数。
- 每个步骤都提供“AI 帮我完成”“检查缺失项”“一键继续下一步”“撤销本次生成”。
- 对新用户提供样例项目：1 个短篇小说、3 个角色、1 个场景、1 套分镜、2 个镜头、1 条成片清单。

## 新增/修改/删除能力审计

### 后端已具备删除能力

- Novel、Chapter、Character、Script、Storyboard、Shot。
- StoryBible、Asset、Project、ProjectMember。
- Workflow、ImageJob、TTSJob、SynthesisJob。
- Timeline、Track、Clip。
- LLMConfig。

### 后端缺失或不完整

- VideoJob：有创建、查询、刷新，但没有删除、取消、归档、批量删除。
- NovelImportJob：有预览、确认、查询，但没有删除、取消、重试、清理临时文件。
- Publication：有创建发布记录，但缺列表、详情、更新、删除、撤回发布。
- StoryEntity：有模型和抽取落库，但缺实体 CRUD、合并、删除、恢复、关系编辑。
- StoryboardTemplate：目前主要是内置模板列表/匹配，缺自定义模板 CRUD、删除、归档、版本管理。
- ExternalAPIConfig：有创建/列表，缺更新、删除、测试、设默认的完整闭环；与 LLMConfig 存在职责重叠。
- Activity/UsageLog：通常不物理删除，但需要按项目/用户保留策略和管理员清理策略。

### 前端删除入口不完整

- 已有删除入口：小说、章节、角色、剧本、镜头、LLM配置、团队成员。
- 不完整：任务中心有删除图标但缺实际处理函数；视频任务、图像任务、TTS任务、合成任务删除入口需要按任务类型调用后端。
- 不完整：分镜管理页可删除镜头，但缺删除整个分镜的入口；后端已有 `DELETE /storyboards/{id}`。
- 不完整：资产库、Story Bible、StoryEntity、Workflow、Timeline、Publication 缺稳定的前端删除/归档入口。
- 删除体验要求：生产对象默认软删除/归档，支持恢复；危险删除需要二次确认并提示影响范围。

## 竞品对标后的新增优化清单

### P0

1. 新手极速向导：输入小说/梗概后自动创建项目、章节、实体、Story Bible、分镜、镜头和成片草稿。
2. StoryEntity 管理台：角色、场景、道具、事件统一新增、修改、删除、合并、关系编辑。
3. 自定义模板库：题材模板、分镜模板、镜头模板、字幕模板支持项目级 CRUD。
4. 任务中心 CRUD：视频/图片/TTS/合成任务支持删除、取消、重试、批量操作。
5. 发布中心 CRUD：Publication 支持列表、详情、更新、撤回、删除、重新导出。
6. 真实成片渲染：manifest 接入 FFmpeg/云剪辑，产出可下载 mp4 和字幕文件。

### P1

1. Timeline 可视化编辑器：视频轨、对白轨、BGM轨、SFX轨、字幕轨。
2. 资产版本锁定：角色三视图、表情、服装、场景、道具定稿图与镜头绑定。
3. 关键帧编辑：每个镜头支持开始/结束图、关键帧提示词、运动强度。
4. 批量生成与质量检查：缺资产、缺字幕、音画时长不匹配、失败镜头自动重试。
5. 模型方案预设：极速省钱、质量优先、国产模型、海外模型、离线/本地合成。

### P2

1. 团队审核流：待生成、待审阅、需修改、已锁定、已发布。
2. 社媒发布包：16:9、9:16、1:1、封面、标题、简介、标签、多语言字幕。
3. 模板市场：公共模板、项目模板、个人收藏、复用次数和评分。
4. 教程与样例：内置示例项目、步骤 checklist、悬浮帮助、失败原因解释。
5. 成本预算与配额：每章预计图片/视频/TTS费用，生成前预算提示。

## 推荐实施顺序

1. 先修阻断性页面/API 问题：章节详情参数、小说封面接口缺失或入口隐藏、TTS 状态值、团队静态数据。
2. 做小说导入和章节结构，因为这是所有后续生产的输入根。
3. 做实体抽取、Story Bible 自动构建、资产定稿，先解决一致性权威来源。
4. 改造剧本/分镜/镜头生成，让 PromptComposer 和任务默认模型贯穿。
5. 做权限角色和项目归属，避免越往后补成本越高。
6. 做真实合成/导出/发布，完成从素材生成到最终作品的闭环。
7. 最后补质量检查、批量任务、Timeline 和运营体验。

## 验证标准

- 后端单测覆盖：导入、实体抽取 schema、Story Bible 同步、权限、模型解析、合成导出。
- 前端 E2E 覆盖：真实页面操作完成“导入小说 -> 抽取实体 -> 确认 Story Bible -> 生成资产 -> 章节转分镜 -> 镜头参考图 -> 配音 -> 视频 -> 合成 -> 发布”。
- 无 API Key 环境：DEV_MODE 能跑完整流程，并明确标注本地生成。
- 有 API Key 环境：每类模型至少有一次真实调用 smoke test，失败原因要能在任务中心看到。
- 权限验证：owner/editor/viewer/非成员四类用户分别跑关键 API。

---

## 2026-05-13 动漫制作平台与插件生态再对标

### 对标资料

- OpenAI Sora 2: https://openai.com/index/sora-2/ 与 https://help.openai.com/en/articles/12456897
- Google Veo 3: https://blog.google/technology/ai/generative-media-models-io-2025/ 与 https://cloud.google.com/blog/products/ai-machine-learning/announcing-veo-3-imagen-4-and-lyria-2-on-vertex-ai
- Runway Gen-4 References: https://help.runwayml.com/hc/en-us/articles/40042718905875-Gen-4-Image-References-Guide
- Canva AI Video Generator: https://www.canva.com/features/ai-video-generator/
- Toon Boom Harmony: https://www.toonboom.com/products/harmony
- Clip Studio Paint Animation: https://www.clipstudio.net/en/animation/
- Blender Grease Pencil: https://docs.blender.org/manual/en/latest/grease_pencil/introduction.html
- Live2D Cubism Lip-sync: https://docs.live2d.com/4.2/en/cubism-sdk-manual/lipsync/
- ComfyUI Docs: https://docs.comfy.org/index 与 https://docs.comfy.org/development/core-concepts/workflow
- ControlNet: https://github.com/lllyasviel/controlnet
- AnimateDiff: https://github.com/guoyww/animatediff/

### 新趋势

1. 直接音视频生成成为基础能力。Sora 2、Veo 3、Canva/Veo 类入口都已经把对白、音效、环境声或音乐纳入单次视频生成结果。本平台不能只支持“先视频、再 TTS、再合成”，必须支持 `shot_audio_video` 直生任务。
2. 角色和场景一致性依赖参考资产，而不是只依赖 prompt。Runway、Kling、PixVerse 等平台都把参考图、多元素、关键帧、角色一致性作为核心卖点。本平台已有 Story Bible 和实体链路，下一步要把资产版本锁定到每个 Shot/MediaJob。
3. 专业动漫生产仍围绕时间线和可编辑资产。Toon Boom、Clip Studio、Live2D、Blender 的共同点是分镜、cel/rig、口型、轨道、合成和项目文件。本平台的最终产物不应只有 job 列表，而应有可编辑 timeline、字幕轨和资产依赖图。
4. 插件生态强调可组合工作流。ComfyUI、ControlNet、IP-Adapter、AnimateDiff 的价值在于可控节点、模板复用和本地/云端混合执行。本平台应把插件当成 provider/workflow adapter 接入，而不是把所有能力硬编码进端点。

### 当前工程差距

| 能力 | 当前工程 | 生产级缺口 |
| --- | --- | --- |
| 直生音视频 | 无 `shot_audio_video` 任务；视频和 TTS 是分离任务 | 需要一次任务可返回视频、音频、字幕、音画同步元数据和完整 lineage |
| 模型能力注册 | 有 `shot_video/tts_dialogue/final_synthesis` | 缺 `text_to_audio_video/image_to_audio_video/lip_sync/sound_effect/subtitle_generation` 能力矩阵 |
| 字幕 | `Shot.extra_data.subtitle_text`、workflow segment subtitle、SRT artifact | 缺 `SubtitleTrack/SubtitleSegment`、多语言、说话人、审阅状态、时间码编辑和导出版本 |
| 时间线 | 有 Timeline/Track/Clip 模型；workflow 可导出 EDL JSON | 缺从 workflow manifest 自动落库 timeline clips，缺前端可视化字幕/音频轨编辑 |
| 插件 | 没有独立插件/工作流适配层 | 缺 ComfyUI JSON、ControlNet/IP-Adapter/AnimateDiff 参数映射和本地 runner 配置 |
| 前端体验 | 视频页显示上下文，workflow 页显示 SRT/render artifact | 缺直生/分步模式切换、字幕编辑器、批量生成控制台、失败降级提示 |

## 目标架构：直接音视频生成 + 字幕一等公民

### 数据模型

P0 推荐采用兼容式演进，避免一次性迁移所有历史任务：

- 新增 `MediaGenerationJob`，或先在 `VideoJob.extra_data` 兼容以下字段，再在 P1 迁移为独立表：
  - `task_type`: `shot_video`、`shot_audio_video`、`dialogue_video`、`lip_sync_video`、`music_video`、`final_render`。
  - `media_type`: `video`、`audio`、`audio_video`、`subtitle`、`timeline`、`render_package`。
  - `lineage`: `project_id/workflow_id/novel_id/chapter_id/script_id/storyboard_id/shot_id`。
  - `provider_id/model_id/capabilities/provider_task_id`。
  - `input_assets`: 角色、场景、道具、关键帧、参考图、音频、字幕草稿的 asset/version 锁。
  - `output_video_url/output_audio_url/output_manifest_url/subtitle_track_id/timeline_id`。
  - `seed/style_lock/quality_report/retry_of/variant_group_id`。

- 新增 `SubtitleTrack`：
  - `id/user_id/project_id/workflow_id/novel_id/chapter_id/script_id/storyboard_id/language/kind/status/source/export_urls`。
  - `kind`: `dialogue`、`narration`、`lyrics`、`annotation`、`translation`。
  - `source`: `shot_dialogue`、`tts_segments`、`direct_av_model`、`asr`、`manual`。

- 新增 `SubtitleSegment`：
  - `track_id/shot_id/speaker_entity_id/start_seconds/end_seconds/text/original_text/confidence/review_status/style/metadata`。
  - 支持按 shot 重排后自动重算时间码，支持 SRT/VTT/ASS 导出和烧录参数。

### API 契约

- `POST /api/v1/media/generate`
  - 输入：`task_type`、完整 lineage、prompt、reference_asset_ids、subtitle_mode、audio_mode、provider/model、seed、duration、resolution。
  - 输出：统一 `MediaGenerationJob`；直生音视频任务必须返回 `output_video_url`，可选 `output_audio_url`、`subtitle_track_id`、`provider_audio_metadata`。

- `GET /api/v1/media/jobs`
  - 支持按 `media_type/task_type/novel_id/chapter_id/storyboard_id/shot_id/workflow_id/status` 过滤。

- `POST /api/v1/subtitles/from-shot`
  - 从 Shot dialogue、narration、TTS segments 生成可编辑字幕轨。

- `POST /api/v1/subtitles/from-media`
  - 从直接音视频模型返回的对白/ASR/时间戳生成字幕轨。

- `PUT /api/v1/subtitles/{track_id}/segments/{segment_id}`
  - 编辑文本、说话人、时间码、审阅状态。

- `POST /api/v1/subtitles/{track_id}/export`
  - 导出 SRT/VTT/ASS，并返回 artifact URL。

- `POST /api/v1/workflow/{workflow_id}/generate-media-batch`
  - 按镜头批量生成缺失媒体；策略可选 `direct_av_first`、`separate_video_tts`、`video_only`、`tts_only`。

### Provider capability registry

模型注册表需要从“默认模型列表”升级为能力矩阵：

| 能力 | 含义 | 用于 |
| --- | --- | --- |
| `text_to_audio_video` | 文本一次生成带音频视频 | Sora/Veo 类直生镜头 |
| `image_to_audio_video` | 参考图生成带音频视频 | 角色/场景已锁定的镜头 |
| `text_to_video` / `image_to_video` | 静音视频 | 火山 Seedance 等现有路径 |
| `dialogue_tts` | 多角色配音 | 分步生成与补配音 |
| `sound_effect_generation` | 音效生成 | SFX 轨 |
| `music_generation` | BGM/主题音乐 | BGM 轨 |
| `lip_sync` | 音频驱动口型/画面 | 角色对白镜头 |
| `subtitle_timing` | 字幕时间码生成/对齐 | 字幕轨 |
| `audio_video_mux` | 音视频封装/混音 | FFmpeg/云剪辑 |
| `subtitle_burn_in` | 字幕烧录 | 最终导出 |

## 分阶段优化计划

### P0：让直生音视频和字幕可用

1. 数据契约补齐
   - 增加 `MediaGenerationJob` 或 `VideoJob.extra_data` 兼容层。
   - 增加 `SubtitleTrack/SubtitleSegment`。
   - 为 `init_db.py` 增加 SQLite 兼容迁移。
   - 验收：旧视频/TTS/合成历史仍可读，新任务能保存音频、字幕、lineage 和 provider capability。

2. 直生音视频后端入口
   - 增加 `shot_audio_video` 任务类型。
   - DEV_MODE 生成本地可播放 MP4、音频元数据、字幕轨和 SRT。
   - 有 API Key 时按 provider capability 路由到 Sora/Veo 类模型；无能力则降级到 `shot_video + tts_dialogue + synthesis`。
   - 验收：同一 shot 生成出的音视频任务可在任务历史、workflow 和字幕页追踪。

3. 字幕工作台
   - 从 Shot/TTS/direct AV/ASR 生成字幕段。
   - 前端支持编辑文本、说话人、时间码、审阅状态，导出 SRT/VTT/ASS。
   - 验收：用户能修改字幕后重新生成 render package，workflow 导出使用最新字幕轨。

4. Workflow 批量媒体生成
   - 对每个 shot 检查视频、音频、字幕、角色资产、场景资产、seed。
   - 支持 `direct_av_first` 和 `separate_video_tts` 两种策略。
   - 验收：首集 workflow 可以一键生成“带字幕音视频草稿”，失败镜头可单独重试。

5. 前端入口
   - 视频生成页增加“直生音视频/分步生成”切换。
   - 极速向导增加“生成首集音视频草稿”选项，先展示预检、成本和预计耗时。
   - Workflow 页面增加媒体批量生成、字幕轨状态、音频状态和降级策略展示。
   - 验收：无密钥 DEV_MODE 下用户能从章节镜头生成带字幕的本地草稿；有密钥时能选择直生模型。

### P1：生产质量和插件化

1. ComfyUI 工作流适配
   - 支持导入 ComfyUI workflow JSON，声明输入占位符：角色参考图、场景图、pose/depth/canny、prompt、seed、输出节点。
   - 映射 ControlNet/IP-Adapter/AnimateDiff 参数到 Shot controls。
   - 验收：一个项目模板可以调用本地 ComfyUI 生成参考图或短视频，并把输出回写 Asset/Shot。

2. 时间线可视化编辑
   - 将 workflow manifest 自动落库为 Timeline/Track/Clip。
   - 前端展示视频轨、对白轨、BGM、SFX、字幕轨。
   - 验收：用户能拖动字幕/音频/视频片段并重新导出 render package。
   - 2026-05-14 已落地最小产品化闭环：workflow manifest 可同步为 Timeline/Track/Clip；`/timelines` 工作台可按项目查看轨道和片段，编辑片段名称、起始时间、时长、字幕文本，新增字幕片段，锁定/静音轨道；workflow 渲染预检和渲染包默认消费最新可编辑 Timeline，SRT/EDL/HTML 预览会使用用户修改后的字幕和时间码。后续仍需补拖拽、多选、BGM/SFX 资源库和真实转码器按 Timeline 执行。

3. 口型和角色表演
   - 增加 `lip_sync_video` 任务，支持 Live2D/Rhubarb/供应商 lip-sync。
   - 为角色维护 viseme/mouth shape 或 Live2D 参数映射。
   - 验收：对白镜头可按音频驱动口型，并保留字幕和说话人关联。

4. 资产版本锁定和质量检查
   - 每个 MediaJob 写入 asset version locks。
   - 生成前检查缺角色图、缺场景图、字幕为空、音画时长差、风格不一致。
   - 验收：预检失败不进入批量生成，用户能一键补齐缺失资产。
   - 2026-05-14 已落地最小闭环：Shot 支持单个/批量质量重检、预算估算、质量/审核筛选和批量审核状态流转；实体库支持按小说展示生产资料包、资产需求、一致性检查、属性 JSON、版本快照/恢复；镜头生产上下文支持绑定 StoryEntity 并保存实体类型、视觉 DNA 和资产包。后续继续补资产一键生成和失败自动重试。

### P2：团队化和生态化

1. 插件市场/模板市场：发布项目级和公共 ComfyUI/字幕/镜头/音效模板。
2. 多语言字幕和配音：翻译、重配、双语字幕、语言版本发布包。
3. 审核流：导演审、角色一致性审、字幕审、成片审，支持评论和版本回滚。
4. 成本与配额：按镜头估算直生音视频、分步生成、渲染成本，支持预算上限。

### 2026-05-14 P1/P2 进展

- 镜头质量检查已从单镜头编辑面板扩展为列表级生产准入：支持质量状态和审核状态筛选、卡片徽标、风险摘要、预算提示。
- 新增批量质量重检接口和前端批量重检入口，可把历史镜头或未检查镜头补齐 `quality_report/budget_estimate`。
- 多人审核流先落地最小可用操作：批量通过、退回修改，并同步刷新质量建议；评论、版本回滚和角色/字幕/成片分角色审核仍在后续 P2。
- Timeline 已从 artifact 展示推进到可编辑数据库资产：workflow 页面能生成/重建可编辑时间线，工具菜单提供“时间线编辑”入口，字幕轨可新增和修改；渲染包默认使用最新 Timeline 产出 SRT/EDL/HTML 预览。真实拖拽编辑、字幕烧录执行器、团队审阅仍在后续 P1/P2。

## 新验收路径

最小可验收路径应改为：

`Novel -> Chapter -> Story Bible -> StoryEntity -> Storyboard -> Shot -> SubtitleTrack -> MediaGenerationJob(shot_audio_video 或 shot_video+tts) -> Timeline -> RenderPackage -> Publication`

每个产物必须满足：

- 可追踪：有完整 lineage 和 source job。
- 可复现：有 provider/model/seed/prompt_version/asset_version_locks。
- 可编辑：字幕、音频、视频片段能进入 timeline 或字幕工作台。
- 可降级：直生音视频不可用时自动拆分为视频、TTS、合成。
- 可验证：DEV_MODE、无密钥、单测和前端 E2E 都能跑通。

---

## 2026-05-26 深入分析：从首集闭环升级为整部小说动画漫剧生产平台

### 目标重新定义

平台最终目标不是单点“视频生成”，而是让非专业创作者通过小说导入或小说编辑，低门槛完成整部小说的连续动画漫剧生产。核心产物应从单个视频任务升级为“连续剧集工程”：

`Novel -> Series Plan -> Episode Plan -> Story Bible/State Machine -> Entity/Asset Packages -> Script -> Storyboard -> Shot Contracts -> Media Jobs -> Subtitle/Timeline -> Render/Publication`

其中剧情、人物、环境、事件、道具、配音、视觉形象、字幕和模型配置都必须可追踪、可复现、可审阅、可回滚。

### 当前已具备的基础

| 领域 | 当前能力 | 判断 |
| --- | --- | --- |
| 小说与章节 | 支持小说创建、导入预览/确认、章节 CRUD、章节 AI 生成/润色、前后文连续性上下文 | 已具备基础输入和章节编辑能力 |
| Story Bible 与实体 | 已有 Story Bible、StoryEntity、实体抽取、实体统计、生产资料包、一致性检查 | 已有一致性底座，但状态机还不够强 |
| 资产库 | 已有角色/场景/道具/模板/提示词等资产管理，支持全局/小说/章节/剧本/实体范围 | 已有资产库，但资产版本锁和定稿包仍需强化 |
| 剧本/分镜/镜头 | 支持章节生成剧本、智能分镜、镜头 CRUD、镜头质量检查、Production Contract | 已能生成首集/单章节制作链路 |
| 音视频/字幕/合成 | 支持静音视频、直生音视频、TTS、字幕轨、Timeline、workflow render package、Publication 基础 | DEV_MODE 和本地 artifact 闭环较完整，真实生产渲染仍需强化 |
| 模型配置 | 已有多 provider、多能力默认模型、验证状态、模型选择组件、Agent Plan/Seedance 等模型目录 | 基础可用，仍需任务级模型路由解释和批量策略 |
| 前端入口 | 已有极速向导、作品、剧本、分镜、工作流、视频生成、生产适配、实体库、资产库、字幕、时间线、分析、设置 | 功能丰富，但对非专业用户仍偏复杂 |
| 权限与设置 | 已有登录、密码找回、项目成员、设置、数据分析 | 基础具备，仍需资源级权限全链路收敛 |

### 关键差距

1. 当前更像“首集/单章节制作闭环”，还不是“整部小说多集生产管理”。
   - 缺 Series/Episode 层，把整部小说拆成多集、每集目标时长、剧情钩子、承接关系、生产状态统一管理。
   - Quick Start 能做首集工程，但不能把整部小说按章节批量规划成连续剧集。

2. 一致性底座已有，但还不是强状态机。
   - Story Bible/StoryEntity 能记录人物、场景、道具、事件，但角色服装/伤势/关系、道具持有人/状态、场景天气/时间、事件因果还没有统一的状态版本。
   - 生成前检查更多是提示和合约，还需要升级为“阻断/警告/自动修复建议”。

3. AI 辅助分散在多个页面，缺少统一的“AI 制片助手”。
   - 小说、章节、剧本、分镜、实体、视频都有 AI 能力，但用户仍需要理解每个专业环节。
   - 需要一个总控代理按生产阶段自动判断下一步：缺实体则抽取，缺资产则生成，缺字幕则补齐，失败则重试或降级。

4. 资产一致性仍需从“可管理”升级到“生成前必锁定”。
   - 角色多视图、表情、服装、声线、场景参考、道具 DNA 应成为每个 Shot 的版本锁输入。
   - 已生成镜头必须保留当时的资产版本，后续资产更新不能隐式影响历史镜头。

5. 真实生产能力还需要更清晰的分层。
   - DEV_MODE、本地 artifact、外部适配 payload、真实供应商结果需要在 UI 和任务状态里明确区分。
   - 视频、图片过几天不可播放的问题，本质上需要统一媒体持久化、可恢复 URL、过期外链转存和缺失文件巡检。

6. 前端功能入口齐全，但非专业用户路径仍需要简化。
   - 顶部菜单已经覆盖很多页面，但普通用户真正需要的是“继续制作”“一键补齐”“生成下一集”“检查问题”“导出发布”。
   - 专业工具应保留，但默认操作面应更像生产看板，而不是让用户在多个管理页之间跳转。

## 下一阶段优化路线图

### P0：整部小说到连续剧集生产闭环

1. 新增“整书生产计划 / Series Plan”
   - 输入：小说或导入任务。
   - AI 输出：章节拆分、集数建议、每集覆盖章节、每集 30-90 秒短视频目标、钩子、冲突、反转、结尾悬念、下一集承接。
   - 数据建议：先复用现有 Workflow metadata 或新增轻量 `EpisodePlan`/`SeriesPlan` 表。
   - 前端入口：小说详情页和极速向导增加“生成整部漫剧计划”。
   - 验收：一本小说可生成多集生产看板，每集有状态、时长、剧情目标和下一步动作。

2. 升级“一键生产”从首集扩展到多集批量
   - 支持选择：生成第 1 集、生成选中章节、批量生成前 N 集、继续未完成集。
   - 每集自动执行：Story Bible 同步、实体抽取、资产缺口检查、剧本、分镜、镜头、字幕、音视频草稿、渲染包。
   - 提供可暂停、可恢复、可跳过、可重试的 Job Orchestrator。
   - 验收：用户不用理解剧本/分镜/镜头，也能得到每集可审阅草片。

3. Story Bible 状态机
   - 增加状态维度：角色状态、服装状态、关系状态、道具流转、场景时间/天气/空间、事件因果。
   - 每次章节、剧本、分镜、镜头生成都读取并写回状态变更。
   - 生成前做一致性预检：角色形象冲突、道具状态跳变、事件提前发生、场景天气/时间矛盾、对白不符合人物。
   - 验收：中间章节生成不会引用后续事件；道具和人物状态能跨集继承。

4. 资产定稿包与版本锁
   - 角色包：正面/侧面/全身/表情/服装/声线/口吻。
   - 场景包：空间结构、光照、天气、关键机位。
   - 道具包：材质、形状、标记、持有人、状态流转。
   - 每个 Shot 写入 `asset_version_locks`，MediaJob 保留生成时引用资产版本。
   - 验收：重生成某个镜头时默认复用同一资产版本；资产更新需用户确认是否影响后续镜头。

5. 媒体持久化与历史可播放
   - 所有图片、音频、视频、字幕、渲染包统一进入 Media Persistence。
   - 外部临时 URL 自动转存为本地或对象存储；历史任务使用持久 URL。
   - 增加媒体巡检：文件缺失、外链过期、缩略图丢失、字幕 artifact 缺失。
   - 验收：生成几天后，历史视频、封面、角色图、字幕仍可播放/下载/预览。

6. AI 制片助手
   - 前端提供一个“AI 帮我继续”入口，基于当前工程状态自动建议下一步。
   - 输出结构化操作计划：将读取哪些上下文、使用哪个模型、预计生成哪些产物、可能成本和风险。
   - 每个长任务展示阶段反馈：读取上下文、生成、保存、同步实体、检查一致性、生成资产、渲染。
   - 验收：异常时展示具体失败阶段和恢复建议，不再只是“生成失败”。

### P1：生产质量与专业控制

1. 多模型路由策略
   - 文本：长篇拆解、剧本、分镜、对白、润色。
   - 图像：封面、角色定稿、场景参考、道具 DNA。
   - 视频：静音视频、直生音视频、图生视频、关键镜头高质量模型。
   - 音频：角色 TTS、音效、BGM、口型同步。
   - 合成：本地 FFmpeg、云渲染、字幕烧录。
   - 验收：每个任务都能解释“为什么用这个模型”，并支持按成本/质量/速度切换策略。

2. 生成后差异检查
   - 对视频/图片结果做 AI 或规则检测：是否出现错误人物、服装不一致、道具消失、字幕缺失、时长不符。
   - 结果进入质量报告，支持一键重生或人工接受。
   - 验收：批量生产后有可量化质量面板。

3. 时间线与字幕生产化
   - Timeline 支持多轨：视频、对白、音效、BGM、字幕。
   - 字幕支持逐句审阅、角色说话人、翻译、多语言、ASS 样式。
   - 渲染支持外挂字幕和烧录字幕。
   - 验收：一集视频可从可编辑 Timeline 重新导出。

4. 审核流
   - 角色审核、剧本审核、分镜审核、字幕审核、成片审核。
   - 支持通过、退回修改、评论、版本快照。
   - 验收：小团队可以分工协作，不覆盖彼此修改。

5. 真实生产适配
   - Sora/Veo/Seedance/ComfyUI/FFmpeg Cloud 统一通过生产适配管理配置。
   - 区分 `dev_artifact`、`adapter_ready`、`cloud_pending`、`rendered`、`failed`。
   - 验收：配置通过的外部能力能在 workflow 和视频生成页被明确选择和调用。

### P2：模板化、团队化和商业化

1. 题材生产模板
   - 红果短剧式、都市异能、玄幻逆袭、校园恋爱、悬疑反转、机甲科幻等。
   - 每个模板包含集结构、镜头节奏、对白风格、角色 archetype、封面/标题风格。

2. AI 教程式引导
   - 页面上减少专业术语，默认展示“下一步要做什么”。
   - 专业参数折叠到高级模式。
   - 每个页面保留“一键补齐缺失项”。

3. 成本与配额
   - 按集估算：文本 token、图片张数、视频秒数、TTS 字数、渲染资源。
   - 支持预算上限、低成本草稿模式、高质量定稿模式。

4. 数据分析与资产复用
   - 统计每部小说、每集、每个模型、每类资产的成功率、成本、失败原因。
   - 复用全局角色/场景/道具/模板，提高个人和小团队生产效率。

## 前端信息架构优化建议

保留现有专业页面，但默认入口应聚焦 5 个任务区：

1. 首页/控制台：继续制作、待处理问题、最近工程、成本/失败提示。
2. 整书生产：导入小说、章节拆分、生成剧集计划、批量生产。
3. 一致性中心：Story Bible、实体、资产定稿包、状态机、问题检查。
4. 生产工作台：按集执行剧本、分镜、镜头、音视频、字幕、渲染。
5. 配置与交付：模型、生产适配、团队权限、发布导出、数据分析。

默认面向非专业用户展示“极速模式”：

- 导入小说
- AI 生成整部漫剧计划
- 选择第 1 集或批量前 3 集
- AI 自动补齐实体和资产
- 生成草片
- 审阅问题
- 导出/发布

专业用户再进入“标准/专业模式”编辑角色、资产、分镜、镜头、字幕、时间线和模型参数。

## 新验收标准

1. 导入一本 20 章小说后，系统能自动生成整书剧集规划。
2. 用户选择任意一集，能一键生成剧本、分镜、镜头、字幕和带音视频草片。
3. 每个镜头都能追溯小说、章节、剧本、分镜、人物、场景、道具、事件、资产版本和模型配置。
4. 角色形象、服装、声线、道具状态和事件因果能跨集继承。
5. 生成失败有阶段、原因和重试/降级方案。
6. 历史图片、视频、字幕和渲染包不会因外链过期而不可用。
7. 非专业用户不需要理解所有专业页面，也能通过“AI 帮我继续”完成首集和后续剧集。
8. 生产环境下无模拟数据伪装真实结果；DEV_MODE、本地 artifact、真实云生成必须明确标识。
