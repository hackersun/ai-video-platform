# 执行进度

## 2026-05-08

- 创建任务计划、发现记录和进度文件。
- 并行启动三个只读检查：后端 API 契约、前端调用契约、统一模型配置规划。
- 准备执行第一批小范围修复：路由挂载、合成契约、workflow 响应、模型默认配置敏感信息清理。
- 已修复后端核心路由挂载、合成契约、workflow 字段、角色创建返回、镜头重排路由顺序、TTS/Video 回写 Shot。
- 已修复前端 synthesis API 基址、TTS 链路路径、api-client TTS/合成类型、脚本详情页分镜路径。
- 新增 `docs/novel-to-anime-optimization-plan.md` 作为后续完整实施蓝图。
- 验证：`python3 -m compileall app` 通过；路由 smoke test 显示 workflow/images/assets/projects/timelines/storyboard-ai/synthesis/shots 路径已注册。
- 验证：`pytest -q test_workflow_routes.py` 通过，16 passed；`pytest -q test_parent_ownership_routes.py` 通过，12 passed。
- 前端验证：`npx tsc --noEmit` 未通过，剩余错误在 `frontend/src/app/login/page.tsx` 和 `frontend/src/app/register/page.tsx` 的既有 `AuthResponse.detail` 类型定义，不属于本次生成链路改动。

## 2026-05-09

- 复核未完成阶段，确认本轮目标：补齐统一模型规划 API、Story Bible/Prompt Composer、一致性 prompt 输出、任务 project/workflow 绑定、前端类型检查修复，并跑本地可行测试。
- 已新增 `backend/app/core/model_registry.py` 与 `/api/v1/llm/registry`、`/api/v1/llm/task-defaults`。
- 已新增 Story Bible 模型、路由、Prompt Composer，并挂载 `/api/v1/story-bibles`。
- 已让 Video/TTS/Synthesis 任务支持 `project_id/workflow_id`，并让 workflow 状态按绑定任务返回。
- 已修复前端 `AuthResponse.detail` 类型错误。
- 验证结果：`python3 -m compileall app` 通过；`pytest -q` 通过，33 passed、2 skipped；`npx tsc --noEmit` 通过；`npm run build` 通过。

## 2026-05-09 深度审计

- 使用 `web-design-guidelines` 技能时，外部规则源 `raw.githubusercontent.com` 拉取失败；本轮 UI 审计改用项目既有前端约束和页面代码静态检查。
- 已开始扫描 mock/placeholder/TODO/skip/未实现标记，发现前端仍有模拟生成、示例用户、模拟任务数据，后端仍有真实合成占位、OpenAI 视频占位、外部集成测试跳过等风险点。
- 已启动前后端并完成真实 API smoke；基础创作数据链路可用。
- 已运行前端页面 Playwright 审计：未认证 E2E 失败，带 DEV token 的主要页面全部可渲染。
- 最终回归：`python3 -m compileall app` 通过；后端 `pytest -q` 在服务启动状态下 45 passed、1 skipped；前端 `npx tsc --noEmit` 通过。

## 2026-05-09 Phase 10

- 开始修复“前端完整跑完流程”：目标是在 DEV_MODE 下提供本地生成闭环，消除关键页面静态模拟数据，并用 Playwright 从前端验证全流程。
- 已新增 DEV_MODE 本地生成工具，并让图片、TTS、视频、合成在无云 API Key 时生成可追踪的成功任务；视频/TTS/图片会回写 Shot，合成会产生输出任务记录。
- 已将任务中心改为读取真实后端任务聚合；移除 LLM 测试、剧本 AI 生成、个人资料页的误导性模拟成功/示例数据；新增 `frontend/e2e/full-flow.spec.ts` 覆盖浏览器登录态下的完整生成链路。
- 验证通过：`python3 -m compileall app`、后端 `pytest -q`（服务启动状态 45 passed、1 skipped）、前端 `npx tsc --noEmit`、`npm run build`、`npx playwright test e2e/full-flow.spec.ts --project=chromium`、`npx playwright test e2e/app.spec.ts --project=chromium`。

## 2026-05-10 深度分析

- 继续基于现有分析审计后端小说/章节/角色、StoryBible、分镜、镜头、资产、图片、TTS、视频、合成、workflow、项目权限和模型配置。
- 确认当前工程是“DEV_MODE 基础闭环 + 局部真实云调用”的原型，尚未达到外部小说导入、实体审阅、Story Bible 自动一致性、真实导出发布、项目成员权限隔离的可用产品标准。
- 发现前端关键阻断点：小说详情调用不存在的 `/novels/{id}/generate-cover`；章节详情页 `[chapter_id]` 代码读取 `params.chapterId`；团队页仍是静态数据；工作流是导航式向导而非状态机。
- 已更新 `findings.md` 和 `docs/novel-to-anime-optimization-plan.md`，补充 P0/P1/P2 任务、验收标准和推荐实施顺序。

## 2026-05-10 自动实施

- 已复核并确认当前基础编译通过：`python3 -m compileall app`。
- 已新增后端一致性上下文服务 `app/services/consistency_context.py`，把 Story Bible、项目风格、镜头字段、角色引用和任务默认模型元数据集中解析。
- 已把一致性上下文接入图像生成、镜头参考图生成、视频生成、TTS 生成、分镜生成；分镜生成同时修复了 `camera_movement/sound_effect/music_mood` 生成后未落库的问题。
- 验证通过：`python3 -m compileall app`；`pytest -q test_model_registry_story_bible.py test_workflow_routes.py test_parent_ownership_routes.py`，31 passed。
- 已合并后端小说导入、统一实体抽取、Story Bible 自动生成/章节同步/一致性检查能力，以及项目成员权限和本地发布导出能力。
- 合并后端验证通过：`python3 -m compileall app`；`pytest -q test_novel_import_story_bible.py test_model_registry_story_bible.py test_project_permissions_publication.py test_workflow_routes.py test_parent_ownership_routes.py`，39 passed。
- 已修正前端 API client 与页面契约：小说导入改走 `/novels/import/preview` + `/novels/import/confirm`，小说详情实体抽取改走 `/story-bibles/entities/extract`，Story Bible 改走 `generate-from-novel` 和 `check-consistency`，团队角色改为 owner/editor/viewer，合成发布/导出改走 `/synthesis/publish`。
- 全量验证通过：后端 `pytest -q` 结果 53 passed、1 skipped；前端 `npm run build` 通过；前端 `npx tsc --noEmit` 在 build 生成 `.next/types` 后通过；Playwright `e2e/full-flow.spec.ts` + `e2e/novel-import-story-bible.spec.ts` 结果 2 passed。
- 本地服务已重启并保持运行：后端 `http://127.0.0.1:8000`，前端 `http://localhost:3000`。
- 收尾检查通过：`git diff --check` 通过；清理尾随空格后再次运行 `npx tsc --noEmit` 通过。

## 2026-05-11 智能分镜自动化

- 开始分析“小说/章节自动匹配模板并生成分镜镜头”的流程。
- 确认现状：前端已有静态 `storyboard-templates.ts`，但没有接入后端；后端 `/storyboards/generate` 主要从剧本生成，不能直接从小说/章节生成。
- 本轮目标：把模板库后端化，新增模板匹配和小说/章节智能生成接口，并在前端分镜管理页提供入口。
- 已新增后端预制模板库与模板匹配服务，覆盖对话、动作、情绪、成长蒙太奇、悬疑揭示、世界观建立等常用动漫分镜结构。
- 已新增 `/api/v1/storyboards/templates`、`/api/v1/storyboards/templates/match`、`/api/v1/storyboards/generate-smart`，可直接从小说/章节生成自动改编脚本、分镜和镜头。
- 智能生成的镜头已补齐视觉描述、prompt、台词、镜头角度、运镜、情绪、光线、调色、音效、配乐、环境声、关键帧和 `extra_data.review_status=pending_review`，用于后续人工审核微调。
- 已在前端分镜管理页增加“智能生成”区域，支持选择小说/章节、镜头数、风格，展示自动匹配模板原因，并一键生成可编辑分镜。
- 已新增后端测试 `test_storyboard_templates.py` 和前端 E2E `frontend/e2e/smart-storyboard.spec.ts`。
- 补充前端缺失依赖 `@radix-ui/react-dialog`、`@radix-ui/react-dropdown-menu`、`@radix-ui/react-tooltip`，避免新环境中 `tsc` 因本地 node_modules 残留缺失而失败。
- 验证通过：`python3 -m compileall app`；后端 `pytest -q` 结果 66 passed、1 skipped；`pytest -q test_storyboard_templates.py` 结果 3 passed；前端 `npm run build` 通过；前端 `npx tsc --noEmit` 通过；`git diff --check` 通过；Playwright `e2e/full-flow.spec.ts` + `e2e/novel-import-story-bible.spec.ts` + `e2e/smart-storyboard.spec.ts` 结果 3 passed。
- 本地服务已重新启动并验证可用：后端 `http://127.0.0.1:8000/health` 返回 200，前端 `http://localhost:3000/storyboards` 返回 200。

## 2026-05-11 章节 AI 编辑与连续性

- 已把章节生成统一接入小说简介、全书章节顺序、上一章、下一章、Story Bible 和一致性上下文；新增 `chapter_writing` 任务默认模型规划。
- 已新增 `/api/v1/chapters/{chapter_id}/ai-assist`，支持 `rewrite`、`extend`、`polish` 三种模式。结果会立即更新章节正文、字数、状态和更新时间，并同步实体抽取与已有 Story Bible。
- `/api/v1/chapters/generate` 已改为复用同一套章节生成上下文，并在 DEV_MODE 无文本模型密钥时返回可验证草稿，避免本地全流程被云密钥阻断。
- 章节编辑页已从通用 `autoGenerate` 改为章节专用 AI 接口，增加补充要求、目标字数、AI 重写/续写/润色按钮；手工编辑会自动保存到数据库，页面显示保存状态。
- 已新增后端测试 `test_chapter_ai_assist.py`，覆盖章节生成上下文、AI 重写/续写/润色持久化、非法模式校验。
- 已新增前端 E2E `frontend/e2e/chapter-ai-edit.spec.ts`，覆盖章节编辑页自动保存、AI 续写、数据库持久化和实体抽取。
- 验证通过：`python3 -m compileall app`；后端 `pytest -q` 结果 69 passed、1 skipped；章节专项 `pytest -q test_chapter_ai_assist.py` 结果 3 passed；前端 `npm run build` 通过；前端 `npx tsc --noEmit` 通过；`git diff --check` 通过；Playwright `e2e/full-flow.spec.ts` + `e2e/novel-import-story-bible.spec.ts` + `e2e/smart-storyboard.spec.ts` + `e2e/chapter-ai-edit.spec.ts` 结果 4 passed。
- 当前服务可用：后端 `http://127.0.0.1:8000/health` 返回 200，前端 `http://localhost:3000/novels` 返回 200。
- 剩余非本轮风险：`backend/app/services/openai_service.py` 中 OpenAI Sora 仍是占位说明；`workflow.py` 仍有 workflow 级合成占位路径；`synthesis.py` 非 DEV_MODE 仍有“本地合成占位”命名；`characters.py` 有过时的“模拟数据库”注释；`usage_stats.py` 和 `external_api.py` 仍有 TODO。上述未影响本轮章节 AI 和小说到视频 DEV_MODE 全流程，但后续生产化需要继续收敛。

## 2026-05-11 视频链路连续性

- 开始审计视频生成链路，目标是补齐小说、章节、剧本、分镜、镜头到视频任务的连续性关联。
- 初步确认：后端视频接口已有部分 lineage 字段，但缺 `chapter_id` 和自动补全；前端视频生成页缺章节级联选择和 URL 参数承接。
- 已补齐后端视频 lineage：`/video/generate` 支持 `chapter_id`，可从 `shot_id` 自动反推分镜、剧本、章节、小说，并拒绝不匹配组合；`/video/jobs` 支持按 `novel_id/chapter_id/script_id/storyboard_id/shot_id` 过滤并返回标题/章节序号。
- 已补齐上游响应：剧本响应返回 `chapter_id`，分镜响应返回 `novel_id/chapter_id`，手动分镜会继承剧本的小说/章节来源。
- 已优化前端视频生成页：制作链路控件常驻显示，支持小说、章节、剧本、分镜、镜头级联选择；URL 可带入 `workflow_id/novel_id/chapter_id/script_id/storyboard_id/shot_id`；镜头会自动填充 prompt/参考图；历史记录按当前链路过滤。
- 已补充后端测试 `test_video_job_infers_full_lineage_from_chapter_shot` 和前端 E2E `video generation page preserves novel chapter script storyboard shot lineage`。
- 验证通过：`python3 -m compileall app`；后端 `pytest -q` 结果 70 passed、1 skipped；`pytest -q test_workflow_routes.py` 结果 17 passed；前端 `npx tsc --noEmit` 通过；前端 `npm run build` 通过；Playwright `e2e/full-flow.spec.ts` 结果 2 passed；`git diff --check` 通过。
- 本地服务已重启并验证可用：后端 `http://127.0.0.1:8000/health` 返回 200，前端 `http://localhost:3000/video-generation` 返回 200。

## 2026-05-11 多镜头连续成片与竞品对标

- 已开始联网调研 Runway、Kling、Luma、Pika、PixVerse、Animaker、Vyond、Canva、Adobe Firefly 等平台，结论已写入 `findings.md`。
- 已确认本轮最小生产化目标：先把 workflow 合成从“返回第一个视频 URL”升级为“生成可消费的多镜头成片 manifest”，包含镜头顺序、视频、配音、字幕、转场、总时长、血缘和一致性元数据。
- 已更新 `task_plan.md`，新增 Phase 34-37 和明确验收标准。
- 后端已把 `/workflow/concatenate/{workflow_id}` 改为多镜头连续成片 manifest：校验视频/TTS成功状态、按输入顺序组织 segments、按 `shot_id` 匹配配音、输出字幕轨和转场信息，并写入 `/static/exports/*.json`。
- 专项测试首次失败发现智能分镜模板可产出 2-3 秒镜头，但视频模型最小 4 秒；已把模板生成镜头时长归一到 4-10 秒，避免后续分镜到视频批量生成被模型约束阻断。
- 前端 workflow 页已支持 `?workflow_id=` 恢复已有工作流，并在合成步骤展示多镜头连续成片状态、镜头数、配音数、段落数、预计时长、成片清单和 DEV_MODE 输出链接。
- 新增后端测试 `test_workflow_concatenate_builds_multi_shot_sequence_manifest`，验证两个镜头视频、两个 TTS、字幕、转场、manifest 文件和 workflow 状态回读。
- 新增前端 E2E `workflow page shows multi-shot continuous final video manifest`，从浏览器会话创建小说/章节/智能分镜/工作流/视频/TTS/连续成片，并打开 workflow 页面验证 manifest 可见。
- 已更新 `docs/novel-to-anime-optimization-plan.md`，补充竞品对标后新增结论、已落地的 workflow 成片清单，以及仍需真实 FFmpeg/云剪辑渲染器的生产差距。
- 验证通过：`python3 -m compileall app`；后端 `pytest -q` 结果 71 passed、1 skipped；后端专项 `pytest -q test_workflow_routes.py` 结果 18 passed；前端 `npm run build` 通过；前端 `npx tsc --noEmit` 通过；Playwright `e2e/full-flow.spec.ts` 结果 3 passed；`git diff --check` 通过。
- 当前服务已用最新代码重启并验证可用：后端 `http://127.0.0.1:8000/health` 返回 200，前端 `http://localhost:3000/workflow` 返回 200。

## 2026-05-11 全流程竞品深度对标与 CRUD 审计

- 已进一步扩展竞品对比范围，按四类平台整理：AI 视频生成型、在线动画制作型、通用视频编辑发布型、数字人口播型。
- 已把全流程功能矩阵、制作流程对比、动漫题材/分镜/镜头参数模板、AI辅助能力、低门槛产品设计、CRUD删除缺口写入 `docs/novel-to-anime-optimization-plan.md`。
- 已补充 `findings.md`：本平台定位应是“长篇小说改编动漫生产线”，差异化优势是小说/章节/Story Bible/实体/镜头链路，短板是模板可视化、资产版本锁定、关键帧、Timeline、真实渲染、任务/发布 CRUD。
- CRUD 审计结论：后端缺 VideoJob、NovelImportJob、Publication、StoryEntity、StoryboardTemplate、ExternalAPIConfig 的完整删除/取消/归档/重试能力；前端缺任务中心删除处理、整分镜删除、资产/Story Bible/实体/工作流/时间线/发布记录删除或归档入口。
- 本轮仅更新规划与发现文件，没有改业务代码；因此不需要重新跑编译/测试。已运行 `git diff --check` 做格式收尾。

## 2026-05-12 Phase 41 易用性与 CRUD 补齐

- 复盘 `task_plan.md`、`progress.md`、`findings.md`，确认唯一未完成阶段为 Phase 41。
- 已落地任务队列页的查询过滤条件，补齐任务类型、时间范围、自定义日期、产物状态、排序和重置筛选，不影响取消/删除/下载等原有操作。
- 过滤实现保持前端本地筛选，不改后端任务接口契约；展示文本和任务操作流程保持不变。
- 发现并修复前端刷新后样式丢失问题：`next dev` 的 `/_next/static/css/app/layout.css` 在旧缓存状态下返回 404；已清理 `frontend/.next` 并重启前端服务，样式资源恢复 200。
- 确认后端已有一批前序落地能力：VideoJob 取消/软删除，NovelImportJob 更新/重试/归档，Publication 列表/更新/撤销/归档，StoryEntity CRUD，Asset/template 软删除，任务中心真实聚合。
- 新增前端 `/quick-start` 极速向导：用户输入作品名、梗概、首章、题材、风格和镜头数后，前端顺序调用 Novel、Chapter、Story Bible、`/storyboards/generate-smart` 和 `/workflow/start`，生成首集制作工作区。
- 顶部导航新增“极速向导”，保留实体库、模板库、任务队列等管理入口。
- 实体库页面补齐编辑能力：可修改实体类型、名称、别名和描述；编辑按钮增加稳定 `title`，便于测试和可访问操作。
- 模板库页面补齐编辑能力：可修改模板名称、类型、标签、描述、提示词、镜头数和公开状态；自定义模板继续走 Asset API 存储和软归档。
- API client 补齐 `generateSmartStoryboard`、扩展 `startWorkflow` 支持 `chapter_id/script_id/storyboard_id`，新增 `updatePublication`。
- 新增 E2E 覆盖：`quick start creates an editable first episode workspace`、`management pages can edit templates and entities`。
- 验证通过：`python3 -m compileall app`；`pytest -q test_project_permissions_publication.py test_workflow_routes.py test_storyboard_templates.py` 结果 28 passed；`npm run build` 通过；`npx tsc --noEmit` 通过；`git diff --check` 通过；Playwright 新增两条用例 2 passed。
- 本地服务已启动并验证可用：后端 `http://127.0.0.1:8000/health` 返回 healthy，前端 `http://localhost:3000/quick-start` 返回 200。

## 2026-05-12 生成级生产化稳定阶段

- 新增 Phase 42-44，目标是把 workflow 多镜头 manifest 推进到“可预检、可重试、可下载本地渲染包”的稳定生成级闭环。
- 初步审计确认：`/workflow/concatenate/{workflow_id}` 已能产出多镜头 manifest 和 SynthesisJob，但当前 `render_backend=local_manifest`，尚缺单独的渲染预检、渲染执行/重试、SRT/EDL/HTML preview 等用户可消费 artifact。
- 本轮实现边界：DEV_MODE 下优先生成本地渲染包，不引入真实 FFmpeg 或新云剪辑供应商；非 DEV_MODE 可保留 pending_renderer 状态和结构化预检结果。
- 后端已新增 `/api/v1/workflow/{workflow_id}/render/preflight` 和 `/api/v1/workflow/{workflow_id}/render`；预检返回结构化 issues，渲染输出 render manifest、timeline EDL、SRT、HTML preview，并回写 `SynthesisJob.extra_data.render_*` 和 `Workflow.metadata_`。
- 前端 API client 已补齐 `preflightWorkflowRender`、`renderWorkflowPackage`；workflow 合成步骤增加渲染预检、生成/重新渲染、issue 列表和 artifact 链接，导出步骤展示 HTML 预览、SRT、时间线 EDL、渲染清单。
- E2E 已扩展 `workflow page shows multi-shot continuous final video manifest`，覆盖连续成片 manifest 后点击“渲染预检”、预检通过、生成本地渲染包、展示四类 artifact。
- 验证过程发现 8000 后端旧进程未加载新增 render 路由，已重启后端并用 curl 确认预检接口 200；Playwright 配置原先检查根路径 `/`，但当前根路径 404，已改为检查 `/workflow`；`next build` 后需重启 dev server 避免 `.next` chunk 404。
- 验证通过：`python3 -m compileall app`；`pytest -q test_workflow_routes.py` 结果 21 passed；前端 `npm run build` 通过；`npx tsc --noEmit` 通过；Playwright `npx playwright test e2e/full-flow.spec.ts --project=chromium -g "workflow page shows multi-shot"` 结果 1 passed；`git diff --check` 通过。

## 2026-05-12 生产一致性贯穿修复

- 已核验分支：当前在 `main`；`workflow-fixes` 和 `worktree-agent-a9b328a1` 均已是 `main` 祖先；本地 `main` 领先 `origin/main` 39 个提交，当前还有大量未提交改动，因此未执行额外合并。
- 已新增一致性上下文 helper：可按 novel/chapter 加载或自动抽取 `StoryEntity`，并为镜头生成 `character_refs`、`scene_refs`、`prop_refs`、`event_refs`、`environment_context`。
- 智能分镜持久化已把人物、场景、道具、事件、环境和 `subtitle_text` 写入 Shot；视频生成已把这些上下文注入最终 prompt，并在 VideoJob response 中返回。
- 视频生成页已改为加载全部角色，不再只显示带 avatar 的角色；当前镜头和生成历史都展示人物、场景、道具、事件和字幕信息。
- 验证通过：`python3 -m compileall app`；`pytest -q test_storyboard_templates.py` 4 passed；`pytest -q test_storyboard_templates.py test_workflow_routes.py` 25 passed；`npx tsc --noEmit` 通过；`npm run build` 通过；Playwright `npx playwright test e2e/full-flow.spec.ts --project=chromium -g "video generation page preserves"` 1 passed；`git diff --check` 通过。

## 2026-05-12 分支与全量验证复核

- 分支复核：当前仍在 `main`；`git branch --no-merged main` 无输出；`workflow-fixes` 和 `worktree-agent-a9b328a1` 均已合入本地 `main`。
- 远端状态：`main...origin/main` 为 `39 0`，即本地 `main` 领先远端 39 个提交且远端无新增提交；当前工作树仍有大量未提交/未跟踪文件，因此尚不能视为已推送或发布。
- 后端验证沿用本轮已完成结果：`python3 -m compileall app` 通过；后端全量 `pytest -q` 结果为 79 passed、1 skipped。
- 前端验证：`npm run build` 通过；`npx tsc --noEmit` 通过；`git diff --check` 通过。
- Playwright 复核：完整 51 用例首次运行时因 `next build` 后旧 dev server 复用 `.next` 出现 `Cannot find module './vendor-chunks/@swc.js'`，已清理 `.next` 并重启干净 dev server 后重跑关键链路。
- 干净 dev server 下关键链路 `npx playwright test e2e/chapter-ai-edit.spec.ts e2e/full-flow.spec.ts --workers=1` 结果为 6 passed、3 failed；通过项包含小说到动漫 DEV_MODE 链路、任务取消归档、极速向导、模板/实体编辑、视频生成页链路谱系、多镜头连续成片 manifest。
- 失败项：`chapter-ai-edit.spec.ts` 两个章节 AI 写作用例在 60 秒超时，失败点为 alert/dialog 接受时页面已关闭；`full-flow.spec.ts` 的发布记录撤销/归档用例在定位 `撤销发布` 按钮时 30 秒超时。

## 2026-05-12 极速向导与链路关联修复

- 修复极速向导可用性：新增本地草稿自动保存、手动“保存草稿”按钮和恢复能力；“生成首集工程”不再因必填项未完成而灰掉不可点，点击后明确提示缺少作品名、梗概、章节内容或镜头数。
- 优化分镜页链路：支持按小说/章节筛选分镜，`?storyboard_id=` 会自动选中目标分镜；分镜列表和详情展示小说、章节、剧本上游链路。
- 分镜页新增“生成视频”和每个镜头的“生成镜头视频”入口，跳转到视频生成页时带完整 `novel_id/chapter_id/script_id/storyboard_id/shot_id`。
- 优化视频生成页级联：选小说/章节后会加载并过滤对应剧本、分镜和镜头；URL 只带镜头或分镜时也会补齐并显示上游链路。
- 后端手动创建/更新/批量创建镜头时，会根据所属分镜的小说/章节/剧本重新构建人物、场景、道具、事件、环境和字幕上下文，避免只有智能分镜路径具备一致性信息。
- 验证通过：`python3 -m compileall app`；`pytest -q test_storyboard_templates.py test_workflow_routes.py` 25 passed；`npx tsc --noEmit` 通过；`npm run build` 通过；`git diff --check` 通过；Playwright `quick start|video generation page preserves` 2 passed。
- 服务已重启并验证：后端 `/health` 200，前端 `/quick-start` 和 `/storyboards` 200。

## 2026-05-12 角色小说归属修复

- 开始修复角色跨小说泄漏问题：目标是新增角色小说/章节归属，后端按小说过滤，前端角色管理与视频生成按当前小说取数。

## 2026-05-12 角色小说归属隔离修复

- 已为 Character 模型新增 `novel_id/chapter_id`，并在 `init_db.py` 增加同步/异步迁移，当前本地数据库已执行迁移。
- `/characters` 支持 `novel_id/chapter_id/include_global` 查询参数；传 `novel_id` 时默认只返回该小说角色，`include_global=true` 才会包含未绑定小说的全局角色。
- 创建、更新、AI 提取角色会校验小说/章节归属并保存到 Character；章节归属会自动反推小说，章节不属于指定小说时返回 422。
- `build_shot_entity_context()` 不再全用户按名称匹配角色，改为当前小说/章节优先，最多回退全局角色；`build_consistency_prompt()` 会拒绝把其他小说的角色 ID 注入当前小说生成上下文。
- TTS 多角色对白按角色名取音色时改成当前小说/章节范围匹配，避免同名角色跨小说串音色。

## 2026-05-19 小说/剧本连续性审计

- 已完成小说管理、章节生成、剧本生成、Story Prompt Context、StoryEntity/Story Bible、前端小说详情和剧本页的针对性代码审计。
- 结论：章节生成和封面/分镜/视频已较多复用统一故事上下文；剧本生成仍是主要短板，未复用 `load_story_prompt_context()` 和 production pack，且“前情提要”可能在改编中间章节时误取后续章节。
- 已更新 `findings.md`，记录剧本生成提示词、章节关联、人物关系、事件线、前端生产入口的缺口。
- 已更新 `task_plan.md`，新增 Phase 64-69，作为下一轮落地开发计划。
- 角色管理页新增“小说范围”筛选，创建角色可选所属小说；从小说/章节/手动文本提取后会刷新到对应小说范围。
- 视频生成页加载角色参考时随 `selectedNovel` 调用 `/characters?novel_id=...`，切换小说会清空旧角色参考和图片，避免沿用上一部小说的角色。
- 新增 `backend/test_character_scope.py`，覆盖小说过滤、镜头实体同名角色匹配、TTS 同名角色音色匹配。
- 验证通过：`python3 -m compileall app`；`pytest -q test_character_scope.py test_storyboard_templates.py test_workflow_routes.py` 28 passed；`npx tsc --noEmit` 通过；`npm run build` 通过；`git diff --check` 通过。
- 服务已重启并验证：后端 `http://127.0.0.1:8000/health` 200，前端 `http://localhost:3000/characters` 200。

- 补充修复：TTS 从 `shot_id` 进入时会通过分镜/剧本反推 `novel_id/chapter_id`，多角色按名称取音色也能保持小说作用域。复验通过：`python3 -m compileall app`；`pytest -q test_character_scope.py test_workflow_routes.py` 24 passed；`npx tsc --noEmit` 通过；`git diff --check` 通过。

## 2026-05-12 视频历史与一致性再修复

- 已修复 DEV_MODE 视频历史不可播放的底层问题：`dev_video_url()` 和 `dev_synthesis_url()` 会实际写入一个本地可播放 MP4，占位 URL 不再指向不存在的文件。
- 已修复视频下载代理：`/api/v1/video/download` 支持本地 `/static/...` 相对路径和后端静态文件直返，远端 URL 仍走代理下载；404/超时错误不再被吞成不明确异常。
- 已修复前端视频生成页：当前预览和历史播放会把相对媒体 URL 解析到后端 origin；历史下载按钮改为调用下载代理并用 blob 触发下载；历史图标按钮补充 `title`，便于可访问操作和 E2E。
- 已加固生成一致性：分镜/剧本风格、题材、说明和镜头编号会进入一致性 prompt；`shot_video` prompt 增加明确的视频一致性约束；未显式传 seed 时会按 Story Bible/小说/章节/剧本/分镜/镜头/模型派生稳定 seed。
- 已修复真实视频 SDK 调用参数：`seed/duration/resolution/camera_fixed/watermark` 作为顶层参数传入，同时 prompt 文本中补回 `--resolution`。
- 验证通过：`python3 -m compileall app`；`pytest -q test_workflow_routes.py test_storyboard_templates.py` 27 passed；`npx tsc --noEmit` 通过；`npm run build` 通过；Playwright `video generation page preserves novel chapter script storyboard shot lineage` 1 passed；`git diff --check` 通过。
- 服务已重启并验证：后端 `http://127.0.0.1:8000/health` 200，前端 `http://localhost:3000/video-generation` 200。

## 2026-05-13 动漫制作平台与插件生态规划

- 使用 planning-with-files 接续当前任务，复盘 `task_plan.md`、`findings.md`、`progress.md` 和 `docs/novel-to-anime-optimization-plan.md`。
- 只读审计当前代码：`model_registry.py` 目前覆盖 `shot_video/tts_dialogue/final_synthesis`，缺 `shot_audio_video` 和字幕/口型/音效等能力；`VideoJob` 不支持一等 `audio_url/subtitle_track_id`；`SynthesisJob` 是合成任务而非直生音视频任务；Timeline 已有 subtitle clip 字段但 workflow 未自动落库为可编辑字幕轨。
- 联网对标官方资料：OpenAI Sora 2、Google Veo 3、Runway Gen-4 References、Canva AI Video Generator、Toon Boom Harmony、Clip Studio Paint、Blender Grease Pencil、Live2D、ComfyUI、ControlNet、AnimateDiff。
- 已更新 `findings.md`：补充平台/插件生态对标、当前工程直接音视频和字幕缺口、推荐架构结论。
- 已更新 `task_plan.md`：新增 Phase 59-66，把本轮分析、数据契约、字幕链路、直生音视频、前端工作台和验证拆为可执行阶段。
- 已更新 `docs/novel-to-anime-optimization-plan.md`：新增 2026-05-13 深度对标、目标架构、API 契约、Provider capability registry、P0/P1/P2 优化计划和新验收路径。
- 本轮为规划与文档更新，没有修改运行时代码；需执行 `git diff --check` 做格式收尾。

## 2026-05-13 直生音视频与字幕一等公民落地

## 2026-06-02 全流程回归验收

- 本轮目标：围绕小说/章节、角色/实体/资产、剧本、分镜/镜头、TTS、视频、合成/workflow、模型配置、任务/发布等核心子功能做一次本地回归验证。
- 验收边界：不真实消耗外部 AI/视频额度，优先验证 DEV_MODE、本地服务、自动化测试、关键页面渲染和核心接口链路。
- 待执行：服务健康检查、后端 pytest、前端 tsc/build、关键 Playwright/E2E、模块完备度和优化点汇总。
- 服务健康检查：前端 `http://127.0.0.1:3000/login` 返回 200，后端 `http://127.0.0.1:8000/health` 返回 healthy；3000 和 8000 端口均有监听进程。
- 后端全量 pytest 第一轮：收集阶段失败，原因是根目录和 `backend/tests/` 下存在同名 `test_consistency_checker.py`，pytest 导入模块名冲突；已新增 `backend/tests/__init__.py` 让子目录按包名收集。
- 后端全量 pytest 第二轮：`367 passed, 1 skipped, 18 warnings`；warning 为开发环境 `FERNET_KEY` 未配置和测试代码 `datetime.utcnow()` 过时提示。
- 前端 `npm run build` 通过。`npx tsc --noEmit` 与 build 并行运行时因 `.next/types` 被构建过程重写产生 TS6053 竞态缺文件，需在 build 完成后单独重跑。
- 前端 `npx tsc --noEmit` 单独重跑通过。

## 2026-06-06 生产级全链路深度分析

- 本轮目标：基于现有代码和已落地阶段，重新梳理小说到动漫视频生产链路，输出面向个人/小团队的生产级一致性、AI 赋能、工作流、界面和测试优化方案。
- 已复盘 `task_plan.md`、`findings.md`、`progress.md`，确认当前已有大量 P0/P1 能力落地，但主风险从“有没有接口”转为“能力是否强制贯穿、是否前端可见、是否形成低门槛生产链路”。
- CodeGraph 未初始化，已改用 `rg`、关键文件审计和子 agent 只读审计推进。
- 已并行派发 3 个只读 explorer：后端一致性/生成链路、前端工作流/交互可见性、测试与生产风险；主线程继续负责最终架构方案与计划文档。

## 2026-05-27 参考图公网交付能力

- 已新增对象存储/CDN生产适配 provider：`object_storage`，能力包含公开静态媒体出口、CDN交付、后续 S3/MinIO/OSS 预留。
- 已新增 `backend/app/services/media_delivery.py`，统一判断云端可访问 URL，并把本地 `/static/...` 按用户默认对象存储/CDN配置映射为公网 URL。
- 视频生成和 workflow 批量视频生成已接入参考图交付解析：有公网配置时传 `provider_image_url` 给火山图生视频；无配置或配置未验证时继续安全跳过，避免 `content[0].image_url` 400。
- VideoJob `prompt_parameters` 会记录原始 `image_url`、实际 `provider_image_url`、`image_delivery_method`、`image_delivery_config_id` 和跳过原因。
- 生产适配前端页面已展示对象存储/CDN能力、应用入口、状态卡片和配置提示，配置后可作为默认公网参考图出口使用。
- 验证通过：`python3 -m compileall app`；`DEV_MODE=true pytest -q test_production_adapters.py test_workflow_routes.py test_volcano_service.py` 48 passed；前端 `npx tsc --noEmit` 通过；`npm run build` 通过；`git diff --check` 通过。
- 服务已重启并验证：后端 `/health` 200，前端 `/production-adapters` 200，前端 `/video-generation` 200。

- 新增后端模型：`MediaGenerationJob`、`SubtitleTrack`、`SubtitleSegment`，并在 `init_db.py` 中加入同步/异步 SQLite 兼容迁移。
- 扩展 `model_registry.py`：新增 `openai.sora_2`、`google.veo_3`、`local.subtitle_exporter`，新增任务默认 `shot_audio_video` 与 `subtitle_generation`，为真实直生音视频供应商接入预留 capability matrix。
- 新增后端 API：`/api/v1/media/generate`、`/api/v1/media/jobs`、`/api/v1/media/jobs/{id}`、`/api/v1/media/jobs/{id}/export-subtitles`；DEV_MODE 下直生音视频会输出本地可播放 MP4、占位音频、字幕轨和 lineage。
- 新增字幕 API：可从 Shot、TTS、MediaJob 生成字幕轨，支持字幕段新增/编辑/归档，并导出 SRT/VTT/ASS。
- 新增 workflow 批量能力：`/api/v1/workflow/{workflow_id}/generate-media-batch` 可按工作流分镜镜头批量生成直生音视频草稿和字幕轨，并回写 Shot 音视频状态。
- 前端 `video-generation` 页面新增生成模式切换：静音视频走原 `/video/generate`，直生音视频走 `/media/generate`；成功后展示字幕轨、SRT 导出按钮和直生历史。
- 前端 API client 增加 `generateMedia/getMediaJobs/getSubtitleTrack/createSubtitleTrackFromShot/updateSubtitleSegment/exportSubtitleTrack/generateWorkflowMediaBatch`。
- 新增后端测试 `test_media_subtitles.py`：覆盖单镜头直生音视频、字幕轨导出、字幕段编辑和 workflow 批量直生。
- 新增浏览器 E2E：`video generation page can create direct audio video with subtitle track`，验证页面选择直生音视频、预览、字幕轨和字幕导出。
- 验证通过：`python3 -m compileall app`；`pytest -q test_media_subtitles.py test_workflow_routes.py` 26 passed；`npm run build` 通过；build 后单独 `npx tsc --noEmit` 通过；Playwright 新增用例 1 passed；`git diff --check` 通过。

## 2026-05-13 P1/P2 模型目录生产化补强

- 确认 P1/P2 仍有真实云渲染、Timeline 可视化、字幕烧录、多人审核、资产版本锁 UI、企业权限和真实通知等生产适配任务。
- 本轮继续执行可验证的 P1/P2 项：补齐火山 Seedance 2.0 模型目录和已有数据库的模型回填，避免前端视频模型列表与后端运行时目录不一致。
- 已新增火山模型：`doubao-seedance-2-0-260128`、`doubao-seedance-2-0-fast-260128`，覆盖 `volcano_config.py`、`model_registry.py`、`init_llm_config.py` 和 `/llm/models` 默认目录。
- `shot_video` 默认模型已调整为 `volcano.seedance.2_0_fast`，并保留 Seedance 2.0 与 1.0 Pro Fast 作为 fallback。
- `/llm/providers`、`/llm/models` 已改为在已有数据库中也回填/更新内置目录；同时修正 `Doubao-Seed-2.0-pro` 为 `chat`，避免误出现在视频模型列表。
- 新增专项测试覆盖模型目录回填和 `/video/generate` 选择 `doubao-seedance-2-0-fast-260128` 后实际提交该 endpoint。
- 验证通过：`python3 -m compileall app`；`pytest -q test_text_model_config.py test_model_registry_story_bible.py test_workflow_routes.py` 39 passed；后端全量 `pytest -q` 101 passed、1 skipped；前端 `npm run build` 通过；前端 `npx tsc --noEmit` 通过；`git diff --check` 通过。
- 已用 `tmux` 重启本地服务并验证：后端 `http://127.0.0.1:8000/health` 返回 healthy，前端 `http://127.0.0.1:3000/video-generation` 返回 200，`/api/v1/llm/models?provider=volcano` 已返回两个 Seedance 2.0 模型。

## 2026-05-14 顶部菜单下拉修复

- 修复顶部导航“工具 / 更多”下拉失效问题：改为 Radix `DropdownMenu`，菜单内容通过 portal 渲染，避免被横向滚动导航容器裁掉。
- 将两个菜单设置为 `modal={false}`，避免打开“工具”后“更多”从无障碍树里消失，保证两个并列菜单都可连续展开。
- 菜单项改为 `router.push` 跳转，避免 `asChild` 链接行为差异导致的点击不稳定。
- 新增前端 E2E `frontend/e2e/top-navigation.spec.ts`，覆盖“工具 / 更多”菜单展开和功能入口可见性。
- 验证通过：`npx tsc --noEmit`、`npx playwright test e2e/top-navigation.spec.ts --project=chromium`、`git diff --check`。
- 本地服务已重启并验证：后端 `http://127.0.0.1:8000/health` 200，前端 `http://localhost:3000/video-generation` 200。

## 2026-05-14 P0/P1 轻量生产资料包落地

- 已补齐 StoryEntity 生产资料包能力：按小说聚合角色、场景、道具、事件、人物关系、事件时间线、场景标签和资产需求。
- 已补齐实体一致性检查：提示角色多视图缺失、场景标签缺失、道具 DNA 缺失、事件参与者或道具未登记。
- 已补齐实体版本快照和恢复接口，并修复实体属性更新会覆盖 `version_snapshots` 的问题，避免资产包编辑后丢失可回滚版本。
- 已补齐镜头生产上下文的实体参考绑定：`entity_reference_bindings` 会解析 StoryEntity 并保存实体类型、名称、描述、视觉 DNA 和资产包。
- 前端 `/entities` 已展示小说范围、生产资料包、一致性检查、属性 JSON 编辑、实体快照和恢复入口。
- 前端 `/shots` 的生产上下文面板已补充实体参考绑定 JSON，镜头媒体生成和生产适配可拿到角色/场景/道具/事件绑定。
- 新增后端测试 `test_story_entity_production_pack.py`，覆盖生产包、一致性检查、版本快照/恢复和镜头实体绑定。

## 2026-05-27 分镜与角色生成修复

- 已复盘当前任务和计划文件，确认本轮聚焦可直接验证的阻断点：分镜整删、AI 分镜入口、角色抽取排重、头像上下文生成、封面错误提示。
- 已审计后端 `storyboards.py`、`characters.py`、`novels.py`、`images.py` 和前端 `storyboards/page.tsx`、`characters/page.tsx`、`novels/[id]/page.tsx`。
- 确认分镜智能生成后端能力已存在，但前端显式入口不足；确认角色头像应新增专用后端接口，前端不再手拼通用图片 prompt。
- 已修复后端分镜删除：删除 Storyboard 前显式删除所属 Shot，并返回 `deleted_shot_count`。
- 已新增后端角色头像接口 `/characters/{id}/generate-avatar`，提示词包含小说题材/简介、角色描述、外貌、性格、声音、标签和性别锚点；DEV_MODE 无图像 Key 时返回本地持久头像。
- 已修复角色提取排重：同一小说范围内同名角色会更新已有记录，跨小说同名角色保持隔离。
- 已更新前端分镜页：页头、空态、新建弹窗、详情区都有更明显的 AI 生成入口；列表卡和详情区支持删除整分镜。
- 已更新前端角色页：创建后自动头像和手动头像均调用角色头像专用接口；小说详情封面生成会展示后端具体错误。
- 验证通过：`python3 -m compileall app`；`pytest -q test_character_scope.py test_storyboard_templates.py` 11 passed；`pytest -q test_character_scope.py test_storyboard_templates.py test_workflow_routes.py` 39 passed；`npx tsc --noEmit` 通过；`npm run build` 通过；构建后 `npx tsc --noEmit` 通过；`git diff --check` 通过。

## 2026-05-27 题材预设库扩展

- 已根据用户要求开始扩展分镜风格、模板、资产、实体、角色预设。
- 联网调研后归纳题材元素：修仙重宗门/灵气/突破/雷劫/法宝/秘境；武侠重江湖/门派/侠义/秘籍/擂台/刀剑；玄幻重血脉/异兽/神器/圣地/古遗迹；都市异能重现代城市/隐藏组织/实验室/夜巷/觉醒/追查。
- 确认落地入口：后端系统分镜模板 `storyboard_template_service.py`，默认资产/实体库 `default_anime_library.py`，前端风格下拉 `shot-labels.ts`。
- 已新增 8 个系统分镜模板：修仙突破/雷劫、宗门审判、武侠江湖对决、武侠夜探门派、玄幻秘境探索、玄幻血脉觉醒、都市异能觉醒、都市夜巷追查。
- 已扩展默认实体库：题材角色、宗门/门派/现代城市/秘境场景、法宝/玉牌/秘籍/灵核/门禁卡道具，以及突破、比武、秘境开启、都市觉醒事件。
- 已扩展默认资产库：修仙、武侠、玄幻、都市异能场景包和题材提示词，可作为全局资产复用，也可在资产库里编辑。
- 前端分镜风格下拉新增修仙/仙侠、武侠江湖、玄幻冒险、都市异能、东方幻想、现代都市；模板库卡片增加关键词展示，方便确认题材模板。
- 验证通过：`python3 -m compileall app`；`pytest -q test_storyboard_templates.py test_asset_templates.py test_story_entity_production_pack.py` 19 passed；前端 `npx tsc --noEmit` 通过；`npm run build` 通过；构建后再次 `npx tsc --noEmit` 通过；`git diff --check` 通过。

## 2026-05-14 P1/P2 镜头质量准入与审核流

- 接续 P1/P2 任务，选择可落地且可验证的切片：镜头质量准入、预算提示和多人审核的最小闭环。
- 后端新增 `POST /api/v1/shots/quality/batch`，可对选中镜头去重批量重检，写回 `Shot.extra_data.quality_report` 和 `budget_estimate`，并返回缺失 ID。
- 后端生产上下文更新后会同步刷新质量报告；审核通过或锁定后，不再提示“完成镜头审核后再进入批量生成或真实渲染”。
- 前端 `/shots` 新增质量状态、审核状态筛选；镜头卡片展示质量徽标、评分、审核状态、风险数量和预算 token。
- 前端 `/shots` 选中镜头后新增“批量重检”“批量通过”“退回修改”，批量审核后自动刷新质量报告，作为批量生成前的准入操作。
- 新增后端测试 `test_shot_quality_batch_refreshes_reports_and_review_state`，覆盖批量重检、缺失 ID、审核状态影响质量建议。
- 验证通过：`python3 -m compileall app`；`pytest -q test_production_adapters.py` 6 passed；前端 `npx tsc --noEmit` 通过；`git diff --check` 通过。
- 浏览器验证：未登录访问 `/shots` 正常跳转登录；注入 DEV token 后 `/shots` 可打开，筛选面板可见“质量状态/审核状态”，临时镜头数据下可见“批量重检/批量通过/退回修改”和质量/审核徽标。临时测试小说已删除。

## 2026-05-13 全流程工作台对齐与生产就绪检查

- 审计前后端能力对齐后，确认最大缺口在 workflow 页面：后端已有批量直生音视频和字幕能力，但页面没有入口、状态不展示、步骤按 `current_step` 锁死。
- 后端 `/workflow/status/{workflow_id}` 已返回 `media_jobs`、`subtitle_tracks` 和 `metadata`，供前端展示媒体任务、字幕轨和生产就绪检查。
- 后端 `/workflow/concatenate/{workflow_id}` 已支持 `media_job_ids`，直生音视频任务会作为视频段落进入 manifest，并把直生音频、字幕文本、小说/章节/剧本/分镜/镜头 lineage 写入连续成片清单。
- workflow 页面现在会从状态接口回填 `novelId/chapterId/scriptId/storyboardId`，并按已有产物解锁步骤，避免生成首集工程后视频/合成/导出入口仍灰色不可点。
- workflow 视频步骤新增“批量直生音视频”，可直接从分镜镜头生成本地可验证的音视频草稿和字幕轨；合成步骤可直接用这些媒体任务生成连续成片和渲染包。
- 新增“生产就绪检查”面板，展示上游链路、镜头草稿、音频/配音、字幕轨、连续成片、渲染包状态，并明确 DEV_MODE 与真实生产适配边界。
- 新增浏览器 E2E `workflow page can batch generate direct audio video and render package`，覆盖 workflow 页面一键直生音视频、生产检查更新、连续成片、渲染包和导出 artifact 入口。
- 验证通过：`python3 -m compileall app`；`pytest -q test_media_subtitles.py test_workflow_routes.py` 26 passed；`npm run build` 通过；`npx tsc --noEmit` 通过；Playwright workflow 批量直生用例 1 passed。
- 本地服务已运行最新代码：后端 `http://127.0.0.1:8000`，前端 `http://127.0.0.1:3000`。

## 2026-05-13 P1/P2 提示词一致性深化

- 本轮假设：不改数据库结构、不新增供应商；先把现有生成入口统一到同一套小说上下文，确保封面、章节、分镜对白、视频和直生音视频都能承接人物、场景、道具、事件和章节连续性。
- 新增 `backend/app/services/story_prompt_context.py`，提供 `load_story_prompt_context()`、`build_cover_prompt()`、`build_chapter_continuity_block()`、`build_shot_dialogue_context()`、`build_video_continuity_constraints()`。
- 封面生成改为使用统一故事上下文；小说详情页的封面生成请求也改为传标题/题材/简介和补充要求，不再用简单 prompt 绕过后端上下文增强。
- 章节生成新增“小说连续性上下文” block，真实 LLM prompt 和 DEV_MODE 草稿都会承接题材、人物、场景、道具、事件和前后章节。
- 智能分镜模板对白改为具体人物对白或围绕场景/道具/事件的旁白；AI refine 输入加入实体清单，减少分镜和镜头与小说上下文脱节。
- `/video/generate` 和 `/media/generate` 注入动漫连续性硬约束；直生音视频任务额外保存 `source_prompt` 与 `story_continuity_constraints`，便于调试和后续供应商适配。
- 新增 `backend/test_story_prompt_context.py`，验证封面 ImageJob.prompt、章节 DEV_MODE 内容、分镜对白、视频 prompt、直生音视频 prompt 都包含同一小说的人物/场景/道具/事件。
- 验证通过：`python3 -m compileall app`；`pytest -q test_story_prompt_context.py test_storyboard_templates.py test_media_subtitles.py test_workflow_routes.py` 34 passed；`pytest -q test_chapter_ai_assist.py test_text_model_config.py test_character_scope.py` 16 passed；`npm run build` 通过；`npx tsc --noEmit` 通过。

## 2026-05-13 真实生产适配 P1/P2

- 本轮假设：真实 Sora/Veo/ComfyUI/FFmpeg 云渲染/口型服务均作为可选生产适配，不在无配置环境中阻断 DEV_MODE 小说到动漫主链路；外部接入统一走 `/external` 配置。
- 已扩展外部能力配置：内置 OpenAI/Sora、Google/Veo、ComfyUI、FFmpeg 云渲染、本地 FFmpeg、口型/唇形、Runway、Qwen；配置支持保存、更新、测试、删除和 capability status。
- 已新增镜头生产上下文接口：`GET/PUT /api/v1/shots/{shot_id}/production-context`，支持资产版本锁、关键帧、多视图角色参考、口型配置、审核状态、审核人和 provider hints。
- 已扩展统一媒体生成：`/media/generate` 接收 `external_config_id`、`adapter_options`、`asset_version_locks`、`keyframes`、`character_multiview_refs`、`lip_sync_mode`、`review_required`，并保存 adapter payload。
- 已完成 workflow FFmpeg 云渲染分支：`render_backend=ffmpeg_cloud` 会产出云渲染请求包、timeline JSON、SRT 和 render manifest；DEV_MODE 返回 `adapter_ready`，非 DEV_MODE 无配置返回 422，有真实输出 URL 才标记为 rendered。
- 前端新增 `/production-adapters` 管理页，支持能力矩阵、配置保存/编辑/测试/删除；顶部工具菜单新增“生产适配”；`/llm-config` 外部 API tab 指向新页面。
- workflow 合成步骤新增渲染执行器选择，可在本地渲染包和 FFmpeg 云渲染间切换，并可选择云渲染配置和字幕烧录选项。
- 新增 `backend/test_production_adapters.py`，覆盖外部配置生命周期、镜头生产上下文、ComfyUI adapter payload、FFmpeg 云渲染 adapter_ready。
- 验证通过：`python3 -m compileall app`；`pytest -q test_production_adapters.py` 4 passed；`pytest -q test_production_adapters.py test_media_subtitles.py test_workflow_routes.py` 30 passed；`npm run build` 通过；build 后单独 `npx tsc --noEmit` 通过；`git diff --check` 通过。
- 服务已重启并验证：后端 `http://127.0.0.1:8000/health` 返回 healthy，前端 `http://127.0.0.1:3000/production-adapters` 返回 200。

## 2026-05-13 前端可见性复查与补强

- 浏览器复查确认 `/production-adapters` 已可直接打开，能力矩阵和配置表单都能显示；之前“看不到”的核心原因是入口藏在“工具”下拉里，且部分能力只在后端或 workflow 特定步骤出现。
- 已将“生产适配”从工具下拉提升到顶部主导航，用户不需要展开下拉即可进入。
- 控制台新增三张入口卡片：生产适配、镜头生产上下文、批量直生与云渲染。
- 镜头管理页新增常驻提示卡，并在镜头编辑面板中补齐资产版本锁、关键帧、多视图角色参考、口型/唇形和审核状态的可编辑区域。
- 视频生成页新增“生产适配上下文”面板，可选择外部适配配置，查看当前镜头资产锁/关键帧/多视图/审核状态，选择口型模式，并决定生成后是否进入审核。
- 已用 Playwright 真实页面验证：`/dashboard` 可见顶部“生产适配”和三张入口卡；`/video-generation` 可见“生产适配上下文”；`/shots` 可见“镜头生产上下文已接入”提示。
- 验证通过：`npm run build`、build 后 `npx tsc --noEmit`、`git diff --check`；服务继续运行在后端 `127.0.0.1:8000`、前端 `127.0.0.1:3000`。

## 2026-05-13 AI 生成提示词与反馈优化

- 已完成第一轮审计：章节链路上下文较完整；剧本生成、角色提取、实体抽取、storyboard-ai 辅助接口缺少统一生成元信息和足够可见的阶段反馈。
- 发现角色提取头像失败未返回前端，实体抽取缺上下文摘要，剧本生成未复用统一故事上下文，前端多个 AI 入口仍是简单 spinner/alert。

## 2026-05-13 视频模型调用与生产适配使用说明补强

- 复核当前生产适配消费链路：`/production-adapters` 是统一配置入口，`/shots/{id}/production-context` 维护镜头级资产锁/关键帧/多视图/口型/审核上下文，`/media/generate` 消费直生音视频和 ComfyUI/口型 adapter payload，`/workflow/{id}/render` 消费 FFmpeg 云渲染配置。
- 修复 `/video/generate` 的模型解析：现在按用户选择的 `LLMModel.id` 或 `LLMModel.model_id` 找视频模型，校验 `video/video-generation` 类型，并把 provider、API model、endpoint、验证状态和参数写入 VideoJob。
- 修复视频页默认模型选择：只允许火山视频类型配置作为默认视频模型，避免火山文本/图片默认配置被误用，导致用户看到“未验证”或生成没走所选视频模型。
- 修复公网参考图预检失败后未传图的问题：公网 URL 即使 HEAD/CORS 预检失败也会继续传给后端，只有本地/私有 URL 才跳过。
- 前端补齐可见说明：生产适配页新增“应用位置”；视频生成页明确静音视频不消费生产适配配置，直生音视频会提交外部配置、资产锁、关键帧、多视图、口型和审核参数；workflow 渲染说明本地包/云渲染分别消费的 manifest、timeline、SRT 和外部配置。
- 新增/扩展后端测试 `test_video_generation_uses_selected_video_model_config_metadata`，验证所选视频模型 endpoint、参考图参数和任务元数据。
- 验证通过：`python3 -m compileall app`；`pytest -q test_workflow_routes.py test_production_adapters.py test_media_subtitles.py` 31 passed；`npm run build` 通过；`npx tsc --noEmit` 通过；`git diff --check` 通过。

## 2026-05-13 管理页筛选与工作流串联修复

- 开始处理用户反馈：`/shots` 缺小说/章节筛选；`/workflow` 首页入口不明显，章节选择后角色、剧本、分镜、镜头没有按当前链路加载，角色步骤缺 AI 提取，流程容易回到小说起点。
- 初步定位：`/shots` 只从第一个剧本加载分镜下拉，镜头列表未保存 novel/chapter/script 元数据，无法做小说/章节筛选。
- 初步定位：`/workflow` 的章节步骤只展示章节不选择章节；角色步骤是静态跳转；剧本/分镜/镜头步骤基本是占位跳转，没有读取当前小说/章节下已有产物，也没有生成/提取闭环。
- 后端补齐：`/scripts` 支持 `novel_id/chapter_id` 过滤；`/workflow/{workflow_id}/step` 可保存 novel/chapter/script/storyboard 链路，避免前端轮询丢上下文。
- 前端补齐：`/workflow` 章节可选中并持久化；角色步骤按小说/章节加载角色并支持 AI 提取；剧本步骤加载/生成当前章节剧本；分镜步骤加载/智能生成分镜；镜头步骤加载当前分镜镜头。
- 镜头管理补齐：`/shots` 新增小说、章节、剧本、分镜、状态和搜索组合筛选，支持 URL 参数恢复，镜头卡片展示上游链路，跳视频生成携带完整 lineage。
- 入口补齐：顶部导航新增“工作流”，控制台流程入口从“生成视频”调整为“完整工作流”；剧本页新增小说/章节筛选；分镜页支持 `novel_id/chapter_id` URL 参数。
- 验证通过：`python3 -m compileall app`；`pytest -q test_workflow_routes.py test_character_scope.py test_storyboard_templates.py` 31 passed；`npx tsc --noEmit`；`npm run build`；`git diff --check`。
- 服务已重启并验证：后端 `/health` 200，前端 `/workflow`、`/shots`、`/dashboard` 均 200。

## 2026-05-13 平台前端流程与生产化复查

- 已复盘认证、设置、弹窗、Dashboard、导航和关键 API 调用，确认本轮 P0 为：认证守卫失效、设置页后端接口缺失、忘记/重置密码缺失、生产模式 JWT 未校验、弹窗滚动边界和个人资料“开发中”入口。
- 已尝试按 `web-design-guidelines` skill 拉取最新远程规则，但 `raw.githubusercontent.com` robots/连接失败；本轮按本地可验证 UI 可用性和现有设计约束继续修复。
- 工作树已有大量前序未提交改动，本轮只修改账户认证、全局 Dialog、主要手写弹窗、个人资料页和测试文件。
- 已落地账户链路：后端资料更新、修改密码、忘记/重置密码接口；前端登录页找回密码入口、找回/重置页面、个人资料头像 URL 保存；`users` 表新增头像和重置令牌兼容迁移。
- 已加固权限入口：前端 AuthContext/fetch-with-auth 公共路径判断修复；后端 `get_current_user_id` 非 DEV_MODE 必须校验签名 JWT，DEV_MODE 保留本地开发 token。
- 已加固 UI 可用性：通用 Dialog、镜头编辑、新建分镜、剧本创建/AI 生成弹窗都增加视口内滚动；顶部导航横向滚动；Dashboard 空状态“浏览示例”改为“查看作品”。
- 新增测试：`backend/test_auth_account.py` 覆盖资料保存、改密、忘记/重置密码、非 DEV_MODE 拒绝未签名 token；`frontend/e2e/auth-account.spec.ts` 覆盖未登录跳转和找回密码入口。
- 验证通过：`python3 -m compileall app`；后端专项 `pytest -q test_auth_account.py test_workflow_routes.py` 27 passed；后端全量 `pytest -q` 99 passed、1 skipped；前端 `npx tsc --noEmit`；`npm run build`；Playwright `npx playwright test e2e/auth-account.spec.ts --project=chromium` 1 passed；`git diff --check`。
- 服务已重启并验证：后端 `http://127.0.0.1:8000/health` 200；前端 `/forgot-password`、`/reset-password`、`/settings/profile` 均 200。

## 2026-05-14 P1/P2 Timeline 产品化

- 接续 P1/P2，选择当前最可落地的生产能力：把 workflow 多镜头 manifest 变成数据库内可编辑 Timeline，并提供前端时间线编辑工作台。
- 后端新增 `/api/v1/workflow/{workflow_id}/timeline/sync`：从最新或指定 `SynthesisJob.extra_data.segments` 生成/复用项目、时间线、视频轨、音频轨、字幕轨和 Clip，并回写 `Workflow.metadata_.latest_timeline_id` 与 `SynthesisJob.extra_data.timeline_id/timeline_clip_count`。
- 修复 `workflow.py` 漏导入 `func` 导致同步接口测试失败的问题。
- workflow 页面合成步骤新增“可编辑 Timeline”模块，可一键生成/重建时间线，并展示轨道和片段。
- 新增前端 `/timelines` 页面，工具菜单新增“时间线编辑”；页面按项目加载时间线，展示视频/音频/字幕轨，可保存片段名称、起始秒、时长、字幕文本，支持删除片段、锁定/静音轨道。
- 修复 Timeline 后端片段创建路由冲突：原来创建时间线和创建片段都声明 `POST /timelines`，片段创建会被时间线创建接口抢走；已改为 `POST /timelines/{timeline_id}/clips`，并补前端 `createTimelineClip`。
- 新增后端测试 `test_timeline_clip_create_uses_nested_clip_route`，覆盖嵌套片段创建和路径/body 时间线不一致校验。
- 验证通过：`python3 -m compileall app`；`pytest -q test_workflow_routes.py -k "timeline_clip_create or multi_shot_sequence_manifest or render"` 3 passed；前端 `npx tsc --noEmit` 通过；`git diff --check` 通过。
- 服务已重启并验证：后端 `/health` 200；前端 `/timelines`、`/workflow` 200；浏览器注入 DEV token 后 `/timelines` 可见项目、时间线、视频片段、字幕片段和“添加字幕片段”；顶部“工具”下拉可展开并显示“时间线编辑”入口。

## 2026-05-14 P1/P2 Timeline 渲染联动

- 接续上一阶段发现的断点：Timeline 已可编辑，但 workflow 渲染仍只读 `SynthesisJob.extra_data.segments`，会忽略用户在 `/timelines` 修改过的字幕和片段时间。
- 后端新增渲染源解析层：`_resolve_render_source()` 默认优先读取 `Workflow.metadata_.latest_timeline_id` 或 `SynthesisJob.extra_data.timeline_id`，把 Timeline active clips 转换成 render segments；没有 Timeline 时自动回退原 manifest。
- SRT、EDL 和 HTML preview 现在支持 Timeline 派生的多字幕片段；EDL 会标记 `source=editable_timeline` 和 `timeline_id`。
- 渲染缓存增加 `render_source_key`，Timeline 更新时间或片段数量变化后不会复用旧渲染包。
- `/workflow/{id}/render/preflight` 和 `/workflow/{id}/render` 新增 `use_editable_timeline/timeline_id` 参数；响应返回 `render_source/timeline_id`。
- workflow 页面渲染区域新增“使用可编辑 Timeline”开关，默认开启；页面会显示当前渲染源是“可编辑 Timeline”还是“原始成片清单”。
- 扩展 `test_workflow_concatenate_builds_multi_shot_sequence_manifest`：同步 Timeline 后修改字幕 Clip，再强制渲染，断言生成的 SRT/EDL 使用“已编辑 Timeline 字幕”及新的时间码。
- 验证通过：`python3 -m compileall app`；`pytest -q test_workflow_routes.py -k "multi_shot_sequence_manifest or render_preflight or timeline_clip_create"` 3 passed；前端 `npx tsc --noEmit` 通过；`git diff --check` 通过。
- 服务已重启并验证：后端 `/health` 200，前端 `/workflow` 200。

## 2026-05-14 P0/P1 前后端可见性复核与资产库

- 复核 `task_plan.md`、`findings.md`、`progress.md` 和 `docs/novel-to-anime-optimization-plan.md`，确认 P0/P1 主链路前端入口已经覆盖：直生音视频、字幕、workflow 批量生成、生产适配、Timeline、实体生产资料包、镜头质量准入和审核。
- 定位到本轮最明确缺口：后端 `/assets` 是资产版本锁、角色/场景/道具/音效/关键帧管理的基础，但前端只有 `/templates` 局部管理模板资产，缺少通用资产库页面。
- 已新增前端 `/assets` 页面：加载资产分类、项目和资产列表；支持分类/项目/公开范围/搜索筛选；支持新建、编辑、归档和打开资源 URL；保存后保留明确成功反馈。
- API client 新增 `getAssetCategories()`，`getAssets()` 支持 `project_id` 参数。
- 顶部“工具”菜单新增“资产库”，控制台新增“资产库”入口卡片；导航 E2E 已覆盖资产库菜单项。
- 新增前端 E2E `frontend/e2e/assets.spec.ts`，覆盖资产库创建、编辑和归档。测试首次暴露保存后成功提示被刷新清空的问题，已修复后重跑通过。
- 验证通过：`python3 -m compileall app`；`pytest -q test_asset_templates.py test_story_entity_production_pack.py test_production_adapters.py` 8 passed；`npm run build` 通过；`npx tsc --noEmit` 通过；`npx playwright test e2e/assets.spec.ts e2e/top-navigation.spec.ts --project=chromium --workers=1` 2 passed；`git diff --check` 通过。
- `npm run build` 后已重新创建 tmux 服务会话；当前后端 `http://127.0.0.1:8000/health`、前端 `http://127.0.0.1:3000/assets` 和 `/dashboard` 均返回 200。

## 2026-05-15 视频/音视频历史筛选与剧本分页

- 已开始补齐视频生成页历史筛选：新增历史筛选面板，准备把小说、章节、剧本、分镜、镜头作为统一过滤条件，作用于视频历史和音视频直生历史。
- 后端 `media/jobs` 已补 `script_id` 过滤；`scripts` 列表已补 `page/page_size`，用于剧本分页展示。
- 前端视频生成页已开始接入剧本分页和历史筛选面板，后续需要跑编译、类型检查和浏览器验证确认行为没有回退。
- 已完成：历史筛选面板可见并同时驱动静音视频历史与直生音视频历史；剧本下拉按 8 条分页，长列表显示上一页/下一页；音视频直生历史补充小说/章节/剧本/分镜/镜头链路文本。
- 验证通过：`python3 -m compileall app`；`pytest -q test_parent_ownership_routes.py test_media_subtitles.py` 16 passed；`npx tsc --noEmit` 通过；`git diff --check` 通过；浏览器验证 `/video-generation` 可见历史筛选、五类筛选项和剧本分页。

## 2026-05-15 模板库系统预制模板可编辑与扩展

- 扩展后端系统分镜模板库，新增强钩子开场、主要人物登场、群像会议/任务简报、反派压迫/危机降临、危机救援/逆转、结尾悬念/下集钩子、日常喜剧节奏、调查推理过程等通用动漫模板。
- 系统模板编辑采用用户级覆盖层：前端保存为 `Asset(category=template)`，`shot_template.system_template_id` 指向原系统模板，后端列表、模板匹配和智能生成保持系统模板稳定 ID 并优先应用用户覆盖版本。
- `/templates` 系统预制模板卡片已增加编辑入口，支持修改名称、类型、标签、描述、提示词和镜头数；保存后展示“已定制”，刷新后仍保持定制状态。
- 自定义模板列表会过滤系统覆盖资产，避免用户级覆盖同时出现在“系统模板”和“自定义模板”两处造成误解。
- 新增后端测试覆盖系统模板扩展、系统模板覆盖列表、指定模板匹配和智能生成消费覆盖模板；新增浏览器 E2E 覆盖系统模板编辑和刷新持久化。
- 验证通过：`python3 -m compileall app`；`pytest -q test_storyboard_templates.py test_asset_templates.py` 6 passed；`npx tsc --noEmit` 通过；`npx playwright test e2e/templates.spec.ts --project=chromium` 1 passed；`git diff --check` 通过。

## 2026-05-15 火山方舟 Agent Plan 模型配置

- 已按用户提供的 `火山方舟_Agent Plan - Coding Plan _1778814726.pdf` 抽取关键接入信息：Agent Plan 使用专属 API Key 和 `https://ark.cn-beijing.volces.com/api/plan/v3`，不能混用普通方舟 `/api/v3`。
- 新增 `backend/app/core/volcano_agent_plan_config.py`，定义独立 provider `volcano_agent_plan` 和 16 个模型：文本模型、`doubao-embedding-vision`、`doubao-seedream-5.0-lite`、`doubao-seedance-1.5-pro/2.0/2.0-fast`。
- 后端 `/llm/providers`、`/llm/models` 默认回填已接入 Agent Plan；`init_llm_config.py` 也同步新增，支持空库初始化。
- `create_text_generation_service` 和 `create_image_generation_service` 支持 `volcano_agent_plan`，复用火山兼容服务但使用 Agent Plan 专属 base_url。
- LLM 配置测试新增 `test_volcano_agent_plan_api()`，按文本、图像、视频模型分别走 `/chat/completions`、`/images/generations`、`/contents/generations/tasks`。
- 静音视频生成允许 `volcano_agent_plan` 视频模型，状态查询和刷新会按任务 extra_data 中的 provider 取对应 Key；前端视频模型选择同时加载普通火山和 Agent Plan 模型。
- 前端 `/llm-config` 新增动态 provider 标签，展示“火山方舟 Agent Plan”模型，并提示专属 Key、`/api/plan/v3` 和 Small 套餐视频限制；保存 Agent Plan 配置时写入专属 base_url。
- 关键修复：视频生成页传配置模型 ID 而不是 API model_id，避免 `doubao-seedance-2.0-fast` 与普通火山模型 ID 冲突导致串 provider。
- 验证通过：`python3 -m compileall app`；`pytest -q test_text_model_config.py test_volcano_service.py test_workflow_routes.py -k "agent_plan or seedance_20 or llm_model_catalog"` 6 passed；前端 `npx tsc --noEmit` 通过；接口回填确认 `volcano_agent_plan` provider 和 16 个模型可见；`git diff --check` 通过。

## 2026-05-16 AI 模型能力级默认与前端展示

- 已把后端 LLM 默认配置改为按能力类别独立生效：文本、图像、语音、视频、向量互不覆盖。
- `/llm-config` 新增“能力默认模型”总览卡片，按能力展示当前默认/优先可用配置、provider、模型名和验证状态；保存列表也标明“文本生成默认/图像生成默认/语音默认”等。
- 新增前端 helper `frontend/src/lib/model-configs.ts`，统一判断模型能力、验证状态标签、状态颜色和默认配置。
- `/video-generation` 区分“已保存配置”和“模型目录候选”，默认优先选视频能力默认配置，其次选已验证配置；生产模式下未保存或未验证的视频模型会禁用生成并给出提示。
- `/tts` 改为展示已保存的语音模型配置，默认选择语音能力默认配置；生成时提交 `model_config_id` 和 API model，避免只按 provider 猜模型。
- 后端 `/tts/generate` 支持 `model_config_id`，从 LLMConfig 精准解析 provider、API Key、base_url 和 TTS API model，并写入任务 extra_data。
- 验证通过：`python3 -m compileall app`；`pytest -q test_text_model_config.py test_volcano_service.py test_workflow_routes.py -k "llm_defaults_are_scoped or llm_set_default_only_replaces_same_capability or agent_plan or seedance_20 or llm_model_catalog"` 10 passed；前端 `npx tsc --noEmit` 通过；`git diff --check` 通过。

## 2026-05-16 AI 模型能力选择贯穿收尾

- 复核上一轮模型选择改动后，确认小说、章节、角色、实体、分镜、极速向导和 workflow 已接入通用能力模型选择组件；本轮定位并修复剧本管理页漏接。
- 剧本管理页新增文本模型选择卡，展示默认/验证状态；从章节改编剧本必须选择小说和章节，调用 `/scripts/generate`，传入 `model_config_id`，生成结果直接落库并刷新剧本列表。
- 剧本管理页自定义描述生成保留 `/coding-plan/storyboard`，但移除离线模拟结果，失败时透出后端错误；请求体同步传入所选文本模型配置。
- 后端 `/coding-plan/generate`、`/coding-plan/novel`、`/coding-plan/storyboard`、`/coding-plan/auto-generate` 支持 `model_config_id`，默认按当前用户文本模型配置创建服务，仍兼容旧的显式 `api_key`。
- 前端 `api-client` 的 `generateCodingPlan`、`generateNovelWithPlan`、`autoGenerate` 增加可选 `modelConfigId` 参数，避免后续复用时绕过模型配置。
- 新增后端测试 `test_coding_plan_resolves_selected_text_model_config`，验证 Coding Plan 辅助接口解析指定文本模型配置。
- 验证通过：`python3 -m compileall app`；`pytest -q test_text_model_config.py test_workflow_routes.py test_character_scope.py test_storyboard_templates.py` 53 passed；前端 `npx tsc --noEmit` 通过；`git diff --check` 通过。

## 2026-05-19 短剧式动漫短视频一致性分析

- 复盘当前计划、发现和进度文件，确认平台已具备 Story Bible、实体生产资料包、资产库、模型能力选择、直生音视频、字幕轨、Timeline 和生产适配等基础能力。
- 只读检查当前一致性相关代码：`story_prompt_context.py`、`consistency_context.py`、`prompt_composer.py`、`model_registry.py`、`media.py` 和 Story Bible 一致性检查。
- 联网核对官方/权威资料：Sora 2 和 Veo 3 都强调视频与同步音频生成；Runway Gen-4 References 和 Kling Elements 强调用参考图保持人物/地点/物体一致。
- 得出下一阶段重点：从“字段和页面具备”升级为“生成前强制 Production Contract + 短剧节奏模板 + 一致性校验器 + 模型路由解释 + 前端短视频出片模式”。
- 已更新 `task_plan.md` 与 `findings.md`，新增 Phase 154-161 和短剧式一致性生产分析结论。

## 2026-05-19 Phase 154-161 短视频生产闭环落地

- 新增后端服务 `backend/app/services/short_video_production.py`，在不新增数据库表的前提下，把短视频单集规划、镜头 Production Contract、工作流就绪度和批量合约刷新集中实现。
- 新增 `/api/v1/short-video/episode-plan`：根据小说、章节、Story Bible、角色、场景、道具和事件生成 9:16、30-90 秒短剧式规划，包含开场钩子、冲突、反转、结尾悬念、情绪曲线和镜头节奏。
- 新增 `/api/v1/short-video/shots/{shot_id}/production-contract`：从 Shot 反推小说、章节、剧本、分镜，聚合实体、字幕、关键帧、资产锁、Story Bible 状态、seed、模型路线、质量报告和预算估算，并可写回 `Shot.extra_data.production_context.production_contract`。
- 新增 `/api/v1/short-video/workflow/{workflow_id}/readiness` 与 `/refresh-contracts`：按工作流批量检查镜头合约、总时长、阻断项、提醒项和推荐下一步。
- 前端 `frontend/src/app/workflow/page.tsx` 新增“短视频出片模式”面板，用户可直接检查本集短视频规划、刷新镜头合约、查看人物/场景/字幕/资产锁缺口和默认模型路线。
- API client 新增短视频生产接口方法，供 workflow 页面和后续页面复用。
- 新增后端测试 `backend/test_short_video_production.py`，验证短视频规划、合约持久化、工作流就绪度和批量刷新。
- 已完成阶段性验证：`python3 -m compileall app` 通过；`pytest -q test_short_video_production.py` 3 passed；前端 `npx tsc --noEmit` 通过。

## 2026-05-19 P0/P1/P2 小说与剧本连续性落地收口

- 已复核 Phase 64-69 的后端、前端和测试实现，并补齐一条浏览器回归覆盖“按小说/章节进入剧本管理 -> 展示章节连续性上下文 -> 生成剧本 -> 展示一致性检查”。
- 修复前端剧本页 URL 初始化缺陷：`/scripts?novel_id=...&chapter_id=...` 进入页面后，章节筛选原先会在章节列表异步加载前被清空，导致 AI 生成弹窗默认回到第一章；现在会保留 URL 中的章节选择。
- 新增 E2E `script generation shows chapter continuity context and consistency check`，验证前情章节、后续约束、人物/场景/道具/事件/关系计数、关键实体、生成结果和一致性检查均在前端可见。
- 验证通过：`python3 -m compileall app`；后端专项 `pytest -q test_story_prompt_context.py test_parent_ownership_routes.py -k "script or context"` 15 passed；后端全量 `DEV_MODE=true pytest -q` 127 passed、1 skipped；前端 `npx tsc --noEmit` 通过；前端 `npm run build` 通过；新增 Playwright 用例 1 passed；`git diff --check` 通过。
- `npm run build` 后已重启前端 dev server；当前服务可用：后端 `http://127.0.0.1:8000/health` 返回 healthy，前端 `http://127.0.0.1:3000/scripts` 返回 200。

## 2026-05-19 测试提示与服务重启收敛

- 清理 pytest 提示：`backend/test_api.py` 的辅助客户端类从 `TestClient` 改名为 `ApiClient`，避免 pytest 误收集；测试函数不再返回 bool，失败分支改用 `pytest.fail()`。
- 清理 Python 3.14 时间弃用提示：新增 `backend/app/core/time_utils.py` 的 `utc_now()`，后端模型默认时间和业务更新时间统一从 `datetime.utcnow()` 替换为兼容现有 naive UTC 存储的 helper。
- 清理 FastAPI 状态码弃用提示：`HTTP_422_UNPROCESSABLE_ENTITY` 更新为 `HTTP_422_UNPROCESSABLE_CONTENT`，HTTP 状态码保持 422。
- 验证通过：`python3 -m compileall app`；`DEV_MODE=true pytest -q` 127 passed、1 skipped、1 warning；`npx tsc --noEmit` 通过；`npm run build` 通过；`git diff --check` 通过。
- 剩余 1 条 warning 是未设置 `FERNET_KEY` 的生产安全提示，测试环境可接受；生产环境必须设置稳定 `FERNET_KEY`，否则加密 API Key 重启后不可解密。
- 已重启服务并验证：后端 `http://127.0.0.1:8000/health` 返回 healthy；前端 `http://127.0.0.1:3000/scripts` 和 `http://127.0.0.1:3000/workflow` 返回 200。

## 2026-05-20 实体与资产作用域开发

- 开始接续实体/资产抽取与作用域管理：目标是补齐 script 级实体、实体/资产全局与小说/章节/剧本动态升降级、抽取实体同时生成资产占位，并前端可操作。

## 2026-05-20 实体与资产作用域开发完成

- 后端 StoryEntity 已支持 script_id、scope 筛选和 `/story-bibles/entities/{id}/scope` 动态升全局/绑定小说章节剧本。
- 新增 `/story-bibles/entities/extract-assets`，可从小说/章节/剧本/文本抽取角色、场景、道具、事件，并同步创建资产占位，资产可绑定全局/小说/章节/剧本/实体。
- 前端 `/entities` 支持小说/章节/剧本筛选、实体范围筛选、抽取实体+资产、实体升全局和绑定当前范围。
- 前端 `/assets` 支持小说/章节/剧本/实体/范围筛选，资产表单可绑定上游范围，并支持升全局/绑定当前范围。
- 验证通过：`python3 -m compileall app`；`DEV_MODE=true pytest -q test_story_entity_production_pack.py test_asset_templates.py` 3 passed；前端 `npx tsc --noEmit`；`npm run build`；`git diff --check`；服务重启后 `/health`、`/entities`、`/assets` 200；接口烟测抽取 4 个实体和 4 个资产并成功升全局。

## 2026-05-20 默认动漫资产与实体库落地

- 新增 `backend/app/services/default_anime_library.py`，提供 13 个默认实体和 10 个默认资产。
- 默认实体是用户级全局实体，包含热血少年主角、冷静行动女主、神秘导师、压迫型反派、城市夜巷、学校天台、玄幻大殿、赛博实验室、命运吊坠、能量核心、开场危机、线索发现、结尾反转。
- 默认资产是用户级全局资产，包含角色一致性提示词、短视频钩子提示词、场景参考、道具 DNA、现代战斗风衣、动作音效、悬疑音乐和 9:16 短剧三段式镜头模板。
- 接入 `/assets` 和 `/story-bibles/entities` 列表接口，第一次访问自动创建，后续不会重复；用户可以编辑、归档或绑定到当前小说/章节/剧本/实体。
- 验证通过：`python3 -m compileall app`；`DEV_MODE=true pytest -q test_asset_templates.py test_story_entity_production_pack.py` 5 passed；`git diff --check`；重启后接口烟测返回 10 个默认资产、13 个默认实体。

## 2026-05-20 资产库筛选与统计修复

- 修复 `/assets/categories` 分类统计：按当前用户可见资产计算，并支持 `include_public`，不再把其他用户私有资产计入。
- 修复 `/assets` 小说/章节/剧本/实体筛选：默认会包含真正全局资产；只有指定 `scope=novel/chapter/script/entity` 时才只看绑定资产。
- 前端 `/assets` 调整筛选文案：普通范围为“全部范围（含全局）”，项目下拉改为“仅全局资产”，并补充筛选说明。
- 前端统计修正：全局资产只统计未绑定项目/小说/章节/剧本/实体的通用资产。
- 验证通过：`python3 -m compileall app`；`DEV_MODE=true pytest -q test_asset_templates.py` 3 passed；`npx tsc --noEmit`；`git diff --check`；重启后接口烟测确认小说筛选同时返回全局资产和小说资产，`scope=novel` 只返回小说资产。

## 2026-05-20 实体库筛选与维护修复

- 修复 `/story-bibles/entities` 查询语义：默认选择小说/章节/剧本时包含可复用全局实体；只有 `scope=novel/chapter/script/global` 时才做严格范围筛选。
- 实体列表每次查询都会确保默认全局实体可用，避免选择“仅全局”时因未初始化而空列表。
- 前端 `/entities` 修复切换小说时旧章节/旧剧本条件参与查询的问题，避免筛选组合互相矛盾。
- 前端范围文案改为“全部范围（含全局）/仅全局/仅小说/仅章节/仅剧本”，并补充筛选说明。
- 补充测试覆盖默认查询含全局与小说实体、仅小说/仅章节过滤、编辑/快照/删除维护能力。
- 验证通过：`python3 -m compileall app`；`DEV_MODE=true pytest -q test_story_entity_production_pack.py` 4 passed；`npx tsc --noEmit`；`git diff --check`；重启后接口烟测确认默认查询包含全局+小说实体，`scope=novel` 只返回小说实体。

## 2026-05-20 实体库统计数字修复

- 根因确认：前端实体统计原先从当前 `entities` 列表计算，列表会受实体类型筛选和 `limit=200` 分页影响，导致选择“角色”后场景/道具/事件统计变 0，数据量大时也可能少算。
- 后端新增 `/story-bibles/entities/stats`，按当前用户、小说、章节、剧本和范围筛选直接聚合 `character/scene/prop/event` 数量，并默认确保用户级全局 starter 实体已初始化。
- 后端列表和统计共用同一套范围筛选 helper：默认选择小说/章节/剧本时包含全局实体；指定 `scope=global/novel/chapter/script` 时严格按范围统计。
- 前端 `/entities` 统计卡改为读取统计接口，统计随小说/章节/剧本/范围变化，但不再受右侧实体类型筛选和分页影响；抽取、创建、编辑、删除、范围调整和顶部刷新都会同步刷新统计。
- 补充测试覆盖：默认统计含全局和小说/章节实体、列表 `entity_type` 与 `limit` 不影响统计、`scope=novel` 和 `scope=chapter` 严格统计。
- 验证通过：`python3 -m compileall app`；`DEV_MODE=true pytest -q test_story_entity_production_pack.py` 5 passed；`npx tsc --noEmit`；`git diff --check`。

## 2026-05-20 实体库统计数字修复

- 修复实体库角色/场景/道具/事件统计不准的问题：新增 `/story-bibles/entities/stats` 后端聚合接口，统计按当前小说、章节、剧本和范围筛选计算，不受实体类型筛选和列表分页限制。
- 后端实体列表和统计接口已复用同一套范围筛选语义：默认筛选包含全局实体；`scope=global/novel/chapter/script` 时进入严格范围统计。
- 前端 `/entities` 统计卡改为读取后端统计接口；创建、删除、编辑、恢复快照、抽取实体和升降级范围后同步刷新列表、统计和生产资料包。
- 前端补充说明：当前范围总数与分类统计不受右侧“全部类型/角色/场景/道具/事件”列表筛选影响。
- 验证通过：`DEV_MODE=true pytest -q test_story_entity_production_pack.py` 6 passed；`python3 -m compileall app` 通过；`npx tsc --noEmit` 通过；`git diff --check` 通过。

## 2026-05-22 UI 交互与弹窗体验优化

- 统一前端提示体验：将 `frontend/src/app` 和 `frontend/src/components` 下的原生 `alert/confirm` 全部替换为项目内 `ToastProvider/useToast` 与 `ConfirmDialog`。
- 优化高频页面操作反馈：小说、章节、剧本、角色、分镜、镜头、字幕、TTS、视频生成、合成、workflow、团队、时间线、生产适配等页面的保存、生成、失败、删除、归档、恢复版本等操作改为非阻塞提示或统一确认弹窗。
- 强化破坏性操作保护：删除角色、章节、镜头、字幕段、时间线片段、团队成员、生产适配配置、恢复剧本版本、AI 重写章节等动作均使用统一确认弹窗。
- 补充全局交互基础组件：Tabs 支持真实受控状态与可访问语义，Dialog/Toast/ConfirmDialog 统一暗色玻璃风格、焦点状态和异步加载状态。
- 验证通过：`rg -n "alert\\(|confirm\\(" frontend/src/app frontend/src/components` 无结果；前端 `npm run build` 通过。

## 2026-05-22 UI 可访问性与弹窗语义第二阶段

- 顶部导航修复 `transition-all` 和无替代焦点样式：桌面/移动导航、工具/更多菜单触发器改为明确 `transition-colors` 和 `focus-visible:ring`，并补充菜单触发器语义标签。
- 小说、剧本、任务队列、镜头页高频图标按钮补齐 `aria-label/title`，避免只有图标导致读屏和键盘用户无法判断操作含义。
- 小说、剧本、仪表盘、视频生成、镜头页的导航按钮统一改为 `Button asChild` 包裹 `Link`，消除 `Link` 包 `Button` 的嵌套交互问题。
- 镜头编辑弹窗从自定义固定遮罩迁移到共享 `Dialog`，保留原表单和保存逻辑，同时获得焦点陷阱、Esc/外点关闭、语义标题和滚动控制。
- 收窄进度条、卡片、模式选择等动效的过渡属性，清理关键加载/保存/搜索文案中的 `...` 为 `…`。
- 验证通过：PCRE 嵌套 `Link/Button` 复扫无结果；`rg -n "alert\\(|confirm\\(" frontend/src/app frontend/src/components` 无结果；前端 `npm run build` 通过。

## 2026-05-22 UI 可访问性与弹窗语义第三阶段

- 继续迁移自定义浮层：剧本创建/编辑弹窗、AI 生成剧本弹窗、分镜新建/智能生成弹窗改为共享 `Dialog`，统一焦点陷阱、Esc/外点关闭、语义标题和移动端滚动控制。
- 分镜页镜头操作补齐无障碍标签：生成视频、上移、下移、删除镜头等图标按钮增加 `aria-label/title`；参考图生成按钮增加键盘焦点样式。
- 扩展 `Button asChild` 收敛范围：新建小说、小说详情、章节列表、章节编辑、设置页、脚本详情等跳转按钮不再使用 `Link` 包 `Button`。
- 高频媒体预览图补充 `width/height/loading="lazy"`：资产、角色头像、工作流角色、视频参考图、分镜参考图、镜头背景图、仪表盘/小说封面、个人头像等，降低布局抖动风险。
- 全站明显加载/保存/搜索/生成文案中的 `...` 统一为 `…`，保留 `/static/...` 等路径示例不动。
- 验证通过：自定义浮层扫描只剩共享 `Dialog`；PCRE 嵌套 `Link/Button` 扫描无结果；前端 `npm run build` 通过。

## 2026-05-22 UI 剩余细节收口第四阶段

- 补齐剩余高频 icon-only 操作语义：团队成员移除、TTS 片段播放、字幕轨选择、密码显示/隐藏、头像图片提示、workflow 错误关闭/步骤跳转等按钮增加 `aria-label/title` 或明确 `type="button"`。
- 清理剩余 `处理中...` 文案为 `处理中…`，并把 TTS、Synthesis、Workflow、Toast 中不必要的 `transition-all` 收窄为 `transition-colors`、`transition-[width]` 或 `transition-[opacity,transform]`。
- 再次扫描确认重点范围无明显 `加载中.../生成中.../保存中.../处理中...` 和 `transition-all` 残留；嵌套 `Link/Button` 扫描仍无结果。
- 验证通过：前端 `npm run build` 通过。

## 2026-05-22 数据分析与系统设置完善

- 已将 `/analytics` 从静态 mock 改为真实数据面板：读取 `/dashboard/stats`、`/usage-stats/summary`、`/usage-stats/by-model`、`/usage-stats/daily`、视频/TTS/图片/合成/媒体任务列表，展示作品资产、AI 请求、Token/成本、每日趋势、模型排行、任务完成率和近期活动。
- `frontend/src/lib/api-client.ts` 补齐 `getUsageSummary`、`getUsageByModel`、`getDailyUsage`、`getUsageLogs`；旧 `getUsageStats` 保留兼容但不再指向不存在的 `/usage-stats?period=` 主路径。
- `/settings` 首页新增账户摘要、通知/外观偏好摘要和可点击即保存的快捷设置；个人资料和安全设置仍沿用后端真实接口。
- 新增 `/settings/notifications`：支持生成完成、失败任务、周报摘要、浏览器通知、免打扰时段偏好，支持浏览器通知授权和测试通知；当前偏好保存到 localStorage。
- 新增 `/settings/appearance`：支持强调色、紧凑布局、减少动效和紧凑卡片偏好；新增 `UserPreferencesHydrator` 在刷新后恢复外观设置。
- 验证通过：前端 `npx tsc --noEmit` 通过；`npm run build` 通过；`git diff --check` 通过。

## 2026-05-22 数据分析正式数据源修正

- 根据反馈修正 `/analytics` 数据口径：前端不再多接口拼装，不再对统计接口使用 `catch(() => [])` 静默归零。
- 后端新增 `/api/v1/dashboard/analytics` 作为数据分析页唯一正式数据源，直接从数据库聚合内容资产、五类生成任务、每日任务趋势、模型用量和近期活动。
- 接口响应明确包含 `data_source: "database"` 与 `is_mock: false`；前端页面顶部展示“后端数据库正式统计”，接口失败时显示错误，不伪装成 0。
- 修复模型排行统计口径：当前 `LLMUsageLog` 没有 `model` 字段，聚合改为按 `config_id` 统计，并关联 `LLMConfig/LLMModel` 解析模型显示名。
- 新增 `backend/test_dashboard_analytics.py`，验证正式接口能统计真实创建的小说、章节、角色、剧本、分镜、镜头、资产、视频、TTS 和直生音视频任务。
- 验证通过：`DEV_MODE=true pytest -q test_dashboard_analytics.py` 1 passed；`python3 -m compileall app` 通过；前端 `npx tsc --noEmit` 通过；`npm run build` 通过；`git diff --check` 通过。
- 服务已重启并烟测：后端 `/health` 200，前端 `/analytics` 200，`/api/v1/dashboard/analytics?days=14` 返回 `data_source=database`、`is_mock=false` 和真实数据库计数。

## 2026-05-26 整部小说动画漫剧平台深度分析

- 复盘当前工程已落地能力：小说导入/编辑、章节 AI、Story Bible、实体/资产、剧本、分镜、镜头、质量检查、视频/TTS/直生音视频、字幕、Timeline、渲染包、模型配置、生产适配、数据分析和设置。
- 判断当前系统已经具备“首集/单章节生产闭环”基础，但距离“整部小说连续动画漫剧生产平台”仍缺多集生产编排、跨集状态机、资产版本锁、AI 制片助手和媒体长期持久化。
- 已更新 `docs/novel-to-anime-optimization-plan.md`，新增 2026-05-26 分析章节，明确目标流程、当前能力、关键差距、P0/P1/P2 优化路线、前端信息架构和新验收标准。
- 已更新 `task_plan.md`，新增 Phase 182-190：前 3 项为本轮分析已完成，后续 P0/P1 包括整书生产计划、Story Bible 状态机、资产版本锁、媒体持久化、AI 制片助手和生产质量检查。
- 已更新 `findings.md`，记录整部小说动画漫剧平台的核心发现和后续建设重点。

## 2026-05-26 Phase 193 开始执行

- 按当前规划优先落地 P0“整书生产计划 / 多集 Episode Plan”。
- 实施假设：第一版不新增数据库表，复用 `Novel.extra_data.series_plan` 持久化整本小说的多集生产编排，后续再按生产规模拆分 Series/Episode 表。
- 成功标准：后端可生成并读取多集计划；计划按章节顺序覆盖整本小说；每集包含章节范围、钩子、冲突、反转、悬念、承接、人物/场景/道具/事件、生产状态和下一步动作；前端小说详情可展示并一键生成/继续单集工作流；专项测试、编译和前端类型/构建验证通过或记录阻断原因。

## 2026-05-26 Phase 193 完成

- 新增 `backend/app/services/series_production.py`，生成整书多集 Episode Plan，并把计划保存到 `Novel.extra_data.series_plan`。
- 新增小说接口：`GET /api/v1/novels/{novel_id}/series-plan` 读取已保存计划，`POST /api/v1/novels/{novel_id}/series-plan` 生成并可持久化计划。
- Episode Plan 已包含章节范围、剧情钩子、冲突、反转、悬念、下集承接、关键人物/场景/道具/事件、剧本/分镜/镜头/视频/直生任务计数、生产状态、下一步动作和 workflow 入口。
- 小说详情页新增“整书计划”顶部按钮和标签页，支持 AI 生成多集计划、查看每集一致性上下文、创建或继续本集工程。
- 顺手修复小说详情“设置”页签只读字段警告和保存无效问题，标题、简介、类型现在会调用后端更新接口并同步页面状态。
- 新增 `backend/test_series_production.py`，验证生成、持久化、顺序覆盖和无章节错误。
- 验证通过：`python3 -m compileall app`；`DEV_MODE=true pytest -q test_series_production.py test_short_video_production.py` 5 passed；`DEV_MODE=true pytest -q` 137 passed、1 skipped、1 warning；`npx tsc --noEmit`；`npm run build`；`git diff --check`。
- 已重启服务并烟测：后端 `http://127.0.0.1:8000/health` healthy；前端 `http://127.0.0.1:3000/novels` 200；临时小说 3 章调用 series-plan 接口成功生成 2 集计划；浏览器打开小说详情并切换“整书计划”标签页可见。
- 剩余 warning：测试环境未设置 `FERNET_KEY`，这是既有安全提示；生产环境必须设置稳定密钥。
- 注意事项：不要并行运行 `npx tsc --noEmit` 与 `next build`，构建会重建 `.next/types` 导致 tsc 读到中间状态；本轮已在 build 完成后单独重跑 tsc 并通过。

## 2026-05-26 Phase 194-198 生产控制闭环

- 接续完成 Phase 194：Story Bible 状态机已通过专项验证，并确认前端小说详情 Story Bible 标签页有“状态机/状态检查”入口。
- 新增 `backend/app/services/production_control.py`，统一实现小说级生产定稿包、资产版本锁应用、媒体持久化巡检、工作流质量检查和 AI 制片助手。
- 新增 `/api/v1/production-control` 路由：`/novels/{novel_id}/production-pack`、`/workflow/{workflow_id}/asset-locks`、`/media-audit`、`/quality-check`、`/producer-assistant`。
- 扩展 `media_persistence.py`：新增音频/artifact 类型、`local_static_path_for_url()` 和 `audit_media_url()`，用于判断历史视频、图片、音频、字幕和渲染包是否本地可长期访问。
- 扩展 workflow 批量直生音视频：MediaJob 会继承 Shot 生产上下文中的资产版本锁、关键帧、多视图参考和 Production Contract，后续真实 Sora/Veo/ComfyUI/口型适配可直接消费。
- 前端 workflow 新增 “AI 制片控制台”：显示基础就绪度、下一步建议、制片检查、AI 补齐、资产定稿、媒体巡检和质量检查入口，并展示资产锁数量、媒体缺失和质量分。
- 新增 `backend/test_production_control.py`：覆盖生产定稿包、镜头资产锁、直生音视频资产锁继承、媒体巡检、质量检查和 AI 制片助手安全补齐。
- 验证通过：`python3 -m compileall app`；`DEV_MODE=true pytest -q test_story_state_machine.py test_production_control.py` 4 passed；`DEV_MODE=true pytest -q test_short_video_production.py test_media_subtitles.py test_workflow_routes.py test_series_production.py test_story_state_machine.py test_production_control.py` 39 passed；前端 `npx tsc --noEmit` 通过；`npm run build` 通过；`git diff --check` 通过。

## 2026-05-26 前端可见性补强执行中

- 已确认生产控制能力在后端和 workflow 侧栏中存在，但缺少独立、显眼的前端入口，用户容易误判为“没有功能”。
- 新增 `/producer` 独立页面，将 Story Bible 状态机、资产定稿包、媒体巡检、质量检查和 AI 制片助手集中成一个生产工作台。
- 同步补齐顶部导航“AI制片”、控制台“AI制片中心”卡片，以及 workflow 页顶部直达按钮。
- 验证通过：前端 `npx tsc --noEmit` 通过；`npm run build` 通过；`git diff --check` 通过；重启前端服务后 `/producer`、`/dashboard`、`/workflow` 均返回 200，后端 `/health` 返回 200。

## 2026-05-26 工作流与 AI 制片流程复核

- 本轮针对用户反馈重新检查 `/workflow` 与 `/producer`：当前 AI 制片中心仍以“选择已有工作流”为起点，缺少小说/章节选择和“为当前章节创建/继续工程”的入口，导致用户无法按小说生产语义启动。
- 工作流页已有视频批量生成、视频拼接、渲染包等接口调用，但动作分散在视频/合成步骤，缺少一个面向非专业用户的“按当前小说/章节/剧本/分镜/镜头一键生成本集草片”流程按钮和阶段反馈。
- 新增共享前端流程 `frontend/src/lib/episode-preview-production.ts`，统一串联工作流链路确认、剧本复用/生成、分镜复用/生成、AI 制片安全补齐、资产锁、短视频 Production Contract、批量直生音视频、拼接、渲染预检和渲染包。
- `/producer` 已改为先选小说和章节，再筛选/创建本集制片工程；同页展示文本/视频模型选择和本集草片阶段反馈。
- `/workflow` 顶部已新增“一键生成本集草片”面板，直接展示小说/章节/分镜/字幕状态和 9 个阶段进度，生成成功后提供预览、字幕和时间线入口。
- 验证已完成：后端 `DEV_MODE=true pytest -q test_workflow_routes.py test_short_video_production.py test_production_control.py` 32 passed；前端 `npx tsc --noEmit` 通过；`npm run build` 通过；`git diff --check` 通过。
- 已重启前端服务并烟测：`/producer` 200、`/workflow` 200、后端 `/health` 200。

## 2026-05-26 AI 制片模型调用修复开始

- 用户反馈 AI 制片生成的视频和音频完全不对，经排查确认当前一键流程使用 workflow 批量直生音视频 DEV 占位接口，未真正调用用户选择的视频模型和声音模型。
- 修复方向：保留直生音视频策略，但新增/接入“视频+声音分步生成”策略，前端必须同时传入视频模型和声音模型，后端分别创建 VideoJob/TTSJob 并写入 workflow，合成时使用这些任务。

## 2026-05-26 AI 制片模型调用修复完成

- 后端 `/workflow/{workflow_id}/generate-media-batch` 已支持 `separate_video_tts`：按用户所选视频模型配置创建 `VideoJob`，按用户所选声音/TTS 模型配置创建 `TTSJob`，并生成字幕轨。
- 真实视频路径会调用火山 Ark `content_generation.tasks.create()`，真实声音路径会调用 MiniMax 或火山 TTS；DEV_MODE 且缺 Key 时才生成本地占位，非 DEV 不再静默占位。
- 云端任务未完成时返回 `ready_for_concatenate=false` 和 pending job ids，前端 AI 制片流程会停止在媒体阶段并提示等待，不再继续假合成。
- 前端 `/producer` 继续传入文本、视频、声音模型；`/workflow` 视频步骤也从“批量直生音视频”改为默认“视频+配音分步生成”，并传 `audio_model_config_id`。
- 无对白镜头会自动生成旁白草稿进入 TTS 和字幕轨，避免短视频部分镜头无声音。
- 验证通过：`DEV_MODE=true pytest -q test_workflow_routes.py::test_workflow_media_batch_separate_video_tts_uses_selected_models test_workflow_routes.py::test_workflow_concatenate_builds_multi_shot_sequence_manifest` 2 passed；`DEV_MODE=true pytest -q test_workflow_routes.py test_production_control.py test_short_video_production.py` 33 passed；`python3 -m compileall app` 通过；前端 `npx tsc --noEmit` 通过；`npm run build` 通过；`git diff --check` 通过。

## 2026-05-27 多镜头视频一致性修复开始

- 用户反馈《逆天至尊》第一章同一分镜两个镜头视频完全不像同一部动漫；本轮聚焦后端真实生成链路，而不是只调整前端展示。
- 已确认修复边界：保留现有 VideoJob/Shot/StoryEntity/Asset 数据结构，不新增迁移；新增视频一致性包 helper，统一服务单镜头和 workflow 批量生成。
- 已开始修改 `backend/app/api/v1/endpoints/video.py`：有效角色按当前小说/章节过滤，错误实体从人物上下文剔除；新增分镜级 `style_lock`、`series_seed`、`character_visual_locks`、`reference_image_source` 和参考图回退。
- 已开始修改 `backend/app/api/v1/endpoints/workflow.py`：`separate_video_tts` 改用视频一致性包生成最终 prompt、seed 和 image_url，不再直接用普通 `_shot_generation_prompt(shot)` 调 SDK。
- 已收紧 `entity_extraction_service.py` 的本地角色抽取规则，只有显式“角色/人物/主角/配角”或“某某说/问/喊/名为”等上下文才抽角色，避免普通动作/状态词污染角色库。

## 2026-05-27 多镜头视频一致性修复完成

- `/video/generate` 已落地视频一致性包：真实角色优先、显式角色保留、污染角色过滤、角色名误入道具时剔除，并把角色视觉 DNA、场景、道具、事件、字幕、资产锁和 Story Bible 写入最终 prompt。
- 同一分镜的视频任务现在保存共同的 `consistency.series_seed`、`style_lock` 和 `character_visual_locks`；每个镜头仍有镜头级 seed，避免完全复制但保持同一系列锚点。
- 参考图回退顺序已补齐：用户传入图、Shot.image_url、角色资产锁、角色头像、通用资产锁、当前小说资产库；来源写入 `prompt_parameters.reference_image_source`，便于前端和历史记录解释。
- Workflow `separate_video_tts` 现在使用同一套最终 prompt、seed 和参考图参数，真实火山 Ark SDK 请求不再只发送普通镜头描述。
- 新增三类回归：逆天至尊式污染实体与主角一致性、批量 workflow 一致性 prompt、实体抽取不误判疼痛/狂喜/阳光/年轻/瘦弱。
- 验证通过：`python3 -m compileall app`；`DEV_MODE=true pytest -q` 152 passed、1 skipped、1 warning；`DEV_MODE=true pytest -q test_workflow_routes.py test_storyboard_templates.py test_character_scope.py test_story_prompt_context.py test_story_entity_production_pack.py` 59 passed；前端 `npx tsc --noEmit` 通过；`npm run build` 通过；`git diff --check` 通过。

## 2026-05-27 整部小说级视频与剧情一致性完成

- 新增 `backend/app/services/novel_continuity.py`，统一构建整部小说连续性包：小说级系列种子、章节种子、上一章承接、当前章状态快照、下一章不可矛盾约束、状态机摘要、最近事件线和实体锁。
- `/video/generate` 已从分镜级 `series_seed` 升级为 `novel_series_seed + chapter_seed + storyboard_seed + shot_seed`。同一小说跨章节共享小说级视觉系列，章节和镜头只做局部派生。
- 视频最终 prompt 增加“整部小说连续性锁”，包含上一章承接、当前章状态锁、最近事件线、人物/场景/道具状态机和硬约束；VideoJob.extra_data.consistency 保存同一套信息用于历史追踪。
- 剧本生成上下文和剧本 `extra_data.generation_context` 已写入小说连续性锁，前端生成上下文接口也能返回 `novel_series_seed/chapter_seed/continuity_lock`。
- 分镜 AI 生成、智能分镜和每个 Shot.extra_data 都写入 `novel_continuity/continuity_lock/chapter_state_snapshot`，保证后续视频、配音、字幕和合成可继承同一套小说级上下文。
- 新增跨章节回归测试：同一《逆天至尊跨章》第一章与第二章分别生成分镜和视频，断言 `novel_series_seed` 相同、`chapter_seed` 不同，第二章 prompt 包含第一章承接、孙剑和断剑。
- 验证通过：`python3 -m compileall app`；后端相关 `DEV_MODE=true pytest -q test_workflow_routes.py test_story_prompt_context.py test_storyboard_templates.py test_story_state_machine.py` 51 passed；后端全量 `DEV_MODE=true pytest -q` 153 passed、1 skipped；前端 `npx tsc --noEmit`、`npm run build`、构建后再次 `npx tsc --noEmit` 通过；`git diff --check` 通过。

## 2026-05-27 视频模型列表测试数据清理

- 用户反馈视频生成页出现 `test-video-*` 等无效视频模型。排查确认本地开发库被自动测试写入 37 条测试模型和 37 条测试配置。
- 后端 `/llm/models` 与 `/llm/configs` 默认过滤内部测试模型，包括 `test-video-*`、`doubao-seedance-test`、`doubao-seedance-consistency-test`、`speech-test` 等。
- 前端通用模型能力筛选和视频生成页模型列表增加兜底过滤，避免旧缓存或其他页面传入测试配置时继续展示。
- 已清理本地 SQLite 中 37 条测试模型和 37 条测试配置；接口复核火山视频模型列表不再包含 `test-video-*`。
- 验证通过：`python3 -m compileall app`；专项后端测试 5 passed；前端 `npx tsc --noEmit`；`git diff --check`；服务重启后 `/video-generation` 200。

## 2026-05-30 智能剧本到视频链路修复

- 针对“智能生成剧本报错，重新检查小说到视频链路”完成根因排查：剧本生成专项前半段可过，但后续智能分镜/镜头链路会在读取 Asset 模板时触发 `sqlite3.OperationalError: no such column: assets.entity_type`。
- 根因 1：`Asset` ORM 已新增 `entity_type/version/is_locked/is_final/source_job_id/source_prompt` 等生产字段，服务层也使用 `source_url/generation_params` 做预置资产去重，但 `init_db.py` 对旧 SQLite 的迁移只补到 `entity_id`，导致老库和测试库结构不完整。
- 修复：`backend/app/models/asset.py` 补齐 `source_url/generation_params` 字段；`backend/init_db.py` 同步/异步迁移补齐 Asset 当前读写字段，老库启动后可自动迁移。
- 根因 2：没有先生成 Story Bible/StoryEntity 时，`load_story_prompt_context()` 已能从小说/章节文本抽取角色、场景、道具、事件，但 `scripts.py` 的 `summary/generation_context` 只读持久化 StoryEntity，导致智能剧本生成元数据为空，后续分镜/视频一致性锚点变弱。
- 修复：`build_script_generation_context()` 合并文本抽取出的 story context 到 production pack，保证非专业用户只导入小说和章节时，也能把人物、场景、道具、事件传入剧本生成、上下文预览和后续链路。
- 补强：`VideoGenerateResponse` 现在直接返回 `project_id/workflow_id/novel_id/chapter_id/script_id/storyboard_id/shot_id`，前端点击生成后即可确认绑定关系，不必等历史列表二次查询。
- 新增/更新回归：`test_script_generation_uses_text_extracted_entities_without_story_bible` 覆盖无 Story Bible 的文本实体承接；`test_video_job_infers_full_lineage_from_chapter_shot` 覆盖视频即时响应 lineage。
- 验证通过：`python3 -m compileall app init_db.py`；`DEV_MODE=true pytest -q test_asset_templates.py` 4 passed；`DEV_MODE=true pytest -q test_story_prompt_context.py` 8 passed；`DEV_MODE=true pytest -q test_story_prompt_context.py test_asset_templates.py test_workflow_routes.py test_storyboard_templates.py` 58 passed、1 warning；前端 `npx tsc --noEmit` 通过；`npm run build` 通过；`git diff --check` 通过。
- API smoke 通过：创建小说、章节，调用 `/scripts/generate`、`/scripts/generate-context/{chapter_id}`、`/storyboards/generate-smart`、`/video/generate`，再按 `novel_id/chapter_id/storyboard_id/shot_id` 查询视频历史，链路全部返回成功并保持 lineage 一致。
- 服务已收敛重启：清理旧 8000/3000 监听进程后，用固定 tmux 会话启动 `ai-video-backend` 与 `ai-video-frontend`；后端 `/health` 200，前端 `/scripts` 200，启动日志无报错。
- 剩余提示：测试环境仍有既有 `FERNET_KEY` warning，生产环境需要设置稳定密钥，否则加密存储的模型 Key 重启后可能无法解密。

## 2026-05-30 章节生产链路重复剧本修复

- 用户前端 toast `生成失败: Multiple rows were found when one or none was required` 已定位到 `/api/v1/chapters/{chapter_id}/production-status` 与 `/generate-all` 假设同一章节只有一份剧本。
- 新增章节生产链路 helper：同一章节多份剧本时按 `updated_at/created_at` 取最新剧本，同一剧本多份分镜时按最新分镜返回生产状态，不再使用 `scalar_one_or_none()` 读取可版本化记录。
- `generate-storyboard` 与 `generate-all` 现在复用最新剧本继续生成；智能分镜新增可选 `script_id`，一键生成时分镜绑定同一份剧本，不再隐式创建另一份自动改编脚本导致返回 `script_id` 和实际分镜脚本不一致。
- 新增回归 `test_chapter_generation_reuses_latest_script_when_multiple_scripts_exist`：同一章节连续生成两份剧本后，生产状态和一键生成都应返回最新剧本，并让新分镜绑定该剧本。
- 验证通过：先确认新增测试红在 `MultipleResultsFound`；修复后 `DEV_MODE=true pytest -q test_workflow_routes.py::test_chapter_generation_reuses_latest_script_when_multiple_scripts_exist` 1 passed；`python3 -m compileall app init_db.py` 通过；`DEV_MODE=true pytest -q test_story_prompt_context.py test_asset_templates.py test_workflow_routes.py test_storyboard_templates.py` 59 passed、1 warning。

## 2026-05-30 角色智能提取 500 修复

- 用户反馈角色智能提取报 500。后端日志定位到 `/api/v1/characters/extract` 自动生成头像阶段：某个角色头像生成失败并 `rollback()` 后，同批次后续角色 ORM 对象被过期，继续访问 `char.avatar` 触发 SQLAlchemy `MissingGreenlet`。
- 修复：角色提取入库提交后只保留角色 ID；头像生成循环每次按 ID 重新查询角色，失败回滚后不再复用已过期 ORM 对象；最终返回前也按 ID 重新查询，保证响应数据来自当前会话的已加载对象。
- 新增回归：单角色自动头像成功路径；两名角色中第一名头像生成失败后，接口仍返回 201 并继续处理第二名，避免再次出现 `MissingGreenlet`。
- 验证通过：先确认 `test_extract_characters_continues_after_one_avatar_generation_failure` 红在 `char.avatar` 的 `MissingGreenlet`；修复后该测试 1 passed；`python3 -m compileall app init_db.py` 通过；`DEV_MODE=true pytest -q test_character_scope.py` 7 passed。

## 2026-05-31 P1 Story Bible 角色音色锁落地

- 工作流批量“视频+配音分步生成”现在会为每个镜头解析 Story Bible：显式请求、Shot.extra_data、Storyboard.content、Workflow metadata 和小说最新 Story Bible 都可作为候选来源。
- 批量 TTS 会从镜头对白、character_refs、entity_refs 中识别主说话角色，并优先使用 Story Bible `character_rules.voice/voice_model/voice_speed`；回退顺序为角色库音色、界面默认音色。
- `/workflow/{workflow_id}/generate-media-batch` 返回 `tts_voice_lock_count`，TTSJob.extra_data 写入 `voice_source/voice_character_name/story_bible_id`，工作流状态接口也返回 TTS extra_data，前端可以解释真实命中情况。
- 独立 `/tts/generate` 多角色对白修复为按段解析 Story Bible 音色和语速，不再把第一个角色音色套到所有角色；DEV_MODE 生成也写入每段 `voice_source/speed`。
- 前端 `/workflow` 视频步骤新增 Story Bible 角色音色锁选择、开关和命中数量提示；`/tts` 页面新增角色音色锁选择，并修复成功状态只识别 `completed` 导致 `succeeded` 音频不显示的问题。
- 同步收敛全量测试阻断项：修复 Graph/Versions 路由双 prefix 导致的 404，补齐旧 SQLite `publications` 表当前 ORM 字段迁移，并更新 Shot Quality 测试样例以匹配生产级“场景/道具/事件/审核状态”检查规则。
- 验证通过：新增测试先红后绿；`DEV_MODE=true PYTHONPATH=. pytest -q --import-mode=importlib .`（backend 目录）341 passed、1 skipped；`DEV_MODE=true pytest -q backend/test_tts_story_bible.py ...` 29 passed；`python3 -m compileall backend/app` 通过；前端 `npx tsc --noEmit` 和 `npm run build` 通过；服务已重启，后端 `/docs` 200，前端 `/workflow` 与 `/tts` 200，浏览器确认 `/tts` 角色音色锁渲染且无前端错误日志。

## 2026-05-31 轻量生产闭环补强

- 并行启动前端/后端只读审计，结论收敛到小团队最容易卡住的闭环问题：AI 制片入口不够显性、继续制作路由契约不一致、剧本页生成分镜只创建空壳、合成/发布没有保存可播放视频 URL。
- 后端短视频就绪度新增空分镜阻断：当工作流已绑定分镜但没有镜头时返回 `missing_shots`，推荐先生成或创建镜头，不再在 `ready=false` 时提示“链路已就绪”。
- 前端 `/producer` 新增“出片就绪度”状态卡和详细面板，自动加载镜头数、预计时长、阻断项、提醒和建议；支持一键刷新生产合约。
- `/producer` 一键草片生成支持自动创建本集工程；章节一键生成剧本/分镜后会自动挂载到工作流并刷新短视频就绪度。
- 修复前端路由契约：章节/小说不再跳不存在的 `/scripts/new`；剧本和分镜到视频统一使用 `script_id/storyboard_id`；视频页兼容旧 `script/storyboard` 参数；分镜页兼容旧 `sb` 参数。
- 剧本列表和剧本详情的“生成分镜”改调用 `/storyboards/generate`，生成真实镜头后进入分镜上下文，不再只创建空分镜壳。
- `/synthesis/execute` 写入源视频/音频 URL，避免 `synthesis_jobs.video_url` 非空约束失败；`/synthesis/publish` 从合成任务写入 `Publication.video_url/cover_url/duration_seconds/visibility`，本地 artifact 同步记录可播放视频。
- 合成页打开当前合成结果、导出结果和发布 artifact 时，会把 `/static/...` 解析到后端 origin，避免前端端口访问不到静态媒体。
- 已完成针对性验证：短视频就绪度新增测试先红后绿；`test_project_permissions_publication.py` 新增发布视频 URL 与 `/synthesis/execute` 落库回归先红后绿；前端 `npx tsc --noEmit` 通过；后端专项 `test_project_permissions_publication.py test_short_video_production.py` 10 passed。

## 2026-06-05 Quick Start 整书计划入口收口

- 复盘计划后确认最新阶段已完成到 Phase 230，剩余明确用户可见缺口之一是：Quick Start 仍偏首集工程，完成后没有直接进入整部小说/多集生产计划。
- Quick Start 成功结果区新增“进入整书计划”按钮，跳转到 `/novels/{novelId}?tab=series-plan`，让用户从首集工程继续规划整部漫剧。
- 小说详情页新增 URL 标签参数支持：`?tab=series-plan` 直接打开“整书计划”，`?tab=series` 兼容为同一标签。
- 新增 `frontend/e2e/quick-start-series-plan.spec.ts`，覆盖 Quick Start 结果入口和小说详情 URL 参数激活整书计划。
- 验证通过：先红后绿；`PATH=/opt/homebrew/opt/node@22/bin:$PATH npx playwright test e2e/quick-start-series-plan.spec.ts --project=chromium` 2 passed；`PATH=/opt/homebrew/opt/node@22/bin:$PATH npx tsc --noEmit` 通过；`PATH=/opt/homebrew/opt/node@22/bin:$PATH npm run build` 通过；`git diff --check -- frontend/src/app/quick-start/page.tsx frontend/src/app/novels/[id]/page.tsx frontend/e2e/quick-start-series-plan.spec.ts` 通过。
- 验证环境说明：本机 nvm/Codex 自带 Node 加载 `@next/swc-darwin-arm64` 会被 macOS Team ID 校验拦截；Homebrew Node 22 可以正常加载 SWC，因此前端构建、Playwright 和后续 dev server 均显式使用 `/opt/homebrew/opt/node@22/bin`。

## 2026-06-05 多视图资产制片向导收口

- 后端新增创作者向多视图预设：角色三视图、场景四视图、道具多视图，接口为 `/api/v1/assets/view-presets`。
- 后端新增 `/api/v1/assets/generate-entity-views`，可按小说 StoryEntity 生成指定视图或缺失视图；生成资产会绑定 `novel_id/chapter_id/script_id/entity_id/entity_type`，并保存 `generation_params.view_key/view_label/style/aspect_ratio`。
- 资产锁定逻辑改为同一实体同一视图互斥，正面、侧面、背面或场景多个视图可以同时定稿。
- 资产页新增“AI 资产制片向导”：先选小说，再选角色/场景/道具和画面风格，展示必备视图、生成状态、预览、编辑和锁定入口。
- 资产编辑表单改为低门槛默认视图：资源/缩略图支持上传和预览，普通路径不再直接暴露 JSON；变量配置、视图配置、原始提示词和生成参数移入“高级设置”。
- 资产列表和实体筛选中文化展示，减少 `image/character/prop/anime` 等内部值外露。
- 新增后端测试 `backend/test_asset_multiview_generation.py` 和前端资产页 E2E，覆盖预设接口、实体多视图生成、视图锁定、资产创建/编辑/归档、AI 向导选择和高级字段默认隐藏。
- 验证通过：`pytest -q backend/test_asset_multiview_generation.py` 2 passed；`PATH=/opt/homebrew/opt/node@22/bin:$PATH npx playwright test e2e/assets.spec.ts --project=chromium` 2 passed；`PATH=/opt/homebrew/opt/node@22/bin:$PATH npx tsc --noEmit` 通过；`git diff --check -- frontend/src/app/assets/page.tsx frontend/e2e/assets.spec.ts frontend/src/lib/api-client.ts backend/app/services/asset_generation_service.py backend/app/api/v1/endpoints/assets.py backend/test_asset_multiview_generation.py` 通过。

## 2026-06-05 Phase 241 实体页多视图可见性

- 实体审阅台已从裸 `fetch('/api/v1/...')` 切换为统一 `apiClient`，避免前端同源没有 API 代理时实体列表、统计、编辑、删除、批量确认和合并失效。
- 角色/场景/道具实体卡片新增“多视图定稿包”，按预设视图展示 `已定稿/已生成/待补齐`，让创作者在实体库就能判断参考资产是否完整。
- 实体卡片新增“补齐多视图”入口，跳转到 `/assets?novel_id=...&entity_type=...&entity_id=...`；资产库会读取 URL 参数并自动预选向导小说、对象类型和小说对象。
- 资产手工创建/更新 payload 补齐 `entity_type`，后端 Asset 创建/更新模型同步支持该字段，手工补图和 AI 生成图都能进入同一套实体多视图链路。
- 新增 `frontend/e2e/entities-multiview.spec.ts`，覆盖创建小说实体、创建并锁定视图资产、实体页状态展示和跳转资产向导。
- 验证通过：`PATH=/opt/homebrew/opt/node@22/bin:$PATH npx playwright test e2e/entities-multiview.spec.ts --project=chromium` 1 passed；`PATH=/opt/homebrew/opt/node@22/bin:$PATH npx playwright test e2e/assets.spec.ts --project=chromium` 2 passed；`PATH=/opt/homebrew/opt/node@22/bin:$PATH npx tsc --noEmit` 通过；`python3 -m compileall backend/app` 通过；`pytest -q backend/test_asset_multiview_generation.py` 2 passed。

## 2026-06-05 Phase 242 分镜与镜头多视图提醒

- 分镜管理页的镜头详情新增“参考资产完整度”，会根据镜头 `character_refs` 和 `extra_data.entity_refs` 拉取实体资产包，展示多视图定稿数、缺失项和补齐入口。
- 镜头管理页编辑弹窗新增同样的多视图完整度提醒，非专业用户不需要打开高级 JSON，就能判断当前镜头的角色、场景、道具参考图是否足够稳定。
- “补齐参考图”统一跳转资产制片向导，并携带 `novel_id/chapter_id/entity_type/entity_id`，方便从镜头直接补角色三视图、场景四视图或道具多视图。
- 新增 `frontend/e2e/storyboard-shot-multiview.spec.ts` 和 `frontend/e2e/shots-multiview.spec.ts`，覆盖分镜页和镜头页从出镜实体到资产向导的前端可见链路。
- 验证通过：`PATH=/opt/homebrew/opt/node@22/bin:$PATH npx playwright test e2e/storyboard-shot-multiview.spec.ts e2e/shots-multiview.spec.ts --project=chromium` 2 passed；`PATH=/opt/homebrew/opt/node@22/bin:$PATH npx tsc --noEmit` 通过；`python3 -m compileall backend/app` 通过；`pytest -q backend/test_asset_multiview_generation.py` 2 passed；相关文件 `git diff --check` 通过。

## 2026-06-05 Phase 243 视频生成前参考资产预检

- 视频生成页选择具体镜头后新增“生成前参考资产预检”，按当前镜头出镜角色、场景、道具展示多视图定稿数和缺失项。
- 缺失角色正/侧/背、场景全景/布局/光影、道具主视图等必备视图时，页面提示“建议补齐”，并提供跳转资产制片向导的入口；当前不硬阻断 DEV_MODE 或轻量草片生成。
- 新增 `frontend/e2e/video-preflight-multiview.spec.ts`，覆盖视频生成页从镜头引用实体到缺失视图提醒、补齐入口的生成前可见链路。
- 验证通过：`PATH=/opt/homebrew/opt/node@22/bin:$PATH npx playwright test e2e/entities-multiview.spec.ts e2e/storyboard-shot-multiview.spec.ts e2e/shots-multiview.spec.ts e2e/video-preflight-multiview.spec.ts --project=chromium` 4 passed；`PATH=/opt/homebrew/opt/node@22/bin:$PATH npx tsc --noEmit` 通过；`python3 -m compileall backend/app` 通过；`pytest -q backend/test_asset_multiview_generation.py` 2 passed。

## 2026-06-05 Phase 244-246 多视图生产化收口

- 资产视图预设扩展推荐比例、题材模板示例、示例图路径和提示词样例；资产页向导直接展示“推荐比例：9:16...”和“题材模板示例”，让用户少填提示词。
- 多视图生成改为逐视图容错：某个视图生图失败时，保存 `asset_type=text` 的失败记录，写入 `generation_params.status=failed/error_message/retryable/view_key`，接口返回 `failures` 而不是整体 500。
- 新增 `/assets/{asset_id}/retry-generation` 和 `/assets/{asset_id}/visual-consistency`；前端资产卡片展示失败原因、重试生成按钮和“一致性 N”。
- 前端 `apiClient` 补齐失败重试和一致性写回方法，资产页补稳定 `data-testid`，避免中文文案重复导致 E2E 误匹配。
- 验证通过：`pytest -q backend/test_asset_multiview_generation.py` 4 passed；`PATH=/opt/homebrew/opt/node@22/bin:$PATH npx playwright test e2e/assets.spec.ts --project=chromium` 3 passed；`PATH=/opt/homebrew/opt/node@22/bin:$PATH npx tsc --noEmit` 通过；`python3 -m compileall backend/app` 通过；多视图回归 E2E 4 passed。

## 2026-06-06 Phase 250 后端一致性预检底座

- 已新增 `entity_ref_normalizer`，统一兼容旧 ID 列表和新 dict refs，后续新写入按 dict refs 输出。
- 已修复 `AssetLockService`：支持 dict refs，按实体类型/分类和用户/小说范围查锁定资产；`unlock_shot_assets` 只解除镜头绑定，不再修改共享资产锁。
- 已移除 `consistency_context.py` 中重复覆盖的 `auto_fill_shot_entity_refs` 旧定义，并让 `build_consistency_prompt` 注入镜头锁定资产到最终 prompt 和 metadata。
- 已新增统一生产预检服务 `consistency_preflight.py` 和标准接口 `POST /api/v1/consistency/preflight`，返回 `ready/issues/blocking_issue_count/model_route/entity_refs/asset_version_locks`。
- TDD 验证：先运行 `DEV_MODE=true PYTHONPATH=. pytest -q tests/test_p0_consistency_pipeline.py -q`，4 个新增断言按预期失败；实现后同命令 12 passed。
- 回归验证通过：`python3 -m compileall app`；`DEV_MODE=true PYTHONPATH=. pytest -q tests/test_p0_consistency_pipeline.py test_asset_lock_service.py test_prompt_composer_locked_assets.py test_shots_rebuild_prompts.py test_fill_entity_refs.py test_consistency_checker.py`，64 passed；`git diff --check` 通过。

## 2026-06-06 Phase 250 生产门禁收口

- 视频、图片、TTS、直生音视频入口已接入统一 `build_generation_context_package()`：生产模式下不能关闭一致性上下文，除非显式 unsafe 降级。
- 生产提交前会阻断未验证 LLM 模型配置、缺失或无法解密 API Key、未验证外部生产适配配置、本地 `/static` 参考图参与云端图生视频等问题。
- 失败返回统一结构：`generation_preflight_failed`、issues、blocking count 和 autofix actions；图片/TTS/媒体在预检失败时不会创建历史任务。
- 预检接口支持 `external_config_id`，便于前端在 ComfyUI/云渲染/直生音视频配置上展示相同问题提示。
- 验证通过：`DEV_MODE=true PYTHONPATH=. pytest -q tests/test_p0_consistency_pipeline.py -q` 20 passed；`DEV_MODE=true PYTHONPATH=. python3 -m compileall app && pytest -q tests/test_p0_consistency_pipeline.py test_asset_lock_service.py test_prompt_composer_locked_assets.py test_shots_rebuild_prompts.py test_fill_entity_refs.py test_consistency_checker.py test_media_subtitles.py test_tts_story_bible.py test_image_generation_links.py test_workflow_routes.py` 152 passed。

## 2026-06-06 Phase 251 前端生产状态与工作流入口

- 新增 `ProductionStatusRail` 和 `PreflightIssueList` 组件，用统一卡片展示链路、镜头、音频、字幕、合成和渲染包状态，以及阻断/提醒问题。
- `apiClient` 新增 `preflightGeneration()`，前端后续所有生成页可直接调用 `/consistency/preflight` 展示同一套模型、参考图和资产锁问题。
- `/workflow` 移除无 `workflow_id` 时自动创建“新工作流”的副作用；改为展示“选择或创建本集工程”空态，用户显式进入 AI 制片中心或手动创建空白工程。
- `/workflow` 与 `/producer` 均展示本集生产状态；AI 制片助手的“下一步”提示增加“执行下一步”按钮，直接触发安全补齐。
- 新增 E2E `workflow-production-guidance.spec.ts`，先红后绿验证 workflow 页面不会静默调用 `/workflow/start`。
- 验证通过：`PATH=/opt/homebrew/opt/node@22/bin:$PATH npx playwright test e2e/workflow-production-guidance.spec.ts --project=chromium` 1 passed；`npx tsc --noEmit` 通过；`npm run build` 通过；构建后再次 `npx tsc --noEmit` 通过。

## 2026-06-06 Phase 252 合成历史与渲染产物收口

- 先新增后端红灯测试 `test_synthesis_jobs_filter_lineage_and_expose_render_artifacts`，确认旧 `/synthesis/jobs` 会忽略小说/章节/剧本/分镜/镜头和 render 状态筛选。
- 后端 `SynthesisJobResponse` 新增 lineage 与 render artifact 一等字段；`/synthesis/jobs` 支持 `status/render_status/novel_id/chapter_id/script_id/storyboard_id/shot_id` 过滤，并兼容 `extra_data` 顶层、`lineage` 和 `segments[].lineage` 三种历史结构。
- 新增前端红灯 E2E `synthesis-history.spec.ts`，确认旧页面没有合成历史筛选和历史就地预览。
- `/synthesis` 页面新增“合成历史筛选”、历史卡片 lineage 摘要、就地预览面板、字幕 SRT/时间线/渲染清单链接；历史播放不再把用户带回顶部当前合成结果区域。
- 排查并处理验证环境问题：现有 3000 dev server 复用旧 `.next` 导致客户端 JS chunk 404，清理 `.next` 并重启前端后专项 Playwright 通过。
- 验证通过：`DEV_MODE=true PYTHONPATH=. python3 -m compileall app && DEV_MODE=true PYTHONPATH=. pytest -q tests/test_p0_consistency_pipeline.py test_asset_lock_service.py test_prompt_composer_locked_assets.py test_shots_rebuild_prompts.py test_fill_entity_refs.py test_consistency_checker.py test_media_subtitles.py test_tts_story_bible.py test_image_generation_links.py test_workflow_routes.py` 153 passed；`PATH=/opt/homebrew/opt/node@22/bin:$PATH npx tsc --noEmit` 通过；`PATH=/opt/homebrew/opt/node@22/bin:$PATH npm run build` 通过；构建后再次 `npx tsc --noEmit` 通过；Playwright `e2e/synthesis-history.spec.ts e2e/workflow-production-guidance.spec.ts` 2 passed；内置浏览器检查 `/synthesis` 标题和历史筛选可见。

## 2026-06-06 Phase 253 P0 验证与批量门禁收口

- 新增非 DEV workflow 批量生成红灯测试 `test_non_dev_workflow_media_batch_blocks_unverified_video_model_before_jobs`：旧代码返回 200 并可能创建供应商任务；修复后返回 422，`detail.code=generation_preflight_failed`，且未创建 VideoJob。
- workflow 批量“视频+配音”在供应商调用前预先为每个镜头构建一致性 package，并调用统一 `build_generation_context_package()`；生产模式会阻断未验证模型、非公网参考图、lineage 不匹配、缺实体引用和缺资产锁。
- 合成历史筛选补同步 ref，修复快速填写小说/章节/渲染状态后点击“筛选历史”仍发旧参数的问题。
- 验证过程：新增测试先红后绿；`DEV_MODE=true PYTHONPATH=. pytest -q test_workflow_routes.py::test_non_dev_workflow_media_batch_blocks_unverified_video_model_before_jobs -q` 通过；workflow 批量媒体专项 5 passed；后端紧凑一致性套件 154 passed。
- 前端验证：`PATH=/opt/homebrew/opt/node@22/bin:$PATH npx tsc --noEmit` 通过；`npm run build` 通过；构建后再次 `npx tsc --noEmit` 通过；Playwright `e2e/synthesis-history.spec.ts e2e/workflow-production-guidance.spec.ts` 2 passed。
- 环境备注：第一次重跑 synthesis E2E 失败是旧 3000 dev server 复用 stale `.next`，清理 `.next` 并以 `npm run dev -- -p 3000` 重启后通过；后续 Playwright 前如遇同类症状先重启前端。

## 2026-06-06 Phase 254 P1 AI 制片下一步单项执行

- AI 制片助手新增 `action_code` 请求字段；后端 `build_ai_producer_assistant()` 保留 `auto_fix=true` 全量安全补齐，同时支持只执行当前推荐动作。
- 单项执行时不会因为质量报告持久化或后续 ready 动作把其他状态一并写入，避免新手点击“下一步”后状态跳太多、难以回溯。
- `/producer` 的“执行下一步”按钮改为发送当前 `next_action.code`；独立“安全补齐”按钮继续 broad `auto_fix=true`，保留自动化批量修复入口。
- 新增后端回归 `test_ai_producer_assistant_executes_only_requested_safe_next_action`，覆盖只生成资产定稿包、不顺带写入 production contract。
- 新增前端 E2E `producer-next-action.spec.ts`，通过 mock API 断言页面提交的第二次制片助手请求为 `{ auto_fix: true, action_code: 'build_production_pack' }`。
- 验证通过：`DEV_MODE=true PYTHONPATH=. pytest -q test_production_control.py::test_ai_producer_assistant_executes_only_requested_safe_next_action -q` 1 passed；`DEV_MODE=true PYTHONPATH=. pytest -q test_production_control.py -q` 3 passed；`DEV_MODE=true PYTHONPATH=. python3 -m compileall app && DEV_MODE=true PYTHONPATH=. pytest -q test_production_control.py test_workflow_routes.py` 43 passed；前端 `PATH=/opt/homebrew/opt/node@22/bin:$PATH npx tsc --noEmit && npm run build && npx tsc --noEmit` 通过；Playwright `e2e/producer-next-action.spec.ts e2e/workflow-production-guidance.spec.ts e2e/synthesis-history.spec.ts` 3 passed。

## 2026-06-06 Phase 255 P1 本集制片工程复用

- AI 制片中心 `createWorkflowRecord()` 改为幂等的“创建/复用本集工程”：同一小说、同一章节已有未归档 workflow 时优先复用，不再重复 `POST /workflow/start`。
- 复用已有 workflow 时，如果一键生成返回了新的 `script_id/storyboard_id`，会通过 `updateWorkflowStep()` 挂载到已有工程，保持小说章节生产线连续。
- `createWorkflowForSelection`、`runOneClickProduction`、`runPreviewProduction` 三条路径都复用同一幂等入口，减少剧本、分镜、镜头、配音和视频散落到多个同章节工程。
- 按钮文案改为“创建/复用本集工程”，让用户明确系统会优先接上已有工程。
- 新增前端红绿回归：已有 `wf-existing` 时点击“创建/复用本集工程”不会调用 `/workflow/start`，失败前 `startWorkflowCalls=1`，修复后为 0。
- 验证通过：`PATH=/opt/homebrew/opt/node@22/bin:$PATH npx tsc --noEmit` 通过；`PATH=/opt/homebrew/opt/node@22/bin:$PATH npm run build && npx tsc --noEmit` 通过；Playwright `e2e/producer-next-action.spec.ts e2e/workflow-production-guidance.spec.ts e2e/synthesis-history.spec.ts` 4 passed。
