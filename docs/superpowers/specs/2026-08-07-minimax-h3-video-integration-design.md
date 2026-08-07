# MiniMax H3 视频模型接入设计

## 目标

在不改变现有 Seedance、旧版 Hailuo、视频任务和已保存模型绑定行为的前提下，为平台增加可实际提交、轮询和交付结果的 MiniMax H3 视频生成能力。

首批交付覆盖：

- 文生视频。
- 首帧图生视频。
- 首帧加尾帧视频。
- 图片、视频、音频组合参考生成。
- 768P 与 2K 输出。
- 4 至 15 秒整数时长。
- 常见固定宽高比与图生视频自适应比例。
- 异步任务提交、状态轮询、失败回写和成片 URL 持久化。
- 模型中心配置、能力展示、任务绑定以及视频生成页真实选择。

## 非目标

首批不接入以下独立产品能力：

- H3-Context-IR 提示词增强任务。
- 768P 视频再生成至 2K。
- MiniMax 任务列表、取消和删除管理界面。
- 未经官方接口契约确认的“原生音频开关”。参考音频输入属于本次范围，但不能把它等同于模型必然生成同步音频。
- 自动发起收费任务作为普通配置测试。

这些能力可以在核心生成链路稳定后独立扩展，避免把不同任务类型和计费行为耦合到首批接入。

## 官方契约基线

本设计以 2026-08-07 的 MiniMax 官方文档为准：

- 模型 ID：`MiniMax-H3`。
- 创建接口：`POST /v2/video_generation`。
- 查询接口：`GET /v2/query/video_generation/{task_id}`。
- 创建请求使用多模态 `content[]`，元素类型为 `text`、`image_url`、`video_url` 或 `audio_url`。
- 素材用途通过 `role` 表达：`first_frame`、`last_frame`、`reference_image`、`reference_video`、`reference_audio`。
- 输出分辨率：`768P`、`2K`。
- 输出时长：4 至 15 秒整数值。
- 文生视频必须提供非 `adaptive` 的 `ratio`；图生视频按输入图片自适应。
- 首尾帧入口允许 0、1 或 2 张图片。
- 全能参考入口允许最多 9 张图片、3 段视频、3 段音频，混合素材总数最多 12 个。
- 提示词最多 7000 字符。
- 成功状态为 `succeeded`，成片地址位于 `task.content.url`；失败终态包括 `failed` 与 `cancelled`。
- 官方建议轮询间隔为 10 秒。

官方来源：

- <https://platform.minimaxi.com/docs/guides/video-generation>
- <https://platform.minimaxi.com/docs/api-reference/video-generation-v2-create>
- <https://platform.minimaxi.com/docs/api-reference/video-generation-v2-query>

## 当前系统差距

当前平台已具备通用 `VideoCommand`、模型目录、连接配置、执行快照和视频任务持久化，但仍缺少完整的 H3 生产链路：

1. 内置驱动注册表没有 MiniMax 视频驱动。
2. MiniMax 目录只覆盖文本、图片和语音模型。
3. 当前视频请求先构造成 Ark/Seedance content，文本中混入 `--duration` 等 Ark 参数，不能直接发送给 H3。
4. 通用视频命令只保留素材 URL，无法完整表达首帧、尾帧和参考素材角色。
5. 视频状态查询和后台刷新仍以 Ark SDK 为主，无法读取 H3 v2 的 `task.content.url`。
6. 当前前端请求没有独立尾帧字段和 H3 比例选择契约。

只增加模型种子数据会形成“模型卡可见、实际请求不可用”的假接入，因此不可采用。

## 架构设计

### 1. H3 能力契约

新增独立的 MiniMax H3 视频契约模块，作为以下规则的唯一所有者：

- 模型 ID 和 v2 端点。
- 参数 schema：`duration`、`resolution`、`ratio`。
- 提示词和参考素材上限。
- 输入模式与 role 规则。
- 供应商状态到平台状态的映射。

Seedance 合同保持不变。H3 规则不得加入 `seedance_contract.py`，避免用供应商名称判断行为。

### 2. 提供商中立的参考素材表达

扩展视频命令边界，使每个参考素材同时保留：

- 媒体类型。
- 公网 URL。
- 角色。

现有 `reference_images`、`reference_videos`、`reference_audios` 兼容字段继续保留，既有驱动的请求结构和限制统计不变。H3 驱动只读取结构化参考项；没有显式 role 的旧请求按以下兼容规则处理：

- 单张主图且没有其他参考素材：`first_frame`。
- `reference_image_urls`：`reference_image`。
- `reference_video_urls`：`reference_video`。
- `reference_audio_urls`：`reference_audio`。
- 新增的尾帧 URL：`last_frame`。

不得静默把超过上限的素材发送给供应商。平台在提交前返回可理解的 422 校验错误，并保留被拒绝的具体类别和数量，不记录敏感 URL 查询参数。

### 3. MiniMax H3 v2 驱动

新增内置驱动 `minimax_h3_video_v2`：

- `submit()` 把通用视频命令转换为 H3 `content[]`。
- 文本内容只包含最终 prompt，不附加 Ark CLI 风格参数。
- `duration`、`resolution`、`ratio` 位于请求顶层。
- 使用当前 MiniMax 连接的 Bearer API Key 和区域化 `base_url`。
- 验证 HTTP 状态、供应商业务错误和 `task_id`，只返回脱敏证据。
- `poll()` 调用 H3 v2 查询接口，并统一返回 pending、running、completed、failed 或 cancelled。
- 完成时返回 `video_url`、分辨率、时长、比例和脱敏 usage。

普通连接测试只验证配置完整性，不提交收费视频。真实可用状态必须来自用户明确触发的生成任务或单独的付费预检动作。

### 4. 模型目录与绑定

在 MiniMax provider 下增加 `MiniMax-H3` 视频模型，并声明：

- capability：`video_generation`、`text-to-video`、`image-to-video`、`reference-to-video`。
- driver：`minimax_h3_video_v2`。
- reference limits：图片 9、视频 3、音频 3、混合总数 12。
- 参数：4～15 秒、768P/2K、比例。
- 状态：配置后可选择，但未经过真实任务前不得展示为“已验证生成成功”。

既有默认 `shot_video` 绑定不自动切换到 H3。用户在模型中心显式设为默认或为任务绑定后，视频生成和工作流才使用 H3。

### 5. 提交与轮询数据流

生成流程：

1. 前端提交模型配置、prompt、时长、分辨率、比例和参考素材。
2. 后端解析当前绑定并执行通用预检。
3. 执行快照记录模型版本、driver key、脱敏参数和参考素材数量。
4. H3 驱动创建任务并返回 `task_id`。
5. `VideoJob.extra_data` 保存 provider、driver key、连接 ID、执行快照 ID和 H3 任务类型；不保存 API Key。
6. 前端或后台刷新按 job 中的 driver key 分发轮询，而不是固定调用 Ark SDK。
7. H3 成功后读取 `task.content.url`，通过现有媒体交付边界持久化远端 URL，并同步 Shot/Workflow 状态。
8. 失败或取消时记录脱敏原因并执行现有预算/任务收口逻辑。

轮询必须可在进程重启后恢复，不能依赖内存中的 `GenerationContext`。

### 6. 前端交互

模型中心和视频生成页只在选中 H3 时展示 H3 能力：

- 时长整数输入限制为 4～15。
- 分辨率选择 768P / 2K。
- 文生视频展示固定比例选择，禁止 `adaptive`。
- 选择首帧时比例显示为自适应。
- 可选尾帧输入。
- 显示参考图片、视频、音频数量和总数限制。
- 不展示未实现的 Context-IR、再生成或原生音频控制。

其他视频模型继续使用各自现有参数，不因 H3 接入改变默认值或可选项。

## 错误处理与安全

- API Key 只从已保存连接或单次请求读取，不进入日志、任务 extra_data、执行快照或错误正文。
- 供应商原始响应只允许提取状态码、错误类型和安全摘要。
- 网络超时、无 `task_id`、未知状态和成功但无 `content.url` 均作为明确失败处理，不伪造成功。
- 已受理但结果不明确的任务保持可恢复状态，不能自动重复提交并造成重复计费。
- 参考素材必须是供应商可访问的公网 URL，并继续经过现有媒体交付和生产引用安全门。

## 测试与验收

所有行为变化按测试驱动实施。验收至少包括：

1. H3 模型能进入规范视频目录并绑定 `shot_video`，但不会覆盖既有默认绑定。
2. 文生视频请求生成正确的 `/v2/video_generation` payload，prompt 不含 Ark 参数。
3. 首帧、尾帧及组合参考生成正确的 content type 与 role。
4. 4/15 秒边界通过，3/16 秒失败；768P/2K 通过，其他值失败。
5. 9/3/3 和混合 12 个素材边界通过，超限在供应商调用前失败。
6. 查询接口正确映射处理中、成功、失败和取消状态。
7. 成功任务把 `task.content.url` 写入 VideoJob，并同步关联 Shot/Workflow。
8. 进程重启后仍能根据持久化 driver 信息恢复轮询。
9. 模型中心和视频生成页能选择 H3，并只显示 H3 支持的参数。
10. 现有 Ark/Seedance、MiniMax 图片/TTS、视频模型目录和工作流回归测试继续通过。
11. TypeScript 检查、前端生产构建、后端目标测试和相关浏览器测试通过。

真实 MiniMax API 验收只在已有有效 Key、用户明确同意产生费用且设置最小可用时长后执行；否则以脱敏契约测试和请求快照作为交付证据，并明确标记“未做付费实模验证”。

## 发布与回滚

- 新驱动只会被明确绑定到 H3 的任务选择，不影响既有默认视频模型。
- 若 H3 接口异常，可在模型中心停用 H3 或把 `shot_video` 绑定切回原模型，无需迁移已存在的视频任务。
- 已提交的 H3 任务继续保留 provider、driver 和 snapshot 证据，回滚后仍可人工查询和处理。
- 不修改或删除历史 LLMConfig、VideoJob、Shot、Workflow 数据。
