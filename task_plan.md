# 小说到动漫视频全流程优化计划

## 目标

实现逻辑合理、前后端一致的小说到动漫视频生成闭环：小说/章节、角色、分镜、镜头、参考图、配音、视频、合成、导出，并用统一模型配置支撑文本、图像、声音、视频能力。

## 假设

- 第一阶段先修复当前工程中阻断流程的接口和契约问题，不大规模重写业务模型。
- 现有未提交文件可能来自用户或前序生成，不回滚无关变更。
- 模型供应商继续沿用现有 LLMProvider/LLMModel/LLMConfig 架构，先补规划和关键字段一致性。

## 成功标准

- 前端正在调用的核心 API 不因路由未挂载而 404。
- synthesis、workflow、video、tts 的关键请求/响应字段前后端一致。
- 有明确的统一模型规划：文本、图像、声音、视频各能力如何选择 provider/model/default。
- 至少运行后端导入/针对性测试，记录结果。

## 任务拆分

- [x] Phase 1: 工程现状复盘与断点识别
- [x] Phase 2: 后端高优先级契约修复
- [x] Phase 3: 前端 API 调用契约修复
- [x] Phase 4: 统一模型规划文档与后续任务树
- [x] Phase 5: 验证与剩余风险清单
- [x] Phase 6: 统一模型注册表与任务默认模型 API
- [x] Phase 7: Story Bible 与 Prompt Composer 一致性核心
- [x] Phase 8: 生成任务绑定 project/workflow 并让 workflow 状态按关联任务返回
- [x] Phase 9: 前端类型检查修复与后端/前端验证
- [x] Phase 10: DEV_MODE 本地生成闭环与前端完整 E2E 修复

## Phase 10 验收标准

- 无真实云 API Key 时，DEV_MODE 能从前端完整跑通小说、章节、角色、剧本、分镜、镜头、TTS、视频、合成、任务中心查看。
- 前端不再把静态模拟数据或模拟测试结果标成真实成功。
- `/jobs` 展示后端真实任务聚合。
- Playwright E2E 自动设置认证状态，至少一个完整端到端流程通过。

## Phase 10 修复任务

- [x] 后端补齐 DEV_MODE 图片、TTS、视频、合成本地成功闭环，并回写 Shot/Workflow/Job。
- [x] 前端任务中心改为聚合真实 `/video/jobs`、`/tts/jobs`、`/images/jobs`、`/synthesis/jobs`。
- [x] 移除 LLM 配置、剧本 AI 生成、个人资料页的误导性模拟成功/示例数据。
- [x] 新增前端 E2E：注入 DEV token，经浏览器调用前端同源 API 完整创建小说、章节、角色、剧本、分镜、镜头、图片、TTS、视频、合成，并验证任务中心。
- [x] 运行后端 pytest、前端类型/构建、Playwright 完整流程。

## 2026-05-10 深度分析新增阶段

- [x] Phase 11: 重新审计小说导入、章节编辑、角色/场景/道具/事件抽取、一致性资产链路。
- [x] Phase 12: 重新审计前端完整流程页面和阻断点。
- [x] Phase 13: 重新审计模型配置、项目权限、合成导出发布。
- [x] Phase 14: 输出达到可用标准的 P0/P1/P2 优化任务和验收标准。

## Phase 11-14 成功标准

- 明确当前工程哪些能力已经具备、哪些只是 DEV_MODE 或占位。
- 明确外部小说导入、实体抽取、Story Bible、一致性参考资产、章节到分镜、模型配置、权限、发布导出的缺口。
- 更新 `docs/novel-to-anime-optimization-plan.md`，形成可直接拆分实施的任务清单。
- 不把当前原型误判为生产可用。

## 2026-05-10 自动实施阶段

- [x] Phase 15: 修复当前阻断点：章节参数、小说封面生成、静态媒体服务。
- [x] Phase 16: 实现外部小说导入：上传、预览、确认导入、导入任务记录。
- [x] Phase 17: 实现统一实体抽取：角色、场景、道具、事件，并支持 Story Bible 自动生成/同步/一致性检查。
- [x] Phase 18: 强化参考资产：实体资产字段、图片生成自动入库、Shot/Character 资产回写。
- [x] Phase 19: 强化项目权限：项目成员真实接口、owner/editor/viewer 角色校验、团队页接真实数据。
- [x] Phase 20: 实现成片导出发布：合成输出文件、发布记录、下载/分享入口。
- [x] Phase 21: 全量验证：后端 pytest、前端 tsc、前端 E2E 全流程。

## 2026-05-11 智能分镜自动化阶段

- [x] Phase 22: 预制分镜/镜头模板库，支持按小说题材、章节内容、叙事意图自动匹配模板。
- [x] Phase 23: 后端支持从小说/章节一键生成分镜与镜头，自动填充视觉描述、台词配音、镜头角度、运镜、情绪、光线、调色、音效和配乐提示。
- [x] Phase 24: 前端分镜管理页增加“从小说/章节智能生成”入口，展示匹配模板和生成参数，生成后进入人工审核修改。
- [x] Phase 25: 补充模板匹配和智能生成测试，确保 DEV_MODE 下无云密钥也能跑通。

## Phase 22-25 成功标准

- 模板作为后端能力暴露，不再只是前端静态样例。
- 智能生成可以直接选择小说或章节，不要求用户先手工创建剧本。
- 生成出的 Shot 必须包含可用于后续图片、TTS、视频的核心字段。
- 人工仍可在现有分镜/镜头编辑界面确认和修改细节。

## 2026-05-11 章节 AI 编辑与连续性阶段

- [x] Phase 26: 章节生成逻辑统一接入小说描述、前后章节、Story Bible、角色/场景、道具、事件上下文。
- [x] Phase 27: 章节编辑页支持 AI 重写、续写、润色，生成结果直接持久化到数据库。
- [x] Phase 28: 章节编辑页支持手工编辑自动保存，避免内容只存在前端内存。
- [x] Phase 29: 补充章节 AI 后端测试和前端 E2E，验证无云密钥 DEV_MODE 下可跑通。

## 2026-05-11 视频链路连续性阶段

- [x] Phase 30: 审计视频生成、TTS、合成与 workflow 的小说/章节/剧本/分镜/镜头关联链路。
- [x] Phase 31: 后端补齐视频任务 lineage 推导、章节关联、链路不匹配校验和任务响应字段。
- [x] Phase 32: 前端视频生成页补齐小说、章节、剧本、分镜、镜头级联选择和自动 prompt/参考图填充。
- [x] Phase 33: 补充后端与前端 E2E，验证从章节镜头进入视频生成后关联字段完整落库。

## 2026-05-11 多镜头连续成片与竞品对标阶段

- [x] Phase 34: 联网调研 Runway、Kling、Luma、Pika、PixVerse、Animaker、Vyond、Canva、Adobe Firefly 等动漫/AI 视频制作平台能力。
- [x] Phase 35: 后端实现 workflow 级多镜头连续成片 manifest：按镜头顺序编排视频、配音、字幕、转场、血缘和一致性元数据。
- [x] Phase 36: 前端 workflow 合成步骤展示连续成片编排结果、镜头/配音数量、字幕/转场/混音策略和 manifest 链接。
- [x] Phase 37: 补充多镜头成片后端测试、前端类型/构建验证，并记录仍需真实渲染服务接入的生产差距。

## 2026-05-11 全流程竞品深度对标与易用性规划阶段

- [x] Phase 38: 补充全流程平台对比：Runway/Kling/Luma/PixVerse/Pika/Firefly、Vyond/Animaker/Powtoon/Renderforest、Canva/Kapwing/InVideo、数字人口播平台。
- [x] Phase 39: 梳理可借鉴的动漫题材模板、分镜模板、镜头参数、字幕/音频/发布预设，并写入优化计划。
- [x] Phase 40: 审计核心资源新增/修改/删除能力，列出后端缺失 API 和前端缺失入口。
- [x] Phase 41: 实施 P0 易用性和 CRUD 补齐：新手极速向导、实体管理台、自定义模板库、任务中心 CRUD、发布中心 CRUD。

## 2026-05-12 Phase 41 落地结果

- [x] 新增 `/quick-start` 极速向导：一次创建小说、首章、Story Bible、智能分镜和工作流，并提供作品、分镜、脚本、工作流后续入口。
- [x] 顶部导航新增“极速向导”，工具菜单保留实体库、模板库、任务队列、发布相关入口。
- [x] 实体管理台支持手工新增、编辑、删除角色/场景/道具/事件。
- [x] 自定义模板库支持系统模板浏览、自定义模板新增、编辑、归档。
- [x] API client 补齐 `generateSmartStoryboard`、扩展 `startWorkflow` 链路参数、补齐 `updatePublication`。
- [x] 任务中心 CRUD、发布中心 CRUD、导入任务归档/重试等后端能力已由前序阶段落地；本轮验证其前端入口可用。

## 2026-05-12 生成级生产化稳定阶段

- [x] Phase 42: 后端补齐 workflow 成片渲染预检、缺失项诊断、可重试本地渲染包输出。
- [x] Phase 43: 前端 workflow 合成/导出步骤展示渲染预检、渲染包、字幕/时间线 artifact、失败重试入口。
- [x] Phase 44: 补充生成级后端测试和浏览器 E2E，验证 DEV_MODE 下从多镜头 manifest 到渲染包可稳定跑通。

## 2026-05-12 Phase 42-44 落地结果

- [x] 新增 workflow 渲染预检接口：检查 synthesis manifest、segments、视频 URL、字幕轨和音频缺失降级策略，并返回结构化 issue。
- [x] 新增 workflow 本地渲染包接口：可重试生成 render manifest、timeline EDL、SRT 字幕和 HTML preview，并回写 SynthesisJob 与 Workflow metadata。
- [x] Workflow 合成步骤展示“渲染预检与本地渲染包”，支持预检、生成、重新渲染和 issue/artifact 展示。
- [x] Workflow 导出步骤优先使用 HTML preview，并展示成片清单、SRT、时间线 EDL、渲染清单入口。
- [x] 浏览器 E2E 覆盖从多镜头 manifest 到预检通过、生成渲染包、展示 artifact 链接。

## 2026-05-12 生产一致性贯穿修复阶段

- [x] Phase 45: 分支/合并状态核验，确认前序优化是否已经进入当前 `main`。
- [x] Phase 46: 后端把小说 StoryEntity/Story Bible 的人物、场景、道具、事件、环境绑定到分镜和镜头。
- [x] Phase 47: 后端视频生成使用镜头绑定实体、场景、角色和字幕上下文，并在任务响应中透出。
- [x] Phase 48: 前端分镜/视频生成页面展示一致性上下文、角色/场景/道具/事件引用和字幕轨。
- [x] Phase 49: 后端测试与浏览器 E2E 验证角色/场景/字幕链路稳定。

## 2026-05-12 Phase 45-49 落地结果

- [x] 当前分支为 `main`，`workflow-fixes` 与 `worktree-agent-a9b328a1` 都是 `main` 的祖先；前序可见分支已合入本地 `main`。本地 `main` 领先远端且工作树有大量未提交改动，未做危险合并。
- [x] 智能分镜生成会自动加载或抽取 StoryEntity，并把人物、场景、道具、事件和环境上下文写入 Shot。
- [x] 视频生成会把 Shot 的 `character_refs/entity_refs/subtitle_text/environment_context` 注入最终 prompt，并透出到 VideoJob 响应。
- [x] 视频生成页显示当前镜头的“人物/场景/道具/事件/环境/字幕”，生成历史也展示视频任务的一致性上下文。
- [x] 实体抽取清洗规则已收紧，避免 `角色：沈砚。场景：...` 被错误合并成一个人物名称。

## Phase 45-49 成功标准

- 当前可见优化分支必须明确是否已合入 `main`；如果未合入，不能在脏工作树上盲目合并。
- 智能分镜生成出的 Shot 必须包含可追踪的 `character_refs` 和 `extra_data.entity_refs/scene_refs/prop_refs/event_refs/environment_context/subtitle_text`。
- 视频生成必须从 `shot_id/storyboard_id` 推导小说、章节、剧本、分镜、镜头，同时把人物、场景、道具、事件、环境、字幕写入最终 prompt 和 VideoJob extra_data。
- 前端必须能在视频生成页看到“本镜头一致性上下文”和字幕文本，不再只显示孤立 prompt。
- DEV_MODE 下至少一条后端测试覆盖实体绑定到镜头再到视频任务，至少一条浏览器 E2E 覆盖页面可见的一致性上下文。

## Phase 42-44 成功标准

- workflow 渲染前必须检查：是否已有 synthesis manifest、视频段落是否完整、视频 URL 是否存在、字幕轨是否可生成、音频缺失是否降级为静音策略。
- 渲染执行必须产生可下载的本地 artifact 包：render manifest、timeline EDL、subtitle SRT、HTML preview/output；并回写 SynthesisJob 与 Workflow metadata。
- 渲染失败/预检失败必须有结构化 issue 列表，前端能展示并阻止继续导出。
- 用户可从 workflow 页面一键执行渲染和重试，不需要手工打开 JSON。
- 无云密钥 DEV_MODE 下后端专项测试、前端构建/类型检查和至少一条浏览器 E2E 通过。

## Phase 26-29 成功标准

- 章节 AI 生成不能只基于孤立 prompt，必须读取小说、前后章节和 Story Bible/实体上下文。
- AI 重写、续写、润色后的章节内容、字数、状态、更新时间必须立即落库。
- 章节编辑页所有正文/标题改动应自动保存，保存状态在界面可见。
- 生成后可继续进入实体抽取、Story Bible 同步、分镜模板匹配等后续流程。

## Phase 30-33 成功标准

- 视频生成必须能从小说、章节、剧本、分镜、镜头任一入口补全上游关联，并拒绝不匹配的组合。
- 前端视频生成页必须提供清晰的级联选择，不再只依赖手填 prompt 或孤立 shot_id。
- 生成任务、任务历史、workflow 状态必须返回 `novel_id/chapter_id/script_id/storyboard_id/shot_id` 及标题/序号等可追踪信息。

## 2026-05-19 小说/剧本连续性优化计划

- [x] Phase 64: 后端剧本生成统一接入 `load_story_prompt_context()`、Story Bible、StoryEntity production pack、人物关系和事件时间线，修复前情章节选择逻辑。
- [x] Phase 65: 剧本生成结果写入完整 `extra_data.generation_context`，包含 `story_bible_id`、`model_id/provider`、`prev_chapter_id/next_chapter_id`、`characters/scenes/props/events/relationships` 摘要、上下文版本时间。
- [x] Phase 66: 补齐剧本一致性检查接口，针对剧本文本检查未登记人物、章节时序矛盾、场景/道具状态冲突、对白角色不存在、事件线断裂。
- [x] Phase 67: 前端剧本生成弹窗展示“将使用的小说上下文”：人物、场景、道具、事件、人物关系、章节承接和模型配置状态；生成失败展示具体原因。
- [x] Phase 68: 小说详情页补齐“章节到剧本”生产看板：每章是否已有剧本/分镜/镜头/视频，支持一键从指定章节生成剧本、同步 Story Bible、检查一致性。
- [x] Phase 69: 测试覆盖：中间章节生成剧本不能引用后续章节作为前情；剧本 prompt 必须包含 Story Bible、人物关系、事件线、关键道具；前端能按小说/章节完成生成链路。

## 2026-05-19 Phase 64-69 落地结果

- [x] 剧本生成会读取小说、当前章节、上一章、下一章、Story Bible、StoryEntity、人物关系、场景/道具/事件线和一致性 prompt。
- [x] 中间章节改编时，上一章只作为前情，下一章只作为不可矛盾的后续约束。
- [x] 剧本生成结果持久化 `scripts.chapter_id` 和 `extra_data.generation_context`，后续分镜、镜头、TTS、视频可继承同一套上下文。
- [x] 剧本详情支持一致性检查和版本快照/恢复；剧本列表生成弹窗展示上下文预览与生成后一致性检查。
- [x] 小说详情页展示章节生产看板，按章显示剧本、分镜、视频产物，并支持从指定章节生成剧本。
- [x] 修复 `/scripts?novel_id=...&chapter_id=...` 初始章节筛选会被清空的问题，确保从小说详情进入剧本生成时不会默认回到第一章。
- [x] 验证通过：后端全量 `pytest -q` 127 passed、1 skipped；前端 `npm run build` 和 `npx tsc --noEmit` 通过；新增浏览器回归 `script generation shows chapter continuity context and consistency check` 通过。

## Phase 64-69 成功标准

- 剧本生成不能只基于章节正文，必须强制读取小说、当前章节、前后章节、Story Bible、人物关系、场景/道具/事件线。
- 改编中间章节时，前情只能取当前章之前的章节；后续章节只能作为“不可矛盾的后续约束”，不能被写成已经发生的前情。
- 生成出的剧本必须保留可追踪上下文元数据，后续分镜、镜头、TTS、视频能继承同一套角色/场景/道具/事件。
- 前端用户在点击生成前能看到当前选择的模型配置、小说/章节、已有 Story Bible 和关键实体摘要。
- 至少新增一条后端测试和一条浏览器 E2E，覆盖章节镜头到视频任务的完整关联落库。

## 2026-05-27 分镜与角色生成修复阶段

- [x] Phase 70: 分镜管理补齐整分镜删除入口，后端删除时显式清理所属镜头。
- [x] Phase 71: 分镜管理补齐显式“从剧本 AI 生成分镜和镜头”入口，避免能力只藏在新建弹窗中。
- [x] Phase 72: 角色提取按用户 + 小说范围 + 角色名排重，重复提取时更新已有角色而不是新建重复记录。
- [x] Phase 73: 角色头像生成改为专用接口，提示词读取角色描述、外貌、性格、标签、小说简介和题材，并约束性别/年龄/身份一致。
- [x] Phase 74: 小说封面错误提示与提示词上下文加强，前端展示后端具体失败原因。
- [x] Phase 75: 补充后端专项测试和前端类型/构建验证，重启前后端服务。

## 2026-05-27 参考图公网交付能力阶段

- [x] Phase 76: 在生产适配配置中新增“对象存储/CDN”能力，支持公开静态媒体出口配置。
- [x] Phase 77: 后端视频生成把本地 `/static/...` 参考图按用户默认存储配置解析为公网 URL，再传给云端图生视频。
- [x] Phase 78: 前端生产适配页展示对象存储/CDN配置入口、状态和应用说明。
- [x] Phase 79: 补充回归测试，覆盖无配置时安全降级、有配置时传公网参考图、工作流批量生成同样生效。

## Phase 76-79 成功标准

- 未配置对象存储/CDN时，现有行为保持：本地参考图不传云端，避免火山 400。
- 配置默认对象存储/CDN且公网基础地址有效时，`/static/...` 参考图会转换成公网 URL 传入视频模型。
- 任务历史保留原始本地参考图，同时记录实际传给供应商的 `provider_image_url`、交付方式和配置ID。
- 前端能在“生产适配”看到并配置该能力，用户知道它用于角色头像、镜头参考图、资产参考图参与云端图生视频。

## 2026-05-27 Phase 70-75 落地结果

- [x] `/storyboards/{id}` 删除接口会显式删除该分镜下的镜头，并返回删除镜头数。
- [x] 分镜页列表卡和详情页新增“删除分镜”，详情页新增“从剧本生成”，空态和页头提供更明显的智能生成入口。
- [x] `/characters/extract` 会按同用户、同小说、同名角色排重，重复提取时合并描述、外貌、性格、声音和标签。
- [x] 新增 `/characters/{id}/generate-avatar`，由后端统一构造角色头像提示词并回写头像；前端创建后自动头像和手动头像都改走该接口。
- [x] 小说详情封面生成失败会展示后端具体 `detail`，成功提示说明已使用小说上下文。
- [x] 验证通过：`python3 -m compileall app`；`pytest -q test_character_scope.py test_storyboard_templates.py test_workflow_routes.py` 39 passed；前端 `npx tsc --noEmit`、`npm run build`、构建后再次 `npx tsc --noEmit` 通过；`git diff --check` 通过。

## 2026-05-27 题材预设库扩展阶段

- [x] Phase 76: 基于修仙、武侠、玄幻、都市异能题材补充分镜风格与系统模板。
- [x] Phase 77: 补充全局默认资产与实体预设，包括角色、宗门/门派/城市/秘境场景、法宝/秘籍/灵核等道具、突破/比武/秘境/都市觉醒事件。
- [x] Phase 78: 前端分镜风格选择增加题材化风格，方便用户快速选择。
- [x] Phase 79: 补充后端模板匹配和默认库测试，验证新预设会出现在模板库、资产库和实体库。
- [x] Phase 80: 运行编译、测试、前端类型/构建，并重启服务。

## 2026-05-27 Phase 76-80 落地结果

- [x] 系统分镜模板新增修仙突破/雷劫、宗门审判、武侠江湖对决、武侠夜探门派、玄幻秘境探索、玄幻血脉觉醒、都市异能觉醒、都市夜巷追查。
- [x] 默认实体库新增少年剑修、宗门长老、江湖剑客、血脉继承者、都市异能者，以及仙门山门、修炼洞府、江湖客栈、竹林山道、古遗迹秘境、城市地铁、隐藏实验室等全局可复用实体。
- [x] 默认资产库新增修仙宗门场景包、修仙突破提示词、武侠江湖场景包、武侠刀剑对决提示词、玄幻秘境场景包、玄幻血脉觉醒提示词、都市异能场景包、都市异能觉醒提示词。
- [x] 前端分镜风格下拉新增修仙/仙侠、武侠江湖、玄幻冒险、都市异能、东方幻想、现代都市；模板库系统卡片展示关键词，便于快速筛选题材模板。
- [x] 验证通过：`python3 -m compileall app`；`pytest -q test_storyboard_templates.py test_asset_templates.py test_story_entity_production_pack.py` 19 passed；前端 `npx tsc --noEmit`、`npm run build`、构建后再次 `npx tsc --noEmit` 通过；`git diff --check` 通过。

## Phase 76-80 成功标准

- 智能分镜模板库至少包含修仙突破、宗门审判、武侠江湖对决、玄幻秘境探索、都市异能觉醒、现代城市追查等题材模板。
- 模板匹配能根据小说题材和章节关键词优先选中对应题材模板，而不是都落到通用动作/对话模板。

## 2026-06-05 低门槛多视图资产制片规划

- [ ] Phase 81: 审计资产库、角色/实体、多视图生成和前端资产页，确认多视图没有形成小说实体级创作者流程。
- [ ] Phase 82: P0 后端补齐统一资产视图预设与按实体生成视图契约：角色三视图、场景四视图、道具多视图。
- [ ] Phase 83: P0 前端资产页增加“AI 资产制片向导”：选择小说、选择角色/场景/道具，展示缺失视图、预览、AI 生成、上传补图和锁定定稿。
- [ ] Phase 84: P0 前端资产编辑降噪：默认隐藏 JSON/变量/生成参数等高级字段，使用中文业务标签和预设选择替代技术配置。
- [ ] Phase 85: P0 验证：后端多视图契约测试、前端类型检查、构建和资产页 E2E。
- [ ] Phase 86: P1 批量补齐整部小说资产包：一键为主要角色/核心场景/关键道具生成缺失视图，并把锁定资产注入分镜、镜头、视频生成。
- [ ] Phase 87: P1 前端生产引导：在工作流/AI 制片中加入“资产准备度”步骤，未锁定三视图或场景/道具参考时给出可操作提示。
- [ ] Phase 88: P2 生产增强：一致性评分、多版本对比、多人审核、LoRA/ComfyUI/对象存储/CDN 深度接入。

## Phase 81-85 成功标准

- 普通创作者不需要填写 JSON，也能完成“小说 -> 实体 -> 多视图资产 -> 锁定定稿”的最小闭环。
- 角色资产必须可追踪到小说角色或 StoryEntity，不能只是全局孤立图片。
- 生成资产必须写入 `novel_id/entity_id/entity_type/category/source_prompt/generation_params.view_key`，后续镜头和视频生成可以稳定取用。
- 资产页应能清楚展示每个实体的必备视图是否已完成、是否已锁定、是否可预览。
- 后端和前端验证必须覆盖多视图预设、生成落库、资产页关键 UI 可见和构建类型检查。
- 默认资产/实体库提供可编辑的题材资产和实体，用户打开资产库/实体库时能复用到新小说。
- 前端分镜风格下拉能直接选择修仙、武侠、玄幻、都市异能等风格。

## Phase 70-75 成功标准

- 用户可在分镜列表或详情页删除多余分镜，删除后关联镜头不残留。
- 用户可在分镜详情页直接从当前剧本生成新的分镜和镜头，或在空态一键进入智能生成。
- 同一小说内重复提取同名角色不会产生重复角色；同名角色跨小说仍保持隔离。
- 角色头像生成不再由前端手拼英文 prompt，后端统一构造包含小说与角色上下文的中文提示词，并在 DEV_MODE 无 Key 时可返回本地头像。
- 小说封面生成继续使用小说简介、主角、场景、道具、事件上下文；失败时前端显示具体原因。

## Phase 34-37 成功标准

- 不再用第一个视频 URL 冒充最终视频；合成任务必须包含 ordered timeline/segments。
- 每个 segment 必须保留 `video_job_id/tts_job_id/shot_id/novel_id/chapter_id/script_id/storyboard_id`、镜头序号、视频 URL、音频 URL、字幕文本、时长、转场和一致性上下文。
- DEV_MODE 下生成本地 `manifest_url` 和 `output_url`，前端可看到连续成片已完成，并能进入合成任务/发布导出链路继续验证。
- 对标竞品缺口要沉淀为后续开发任务：参考资产库、关键帧/多图参考、镜头时间线、唇形/配音、字幕、协作、导出、供应商模型配置。

## Phase 38-41 成功标准

- 对比矩阵必须覆盖 AI 视频生成平台、在线动画制作平台、通用编辑发布平台、数字人口播平台四类。
- 优化清单必须不仅列“功能名”，还要说明对本平台流程的影响：输入、AI 辅助、人审点、输出、可验证结果。
- 模板规划必须覆盖题材模板、分镜模板、镜头参数、音频/字幕/发布预设，并支持系统模板与项目模板区分。
- CRUD 审计必须明确后端 API 缺口和前端入口缺口，删除策略优先采用软删除/归档/恢复。
- 易用性优化必须降低新用户门槛：极速模式、专业模式、团队模式、示例项目、AI检查缺失项、一键继续下一步。

## 本轮成功标准

- `/api/v1/llm/registry`、`/api/v1/llm/task-defaults` 能返回文本、图像、声音、视频任务的统一模型规划。
- Story Bible 可按项目/小说创建、读取、更新，并能组合角色、镜头和一致性设定生成稳定 prompt。
- Video/TTS/Synthesis 任务可保存并返回 `project_id`、`workflow_id`，workflow 状态优先返回当前 workflow 关联任务。
- `python3 -m compileall app`、核心 pytest、前端 `npx tsc --noEmit` 通过，外部云模型调用不作为无密钥环境的强制验证项。

## 错误记录

| 问题 | 处理 |
| --- | --- |
| `python` 命令不存在 | 使用 `python3 -m compileall app` 完成后端语法验证 |
| `npm run lint` 首次运行进入 Next.js ESLint 配置交互 | 改用非交互的 `npx tsc --noEmit` 做前端类型检查 |
| `npx tsc --noEmit` 报 `AuthResponse.detail` 类型错误 | 记录为既有登录/注册类型问题，未纳入本次生成链路修复 |
| `pytest -q` 收集 `test_video_sdk.py` 时缺 `VOLCENGINE_API_KEY` | 改为 pytest module-level skip，避免无密钥环境阻断本地测试 |
| `test_api.py` 依赖已启动的 `localhost:8000` | 改为后端服务未启动时跳过外部集成测试，本地 TestClient 测试继续覆盖核心 API |
| `test_tts_requires_api_key` 与 DEV_MODE 无 Key 成功闭环冲突 | 改为验证非 DEV_MODE 且已认证时仍要求 API Key，保留生产保护 |
| `frontend/e2e/app.spec.ts` 未注入登录态导致业务页跳转 `/login` | 增加 DEV token 初始化，并修复“创建剧本”重复按钮导致的 strict mode 选择器问题 |
| `npx tsc --noEmit` 在 build 前缺 `.next/types` | 先运行 `npm run build` 生成 Next 类型，再重跑 `npx tsc --noEmit` |
| 新增导入/Story Bible E2E 的 `Story Bible` 文本选择器过宽 | 改为精确点击 `Story Bible (` 按钮，避免 strict mode 多匹配 |
| `npx tsc --noEmit` 发现 Radix dialog/dropdown/tooltip 缺失 | 补充 `@radix-ui/react-dialog`、`@radix-ui/react-dropdown-menu`、`@radix-ui/react-tooltip` 到前端依赖 |
| 前端 dev server 运行中执行 `next build` 后 E2E 500 | 重启 dev server 后重跑 E2E，后续避免 dev/build 并行操作同一 `.next` 目录 |
| 章节 AI E2E 首次返回 `Not Found` | 后端服务仍是旧进程，重启后端后新增 `/chapters/{chapter_id}/ai-assist` 生效 |
| 章节 AI E2E 并行时 alert 接受超时 | 放宽该用例超时并先保存 alert 文案再 accept，四条浏览器流程并行通过 |
| 多镜头成片专项测试中视频生成 422 | 智能分镜模板存在 2-3 秒镜头，而视频模型约束为 4-10 秒；模板生成已归一化到 4-10 秒，测试请求也按最小 4 秒提交 |
| `npm run build` 首次提示 workflow 页 `useSearchParams()` 需 Suspense | 将 workflow 页面主体拆为 `WorkflowPageContent`，外层默认导出使用 `Suspense` 包裹，构建通过 |
| 并行运行 `npx tsc --noEmit` 与 `next build` 时 `.next/types` 缺失 | build 会重建 `.next`，导致并行 tsc 读取中间状态；构建完成后单独重跑 tsc 通过 |
| Phase 41 E2E 编辑用例定位器超时 | 页面历史数据会导致文本过滤命中外层容器；为实体/模板编辑按钮补充稳定 `title`，测试改用 `getByTitle` |
| Phase 41 并行运行 `npx tsc --noEmit` 与 `next build` 再次出现 `.next/types` 缺失 | 复用既有处理方式：等待 `next build` 完成后单独重跑 `npx tsc --noEmit`，结果通过 |
| Phase 44 首次 E2E 点击“渲染预检”后弹窗失败 | 后端 8000 仍是旧进程，未加载 `/workflow/{id}/render/preflight`；重启后端后 curl 预检返回 200 |
| Playwright `webServer` 等待 120 秒超时 | 配置检查根路径 `http://localhost:3000`，当前根路径返回 404；改为检查稳定业务页 `/workflow` |
| `next build` 后前端 dev server 页面 JS chunk 404，workflow 查询参数未水合 | 重启前端 dev server 后确认 workflow status 请求正常，再重跑 E2E 通过；后续避免 dev/build 共用 `.next` |

## 2026-05-12 角色小说归属隔离阶段

- [x] Phase 50: 审计角色管理、小说详情、分镜/镜头、视频、TTS 的角色作用域链路。
- [x] Phase 51: 后端 Character 增加 `novel_id/chapter_id`，并通过迁移兼容已有 SQLite 数据库。
- [x] Phase 52: `/characters` 支持按小说/章节过滤，创建、更新和 AI 提取会校验并保存所属小说/章节。
- [x] Phase 53: 一致性上下文、视频生成和 TTS 多角色音色按当前小说优先匹配角色，避免跨小说同名角色串用。
- [x] Phase 54: 前端角色管理页支持小说范围筛选和创建归属，视频生成页随当前小说加载角色参考。
- [x] Phase 55: 补充角色作用域回归测试并完成后端/前端验证。

## Phase 50-55 成功标准

- 角色可以明确绑定小说；`/characters?novel_id=A` 默认不返回小说 B 或未绑定的全局角色。
- 小说详情页和角色管理页的新建/提取角色都能落到对应小说，不再进入所有小说共享池。
- 分镜/镜头生成按 StoryEntity 名称补角色资料时，优先使用同小说角色，不把另一部小说的同名角色形象注入镜头。
- 视频生成页选择小说后，角色参考下拉只展示该小说角色；切换小说会清空旧角色参考。
- TTS 多角色按名称取音色时，也只在当前小说范围内匹配同名角色。

## 2026-05-12 视频历史与一致性再修复阶段

- [x] Phase 56: 修复视频生成历史播放/下载：DEV_MODE 生成真实可播放本地 MP4，占位视频 URL 统一可被前端解析，下载按钮走后端代理。
- [x] Phase 57: 加固视频生成一致性：把分镜/剧本风格和说明注入 prompt，自动生成稳定 seed，并把 seed、duration、resolution 作为视频 SDK 顶层参数传入。
- [x] Phase 58: 回归验证：后端专项、前端类型/构建、浏览器视频链路测试通过，并重启前后端服务。

## Phase 56-58 成功标准

- 历史视频按钮不能再直接打开前端 origin 下的相对 `/static/dev/...` 路径；播放要使用后端可访问地址，下载要使用 `/api/v1/video/download` 代理。
- DEV_MODE 不能只返回一个不存在的 mp4 路径，必须实际落盘一个可播放本地视频文件。
- 视频生成任务必须保存并返回一致性 seed；真实 SDK 调用必须传入 `seed/duration/resolution` 等顶层参数。
- 最终 prompt 必须显式包含 Story Bible、人物/场景/道具/事件、字幕，以及分镜/剧本风格和视频一致性约束。

## 2026-05-13 动漫制作平台对标与音视频直生规划阶段

- [x] Phase 59: 对标互联网常见 AI 视频、在线动画、传统动画软件、剪辑字幕工具和 ComfyUI/ControlNet 等插件生态。
- [x] Phase 60: 审计当前工程对“直接音视频生成”和“字幕一等公民”的支持现状，区分已落地能力与仍是派生/占位的能力。
- [x] Phase 61: 制定生产级目标架构：统一 MediaGenerationJob、SubtitleTrack/SubtitleSegment、Provider capability registry、插件适配层和工作流批量编排。
- [x] Phase 62: P0 实施数据契约：在不破坏现有 VideoJob/TTSJob/SynthesisJob 的前提下，新增或兼容 `audio_url/subtitle_track_url/media_type/task_type/provider_capabilities`。
- [x] Phase 63: P0 实施字幕链路：从 Shot dialogue、TTS 分段、直接音视频模型返回、ASR 四类来源生成可编辑字幕轨，并导出 SRT/VTT/ASS。
- [x] Phase 64: P0 实施直接音视频生成：新增 `shot_audio_video` 任务，支持 Sora/Veo 类模型能力配置；无密钥 DEV_MODE 产出可播放视频、音频元数据和字幕 artifact。
- [x] Phase 65: P0 前端生产工作台：在视频生成、workflow、极速向导中提供“直生音视频”和“分步生成+合成”两种模式，展示字幕轨、音频状态、一致性检查和成本/时长预估。
- [x] Phase 66: P0 回归验证：后端单测覆盖 lineage/字幕/直生音视频 job，前端 E2E 覆盖从章节镜头到带字幕音视频草稿的完整路径。

## 2026-05-13 Phase 62-66 落地结果

- [x] 新增 `MediaGenerationJob`、`SubtitleTrack`、`SubtitleSegment` 模型，并为 SQLite 初始化增加兼容迁移。
- [x] 模型注册表新增 `shot_audio_video`、`subtitle_generation`，并登记 Sora/Veo 类直生音视频能力矩阵。
- [x] 新增 `/media/generate`、`/media/jobs`、`/subtitles/from-shot`、`/subtitles/from-tts`、`/subtitles/from-media`、字幕段编辑和 SRT/VTT/ASS 导出接口。
- [x] 新增 `/workflow/{workflow_id}/generate-media-batch`，DEV_MODE 下按分镜镜头批量生成直生音视频任务和字幕轨。
- [x] 视频生成页新增“静音视频 / 直生音视频”模式切换，直生成功后展示字幕轨、字幕导出入口和音视频直生历史。
- [x] 验证通过：后端专项 26 passed、前端构建和类型检查通过、Playwright 直生音视频用例通过。

## Phase 62-66 剩余边界

- 真实 Sora/Veo/其他直生音视频供应商尚未接入密钥与 SDK，只在 capability registry 中建模；无密钥环境走 DEV_MODE artifact。
- 字幕轨已可编辑和导出，但尚未接入完整可视化 Timeline 编辑器和真实 FFmpeg 字幕烧录。
- ComfyUI/ControlNet/IP-Adapter/AnimateDiff 插件适配、Live2D/口型和团队审核流属于 P1/P2，依赖本轮已落地的数据契约继续推进。

## Phase 59-66 成功标准

- 对标结论必须覆盖：Sora/Veo/Runway/Kling/PixVerse/Luma/Pika/Canva/Vyond/Animaker/Toon Boom/Clip Studio/Live2D/Blender/ComfyUI/ControlNet/IP-Adapter/AnimateDiff 等类型，而不是只列单点视频模型。
- 工程现状必须明确：当前已有视频、TTS、manifest、SRT artifact，但缺少直接音视频任务类型、字幕数据模型、字幕编辑工作台、直接音视频供应商能力路由。
- 直接音视频生成必须保留小说、章节、剧本、分镜、镜头、角色、场景、道具、事件、环境、seed、风格和字幕的完整 lineage。
- 字幕必须成为可编辑、可导出、可烧录/外挂的生产对象，不再只依赖 `Shot.extra_data.subtitle_text` 或 workflow manifest 中的临时字段。
- 前端必须能明确选择“直生音视频”或“分步生成视频+TTS+合成”，并在失败时提供可重试/可降级路径。

## 2026-05-13 全流程生产工作台对齐阶段

- [x] Phase 67: 审计前后端全流程能力对齐，确认 workflow 页面没有承接后端批量直生音视频、媒体任务和字幕轨状态。
- [x] Phase 68: 后端 workflow status 返回 `media_jobs/subtitle_tracks/metadata`，并允许连续成片直接消费 `MediaGenerationJob` 的直生音视频输出。
- [x] Phase 69: 前端 workflow 页面补齐上游链路回填、按产物解锁步骤、生产就绪检查、批量直生音视频入口和导出 artifact 引导。
- [x] Phase 70: 验证直生音视频从工作流批量生成、连续成片、渲染包和导出入口完整可用。

## Phase 67-70 成功标准

- 从 `/workflow?workflow_id=...` 进入时，页面必须自动恢复小说、章节、剧本、分镜链路，不再停留在孤立的新工作流状态。
- 步骤不能只按 `current_step` 灰掉；已有分镜、媒体任务或渲染包时，应按实际产物允许跳到视频、合成和导出步骤。
- workflow 页面必须能一键批量生成直生音视频，并显示媒体任务数、字幕轨数、生产就绪检查和 DEV_MODE/真实生产边界提示。
- 连续成片必须同时支持传统 `VideoJob + TTSJob` 和直生 `MediaGenerationJob`；直生任务的音频、字幕、lineage 必须进入 manifest/render/export。
- 浏览器 E2E 必须覆盖工作流页面批量直生音视频、生成连续成片、渲染包、导出入口。

## 2026-05-13 Phase 67-70 落地结果

- [x] `/workflow/status/{id}` 现在返回媒体任务、字幕轨和 metadata，前端可直接做生产就绪检查。
- [x] `/workflow/concatenate/{id}` 支持 `media_job_ids`，直生音视频任务会作为视频段落和音频轨进入成片 manifest，并保留字幕文本和上游链路。
- [x] workflow 页面按已有产物解锁步骤，修复有分镜/媒体任务时后续步骤仍灰色不可点击的问题。
- [x] workflow 视频步骤新增“批量直生音视频”，合成/导出步骤展示直生音视频计数、字幕轨、HTML 预览、SRT、时间线和渲染清单。
- [x] 左侧新增“生产就绪检查”，明确上游链路、镜头草稿、音频/配音、字幕轨、连续成片、渲染包状态，并提示真实供应商和 FFmpeg/云剪辑仍需生产适配。
- [x] 验证通过：`python3 -m compileall app`、`pytest -q test_media_subtitles.py test_workflow_routes.py` 26 passed、`npm run build`、`npx tsc --noEmit`、Playwright workflow 批量直生用例 1 passed。

## Phase 67-70 剩余边界

- 当前“生产就绪检查”是流程/产物层面的可用性检查，不等同于真实云生产上线认证。
- Sora/Veo/ComfyUI/FFmpeg 云渲染、字幕烧录、多人审核、资产版本锁定和 timeline 可视化仍是后续 P1/P2。

## 2026-05-13 P1/P2 提示词一致性深化阶段

- [x] Phase 71: 审计封面、章节、分镜对白、视频和直生音视频的提示词上下文来源，确认哪些链路仍使用孤立 prompt 或 DEV_MODE 占位文案。
- [x] Phase 72: 新增统一故事提示词上下文服务，复用 Novel、Chapter、Story Bible、StoryEntity 和 Character 组装人物、场景、道具、事件、章节承接和负面约束。
- [x] Phase 73: 封面生成改为自动注入小说题材、主要人物、关键场景、道具和事件；前端传入的封面 prompt 作为补充要求而不是覆盖上下文。
- [x] Phase 74: 章节生成和 DEV_MODE fallback 增强小说连续性上下文，确保章节正文承接题材、人物、场景、道具、事件、前后章节和后续分镜需要的信息。
- [x] Phase 75: 智能分镜模板对白从人物/场景/道具/事件生成，不再输出通用“（角色）片段”占位对白；AI 细化 prompt 明确传入实体清单。
- [x] Phase 76: 视频和直生音视频 prompt 增加动漫连续性硬约束，要求人物形象、场景、道具状态、事件结果和字幕对白与上游一致。
- [x] Phase 77: 补充专项测试并完成后端/前端验证。

## Phase 71-77 成功标准

- 小说封面 ImageJob.prompt 必须能追溯到同一小说的题材、人物、场景、道具、事件和用户补充要求。
- 章节 AI/DEV_MODE 草稿必须显式携带“小说连续性上下文”，并承接人物、场景、道具、事件和前后章节。
- 智能分镜生成的 dialogue 不能再是“（角色）...”占位，要使用具体人物名、道具或事件锚点。
- 视频/直生音视频最终 prompt 必须包含动漫连续性硬约束，约束人物形象、事件结果、道具状态、字幕对白和场景环境。
- 验证需覆盖 `python3 -m compileall app`、后端专项 pytest、前端 `npm run build` 和 `npx tsc --noEmit`。

## 2026-05-13 Phase 71-77 落地结果

- [x] 新增 `backend/app/services/story_prompt_context.py`，集中加载并压缩小说、章节、Story Bible、StoryEntity 和 Character 上下文。
- [x] `/novels/generate-cover` 与 `/novels/{id}/generate-cover` 统一使用故事上下文构建封面 prompt，前端小说详情页不再用简单 prompt 覆盖后端上下文。
- [x] 章节生成把连续性 block 注入真实模型 prompt；DEV_MODE 章节草稿也会写出人物、场景、道具、事件等上下文，便于本地验证。
- [x] 智能分镜模板对白按具体角色和故事锚点生成，AI refine 输入中增加“人物/场景/道具/事件清单”。
- [x] `/video/generate` 与 `/media/generate` 均注入动漫连续性硬约束，直生音视频任务保存 `source_prompt` 和 `story_continuity_constraints`。
- [x] 新增 `backend/test_story_prompt_context.py` 覆盖封面 prompt、章节上下文、分镜对白、视频 prompt 和直生音视频 prompt。

## 2026-05-13 P1/P2 真实生产适配阶段

- [x] Phase 78: 统一外部生产适配配置，覆盖 Sora/Veo、ComfyUI、FFmpeg 云渲染、本地 FFmpeg、口型/唇形等可选能力。
- [x] Phase 79: 镜头生产上下文支持资产版本锁定、关键帧、多视图角色参考、口型配置、多人审核状态，并能被媒体生成任务消费。
- [x] Phase 80: 统一媒体生成任务支持 ComfyUI 工作流、口型任务、云渲染任务的 adapter payload，非 DEV_MODE 必须通过外部配置提交或进入 adapter_ready。
- [x] Phase 81: workflow 渲染支持 FFmpeg 云渲染适配，消费 manifest/timeline/SRT，不把 adapter_ready 伪装成已完成成片。
- [x] Phase 82: 前端新增生产适配管理页，统一配置、测试、编辑和删除外部能力；工作流页面可选择本地渲染包或 FFmpeg 云渲染。
- [x] Phase 83: API client 补齐外部配置、镜头生产上下文和渲染适配参数。
- [x] Phase 84: 后端专项、前端构建/类型检查和格式检查通过。

## Phase 78-84 成功标准

- 外部接入必须通过 `/external` 管理配置，不在生成页面散落 API Key。
- Sora/Veo/ComfyUI/FFmpeg 云渲染、口型等能力是可选支撑能力；未配置时不能阻断 DEV_MODE 主流程。
- 非 DEV_MODE 的真实媒体/渲染任务没有配置时返回明确错误；有配置但缺少提交路径时状态为 `adapter_ready`。
- 资产版本锁、关键帧、多视图角色参考、口型和审核信息必须保存到 Shot/MediaJob/Render payload，可追溯到具体镜头。
- 前端必须能看到生产适配配置入口，并能对配置执行保存、测试、编辑、删除；workflow 渲染可选择云渲染配置。

## 2026-05-13 Phase 78-84 落地结果

- [x] `/external` 已成为生产适配统一配置面：内置 OpenAI/Sora、Google/Veo、ComfyUI、FFmpeg 云渲染、本地 FFmpeg、口型/唇形、Runway、Qwen，并支持配置保存、更新、测试、删除和 capability status。
- [x] `/shots/{shot_id}/production-context` 可保存资产版本锁、关键帧、多视图角色参考、口型配置、审核状态和 provider hints。
- [x] `/media/generate` 支持 `comfyui_workflow/lip_sync_video/final_render/cloud_render` 等 adapter task，payload 保留 asset locks、keyframes、multi-view refs、lip_sync 和 review state。
- [x] `/workflow/{id}/render` 新增 `render_backend=ffmpeg_cloud`，生成云渲染请求包、timeline、SRT 和 render manifest；DEV_MODE 返回 `adapter_ready`，非 DEV_MODE 无配置时 422。
- [x] 新增 `/production-adapters` 前端管理页，LLM 配置外部 API 标签指向该页；workflow 合成步骤可选本地渲染包或 FFmpeg 云渲染配置。
- [x] 新增 `backend/test_production_adapters.py`；验证通过：`python3 -m compileall app`、`pytest -q test_production_adapters.py test_media_subtitles.py test_workflow_routes.py` 30 passed、`npm run build`、`npx tsc --noEmit`、`git diff --check`。

## 2026-05-13 视频模型调用与生产适配可见性补强

- [x] Phase 85: 修复 `/video/generate` 的视频模型解析，确保用户选择的视频模型解析为 provider/API model/endpoint，并写入 VideoJob 元数据。
- [x] Phase 86: 修复前端视频模型默认选择，只允许 `video/video-generation` 类型配置成为默认视频模型，避免文本/图片默认配置误导为“未验证”。
- [x] Phase 87: 明确生产适配消费路径：静音视频只走火山 `/video/generate`；直生音视频走 `/media/generate`；workflow 云渲染走 `/workflow/{id}/render`。
- [x] Phase 88: 前端生产适配页、视频生成页、workflow 页展示“应用位置、当前模式是否消费配置、实际提交的资产锁/关键帧/多视图/口型/审核参数”。
- [x] Phase 89: 补充视频模型调用测试并完成后端/前端验证。

## Phase 85-89 成功标准

- 视频生成页选择的模型必须作为 `model` 传给后端，后端必须使用解析后的火山 endpoint 调用 SDK。
- VideoJob 响应和历史必须显示 `provider_id/api_model_id/model_endpoint_id/model_test_status/prompt_parameters`，便于确认真实调用了哪个模型。
- 参考图公网预检失败时仍传给后端和供应商，只有本地/私有地址才跳过，避免图生视频悄悄退化为文生视频。
- 生产适配能力必须有清晰使用入口和消费说明，用户能知道配置什么时候生效、什么时候不会被静音视频消费。
- 验证覆盖 `python3 -m compileall app`、后端专项 pytest、前端 `npm run build`、`npx tsc --noEmit` 和 `git diff --check`。

## 2026-05-13 Phase 85-89 落地结果

- [x] `/video/generate` 现在会解析所选视频模型配置，保存 provider、API model、endpoint、配置验证状态和 prompt 参数；真实 SDK 调用使用 `model_endpoint_id`。
- [x] 静音视频选择非火山视频模型时返回明确 422，提示切换到直生音视频或 workflow 生产适配路径。
- [x] 视频生成页只把火山视频类型配置作为默认视频模型，卡片展示“默认视频配置/验证状态/API 模型”；生成历史展示实际 provider、endpoint、seed、参考图是否传入。
- [x] 生产适配页新增“应用位置”面板，指向视频生成、镜头生产上下文、workflow 批量直生和云渲染四个消费点。
- [x] 视频生成页生产适配面板明确显示：静音视频不消费 Sora/Veo/ComfyUI/口型配置；直生音视频会提交镜头上下文和生产适配参数。
- [x] workflow 批量直生和渲染执行说明补充了实际消费的上下文、manifest、timeline、SRT 和云渲染配置。

## 2026-05-13 管理筛选与 Workflow 串联修复阶段

- [x] Phase 90: 修复 `/shots` 管理页筛选：新增小说、章节、剧本、分镜、状态和搜索组合筛选，镜头卡片展示上游链路，生成视频跳转携带完整 lineage。
- [x] Phase 91: 修复 `/workflow` 链路持久化：`PUT /workflow/{id}/step` 支持保存 novel/chapter/script/storyboard，前端选择小说/章节/剧本/分镜/镜头后写回后端，轮询不再把流程拉回起点。
- [x] Phase 92: 补齐 workflow 后续步骤能力：角色步骤按当前小说/章节加载角色并支持 AI 提取；剧本步骤加载/生成当前章节剧本；分镜步骤加载/智能生成分镜；镜头步骤加载当前分镜镜头。
- [x] Phase 93: 补齐入口和相关管理页筛选：顶部主导航新增“工作流”，控制台流程入口指向 `/workflow`，剧本页新增小说/章节筛选，分镜页支持 URL 小说/章节参数。
- [x] Phase 94: 验证与服务重启：后端编译、专项测试、前端类型/构建、格式检查通过，并重启本地前后端服务。

## Phase 90-94 成功标准

- `/shots?novel_id=&chapter_id=&script_id=&storyboard_id=` 能恢复筛选上下文，页面可按小说/章节/剧本/分镜筛镜头，并保留编辑、删除、批量生成入口。
- `/workflow` 从选择章节开始，角色、剧本、分镜、镜头步骤都必须读取当前链路下的已有产物，不能只跳转到外部管理页。
- 角色步骤必须能在当前小说/章节中执行 AI 提取角色；生成后当前步骤能看到角色列表。
- 剧本、分镜、镜头选择必须写入工作流状态，定时刷新后不应回到小说起点。
- 首页/控制台和顶部导航必须提供可见的 workflow 入口。

## 2026-05-13 平台前端流程与生产化复查阶段

- [x] Phase 95: 审计认证守卫、权限隔离、账户资料/密码流程、忘记/重置密码入口。
- [x] Phase 96: 审计弹窗边界、低高度/移动端滚动、导航菜单溢出和明显未落地 UI。
- [x] Phase 97: 审计模拟/写死数据、前端保存是否落库、核心页面调用是否有对应后端 API。
- [x] Phase 98: 落地 P0 修复并运行后端、前端和关键页面验证。

## 2026-05-13 Phase 95-98 落地结果

- [x] 修复前端认证守卫公共路径判断，未登录访问设置等受保护页面会跳转 `/login`。
- [x] 后端补齐 `/auth/profile`、`/auth/change-password`、`/auth/forgot-password`、`/auth/reset-password`，并为 `users` 表补头像和重置令牌字段迁移。
- [x] 非 DEV_MODE 下认证依赖改为校验签名 JWT；DEV_MODE 保留本地/E2E 开发 token 兼容。
- [x] 登录页新增“忘记密码”入口，前端新增 `/forgot-password` 和 `/reset-password` 页面。
- [x] 个人资料页头像从“开发中”弹窗改为头像 URL 输入并随资料保存落库。
- [x] 全局 Dialog 和 shots/storyboards/scripts 手写弹窗增加视口内滚动保护；顶部导航支持横向滚动，Dashboard 空状态文案从“浏览示例”改为“查看作品”。
- [x] 验证通过：后端编译、后端全量 pytest、前端类型检查、前端生产构建、Playwright 认证用例、关键页面 HTTP 访问。

## Phase 95-98 成功标准

- 未登录访问受保护页面必须跳转登录页；DEV_MODE 只在本地兼容开发 token，非 DEV_MODE 必须验证 JWT 签名。
- 登录页提供找回密码入口；后端提供资料更新、修改密码、忘记密码、重置密码接口，前端设置页保存能真实落库。
- 通用 Dialog 和主要手写弹窗在低高度窗口内可滚动，底部操作按钮可点击。
- 明显“开发中”或“示例”入口不能冒充可用功能；能落库的前端操作要调用真实 API。
- 至少通过后端账户专项测试、后端编译、前端类型/构建和关键页面 HTTP 访问验证。

## 2026-05-13 P1/P2 模型目录生产化补强阶段

- [x] Phase 99: 增加火山视频模型 `doubao-seedance-2-0-260128` 和 `doubao-seedance-2-0-fast-260128`，覆盖火山 endpoint 映射、运行时模型列表、统一模型注册表和初始化种子。
- [x] Phase 100: 修复 LLM 模型目录漂移问题，`/llm/providers` 和 `/llm/models` 在已有数据库中也会回填/更新内置 Provider 与 Model，不再只在空表时初始化。
- [x] Phase 101: 视频生成链路验证所选 Seedance 2.0 Fast 模型会作为实际 `model_endpoint_id` 提交到火山 SDK，并写入 VideoJob 元数据。
- [x] Phase 102: 后端全量 pytest、前端构建、前端类型检查和格式检查通过。

## Phase 99-102 成功标准

- `/api/v1/llm/models?provider=volcano` 必须返回 Seedance 2.0 和 Seedance 2.0 Fast，并保持 `Doubao-Seed-2.0-pro` 为文本模型，不再误入视频模型列表。
- `shot_video` 默认模型升级到 Seedance 2.0 Fast，备用模型包含 Seedance 2.0 和旧 Seedance 1.0 Pro Fast。
- 用户在视频生成页选择 `doubao-seedance-2-0-fast-260128` 时，后端必须使用该 endpoint 调用火山视频生成 SDK，而不是回退到默认或文本模型。
- 已有数据库即使已初始化过旧模型，也能通过列表接口自动补齐新增内置模型。

## 当前仍余 P1/P2 边界

- 真实 Sora/Veo/ComfyUI/FFmpeg 云渲染 SDK 提交仍属于适配层后续工作；当前已建模和可配置，但未把第三方真实任务轮询做成完整生产闭环。
- Timeline 可视化编辑、字幕烧录、多人审核流、资产版本锁 UI 和批量质量评估仍需继续产品化。
- 企业级权限、审计日志、项目级任务默认模型覆盖、真实邮件投递和通知中心仍是生产上线前的 P1/P2。

## 2026-05-14 P1/P2 镜头质量准入与审核流阶段

- [x] Phase 103: 后端新增镜头批量质量重检接口，支持一次刷新多个 Shot 的 `quality_report` 和 `budget_estimate` 并写回 `extra_data`。
- [x] Phase 104: 镜头生产上下文变更后同步刷新质量报告，审核状态会影响质量建议，避免审核通过后仍提示“待审核”。
- [x] Phase 105: 前端镜头页新增质量状态、审核状态筛选，镜头卡片展示质量徽标、评分、风险/预算摘要。
- [x] Phase 106: 前端镜头页新增批量重检、批量通过、退回修改，作为批量生成前的生产准入操作。
- [x] Phase 107: 后端专项、前端类型、格式检查和浏览器 `/shots` 页面可见性验证通过。

## Phase 103-107 成功标准

- 用户可以在镜头列表按质量状态和审核状态筛选，不再只能逐个打开镜头查看。
- 批量生成前可以对选中镜头一键重检，旧数据或未检查镜头能补齐质量报告和预算提示。
- 多人审核流的最小闭环可用：选中镜头后可以批量标记“已通过”或“需修改”，并自动刷新质量建议。
- 后端批量接口必须去重、返回缺失 ID、只更新当前用户有权限的镜头。
- 无需真实云密钥，DEV_MODE 下后端测试和前端页面验证能跑通。

## 2026-05-14 P1/P2 Timeline 产品化阶段

- [x] Phase 108: workflow 连续成片清单可同步为数据库内 `Timeline/Track/Clip`，自动创建承载项目，生成视频轨、音频轨和字幕轨。
- [x] Phase 109: workflow 页面展示“可编辑 Timeline”，支持一键生成/重建时间线，并读取轨道和片段展示。
- [x] Phase 110: 前端新增 `/timelines` 时间线编辑工作台，工具菜单提供入口；可按项目选择时间线，查看视频/音频/字幕轨，编辑片段名称、起始时间、时长和字幕文本。
- [x] Phase 111: 修复 Timeline 片段创建路由冲突，新增明确 `POST /timelines/{timeline_id}/clips`，前端支持新增字幕片段、保存片段、删除片段、锁定/静音轨道。
- [x] Phase 112: 后端专项、前端类型、格式检查、服务重启和浏览器页面/菜单验证通过。

## Phase 108-112 成功标准

- workflow manifest 不再只停留在 JSON/EDL artifact，必须能落库为可编辑 Timeline 资产。
- 用户能从 workflow 页面看到同步状态，并能进入工具菜单下的时间线编辑工作台继续调整片段。
- Timeline 页面必须调用真实后端 API 保存片段和轨道状态，不能只做前端内存编辑。
- 字幕轨至少支持新增、修改文本、调整起始时间和时长，作为后续字幕烧录/成片审阅的可编辑输入。
- 无需真实云密钥，DEV_MODE 下后端测试、前端类型检查和浏览器可见性验证能跑通。

## 2026-05-14 P1/P2 Timeline 渲染联动阶段

- [x] Phase 113: 后端渲染预检和渲染包支持优先消费最新可编辑 Timeline，缺少 Timeline 时回退到原始 manifest。
- [x] Phase 114: Timeline 渲染源会把视频/音频/字幕 Clip 转成 render segments，SRT、EDL 和 HTML 预览都使用用户修改后的字幕文本、起始时间和时长。
- [x] Phase 115: 渲染缓存增加 source key，Timeline 更新后不会复用旧 manifest 渲染包。
- [x] Phase 116: workflow 页面新增“使用可编辑 Timeline”开关和当前渲染源提示，预检/渲染请求传入 timeline 参数。
- [x] Phase 117: 后端专项、前端类型、格式检查和服务重启验证通过。

## Phase 113-117 成功标准

- 用户在 `/timelines` 修改字幕或片段时间后，再回 workflow 渲染，SRT 和 EDL 必须体现最新 Timeline 内容。
- 用户可以关闭“使用可编辑 Timeline”，按原始连续成片 manifest 渲染，便于回退和对比。
- FFmpeg 云渲染请求包也必须携带 `render_source/timeline_id` 和 Timeline 派生 segments。
- Timeline 无视频片段时预检必须阻止渲染并给出结构化问题。
- 无需真实云密钥，DEV_MODE 下专项测试和前端类型检查能跑通。

## 2026-05-14 P0/P1 轻量生产资料包阶段

- [x] Phase 118: 后端补齐小说级实体生产资料包，聚合人物关系、事件时间线、场景标签和资产需求。
- [x] Phase 119: 后端补齐 StoryEntity 一致性检查、版本快照和版本恢复，并保护快照历史不被属性更新覆盖。
- [x] Phase 120: 镜头生产上下文补齐 `entity_reference_bindings`，保存角色/场景/道具/事件的实体元数据、视觉 DNA 和资产包。
- [x] Phase 121: 前端实体库展示小说范围、生产资料包、一致性问题、属性 JSON、版本快照和恢复入口。
- [x] Phase 122: 前端镜头管理生产上下文展示实体参考绑定 JSON，并随保存提交到后端。
- [x] Phase 123: 后端专项、前端类型检查和格式检查通过。

## Phase 118-123 成功标准

- 实体库必须按小说展示生产资料包，不能把所有小说的角色、场景、道具、事件混成一个池。
- 角色资产包、场景标签、道具 DNA、事件参与者和道具状态变化必须能被一致性检查发现或进入生产包。
- 实体属性编辑后已有版本快照不能丢失，用户可以恢复到旧资产包或旧视觉设定。
- 镜头生产上下文可以绑定 StoryEntity，并在保存后持久化解析后的名称、类型、视觉 DNA 和资产包。
- 后端专项测试覆盖生产包、一致性检查、版本恢复和镜头实体绑定。

## 2026-05-14 P0/P1 前后端可见性复核与资产库阶段

- [x] Phase 124: 复核 P0/P1 任务与当前前端页面/API 对齐状态，确认直生音视频、字幕、workflow、生产适配、Timeline、实体生产资料包和镜头质量准入均已有前端入口。
- [x] Phase 125: 补齐通用资产库前端工作台，承接后端 `/assets` 能力，支持分类/项目/公开资产筛选、搜索、新增、编辑、归档和资源打开。
- [x] Phase 126: 顶部工具菜单与控制台新增“资产库”入口，避免资产版本锁、角色/场景/道具参考资产只存在后端或模板页局部能力中。
- [x] Phase 127: 增加资产库浏览器 E2E，并复验顶部工具菜单、后端资产/生产资料包/生产适配专项、前端类型/生产构建和服务健康检查。

## Phase 124-127 成功标准

- P0/P1 核心能力必须能从前端入口进入，不只停留在后端接口或计划文档中。
- 资产库不能只作为模板库的内部实现；角色、场景、道具、服装、音效、关键帧、LoRA/IP-Adapter 等资产要有统一管理页面。
- 资产新增、编辑、归档必须真实调用 `/assets` API，并能按分类、项目和公开范围筛选。
- 顶部“工具”菜单和控制台必须能看到资产库入口。
- 验证覆盖前端类型检查、后端编译、后端资产相关专项、前端生产构建、Playwright 资产库/导航用例和服务健康检查。

## 2026-05-15 视频/音视频历史筛选与剧本分页阶段

- [x] Phase 128: 后端补齐媒体任务历史的 `script_id` 过滤，并补专项测试。
- [x] Phase 129: 前端视频生成页在历史展示区增加小说、章节、剧本、分镜、镜头筛选入口，统一驱动静音视频历史与直生音视频历史。
- [x] Phase 130: 前端剧本选择增加分页展示能力，避免剧本列表过长时不可控。
- [x] Phase 131: 前端直生音视频历史展示完整链路信息，并复验类型检查和关键后端测试。

## Phase 128-131 成功标准

- 视频历史和音视频历史都能按小说、章节、剧本、分镜、镜头筛选。
- 媒体任务接口必须支持 `script_id` 查询参数，不能只支持小说/章节/分镜/镜头。
- 剧本下拉不能一次性把长列表全部铺开，前端要有明确分页/翻页展示。
- 历史条目应展示可理解的链路文本，用户能判断任务属于哪部小说、哪章、哪个剧本、分镜和镜头。

## 2026-05-15 模板库系统预制模板可编辑与扩展阶段

- [x] Phase 132: 后端扩展常用系统预制分镜模板，覆盖开场钩子、人物登场、群像会议、反派压迫、危机救援、结尾悬念等通用动漫制作场景。
- [x] Phase 133: 后端支持系统模板用户级编辑覆盖，`/storyboards/templates`、模板匹配和智能生成优先使用覆盖版本。
- [x] Phase 134: 前端 `/templates` 系统预制模板增加编辑入口，保存后保持系统模板稳定 ID 并展示已定制状态。
- [x] Phase 135: 补充系统模板编辑测试，运行后端专项、前端类型检查和浏览器验证。

## Phase 132-135 成功标准

- 系统预制模板不再只读；用户在模板库能直接编辑系统模板的名称、标签、描述、提示词和镜头数。
- 系统模板编辑必须持久化到数据库，刷新后仍能看到已定制版本。
- 智能分镜模板匹配和指定模板生成必须能消费用户编辑后的系统模板。
- 新增系统模板必须是常用、通用、可直接服务小说动漫改编的模板，不只是展示卡片。

## 2026-05-15 火山方舟 Agent Plan 模型配置阶段

- [x] Phase 136: 读取用户提供的火山方舟 Agent Plan PDF，提取专属 Base URL、API Key、模型清单和多模态调用差异。
- [x] Phase 137: 新增独立模型提供者 `volcano_agent_plan`，避免 Agent Plan Key 与普通火山方舟 Key 混用。
- [x] Phase 138: 补齐 Agent Plan 文本、向量、图像和视频模型目录，并接入后端默认 provider/model 回填。
- [x] Phase 139: 后端服务工厂、测试连接和静音视频生成支持 Agent Plan 专属 `/api/plan/v3`。
- [x] Phase 140: 前端模型配置页和视频生成页展示/选择 Agent Plan 模型，并提示专属 Key 和套餐限制。
- [x] Phase 141: 编译、后端专项、前端类型检查和接口回填验证通过。

## Phase 136-141 成功标准

- LLM 配置页能看到“火山方舟 Agent Plan”，并能选择文本、图像、视频等 Agent Plan 模型。
- 保存 Agent Plan 配置时保留专属 base_url，测试连接和业务调用不走普通火山 `/api/v3`。
- 视频生成页能加载普通火山和 Agent Plan 视频模型，且用配置模型 ID 选择，避免两个 provider 的 API model_id 冲突。
- 当前数据库无需手工清库，访问 `/llm/providers`、`/llm/models?provider=volcano_agent_plan` 会自动回填新目录。

## 2026-05-16 AI 模型能力级默认与前端可见选择阶段

- [x] Phase 142: 后端默认配置语义从全局唯一改为按能力类别独立默认，覆盖文本、图像、语音、视频和向量。
- [x] Phase 143: LLM 配置页新增能力默认模型总览，展示每类能力的默认/优先可用配置、提供者、模型和验证状态。
- [x] Phase 144: 视频生成页区分“已保存配置”和“模型目录候选”，生产模式下要求选择已配置且已验证的视频配置。
- [x] Phase 145: 语音合成页从硬编码提供商选择改为选择已保存 TTS 模型配置，并把配置模型 ID 传给后端执行。
- [x] Phase 146: 后端 TTS 生成支持 `model_config_id`，按所选配置解析 provider、API Key、base_url 和真实 API model。
- [x] Phase 147: 后端专项、前端类型检查和格式检查通过。

## Phase 142-147 成功标准

- 文本默认、图像默认、语音默认、视频默认互不覆盖；用户可以为每类能力分别设置默认模型配置。
- 前端模型配置页必须清晰显示每类能力当前默认模型，以及是否已验证通过。
- 使用视频能力时，前端默认选中视频能力的默认配置；未保存或未验证配置必须有明确提示。
- 使用语音能力时，前端只展示已保存的语音模型配置，默认选择语音能力默认配置，并提示未验证状态。

## 2026-05-16 AI 模型能力选择贯穿阶段

- [x] Phase 148: 后端文本、图像、视频、语音等主要生成入口支持传入 `model_config_id`，并按能力校验已保存配置。
- [x] Phase 149: 新增通用前端 `ModelCapabilitySelector`，在小说、章节、角色、实体、分镜、极速向导和 workflow 等 AI 入口展示默认模型、验证状态和可切换配置。
- [x] Phase 150: Story Bible、实体抽取、封面生成、章节 AI、角色抽取、分镜生成等链路消费前端选择的模型配置，并保留 DEV_MODE 回退。
- [x] Phase 151: 剧本管理页 AI 生成补齐文本模型选择；从章节改编剧本改走 `/scripts/generate` 并直接落库，自定义描述生成也传入 `model_config_id`。
- [x] Phase 152: Coding Plan 辅助接口支持 `model_config_id`，前端 API client 同步可传模型配置，避免后续复用时绕过统一模型配置。
- [x] Phase 153: 后端专项、前端类型检查和格式检查通过。

## Phase 148-153 成功标准

- 前端 AI 生成入口必须明确展示“使用哪个能力模型、是否默认、是否验证通过”，不能只显示无限等待或孤立按钮。
- 用户选择的文本/图像/语音/视频配置必须真实进入后端请求体；后端不能只使用全局默认或硬编码 provider。
- 剧本、分镜、章节、角色、实体、封面等文本/图像生成链路要保持小说、章节、角色、场景、道具、事件上下文，并使用对应能力模型。
- Coding Plan 等辅助入口如果继续存在，也必须接入同一套用户模型配置和认证依赖。

## 2026-05-19 短剧式动漫短视频一致性生产分析阶段

- [x] Phase 154: 建立“小说到短视频”的叙事控制层，按集/场/镜头管理钩子、冲突、反转、悬念、情绪曲线和下集承接。
- [x] Phase 155: 强化 Story Bible 为唯一一致性源，补齐角色状态、服装状态、道具流转、场景时间/天气/空间、事件因果和禁改规则。
- [x] Phase 156: 为每个 Shot 生成并锁定 Production Contract：人物、场景、道具、事件、对白、字幕、参考资产版本、seed、模型配置、关键帧和审核状态。
- [x] Phase 157: 增加短剧分集模板和短视频镜头节奏模板：开场 3 秒钩子、冲突升级、爽点/反转、结尾悬念、下一集伏笔。
- [x] Phase 158: 增加一致性校验器：生成前校验资产缺失、角色串用、道具状态冲突、事件顺序冲突、对白不符合人物口吻、字幕缺失、镜头时长不适合短视频。
- [x] Phase 159: 模型路由策略升级：长文本/结构化文本、角色/场景图、静音视频、直生音视频、TTS、口型、字幕、渲染分别按任务选择已验证模型，并记录模型版本。
- [x] Phase 160: 前端工作流增加“短视频出片模式”，展示每集目标时长、镜头节奏、钩子文案、一致性检查结果、缺失资产和推荐下一步。
- [x] Phase 161: 补充短剧式生产专项测试，覆盖同一小说多集、多镜头、多角色、多道具状态的一致性继承。

## 2026-05-19 Phase 154-161 落地结果

- [x] 新增 `/api/v1/short-video/episode-plan`，基于小说、章节、Story Bible 和实体上下文生成 9:16、30-90 秒短剧式单集规划。
- [x] 新增 `/api/v1/short-video/shots/{shot_id}/production-contract`，为镜头生成并可持久化 Production Contract，写入 `Shot.extra_data.production_context.production_contract`。
- [x] 新增 `/api/v1/short-video/workflow/{workflow_id}/readiness` 和 `/refresh-contracts`，按工作流分镜批量检查镜头合约、阻断项、提醒项、总时长和推荐下一步。
- [x] Production Contract 统一带出人物、场景、道具、事件、对白字幕、Story Bible 状态、资产锁、多视图参考、关键帧、seed、模型路线、质量报告和预算估算。
- [x] 前端 workflow 增加“短视频出片模式”面板，展示目标时长、9:16 出片、钩子/悬念、镜头合约状态、字幕/资产锁缺口和默认模型路线。
- [x] 新增 `backend/test_short_video_production.py`，覆盖短视频规划、镜头合约持久化和工作流就绪度/批量刷新。

## Phase 154-161 成功标准

- 一条短视频不能只由孤立 prompt 生成，必须能追溯到小说、章节、剧本、分镜、镜头、实体、资产、字幕和模型配置。
- 每个镜头生成前必须有可读的 Production Contract；严重缺失项阻断，轻微缺失项提示并允许降级。
- 同一角色跨镜头必须优先使用锁定参考资产、同一 voice profile、同一服装/状态；切换服装或受伤等状态必须由事件驱动。
- 同一道具跨镜头必须有状态流转，例如“钥匙在 A 手中 -> 掉落 -> B 捡起”；不允许无原因消失或变形。
- 同一场景必须保持空间、时间、天气和光影设定；剧情需要变更时必须生成场景转场或时间跳转说明。
- 短剧式模板必须能输出 9:16 优先、30-90 秒、强钩子、强节奏、结尾悬念的镜头计划。
- 模型选择必须可解释：为什么该任务用长文本模型、Seedance 静音视频、Sora/Veo/Seedance 直生音视频、TTS 或 FFmpeg 渲染。

## 2026-05-20 实体与资产统一作用域阶段

- [x] Phase 162: 后端补齐 StoryEntity 的 script_id 作用域、列表筛选和动态升降级。
- [x] Phase 163: 后端新增 AI 抽取实体并生成资产占位接口，资产支持全局/小说/章节/剧本/实体绑定。
- [x] Phase 164: 前端实体库与资产库补齐作用域筛选、抽取实体+资产、升全局/绑定当前范围操作。
- [x] Phase 165: 后端专项、前端类型/构建、服务重启验证。

## Phase 162-165 成功标准

- 实体和资产都能按 global/novel/chapter/script/entity 范围筛选和调整。
- 从小说、章节或剧本抽取实体时，能自动带上上游链路，并可同时创建资产占位。
- 前端页面能看到作用域标记和操作按钮，不再只能靠手填 ID。
- 定向测试覆盖抽取、作用域升降级和资产创建。

## 2026-05-20 默认动漫资产与实体库阶段

- [x] Phase 166: 新增用户级可编辑默认动漫实体库，覆盖通用角色、场景、道具和事件。
- [x] Phase 167: 新增用户级可编辑默认动漫资产库，覆盖提示词、场景参考、道具 DNA、服装、音效、音乐和 9:16 短剧分镜模板。
- [x] Phase 168: 接入实体/资产列表接口，用户打开页面时自动补齐默认库，且不绑定具体小说。
- [x] Phase 169: 补充专项测试、编译、格式检查和接口烟测。

## 2026-05-20 资产库筛选与统计修复阶段

- [x] Phase 170: 修复分类数量统计，按当前用户可见范围和公开开关计算。
- [x] Phase 171: 修复小说/章节/剧本/实体筛选默认包含全局资产的逻辑。
- [x] Phase 172: 修复前端资产库筛选文案、范围语义和本地统计口径。
- [x] Phase 173: 补充回归测试并完成服务重启烟测。

## 2026-05-20 实体库筛选与维护修复阶段

- [x] Phase 174: 修复后端实体列表默认包含全局实体的查询语义。
- [x] Phase 175: 修复前端实体库筛选文案、旧条件查询和范围选择逻辑。
- [x] Phase 176: 补充实体查询和维护功能回归测试。
- [x] Phase 177: 重启服务并完成实体接口/页面烟测。

## 2026-05-20 实体库统计修复阶段

- [x] Phase 178: 后端新增实体统计接口，按小说/章节/剧本/范围统一聚合角色、场景、道具和事件数量。
- [x] Phase 179: 复用实体列表范围筛选语义，避免列表和统计口径分叉。
- [x] Phase 180: 前端实体库统计卡改为读取统计接口，不再从当前分页列表反推数量。
- [x] Phase 181: 补充统计回归测试并完成编译、类型和格式验证。

## 2026-05-22 数据分析与系统设置完善阶段

- [x] Phase 182: `/analytics` 从静态 mock 改为读取 dashboard、usage-stats、任务队列和媒体任务真实数据。
- [x] Phase 183: `/settings` 首页补齐账户摘要、偏好摘要和可保存快捷设置。
- [x] Phase 184: 新增 `/settings/notifications` 和 `/settings/appearance`，使用 localStorage 保存本机通知/外观偏好。
- [x] Phase 185: 补齐前端 usage-stats API client 契约并完成类型、构建、格式验证。

## Phase 182-185 成功标准

- 数据分析页面不能继续展示静态播放量/用户增长 mock；必须能从现有后端接口汇总作品、模型用量、任务健康度和近期活动。
- 使用统计 API client 不能继续调用不存在的 `/usage-stats?period=` 作为主路径；新增方法需匹配后端 `/summary`、`/by-model`、`/daily`、`/logs`。
- 系统设置入口必须全部可达；通知和外观配置刷新后能恢复，不影响认证、资料、安全和生成链路。
- 外观优化只做安全偏好，不引入大范围主题重构，避免影响现有页面可读性。

## 2026-05-22 数据分析正式数据源修正阶段

- [x] Phase 186: 新增后端 `/dashboard/analytics` 聚合接口，统一从数据库统计内容资产、生成任务、每日趋势、模型用量和近期活动。
- [x] Phase 187: 前端 `/analytics` 改为只读取正式聚合接口，移除多接口拼装和失败静默归零。
- [x] Phase 188: 补充后端专项测试，验证接口返回 `data_source=database`、`is_mock=false` 和真实插入记录统计。
- [x] Phase 189: 完成后端编译、前端构建、格式检查、服务重启和接口烟测。

## Phase 186-189 成功标准

- 数据分析页展示的所有数字必须来自一个后端正式聚合接口，不再由前端自行拼装多个任务列表。
- 后端接口必须明确标记数据来源，不允许返回模拟数据。
- 接口失败时前端必须显示错误或空态，不能静默展示 0 作为真实结果。
- 模型排行必须匹配当前数据库模型字段，不能引用不存在的 `LLMUsageLog.model`。

## 2026-05-26 整部小说动画漫剧生产平台规划阶段

- [x] Phase 190: 复盘当前小说、章节、Story Bible、实体、资产、剧本、分镜、镜头、音视频、字幕、合成、模型配置和生产适配能力。
- [x] Phase 191: 明确当前平台已具备首集/单章节生产闭环，但还缺整部小说多集编排、强状态机、资产版本锁和 AI 制片助手。
- [x] Phase 192: 更新 `docs/novel-to-anime-optimization-plan.md`，新增整书生产计划、Series/Episode、Story Bible 状态机、资产定稿包、媒体持久化和 AI 制片助手路线。
- [x] Phase 193: P0 落地整书生产计划：小说详情生成多集 Episode Plan，并展示每集生产状态和下一步动作。
- [x] Phase 194: P0 落地 Story Bible 状态机：角色/服装/关系/道具/场景/事件状态跨章节和跨集继承。
- [x] Phase 195: P0 落地资产定稿包与版本锁：角色、场景、道具定稿图和声线进入 Shot/MediaJob asset locks。
- [x] Phase 196: P0 落地媒体持久化巡检：外部临时 URL 转存，历史视频/图片/字幕/渲染包可长期播放下载。
- [x] Phase 197: P0 落地 AI 制片助手：按当前工程状态自动补齐缺失项、执行下一步、反馈阶段进度和失败恢复建议。
- [x] Phase 198: P1 落地生产质量检查：生成后差异检测、质量面板、批量重生、审核流和真实生产适配状态收敛。

## 2026-05-26 Phase 193 落地结果

- [x] 新增后端整书生产计划服务 `series_production.py`，按章节顺序拆分多集，并复用现有剧本、分镜、镜头、视频任务、直生音视频任务和 workflow 计算每集生产状态。
- [x] 新增 `/api/v1/novels/{novel_id}/series-plan` GET/POST，计划保存到 `Novel.extra_data.series_plan`，避免当前阶段引入额外迁移。
- [x] 每集计划包含覆盖章节、目标时长、画幅、剧情钩子、冲突、反转、悬念、下集承接、关键人物/场景/道具/事件、生产计数、下一步动作和 workflow 入口。
- [x] 小说详情页新增“整书计划”入口和标签页，可生成多集计划、查看每集状态，并创建/继续本集 workflow。
- [x] 小说详情设置页签的标题、简介、类型现在可真实保存，不再只是只读输入框。
- [x] 补充 `backend/test_series_production.py`，覆盖生成、持久化、章节顺序覆盖、状态推导和无章节错误。
- [x] 验证通过：`python3 -m compileall app`；`DEV_MODE=true pytest -q` 137 passed、1 skipped、1 warning；`npx tsc --noEmit`；`npm run build`；`git diff --check`；服务重启后后端 `/health`、前端 `/novels`、series-plan 接口和浏览器小说详情页烟测通过。

## Phase 193 后续补强点

- 极速向导到整书计划的跳转已在 Phase 231-233 补齐；Quick Start 完成后可直接进入当前作品的整书生产计划。
- 多集计划目前用规则和已有产物计算，不调用文本模型深度生成集纲；后续 Story Bible 状态机落地后，可让 AI 根据人物状态、事件因果和道具流转生成更细的跨集大纲。
- 持久化暂存 `Novel.extra_data.series_plan`，后续进入团队协作、多人审核、批量生产时建议拆为 `SeriesPlan/EpisodePlan` 独立表并增加版本历史。

## 2026-05-26 Phase 194-198 落地结果

- [x] Story Bible 状态机已落地：新增状态机服务和 `/story-bibles/{id}/state-machine` 读写/检查接口，状态写入 `StoryBible.extra_data.state_machine`，并注入 Story Prompt Context 与 Prompt Composer。
- [x] 小说详情 Story Bible 区域已展示跨章节状态机、人物/场景/道具/事件当前状态和状态检查提示。
- [x] 新增生产控制层 `/production-control`：小说级资产定稿包、工作流资产锁应用、媒体持久化巡检、AI 制片助手和生产质量检查统一成可调用 API。
- [x] 资产定稿包复用现有 `Asset/StoryEntity/Novel.extra_data`，可为缺少定稿图的角色、场景、道具自动创建 DEV_MODE 占位资产，并把版本锁写入 `Shot.extra_data.production_context.asset_version_locks`。
- [x] 工作流批量直生音视频会继承镜头资产锁、关键帧、多视图参考和 Production Contract 到 `MediaGenerationJob.input_assets/extra_data`，避免只锁在前端或 Shot 中。
- [x] 媒体巡检会检查 VideoJob、MediaGenerationJob、TTSJob、SynthesisJob 和渲染 artifact 的本地/远端/缺失状态；远端临时 URL 可转存为 `/static/generated/...`。
- [x] Workflow 左侧新增 “AI 制片控制台”，可执行制片检查、AI 安全补齐、资产定稿、媒体巡检和生产质量检查，并显示下一步、资产锁数量、媒体缺失和质量分。
- [x] 新增 `backend/test_production_control.py`，覆盖定稿包、资产锁、媒体任务继承资产锁、媒体巡检、质量检查和 AI 制片助手自动补齐。
- [x] 验证通过：`python3 -m compileall app`；`DEV_MODE=true pytest -q test_story_state_machine.py test_production_control.py` 4 passed；相关后端专项 39 passed；前端 `npx tsc --noEmit`；`npm run build`；`git diff --check`。

## Phase 194-198 剩余边界

- 当前资产定稿包第一版采用 `Novel.extra_data` 和 `Shot.extra_data` 持久化，适合轻量团队快速落地；后续多人协作、审批和资产依赖图建议拆独立版本表。
- 媒体巡检已能发现本地缺失和转存远端 URL，但真实对象存储、CDN、供应商回调重拉和定时巡检任务仍属于后续生产运维能力。
- 生产质量检查目前以镜头字段、资产锁、字幕、关键帧和实体引用为主；真正的视频画面差异检测、角色脸部一致性视觉评分和批量重生策略仍需接视觉模型或外部检测服务。

## 2026-05-26 前端可见性补强阶段

- [x] Phase 199: 新增独立 `/producer` AI 制片中心，把 Story Bible 状态机、资产定稿包、媒体巡检、质量检查和 AI 制片助手集中展示。
- [x] Phase 200: 顶部导航、控制台和工作流页补齐显眼入口，避免生产控制能力只藏在工作流侧栏。
- [x] Phase 201: 完成前端类型检查、构建、格式检查和页面烟测。

## Phase 199-201 成功标准

- 用户从顶部导航或控制台能直接进入 AI 制片中心。
- AI 制片中心能选择已有工作流，展示工作流产物数量，并执行制片检查、安全补齐、资产定稿、媒体巡检和质量检查。
- Story Bible 状态机不再只在小说详情内可见；独立页面可选择 Story Bible 并执行检查/生成。

## 2026-05-26 工作流与 AI 制片流程修复阶段

- [x] Phase 202: AI 制片中心增加小说/章节选择、按小说章节筛选已有 workflow、为当前章节创建工程。
- [x] Phase 203: AI 制片中心补齐“本集草片一键生成”动作，串联制片检查、资产锁、短视频合约、批量音视频、拼接、渲染预检和渲染包。
- [x] Phase 204: Workflow 页面增加同样的完整生成入口和阶段反馈，避免视频生成只藏在分散步骤里。
- [x] Phase 205: 完成前端类型检查、构建、格式检查、页面/API 烟测和服务重启。

## Phase 202-205 成功标准

- 用户可以从 AI 制片中心先选小说、再选章节，并看到该章节已有工作流或创建新工作流。
- 一键生成动作必须明确使用当前 workflow 的小说、章节、剧本、分镜、镜头、对白、字幕和资产锁上下文。
- 每个阶段必须有可见状态和失败原因，不能只显示“等待中”。
- `/producer` 和 `/workflow` 页面必须可访问，前端类型检查和生产构建通过。

## 2026-05-26 AI 制片模型调用修复阶段

- [x] Phase 206: 修复 AI 制片一键生成只走 DEV 占位直生音视频的问题，区分“直生音视频”和“视频+声音分步生成”策略。
- [x] Phase 207: 后端 workflow 批量生成支持音频模型配置、视频任务和 TTS 任务分别落库，并在任务 metadata 中记录真实使用的模型配置。
- [x] Phase 208: 前端 AI 制片中心和 workflow 显示视频模型、声音模型和生成策略，传入对应模型配置。
- [x] Phase 209: 补充专项测试、类型检查、构建、烟测和服务重启。

## Phase 206-209 成功标准

- 如果选择“视频+声音分步生成”，后端必须创建 VideoJob 和 TTSJob，并在合成时使用这两类任务。
- 如果选择“直生音视频”，前端必须明确说明声音由直生音视频模型负责，不再假装使用独立声音模型。
- 模型配置 ID、测试状态、provider、API model 必须写入任务 metadata，便于历史追踪。
- 非 DEV 且真实供应商未适配时，接口不能静默生成占位视频或音频，必须返回明确原因。

## 2026-05-26 Phase 206-209 落地结果

- [x] `/workflow/{workflow_id}/generate-media-batch` 新增 `separate_video_tts` 策略：真实视频路径会按所选视频模型配置调用火山 Ark 任务接口；声音路径会按所选 TTS 配置调用 MiniMax 或火山 TTS。
- [x] Workflow 批量生成现在返回 `video_job_ids/tts_job_ids/pending_*_job_ids/ready_for_concatenate`，云端任务未完成时前端不会继续假装合成已完成。
- [x] 无对白镜头会生成旁白草稿并走声音模型，避免批量成片出现部分镜头无声音、无字幕断点。
- [x] AI 制片中心和 Workflow 视频步骤都展示文本、视频、声音模型选择；默认走“视频模型 + 声音模型”分步生成，并把 `model_config_id/audio_model_config_id` 传给后端。
- [x] 新增后端测试验证所选视频模型 `api_model_id` 真实传入视频 SDK、所选声音模型真实传入 TTS 服务，并写入任务历史 metadata。

## 2026-05-27 多镜头视频一致性修复阶段

- [x] Phase 210: 视频生成上下文改为“有效一致性包”，按当前小说/章节过滤错误实体，真实角色优先进入 prompt。
- [x] Phase 211: 同一分镜共享分镜级风格锁、系列 seed、角色视觉 DNA 和资产版本锁，镜头 seed 只作为同一系列下的镜头差异。
- [x] Phase 212: 视频参考图自动回退到镜头图、角色头像、资产版本锁或小说资产库，避免无参考图导致人物/场景漂移。
- [x] Phase 213: Workflow 批量视频+配音生成复用同一套最终一致性 prompt 和参考图参数，不再只发送普通镜头描述。
- [x] Phase 214: 收紧本地实体抽取规则，避免“疼痛/狂喜/阳光/年轻/瘦弱”等普通词进入角色库。
- [x] Phase 215: 补充真实案例回归测试、编译验证、服务重启和烟测。

## Phase 210-215 成功标准

- 同一小说/章节/剧本/分镜下的多个镜头任务必须保存相同 `consistency.series_seed` 和 `style_lock`。
- 视频任务 prompt 必须包含当前小说真实角色的姓名、身份/外貌/性格等视觉 DNA；错误实体不能作为角色规则进入视频 prompt。
- 未显式传参考图时，系统必须记录 `reference_image_source`，并尽量自动选择镜头图、角色头像或资产图作为图生视频参考。
- 工作流批量生成和单镜头生成必须使用同样的一致性包，真实 SDK 参数里也要带最终 prompt、seed 和参考图。

## 2026-05-27 Phase 210-215 落地结果

- [x] `/video/generate` 现在先构建视频一致性包：当前小说角色、显式 StoryEntity 角色、场景、道具、事件、字幕、Story Bible、资产锁和分镜风格锁统一进入最终 prompt。
- [x] 污染实体会被过滤：未匹配真实角色且来源为“规则识别人物”的 character ref 不再进入人物规则；道具名包含真实角色名时会被剔除。
- [x] 同一分镜生成的视频任务保存相同 `consistency.series_seed` 与 `style_lock`，镜头级 seed 保留差异但继承同一系列锚点。
- [x] 未传 `image_url` 时会自动回退到镜头参考图、角色头像、资产版本锁和当前小说资产库，并在 `prompt_parameters.reference_image_source` 中记录来源。
- [x] Workflow `separate_video_tts` 批量生成复用同一套一致性包，真实 SDK 也发送最终 prompt、seed 和参考图。
- [x] 新增回归测试覆盖《逆天至尊》第一章同一分镜多镜头、污染实体过滤、角色头像回退、批量生成一致性 prompt 和实体抽取误判。
- [x] 验证通过：后端全量 `DEV_MODE=true pytest -q` 152 passed、1 skipped；前端 `npm run build`、`npx tsc --noEmit`、`git diff --check` 通过。

## 2026-05-27 整部小说级视频与剧情一致性阶段

- [x] Phase 216: 新增小说级连续性包，统一生成 `novel_series_seed`、`chapter_seed`、章节承接、状态机摘要、事件线和实体锁。
- [x] Phase 217: 视频生成从“分镜级 series seed”升级为“整部小说级 series seed + 章节/分镜/镜头派生 seed”，跨章节共享同一小说视觉系列。
- [x] Phase 218: 剧本生成 prompt 与 `generation_context` 写入整部小说连续性锁，防止中间章节改编时割裂前后剧情。
- [x] Phase 219: 分镜生成和智能分镜把小说连续性写入分镜 content 与每个 Shot.extra_data，后续视频、配音、字幕和合成可继承。
- [x] Phase 220: 补充跨章节回归测试、全量后端测试、前端类型/构建验证和服务重启。

## Phase 216-220 成功标准

- 同一小说不同章节的视频任务必须共享 `consistency.novel_series_seed`，但拥有不同 `chapter_seed`。
- 第二章及后续章节的视频 prompt 必须包含上一章承接、当前章状态快照、最近事件线、角色/场景/道具状态机。
- 剧本、分镜、镜头、视频任务都必须保存可追踪的 `continuity_lock`，不能只在最终视频 prompt 里临时拼接。
- 分镜和视频生成不能把后续章节当成已经发生的剧情，只能作为不可矛盾约束。

## 2026-05-31 P1 Story Bible 角色音色锁阶段

- [x] Phase 221: Workflow 批量 TTS 解析 Story Bible，按镜头对白/角色引用选择角色音色和语速。
- [x] Phase 222: TTSJob 与 Workflow 状态返回实际命中的 `voice_source/voice_character_name/story_bible_id`，接口返回命中数量。
- [x] Phase 223: 独立 TTS 多角色对白按段使用 Story Bible 音色，修复生成成功状态和前端播放展示。
- [x] Phase 224: `/workflow` 与 `/tts` 前端展示角色音色锁、Story Bible 选择和命中提示。
- [x] Phase 225: 补充回归测试、类型检查、编译检查、服务重启和页面烟测。

## Phase 221-225 成功标准

- 同一小说/章节/分镜下的批量配音必须优先继承 Story Bible 角色音色，不能只使用默认音色。
- 多角色对白必须逐段解析角色音色，不能把第一个角色的声音应用到所有角色。
- 前端必须能看到当前是否启用角色音色锁、选中的 Story Bible，以及本次配音命中数量。
- 生成历史和 Workflow 状态必须保存实际使用的音色来源，便于后续一致性检查定位问题。

## 2026-05-31 轻量生产闭环补强阶段

- [x] Phase 226: AI 制片页显性展示短视频出片就绪度，自动加载阻断项、提醒和下一步建议。
- [x] Phase 227: AI 制片一键草片生成支持无工作流时自动创建本集工程；章节一键生成剧本/分镜后自动挂载工作流。
- [x] Phase 228: 修复前端继续制作路由契约：移除 `/scripts/new` 死链，统一视频页参数 `script_id/storyboard_id`，并兼容旧参数。
- [x] Phase 229: 剧本页“生成分镜”改走真实 AI 分镜接口，生成镜头后跳转到分镜详情上下文。
- [x] Phase 230: 合成/发布保存可播放视频 URL，修复 `/synthesis/execute` 落库缺 `video_url`，合成页打开静态产物时解析后端地址。

## Phase 226-230 成功标准

- 非专业用户在 `/producer` 选择小说和章节后，不必先理解工作流概念也能生成本集草片。
- 短视频就绪度必须准确提示没有镜头、合约缺失、时长不合适等阻断项，不能在 `ready=false` 时显示“已就绪”。
- 从章节、小说、剧本、分镜继续制作时，前端 URL 参数必须被目标页面识别，不能 404 或丢上下文。
- 发布记录必须保留最终可播放 `video_url`、封面、时长和本地 artifact，便于后续播放/下载/归档。
- 本轮只修轻量闭环阻断点，不展开真实云回调、多人审核和完整剪辑台。

## 2026-06-05 Quick Start 整书计划入口收口阶段

- [x] Phase 231: Quick Start 成功结果补齐“进入整书计划”入口，指向当前作品的整书生产计划标签页。
- [x] Phase 232: 小说详情支持 `?tab=series-plan` 和 `?tab=series` 直接打开整书计划，避免从首集向导回到作品后仍需手动找入口。
- [x] Phase 233: 新增前端 E2E 覆盖 Quick Start 结果入口和小说详情标签参数；前端类型检查、构建和 diff 检查通过。

## Phase 231-233 成功标准

- 极速向导完成后，用户能直接进入整部小说/多集漫剧计划，不再只停留在首集工程。
- 小说详情页的整书计划标签可被 URL 参数直接激活，方便后续从控制台、AI 制片和任务中心跳转。
- 本阶段只补齐既有整书计划能力的前端串联，不新增后端表结构或新的生产流程。

## 2026-06-05 低门槛多视图资产制片阶段

- [x] Phase 234: 后端提供创作者可理解的角色三视图、场景四视图、道具多视图预设接口。
- [x] Phase 235: 后端支持按小说 StoryEntity 一键生成多视图资产，并保持 `novel_id/chapter_id/script_id/entity_id/entity_type/view_key` 关联。
- [x] Phase 236: 资产版本锁改为同一实体同一视图互斥，允许角色正面、侧面、背面同时定稿。
- [x] Phase 237: 前端资产库新增“AI 资产制片向导”，按小说、实体类型、小说对象和画面风格补齐缺失视图。
- [x] Phase 238: 资产编辑表单默认隐藏变量配置、视图配置和生成参数 JSON，高级设置按需展开。
- [x] Phase 239: 资产列表和实体选择中文化展示，减少 `image/character/prop` 等内部值外露。
- [x] Phase 240: 补充后端多视图测试、前端资产页 E2E、类型检查和 diff 检查。

## Phase 234-240 成功标准

- 角色三视图、场景四视图、道具多视图不再是孤立资产，必须能绑定到当前小说实体，并被后续镜头/视频一致性链路复用。
- 普通创作者路径不展示 JSON 和英文内部字段；高级参数只在用户主动展开时显示。
- 资产页必须能上传/预览资源和缩略图、选择小说实体、生成缺失视图、预览并锁定视图资产。
- 后端 DEV_MODE 下没有真实图像模型配置时也能生成可验证本地图片，方便完整流程测试。
- 本阶段不扩展真实 LoRA 训练、多角度视觉检测和完整素材依赖图；这些保留为后续 P2/P3。

## Phase 241+ 剩余计划

- [x] Phase 241: 角色/场景/道具详情页展示“已定稿多视图包”，并提供从实体库直接进入资产制片向导的入口。
- [x] Phase 242: 分镜和镜头编辑页选择角色、场景、道具时，显示对应多视图定稿状态和缺失项提醒。
- [x] Phase 243: 视频生成前增加“参考资产完整度预检”，缺角色正/侧/背、场景全景/布局/光影、关键道具主视图时给出一键补齐建议。
- [x] Phase 244: 资产模板库增加面向题材的示例预览图、提示词样例和画面比例推荐，进一步减少手填提示词。
- [x] Phase 245: 增加多视图生成失败的任务记录和重试入口，避免用户只看到一次性 toast。
- [x] Phase 246: 后续接入真实视觉一致性检测或多图参考模型时，把检测分数和模型输入资产写回资产版本历史。

## 2026-06-05 Phase 241 落地结果

- [x] 实体审阅台改为统一使用 `apiClient` 调用 StoryEntity 接口，不再直接请求前端同源 `/api/v1/...`。
- [x] 角色、场景、道具实体卡片展示“多视图定稿包”，按视图标注 `已定稿/已生成/待补齐`。
- [x] 实体卡片新增“补齐多视图”入口，跳转 `/assets?novel_id=...&entity_type=...&entity_id=...`。
- [x] 资产库支持读取 URL 参数，自动预选向导小说、对象类型和小说对象。
- [x] 手工创建/更新资产支持保存 `entity_type`，保证手工补图与 AI 多视图生成进入同一套实体资产链路。
- [x] 新增前端 E2E 覆盖实体页多视图状态和跳转补齐入口。

## 2026-06-05 Phase 242 落地结果

- [x] 分镜详情页镜头面板展示“参考资产完整度”，按当前镜头引用的角色、场景、道具显示多视图定稿数和缺失视图。
- [x] 镜头管理编辑弹窗展示同样的多视图完整度提醒，用户打开镜头即可看到角色三视图、场景四视图或道具多视图是否补齐。
- [x] 分镜页和镜头页的“补齐参考图”统一跳转资产制片向导，并携带 `novel_id/entity_type/entity_id`，减少手动选择。
- [x] 新增前端 E2E 覆盖分镜页和镜头管理页的多视图缺失提醒。

## 2026-06-05 Phase 243 落地结果

- [x] 视频生成页在选择具体镜头后展示“生成前参考资产预检”，按出镜角色、场景、道具显示多视图定稿数和缺失项。
- [x] 缺失必备视图时展示“建议补齐”和“去补齐参考图”入口；DEV_MODE 和轻量创作流程不硬阻断生成，避免用户被资产门槛卡死。
- [x] 预检入口携带 `novel_id/chapter_id/script_id/entity_type/entity_id` 跳转资产制片向导，能从生成前直接补齐角色三视图、场景四视图或道具多视图。
- [x] 新增前端 E2E 覆盖视频生成页预检面板、缺失视图提示和补齐入口。

## 2026-06-05 Phase 244-246 落地结果

- [x] 多视图预设补齐推荐画面比例、题材模板示例、示例预览图路径和提示词样例；资产制片向导直接展示“推荐比例”和“题材模板示例”。
- [x] 多视图生成单视图失败时不再整体 500，而是保存失败资产记录，写入视图、错误原因、重试状态和血缘信息。
- [x] 资产列表和向导视图卡片展示“生成失败”、错误原因和“重试生成”按钮；重试成功后可生成对应参考图并刷新资产列表。
- [x] 新增资产视觉一致性写回接口，保存当前评分和最多 20 条历史；资产列表展示“一致性 N”，为后续真实视觉检测接入预留轻量入口。
- [x] 新增后端和前端回归测试覆盖题材示例、失败记录、重试入口、视觉一致性分数显示与写回。

## 2026-06-06 生产级全链路收口规划阶段

- [x] Phase 247: 复盘现有全部阶段、规划文件、核心后端服务、前端生产页面和测试覆盖，确认当前主要风险从“缺模块”转为“能力分散且可绕过”。
- [x] Phase 248: 并行只读审计后端一致性/生成链路、前端工作流/交互可见性、测试与生产风险，并将关键发现写入 `findings.md`。
- [x] Phase 249: 输出生产级优化实施计划 `docs/superpowers/plans/2026-06-06-production-grade-platform-optimization.md`，覆盖架构分析、全模块 AI 赋能、一致性中枢、工作流、前端、测试、排期和部署。
- [x] Phase 250: P0 落地：新增统一生产预检服务，统一 `entity_refs` 结构，修复资产锁服务，并让视频/TTS/媒体/图片生成生产模式不可绕过一致性门禁。
- [x] Phase 251: P0 落地：前端新增全局生产状态与一键下一步，workflow 不再无参数静默创建，镜头和资产编辑默认隐藏 JSON 专家字段。
- [x] Phase 252: P0 落地：统一 synthesis 与 workflow render/timeline/subtitle 管线，历史播放/下载/筛选和最终 artifact 验收稳定可用。
- [x] Phase 253: P0 验证：运行紧凑后端一致性套件、前端类型/构建、核心 Playwright 链路，并新增非 DEV 预检门禁测试。

## Phase 250-253 成功标准

- 所有生产生成入口必须先通过同一套 preflight package：lineage、Story Bible、StoryEntity、资产锁、音色、字幕、模型、参考图公网可达、seed、prompt 版本。
- `shot.extra_data.entity_refs` 不再混用 ID 列表和 dict refs；旧数据可兼容读取，新写入结构稳定。
- 缺角色/场景/道具定稿、模型未验证、参考图不可公网访问、章节/剧本/镜头不匹配等问题在生产提交前可见并可一键修复或明确降级。
- 前端默认路径只暴露“继续制作、AI 补齐、检查问题、生成草片、合成导出”，专家 JSON 参数只在高级模式展示。
- 最终验收不只看 manifest，还要验证输出文件、字幕、时间线、血缘和历史播放/下载入口。

## 2026-06-06 Phase 250 部分落地结果

- [x] 后端一致性预检底座完成：新增 `entity_ref_normalizer`、`consistency_preflight` 和标准 `POST /api/v1/consistency/preflight`。
- [x] 资产锁服务修复：兼容 dict refs，按实体类型/分类查锁定资产，解锁只解除镜头绑定，不修改共享资产。
- [x] `build_consistency_prompt` 已接入镜头锁定资产，并在 metadata 中透出 `locked_assets`。
- [x] 验证通过：`python3 -m compileall app`；后端关联专项 64 passed；`git diff --check` 通过。
- [x] 视频/TTS/媒体/图片生产入口已强制接入 preflight 门禁：生产模式不能关闭一致性上下文，未验证模型/外部适配配置、非公网参考图会在任务创建前返回结构化 422。
- [x] 验证通过：`python3 -m compileall app`；`pytest -q tests/test_p0_consistency_pipeline.py ... test_workflow_routes.py`，152 passed。

## 2026-06-06 Phase 252 落地结果

- [x] `/api/v1/synthesis/jobs` 支持按 `project_id/workflow_id/status/render_status/novel_id/chapter_id/script_id/storyboard_id/shot_id` 查询合成历史；小说、章节、剧本、分镜、镜头可从 `extra_data`、`lineage` 或多段 `segments[].lineage` 中兼容读取。
- [x] 合成任务响应新增一等字段：`novel_id/chapter_id/script_id/storyboard_id/shot_id/manifest_url/preview_url/srt_url/timeline_url/render_manifest_url/render_status/render_backend/segment_count`，前端不再需要打开 JSON 才能播放或下载 render artifact。
- [x] `/synthesis` 页面保留快速视频+音频合成功能，同时新增“合成历史筛选”、历史就地预览、字幕 SRT、时间线和渲染清单入口；历史播放不再复用页面上方当前合成结果区域。
- [x] 新增 Playwright 回归 `frontend/e2e/synthesis-history.spec.ts`，覆盖筛选请求、历史结果展示、就地预览和三类 artifact 链接。
- [x] 验证通过：`DEV_MODE=true PYTHONPATH=. python3 -m compileall app && DEV_MODE=true PYTHONPATH=. pytest -q ... test_workflow_routes.py` 153 passed；前端 `npx tsc --noEmit`、`npm run build`、构建后再次 `npx tsc --noEmit` 通过；Playwright `synthesis-history.spec.ts` 与 `workflow-production-guidance.spec.ts` 2 passed；内置浏览器确认 `/synthesis` 可见“合成历史筛选”。

## 2026-06-06 Phase 253 落地结果

- [x] 新增非 DEV workflow 批量生成门禁回归：`test_non_dev_workflow_media_batch_blocks_unverified_video_model_before_jobs`，确认未验证视频模型会在供应商调用和 VideoJob 创建前返回统一 `generation_preflight_failed`。
- [x] workflow 批量“视频+配音”生成在生产模式下逐镜头执行统一 `build_generation_context_package()` 预检，覆盖模型验证、参考图公网、lineage、实体引用和资产锁阻断。
- [x] 合成历史筛选修复快速输入后按钮读取旧 state 的问题，使用同步 ref 保证点击“筛选历史”时发送当前小说/章节/剧本/分镜/镜头/状态参数。
- [x] 验证通过：新增测试先红后绿；批量媒体专项 5 passed；后端紧凑一致性套件 154 passed；前端 `tsc -> build -> tsc` 通过；Playwright `synthesis-history.spec.ts` 与 `workflow-production-guidance.spec.ts` 2 passed。
- [x] 验证环境记录：旧 3000 dev server 可能复用 stale `.next` 导致 synthesis E2E 假失败，清理 `.next` 并重启前端后通过。

## 2026-06-06 Phase 254 P1 AI 制片下一步单项执行

- [x] AI 制片助手接口新增 `action_code`，保留不传时“安全补齐全部可自动动作”的旧行为。
- [x] 后端自动补齐改为按 `action_code` 精确执行，点击下一步只执行当前推荐动作，不再顺带刷新合约、转存媒体或持久化质量检查。
- [x] `/producer` 的“执行下一步”按钮传入当前 `next_action.code`；“安全补齐”按钮继续执行全部安全动作，保证轻量自动化与精确下一步并存。
- [x] 新增后端回归 `test_ai_producer_assistant_executes_only_requested_safe_next_action`，确认单项执行不会写入非目标动作的 production contract。
- [x] 新增前端 E2E `producer-next-action.spec.ts`，确认页面点击“执行下一步”提交 `{ auto_fix: true, action_code: ... }`。
- [x] 验证通过：`python3 -m compileall app`；`pytest -q test_production_control.py test_workflow_routes.py` 43 passed；前端 `tsc -> build -> tsc` 通过；Playwright `producer-next-action.spec.ts`、`workflow-production-guidance.spec.ts`、`synthesis-history.spec.ts` 3 passed。

## Phase 254 成功标准

- AI 制片中心的新手路径能明确“下一步只做这一件事”，不会因为一次点击把多个安全动作全部执行导致用户难以理解状态变化。
- 需要批量补齐时仍可使用独立“安全补齐/AI 补齐”入口，避免削弱自动化。
- 该能力必须同时有后端行为测试和前端请求 payload 测试，防止以后按钮回退成 broad `auto_fix=true`。

## 2026-06-06 Phase 255 P1 本集制片工程复用

- [x] AI 制片中心的创建工程逻辑改为“创建/复用本集工程”：同一用户、同一小说、同一章节已有未归档 workflow 时优先复用，不再重复 `POST /workflow/start`。
- [x] 复用已有 workflow 时，如果一键剧本/分镜生成返回了新的 `script_id/storyboard_id`，会通过 `updateWorkflowStep()` 挂载到已有工程，保持章节生产线唯一。
- [x] “一键生成本集草片”和章节一键生产都复用同一 `createWorkflowRecord()` 幂等入口，避免脚本、分镜、镜头、字幕和视频散落到多个同章节工程。
- [x] 前端按钮文案从“创建本集工程”改为“创建/复用本集工程”，降低用户误以为每次都新建的困惑。
- [x] 新增 Playwright 回归：已有 `novel_id + chapter_id` workflow 时点击“创建/复用本集工程”不会调用 `/workflow/start`，并保持当前 workflow 为 `wf-existing`。
- [x] 验证通过：前端 `tsc -> build -> tsc` 通过；Playwright `producer-next-action.spec.ts`、`workflow-production-guidance.spec.ts`、`synthesis-history.spec.ts` 共 4 passed。

## Phase 255 成功标准

- 同一本小说同一章节默认只有一条制片主线，减少角色、分镜、镜头、配音和视频生成结果分叉。
- 用户仍可在工程下拉中选择已有工程；显式“创建/复用”优先复用，不隐藏执行结果。
- 后续一键生产产物能挂到已有工程，而不是因为 `workflowId` 暂时为空就创建重复工程。

## 2026-06-06 Phase 256 P1 TTS 章节剧本过滤

- [x] 修复 `/tts` 创作链路选择剧本时只按小说过滤的问题；现在请求 `/scripts?novel_id=...&chapter_id=...`，确保配音剧本和当前章节一致。
- [x] `Script` 前端类型补齐 `chapter_id/extra_data`，本地兜底过滤同时检查 `script.chapter_id` 和 `script.extra_data.chapter_id`。
- [x] 章节被清空或切换时同步清空剧本、分镜、镜头选择，避免旧章节下游选择残留。
- [x] 新增 Playwright 回归：同一本小说两章两剧本，选择第二章后只展示第二章剧本，且脚本请求携带 `chapter_id=chapter-002`。
- [x] 验证通过：前端 `tsc -> build -> tsc` 通过；Playwright `tts-script-filter.spec.ts` 1 passed。

## Phase 256 成功标准

- TTS 配音不能把同一本小说其他章节的剧本混入当前章节，避免角色台词、音色锁和字幕上下文错位。
- 切换章节后所有下游创作对象必须重选，保证小说、章节、剧本、分镜、镜头链路一致。
- 后端已支持 `chapter_id` 过滤，本阶段只补齐前端调用和回归测试，不扩展新接口。

## 2026-06-06 Phase 257 P1 剧本 AI 自定义生成链路修复

- [x] 修复 `/scripts` 的“AI生成剧本 / 自定义描述”误调用 `/coding-plan/storyboard` 的问题；自定义描述改走剧本 AI 辅助能力，不再生成技术分镜文本。
- [x] 自定义生成后的“创建剧本”保留当前筛选小说、章节、题材和风格上下文，避免孤立剧本丢失章节链路。
- [x] 文本模型能力识别兼容 `model_type=text` 与 `capabilities=["text"]`，已验证默认文本模型能在剧本生成请求中带出 `model_config_id`。
- [x] 新增 Playwright 回归 `scripts-ai-generation.spec.ts`，覆盖自定义描述不访问技术分镜接口、走剧本 AI 辅助、保存时带 `novel_id/chapter_id`。
- [x] 验证通过：前端 `tsc -> build -> tsc` 通过；后端 `compileall app` 通过；Playwright `scripts-ai-generation.spec.ts` 1 passed。

## Phase 257 成功标准

- “AI生成剧本”弹窗中的任何生成方式都不能访问技术分镜接口。
- 自定义描述可以用于生成剧本草稿，并在保存时继承当前小说/章节上下文。
- 前端模型能力选择必须能识别已配置、已验证的文本模型，并把默认模型配置传入 AI 请求。

## 2026-06-06 Phase 258 P1 候选：视频历史回填镜头成片

- [x] 在 `/video-generation` 历史成功视频中增加“设为镜头视频”入口。
- [x] 成功历史任务可通过 `PUT /shots/{shot_id}` 回填 `video_url/video_status`，支撑旧任务迁移和人工挑选版本。
- [x] 新增 Playwright 回归，断言点击历史回填按钮会更新当前镜头。

## 2026-06-06 Phase 258 落地结果

- [x] `/video-generation` 的“生成历史”和“音视频直生历史”均支持把成功产物回填为镜头成片视频。
- [x] 回填按钮仅在任务成功、存在视频 URL、且能确定目标 `shot_id` 时展示，避免失败/生成中任务误写镜头。
- [x] 回填写入保持原始视频 URL，播放预览仍按后端静态媒体 origin 解析，避免把浏览器 origin 误写入数据库。
- [x] 回填成功后刷新镜头详情和历史列表，并把当前预览切换为回填的视频。
- [x] 新增 Playwright 回归 `frontend/e2e/video-generation-history-backfill.spec.ts`，覆盖视频历史和音视频直生历史两类产物回填请求。
- [x] 验证通过：Playwright `video-generation-history-backfill.spec.ts` 1 passed；前端 `npx tsc --noEmit` 通过；前端 `npm run build` 通过；后端 `DEV_MODE=true PYTHONPATH=. python3 -m compileall app` 通过。
