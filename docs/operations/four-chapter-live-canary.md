# 四章动漫实模 Wave 1 操作手册

状态：Task 9 Wave 1；Wave 2 永久默认关闭。

## 安全边界

- 唯一目标库：`/tmp/ai-video-platform-four-chapter.db`，权限 `0600`。
- 源库必须先复制到另一个 `/tmp/*.db`；runner 拒绝直接读取仓库开发库。
- 只允许四个固定模型配置 ID：MM-M3、image-01、豆包语音 Seed-TTS 2.0、Seedance 1.5 Pro。
- 只允许七牛 Kodo 存储配置 `0e8091db-0d9c-4e12-9ae7-7ff26e42f03c`；实模参考图必须先持久化并上传七牛，再把签名公网 URL 交给视频模型。
- MiniMax 参考图请求使用供应商当前稳定支持的 URL 返回；该 URL 必须立即下载到本地、再上传七牛，最终只允许绑定七牛公网 URL，不得把供应商临时 URL 直接绑定为视频参考资产。
- 每次图像响应只保存 `image-provider-response-shape-v1` 结构证据（任务 ID 是否存在、URL/base64 数量、成功/失败计数、状态码和消息哈希），禁止保存原始 URL、base64、提示词、消息正文或认证信息。
- 实模清单使用 `model-execution-evidence-v1`：每个 text/image/tts/video 绑定必须记录 `contract_version`、`prompt_profile`、`verification_status` 和 `routing_mode`，不得记录提示词正文。
- 暂存脚本只输出非敏感 ID、数量和哈希；不得查询、解密或打印 API key。
- 服务端预算固定 RMB 10、2 个跨集关键镜头。预算在每次 provider 提交前预留，前端数字不是授权来源。
- 六镜头 Wave 2 不接受本次预算继承；runner 会直接拒绝 `ANCHOR_COUNT=6`。

## 前置核验

1. 确认 Task 8 全部确定性验收通过。
2. 只读记录开发库文件大小以及 `users/novels/chapters/llm_configs/series_production_runs/media_generation_jobs` 行数。
3. 从前端配置页重新测试 `sunqy-volcano-seed-tts-2-0`；必须走 OpenSpeech V3、资源 `seed-tts-2.0`，并以安全声线 `zh_female_vv_uranus_bigtts` 生成真实音频。测试失败即停止，不得进入图片或视频生成。
4. 用不包含密钥的联表查询确认四个模型配置与指定七牛配置同属 sunqy、active、test_status=success；TTS `test_message` 必须是 `豆包语音 V3 连接成功`，七牛 bucket 和公网映射完整。
5. 复制开发库到 `/tmp/ai-video-platform-four-chapter-source.db` 并设为 `0600`。
6. 运行静态 gate、runner 单测、typecheck。任何失败都禁止 live。
7. 确认 runner 输出 `实模 provider fake：已关闭`，且浏览器探针访问确定性 setup 路由得到 404。任何 deterministic job 都是失败，不是实模证据。

## Wave 1 命令

```bash
cp backend/ai_video.db /tmp/ai-video-platform-four-chapter-source.db
chmod 600 /tmp/ai-video-platform-four-chapter-source.db

PRODUCTION_OS_LIVE=1 \
PRODUCTION_OS_LIVE_REQUIRED=1 \
PRODUCTION_OS_LIVE_MAX_RMB=10 \
PRODUCTION_OS_LIVE_ANCHOR_COUNT=2 \
FOUR_CHAPTER_LIVE_SOURCE_DB=/tmp/ai-video-platform-four-chapter-source.db \
FOUR_CHAPTER_LIVE_SOURCE_USER_ID=56ae84de-951f-4e74-ac79-3550d6f6f3b2 \
npm run verify:four-chapter:live
```

浏览器必须可见地完成：创建四章 → 生成整书计划 → 整书自动制作 → 启用实模验证 → 四个服务端配置测试 → 服务端 binding validate → 两个不同集关键镜头 → 生成所选关键镜头。禁止用直接 API 生成替代最后一步。

## 失败关闭条件

以下任一项出现即报告 `阻塞` 或 `失败`，不得重试已可能提交的付费请求：

- 配置缺失、模型名不符、测试失败或超过 900 秒新鲜度；
- Story Bible、状态机、人物/场景/道具资产、角色声音未锁定；
- 两个推荐镜头不跨集；
- 预算预留失败、实际金额超限或 provider 接受状态不确定；
- 对话镜头缺 TTS/voice binding；
- 缺 image/reference、video、provider task ID、模型快照、artifact URL；
- 参考图未经过七牛对象上传、签名公网 URL 缺失或签名已过期；
- MiniMax 返回生成 `id` 但没有图片时，必须绑定该 ID、保留预算并停止后续视频提交；官方没有图像状态查询接口时禁止伪造轮询或自动重新提交。
- 评价不是新生成、不是 artifact-bound、六维不齐或任一 blocking；
- 媒体不可访问、超时或临时库污染开发库。
- 暂存库 schema 与当前 ORM 不一致；尤其 provider operation 的恢复/成本/产物字段缺失。
- 豆包语音实模声线固定使用已验证的 `zh_female_vv_uranus_bigtts`；运行时必须与前端连接测试一样把 `app_id` 和 `resource_id=seed-tts-2.0` 装配到 OpenSpeech V3 地址。仅有旧测试时间或裸 `base_url` 都不得进入 Wave 1。
- `separate_video_tts` 必须先提交 TTS；TTS 被明确拒绝时禁止提交该镜头的视频任务。
- TTS 明确拒绝后，工作台必须显示“声音生成未受理”、费用预留已释放、参考图继续锁定，以及修改声线/重新测试/仅重试失败阶段入口；本轮仍判定为实模未闭环并停止，禁止自动点击重试。

## 证据与清理

允许保留在 runner 打印的仓库外 `/tmp/...output...` 目录中的：页面截图、redacted manifest、`failure-evidence.json`、非敏感任务/配置/模型/供应商 ID、artifact URL、时间、成本和评分。失败证据必须在删除隔离库前生成，严禁 trace/localStorage/header/API key、提示词或原始媒体内容。

运行结束后：

```bash
rm -f /tmp/ai-video-platform-four-chapter.db
rm -f /tmp/ai-video-platform-four-chapter-source.db
```

最后再次只读比对开发库文件大小与受保护表行数，并确认 `frontend/tsconfig.json` 没有新增漂移。

## 2026-07-15 实模结果

- 运行 `b9403b6e-aa7e-4021-a66a-275d53a3cdcf` 从前端完成四章创建、整书计划、故事锁、两个跨章关键镜头选择和复合参考图生成。
- 参考图 provider task `06a61a0e6729bc641f194e1b6a5995a3` 已结算，资产 `3a17a8dd-f8f7-4b3d-bf5a-b7c7b4118cb2` 经七牛上传后的公网 URL 回读、图片解码和布局校验后锁定；布局分数 `1.00`，阈值 `0.75`，实际费用 RMB 1.00。
- MiniMax TTS 在供应商受理前明确拒绝；RMB 0.50 预留已释放，恢复状态为 `confirmed_rejected_before_acceptance`，安全恢复范围仅为 `failed_stage`。
- 前端已显示“声音生成未受理”、修改声线、重新测试声音模型、修改后重试失败阶段和“参考图已锁定，不会重新生成”。
- 视频提交数为 0，视频费用为 0；因此本轮证明失败关闭与恢复闭环，但不构成两个实模视频和六维语义一致性通过证据。按授权要求未自动重试。
- 脱敏证据位于本次 runner 输出目录中的 `failure-evidence.json`、`tts-fail-closed-evidence.json` 和 `04-tts-fail-closed-recovery.png`；不含密钥、提示词正文和公网签名 URL。

## 2026-07-16 豆包语音 2.0 实模结果

- 运行 `5441ddad-9dea-44d1-b9c4-8f14c0ec95a2` 从前端创建四章，完成整书计划、故事锁、两个跨章关键镜头与复合参考图；参考图布局分 `0.751964`，阈值 `0.75`，经七牛配置 `0e8091db-0d9c-4e12-9ae7-7ff26e42f03c` 持久化并锁定。
- TTS 明确绑定 `sunqy-volcano-seed-tts-2-0 / volcano / seed-tts-2.0 / volcano.seed_tts.v3.v1`，安全声线为 `zh_female_vv_uranus_bigtts`；两个真实音频任务均成功并有音频产物。
- 两个 Seedance 视频任务 `cgt-20260716222529-fkzws`、`cgt-20260716222535-6csqf` 均成功并有视频产物；供应商提交次数各为一次，失败后重提次数为零。
- 实模发现视频状态刷新错误复用了 Volcano 的默认 TTS 地址。刷新现已按任务保存的 `model_config_id` 解析 Seedance Key 与 base URL；已有任务只做状态查询，没有重新生成。
- Seedance 成功状态未返回实际费用时，服务端按已预留的可信估算结算并标记 `estimated_as_actual`。本轮账本为已花费 RMB 9.00、预留 RMB 0.00，未超过服务端 RMB 10 上限。
- 前端恢复验收观察到一次 `reconcile-selected=completed`、两个聚合产物成功、`generate-selected` 调用为零、视频刷新调用为零；证据位于 `/tmp/ai-video-platform-four-chapter-output-20260716-doubao-recovery/`。
- 当前两个产物仍标记 `trusted_multimodal_evaluation_required`，因此只能确认链路、模型绑定、资产/声音/视频产物和结构一致性；尚不能把画风、人物、场景、道具、事件、配音语义与故事六维一致性宣称为可信评审通过。
