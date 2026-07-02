# 工程发现

## 当前能力

- 后端已有 novels、chapters、characters、scripts、storyboards、shots、video、tts、synthesis、workflow、images、assets、projects、timelines、storyboard_ai 等模块文件。
- 前端已有 workflow、video-generation、characters、storyboards、shots、tts、synthesis 等页面。
- `VideoGenerateRequest` 已支持 `novel_id/script_id/storyboard_id/shot_id`，并在 `extra_data` 存储关联标题。

## 高优先级问题

- `backend/app/api/v1/router.py` 未挂载 `workflow/images/assets/projects/timelines/storyboard_ai`，但前端和 api-client 已调用这些路径。
- `frontend/src/lib/api-client.ts` 的 `generateSynthesis` 调用 `/synthesis/generate`，后端实际是 `/synthesis/create`。
- `backend/app/models/synthesis_job.py` 使用 `video_url/audio_url` 字段，`backend/app/api/v1/endpoints/synthesis.py` 的请求/响应仍使用旧的 `video_job_id/tts_job_id` 字段，会导致构造模型失败或响应模型不匹配。
- `backend/app/api/v1/endpoints/workflow.py` 返回 `WorkflowDetailResponse` 时混用 `metadata_` 和 `metadata`，容易触发 Pydantic 字段错误。
- workflow status 返回的视频/TTS任务缺少关联字段，前端按 `novel_id/script_id` 过滤无效。
- `backend/app/core/model_defaults.py` 注释和常量包含明文 API Key，不应保留在代码中。

## 本轮已处理

- 主路由已挂载 workflow/images/assets/projects/timelines/storyboard-ai。
- synthesis 支持 `/create` 记录创建和 `/generate` 兼容即时合成调用。
- TTS 支持新字段 `text_content/voice_model/api_provider`，并兼容旧字段 `text/api_key/voice`。
- TTS 和视频生成状态会回写到 Shot 的 `audio_*` / `video_*` 字段。
- 角色创建接口返回 `CharacterResponse`，新建后可继续生成头像。
- 移除核心配置和 SDK 测试脚本中的明文 Key。

## 一致性缺口

- 缺顶层 Project/StoryBible 作为人物、场景、道具、事件、风格的权威来源。
- 角色、场景、道具资产未被统一注入到分镜、图像、视频、TTS prompt。
- 生成结果未稳定回写 Shot，导致镜头不是全流程生产中枢。

## 2026-05-09 复核

- 后端阻断路由和 TTS/Video/Synthesis 契约已有一轮修复，但完整路线图的统一模型注册表、Story Bible、Prompt Composer、任务与 workflow 绑定尚未落地。
- 前端当前明确的类型失败是 `AuthResponse` 缺少 FastAPI 错误响应常见的 `detail` 字段。
- 现有 `LLMProvider/LLMModel/LLMConfig` 可以继续作为用户密钥与数据库种子结构；本轮更适合新增轻量 `model_registry.py` 作为权威运行时规划，避免大迁移。
- `VideoJob` 缺少直接列级 `project_id/workflow_id/novel_id/...`，已有 lineage 存在 `extra_data`；本轮可先新增 `project_id/workflow_id` 列并保持其他 lineage 兼容 `extra_data`。

## 2026-05-09 完成项

- 新增统一模型注册表，覆盖 `text/image/video/audio/local_synthesis` 和 `novel_generation/script_generation/storyboard_generation/character_image/scene_reference_image/shot_video/tts_dialogue/final_synthesis` 任务默认模型。
- 新增 Story Bible 数据模型、CRUD API 和 Prompt Composer，可把故事风格、世界观、角色规则、场景规则、道具规则、事件时间线、角色与镜头上下文组合成稳定 prompt。
- `VideoJob/TTSJob/SynthesisJob` 增加 `project_id/workflow_id`，生成接口接收并返回这些字段，workflow 状态优先返回当前 workflow 绑定任务。
- 全量 pytest 中真实云 SDK 测试和外部 localhost 集成测试改为环境缺失时跳过，本地核心 API/服务测试保持通过。

## 2026-05-09 深度审计初步发现

- `frontend/src/app/llm-config/page.tsx` 在 API 测试失败时会回退“模拟测试成功”，这会让用户误以为 Key 已验证。
- `frontend/src/app/scripts/page.tsx` 的 AI 剧本生成失败后会使用模拟生成结果，实际 LLM 失败不会被明确暴露。
- `frontend/src/app/novels/new/page.tsx` 的 AI 生成仍是前端本地模拟，没有接入后端生成链路。
- `frontend/src/app/jobs/page.tsx` 使用模拟任务数据，不是后端真实 job 聚合。
- `frontend/src/app/settings/profile/page.tsx` 在用户信息接口不可用时显示“示例用户”，会掩盖 auth/profile 契约问题。
- `backend/app/api/v1/endpoints/workflow.py` 的视频拼接仍是 tracked placeholder，未做真实多片段拼接、混音、字幕或导出。
- `backend/app/api/v1/endpoints/synthesis.py` 的 `/create` 只是创建记录；真实转码/混音只存在不确定的 provider hook。
- `backend/app/services/openai_service.py` 视频生成是占位并抛 `NotImplementedError`。
- 自动化测试覆盖集中在后端核心 API；前端 E2E 文件存在，但已有 test-results 显示小说详情、剧本创建、分镜创建曾失败，需要重新验证。

## 2026-05-09 服务可用性验证

- 已启动真实后端 `uvicorn main:app --host 127.0.0.1 --port 8000` 和前端 `npm run dev`，服务均可启动。
- 真实 API smoke 通过：`Novel -> Chapter -> Character -> Script -> Storyboard -> Shot -> StoryBible -> compose-prompt -> Workflow -> LLM registry` 全部返回 2xx。
- 不带登录态跑 `frontend/e2e/app.spec.ts`：16 个页面冒烟测试中 8 个失败，失败页面都被重定向到登录页；这是 E2E 未初始化认证状态，不代表业务页无法渲染。
- 带 DEV token 的页面审计通过：`/novels`、`/scripts`、`/characters`、`/storyboards`、`/shots`、`/video-generation`、`/tts`、`/synthesis`、`/workflow`、`/llm-config`、`/jobs`、`/dashboard` 均能渲染业务页面。
- 真实页面审计确认：`/video-generation` 显示未配置火山 API Key，不能执行真实视频生成；`/synthesis` 因没有真实视频/音频任务显示不可合成；`/jobs` 显示模拟任务数据。
- 在后端服务启动时重新跑 `pytest -q`，结果为 45 passed、1 skipped；其中 `test_api.py` 也跑过真实 localhost API，但该文件仍有返回 bool 的 pytest 警告，测试质量需要整理。
- 当前唯一 skipped 为真实火山视频 SDK 测试，需 `VOLCENGINE_API_KEY` 才能验证。

## 2026-05-10 小说到视频可用标准深度分析 - 后端模型与端点

- 现有后端已具备基础链路对象：Project、Novel、Chapter、Character、StoryBible、Storyboard、Shot、Asset、ImageJob、TTSJob、VideoJob、SynthesisJob、Workflow。
- 小说当前只支持手动创建、更新、AI生成；缺少外部小说导入接口，包括 TXT/Markdown/DOCX/EPUB/PDF 上传、章节切分、编码检测、重复章节处理、导入预览、导入任务状态、来源元数据和失败重试。
- Character 具备从小说/章节/文本抽取角色能力，并可尝试生成头像；但只覆盖角色，没有统一抽取 Scene/Prop/Event，且角色表没有 novel_id/project_id 归属、别名、关系、首次出现章节、状态变化、参考图资产版本等一致性字段。
- StoryBible 已有 style/worldview/character_rules/scene_rules/prop_rules/event_timeline，可作为一致性容器；但目前靠手工维护，缺少从小说/章节自动生成与增量更新，也缺少一致性校验结果、冲突状态、实体版本历史。
- Storyboard 生成从 Script 内容生成 Shots，但没有直接按 Novel/Chapter 生成分镜；生成时没有显式注入 StoryBible、角色、场景、道具、事件时间线，也没有把 sound_effect/music_mood/camera_movement 等完整写入 Shot 字段。
- Shot 模型有镜头、对白、视觉描述、运镜、情绪、光影、音效、角色引用、参考图、音频、视频字段，是生产中枢雏形；但缺少场景/道具/事件引用字段、生成批次/质量评分/审核状态、prompt版本和一致性检查结果。
- Asset 模型支持 character/scene/prop/costume/music/sfx/template/prompt，但没有从实体抽取自动创建资产、没有资产与 StoryBible 规则的双向同步、没有引用锁定策略和使用依赖图。
- PromptComposer 可组合 Project、StoryBible、Character、Shot，但当前未被 storyboards/shots/images/video/tts 主生成链路系统性使用，属于能力存在但未贯穿生产流程。
- Images 能按 shot_id/character_id 生成图，但请求只有 prompt/style，不会自动根据 StoryBible/角色/场景/道具组合提示词；DEV_MODE 可用，但真实云端依赖火山 Key。
- `novels.py` 只有 CRUD 和 `/generate`，没有 `UploadFile`、文件解析、导入任务或章节切分相关接口；`Novel.source` 只区分 manual/ai_generated，不能表达外部文件来源、导入版本和原始文件元数据。
- `chapters.py` 支持手动创建、更新、AI生成和重生成，但章节编辑后没有触发 StoryBible/实体库/分镜镜头的增量一致性校验，也没有“本章提取分镜/镜头”的直接后端入口。
- `characters.py` 的 `/extract` 只返回并保存 Character；提示词没有输出 entity_id、首次出现章节、别名、关系、状态变化、服装/道具绑定，也不会写入 StoryBible 或 Asset。
- 角色头像自动生成直接在角色抽取循环里调用火山图片生成，失败只追加错误但响应结构不暴露这些错误；也没有 ImageJob/Asset 记录和参考图版本锁定，无法为后续视频生成提供可追溯参考资产。
- `storyboards.py` 的 `/generate` 只接受 `script_id`，不支持 `novel_id/chapter_id` 直接生成分镜，也没有读取 StoryBible、角色表、资产库作为输入；生成 prompt 要求了 `camera_movement/sound_effect/music_mood`，但落库 SQL 只写 `prompt/dialogue/visual_description/camera_angle`，导致重要镜头信息丢失。
- `storyboard_ai.py` 能按场景描述生成台词/镜头，但属于辅助接口，未验证 storyboard 归属，也不落库；它没有统一使用 PromptComposer 或模型任务默认配置。
- `shots.py` 支持精细字段、批量创建、参考图生成和回写 Shot；但镜头缺少 scene_refs/prop_refs/event_refs/asset_refs/consistency_status/prompt_version/review_status 等生产字段，无法形成“人物、场景、道具、事件”全引用闭环。
- `assets.py` 可做资产 CRUD 和公开/项目资产复用，但列表权限以 `project_id + user_id/is_public` 为主，没有 ProjectMember 级访问控制，也没有自动把角色头像、场景图、道具图、镜头参考图作为版本化资产写入和绑定。
- `images.py` 有 ImageJob 和 DEV_MODE，本地能闭环；真实生成仍默认火山，未通过统一 `model_registry` 的任务默认模型选择，也没有从 StoryBible/PromptComposer 自动生成最终 prompt。
- `video.py`/`tts.py` 已支持任务关联和 Shot 回写；但视频 prompt/TTS 文本仍由前端或调用方直接传入，未强制通过 StoryBible、角色音色、参考图资产、镜头字段统一组合。
- `synthesis.py` 的 `/create` 在 DEV_MODE 直接成功，非 DEV_MODE 只是 pending 记录；`workflow.py` 的 `/concatenate` 明确 TODO，当前只返回第一个视频 URL，尚未实现真实多镜头拼接、混音、字幕、封面、导出文件和发布记录。
- ProjectMember 模型存在，但大部分 API 仍只按 `resource.user_id == current_user_id` 校验；项目成员 owner/editor/viewer 角色没有形成通用鉴权依赖，团队协作和权限隔离尚未可用。
- `projects.py` 的成员接口只能列出成员，没有邀请、变更角色、移除成员；`frontend/src/app/teams/page.tsx` 完全使用静态张三/李四/王五数据，不是后端真实项目权限。
- LLMConfig 已按用户存储并加密 Key，`/llm/api-key/{provider}` 不回传明文，这是安全方向正确；但当前只有用户级默认配置，没有“按任务/项目/工作流覆盖”的配置表，文本/图像/声音/视频模型在各生成端点里仍有硬编码或前端直选。
- `model_registry.py` 已定义任务默认模型，但主要生成端点尚未统一按 task 取模型、校验能力、记录模型版本和调用成本；前端 LLM 配置页也主要按 provider/model 配置，没有面向小说生成、实体抽取、分镜、角色图、镜头视频、TTS、合成的任务级默认设置。
- 前端小说列表把 `word_count` 映射为 `characters` 显示，导致“角色数”统计错误；小说详情页调用 `/characters?novel_id=`，后端 characters 列表不支持 novel_id 过滤，角色归属也没有 novel_id 字段。
- 前端小说详情页调用 `/novels/{id}/generate-cover`，后端不存在该接口，会导致封面生成必然失败。
- 前端章节详情页路径目录为 `[chapter_id]`，代码读取 `params.chapterId`，会请求 `/chapters/undefined`；编辑页使用 `params.chapter_id` 是正确的，详情页存在阻断性参数错误。
- 前端没有外部小说导入 UI，也没有“导入预览、章节切分确认、实体抽取审阅、StoryBible 自动生成、场景/道具/事件审阅”的工作台。
- 工作流页面主要是导航式向导，步骤可以手动前进，缺少后端状态机校验、必填产物检测、失败重试、批量任务进度和一键继续；导出步骤也没有真实发布/导出配置。

## 2026-05-11 视频链路连续性初步发现

- 后端 `VideoGenerateRequest` 已有 `novel_id/script_id/storyboard_id/shot_id` 和一致性上下文参数，但请求没有 `chapter_id`，无法表达“第几章的哪个镜头生成了视频”。
- 后端视频生成会校验 `shot_id -> storyboard_id -> script_id` 的一致性，但没有从 `script.novel_id`、`storyboard.chapter_id` 或 `shot` 上游自动补全 `novel_id/chapter_id`，任务历史只能部分追踪来源。
- 前端视频生成页读取 URL 参数只覆盖 `script_id/storyboard_id/shot_id`，没有 `novel_id/chapter_id/workflow_id`，页面内级联选择也没有章节维度。
- 当前视频生成页历史记录读取 `/video/jobs` 全量结果，未按当前小说/章节/剧本/分镜/镜头筛选，用户很难判断某章某镜头是否已经生成过视频。
- 前端已有模型选择、角色参考图、镜头 prompt 自动填充等能力，但链路入口仍偏“单镜头生成工具”，没有形成小说章节生产线视角。
- 分镜智能生成会把 `chapter_id` 写到自动脚本 `extra_data` 和分镜 `content`，但 `StoryboardResponse` 不返回 `novel_id/chapter_id`，前端无法直接用返回值恢复章节关联。
- `TTSJob` 有 `novel_id/chapter_id/script_id/storyboard_id/shot_id` 列；`VideoJob` 目前主要把上游 lineage 放在 `extra_data`，本轮可以先保持 schema 稳定，补齐响应和过滤能力。

## 2026-05-11 视频链路连续性修复结论

- 已采用不迁移数据库的保守方案：视频任务继续用 `VideoJob.extra_data` 保存完整 lineage，但 API 请求、响应、查询过滤都暴露 `novel_id/chapter_id/script_id/storyboard_id/shot_id`。
- `/video/generate` 现在会统一推导 lineage：`shot -> storyboard -> script -> chapter -> novel`，并对请求中显式传入的不匹配 ID 返回 422，避免错把一个章节的镜头生成到另一个章节下。
- 分镜与剧本响应已补齐章节来源，前端视频页可以恢复制作链路，不再只是一块孤立的 prompt 输入工具。
- 当前仍未实现真实多镜头连续视频剪辑、跨镜头转场、字幕和混音生产级导出；这属于后续 synthesis/workflow 生产化阶段，而非本轮单镜头视频生成关联修复。

## 2026-05-11 互联网动漫/AI 视频平台对标发现

- 参考来源：Runway Gen-4 References/Gen-4 Research、Kling Element Library/Video O1 Guide、Kuaishou Kling multi-image reference release、Luma Ray/Dream Machine、PixVerse V6 Character Consistency、Adobe Firefly Video/Image-to-Video、Canva AI Video Generator、Vyond AI Avatars、Animaker Lip Sync help。
- Runway 的 Gen-4/Act-One 方向强调用参考图保持角色、地点、物体风格一致，并支持表演驱动、视频生成和编辑工作流；对本平台的启发是必须把角色/场景/道具参考资产、镜头 prompt、关键帧和成片时间线串成一条生产链，而不是只做单次视频生成。
- Kling/Kuaishou、PixVerse 等视频生成平台重点提供图生视频、多元素/多参考图、角色一致性、唇形或音频驱动视频等能力；对本平台的启发是每个镜头需要明确绑定参考图、角色、道具和音频，并让模型调用按任务默认配置选择供应商。
- Luma Dream Machine 方向强调关键帧、参考、修改和镜头级生成；对本平台的启发是要为镜头提供 start/end/keyframes 与连续转场信息，让前后镜头的画面与事件衔接可控。
- Pika、Adobe Firefly、Canva 更偏易用的视频生成、效果、图像到视频、编辑和发布能力；对本平台的启发是需要在生成链路之后补字幕、转场、封面、导出格式和发布记录。
- Animaker、Vyond、Synthesia、HeyGen 一类平台更强在角色/模板/配音/字幕/团队协作/品牌库；对本平台的启发是后续要补资产版本、角色音色、字幕审阅、团队权限和项目级品牌/风格锁定。
- 本平台当前差异化优势是“小说/章节/Story Bible/实体抽取/分镜/镜头”的上游叙事结构较完整；明显短板是生产级多镜头时间线、真实渲染、混音、字幕、关键帧、资产版本锁定、批量重生成和协作审核。

## 2026-05-11 多镜头连续成片缺口

- `workflow.py` 的 `/workflow/concatenate/{workflow_id}` 当前只取第一个视频任务的 `video_url`，因此它不是成片，只是占位记录。
- 当前 workflow 合成没有校验所有视频任务是否成功、是否有 URL、是否同属一个 workflow/小说/章节链路，也没有保留输入顺序。
- 当前 workflow 合成只取第一个 TTS 音频，不能按 `shot_id` 匹配每个镜头的配音、字幕和时长。
- 合成结果缺少 manifest/timeline：没有 segments、track、字幕、转场、混音策略、导出质量、总时长、源任务血缘，后续真实 FFmpeg/云剪辑服务无法消费。
- 前端 workflow 合成步骤只显示“视频合并”，没有展示多镜头连续成片的编排结果和可验证 artifact。

## 2026-05-11 全流程竞品深度对比新增发现

- 全流程平台可以分为四类：AI 视频生成型（Runway/Kling/Luma/PixVerse/Pika/Firefly）、在线动画制作型（Vyond/Animaker/Powtoon/Renderforest）、通用视频编辑发布型（Canva/Kapwing/InVideo）、数字人口播型（Vyond AI Avatars/HeyGen/Synthesia）。本平台应定位为“长篇小说改编动漫生产线”，而不是单点视频生成器。
- 在线动画制作平台的核心降低门槛能力是模板、角色库、场景库、道具库、拖拽时间线、配音字幕和团队协作；本平台当前缺模板可视化管理、自定义模板 CRUD、素材库预设和新手极速向导。
- AI 视频平台的核心能力是参考图、多图元素、关键帧、镜头运动、一致性和批量生成；本平台已有 Story Bible/实体/镜头结构优势，但需要把参考资产版本锁定、关键帧和质量检查变成强制生产步骤。
- CRUD 审计显示：后端已有 Novel/Chapter/Character/Script/Storyboard/Shot/StoryBible/Asset/Project/Workflow/ImageJob/TTSJob/SynthesisJob/Timeline/LLMConfig 删除能力；缺 VideoJob、NovelImportJob、Publication、StoryEntity、StoryboardTemplate、ExternalAPIConfig 的完整删除/取消/归档/重试能力。
- 前端删除入口不完整：任务中心有删除图标但缺处理；分镜页只能删镜头不能删整个分镜；资产、Story Bible、实体、工作流、时间线、发布记录缺稳定删除/归档入口。
- 优化清单新增 P0：新手极速向导、实体管理台、自定义模板库、任务中心 CRUD、发布中心 CRUD、真实成片渲染。

## 2026-05-12 Phase 41 实施发现

- Phase 41 的后端 CRUD 缺口已有大量前序改动补齐：视频任务可取消/归档，导入任务可更新/重试/归档，发布记录可列表/详情/更新/撤销/归档，实体和模板底层分别由 StoryEntity/Asset API 支持。
- 更大的当前缺口在前端可操作性：用户需要一个低门槛入口把小说、章节、Story Bible、分镜和工作流串起来，也需要实体/模板能在管理台直接编辑。
- 新增 `/quick-start` 后，极速模式的最小闭环是：用户输入故事信息 -> 创建 Novel/Chapter -> 可选生成 Story Bible -> 智能分镜 -> 创建绑定上游链路的 Workflow。它不生成视频/TTS，避免把耗时任务强塞进首屏向导。
- 实体库和模板库现在具备新增、编辑、删除/归档的基础 CRUD；模板仍复用 Asset(category=template)，系统模板仍由后端预制列表提供，不做硬删除。
- 仍未完成的生产级能力：真实 FFmpeg/云剪辑渲染、Timeline 可视化编辑、参考资产版本锁定、关键帧/多图参考强制校验、发布审核流、任务批量重试/恢复、项目级任务默认模型覆盖。

## 2026-05-12 生成级生产化审计发现

- workflow 多镜头合成当前已经从“第一个视频 URL”升级为 manifest，但该 manifest 仍是编排清单，不是用户可直接理解的成片渲染包。
- SynthesisJob 的 `extra_data.render_status` 有 `ready/pending_renderer`，但缺少独立的预检接口和渲染重试接口，前端无法在导出前解释缺视频、缺音频、缺字幕或缺 manifest 的具体原因。
- 现有 manifest 已包含 segments、tracks、subtitle、transition、lineage 和 shot_controls，足够生成本地 SRT、EDL/timeline JSON 和 HTML preview；因此本轮可以不引入 FFmpeg，先补稳定可消费 artifact。
- 前端 workflow 页面已展示 manifest 链接，但用户仍需要手工打开 JSON；应在合成/导出步骤直接展示预检状态、渲染包链接和重试按钮。

## 2026-05-12 生成级生产化实施结论

- DEV_MODE 渲染包现在是“可消费 artifact”，不是声称真实转码：后端输出 HTML preview、SRT、timeline EDL 和 render manifest，后续真实 FFmpeg/云剪辑可以消费同一套 timeline/manifest。
- 渲染预检会把阻断项和降级项结构化返回：缺 synthesis manifest、segments 为空、segment 缺 video URL 为阻断；缺音频会按静音降级 warning；缺字幕会按无字幕轨 warning。
- 前端 workflow 合成步骤现在可以完成用户可见闭环：看到连续成片 manifest 后直接预检、生成或重新渲染，并打开 HTML/SRT/EDL/渲染清单。
- Playwright 的服务健康检查不应依赖根路径 `/`，因为当前应用根路径可返回 404；使用 `/workflow` 更符合现有 App Router 页面状态。
- `next build` 会重建 `.next`，如果 dev server 同时运行，浏览器可能拿到旧 HTML 指向已删除的 chunk，导致页面不水合；运行 build 后要重启 dev server 再做浏览器 E2E。

## 2026-05-12 生产一致性贯穿发现

- 分支层面不是“优化没合并”：当前 `main` 已包含可见优化分支提交，问题是大量优化能力在后端或局部页面，未贯穿到分镜、镜头、视频生成和前端可见上下文。
- 旧链路中 `Shot` 只稳定保存 `character_refs`，场景、道具、事件、环境主要没有绑定到镜头；视频生成只拿 lineage 和部分一致性 metadata，任务历史也不返回实体上下文。
- 修复后，智能分镜会把 StoryEntity 的人物、场景、道具、事件绑定到每个镜头，并把字幕文本保存为 `extra_data.subtitle_text`；视频任务保存并返回同一套实体引用。
- 前端原先只加载带 avatar 的角色，会让没有头像但在故事中出现的人物消失；已改为加载全部角色，并在视频生成页展示镜头上下文。
- 实体抽取规则原先会把 `角色：沈砚。场景：...` 误清洗成一个过长人物名；已收紧 `_clean_name`，遇到句号或新实体标签即截断。

## 2026-05-12 角色小说归属审计发现

- Character 当前只有 `user_id`，没有 `novel_id/chapter_id`，导致同一用户下角色被当作全局角色库使用。
- `/characters?novel_id=` 已被小说详情页调用，但后端列表接口没有接收该参数，实际仍返回用户全部角色。
- `/characters/extract` 从小说或章节提取后创建 Character 时未保存来源小说/章节，后续无法按作品过滤。
- `build_shot_entity_context()` 使用全用户 Character 按名称匹配 StoryEntity，存在不同小说同名/异名角色串用风险。
- 视频生成页当前加载 `/characters` 全量角色，选定小说后角色参考下拉仍可能出现其他小说角色。

## 2026-05-12 角色小说归属修复结论

- 角色归属边界已从“用户级全局池”改为“小说级作用域 + 可选全局角色库”。生产链路中传入小说后默认不会混入其他小说角色。
- 小说详情页原本已调用 `/characters?novel_id=...`，后端现在支持该契约，因此角色 tab 不再展示同用户其他小说角色。
- 视频生成页和一致性上下文是最容易串角色的两个下游入口，本轮已改为按当前小说取数和按当前小说匹配 StoryEntity。
- TTS 多角色对白按名称匹配音色也是同类问题，已纳入本轮修复，避免视频角色正确但配音角色错误。
- 仍建议后续把 Scene/Prop/Event 的资产引用也扩展为强归属模型，目前 StoryEntity 已有 novel/chapter 归属，风险低于 Character，但资产库仍可能存在项目/全局复用边界需要继续细化。

## 2026-05-12 视频历史与一致性再修复发现

- 视频历史播放失败有两个根因：前端直接把后端返回的 `/static/dev/...` 当作前端同源资源使用，落到 `localhost:3000`；同时 DEV_MODE 原先只返回 mp4 路径，没有实际生成本地 mp4 文件。
- 历史下载按钮原先只是 `window.open(job.video_url)`，没有使用后端已有 `/video/download` 代理，也不能保证浏览器按附件下载。
- 视频生成请求模型已有 `seed` 字段，但 `/video/generate` 未把 seed 传给火山 SDK，也未在 VideoJob 响应中透出；同一小说/分镜/镜头重生成缺少可重复随机锚点。
- SDK 本地签名确认 `content_generation.tasks.create()` 支持顶层 `seed/duration/resolution/camera_fixed/watermark`；原实现只把 duration/camerafixed/watermark 拼进 prompt，且 `resolution_arg` 定义后未拼入。
- `build_consistency_prompt()` 已能拿 Story Bible、角色和镜头实体，但对分镜/剧本的 `style/genre/description` 注入不足，导致只选到分镜或重生成镜头时风格锚点偏弱。

## 2026-05-13 动漫制作平台和插件生态对标发现

- AI 视频模型平台已经从“静音单镜头生成”快速转向“视频+同步音频”直生：OpenAI Sora 2 官方定位为视频和音频生成模型，Google Veo 3 官方资料强调可生成带背景声、对白和音效的视频；Canva 已把 Veo-3 封装成 8 秒 16:9、带同步音频的低门槛文本生成视频入口。
- Runway Gen-4 References、Kling Elements、PixVerse Character Consistency、Luma/Ray 一类工具的共同点是参考图、多元素、角色一致性、关键帧或镜头控制；这些能力说明本平台必须把角色/场景/道具资产版本、关键帧、seed、镜头参数和模型输入锁定为可复现的生产上下文。
- Vyond、Animaker、HeyGen/Synthesia 等口播/动画平台的强项不是小说理解，而是角色库、模板、配音、口型、字幕、多语言和团队协作；本平台需要在已有小说/分镜优势上补对白审阅、角色音色、口型/唇形任务和字幕审阅。
- Toon Boom Harmony、Clip Studio Paint、Live2D Cubism、Blender Grease Pencil 代表传统/专业动漫生产流程：分镜、原画/动画 cel、rig、口型、合成、时间线和项目文件协作是核心生产资产；本平台不能只停留在 prompt/job 列表，需要可编辑 timeline、轨道、镜头版本和资产锁定。
- ComfyUI、ControlNet、IP-Adapter、AnimateDiff、LoRA 等插件生态的价值在于“可视化节点工作流 + 可控生成 + 可复用模板”；本平台应支持插件化 provider/workflow adapter，把 ComfyUI JSON、ControlNet pose/depth/canny、IP-Adapter 参考图、AnimateDiff 动作模板映射到 Shot/Asset/MediaJob。
- 本平台的差异化仍是“长篇小说改编动漫生产线”：Novel/Chapter/Story Bible/StoryEntity/Storyboard/Shot 已经比通用视频工具更适合连续叙事；短板是直接音视频生成、字幕一等公民、真实时间线渲染、插件工作流接入、批量生成/审核和协作生产。

## 2026-05-13 当前工程对直接音视频和字幕的缺口

- `model_registry.py` 目前有 `shot_video`、`tts_dialogue`、`final_synthesis`，没有 `shot_audio_video/text_to_audio_video/image_to_audio_video/sound_effect_generation/lip_sync/subtitle_generation` 等能力声明。
- `VideoJob` 只稳定存 `video_url/cover_url`，音频、字幕、音画同步策略主要落在 `extra_data` 或后续 `SynthesisJob`，不能表达“一次模型调用直接产出带音频视频”的任务。
- `SynthesisJob` 面向“已有 video_url + audio_url 的合成”，DEV_MODE 能出本地 output，workflow 能出 manifest/SRT/HTML preview；但非 DEV_MODE 仍不是完整渲染执行器，也不是直生音视频模型任务。
- 字幕目前分散在 `Shot.extra_data.subtitle_text`、`VideoJobResponse.subtitle_text`、workflow manifest 的 segment subtitle、render 阶段的 SRT 文件；没有 `SubtitleTrack/SubtitleSegment` 数据模型、审阅状态、多语言、说话人、时间码和导出版本。
- `Timeline/Track/Clip` 已支持 subtitle 类型和 `Clip.text_content`，但 workflow render 只是导出 EDL/JSON，没有把字幕轨作为数据库内可编辑时间线产物自动写入。
- 前端视频生成页能显示镜头字幕和历史字幕，workflow 页能打开 SRT artifact；但用户不能编辑字幕段、不能选择字幕来源、不能对直接音视频模型返回的音频/对白做审阅，也不能在极速向导里一键生成带字幕的首集草稿。

## 2026-05-13 推荐架构结论

- 新增统一媒体任务层：优先设计 `MediaGenerationJob`，兼容映射现有 `VideoJob/TTSJob/SynthesisJob`；字段包含 `task_type`、`media_type`、`lineage`、`provider_id`、`model_id`、`capabilities`、`input_assets`、`output_video_url`、`output_audio_url`、`subtitle_track_id`、`timeline_id`、`seed`、`style_lock`、`asset_version_locks`、`quality_report`。

## 2026-05-27 参考图公网交付发现

- 火山图生视频要求 `content[].image_url` 是云端可访问的 http(s) 图片地址；平台本地 `/static/...`、`localhost`、内网地址不能直接传给火山。
- 当前媒体持久化服务只负责把远端临时 URL 下载到本地 `/static/generated/...`，可保证历史播放/展示稳定，但不等同于公网可访问。
- 现有 `/external` 生产适配配置已经能管理可选外部能力，适合承载“对象存储/CDN”配置，不需要新增独立配置体系。
- 本轮最小可落地方案是“公开静态媒体出口”：用户配置一个公网 `public_base_url` 或基础地址，把本地 `/static/...` 映射成 `https://cdn.example.com/static/...`。如果该 CDN/对象存储已同步或反代本机静态目录，云端视频模型即可读取参考图。
- 完整对象存储直传（S3/MinIO/OSS SDK 上传、本地文件同步、签名 URL 生命周期）可作为后续增强；本轮预留配置字段，但不引入新 SDK 和大迁移。

## 2026-06-06 生产级全链路深度审计新增发现

- 当前工程已经不是“缺基础模块”的状态：Novel/Chapter/Script/Storyboard/Shot、StoryBible/StoryEntity、Asset、多视图资产、Video/TTS/Media/Subtitles/Synthesis/Workflow、模型配置、生产适配、极速向导、AI 制片中心都已经存在。
- 当前主要风险是“能力分散且可绕过”：视频端点具备最完整的 `_build_video_consistency_package()`，但章节、剧本、分镜、参考图、TTS、直生音视频等入口仍不同程度把一致性当作 prompt 增强或可选参数，而不是生产门禁。
- `backend/app/services/consistency_context.py` 中 `auto_fill_shot_entity_refs()` 定义了两次，后面的 4 参数版本覆盖前面的 5 参数版本。虽然当前调用可能依赖后者，但这是误维护和误调用的高风险点。
- `shot.extra_data.entity_refs` 的结构需要统一：部分路径写入 ID 列表，`build_shot_entity_context()`/视频响应倾向使用完整 dict refs，而 `AssetLockService.lock_shot_assets()` 又假设是 ID。结构混用会影响资产锁、提示词重建和批量生成。
- `backend/app/services/asset_lock_service.py` 存在可执行风险：`await db.execute(...).scalar_one_or_none()` 的 await 优先级错误；`unlock_shot_assets()` 会解锁共享 Asset 本身，而不仅是解除某个 Shot 的引用；`_get_entity_locked_asset()` 接收 `entity_type` 但查询未使用。
- 资产锁目前更多用于记录和部分视频 prompt 注入，不是所有生成路径的必经输入。`build_consistency_prompt()` 未传 `locked_assets` 给 `compose_generation_prompt()`，导致“重建 prompt/图片/部分媒体任务”可能丢失资产锁约束。
- 媒体交付策略是合理的：无公网对象存储/CDN时跳过本地参考图，避免供应商 400；但生产路径应在预检阶段把“参考图不可公网访问”列为阻断或明确降级，而不是任务创建后才在 prompt 里备注。
- 测试覆盖量较大，已覆盖 DEV_MODE 全流程、实体抽取、Story Bible、资产多视图、TTS 音色、媒体字幕、workflow manifest/render package；但多数验证是 DEV_MODE、元数据或 manifest 级，缺少真实生产门禁和最终 MP4 的可播放/音轨/字幕/顺序硬验收。
- 样例风格图实际已落在 `backend/static/starter`，且 `asset_generation_service.py` 引用的 62 个 starter URL 都存在；若前端仍看不到样例，问题更可能是静态资源服务、URL 转换、懒加载容器或页面条件展示，而不是文件缺失。
- 前端仍存在非专业用户不友好的技术字段：镜头编辑中可见 `asset_version_locks`、`keyframes`、`character_multiview_refs`、`reference_assets`、`provider_options` 等 JSON 输入；资产编辑也仍有变量配置/视图配置/生成参数 JSON，需要改成向导式表单和模板选择。

## 2026-06-06 推荐架构结论

- 不建议破坏性重构底层。应新增轻量 `GenerationOrchestrator` / `ConsistencyPreflightService`，复用既有 Story Prompt Context、Prompt Composer、Production Pack、Asset Lock、Voice Service、Media Delivery、Model Registry。
- 所有生成端点统一调用预检：`novel_id/chapter_id/script_id/storyboard_id/shot_id/task_type` -> 解析 lineage -> 构建 story pack -> 规范 entity refs -> 锁定资产版本 -> 检查模型能力和媒体公网可达 -> 生成 prompt/seed/subtitle/voice/reference package -> 返回 blocking/warning/autofix actions。
- 前端应把同一套 package 展示为“全局锁定状态”，而不是让用户读 JSON：人物已锁、场景已锁、道具已锁、画风已锁、音色已锁、字幕已就绪、参考图可用于云端、模型已验证。

## 2026-05-19 小说/剧本连续性审计发现

- 章节生成链路相对完整：`chapters.generate_chapter_text()` 会加载小说、前后章节、Story Bible、StoryEntity、Character，并通过 `build_chapter_continuity_block()` 和 `build_consistency_prompt()` 形成连续性硬约束；生成后 `persist_story_context_from_chapter()` 会把人物、场景、道具、事件同步回 StoryEntity/Story Bible。
- 统一故事上下文服务已经具备复用价值：`story_prompt_context.load_story_prompt_context()` 能输出小说题材、简介、风格、世界观、章节摘要、人物、场景、道具、事件；封面、章节、分镜、视频、直生音视频已经不同程度消费该上下文。
- 剧本生成链路明显落后：`scripts.generate_script()` 只读取当前章节正文、小说简介和“其他章节中的最后一章”，未复用 `load_story_prompt_context()`，也未注入 Story Bible、人物关系、事件时间线、场景/道具状态、负面约束、资产要求和短视频节奏。
- 剧本生成的前情选择有逻辑风险：它从“除当前章节外的所有章节”中取最后一章作为前情，如果正在改编中间章节，可能错误引用后续章节作为前情，造成剧本和小说时序矛盾。
- 人物关系有存储和生产包出口，但未成为剧本硬约束：StoryEntity.attributes 可包含 `relationships`，`/story-bibles/entities/production-pack/{novel_id}` 会返回 relationships/event_timeline/scene_tags/asset_requirements，但剧本生成没有调用或注入这些数据。
- 剧本与章节关联仍主要放在 `Script.extra_data.chapter_id`，响应层会透出 `chapter_id`，前端也能筛选；但数据库层没有 `scripts.chapter_id` 索引，后续分页、权限、查询和一致性校验会越来越吃力。
- 前端剧本页已经支持按小说/章节筛选、选择章节生成剧本和模型配置选择；但缺少“生成前上下文预览/预检”“人物关系与事件线提示”“生成后一致性检查结果”和“从小说详情直接选章节生成剧本”的一体化入口。
- 小说详情页有章节、角色、剧本、Story Bible 入口；但剧本 Tab 只有列表和新建链接，没有一键从某章节生成剧本，也没有展示每章是否已有剧本、分镜、镜头、视频等产物状态。

## 2026-05-27 分镜与角色生成问题发现

- 后端 `DELETE /storyboards/{id}` 只删除 Storyboard 本身，虽然 Shot 外键声明了 cascade，但本地 SQLite/SQLAlchemy 路径不能依赖数据库级联；应显式删除该分镜下镜头，避免前端删除后下游镜头残留。
- 前端分镜页已有智能生成能力，但主要藏在“新建分镜”弹窗里；详情区没有“从当前剧本生成分镜和镜头”的明显入口，列表卡也没有整分镜删除按钮。
- 角色抽取接口从 AI 返回列表后直接创建 `Character`，没有同小说范围排重；同一小说重复提取会产生多个同名角色，后续分镜、视频、TTS 容易匹配到不稳定角色。
- 角色头像生成现在由前端直接调用 `/images/generate`，prompt 是英文短句，未强制注入小说题材、角色身份、性别、外貌、性格和标签，容易出现性别错误或无关头像；图像模型异常时也会直接显示通用 500。
- 小说封面后端已经使用 `build_cover_prompt()` 和 `load_story_prompt_context()`，但前端错误处理丢弃后端 `detail`，用户只看到通用失败提示。

## 2026-05-27 修复结论

- 分镜删除不再依赖数据库外键级联，接口层会显式清理镜头；前端删除后会同步清空当前选择，避免还显示已删除分镜的镜头列表。
- 角色头像生成路径从“前端拼 prompt 调通用图片接口”收敛为“后端按角色/小说上下文生成头像并回写角色”，更适合保证性别、身份、外观和题材一致性。
- 角色抽取排重规则采用小说作用域而非全用户作用域：同一小说重复提取同名角色合并，跨小说同名角色仍然允许独立存在。
- 封面生成上下文本身已具备小说、章节、人物、场景、道具、事件约束，本轮前端改为透出后端具体失败原因，便于用户定位是模型配置、图片返回还是持久化问题。

## 2026-05-27 题材预设调研发现

- 修仙/仙侠题材常见生产元素：修炼境界、灵气、宗门、师徒/同门关系、法宝、丹药、灵兽、秘境、雷劫、突破和宗门审判。适合模板：突破、宗门议事/审判、御剑追逐、秘境发现。
- 武侠题材常见生产元素：江湖、门派、侠义、恩怨、武林大会、客栈、镖局、山门、秘籍、名剑、轻功、刀剑对决。适合模板：江湖对峙、擂台比武、夜探门派、客栈冲突。
- 玄幻题材常见生产元素：多族群/大陆、血脉觉醒、异兽、神器、古遗迹、元素能量、王朝/学院/圣地、跨地域冒险。适合模板：秘境探索、异兽遭遇、血脉觉醒、神器现世。

## 2026-06-05 多视图资产与低门槛创作审计发现

- 后端 `Asset` 已有 `novel_id/chapter_id/script_id/entity_id/entity_type/source_prompt/generation_params/is_locked`，足够承载小说实体级多视图资产，不需要新增大表。
- 后端 `AssetGenerationService` 已能生成角色、场景、道具资产并落库，但当前角色生成的是 `avatar/full_body/expressions/poses`，不是生产一致性更需要的“正面/侧面/背面”三视图。
- 场景生成当前只有 `main_scene/detail`，道具生成只有 `main`，都不足以支撑场景空间连续性、道具跨镜头比例和使用状态一致性。
- 前端资产页已经支持上传、预览、编辑、锁定、作用域调整和小说/实体筛选，但核心编辑区仍暴露 `variables/shot_template/generation_params` JSON，普通创作者理解成本高。
- 资产页已有“角色三视图/场景四视图/道具多视图”快速筛选和系统模板展示，但没有把这些模板变成“选择小说实体 -> 查看缺失视图 -> AI 生成/上传 -> 锁定定稿”的工作流。
- 多视图与小说角色的关联目前依赖用户手工选 `entity_id` 或角色生成接口的 `character_id`，对 StoryEntity 中的角色、场景、道具没有统一的生成入口。
- 低门槛方案应保留高级字段，但默认折叠；主流程只展示中文业务概念：所属小说、对象类型、对象名称、必备视图、生成风格、画面比例、参考图预览、定稿锁定。
- 都市异能/现代都市题材常见生产元素：现代城市、学校/公司/医院/警局/实验室、隐藏组织、异能觉醒、都市追查、监控/手机/终端、夜巷、天台、地铁。适合模板：都市觉醒、夜巷追逐、调查推理、组织简报。
- 当前工程已有通用模板和少量默认资产/实体，但题材模板还偏通用；扩展应直接落在 `storyboard_template_service.py` 与 `default_anime_library.py`，这样现有智能生成和资产/实体管理页面能立即使用。

## 2026-05-13 Seedance 2.0 模型目录发现

- 视频生成页不需要硬编码火山视频模型，它已从 `/api/v1/llm/models?provider=volcano` 动态加载 `video` 和 `video-generation` 类型模型；因此新增模型的关键是后端目录、DB 种子和已有数据库回填。
- 旧目录中 `Doubao-Seed-2.0-pro` 被标记成 `video-generation`，会污染视频模型列表；已修正为 `chat`，避免用户在静音视频生成中选到文本模型。
- 仅在表为空时初始化默认模型不足以支持长期迭代；已有数据库需要列表接口回填新增内置模型，否则前端看不到新模型。
- 本轮新增的 `doubao-seedance-2-0-260128` 和 `doubao-seedance-2-0-fast-260128` 已在火山 endpoint 映射、统一模型注册表、初始化脚本和 LLM 默认目录中保持一致。
- 静音视频链路已验证会把用户选择的 Seedance 2.0 Fast endpoint 传给火山 SDK，并保存到 VideoJob 的 `api_model_id/model_endpoint_id`。
- 新增字幕一等模型：`SubtitleTrack` 表示一条语言/用途字幕轨，`SubtitleSegment` 表示逐段字幕；每段包含 `shot_id`、`speaker_entity_id`、`start_seconds`、`end_seconds`、`text`、`source`、`review_status`、`confidence`、`style`，并支持 SRT/VTT/ASS 导出。
- 供应商能力注册需要从模型列表升级为 capability matrix：`text_to_video`、`image_to_video`、`text_to_audio_video`、`image_to_audio_video`、`dialogue_audio`、`sound_effects`、`music`、`lip_sync`、`subtitle_timing`、`watermark`、`seed`、`reference_image_count`、`duration_limits`。
- 直接音视频路径不能取代分步路径：生产平台应同时支持 `shot_audio_video` 直生、`shot_video + tts_dialogue + synthesis` 分步、`lip_sync_video` 音频驱动、`final_render` 多轨渲染四种路径，并允许 workflow 按模型可用性自动降级。
- 插件化能力应先落为“工作流模板和适配器”，不是大而全插件市场：P0 支持本地 FFmpeg/字幕、Sora/Veo 类 direct A/V provider、ComfyUI workflow JSON 导入/参数填充；P1 再接 ControlNet/IP-Adapter/AnimateDiff 节点级参数。

## 2026-05-13 全流程工作台对齐发现

- 后端已经有 `/workflow/{workflow_id}/generate-media-batch`，但 workflow 页面没有入口，导致“直生音视频”和字幕一等能力只在视频生成页局部可见，用户无法从首集工程继续批量生成。
- workflow 页面从 `workflow_id` 恢复时只刷新任务列表，没有把后端返回的 `novel_id/chapter_id/script_id/storyboard_id` 写回本地 `workflowData`，因此页面会像新工作流一样显示早期步骤，后续入口容易灰掉。
- 步骤锁定原先按 `idx > currentStep`，但后端 `current_step` 可能仍是 1；即使工作流已有分镜、媒体任务和渲染包，用户也不能直接跳到视频/合成/导出，这是“生成首集工程后按钮灰色”的同类交互问题。
- workflow status 原先不返回 `MediaGenerationJob` 和 `SubtitleTrack`，前端无法展示直生音视频、字幕轨和生产就绪状态；这造成后端能力已落地但前台没有体现。
- 连续成片原先只接受 `VideoJob`，不能直接消费直生音视频 `MediaGenerationJob`；这会迫使用户再走分步视频/TTS链路，违背“支持直接音视频生成”的目标。
- 修复后，workflow 可以从小说/章节/分镜直接批量直生音视频，媒体任务的音频、字幕、lineage 进入 manifest/render/export；前端生产就绪检查可解释缺视频、缺音频、缺字幕、缺成片、缺渲染包等状态。
- 当前仍不能称为完整生产级 SaaS：真实 Sora/Veo provider SDK、真实 FFmpeg/云剪辑转码、字幕烧录、资产版本锁定、多人审核、成本计费和故障恢复仍未完成；本轮达成的是 DEV_MODE 下可验证的生产流程雏形。

## 2026-05-13 P1/P2 提示词一致性深化发现

- 封面生成原先会在小说详情页被前端简单 prompt 覆盖，后端只知道“标题/类型”，不能自动把 StoryEntity、Story Bible、章节中的人物、场景、道具、事件纳入封面画面。
- 章节真实生成已经接入 `build_consistency_prompt()`，但 DEV_MODE fallback 文案仍偏通用，缺少显式人物、场景、道具、事件清单；本地全流程验证时无法证明章节连续性真的被承接。
- 智能分镜持久化会绑定实体，但模板层对白仍可能输出“（角色）{beat}”，这会让字幕、TTS、直生音视频拿到不符合人物口吻的占位文本。
- 视频生成已能注入镜头实体和字幕，但直接音视频 `/media/generate` 还主要保存用户 prompt；两条视频路径需要共享“动漫连续性硬约束”，避免分步视频和直生音视频逻辑不一致。

## 2026-05-22 数据分析与系统设置审计发现

- `/analytics` 当前仍是静态 mock 卡片，播放量/用户增长图表只是“图表数据加载中…”占位，没有读取 dashboard、usage-stats 或任务队列真实数据。
- 后端已有可复用统计接口：`/dashboard/stats`、`/usage-stats/summary`、`/usage-stats/by-model`、`/usage-stats/daily`、`/usage-stats/logs`；但前端 `getUsageStats(period)` 仍指向不存在的 `/usage-stats?period=`。
- `/settings` 首页已有“通知设置”和“外观设置”入口，但对应页面缺失；快捷设置只是静态按钮，不能保存或反馈状态。
- 本轮优化应优先复用现有接口和 localStorage 偏好，避免新增后端偏好表或改动认证/生成链路。

## 2026-05-22 数据分析正式数据源修复发现

- 前端多接口拼装统计会导致数据口径不一致，且 `catch(() => [])` 会把接口失败伪装成正式 0，用户无法区分“无数据”和“统计失败”。
- 既有 `usage_stats.py` 按模型统计引用 `LLMUsageLog.model`，但当前 ORM 只有 `config_id/request_type/tokens/cost` 等字段；模型排行应按 `config_id` 聚合，并可选关联 `LLMConfig/LLMModel` 解析显示名。
- 正式数据分析页需要后端聚合接口作为单一数据源，明确返回 `data_source=database` 和 `is_mock=false`，并让前端在接口失败时展示错误而不是兜底模拟。
- 新增的 `story_prompt_context.py` 是轻量聚合层，不迁移 schema；它按 novel/chapter 读取 Novel、Chapter、StoryBible、StoryEntity、Character，并在缺少已持久化实体时从文本中做确定性抽取，用于封面、章节、分镜对白和视频 prompt。
- 封面 prompt 现在把用户 prompt 作为“用户补充要求”，而不是覆盖自动上下文；生成任务保存的 ImageJob.prompt 可追溯题材、主要人物、关键场景、关键道具和事件冲突。
- 分镜模板对白现在优先使用具体角色名，并把场景、道具或事件塞入旁白/对白锚点；AI refine 的 user prompt 也显式带入人物/场景/道具/事件清单，减少模型只根据模板草案自由发挥。
- 视频和直生音视频现在都追加“动漫连续性硬约束”，要求人物脸型、发型、服装、年龄感、身份关系、场景空间、天气光影、关键道具状态、事件结果和对白字幕与上游一致。
- 当前仍未解决的 P1/P2：资产版本锁定、角色多视图参考图、关键帧 start/end、口型/唇形、真实供应商对参考图/字幕的能力适配、字幕烧录和多人审核仍需继续落地。

## 2026-05-13 真实生产适配落地发现

- 工程中已有 `ExternalAPIProvider/ExternalAPIConfig/ExternalAPIUsageLog`，适合作为 Sora/Veo/ComfyUI/FFmpeg 云渲染/口型等外部能力的统一配置面；不需要新增平行 provider 表。
- 外部适配必须区分三种状态：`success/rendered` 表示已拿到真实产物，`cloud_pending/pending` 表示已提交等待供应商，`adapter_ready` 表示本平台已生成可提交 payload 但缺少真实提交路径或处于 DEV_MODE。
- `Shot.extra_data.production_context` 能承载资产版本锁、关键帧、多视图角色参考、口型配置和审核状态，短期不必迁移新表；后续若要做资产依赖图、版本回滚和多人审批记录，再拆独立表更稳。
- ComfyUI 适配最小闭环是保存 `workflow_json + lineage + asset locks + keyframes + multi-view refs`，由 `/media/generate` 统一生成 adapter payload；真实执行需要管理页配置 base_url/submit_path。
- FFmpeg 云渲染不应复用 DEV_MODE 的 synthesis output_url 作为云渲染结果；云渲染分支现在只返回 render manifest/timeline/SRT，除非外部服务响应具体 `output_url`，否则不标记为成片完成。
- 前端原 `llm-config` 的外部 API tab 仍是“开发中”占位，容易让后端能力不可见；新增独立 `/production-adapters` 后，外部能力配置、测试、编辑、删除有明确入口。

## 2026-05-13 AI 生成提示词与反馈审计发现

- 章节生成/润色已接入小说、章节、Story Bible 和实体上下文，但前端执行时主要显示 spinner 或 alert，缺少“正在读取上下文/生成/保存/同步实体”的阶段反馈。
- 剧本生成仍使用端点内手工拼接 prompt，只有小说简介和一个前情片段；未统一复用 `story_prompt_context` 的人物、场景、道具、事件清单，也未在响应中暴露 provider/model、上下文摘要、告警或生成阶段。
- 角色提取能按 novel/chapter 保存归属，但响应是裸 `Character[]`；头像生成失败只存在后端局部 `avatar_errors`，不会返回给前端，用户无法知道是文本提取成功但头像失败，还是整体失败。
- 实体抽取 `/story-bibles/entities/extract` 是确定性抽取，已覆盖 character/scene/prop/event，但响应缺少上下文来源、抽取阶段、persist 状态和“文本过短/无实体/缺章节”的清晰生成反馈。
- `storyboard_ai.py` 的台词和批量镜头辅助接口仍只基于用户传入 scene/chapter/characters，未通过 shot_id/storyboard_id 反查小说章节和 Story Bible；JSON 解析失败时还可能返回默认描述，容易掩盖模型输出质量问题。
- 分镜智能生成已强上下文化，但普通 `/storyboards/generate`、前端分镜生成按钮和脚本页 AI 生成缺少明确进度反馈；失败原因主要靠 alert 或通用报错。
- 小说新建页简介/封面生成、小说详情实体抽取、角色提取、剧本生成、分镜生成、章节 AI 写作都需要从“等待中...”升级为可见阶段文案，并把后端 detail/error_reason 透出。

## 2026-05-13 视频模型与生产适配消费链路复查发现

- `/llm/configs` 需要区分 `config_model_id` 和真实 `api_model_id`；前端把配置 `model_id` 误当 API 模型 ID 会导致视频生成没有按用户选择的模型调用。
- 视频生成页原先找默认配置只看 `is_default && provider_id === 'volcano'`，没有筛选 `model_type`，火山文本/图片默认配置会被误认作视频默认配置，表现为视频模型“未验证”或选择状态不一致。
- `/video/generate` 是静音视频路径，当前生产可用范围是火山视频 SDK；Sora/Veo/ComfyUI/口型等生产适配属于 `/media/generate` 直生音视频或 workflow 渲染路径，不能混在静音视频按钮里暗中生效。
- 生产适配的实际消费点有四个：`/production-adapters` 管配置，`/shots/{id}/production-context` 管镜头生产上下文，`/media/generate` 提交直生音视频/ComfyUI/口型 adapter payload，`/workflow/{id}/render` 提交 FFmpeg 云渲染请求。
- 静音视频历史必须显示 provider、API model、endpoint、验证状态、seed、参考图是否传入，才能让用户确认“我选择的模型是否真的被调用”。
- 公网参考图预检失败不应静默丢弃图片；CORS/HEAD 失败不代表供应商无法访问，应该继续传入，由供应商返回更准确错误。本地/私有地址才应阻止传入。

## 2026-05-13 管理筛选与 Workflow 串联发现

- `/shots` 原实现只从第一个剧本加载分镜下拉，镜头虽然遍历全量剧本，但没有把 novel/chapter/script lineage 保存进前端列表项，因此无法按小说、章节、剧本筛选，也无法从镜头页带完整链路去视频生成页。
- `/workflow` 的章节步骤只展示章节，没有“选中章节”行为；角色步骤是静态跳转，不读取当前小说/章节角色，也没有 AI 提取入口。
- `/workflow` 的剧本、分镜、镜头步骤大多是跳转占位，没有读取当前链路已有产物；用户在章节后继续操作时，会感觉已有角色/剧本/分镜都“加载不出来”。
- 工作流后端 `PUT /workflow/{id}/step` 原本只能保存 step/job ids，不能保存 novel/chapter/script/storyboard；前端本地选中后，轮询状态容易被后端旧链路覆盖，表现为流程又回到小说起点。
- 角色管理页已具备小说范围筛选、AI 提取和 CRUD；分镜页也已有小说/章节筛选和镜头 CRUD。本轮重点补齐了镜头管理、剧本筛选和 workflow 内联操作。

## 2026-05-13 平台生产化复查新增发现

- `frontend/src/contexts/AuthContext.tsx` 把 `!pathname.startsWith('/')` 当作受保护路由判断，导致任意路径都被视为公共路径，未登录不会自动进入 `/login`。
- `frontend/src/app/settings/profile/page.tsx` 已调用 `/auth/profile`，`frontend/src/app/settings/security/page.tsx` 已调用 `/auth/change-password`，但后端 `auth.py` 尚未提供对应接口，资料和密码保存会失败。
- 登录页缺少忘记密码入口；后端也缺 `/auth/forgot-password` 和 `/auth/reset-password`，账户恢复链路不完整。
- `backend/app/core/security.py` 在非 DEV_MODE 下仍只解 JWT payload，不验证签名；生产权限隔离无法成立。
- 通用 `DialogContent` 缺 `max-h` 与 `overflow-y-auto`，手写弹窗如 `shots`、`storyboards`、`scripts` 使用居中 fixed 布局，低高度窗口下底部按钮可能超出不可点击。
- 个人资料页头像按钮仍是 `alert('头像上传功能开发中...')`，属于前端可见未落地入口；Dashboard 空状态“浏览示例”当前实际进入作品列表，文案容易误导。

## 2026-05-14 P0/P1 前后端可见性复核发现

- P0/P1 主链路目前已有前端入口：极速向导、作品/章节、角色、实体库、剧本、分镜、镜头、视频生成、直生音视频、字幕工作台、workflow、生产适配、时间线、任务队列、发布/合成和团队权限。
- 本轮发现的主要前端缺口是通用资产库：后端 `/assets` 已支持角色、场景、道具、服装、音乐、音效、模板、提示词等资产 CRUD，但前端此前只有 `/templates` 局部复用 `category=template`，没有面向生产资产版本锁和参考资产的一等页面。
- 已新增 `/assets` 资产库页面，支持分类、项目、公开范围和搜索筛选；可新增、编辑、归档资产；可登记资源 URL、缩略图、业务标签、风格标签、项目归属和公开状态。
- 顶部“工具”菜单和控制台新增资产库入口，资产版本锁、多视图参考、关键帧、场景/道具参考图不再只藏在镜头生产上下文 JSON 中。
- 静态扫描仍显示部分页面使用 `alert()` 做成功/失败反馈，属于体验和反馈 P1 继续优化项；未发现同级别“后端 P0/P1 能力完全没有前端入口”的新增缺口。
- 当前真实生产边界仍是：OpenAI Sora/Veo/ComfyUI/FFmpeg 云渲染真实 SDK 提交和轮询未完整闭环；DEV_MODE artifact 不等同于生产转码；字幕烧录、多语言字幕、评论式多人审核和成本/配额仍在 P1/P2 后续。

## 2026-05-15 视频/音视频历史筛选发现

- `/video/jobs` 已有小说、章节、剧本、分镜、镜头过滤能力，但前端历史区此前没有独立可见筛选入口，用户只能间接通过左侧制作链路影响历史列表。
- `/media/jobs` 已有小说、章节、分镜、镜头过滤，但缺 `script_id` 参数，导致直生音视频历史无法按剧本筛选。
- 剧本列表接口此前只有兼容旧前端的全量返回；本轮补 `page/page_size` 后不改变旧返回结构，前端可先做轻量分页展示。
- 当前后端没有全量 storyboards/shots 聚合列表接口，历史筛选里的分镜和镜头仍按“小说/章节/剧本 -> 分镜 -> 镜头”的级联方式加载，这符合制作链路逻辑，也避免一次性拉取全量镜头。

## 2026-05-15 模板库系统预制模板发现

- 系统预制模板原先完全来自 `STORYBOARD_TEMPLATES` 静态列表，前端只能浏览不能编辑；自定义模板则是 `Asset(category=template)`，两条链路没有合并。
- 直接修改系统静态模板会变成全局变更，不适合多用户和项目场景；更稳妥的做法是用用户级 Asset 覆盖层保存定制内容，同时保留系统模板稳定 ID。
- 模板匹配和智能分镜不能只看静态列表，否则前端“编辑系统模板”只是展示假象；本轮已让 `/storyboards/templates`、`/storyboards/templates/match` 和 `/storyboards/generate-smart` 共用合并后的模板列表。
- 系统覆盖资产如果也显示在自定义模板区域，会让用户误以为有两套模板；前端已按 `shot_template.system_template_id` 或 `system_override` 标签过滤，系统覆盖只在系统模板卡片上体现。
- 新增常用系统模板后，模板库覆盖了开场、人物登场、群像简报、反派压迫、救援逆转、结尾悬念、日常喜剧和调查推理，能更贴近个人/小团队动漫改编的高频制作场景。

## 2026-05-15 火山方舟 Agent Plan PDF 发现

- 用户提供的 PDF 明确说明 Agent Plan 是订阅式全模态套餐，支持文本生成、图像生成、视频生成、向量化和联网搜索 Harness，并采用 AFP 额度。
- Agent Plan 的核心接入差异是专属 Base URL：`https://ark.cn-beijing.volces.com/api/plan/v3`；文档多处强调接口路径包含 `/plan`，不能与普通方舟 API 混用。
- Agent Plan 使用专属 API Key；PDF 特别提示普通方舟 API Key 或 Coding Plan API Key 不能替代 Agent Plan Key。
- OpenAI 兼容工具示例使用 `@ai-sdk/openai-compatible`，baseURL 为 `/api/plan/v3`，文本模型包括 `ark-code-latest`、`doubao-seed-2.0-code/pro/lite/mini`、`deepseek-v3.2`、`deepseek-v4-flash-beta`、`deepseek-v4-pro-beta`、`glm-5.1`、`kimi-k2.6`、`minimax-m2.7`。
- 多模态 API 示例：图片生成使用 `/images/generations` 与 `doubao-seedream-5.0-lite`；视频生成使用 `/contents/generations/tasks` 与 `doubao-seedance-2.0`/`doubao-seedance-2.0-fast`，并支持 `generate_audio`、`duration`、`ratio`、`watermark` 等参数。
- PDF 还说明 Small 套餐不支持视频生成；文本/向量模型存在 AI 工具使用限制，平台 UI 需要提示用户不要把普通火山 Key 和 Agent Plan Key 混用。
- 由于普通火山和 Agent Plan 都可能有相似的 Seedance API model_id，前端选择视频模型必须传数据库配置模型 ID，而不是只传 API model_id，否则会串到普通火山 provider。

## 2026-05-16 AI 模型能力级配置发现

- 原 `LLMConfig.is_default` 是全局唯一默认；这会导致用户把视频模型设为默认时，文本/图像/语音默认被取消，不符合多能力平台的使用习惯。
- 前端 `/llm-config` 只展示 provider 和保存配置列表，缺少“文本/图像/声音/视频每类当前默认是什么、是否验证通过”的总览，用户无法判断实际会用哪个模型。
- 视频生成页已经有视频模型列表，但会混合未保存的模型目录候选和已保存配置；生产使用时必须明确区分并要求已验证配置。
- 语音合成页此前按 provider 硬编码 MiniMax/Volcano，未消费 LLM 配置中的 TTS 模型、默认状态和验证状态；这会让用户在 LLM 配置里配置了语音模型却看不到应用位置。
- 后端 TTS 生成只按 `api_provider` 找 Key，缺少 `model_config_id`，无法精准使用用户选择的 TTS 模型配置、base_url 和真实 API model。

## 2026-05-16 AI 模型能力贯穿复查发现

- 通用 `ModelCapabilitySelector` 已覆盖小说新建、小说详情、章节列表/详情、角色管理、实体库、分镜管理、极速向导和 workflow，但剧本管理页仍是明显漏口。
- 剧本管理页原“AI生成剧本”调用 `/coding-plan/storyboard`，并且旧实现包含离线模拟结果；这会绕过 `/scripts/generate` 的章节上下文、落库逻辑和用户选择的文本模型配置。
- `/coding-plan/*` 旧接口历史上强依赖前端传 `api_key`，不符合当前统一 LLM 配置架构；保留兼容 `api_key` 的同时，应默认走当前用户的文本模型配置。
- 前端 `api-client` 的 Coding Plan 方法也需要接收 `model_config_id`，否则后续页面复用这些方法时仍可能只用默认模型。
- 修复后，从章节改编剧本会强制选择小说章节并调用 `/scripts/generate` 直接落库；自定义描述技术分镜仍可使用 `/coding-plan/storyboard`，但会带入所选文本模型配置。

## 2026-05-19 短剧式动漫短视频一致性分析发现

- 当前工程已经具备一致性底座：Story Bible、StoryEntity、Character novel scope、Shot entity refs、PromptComposer、直生音视频 MediaJob、SubtitleTrack、Timeline、资产库和生产适配配置都已存在。
- 现有最大缺口不是“有没有字段”，而是缺一个强制的 Production Contract：每个镜头生成前应冻结人物、场景、道具、事件、对白、字幕、参考资产版本、seed、模型配置和审核状态。
- 短剧式短视频需要新增“集/场/镜头节奏”层：开场 3 秒钩子、核心冲突、爽点或反转、结尾悬念、下一集承接；这类节奏不应只靠普通分镜模板隐式生成。
- 红果短剧性质的内容更重视强情绪、强冲突、快速信息交代和连续追更；平台应把章节改编成“短视频单集目标”，而不是默认按小说章节等长铺开。
- Story Bible 需要升级为“状态机”：角色服装/伤势/关系/目标，道具持有人/破损/能量状态，场景时间/天气/空间结构，事件因果和已发生/未发生都要可校验。
- 当前 `story_prompt_context.py` 和 `consistency_context.py` 已能把人物、场景、道具、事件放入提示词，但缺少生成前硬校验和生成后差异检查；模型仍可能忽略约束。
- 对模型选择的结论：长文本/结构化任务用长上下文文本模型；角色/场景定稿图用图像模型；成本敏感批量镜头优先 Seedance 2.0 Fast；关键镜头可用 Seedance 2.0 Pro 或外部直生音视频；有对白/音效需求优先直生音视频或分步 TTS+合成；最终交付仍应走 Timeline/FFmpeg 渲染。
- Sora 2、Veo 3、Seedance 2.0 这类音视频直生模型适合短视频快速出草片，但不应替代资产锁定、字幕审阅、Timeline 和最终渲染；否则多镜头一致性不可控。
- Runway Gen-4 References 和 Kling Elements/Multi-image Reference 类能力说明：角色、地点、物体的一致性关键在参考资产，而不是更长 prompt；平台要把多视图角色图、场景图、道具图作为生成前置条件。
- 前端应增加“短视频出片模式”：用户选择小说/章节后，系统生成本集目标时长、情绪曲线、镜头节奏、钩子文案、结尾悬念、一致性缺失项和推荐模型路径。

## 2026-05-19 短视频 Production Contract 落地发现

- 采用轻量落地方案更稳：不新增 Episode/Contract 表，先把镜头合约写入现有 `Shot.extra_data.production_context.production_contract`，避免在当前脏工作树里扩大迁移范围。
- `Shot -> Storyboard -> Script -> Chapter -> Novel` 的反推链路已经足够支持短视频合约生成；章节来源主要来自 `Storyboard.content.chapter_id` 或 `Script.extra_data.chapter_id`。
- Story Bible 的 `extra_data` 可以承载状态机雏形：`character_states`、`costume_states`、`prop_flows`、`scene_states`、`forbidden_changes`；后续如需更强校验再演进为独立版本化状态表。
- 当前一致性校验适合分为阻断和提醒：缺 prompt/视觉描述、缺字幕属于生成前阻断；缺资产锁、多视图参考、关键帧、场景/道具/事件引用属于提醒并允许 DEV_MODE 降级。
- 模型路线需要在合约中可解释展示，不只是记录模型 ID；用户能看到文本、图像、静音视频、直生音视频、TTS、字幕和合成分别为什么用该默认模型。
- workflow 左侧新增轻量面板比新增整页更符合当前工作流：用户在任意步骤都能看到短视频出片就绪度，并可一键刷新镜头合约。
- 当前 P0 闭环仍不是最终生产级审核流：多人审核、生成后视频差异检测、真实参考图版本依赖图、道具状态自动推理和跨集状态机仍可作为 P1/P2 继续深化。

## 2026-05-20 实体统计发现

- 实体库顶部统计不能从当前展示列表派生；展示列表本身是用户操作视图，会被实体类型筛选、排序和分页限制影响。
- 统计的合理口径是“当前小说/章节/剧本/范围下可见实体总量”，其中默认范围应包含用户可复用全局实体；严格范围只在用户选择 `仅全局/仅小说/仅章节/仅剧本` 时启用。
- 统计接口必须定义在 `/entities/{entity_id}` 动态路由之前，否则 FastAPI 会把 `stats` 当成实体 ID。
- 前端需要向用户说明统计不受右侧类型筛选影响，否则选择“角色”后统计卡仍展示场景/道具/事件数量可能被误解为筛选失效。

## 2026-05-26 整部小说动画漫剧平台分析发现

- 当前平台已经覆盖小说导入/编辑、章节 AI、Story Bible、实体/资产、剧本、分镜、镜头、视频、直生音视频、TTS、字幕、Timeline、渲染包、模型配置、生产适配和数据分析，单集或单章节生产闭环基础较完整。
- 当前最大产品差距不是单点功能缺失，而是“整部小说连续剧集生产层”缺失：需要 Series Plan / Episode Plan，把小说拆成多集并管理每集剧情目标、承接关系、生产状态和批量任务。
- Quick Start 已能创建首集工程并自动刷新合约、直生音视频、编排清单和渲染包；但它仍是首集导向，不能对整部小说做多集规划和持续生产。
- Workflow 已能串联小说、章节、角色、剧本、分镜、镜头、视频、TTS、合成、导出，并有短视频出片模式；但它更像单集工作台，缺少多集生产看板和跨集状态继承。
- Story Bible、StoryEntity 和 Production Contract 已是关键一致性底座；下一阶段需要升级为状态机，明确角色服装/伤势/关系、道具持有人/状态、场景时间/天气/空间、事件因果的跨集状态。
- 资产库已有全局/小说/章节/剧本/实体作用域，但资产版本锁仍需成为生成前强制输入；否则角色形象、场景参考和道具 DNA 仍可能在多镜头/多集生成时漂移。
- 模型配置已经有多 provider、多能力默认、验证状态和 Agent Plan/Seedance 模型目录；下一步要把模型选择升级为任务策略：草稿/低成本/高质量/直生音视频/分步生成/云渲染可解释切换。
- 非专业用户仍会被大量专业页面分散注意力；需要“AI 制片助手”作为默认交互层，自动判断缺什么、用什么模型、下一步做什么、失败怎么恢复。
- 历史图片和视频不可播放的问题应上升为生产级媒体持久化能力：外部临时 URL 转存、文件巡检、缩略图和字幕 artifact 恢复、过期链接重拉或标记不可恢复。
- DEV_MODE、本地 artifact、adapter_ready、cloud_pending、rendered 等状态必须在 UI 中明确区分，避免用户把本地草稿或外部 payload 误认为真实生产成片。

## 2026-05-26 整书生产计划落地发现

- 第一版整书计划不需要新增表即可跑通：`Novel.extra_data.series_plan` 足以保存多集拆分、剧情控制、生产状态、模型路线和下一步动作；这降低了当前脏工作树下的迁移风险。
- 合理的 Episode 状态可以从既有产物推导：章节存在为 `planned`，剧本存在为 `script_ready`，分镜存在为 `storyboard_ready`，镜头存在为 `shots_ready`，视频/直生任务存在为 `media_generating`，成功媒体存在为 `media_ready`。
- 多集计划必须覆盖“章节顺序”而不是只按数量分组；测试已验证 4 章拆 2 集时分别覆盖前 2 章和后 2 章。
- 当前计划的剧情钩子/冲突/反转/悬念为规则生成，能提供生产入口和状态看板，但还不是真正的 AI 集纲；下一步应接 Story Bible 状态机，让 AI 生成跨集人物状态、事件因果和道具流转。
- 前端最自然入口是小说详情页，因为它已经有章节、角色、剧本、Story Bible 和模型配置上下文；Quick Start 可作为后续入口补强，不应阻断本轮 P0。

## 2026-05-26 生产控制闭环落地发现

- Story Bible 状态机适合先作为 `StoryBible.extra_data.state_machine` 的轻量层：它已经能把人物服装/状态、场景环境、道具流转和事件因果变成提示词硬约束，无需立刻引入复杂状态表。
- 资产一致性的关键不是只在镜头页手填 JSON，而是要有小说级“定稿包”：按 StoryEntity 聚合角色、场景、道具可锁定资产，再批量写入 Shot 和 MediaJob，才能保证工作流批量生成也继承同一套参考。
- 当前资产库已有全局/小说/章节/剧本/实体作用域，足以支持个人或小团队轻量生产；缺少定稿图时用 DEV_MODE 占位资产可以让流程可验证，但真实生产仍需要用户替换为正式参考图、多视图和声线。
- 媒体长期可播放问题应分成三类：本地 `/static` 文件存在、远端临时 URL、缺失本地文件。巡检接口按这三类返回，比前端盲目播放失败更可解释。
- AI 制片助手不应直接替代用户做高风险创作决策。当前自动补齐只执行安全项：生成资产占位、应用资产锁、刷新 Production Contract、转存远端媒体；剧本改写、批量重生、审核通过仍保留人工决策。
- 生产质量检查第一阶段可以基于现有结构化信息做“生成前质量门”：提示词、视觉描述、字幕、角色/场景/道具/事件、关键帧、资产锁和审核状态。真正的视频画面一致性检测仍需要后续接入视觉模型。
- Workflow 是当前最合适的生产控制入口：用户已在这里串联小说、章节、剧本、分镜、镜头、音视频、字幕、合成和导出；把 AI 制片控制台放在左侧能降低非专业用户跨页面寻找功能的成本。

## 2026-05-26 前端可见性补强发现

- 当前生产控制相关能力并非缺失，而是前端可见性不足：后端已有 `/production-control`、Story Bible 状态机和 workflow 质量检查，但用户主要只能在 workflow 左侧栏看到一小块面板。
- 最合适的补强方式不是再造一套后端，而是新增独立的 `/producer` 前端工作台，把 Story Bible 状态机、资产定稿包、媒体巡检、质量检查和 AI 制片助手集中成一个明确入口。
- 顶部导航和首页也需要同步出现入口，否则用户仍会把这些能力当成“藏在二级页面里的功能”。

## 2026-05-26 工作流与 AI 制片流程复核发现

- AI 制片中心如果只让用户选择 workflow，会破坏“从小说/章节开始制作”的心智；轻量动漫平台应默认先选择小说，再选择章节，最后自动匹配或创建该章节的工作流。
- 当前 workflow 页面可以逐步生成媒体、拼接和渲染，但完整成片链路不够显性。对非专业用户，应提供一个清晰的“本集草片”动作，按顺序执行制片检查、资产锁、短视频合约刷新、批量直生音视频、拼接、渲染预检和渲染包生成，并逐步展示成功/失败原因。
- 保持一致性的关键不是在 UI 上单独生成视频，而是确保生成前把 novel/chapter/script/storyboard/shot/dialogue/subtitle/asset locks/production contract 传入后端已有批量生成接口；前端需要把该链路呈现成一个明确流程。
- 复用 Quick Start 的自动出片链路最稳：已有后端接口已经会把镜头 Production Contract、资产锁、多视图参考、关键帧和字幕信息写入 MediaGenerationJob；本轮前端只需要把完整链路暴露成 AI 制片中心和 workflow 的标准动作。

## 2026-05-26 AI 制片模型调用复核发现

- 当前 `/workflow/{workflow_id}/generate-media-batch` 只支持 `direct_av_first`，并且在 DEV_MODE 下直接写入本地占位视频/音频 URL；它不会调用用户选择的视频模型生成真实视频，也不会调用用户选择的声音/TTS 模型。
- 前端 AI 制片只传了 `videoModelConfigId`，没有声音模型选择和 `audio_model_config_id` 参数；这会让用户误以为声音模型参与了生成，实际没有。
- 后端单镜头 `/video/generate` 已能按用户视频模型配置创建 VideoJob，`/tts/generate` 已能按用户 TTS 模型配置创建 TTSJob；更稳的修复是让 workflow 批量生成支持 `separate_video_tts`，复用这些任务模型语义，先落库并生成 DEV/真实任务，再由已有拼接接口合成。
- 修复后，`separate_video_tts` 会分别解析用户的视频模型配置和声音模型配置：视频任务写入 `VideoJob.extra_data.model_config_id/api_model_id/model_endpoint_id`，TTS 任务写入 `TTSJob.extra_data.model_config_id/api_model_id/provider_id`。
- 非 DEV 且视频模型无可用 Key 时会明确返回 422；云端视频任务处于 pending 时，接口返回 `ready_for_concatenate=false`，前端停止后续拼接/渲染并提示等待。
- 工作流页原“批量直生音视频”入口仍只传视频模型，容易绕开声音模型；已改为默认“批量生成视频和配音”，同步展示视频模型和声音模型选择。
- 无对白镜头如果不生成音频，会让连续短视频在某些镜头上断声；批量分步生成已加入旁白 fallback，让每个镜头都能进入 TTS 和字幕轨。

## 2026-05-27 题材预设库扩展发现

- 修仙/仙侠、武侠、玄幻、都市异能这类网文题材不能只用“动漫/奇幻”通用风格承接；分镜模板需要内置题材词、镜头结构、场景和关键道具，才能在智能生成时优先命中。
- 题材模板的匹配权重现阶段以 genre tag 和章节关键词为主，专项测试已覆盖修仙突破、武侠对决、玄幻秘境、都市异能觉醒，避免都落到通用动作模板。
- 默认实体和资产应按“全局可复用、用户可编辑”方式注入，而不是写死在前端；这样新小说选择某个题材时能复用通用角色、场景、道具、事件，也能后续降级绑定到具体小说。
- 模板库只展示标签不足以让用户确认模板是否适合当前小说，系统模板卡片增加关键词展示后，用户能直接搜索“雷劫、秘籍、秘境、地铁、监控”等题材触发词。

## 2026-05-27 逆天至尊多镜头视频漂移根因

- 当前真实数据里小说《逆天至尊》已有正确角色“孙剑”，但 StoryEntity 的规则抽取把“疼痛、狂喜、活着、阳光、年轻、瘦弱”等普通叙述词错误抽成 character，视频 prompt 随后把这些污染实体当成“角色规则”注入。
- 同时“孙剑/逆天至尊孙剑”可能被道具规则捕获，导致真正主角没有稳定进入人物一致性约束，反而被当成 prop 或被污染角色挤掉。
- 视频请求多数没有 `image_url`，也没有强制从角色头像、镜头图、资产版本锁或小说资产库回退参考图；对于视频模型来说，只有长文本 prompt 不足以保持人物脸型、服装、场景和画风一致。
- 原 `_resolve_video_seed()` 把 `shot_id` 纳入默认 seed，同一分镜的两个镜头会得到完全不同随机锚点；这会让同一分镜下的视频更像两个独立生成任务。
- Workflow 批量 `separate_video_tts` 分支没有使用 `/video/generate` 的最终一致性 prompt，只把 `_shot_generation_prompt(shot)` 发送给 SDK，因此 AI 制片/工作流批量生成比单镜头生成更容易漂移。
- 修复原则：视频生成前必须先构建“有效一致性包”，只允许当前小说真实角色或精确匹配角色进入人物规则；错误实体要过滤并记录；同一分镜共享 style_lock/series_seed；参考图优先来自镜头图、角色头像、资产锁和当前小说资产。

## 2026-05-27 整部小说级连续性发现

- 同一分镜一致性修复后，剩余核心风险转移到跨章节：原视频 `series_seed` 仍包含 `chapter_id/script_id/storyboard_id/model`，所以同一小说第二章会被当成新的视觉系列，无法天然承接第一章的人物形象和场景风格。
- 剧本生成已有前后章节、Story Bible、StoryEntity 和事件时间线基础，但这些上下文没有形成统一的小说级连续性包，分镜和视频各自拼 prompt，历史任务难以审计“为什么这一章这样生成”。
- Story Bible 状态机已经能描述人物服装/状态、场景天气光影、道具持有人/状态和事件时间线，是跨章节连续性的最佳来源；缺口是把上一章快照、当前章快照和最近事件线固定传入剧本、分镜、视频三层。
- 新的实现边界是平台级“可验证一致性”：每次生成都传入并保存 `novel_series_seed/chapter_seed/continuity_lock/state_machine_summary`，真实模型输出仍需要参考图、多视图、LoRA 或视觉检测继续增强。
- 小说级系列种子不应跟随临时视频模型变化，否则用户切换同类模型会把整部小说拆成多个视觉系列；模型 ID 应进入任务 metadata，章节/分镜/镜头 seed 再做局部派生。

## 2026-05-30 智能剧本链路根因

- 智能生成剧本的直接接口在 DEV_MODE 下可创建 Script；真正阻断“小说到视频”的问题出现在后续链路：智能分镜读取用户模板资产时，旧 SQLite 缺少 Asset 模型新增列，导致任意 Asset ORM 查询/插入都可能 500。
- Asset 表需要和当前 ORM 保持一致：除 `novel_id/chapter_id/script_id/entity_id` 外，还必须迁移 `entity_type/source_url/generation_params/version/is_locked/locked_at/locked_by/is_final/replaced_by_id/source_job_id/source_prompt`。其中 `source_url/generation_params` 已被默认动漫资产库使用，不能只存在于旧库而不在模型中。
- 对轻量化平台来说，不能要求用户先手动生成 Story Bible 才能得到一致性上下文。剧本生成的结构化摘要必须合并 `load_story_prompt_context()` 从小说简介和章节正文中抽取到的人物、场景、道具、事件，否则后续分镜、镜头、视频会缺少生产锚点。
- 视频生成历史已经保存 lineage，但即时生成响应原先只返回 task/job/status，会让前端在刚生成完成时无法展示绑定关系。即时响应和历史响应都应携带同一组 `novel/chapter/script/storyboard/shot` ID。

## 2026-05-30 章节生产链路重复剧本根因

- 章节、剧本、分镜天然是版本化内容：用户多次点击智能生成剧本或重试一键生成后，同一章节出现多份 Script 是合理状态，不应被后端当成唯一记录读取。
- `production-status`、`generate-storyboard`、`generate-all` 的旧实现使用 `scalar_one_or_none()` 查询 `Script.chapter_id == chapter_id`，一旦用户重试生成就会抛 `MultipleResultsFound`，前端只能看到不完整的 500 toast。
- 一键生成还有第二个一致性问题：即使前半段选中了已有剧本，后半段调用智能分镜仍会新建一份“自动改编脚本”，导致返回的 `script_id` 和实际分镜绑定脚本不一致。后续视频生成再沿分镜推导 lineage 时，用户会看到剧本/分镜链路错位。
- 当前修复选择“取最新版本继续生产”，符合前端列表按更新时间展示的心智，也保留用户旧版本；不做数据库唯一约束，避免破坏版本管理需求。
- 边角风险：非常早期数据可能只写 `Script.extra_data.chapter_id` 而没有填 `Script.chapter_id`。当前新增迁移已有 `Script chapter lineage migration`，若线上仍发现老剧本漏字段，应补一次数据回填，而不是在每个热路径里做宽松 JSON 扫描。

## 2026-05-30 角色智能提取 500 根因

- 角色智能提取的文本解析、去重和入库本身可以成功；500 出现在“提取后自动生成头像”的后处理阶段。
- 自动头像生成按角色逐个执行，失败时设计上应该吞掉异常并继续，让角色提取结果先落库。但旧逻辑在异常后执行 `rollback()`，随后继续复用同一批 ORM 对象读取 `char.avatar`。
- SQLAlchemy async 会话中，回滚会让已加载对象进入过期状态；在普通属性访问里触发懒加载会离开 greenlet 上下文，最终抛 `MissingGreenlet`。这类错误不能靠前端重试解决，必须避免回滚后复用过期对象。
- 稳定做法是：跨事务阶段只传递主键 ID，不传递 ORM 实例；每个阶段进入前重新查询需要的对象。角色提取现在按这个原则处理头像循环和最终响应。

## 2026-05-31 轻量生产闭环审计发现

- AI 制片中心已经有生产控制能力，但缺少一个用户能立即理解的“当前能不能出片”信号；短视频就绪度应作为前端第一屏信息，直接展示镜头数量、总时长、阻断项和下一步。
- 工作流对非专业用户不应成为前置概念。选择小说和章节后，一键草片动作可以自动创建本集工程，再把剧本、分镜、镜头、媒体和发布产物挂到同一条链路。
- 前端继续制作参数必须统一：目标页只识别 `script_id/storyboard_id` 时，来源页继续使用 `script/storyboard` 或死链 `/scripts/new` 会让用户误判为功能不可用。
- “生成分镜”不能只是创建空 Storyboard。对小团队来说，按钮语义必须兑现为“剧本 -> 分镜 -> 镜头”可继续生产的结构化产物。
- 发布记录不是只保存 JSON。用户关心的是几天后还能打开视频、字幕和导出包，所以 `Publication` 必须保存最终可播放 `video_url`，并且前端打开 `/static/...` 时必须访问后端静态服务。
- `/synthesis/execute` 的真实合成路径原先没有写入 `SynthesisJob.video_url`，和模型非空约束冲突；这是生产闭环里比 UI 展示更底层的落库风险。

## 2026-06-05 Quick Start 与整书计划入口发现

- 整书多集计划能力已经落在小说详情页，但 Quick Start 完成后的默认后续入口仍是“打开作品/审核分镜/进入工作流/查看脚本”，用户容易继续停留在首集生产语义里。
- 对个人或小团队来说，首集向导完成后最自然的下一步不是再手动找章节或工作流，而是直接进入整部小说的多集生产计划，确认章节拆集、剧情钩子、承接关系和每集生产状态。
- 小说详情标签页需要支持 URL 参数激活；否则从 Quick Start、AI 制片、控制台、任务中心等跨页面跳转都只能落到默认章节标签，整书计划会像“已经实现但前端不可见”。
- 本机验证环境发现 nvm/Codex 的 Node 加载 Next SWC 原生模块会触发 macOS Team ID 校验失败；Homebrew Node 22 可正常加载，后续前端构建/E2E/服务启动应优先使用该 PATH，避免误判业务代码失败。

## 2026-06-05 多视图资产制片与低门槛编辑发现

- 角色三视图、场景四视图、道具多视图如果只作为普通 Asset 存在，用户很难判断它们是否属于某部小说、某个角色/场景/道具；必须通过 `StoryEntity` 绑定 `entity_id/entity_type`，并把 `view_key/view_label` 写入生成参数，才能被后续镜头和视频一致性链路稳定复用。
- 资产版本锁不能只按实体互斥；角色正面、侧面、背面都可能同时是定稿。合理互斥范围是“同一实体 + 同一视图 key”，否则锁定正面会误解锁侧面和背面。
- 资产编辑页原先默认展示变量配置、视图配置、生成参数 JSON 和英文内部值，适合工程调试但不适合非专业创作者。普通路径应只展示名称、归属、上传/预览、说明、AI 提示词和公开状态，高级字段按需展开。
- 前端资产页需要一个显眼的 AI 制片向导，而不是让用户先理解资产表结构；用户只需要选择小说、对象类型、小说对象和风格，然后生成缺失视图。
- 资产列表中的 `image/character/prop` 等内部值会持续制造“后台配置感”；能映射的类型和实体都应显示中文业务标签。
- 已补齐实体库、分镜镜头编辑页、视频生成前预检、题材化模板示例、多视图失败记录和重试入口；剩余真实生产增强集中在真实多图参考/LoRA/视觉检测模型接入。

## 2026-06-05 Phase 242 多视图前端可见性复核

- 实体库、分镜详情和镜头编辑弹窗现在都能展示角色/场景/道具的多视图定稿状态，用户不需要进入高级 JSON 才能判断参考资产是否缺失。
- Phase 243 已把同一套状态前置到视频生成按钮前：缺角色正侧背、场景全景/布局/光影、道具主视图时提示风险和“去补齐”，但不在 DEV_MODE 中硬阻断完整流程。
- Phase 244-246 已补齐题材化模板示例预览、生成失败记录/重试入口和轻量视觉一致性分数写回；下一步缺口是把真实视觉检测、多图参考模型或 LoRA 训练结果接入这些已可见的轻量入口。
