# 模块分类与依赖边界

## 1. 目标架构

保持现有 FastAPI、Next.js、SQLAlchemy 和 React 技术栈，逐步把横向巨型入口收敛为业务能力模块。迁移期间保留原路由和导入兼容层，不进行一次性全仓搬迁。

## 2. 后端分层

目标业务模块结构：

```text
backend/app/features/<feature>/
├── api.py
├── schemas.py
├── application/
├── domain/
├── repositories/
├── adapters/
└── public.py
```

### api.py

负责 HTTP 输入、依赖注入、鉴权上下文和错误映射。不得拥有供应商调用、FFmpeg 操作、复杂 SQL 或跨阶段编排。

### schemas.py

负责 Pydantic 请求、响应和公开枚举。不得访问数据库或服务。

### application/

负责一个用户用例的事务和阶段编排，例如“生成工作流媒体”“渲染工作流包”。可以依赖 domain、repositories 和 adapters。

### domain/

负责纯业务规则、状态机、不可变量和领域错误。不得依赖 FastAPI、SQLAlchemy Session、文件系统或具体供应商 SDK。

### repositories/

负责 SQLAlchemy 查询和持久化。不得返回 HTTPResponse 或抛出 HTTPException。

### adapters/

负责供应商 SDK、HTTP、对象存储、FFmpeg 和外部媒体。通过明确的数据结构返回结果，不暴露供应商细节给 API 层。

### public.py

声明跨业务模块允许使用的最小公共接口。其它 feature 不得导入该模块的私有文件。

## 3. 后端允许依赖

```text
api -> schemas, application, core auth/database
application -> domain, repositories, adapters, other-feature public facade
repositories -> models, core database
adapters -> provider SDK, core config, domain value objects
domain -> Python standard library and domain-local types
```

禁止：

```text
services/domain/repositories/adapters -> api endpoints
endpoint -> another endpoint
models -> service or api
domain -> FastAPI or concrete provider SDK
feature private module -> another feature private module
```

## 4. 前端分类

目标结构：

```text
frontend/src/features/<feature>/
├── api.ts
├── types.ts
├── hooks/
├── actions/
├── components/
├── utils/
└── index.ts
```

### app/**/page.tsx

只负责路由和组装。不得定义跨页面 API client、供应商规则、业务状态机或大段可复用 JSX。

### features/*/api.ts

负责一个领域的 API 方法，复用统一 HTTP transport。不得直接操作 React 状态。

### features/*/hooks

负责页面用例状态、请求生命周期和用户动作。不得重复后端业务判断。

### features/*/components

负责展示和局部交互。复杂弹窗、表单、表格、状态面板独立为组件。

### shared

只放真正跨领域且没有业务所有权的 transport、基础 UI 和通用格式化。业务 helper 不得为了复用而放进 `shared`。

## 5. 当前业务分类

| 业务能力 | 当前主要入口 | 目标所有者 | 优先级 |
|---|---|---|---|
| 工作流媒体生成 | `endpoints/workflow.py` | `features/workflow/application/generate_media.py` | P0 |
| 工作流渲染与拼接 | `endpoints/workflow.py` | `features/workflow/application/render.py`、`adapters/ffmpeg.py` | P0 |
| 视频生成 | `endpoints/video.py` | `features/video/application/generate.py`、provider adapter | P0 |
| Story Bible 与实体 | `endpoints/story_bible.py` | `features/story_bible/*`、`features/entities/*` | P0 |
| 模型配置 | `endpoints/llm_config.py` | `features/model_config/*` | P1 |
| 资产生成 | `services/asset_generation_service.py` | `features/assets/application`、`adapters` | P1 |
| 整书生产运行 | `series_runs.py`、orchestrator | `features/series_run/*` | P1 |
| 前端 API | `src/lib/api-client.ts` | `features/*/api.ts` + shared transport | P0 |
| 视频生成页面 | `app/video-generation/page.tsx` | `features/video-generation/*` | P0 |
| Producer 页面 | `app/producer/page.tsx` | `features/producer/*` | P0 |
| 镜头与分镜页面 | `app/shots`、`app/storyboards` | 对应 feature | P1 |
| Studio | `components/studio`、`studio-api.ts` | 保持现有拆分并继续收敛 | 参考样板 |

## 6. 拆分顺序

### 第一批：建立约束，不改业务

- 代码健康扫描器。
- 存量热点基线。
- 非法依赖扫描。
- CI 棘轮。

### 第二批：解除错误依赖

- 把 endpoint 间共享函数迁入 service/application。
- 把 `shot_quality_service -> video endpoint` 迁为应用服务接口。
- 解除 `series_run_live_preflight <-> series_run_orchestrator` 循环。
- 解除 prompt/visual contract 三模块循环。

### 第三批：后端 P0 用例拆分

- `generate_workflow_media_batch`。
- `render_workflow_package`。
- `concatenate_videos`。
- `generate_video`。
- Story Bible 实体提取和一致性检查。

### 第四批：前端 P0 拆分

- API transport 与领域 client。
- 视频生成页面。
- Producer 页面。
- Assets、Shots、Storyboards、Novel Detail 页面。

### 第五批：测试和类型收敛

- 拆分巨型测试文件。
- 统一 E2E API helper 和 fixture。
- 对新 feature 目录启用 TypeScript strict。
- 逐步扩大 strict 覆盖范围。

## 7. 兼容迁移模式

每次迁移遵守：

1. 用测试锁定原行为。
2. 创建新模块和公开接口。
3. 原入口改为调用新接口。
4. 原路径和响应保持不变。
5. 运行目标测试和全量相关验证。
6. 确认旧文件净行数下降。
7. 单独提交，不混入新功能。

只有所有调用方迁移且验证完成后，才删除兼容 helper。
