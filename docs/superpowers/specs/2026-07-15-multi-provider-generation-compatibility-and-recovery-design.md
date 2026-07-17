# 多供应商生成兼容与人工恢复设计

## 1. 目标

在不削弱现有预算、审批、参考资产、模型新鲜度和零自动重试门禁的前提下，为文本、图像、TTS 和视频建立可扩展的模型契约、提示词适配和人工恢复机制；让工作台能够明确说明失败阶段、费用状态、可执行动作以及重新提交是否会产生新费用。

本设计采用“统一能力契约 + 能力内供应商适配器”方案。统一层只描述业务意图和可验证契约，不把图片、TTS、视频等不同协议强行伪装成同一种 HTTP 请求。

## 2. 当前事实与问题

### 2.1 已配置能力

当前 `sunqy` 用户的活跃配置可覆盖：

- 文本：MiniMax M2.7、MiniMax M3。
- 图像：MiniMax image-01。
- TTS：MiniMax speech-2.6-hd。
- 视频：火山 Seedance 1.5 Pro、阿里 HappyHorse 1.1 I2V/R2V/T2V。

代码可以为更多供应商提供兼容接口，但只有具备真实用户配置、通过服务端测试并完成实模调用的组合才能标记为“实模已验证”。

### 2.2 已确认缺口

1. MiniMax TTS 配置测试和生产 TTS 调用分别构造请求，存在模型、URL、声线、语言增强和输出参数漂移风险。2026-07-14 实模中配置测试成功，生产调用仍被供应商以 `2054` 拒绝。
2. 模型能力、参考限制和提示词选择分散在模型注册表、Prompt Skill、视频参考适配器和各供应商服务中，缺少一次生成可引用的统一契约快照。
3. 后端错误通常只有 `code/message`，前端只能显示一行错误；用户无法判断失败阶段、是否扣费、是否可以安全重试或应该先修改什么。
4. 现有工作台顶部成本和实模账本可能显示不同口径，导致图片已经记账但顶部仍显示 `¥0`。
5. 已有镜头、资产和批处理重试入口彼此独立，整书实模缺少“只恢复失败阶段”的安全入口。

## 3. 设计原则

- 供应商差异必须保留在能力适配器中，不能用一个万能请求掩盖协议差异。
- 配置测试和生产调用必须复用同一份请求契约构建器。
- 模型适配以 `provider_id + api_model_id + contract_version` 为身份，不只按展示名称判断。
- 提示词路由必须保存模板版本、路由原因和回退原因；通用回退不得被展示为专用适配。
- 付费请求默认不自动重试。只有供应商明确在受理前拒绝，才可展示“可安全重新提交”。
- `accepted`、`reserved` 或 `unknown_manual_reconcile` 状态只允许刷新或人工核对，禁止重新提交。
- 手工恢复只重做失败阶段，不能重新生成已经锁定且有效的参考资产。
- 所有公开错误和证据均使用允许字段；不返回 API Key、提示词正文、媒体原文或供应商原始响应。

## 4. 架构

### 4.1 模型执行契约

新增聚焦领域模块，拥有跨能力通用但不含供应商 SDK 的契约类型：

```text
backend/app/features/model_execution_contract/
├── domain.py
├── registry.py
└── public.py
```

核心快照 `ModelExecutionContract` 包含：

```python
provider_id: str
api_model_id: str
capability: Literal["text", "image", "tts", "video"]
contract_version: str
supported_inputs: tuple[str, ...]
response_mode: Literal["sync", "async", "sync_or_async"]
polling_mode: Literal["none", "provider_task", "operation_reconcile"]
prompt_profile: str
reference_limits: dict[str, int]
retry_policy: Literal["never", "confirmed_pre_acceptance_only", "status_poll_only"]
verification_status: Literal["verified", "experimental", "unverified"]
```

`registry.py` 从现有 `model_registry.py`、Seedance contract 和供应商能力定义组合快照，不复制模型目录。未知模型返回 `unverified` 的保守契约，不能自动获得多参考、自动重试或专用提示词能力。

### 4.2 能力请求构建器

供应商请求继续归属各能力适配器：

- 文本：现有文本服务根据输出合同构建 chat/JSON 请求。
- 图像：图像适配器负责比例、返回模式和异步结果解析。
- TTS：新增共享 MiniMax TTS 请求构建器，同时供配置测试和生产调用使用。
- 视频：继续由 `video_reference_adapter.py` 和工作流视频适配器负责参考内容和供应商负载。

共享 MiniMax TTS 请求接口：

```python
build_minimax_tts_request(
    *, model_id: str, text: str, voice_id: str, speed: float,
    output_format: str = "url", language_boost: str | None = None,
) -> MiniMaxTTSRequest
```

配置测试与生产调用只能消费该对象的 `url_path` 和 `payload`，不得再次手写同一请求字段。生产失败证据记录模型、声线、请求契约版本和字段集合，不记录文本或认证信息。

### 4.3 提示词自动适配

沿用 `prompt_template_router.py` 的唯一所有权，扩展调用约定而不是新建第二套路由器：

```python
select_prompt_skill_for_model(
    task=...,
    provider_name=contract.provider_id,
    model_id=contract.api_model_id,
    model_capabilities=[contract.capability, *contract.supported_inputs],
    output_contract=...,
    context=...,
)
```

每次生成持久化以下脱敏路由证据：

- `prompt_profile`
- `prompt_skill_id`
- `prompt_skill_version`
- `routing_reason`
- `fallback_reason`
- `model_contract_version`

文本、图像和视频各自拥有任务模板。TTS 不保存文本提示词，而保存语言、声线、发音策略和请求契约版本。没有专用模板时使用现有内部提示词，并在工作台显示“通用兼容模板”。

### 4.4 恢复动作契约

新增后端领域类型 `RecoveryDescriptor`：

```python
code: str
title: str
message: str
stage: str
provider_status_code: str | None
operation_status: str | None
cost_state: Literal["not_reserved", "released", "reserved", "spent", "unknown"]
safe_retry: bool
retry_requires_confirmation: bool
retry_scope: Literal["none", "status_only", "failed_stage", "shot"]
actions: tuple[RecoveryAction, ...]
```

允许的 `RecoveryAction.code`：

- `refresh_status`：只轮询已有任务，不重新提交。
- `retest_config`：重新测试当前模型及必要的声线/参考能力。
- `edit_voice`：返回声线选择区。
- `switch_config`：修改当前能力的模型配置并重新绑定。
- `retry_failed_stage`：只为明确未受理或明确失败的阶段创建新操作。
- `manual_reconcile`：展示 operation/task ID，要求人工核对。

恢复描述由后端生成。前端只负责展示和调用返回的动作，不重新实现安全判断。

### 4.5 整书实模恢复规则

整书运行增加只读恢复状态聚合和一个受控动作入口：

```text
GET  /series-runs/{run_id}/recovery
POST /series-runs/{run_id}/recovery/actions/{action_code}
```

动作请求必须包含目标 `operation_id` 或 `shot_id` 和当前模型绑定版本。服务端重新检查所有权、运行状态、预算、绑定新鲜度和操作状态。

- TTS `confirmed_rejected_before_acceptance`：可修改声线或配置后重试该镜头 TTS，再继续尚未提交的视频。
- 图片已经 `reconciled` 且参考资产锁定：恢复 TTS/视频时必须复用该资产。
- 视频或 TTS 已有 provider task：只允许刷新状态。
- 状态不明：只允许人工核对，不提供“重试”按钮。
- 切换模型后旧绑定快照失效，必须重新验证并生成新绑定版本。

本设计不引入后台自动重试队列。

## 5. 前端交互

在 `frontend/src/features/series-runs/` 增加独立的恢复展示组件，保持 `series-run-view.tsx` 不增长：

```text
components/recovery-card.tsx
hooks/use-series-run-recovery.ts
types/recovery.ts
```

恢复卡必须显示：

1. 失败阶段的中文名称。
2. 简短原因及供应商错误码。
3. 已完成阶段，例如“参考图已锁定，不会重新生成”。
4. 费用状态，例如“图片已记账 ¥1；本次 TTS 未受理，预留已释放”。
5. 每个按钮的影响：是否重新提交、是否可能产生费用、是否需要先修改配置。

危险动作使用两步确认，确认内容包含能力、镜头、预计新增费用和“不会重做”的阶段。`refresh_status` 不需要付费确认。

成本展示统一读取服务端 `spent_rmb/reserved_rmb/projected_increment_rmb`，不再优先展示可能过期的 `actual_rmb/projected_rmb`。

## 6. API 与数据兼容

- 保留现有生成、参考准备、绑定验证和媒体 API。
- 新恢复 API 和错误字段均为增量添加。
- 不修改既有状态字符串、历史操作或媒体任务。
- 恢复描述可首先放入现有 HTTP `detail`，再由恢复聚合接口读取持久化操作状态生成。
- 不新增数据库表；优先使用运行 metadata、provider operation 和既有任务表。若实现中证明无法满足并发安全，再单独设计 schema 变更，不在本批隐式增加。

## 7. 测试与验证

### 7.1 确定性契约测试

- 未知供应商/版本必须得到保守 `unverified` 契约。
- MiniMax M2.7/M3、image-01、speech-2.6-hd、Seedance 1.5 和 HappyHorse I2V/R2V/T2V 均产生稳定快照。
- MiniMax TTS 配置测试与生产调用生成相同字段集合、模型和声线。
- 每类模型的 Prompt Skill 路由记录专用或回退原因。
- 已受理/状态不明操作不能产生 `retry_failed_stage`。
- 明确提交前拒绝可以产生一次人工重试动作，但不会自动执行。
- 前端恢复卡对费用、阶段和动作进行可见断言。

### 7.2 实模验证

实模继续使用隔离数据库、`sunqy` 配置、七牛公网映射、总预算上限 `¥10`、两个跨集关键镜头和零自动重试。

执行顺序：

1. 从前端创建四章和整书计划。
2. 验证文本、图像、TTS、视频绑定快照及 Prompt 路由证据。
3. 生成并锁定复合参考图；已有有效参考图不得因后续失败重复生成。
4. TTS 先行；若明确拒绝，验证恢复卡，不自动重试。
5. 只有 TTS 成功后才提交两个视频任务。
6. 视频完成后验证人物、场景道具、事件、风格、配音和交付六维证据。

HappyHorse 可做确定性契约与配置验证；只有用户另行提供该轮费用授权并且配置通过新鲜度门禁时才执行额外实模视频，不继承本轮两个 Seedance 镜头的预算。

## 8. 验收标准

- 四种能力都能生成含供应商、模型版本和契约版本的快照。
- 配置测试和正式 MiniMax TTS 不再拥有两份请求构造逻辑。
- 每次提示词选择都有专用或回退证据，且前端可见。
- 任何阻塞都显示中文阶段、原因、费用状态和允许动作。
- 用户能安全刷新未知任务，或在明确未受理后修改配置/声线并只重试失败阶段。
- 不存在自动付费重试；状态不明不会出现重新提交按钮。
- 顶部成本与服务端实模账本一致。
- 确定性回归、类型检查、构建和前端浏览器验收通过后，才允许重新进入实模。

## 9. 范围外事项

- 不在本批新增新的供应商账号或 API Key。
- 不宣称没有真实配置的文本、图像或 TTS 供应商已通过实模。
- 不实现跨供应商自动降级或自动选择最便宜模型。
- 不实现无限重试、后台自动重试或绕过预算门禁。
- 不扩展六镜头 Wave 2。
- 不顺带重构现有大型模型目录、工作流路由或资产生成服务。

## 10. 回滚与安全

- 新契约和恢复字段均为增量；移除新调用即可恢复原生成路径。
- 共享 TTS 请求构建器上线前用刻画测试锁定现有配置测试与生产负载。
- 恢复动作每次重新校验 operation 状态，避免并发点击产生重复提交。
- 所有实模失败继续先导出脱敏证据，再清理隔离数据库。
