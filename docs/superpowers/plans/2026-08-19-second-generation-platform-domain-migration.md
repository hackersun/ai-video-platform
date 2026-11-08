# 二代平台分域迁移实施计划

**Goal:** 在保持现有业务、历史数据、付费供应商任务、媒体产物和外部 API 兼容的前提下，将现有 FastAPI 平台逐域迁移为“Spring 企业控制面 + Python AI/媒体执行面”，并形成可审计、可回滚、可工业验收的二代平台。

**Architecture:** 采用绞杀者模式。Gateway 按域、租户、项目或任务创建时间路由；源系统、新系统的同一业务聚合在任一时刻只有一个写入者；使用 Outbox/CDC、影子读、幂等回填和差异核验完成切换。长业务流程由 Flowable 管理，异步执行由 Kafka 和持久任务状态机管理，XXL-JOB 只触发定时对账/补查/夜间批次/资产备份编排/归档，不直接执行 GPU 或备份数据面。

**Tech Stack:** React/Next.js、Spring Cloud Alibaba、Spring Boot、Spring Cloud Gateway、Nacos、MySQL 8、Redis、Milvus、MinIO/S3、Flowable、XXL-JOB、Kafka、Spark、Python/FastAPI/PyTorch/Hugging Face、FFmpeg、Docker/Kubernetes、OpenTelemetry、Prometheus/Grafana。

**Spec:** `docs/superpowers/specs/2026-08-19-second-generation-platform-architecture-design.md`

## Global Constraints

- 本文是**迁移项目总计划**，不是一个可直接批量编码的巨型任务。
- 每个领域进入实现前，必须生成本文第 17 章所列独立子计划；子计划必须包含准确文件、接口、Schema、失败测试、最小实现步骤、验证命令和提交边界。
- 任何实现都必须重新读取正式总体架构、最新 `AGENTS.md`、相关治理文档、当前代码、数据库画像和运行基线。
- 所有行为变化先有失败测试或正式批准的例外；结构迁移与行为变化分批。
- 不执行大爆炸替换；不允许同一聚合长期双写；不重新提交供应商已受理的付费任务。
- `/api/v1` 在兼容期保持路径、ID、主要字段、状态和错误语义；只有批准的语义变化才新增 `/api/v2`。
- 历史合同、成功 Attempt、账务流水、审计和媒体证据不覆盖、不删除；通过新版本、冲正或补偿表达变化。
- 未通过数据备份/恢复、契约、幂等副作用、安全、运行和回滚门禁的领域不得接管生产写入。
- `BD-001` 至 `BD-013` 的合同阻断决策沿用总体架构；技术计划不得擅自把 20 日解释为完整重构验收，也不得自行决定五项投标演示的提交时点。

---

## 0. 文档控制

> 文档状态：送审稿（V0.95）
> 现状基线日期：2026-08-19
> 本次修订日期：2026-08-20
> 现有工程基线：`main@9a3c8bfb`
> 需求文件 SHA-256：`52ae0db5b5010a867a766de27cb4f5ddf3b7c5c7f7b32a9bafc5a99fd4a5bbd5`
> 对应总体设计：V0.95
> 计划类型：Program Master Plan（分域迁移总计划）

### 0.1 生效条件

本计划只有在下列条件满足后才能进入 W1 生产实施：

1. 总体架构升级为实施基线；
2. 20 日、6 个月、12 个月、付款、SLA 和 IP 边界获得书面澄清；
3. Kafka/RocketMQ、Milvus/Chroma 及 Java/Python 边界 ADR 获批；
4. 生产数据库、对象存储、供应商任务和背景 IP 的只读盘点完成；
5. 采购方提供验收数据、质量阈值、GPU/部署条件和验收责任人；
6. W0 备份恢复、契约金标和第一批数据 Dry-run 通过。
7. 完整采购文件（含被引用的第五章符合性审查）、演示提交规则、交付地点和现场条件已登记；
8. 48.5 万元对应的范围、甲供资源、第三方/OPEX、排除项和变更计价已形成签署矩阵。

### 0.2 意图锁定

架构最终完全按合同目标重建，但执行过程保护已有成果和用户连续性；以可独立验收的业务域逐项替换旧系统，而不是以代码目录搬迁作为进度。

### 0.3 明确不做

- 不先创建全部微服务空壳后再寻找业务边界；
- 不机械翻译 FastAPI endpoint；
- 不让 Java 和 Python 共享业务数据库写权限；
- 不用 Redis、Flowable 或 XXL-JOB 代替持久任务队列；
- 不把本地脏数据整库导入 MySQL；
- 不在影子环境触发模型费用、供应商提交、通知或删除；
- 不用前端路由回滚掩盖已经切换的数据所有权；
- 不把演示录像、页面存在或测试全绿写成工业验收结论。

### 0.4 修订记录与本次深化边界

| 版本 | 日期 | 主要内容 | 状态 |
|---|---|---|---|
| V0.9 | 2026-08-19 | 建立 D00—D15、W0—W6、G0—G8、切换/回滚和资源 ROM 总计划 | 首次送审 |
| V0.95 | 2026-08-20 | 深化实施基线/IMS、Domain/DEL/Reuse、DM/CW状态与恢复、环境晋级、DoR/DoD、资源/依赖、治理、TEST/EVID、ORR和阶段验收包 | 本次送审 |

V0.95 仍是 Program Master Plan，不替代第 17 章要求的领域子计划，也不授权生产写入、外部付费调用、数据删除或正式交付。所有新增周期、门禁窗口和资源分配均需在对应子计划、变更单及合同决策中再次锁定。

### 0.5 实施基线关闭登记

V0.95 保留送审状态。升级 V1.0 前必须把所有生效条件实例化到以下登记；空白“待定”不视为关闭：

| BASE-ID | 条件/BD/ADR | Owner | Approver | 截止日期 | 影响 WP/Gate | 证据 URI/hash | 决策/生效日 | 状态 |
|---|---|---|---|---|---|---|---|---|
| BASE-CONTRACT | BD-001—013、完整采购文件和阶段/演示解释 | PM/LEGAL | PO | W0 锁定 | 全部/MS-20D/MS-06M/MS-12M | 待 W0 建立 | 待签 | OPEN |
| BASE-ARCH | ADR-001—025、总体架构和所有权 | ARCH | 架构委员会/PO | W1 前 | D00—D15/G1 | 待建立 | 待批 | OPEN |
| BASE-DATA | 生产数据/媒体/Provider/Secret 画像和 A/B/C/D | DATA_OWNER | PO/SEC/LEGAL | 首批回填前 | DM/CW/G0/G2 | 待建立 | 待批 | OPEN |
| BASE-ACCEPT | 数据集、指标、阈值、证据、验收/整改/签署 SLA | QA/PO | PO | 对应包冻结前 | G7/各 PKG | 待建立 | 待签 | OPEN |
| BASE-RESOURCE | 人员、环境、GPU、Provider 配额、预算和场地网络 | PM/SRE | PO/FIN | 对应 WP 开始前 | IMS/所有波次 | 待建立 | 待批 | OPEN |

### 0.6 时间、里程碑与计划假设

- `C0` 是合同生效日，★20 日义务从 C0 起算，技术计划不得改写；`T0` 是双方批准的实施开工日/Notice to Proceed，只用于 IMS 排期。若两者不同，差异及责任必须由 BD-001/013 书面处理；
- “6个月/12个月”按书面确认的起算日加日历月计算，不能用“26周/52周”自动替代；周数仅作资源窗口；
- 开发人日按 5×8 工作制和法定节假日日历，7×24/SLA 使用独立服务日历；
- 计划基线必须写入具体日期、节假日、采购方反馈/UAT SLA 和缓冲。未签署前可暂按文档完整性检查 3 个工作日、UAT 5 个工作日、整改/复验各 5 个工作日建模，但这些只是排期假设；
- 里程碑统一使用 `MS-*`，月份使用 `Month-*`，避免与原 M2—M8/月份混用。文中旧称在 V1.0 IMS 冻结时一次性映射，不改变其业务含义。

---

## 1. 成功标准

迁移完成必须同时满足：

1. 经完整采购文件/合同确认纳入验收的技术组件不是空壳，真实参与至少一条生产链；第五章未取得前不得自行扩大“合同强制”范围；
2. 核心业务由新控制面拥有，旧 FastAPI 不再接收生产写流量；
3. `/api/v1` 兼容层在约定周期内服务旧前端/外部调用方，破坏性差异为零或均有批准；
4. 经批准迁移范围内的 A 级及修复复核后的 B 级关键 ID、租户归属、金额、合同、媒体哈希和任务血缘 100% 核对；C 级归档、D 级冻结不计入生产迁移分母；
5. 同一幂等键只有一个有效付费提交和一个有效定稿结果；
6. Worker/K8s/数据库/Kafka/对象存储故障均完成恢复演练；
7. 占位质量逻辑不再参与生产放行；质量阈值有金标和双方签署口径；
8. 五项业务演示在 BD-011 确认的提交时点完成，并与 60 批/1200 分钟、性能、安全和 SLA 分别形成原始证据；
9. 前端核心用户流程全部经过新后端，页面不复制服务端业务规则；
10. 旧写路径在两个稳定发布周期后退役，历史查询、归档和法律保留仍可用；
11. 源码、构建、部署、数据字典、SBOM、权利台账、Runbook、培训和验收材料完整移交；
12. 所有未关闭风险均有书面接受主体，不能以“已知问题”代替验收。

---

## 2. 迁移原则

### 2.1 十条不可突破的规则

1. 按领域和租户/项目切换，不进行全量大爆炸替换。
2. 同一业务聚合始终只有一个写入者。
3. 允许双读、影子投影和异步复制，禁止长期应用层双写。
4. 外部 V1 契约兼容，新内部模型通过 Gateway/BFF 适配。
5. 业务表与 Outbox 同一 MySQL 事务；消费者使用 Inbox 幂等。
6. 已受理付费任务只接管查询和对账，禁止因迁移再次提交。
7. 数据库使用 Expand—Migrate—Contract；Schema、回填和行为变化分批。
8. 锁定内容、生产合同、模型快照、财务和审计只追加版本或冲正。
9. 媒体先复制、校验、切引用；至少两个发布周期后才可归档源对象。
10. 每域完成刻画、影子、切换、观察、回滚演练和退出门禁后才能停止旧写。

### 2.2 通用领域迁移循环

```mermaid
flowchart LR
    A[现状刻画与金标] --> B[OpenAPI/事件/数据合同]
    B --> C[幂等Dry-run回填]
    C --> D[变更追平与影子读]
    D --> E[短暂停写和零差异核验]
    E --> F[Gateway原子切换单写者]
    F --> G[灰度观察与恢复演练]
    G --> H[旧写退役/只读归档]
```

每域均使用以下灰度：内部租户 → 1% → 5% → 25% → 50% → 100%。比例可按项目数或业务量计算，但必须在子计划中明确分母。涉及付费任务的域优先按“任务创建时间 + execution_backend”切分，不把同一任务跨引擎迁移执行。

---

## 3. 目标领域与依赖

```text
D00 平台基础、契约与迁移工厂
 ├── D01 IAM、组织、工作区、RBAC
 │    └── D02 项目、小说、章节、剧本
 │          └── D03 Production Bible、实体、状态与审批
 ├── D04 资产、媒体、版权血缘
 ├── D05 模型工厂、Prompt、绑定与认证
 └── D06 持久任务、Kafka、GPU资源

D02 + D03 + D04 + D05
 └── D07 分镜、镜头与不可变生产合同
       └── D08 Flowable生产流程与人工门禁

D05 + D06 + D07
 ├── D09 Python AI执行器与供应商适配
 ├── D10 声音、TTS、字幕与强制对齐
 └── D11 一致性质检、缺陷与定向修复

D04 + D07 + D10 + D11
 └── D12 时间线、FFmpeg渲染与交付

D01 + D05 + D06
 └── D13 预算、用量、成本、额度与对账

所有领域
 ├── D14 审计、指标、告警与SLA
 └── D15 Gateway/BFF及前端兼容迁移
```

Flowable 只管理阶段和人工任务；Kafka 管理事件/执行命令；XXL-JOB 管理补查/对账/夜间批次触发/资产备份编排/归档；Redis 只做缓存、限流、会话和心跳加速；Python Worker 不拥有企业业务真相。

波次中的周数是资源容量窗口，不是下游领域的自动开工授权。前置域达到 `CR/RR` 后，下游可以并行开展合同、读模型、适配和影子工作；只有前置域达到该切换单规定的 `WR/EX`、接口/事件 Schema 已发布且恢复演练通过后，下游才可接管生产写入或不可逆副作用。否则即使日历已到也必须等待。真实依赖拆分如下：

- 主内容链：`D00 → D01 → D02 → D03 → D07 → D08`；
- 并行基础支线：D00 后并行建设 D04、D05、D06，但它们各自仍须通过退出门；
- 执行汇合：`D05 + D06 + D07 → D09`；声音和质量支线为 `D05 + D06 + D07 → D10/D11`；
- 交付汇合：`D04 + D07 + D10 + D11 → D12 → 工业验收`；
- 横向前置：D13 的最小预算/流水切片、D14 的最小审计/Trace 切片必须在任何真实付费流量前上线，D15 贯穿各域兼容切换。

### 3.1 受控数据所有权矩阵

| 域 | 唯一事实/目标写入者 | 明确不拥有 |
|---|---|---|
| D00 | 契约版本、迁移批次、核对结果和平台级幂等基础；对应平台/迁移组件 | 用户、内容、任务、资产和财务业务事实 |
| D01 | 用户、组织、工作区、成员、会话、角色和权限；`iam-service` | 项目内容、媒体和任务状态 |
| D02 | 项目、作品、章节/剧本版本和导入事实；`creative-domain-service` | Bible、流程任务和资产二进制 |
| D03 | Bible、实体、内容审批结果、状态、证据和语义影响图；`creative-domain-service` | Flowable 人工任务和运行时阶段状态 |
| D04 | 资产元数据、对象 Manifest、版权/同意、保留/删除事实；`asset-service` | 生成任务、质量结论和财务流水 |
| D05 | 模型/制品、Prompt/配方、能力绑定、认证、Voice Profile 和执行快照；`model-factory-service` | Job/Attempt 和媒体对象 |
| D06 | Job、Attempt、租约、Worker/GPU、供应商操作状态和 `reservation_id` 引用；`execution-control-service` | 预算余额、预留/结算流水和供应商成本账务 |
| D07 | Storyboard、Shot、Episode/Shot Contract 及合同依赖/失效；`creative-domain-service` | 流程实例和执行 Attempt |
| D08 | Flowable 定义/实例、人工任务、阶段决策和运行时流程依赖；`production-orchestrator` | 内容审批事实、任务进度和财务 |
| D09 | 无企业业务真相；Worker 只产生签名 Result Manifest 和执行证据 | 所有 Java 业务主表 |
| D10 | 跨域能力：Voice Profile 由 D05 写，音频对象由 D04 写，对齐合同/结果由 D11 写；不新增共享数据库写者 | 角色内容、Job 和财务 |
| D11 | 质量策略、检测结果、缺陷、人工金标、修复决策和对齐结果；`quality-delivery-service` | 原始媒体对象和执行 Attempt |
| D12 | Timeline、渲染/交付合同、交付包及其状态；`quality-delivery-service` | 资产对象本体和账务流水 |
| D13 | 预算、额度、预留、结算、释放、退款、冲正、Usage 和供应商成本对账；`usage-audit-report-service` | Job 调度状态和 Provider 轮询状态 |
| D14 | 追加审计事实、SLA 证据和报表定义；`usage-audit-report-service`。Prometheus/日志平台拥有运行遥测，不反写业务状态 | 任何上游业务聚合 |
| D15 | 无业务真相；Gateway/BFF/前端只路由、适配和展示 | 所有领域数据库和服务端业务规则 |

内容审批完成采用两步可追溯语义：D08 拥有人工作业完成事实并发事件，D03 在自身事务中验证版本后写内容审批/发布事实。语义影响图归 D03/D07 的内容合同边界；Flowable 只保存运行时流程依赖。

### 3.2 切换控制矩阵

| 域组 | 切换键 | 影子比较 | 在途规则/不可逆点 | 回滚负责人 |
|---|---|---|---|---|
| D01 | tenant | 权限判定、资源集合、会话状态 | 首个新 IAM 写入后默认只前向修复 | IAM Lead + SEC |
| D02/D03/D07 | project/novel/run | ID、版本、哈希、状态、V1 响应 | 已发布新合同不可覆盖；必要时反投影兼容读模型 | Creative Lead + DATA |
| D04 | project/object manifest | 对象大小/哈希/权利/引用 | 切引用前可回退；新权利/删除事实只前向修复 | Asset Lead + DATA_OWNER |
| D05 | tenant + capability | 绑定解析、认证、快照哈希 | 已创建任务固定旧快照；新绑定可回退 | Model Lead |
| D06/D09 | task_created_at + execution_backend | 状态、Attempt、Provider ID、Manifest、费用引用 | Provider 已受理后只允许接管/对账；不得重提 | Execution Lead + Provider Owner |
| D08 | process definition/version | 流程阶段、人工任务和业务键 | 进行中实例固定版本；新实例切换 | Orchestrator Lead |
| D10/D11/D12 | pipeline/quality/renderer version + run | 对齐、质量、时间线、成片哈希 | 已交付/已成功产物不覆盖；质量修复通过新 Repair Job+Attempt，交付通过新 Delivery | Quality/Media Lead |
| D13 | tenant/project + ledger epoch | 余额、预留、结算、退款和账单总额 | 首笔新流水后只允许前向修复/冲正 | FIN + Ledger Lead |
| D14 | service/tenant + audit epoch | Trace 完整率、审计数量/哈希 | 首条新审计后不得删除或反写 | SEC + Audit Lead |
| D15 | API/tenant/project feature flag | V1 响应、E2E、页面行为 | UI 可回退但不改变后端写入所有权 | FE Lead + Gateway Lead |

每个子计划必须把本矩阵展开为源表/目标表、Schema、数据库账号、服务端写栅栏、比较键/容差、反投影工具、首次新写后的 no-return 决策和审批人。

### 3.3 Domain Master Register

每个域必须依次达到 `CR（Contract Ready）→ RR（Read Model Ready）→ SR（Shadow Ready）→ WR（Write/Cutover Ready）→ EX（Domain Exit）`。同一日历波次内的下游域只能在前置 `CR/RR` 后做合同或影子工作，前置域未到 `WR/EX` 时不得接管生产写入。

| 域 | 入口依赖/DoR | 主交付物 | 复用策略 | 迁移/切换 | 恢复/no-return | 环境与证据 | Lead/ROM人日 | EX 后解锁 |
|---|---|---|---|---|---|---|---:|---|
| D00 | BASE-CONTRACT/ARCH；环境/网络 | DEL-D00 平台、契约、迁移工厂 | 适配 CI/Compose/治理 | DM-00；无生产CW | R1；无业务新写 | Staging；TEST-CONTRACT+TEST-DR-PLATFORM-MIN/EVID-D00；完整TEST-DR留最终ORR | SRE/ARCH，160—240 | 所有域 CR |
| D01 | D00-CR；身份/IP/安全基线 | DEL-D01 IAM/组织/会话/权限 | 语义复用用户/角色，控制面重写 | DM-01/CW-01，tenant | R3；首个新 IAM 写 | PreProd；TEST-IAM-SEC+TEST-DATA-6M/EVID-D01 | IAM/SEC，120—180 | D02、D13、D15 |
| D02 | D01-CR；内容契约/金标 | DEL-D02 项目/作品/剧本/导入 | 语义/UUID/测试适配复用 | DM-02/CW-02，project | R2；发布新内容版本后前向 | PreProd；TEST-CONTRACT+TEST-DATA-6M/EVID-D02 | Creative，100—140 | D03/D07 |
| D03 | D02-RR；Bible/审批基线 | DEL-D03 Bible/实体/影响图 | 语义/数据/测试适配复用，热点不搬 | DM-02/CW-02，project/run | R2/R3；新快照锁定不覆盖 | PreProd；TEST-CONTRACT+TEST-DATA-6M/EVID-D03 | Creative，120—180 | D07 |
| D04 | D00-CR；对象/权利/Secret画像 | DEL-D04 Asset/Manifest/版权 | 媒体复制+模型语义复用 | DM-03/CW-03，manifest | 切引用前R2；权利/删除R3 | PreProd；TEST-ASSET-MANIFEST+TEST-DATA-6M/EVID-D04 | Asset/DATA，160—240 | D07/D11/D12 |
| D05 | D00-CR；模型/IP/凭据基线 | DEL-D05 模型/Prompt/训练/快照 | Python驱动/Prompt适配复用 | DM-04/CW-03，tenant+capability | 绑定R1；任务快照R3 | PreProd+Canary；TEST-CONTRACT/EVID-D05 | Model/PY，160—240 | D07/D09/D10/D13 |
| D06 | D00-EX；D13-MIN/D14-MIN合同 | DEL-D06 Job/Attempt/ProviderOperation+Epoch/GPU | 任务语义复用，进程队列重写 | DM-05/CW-04，created_at+backend | 未外呼R1；受理后R3 | PreProd故障；TEST-PROVIDER-5W+TEST-DR-FIN-MIN/EVID-D06；全状态TEST-DR留最终ORR | Execution，240—360 | D09/D10/D11 |
| D07 | D02/03/04/05-CR或RR | DEL-D07 分镜/镜头/不可变合同 | 字段/UUID/血缘适配复用 | DM-02/CW-02，run/episode | R2/R3；锁定合同不覆盖 | PreProd；TEST-CONTRACT+TEST-DATA-6M/EVID-D07 | Creative，100—140 | D08/D09/D10/D11/D12 |
| D08 | D07-CR；Flowable职责ADR | DEL-D08 BPMN/人审/阶段/补偿 | 流程语义复用，运行时重建 | 无DM/CW-05，process version | R3；实例固定定义 | PreProd；TEST-CONTRACT/EVID-D08 | Orchestrator，80—120 | 生产主链 |
| D09 | D05/06/07-CR；Provider能力矩阵 | DEL-D09 Python Adapter/Worker/接管 | 驱动直接/适配复用 | DM-05/CW-04，task backend | Provider受理后R3 | Sandbox/PreProd/Canary；TEST-PROVIDER-5W/EVID-D09 | PY/Provider，100—160 | 真实生成 |
| D10 | D05/06/07-CR；授权声音金标 | DEL-D10 情感TTS/四轨对齐 | TTS/音频适配复用 | DM-06/CW-06，voice/pipeline | R2/R3；音频版本不覆盖 | PreProd；TEST-AUDIO/EVID-D10 | Audio/PY，120—180 | D12 |
| D11 | D04/06/07-CR；盲测/阈值 | DEL-D11 质检/校准/修复 | 报告语义复用，占位检测淘汰 | DM-06/CW-06，quality version | R2/R3；修复新Repair Job+Attempt | PreProd；TEST-QUALITY/EVID-D11 | CV/Quality，220—340 | D12/G7 |
| D12 | D04/07/10/11-SR；Golden | DEL-D12 自动剪辑/Timeline/渲染/交付 | FFmpeg基础适配，复杂编译新建 | DM-06/CW-06，renderer/run | R2/R3；交付包不覆盖 | PreProd；TEST-AUTOEDIT/EVID-D12 | Media，180—280 | 工业验证 |
| D13 | D01/05/06-CR；财务口径 | DEL-D13 预算/Ledger/Usage/对账 | 账务事实新建，历史只核对迁移 | DM-05/CW-04+CW-07，ledger epoch | R3；首笔流水后只冲正 | PreProd；TEST-PROVIDER-5W+TEST-DATA-6M/EVID-D13 | FIN/Ledger，100—160 | 付费Canary/报表 |
| D14 | D00-CR；审计/指标定义 | DEL-D14 Audit/Trace/SLA/报告 | 日志/报告适配，审计真相新建 | DM-07/CW-07，audit epoch | R3；追加事实不删除 | 全环境；TEST-IAM-SEC+TEST-DR/EVID-D14 | SEC/SRE，120—180 | 所有生产写/验收 |
| D15 | D00-CR + 每域 OpenAPI | DEL-D15 Gateway/BFF/前端兼容/UI等效性 | React/UI/E2E直接或适配复用 | 无DM/CW-08，API/feature flag | R1路由；不回退写所有权 | CI/PreProd/Prod；TEST-CONTRACT+TEST-UI-STACK+TEST-UAT-ORR；EVID-D15-UI-MIN@MS-06M、EVID-D15@EX | FE/Gateway，180—260 | 用户流量/旧入口退役 |

上述约 2260—3400 人日只覆盖领域主体；治理、数据清洗/切换、独立 QA、安全/性能/UAT 等横向工作见 16.1，不能重复当作“已包含缓冲”。域卡字段、实际负责人、准确日期和状态在 V1.0 基线时从 `TBD/OPEN` 转为签署值。

### 3.4 Integrated Master Schedule（P50 控制骨架）

本 IMS 是唯一受控排期源；W1—W6 章节只是功能波次分组，不另行产生日期承诺。WP 行只引用 16.1 的成本账户，不提供可相加的第二套 ROM；最小切片、验收组包和横向 QA 已包含在对应成本账户中。

| WP-ID | 域/切片与交付 | 前置/关系 | T0 相对窗口 | 成本账户 | 环境 | 退出里程碑/证据 | 关键路径/浮时 |
|---|---|---|---|---|---|---|---|
| WP-00 | W0完整采购/合同/基线/恢复/垂直样例 | C0；合同日历独立 | C0 D1—D20 | CA-GOV+CA-QA | 隔离/Integration | MS-20D；BASE登记 | 合同关键；0 |
| WP-01 | D00平台/契约/迁移工厂 | BASE最低闭合，FS | W3—W10 | CA-PLATFORM+CA-MIG | CI/Staging | D00-EX/EVID-D00 | 技术关键；0 |
| WP-02 | D14-MIN审计/Trace + D11生成内容合规前置门 | D00-CR，SS+2周 | W5—W9 | CA-SEC（MIN包含） | Staging | MS-AUDIT-MIN/EVID-D14-MIN；DEL-D11-COMPLIANCE-MIN/EVID-D11-COMPLIANCE-MIN | 生产前置；≤2周 |
| WP-03 | D01→D02→D03 内容控制链 | D00-CR；域间 CR/RR 为 FS | W8—W20 | CA-IAM+CA-CONTENT | Staging/PreProd | D01—03-EX/EVID-D01—03 | 主关键链；0 |
| WP-04 | D04/D05 资产与模型并行支线 | D00-CR，SS | W8—W18 | CA-ASSET+CA-MODEL | Staging/PreProd | D04/D05-EX/EVID-D04—05 | MS-06M硬前置；≤2周 |
| WP-05 | D06持久任务/ProviderOperation/GPU | D00-EX + D13/14合同，FS | W10—W22 | CA-EXEC | Staging/PreProd | D06-EX/EVID-D06 | 执行关键；≤1周 |
| WP-06 | D13-MIN预算/Ledger + Legacy Completion Adapter | D01/D05/D06-CR，SS | W12—W18 | CA-FIN+CA-MIG（MIN包含） | Staging/PreProd | MS-LEDGER-MIN/EVID-D13-MIN；MS-ADAPTER-WR/EVID-LEGACY-ADAPTER | 付费硬前置；0 |
| WP-07 | D07合同→D08流程→D09执行 | D03-RR + D04/05/06-CR，FS | W16—W23 | CA-STORYFLOW+CA-PY | PreProd | D07—09-EX/EVID-D07—09 | MS-06M主链；0 |
| WP-08 | MS-06M候选、UAT、整改、签署缓冲 | WP-01—07完成，D00—09均达EX，MS-AUDIT-MIN/MS-LEDGER-MIN/MS-ADAPTER-WR/MS-D15-UI-MIN及合规MIN证据通过，FS | W23—W26且不得晚于T0+6日历月 | CA-QA（阶段验证包含） | PreProd/UAT | EVID-UAT-6M；MS-06M/PKG-6M | 合同关键；0 |
| WP-09 | D10/D11 声音/质量并行 | D05/06/07-CR，FS | W20—W32 | CA-AUDIO+CA-QUALITY | Staging/PreProd | D10/D11-EX/EVID-D10—11 | 交付关键；0—2周 |
| WP-10 | D12自动剪辑/渲染/交付 | D04/07/10/11-SR，SS | W28—W38 | CA-MEDIA | PreProd | D12-EX/EVID-D12 | 主关键链；0 |
| WP-11 | D15自W12贯穿；D13/D14完整域自W18扩展 | MIN切片+各域OpenAPI，SS | W12—W40 | CA-FIN+CA-SEC+CA-FE | 全环境 | MS-D15-UI-MIN/EVID-D15-UI-MIN（≤W22）；D13/14/15-WR/MS-ORR-ENTRY | 横向；≤2周 |
| WP-12 | 60批/1200分钟、压力/长稳/安全/DR | WP-09/10/11完成且D12-EX、D13/14/15-WR、MS-ORR-ENTRY，FS | W38—W48 | CA-QA+外部算力/OPEX | PreProd/Production | D13/D14-EX/EVID-D13—14；MS-INDUSTRIAL/EVID-INDUSTRIAL-READY | 合同关键；0 |
| WP-13A | 滚动证据组包、IP/SBOM/培训/ORR材料冻结 | WP-11、WP-12 SS；只允许组包不签终验 | W47—W49 | CA-GOV+CA-QA（组包包含） | Production/UAT | PKG-12M草案/DEL-IP-01（READY） | 证据支线；≤1周 |
| WP-13B | 最终UAT、整改复验、验收签署与退役决定 | WP-12/13A完成，D10—14均达EX且D15达WR，FS | W49—W52且受BD-001起算约束 | CA-QA（最终UAT包含） | Production/UAT | D15-EX/EVID-D15；MS-12M/PKG-12M/G8 | 合同关键；0 |

主关键路径为 `BASE → D00-EX → D01—09-EX/MS-06M → D10—12-EX → D13/D14/D15-WR → 工业验证与D13/D14-EX → D15-EX/最终UAT签署`；D06/D09、D13-MIN/D14-MIN、D11合规最小门和 Legacy Adapter 是在一期汇合点前必须闭合的并行硬前置。表中周数是 P50 容量模型，不证明 6/12 个日历月已经满足；V1.0 必须用实际人员可用量、节假日、采购/安全反馈和 GPU/Provider Lead Time 运行 CPM，记录总浮时/自由浮时和资源平衡。

#### 3.4.1 Milestone Catalog

| 里程碑 | 正式含义 | 通过依据 |
|---|---|---|
| MS-20D | ★20日原文对应的受控W0包，不等于二代终验 | PKG-20D及有权主体签署；受BD-001/011/013约束 |
| MS-PLATFORM | D00平台、契约、迁移和恢复骨架可重建 | D00-EX/EVID-D00 |
| MS-AUDIT-MIN | 首个生产写/真实Canary所需最小追加审计就绪 | DEL-D14-MIN/EVID-D14-MIN签收，审计/Trace/脱敏用例通过 |
| MS-LEDGER-MIN | 首个真实Canary所需最小预算与账务安全就绪 | DEL-D13-MIN/EVID-D13-MIN签收，TEST-DR-FIN-MIN及金额守恒通过 |
| MS-ADAPTER-WR | 在途旧任务完成桥可接管 | DEL-LEGACY-ADAPTER/EVID-LEGACY-ADAPTER签收，Registry/回调/Poll/费用守恒通过 |
| MS-D15-UI-MIN | 一期批准MVP页面、入口和最小BFF投影就绪 | DEL-D15-UI-MIN/EVID-D15-UI-MIN签收，批准页面TEST-UI-STACK通过 |
| MS-CONTROL | IAM/内容/Bible/资产/模型无付费控制链闭合 | D01—05均达EX且EVID-D01—05签收 |
| MS-EXEC | 持久任务、流程、Worker及付费安全链闭合 | D06—09均达EX，五窗口、最小Ledger/Audit与在途接管证据签收 |
| MS-06M | 原文一期建议阶段包；法定日期由BD-001确定 | TEST-UAT-6M/EVID-UAT-6M、PKG-6M和阶段签署通过；不用W26替代日历月 |
| MS-MEDIA | 声音、质量、自动修复、时间线与交付链闭合 | D10—12均达EX且金标/Golden/EVID-D10—12签收 |
| MS-ORR-ENTRY | 允许进入工业验证和最终ORR执行 | D12-EX、D13—15-WR，Runbook/值班/容量/恢复/UAT数据与环境入口清单通过；不等于ORR或终验通过 |
| MS-OPERATIONS | 财务、审计、安全、SLA、兼容和ORR闭合 | D13—15均达EX且EVID-D13—15签收 |
| MS-INDUSTRIAL | 60批/1200分钟及工业证据完成 | TEST-1200、性能/安全/DR/质量证据 |
| MS-12M | 原文二期建议阶段包；起算由BD-001确定 | PKG-12M及有权主体签署 |
| MS-RETIRE | 生产切换后G8正式完成 | 100%灰度、两个稳定周期、退役台账签署 |

### 3.5 Deliverable Master Register

| DEL-ID | 需求/域 | 受控交付物/路径 | Producer | Reviewer/Approver | 到期门 | Pass规则 | EVID-ID/状态 |
|---|---|---|---|---|---|---|---|
| DEL-W0 | W0/★20日边界 | 需求/合同缺口、架构送审稿、迁移控制骨架、恢复报告、目标栈Skeleton和无付费样例 | PM/ARCH/SRE | PO/LEGAL/QA | MS-20D | 清单完整、可复核且未把Skeleton表述为完整D00/二代终验 | EVID-W0/PLANNED |
| DEL-D00 | D00/技术栈 | ADR、OpenAPI/AsyncAPI、平台/迁移/部署/恢复附件 | SRE/ARCH | ARCH/SEC/QA | D00-EX | 可重建、兼容、恢复通过 | EVID-D00/PLANNED |
| DEL-D01 | D01 | IAM、组织、会话、权限Schema/API/事件及迁移包 | IAM/SEC | ARCH/PO/QA | D01-EX | 权限、租户、会话、数据和恢复通过 | EVID-D01/PLANNED |
| DEL-D02 | D02 | 项目/作品/剧本版本、导入Schema/API/事件及迁移包 | Creative | ARCH/PO/QA | D02-EX | 所有权、版本、兼容和数据通过 | EVID-D02/PLANNED |
| DEL-D03 | D03 | Bible/实体/审批/影响图Schema/API/事件及迁移包 | Creative | ARCH/PO/QA | D03-EX | 快照、证据、审批、影子/数据通过 | EVID-D03/PLANNED |
| DEL-D04 | D04 | Manifest/权利/Feature/Taxonomy/向量和对象迁移包 | Asset/DATA | LEGAL/SEC/QA | D04-EX | 哈希/权利/检索/逐单元追溯通过 | EVID-D04/PLANNED |
| DEL-D05 | D05 | 模型/训练/Prompt/绑定/认证/Secret包 | Model/PY | LEGAL/SEC/QA | D05-EX | 制品、认证、快照和回退通过 | EVID-D05/PLANNED |
| DEL-D06 | D06 | Job/Attempt、base key+execution_generation ProviderOperation根、不可覆盖Epoch/提交授权/WorkerLease历史、唯一Grant/CAS/Egress/GPU/DR包 | Execution | ARCH/FIN/SRE/QA | D06-EX | 未受理同根升epoch、已受理失败新代次/预算、晚到隔离均守恒；竞争/站点无代次内重复付费，无第二账本、定稿闭环 | EVID-D06/PLANNED |
| DEL-D07 | D07 | Storyboard/Episode/Shot不可变合同和影响包 | Creative | ARCH/PO/QA | D07-EX | 合同版本、引用和重放通过 | EVID-D07/PLANNED |
| DEL-D08 | D08 | BPMN/人审/阶段/补偿/流程版本包 | Orchestrator | ARCH/PO/QA | D08-EX | 流程、权限、补偿和升级通过 | EVID-D08/PLANNED |
| DEL-D09 | D09 | Python Worker/Adapter/Provider/在途接管包 | PY/Provider | ARCH/FIN/SRE/QA | D09-EX | 参数、出口、回调、接管和Canary通过 | EVID-D09/PLANNED |
| DEL-D10 | D10 | 情感TTS、Voice、字幕和四轨对齐包 | Audio/PY | SME/PO/QA | D10-EX | 音色/可懂/情感/同步通过 | EVID-D10/PLANNED |
| DEL-D11 | D11 | 合规、质检、漂移校准和定向修复包 | CV/Quality | SME/PO/QA | D11-EX | 金标、阈值、调参、RepairRequest及新Repair Job/Attempt源血缘通过 | EVID-D11/PLANNED |
| DEL-D12 | D12 | 粗/精剪、SFX/BGM、Timeline、渲染和交付包 | Media | SME/PO/QA | D12-EX | Golden、同步、权利和成片Manifest通过 | EVID-D12/PLANNED |
| DEL-D13 | D13 | 预算/Ledger/Usage/Provider对账包 | FIN/Ledger | PO/FIN/QA | D13-EX | 金额、流水和账单守恒 | EVID-D13/PLANNED |
| DEL-D14 | D14 | Audit/Trace/SLA/告警/报表包 | SEC/SRE | PO/SEC/QA | D14-EX | 审计、运行、SLA和恢复通过 | EVID-D14/PLANNED |
| DEL-D15 | D15 | Gateway/BFF/React兼容、BFF投影目录、UI库/响应式等效性、E2E和退役清单 | FE/Gateway | PO/ARCH/QA | D15-EX | V1兼容、入口信任边界、投影重建、UI技术栈/响应式、页面和调用归零通过 | EVID-D15/PLANNED |
| DEL-D15-UI-MIN | RQ-STACK-3.1/D15最小切片 | MS-06M范围内MVP页面的UI库组件清单/书面等效评审、响应式断点、入口边界、最小BFF投影与E2E包 | FE/Gateway | PO/ARCH/QA | MS-D15-UI-MIN（最迟W22） | 批准MVP页面逐项通过TEST-UI-STACK；未覆盖页面列入D15完整范围且不冒充通过 | EVID-D15-UI-MIN/PLANNED |
| DEL-D13-MIN | D13最小付费安全切片 | 额度/预留/结算/释放/退款/冲正、Provider Usage/Cost最小流水及逻辑RPO=0复制/仲裁 | FIN/Ledger | FIN/ARCH/SRE/QA | MS-LEDGER-MIN（首个真实Canary前） | 并发/重复/未知/灾备下D13权威聚合与D06 reservation_id双向100%守恒 | EVID-D13-MIN/PLANNED |
| DEL-D14-MIN | D14最小生产审计切片 | 追加审计、Trace、Provider/模型/Manifest/费用关联和告警 | SEC/SRE | SEC/ARCH/QA | MS-AUDIT-MIN（首个生产写/真实Canary前） | 审计不静默丢失、关联完整、敏感数据脱敏 | EVID-D14-MIN/PLANNED |
| DEL-D11-COMPLIANCE-MIN | D11合规前置门 | 剧本/Prompt/参考资产外发前fail-closed策略、人工放行和审计 | Quality/SEC | PO/SEC/QA | 首个真实外部模型调用前 | 命中/策略不可用均阻断；放行有版本/权限/期限 | EVID-D11-COMPLIANCE-MIN/PLANNED |
| DEL-LEGACY-ADAPTER | 在途付费接管 | Registry、Callback/Poll路由、Legacy Completion Adapter及D06/D04/D13 Inbox | EXEC/PY/DATA | EXEC/FIN/Asset/QA | MS-ADAPTER-WR（CW-04前） | 旧任务不重提、完成/资产/费用守恒，旧库写被栅栏拒绝 | EVID-LEGACY-ADAPTER/PLANNED |
| DEL-IP-01 | RQ-IP-01 | 触发验收后的源码/注释/设计/开发日志、可编辑文档、加密介质/密钥交接包，以及归属权转移至采购人的权利转移清单和双方有权主体签署凭证 | PM/研发/LEGAL | PO/LEGAL/QA | 原文验收后T+10工作日 | 版本/范围/SBOM/权利清单、离线构建、文件hash、介质/密钥双人签收及权利转移签署通过；背景IP/第三方例外只认BD-005正式偏离 | EVID-IP-01/PLANNED |
| DEL-SVC-EVOLUTION | RQ-ROADMAP-4.3 | 持续模型量化/剪枝/性能调优、Prometheus/Grafana/Trace趋势及最终技术演进报告 | Model/SRE/PM | PO/ARCH/QA | 签署持续服务周期 | 每次优化有基线/版本/回退/指标，最终报告可由原始证据重算 | EVID-SVC-EVOLUTION/PLANNED |
| DEL-PKG | 路线图/商务 | PKG-20D、PKG-6M、PKG-12M、培训/IP/ORR/服务包 | PM/QA | PO/LEGAL/FIN | 各合同门 | 完整性、复验、签署和触发点明确 | EVID-PKG/PLANNED |

每个 DEL 在受控台账中拆到具体路径、版本/Digest、Producer、Reviewer、Approver、到期日期、需求 ID、验收公式和证据哈希；上表不是以“组”代替逐项签收。

---

## 4. 源资产与目标路径总图

### 4.1 当前关键源路径

| 能力 | 当前路径/资产 |
|---|---|
| API 契约面 | `backend/app/api/v1/router.py`、`backend/app/api/v1/endpoints/` |
| 领域模型 | `backend/app/models/` |
| 供应商/媒体 | `backend/app/features/model_drivers/`、`backend/app/services/` |
| 生产状态/运行 | `backend/app/models/production_state_event.py`、`backend/app/models/series_production_run.py` |
| 模型中心 | `backend/app/models/model_center.py`、相关 feature/service |
| 现有前端 | `frontend/src/app/`、`frontend/src/features/`、`frontend/src/lib/api-client.ts` |
| 测试金标种子 | `backend/tests/`、`frontend/e2e/`、现有发布/验收脚本 |
| 数据/媒体样本 | `backend/ai_video.db`、`backend/static/`；仅用于风险画像，不等于生产 |
| 架构治理 | `docs/architecture/ai-development-governance.md`、`docs/architecture/module-boundaries.md` |

### 4.2 计划新增路径

```text
control-plane/
  pom.xml
  gateway/
  services/{iam,creative,asset,model-factory,orchestrator,execution,quality-delivery,usage-audit}/
  shared-kernel/
contracts/
  openapi/
  asyncapi/
  jsonschema/
infra/
  k8s/
  helm/
  compose/
docs/
  architecture/
  migration/
  acceptance/
  runbooks/
backend/app/workers/              # 首阶段建议位置；独立发布条件满足后再提取
frontend/src/features/            # 按领域迁移页面和API Facade
```

这些是目标路径，不代表当前仓库已经实现。具体模块名在 W1 的 ADR 和首个子计划中锁定；未经设计批准不预建无业务内容的空模块。

### 4.3 Reuse Asset Register

复用不是“文件原样搬运”，而是逐项选择 `DIRECT（直接）/ ADAPT（适配）/ SEMANTIC（只复用语义/测试）/ ARCHIVE（归档）/ REWRITE（重写）`，并用刻画测试和 IP/数据门证明。W0 将下表展开到实际文件/表/对象级：

| REUSE-ID | 资产/路径 | 当前证据 | 目标域 | 类型 | Characterization/验收 | 数据/IP/Secret | 迁移 WP / 退役条件 |
|---|---|---|---|---|---|---|---|
| REUSE-FE | `frontend/src/app/`、`features/`、UI/E2E | React产品流程、97个Playwright spec | D15 | DIRECT/ADAPT | V1响应快照、Playwright、视觉/无障碍 | 清理localStorage/敏感数据 | WP-11；新Facade稳定后退旧页面写入口 |
| REUSE-API | `/api/v1` 路径、DTO、状态/错误 | 现有前后端调用和测试 | D15/各域 | SEMANTIC | OpenAPI消费者合同/差异表 | 不携带旧鉴权旁路 | WP-01/11；兼容调用归零或合同保留 |
| REUSE-BIBLE | StoryEntity/Bible/状态/证据/影响图 | 领域模型、现有测试；热点endpoint不可扩 | D02/D03/D07 | ADAPT/SEMANTIC | UUID/版本/规则金标/影响传播 | A/B/C/D、正文分级 | WP-03/07；新域EX后旧表只读 |
| REUSE-ASSET | Asset/媒体/来源任务/定稿语义 | 本地样本仅作风险画像 | D04 | ADAPT/ARCHIVE | 对象SHA-256、Manifest/权利/引用闭包 | C归档、D冻结；不搬公网URL | WP-04；切引用+观察后归档源 |
| REUSE-MODEL | Provider/Profile/Binding/Recipe/Prompt/快照 | 模型中心、驱动和认证语义 | D05/D09 | DIRECT/ADAPT | 参数合同、Fixture、真实Canary/回退 | Secret重录/KMS；模型/数据权利 | WP-04/07；旧endpoint不再调SDK |
| REUSE-JOB | 旧Job、Provider Task ID、结果/费用引用 | 多类Job/运行记录 | D06/D13 | ADAPT/SEMANTIC | 状态映射、在途登记、金额/结果守恒 | 凭据/回调/账单Owner明确 | WP-05/06；登记册闭合后退旧写 |
| REUSE-PY | 文本/图像/视频/TTS/供应商/FFmpeg代码 | Python生态和已验证参数 | D09/D10/D12 | DIRECT/ADAPT | 公共Facade、Provider合同、Golden | 无业务库写权、出口/Secret隔离 | WP-07/09/10；独立发布后提取 |
| REUSE-QUALITY | 质量报告、修复计划、人审流程 | 结构可用；占位/RGB评分不可验收 | D11 | SEMANTIC/REWRITE | 盲测、检测器Digest、阈值/仲裁 | 金标权利/训练集隔离 | WP-09；占位逻辑退出放行链 |
| REUSE-DATA | UUID、时间、血缘/审计事实 | 本机库约785MB且存在大量引用违规/Schema漂移 | 全域 | ADAPT/ARCHIVE | DM波次、引用/金额/哈希100%核对 | 生产画像后重新基线 | 各DM；禁止整库直灌 |
| REUSE-TEST | `backend/tests/`、`frontend/e2e/`、Fixture | 216个后端测试文件、97个E2E spec | 全域 | DIRECT/ADAPT | 刻画→合同→迁移回归映射 | Fixture去敏/IP确认 | 各WP；仅在替代证据通过后退旧测试 |
| REUSE-DOC | 架构治理、差距/验收/运维经验 | 当前文档与问题知识 | D00/D14 | DIRECT/ADAPT | 版本/hash、当前实现核对 | 不把旧部署说明当新SLA | WP-00/01/13；受控更新不删除历史 |

任何 `DIRECT/ADAPT` 资产没有刻画测试、Owner、权利/Secret 状态和退役条件时，自动降为 `SEMANTIC` 或隔离，不得用“已有成果复用”绕过新架构门禁。

---

## 5. 数据迁移工厂

### 5.1 清单字段

每条记录和媒体对象形成：

```text
source_system / source_table_or_path / source_id
target_domain / target_id / tenant_id / project_id
source_schema_version / target_schema_version / status / aggregate_version
reference_closure / content_sha256 / object_sha256
pii_class / secret_class / rights_class / retention_class
migration_grade / batch_id / result / error_code / owner / approval
```

### 5.2 A/B/C/D 分级

| 等级 | 条件 | 动作 |
|---|---|---|
| A 可直接迁移 | 归属明确、引用闭合、哈希可校验、状态合法、权利明确 | 自动迁移、100% 核对、可进入生产 |
| B 可修复迁移 | 业务引用存在，但引用/血缘/枚举/哈希不完整 | 进入隔离库，修复和复核后迁移 |
| C 归档 | 开发、测试、重复、未引用且不属于定稿交付 | 只读归档，不进入生产主库 |
| D 冻结 | 租户、版权、密钥或来源无法证明 | 禁止自动迁移，等待业务/法务决定 |

### 5.3 迁移规则

- UUID 默认不变；冲突时使用永久 `legacy_id_map`；
- 时间统一为 UTC，并保存原时区信息；金额使用 Decimal 或人民币分；
- 关键 JSON 只按批准字段白名单保存 `legacy_payload`，再投影为规范结构；Payload 必须按数据等级加密、受访问审计和保留期限控制，禁止保存密钥、Token、长期签名 URL 或无业务必要的客户正文；
- 旧密钥不导出明文，使用新 KMS 重加密或标记 `credential_reentry_required`；
- 已受理供应商任务迁移 External Task ID 和状态，不触发 submit；
- 媒体使用 copy，不使用 move；完成 HEAD、抽样下载和 SHA-256 后切引用；
- 财务、锁定合同、发布版本、审计和定稿资产要求 ID 集合与内容哈希 100% 一致；
- 非关键派生字段的容差必须在子计划中量化并获得审批。

### 5.4 本地风险基线

当前本机样本约 785 MB，含 33,222 项资产、91,602 个实体和 21,546 个镜头；外键检查发现 45,892 条违规，另有 2,991 个实体缺失小说引用、231 个资产缺失实体引用；`static` 约 33 GB。它不代表生产，但足以证明全量直灌不可接受。

### 5.5 通用核对

每批次至少核对：

- 行数、主键集合、唯一键、状态分布、聚合版本；
- 外键/引用闭包、租户/项目归属；
- 金额预留、结算、退款和供应商任务数量守恒；
- 媒体大小、MIME、SHA-256、Manifest 和对象可读性；
- API 响应、状态和错误语义；
- 审计/Trace 可关联性；
- 重跑同一批次不新增第二份有效数据。

### 5.6 在途付费任务接管登记册

任何涉及模型供应商、云 GPU、TTS 或媒体 API 的域，在切换前必须建立 `In-flight Task Handover Registry`。每条在途任务至少记录：

```text
legacy_job_id / new_job_id / task_type / tenant_id / project_id
provider / provider_task_id / provider_idempotency_key
provider_operation_id / side_effect_base_key / execution_generation / logical_side_effect_key
source_provider_operation_id / source_operation_epoch / retry_reason
current_operation_epoch / epoch_attempt_id / submit_grant_state
poll_owner / webhook_route / legacy_completion_adapter
credential_ref / model_snapshot_id / execution_contract_sha256
current_state / last_provider_state / cutover_epoch / site_epoch
operation_epoch / submit_lease_id / submit_fencing_token / submit_site_epoch / outbound_started_at
active_monitor_persist_reconcile_lease_ids / worker_lease_history_uri
input_manifest_uri / output_prefix / finalization_owner
asset_owner / reservation_id / expected_cost / ledger_owner
poll_deadline / reconciliation_state / final_error / approval
```

接管规则：

1. 切换高水位冻结后，每个在途任务只能有一个 Poll/Webhook Owner；
2. `provider_task_id`、Provider 幂等键、凭据引用、模型快照和回调路由保留到任务闭合；
3. 旧 Worker 可以继续轮询，但完成结果只能通过受控 `legacy-completion-adapter` 和新所有者的 Inbox 提交到 D06/D04/D13，不得继续写已冻结的旧任务/资产/账务表；
4. Adapter 验证租户、合同哈希、Provider ID、cutover epoch、fencing token、Manifest 和费用引用；重复回调返回既有结果；
5. 供应商状态未知时进入 `UNKNOWN_REQUIRES_RECONCILIATION`，执行补查或人工确认，禁止创建第二次 submit；
6. 过期、无凭据或无权利任务进入隔离/DLQ，并有业务、财务和 Provider Owner 的书面处置；
7. G8 只有在登记册无活动任务，或所有剩余项均进入批准的长期隔离并完成余额/资产/审计守恒后才能签署。

该登记册和 Adapter 必须形成独立跨域子计划，不能分散在 D06/D04/D13 各自实现后再靠人工拼接。

### 5.7 Data Migration Wave Register

本表是 V0.95 控制骨架；W0 生产画像后必须填入准确源实例/Schema/表/路径、量级、吞吐、CDC 高水位和具体日期并重新批准。含 `TBD` 的波次不得执行生产迁移。

| DM-Wave | 域/对象 | 源 → 目标 | 分级/方式 | 前置 | 核对公式/隔离 | P50窗口 | Owner/状态 |
|---|---|---|---|---|---|---|---|
| DM-00 | 契约、配置、迁移元数据 | Git/旧配置 → contracts/D00 Schema/KMS引用 | A/B；版本化导入，无CDC | BASE-ARCH/D00-CR | 版本/hash/Secret引用；未知进入隔离 | W3—W8 | ARCH/SRE / PLANNED |
| DM-01 | 用户/项目成员/组织映射 | 生产用户/项目表TBD → IAM Schema | A/B；Full+增量 | D01-RR、Token/密码策略 | ID/归属/角色/状态100%；冲突隔离IAM Owner | W10—W14 | DATA/IAM / BLOCKED-BY-PROFILE |
| DM-02 | 项目/剧本/Bible/实体/分镜/合同 | 生产内容表TBD → Creative Schema | A/B/C/D；Full+CDC/Outbox | D02/03/07-RR、金标 | ID集合/版本/hash/引用闭包100%；坏引用隔离 | W13—W22 | DATA/Creative / BLOCKED-BY-PROFILE |
| DM-03 | 资产/媒体/向量/权利 | 生产DB/对象路径TBD → Asset Schema/Bucket/Milvus | A/B Copy+增量；C归档；D冻结 | D04-RR、对象/权利策略 | 字节/Version/SHA-256/引用/权利100%；隔离Bucket | W12—W28 | DATA/Asset/LEGAL / BLOCKED-BY-PROFILE |
| DM-04 | 模型/Prompt/配方/绑定/制品 | 生产模型表/仓TBD → Model Schema/Artifact Bucket | A/B；版本导入；Secret重录 | D05-RR、制品/IP/KMS | Digest/许可证/绑定解析/可加载；Secret异常隔离 | W12—W20 | Model/SEC / BLOCKED-BY-PROFILE |
| DM-05 | Job/Provider/在途/预算/费用 | 生产Job/账务TBD → Execution/Ledger Schema | A/B；历史Full+增量+Registry | D06/D13-RR、MS-ADAPTER-WR | 状态/Provider ID/金额/Manifest守恒；未知冻结 | W16—W26 | DATA/EXEC/FIN / BLOCKED-BY-PROFILE |
| DM-06 | 质量/声音/时间线/交付 | 生产质量/媒体表TBD → Quality/Delivery Schema | A/B/C；版本导入+新链影子 | D10/11/12-RR | 合同/对象/时间码/产物hash；占位证据不得迁为PASS | W26—W38 | Quality/Media / BLOCKED-BY-PROFILE |
| DM-07 | 审计/报表/归档/法律保留 | 生产日志/审计/归档TBD → Audit/湖仓/WORM | A/B/C/D；受控导入 | D14-RR、留存/法务 | 事件数/hash链/时间窗/主体；敏感导出隔离 | W20—W42 | SEC/DATA/LEGAL / BLOCKED-BY-PROFILE |

### 5.8 迁移批次状态机

```text
DRAFT → PROFILED → DRY_RUN_PASSED → APPROVED → FROZEN
      → COPYING → CATCHING_UP → CUTOVER → VERIFIED → CLOSED
                                ↘ QUARANTINED
                                ↘ FORWARD_RECOVERY → VERIFIED
```

- `PROFILED`：源版本、行/对象量、A/B/C/D、Owner 和权利已知；
- `DRY_RUN_PASSED`：重复运行无第二份有效数据，吞吐/窗口和核对公式有证据；
- `APPROVED/FROZEN`：数据所有者批准范围并记录高水位，字段映射不再无单变更；
- `CUTOVER`：只能绑定一个已批准 `CW-ID`、`cutover_epoch` 和写栅栏；
- `VERIFIED/CLOSED`：零未解释关键差异、观察期完成，C/D按批准方式归档/冻结；
- `QUARANTINED/FORWARD_RECOVERY`：不得用删除或重跑掩盖失败，必须记录影响、修复制品和复核。

### 5.9 Cutover Wave 与恢复分类台账

| CW-ID | 域/切换单元 | DM-Wave/前置 | P50窗口/最大停写 | Fence/Smoke | Abort阈值 | R类/no-return | Commander/状态 |
|---|---|---|---|---|---|---|---|
| CW-01 | D01 tenant | DM-01、D01-WR | W14—W16；停写TBD | IAM epoch/权限/会话 | 任一跨租户、归属差异 | R3；首个新IAM写 | IAM Lead+SEC / PLANNED |
| CW-02 | D02/03/07 project/run | DM-02、各域WR | W20—W24；TBD | Creative epoch/API/版本/hash | 版本/引用/响应未解释差异 | R2/R3；新快照/合同发布 | Creative+DATA / PLANNED |
| CW-03 | D04/D05 project/capability | DM-03/04、D04/05-WR | W18—W26；TBD | Manifest/Binding epoch | 对象hash/权利/绑定/Secret失败 | R2；权利/撤销R3 | Asset/Model / PLANNED |
| CW-04 | D13-MIN/D14-MIN + D06/D09 新任务 | DM-05、MS-ADAPTER-WR、五窗口+租约换代+已受理失败新代次+站点测试 | W20—W26；新任务短冻结TBD | ledger/execution generation/site epoch、任务Smoke | 同base key/generation重复submit/扣费、复用旧预算、旧站点仍可外呼、未知未接管 | 未外呼R1；受理/流水R3 | EXEC+FIN+PROVIDER+SRE / PLANNED |
| CW-05 | D08 流程新实例 | D07-WR、D08-WR | W22—W26；TBD | process version/business key | 阶段/人审/补偿不一致 | R3；新实例创建 | Orchestrator / PLANNED |
| CW-06 | D10/11/12 pipeline/run | DM-06、各域WR | W32—W40；TBD | pipeline/renderer/quality epoch | 同步/质量/成片hash超阈 | R2/R3；新交付包发布 | Quality/Media / PLANNED |
| CW-07 | D13/D14 全域事实 | DM-05/07、D13/14-WR | W32—W42；TBD | ledger/audit epoch | 金额、审计链或Trace不守恒 | R3；首笔新流水/审计 | FIN+SEC / PLANNED |
| CW-08 | D15 API/page/tenant | 对应域EX、兼容E2E | W14—W46；无业务停写 | route flag/OpenAPI/Playwright | V1破坏、页面副作用错误 | R1路由；后端写者不回退 | FE+Gateway / PLANNED |

恢复分类主表：

| 域组 | R类 | 最大反投影窗口 | no-return 触发 | 前向恢复制品 | 演练/证据/批准 |
|---|---|---|---|---|---|
| D01、D13、D14 | R3 | 不适用 | 身份、流水或审计首个新事实 | 新版本/冲正/撤销/兼容代理 | PreProd；EVID-REC-01；SEC/FIN/PO |
| D02/D03/D07 | R2/R3 | 子计划实测TBD | 新锁定快照/合同发布为R3 | 反投影读模型或新版本 | PreProd；EVID-REC-02；DATA_OWNER |
| D04 | R2/R3 | 切引用前TBD | 权利撤回/删除/新定稿事实 | 对象版本、引用回切或前向修复 | PreProd；EVID-REC-03；Asset/LEGAL |
| D05 | R1/R2 | 新任务前绑定可回退 | 任务创建固定快照 | 回上一认证绑定；旧任务不变 | Staging；EVID-REC-04；Model Lead |
| D06/D09 | R1/R3 | 外呼前可回退 | `outbound_started_at`/Provider受理 | 补查、接管Poll、Manifest认领 | PreProd；EVID-REC-05；EXEC/FIN/PROVIDER |
| D08 | R3 | 不适用 | 新流程实例创建 | 固定原定义/补偿流程 | PreProd；EVID-REC-06；Orchestrator |
| D10/D11/D12 | R2/R3 | 新包发布前TBD | 新质量/交付事实发布 | 新Repair Job+Attempt/新Timeline/回旧Renderer | PreProd；EVID-REC-07；SME/QA |
| D15 | R1 | 路由观察期 | 无业务no-return；随所属域 | Feature Flag/兼容代理 | PreProd/Prod；EVID-REC-08；FE/Gateway |

实际日期、停写上限、在途数量、高水位、命令、Smoke、批准人和结果必须在每张生产切换单实例化；本表中的 `TBD/PLANNED` 明确阻断执行。

---

## 6. 统一迁移门禁

| 门禁 | 必须证明的事实 | 阻断条件 |
|---|---|---|
| G0 备份/恢复 | 数据库、媒体、配置和关键密钥引用完成真实恢复演练 | 只有备份日志、无恢复证据 |
| G1 契约/金标 | 旧 OpenAPI、状态机、错误语义、核心页面和副作用形成刻画测试 | 关键行为无基线 |
| G2 数据完整 | 批准范围内 A 级及修复复核 B 级的 ID、归属、引用、金额、任务、媒体哈希通过；C 归档、D 冻结 | 迁移分母内关键事实有未解释差异，或把 C/D 偷换为生产数据 |
| G3 API 兼容 | 旧前端可经兼容层运行；OpenAPI 无未批准破坏项 | 需要同时重写前后端才能切换 |
| G4 副作用安全 | 同base key/generation只resolve一个根；PREPARED授权为空、Grant时一次固化submit lease/fence/site，阶段接管租约只追加；五窗口/响应丢失/双D06/Egress/站点下每epoch仅一提交。确认未受理同根升epoch；已受理失败仅在终态/旧费收敛后以新generation/根/键/预算重跑；未知不重跑。D06 CAS、无第二账本及财务证据完整 | 可出现双根/Grant/CAS、授权快照被接管覆盖、已受理失败复用旧键/预算、状态不明重跑、D06/D13不守恒、旧站点仍可外呼，或无法证明代次内单次副作用 |
| G5 安全 | 跨租户、越权、会话、密钥、私有媒体、审计测试通过 | 任一 P0 安全缺陷 |
| G6 运行/GPU | 队列积压、Worker/GPU 丢失、租约、DLQ、告警和恢复通过 | 状态不可解释或无法恢复 |
| G7 业务 | 对应演示、真实质量、选择性重生和全链追溯通过 | 占位证据参与通过 |
| G8 退役 | 对旧实现/旧数据库的写流量和兼容代理调用归零，在途登记册闭合、历史查询与观察窗口完成；公开 `/api/v1` 可继续由新服务兼容提供 | 仍有未知旧实现调用方、在途任务或未完成观察期 |

所有领域还必须通过需求追踪、安全、性能、运行、恢复、UAT 和灰度门。5% 灰度建议连续 7 天、100% 建议连续 14 天无 P0/P1 迁移事故；具体窗口在上线变更单中批准。

“稳定发布周期”定义为：同一候选主版本、同一数据/任务状态机兼容范围内连续运行的批准窗口；期间若发生 P0/P1、状态/数据/账务不守恒、回退或影响该域的主版本发布，观察期从修复版本重新开始。无业务流量或只有健康检查不计稳定周期。

### 6.1 环境与制品晋级矩阵

| 环境 | 用途/数据等级 | 真实/替身依赖 | 入口/必跑 | 出口/批准 | 制品/配置/DB规则 |
|---|---|---|---|---|---|
| Local | 单服务开发，合成最小数据 | 默认全替身 | 单元/静态/本地契约 | 开发自检 | 可本地构建，不作为晋级制品 |
| CI | 隔离数据，生成候选镜像 | Provider替身，无付费 | 单元/集成/ArchUnit/Schema/扫描 | Pipeline签名 | 产出一次镜像Digest/SBOM/测试报告 |
| Integration | 多服务/事件/迁移联调，合成/脱敏数据 | 受控替身；外呼默认禁 | 合同、重复/乱序、Dry-run、V1兼容 | Tech Lead/QA | 使用CI同Digest；配置/Secret分离；Expand Schema |
| Staging | 生产同构、两分片、故障/恢复/容量 | Sandbox/批准真实依赖 | G0—G6、迁移/Provider五窗口+站点分区、K8s/DR | ARCH/SRE/SEC/QA | 同Digest晋级；禁止重构建；迁移先Expand/回填 |
| Pre-production/UAT | 候选发布、签署数据/账号、演示/验收预演 | 批准小额Provider/GPU | G0—G7、性能/安全/业务/UAT | PO/QA/SEC/FIN | 与生产发布形态一致；配置审批；Contract删除禁止先行 |
| Production-Canary | 内部→1→5→25→50% | 真实依赖 | Smoke、守恒、Burn-rate、Abort | Change Commander/Gate Board | 同Digest/Schema版本；Feature Flag/epoch受控 |
| Production-Stable | 100%及观察/退役 | 真实依赖 | 14日建议观察、恢复/对账 | PO/SRE/DATA_OWNER | Contract Schema仅在两个兼容周期后独立变更 |

生产数据不得复制到非生产，除非完成批准的脱敏、最小化和留存；只有 Pre-production/Production 的批准身份可触发真实付费副作用。同一候选镜像从 CI 按 Digest 晋级，不在环境间重构建；环境配置、Secret、数据库迁移版本分别受控并共同进入 Evidence Manifest。

### 6.2 Domain DoR / DoD

**DoR（允许进入实现）**：需求/来源/性质和 BD 状态已知；聚合/唯一写者/禁止事实明确；API/事件/状态/错误/数据映射达到 CR；Reuse/DM/CW/R类和在途规则有草案；威胁/容量/Provider能力/预算/IP完成初评；失败测试、Owner/RACI、人日/环境/依赖/交付物/证据 ID 已登记。

**DoD（允许申报 EX）**：实现和目标栈治理通过；合同/单元/集成/E2E/安全/性能/恢复均有新证据；DM/CW 核对、影子比较、写栅栏/Smoke/灰度完成；P0必须为0，P1按18.5处理——生产/正式验收包必须为0，非生产EX只可使用命名Gate的限期豁免；Runbook/看板/告警/值班/培训材料就绪；数据/资产/账务/审计/在途守恒；DEL/EVID签署，旧写退役条件与前向恢复制品明确。

缺任一 DoR 字段只能做探索/原型，不得接生产事实；缺任一 DoD 证据不能以代码完成、页面可见或测试勾选代替域退出。

---

## 7. W0：合同、基线、资产与验收冻结（第 1—20 日）

### 7.1 目标

在不改变生产写路径的前提下，关闭高风险未知量，形成可以实施和验收的共同基线。

### 7.2 任务

- [ ] **W0.1 合同追踪和阻断决策**
  - 产出：取得并登记完整采购文件（含被引用的第五章符合性审查）、源文件 hash/页码；总体架构第 21 章主追踪矩阵、`BD-001`—`BD-013`、阶段/演示/付款/IP/SLA 建议条款；由采购/法务确认进口产品、核心产品、节能/环境标志等采购元数据及外部云模型口径。
  - 验证：每个需求有性质/是否★、来源、设计域、证据、阶段、责任和偏离审批；文件缺失被显式阻断，强制需求无“计划建设即符合”。

- [ ] **W0.2 冻结工程与运行基线**
  - 产出：Commit SHA、镜像、配置、数据库版本、API 快照、Worker/供应商能力；仅对当前实际可运行的五项演示能力录制基线、原始任务 ID 和缺口，不补拍假证据。
  - 验证：在隔离环境可复现；模拟/真实/占位清楚区分；正式视频演示提交时点和格式留待 BD-011。

- [ ] **W0.3 生产数据和媒体只读画像**
  - 产出：表/对象/供应商任务/密钥引用清单、A/B/C/D 分级、Schema 漂移和数据质量报告。
  - 验证：不改源数据；抽样哈希和引用闭包可复核。

- [ ] **W0.4 备份和恢复演练**
  - 产出：数据库、媒体、配置恢复报告，明确 RPO/RTO 实测。
  - 验证：在隔离环境从备份恢复并通过核心只读校验。

- [ ] **W0.5 API/事件/数据合同基线**
  - 产出：V1 OpenAPI 快照、事件信封、错误码、任务/ProviderOperation base key+generation/Epoch/租约/生产合同草案；大模型API、云渲染农场、数字资产版权链三类外部系统清单和合同草案。
  - 验证：现有核心调用形成消费者契约测试。

- [ ] **W0.6 IP、许可证和成本基线**
  - 产出：背景 IP、定制代码、开源 SBOM、模型/字体/音乐/素材权利、GPU/API/OPEX 清单；原文第三方侵权保证、交涉、责任/费用/损失赔偿与责任上限/保险/处置权限法律清单；建立独立 `DEL-IP-01`，预定义原文验收触发、T+10工作日、源码/注释/设计/开发日志、可编辑格式、加密介质、密钥交接、离线构建验证、文件hash、双人签收、归属权转移清单及双方有权主体签署凭证；任何背景IP/第三方例外仅以BD-005正式偏离为准。
  - 验证：D 级资产冻结；未知成本有责任主体；DEL-IP-01 可在触发后按倒排执行；BD-012 未关闭不把技术清单解释为责任已接受。

- [ ] **W0.7 目标栈最小骨架与垂直样例**
  - 产出：隔离环境的 Gateway/Nacos/MySQL/Kafka/MinIO/K8s 骨架；固定数据的导入—合同—无付费 Worker—Manifest 样例。
  - 验证：不接生产写入；重复提交不产生第二结果；可完整销毁并重建。

- [ ] **W0.8 交付地点、现场与部署条件勘察**
  - 产出：采购方指定地点、云上/本地/混合选择、机房/网络/出口/代理/DNS/TLS、CPU/GPU/存储、账号/证书、数据进出、远程支持和8小时到场可达性报告。
  - 验证：现场/网络/GPU/第三方账号均有提供方、到位日、验收方法和晚到影响；地点未知保持 BD-006 阻断。

- [ ] **W0.9 范围—价格—甲供资源—排除项矩阵**
  - 产出：48.5万元对应 DEL/PKG、人员/算力/Provider/存储/测评/驻场/培训/SLA、甲供数据/账号/GPU/场地、排除项、OPEX上限和变更单价。
  - 验证：每项成本和资源有 Owner/上限/付款触发/晚到责任；BD-013 未签只允许无付费验证。

- [ ] **W0.10 指标、演示与验收基线**
  - 产出：节点降低主口径、向量Recall@K/p95、零样本TTS、四轨同步、自动剪辑、日报/漂移/合成效率、60批/1200分钟的公式/数据集/阈值/证据模板；五项演示逐bullet脚本。
  - 验证：原文与派生控制分开；演示提交、20日/6月/12月复验和整改签署流程有书面决定。

### 7.3 20 日交付边界

W0 可以交付架构、追踪、迁移工厂、恢复演练、合同栈骨架和受控垂直样例；不能声称已经完成全量 Java 控制面、真实算法、1200 分钟、7×24 或二代平台终验。五项视频演示只有在 BD-011 确认属于本门时才进入 PKG-20D；本段不能替代★20日原文或把 C0 改为 T0。

### 7.4 退出条件

- `BD-001`—`BD-013` 均按其适用阶段关闭或形成有权主体签署、明确截止和阻断范围的处置；其中至少 `BD-001/002/004/005/006/011/012/013` 在进入承诺性实施前有可执行书面结论；
- G0、G1 的基线部分通过；
- 目标技术 ADR 获批；
- 数据、成本和 IP 风险在批准范围内；
- W1 资金、人员、环境、GPU 和验收资源已到位。

---

## 8. W1：平台地基、契约与迁移工厂（功能波次；排期以3.4 IMS为准）

### 8.1 D00 平台基础

- **当前输入：** `compose.production.yml`、`.github/workflows/ci.yml`、现有配置/安全/发布文档。
- **目标路径：** `control-plane/`、`contracts/`、`infra/k8s/`、`infra/helm/`、`docs/runbooks/`。
- **产出：** Gateway、Nacos、MySQL、Kafka、Redis、MinIO、Milvus、Flowable/XXL-JOB 运行基座、K8s、Secret 管理、OpenTelemetry、Schema Registry/校验、Outbox/Inbox 和幂等基础库。
- **依赖：** ADR-001—005、环境和网络。
- **数据：** `outbox_event`、`inbox_dedup`、`idempotency_record`、迁移批次/核对结果；最终表名由 D00 子计划锁定。
- **测试：** 冷启动、依赖故障、重复/乱序事件、Schema 升降级、Secret 缺失 fail-closed、镜像和环境重建。
- **回滚：** 蓝绿保留现有生产拓扑；G0—G3 未通过前不承载正式写流量。
- **退出：** 同构 Staging 一键重建；备份恢复通过；契约发布和兼容校验可自动执行；迁移 Dry-run 不改源数据。

### 8.2 执行清单

- [ ] 创建 D00 详细子计划和 ADR，不直接从本文批量建服务。
- [ ] 建立 Maven 多模块最小工程、BOM、代码质量和安全扫描。
- [ ] 建立 OpenAPI/AsyncAPI/JSON Schema 目录和兼容性检查。
- [ ] 建立 MySQL 版本化迁移、Outbox/Inbox/幂等及 `ProviderOperation` generation根/Epoch/WorkerLease/提交水位基础模式。
- [ ] 建立 MySQL 主从复制和分片路由；Staging 使用至少两个物理分片验证路由、扩容、故障和恢复，一期单物理分片只能作为书面批准的临时偏离。
- [ ] 建立 Kafka、MinIO、Milvus、Nacos、Redis 的 Staging 拓扑和权限边界。
- [ ] 建立 Flowable 和 XXL-JOB 运行基座；XXL-JOB 仅触发受控夜间批次、资产备份编排、补查和对账，实际 GPU/备份由对应执行系统完成。
- [ ] 建立 K8s CPU/GPU 节点池、Secret、NetworkPolicy、镜像签名和发布流水线。
- [ ] 建立 OTel、Prometheus/Grafana、日志和 Trace 基线，以及 D14 最小追加审计接收/持久化切片；任何新生产写入必须先有可关联 Trace 和审计。
- [ ] 建立 D11 最小内容合规前置门：剧本/Prompt/参考资产进入真实外部模型前 fail-closed 检查、规则版本、人工放行和审计；W4 再扩展完整生成质量与修复。
- [ ] 固化大模型 API、云渲染农场、数字资产版权链三类 External Integration Contract 模板和 Sandbox；未选厂商时不得伪造真实接口证据。
- [ ] 完成 CI → Integration → Staging 的同一镜像 Digest、配置/Secret 和 Expand Schema 晋级演练。
- [ ] 完成数据库、Kafka、对象存储和集群恢复演练。

### 8.3 里程碑 MS-PLATFORM

生产同构 Staging 和迁移工厂可重复构建；基础设施不是“部署即通过”，而是完成真实 API、事件、对象和恢复验证。

---

## 9. W2：企业控制面核心（功能波次；排期以3.4 IMS为准）

### 9.1 D01 IAM、组织、工作区与 RBAC

- **当前输入：** `backend/app/models/user.py`、Project/ProjectMember、JWT/Bearer、`backend/app/core/permissions.py`、前端会话。
- **目标服务：** `iam-service`；Gateway 安全上下文。
- **数据所有权：** 用户、组织、工作区、成员、项目成员、会话、角色、权限、邀请和安全事件。
- **切换单元：** 先个人组织，再企业租户；按租户原子切换。
- **契约：** `subject/tenant/workspace/project/roles/permissions`；认证、会话、组织、成员和权限 API。
- **事件：** `identity.user.activated.v1`、`iam.membership.changed.v1`、`iam.session.revoked.v1`。
- **测试：** 权限矩阵正反向、跨租户、成员停用、Refresh 轮换/并发刷新、MFA、匿名与越权不泄漏对象存在性。
- **数据迁移：** 保留用户 ID 和兼容密码哈希；旧 Token 不迁；项目归属必须完整。
- **回滚：** 旧 Bearer 保留约定兼容周期；新隔离校验一旦启用不得通过降级关闭。
- **退出：** 客户资源 API 100% 接入统一鉴权；跨租户访问为零；所有项目有明确组织/工作区归属。

### 9.2 D02 项目、小说、章节、剧本与导入

- **当前输入：** Project、Novel、Chapter、Script、NovelImport、源文件。
- **目标服务：** `creative-domain-service`。
- **数据所有权：** 项目、作品、章节版本、剧本版本、源文件 Manifest 和导入结果。
- **切换单元：** 项目。
- **事件：** `content.source.ingested.v1`、`content.chapter.versioned.v1`、`content.script.imported.v1`。
- **测试：** V1 刻画、顺序、版本、编码、大文件、重复导入幂等和源文件哈希。
- **回滚：** Gateway 按项目路由；新服务写入后旧 API 只能调用新主数据或只读投影，不恢复双写。
- **退出：** ID、章节顺序、正文哈希和项目归属 100% 一致；旧页面无需语义修改可读取。

### 9.3 D03 Production Bible、实体、状态与审批

- **当前输入：** StoryBible、StoryEntity、Character、EntityMention、ProductionStateEvent、现有快照/Story Lock。
- **目标服务：** `creative-domain-service` 内独立领域模块。
- **数据所有权：** 实体、别名、关系、状态变化、证据、内容审批/发布事实、规则、快照、版本和语义影响图。
- **切换单元：** 小说/系列。
- **事件：** `bible.draft.extracted.v1`、`entity.approved.v1`、`bible.snapshot.published.v1`、`bible.change.invalidated.v1`。
- **测试：** 章节边界防剧透、证据定位、实体合并、状态时序、快照哈希、审批权限、变更影响。
- **回滚：** 旧 Bible 仅为只读投影；已发布新快照不反向覆盖旧 JSON。
- **退出：** 锁定镜头均指向确定 Bible 版本；关键实体无孤儿；连续三批无关键投影差异。

### 9.4 D04 资产、媒体与版权血缘

- **当前输入：** Asset、MediaGenerationJob、ProviderAssetBinding、本地 `static`、现有对象/供应商输出。
- **目标服务：** `asset-service` + MinIO/S3 + Milvus。
- **数据所有权：** 资产元数据、对象 Manifest、引用、版权/同意、保留策略和删除回执；版本化 Asset Feature/Taxonomy Contract，包括脸部/发型、服饰、年龄、身体比例、体态、声音特征及场景/风格/光影层级、同义词、Embedding/提取模型版本和人工确认。
- **切换单元：** 对象 Manifest + 项目；先复制后改引用。
- **事件：** `asset.ingested.v1`、`asset.finalized.v1`、`media.persisted.v1`、`rights.asset.blocked.v1`。
- **测试：** SHA-256、跨租户、签名过期、对象缺失、临时 URL、删除/法律保留和恢复；固定查询集上的跨分镜快速索引 Recall@K/Precision@K/无结果率/p95；每个图像/音频/视频单元均核对 `provider_operation_id/generation_parameter_snapshot_id/seed/duration_ms/media_unit_index`、输入输出哈希和生成记录。
- **回滚：** 数据库指针切回旧对象；源媒体保留至少两个发布周期。
- **退出：** A 级对象字节与哈希 100% 一致；生产媒体不依赖公开 `/static`；生成物可追溯来源、权利和逐单元参数；角色/场景资产可按批准 Taxonomy 跨分镜检索且无孤立向量。

### 9.5 D05 模型工厂、Prompt、绑定与认证

- **当前输入：** 模型连接、Profile、Binding、Recipe、Prompt、认证和不可变执行快照。
- **目标服务：** `model-factory-service`；Python Runtime Worker。
- **数据所有权：** 连接密文引用、训练数据集 Manifest 引用、Experiment/Training Run、模型/制品版本、LoRA/ControlNet、绑定、配方、Prompt、模型认证与发布记录；训练原始对象仍由 D04 管理，D05 仅向 D14 发审计请求事件，追加审计事实仍由 D14 唯一写入。
- **切换单元：** 租户 + 能力绑定；每个任务固定快照。
- **事件：** `model.artifact.certified.v1`、`model.profile.published.v1`、`model.binding.changed.v1`、`model.profile.revoked.v1`。
- **测试：** 数据集权利/哈希、训练重现、离线金标评估、密钥脱敏、版本不可变、能力参数、绑定解析、真实认证、Canary、回退和任务重放。
- **回滚：** 绑定回到上一认证版本；已创建任务继续原快照。
- **退出：** 配置、认证、发布、用户可见、Worker 可加载和真实任务可用分别有证据。

### 9.6 执行清单

- [ ] 分别创建 D01—D05 子计划、Schema 和契约测试。
- [ ] 先实现无付费垂直切片：导入 → 实体候选 → 人审 → Bible 快照 → 资产/模型引用 → 锁定镜头合同。
- [ ] 完成 IAM、内容、Bible、资产和模型域的幂等回填与影子读。
- [ ] 建立 D04 Asset Feature/Taxonomy Contract、跨分镜向量索引和逐媒体单元生成日志；执行 `TEST-ASSET-MANIFEST`。
- [ ] 按内部租户/项目灰度切换唯一写入者。
- [ ] 完成跨租户、安全、对象和模型回退演练。
- [ ] 在 BD-011 确认的证据规则下完成 DEMO-6.1-0（人物关系分析+关键事件）及 DEMO-6.1-a—e 新链路预演，并完成 DEMO-6.2-0（创建原创角色、来源/权利证据+多情绪连续生成）和 DEMO-6.2-a/d 的资产档案、后台调用/参数/生成记录证据；若要求投标前提交，本波次仅作复验而非首次交付。

### 9.7 里程碑 MS-CONTROL

从剧本导入到不可变镜头合同的无付费链路由新控制面完成；旧 API 可兼容读取；G1—G4 通过，D01 所需的租户隔离、基础会话、KMS 和私有媒体达到 G5 最小生产前置，完整企业安全认证仍在 W5 闭环。

---

## 10. W3：流程、任务、GPU 与 Python 执行（功能波次；排期以3.4 IMS为准）

### 10.1 D06 持久任务、Kafka 与 GPU 资源

- **当前输入：** BatchJob、SeriesProductionRun、Image/Video/TTS/Synthesis Job、进程内后台任务。
- **目标服务：** `execution-control-service` + 无第二业务账本的 `provider-egress-service`（或经 ADR 批准的 D06 内部组件）。
- **数据所有权：** D06唯一拥有Job、Attempt、幂等、追加式`WorkerLease`历史（SUBMIT/MONITOR/PERSIST/RECONCILE）、Worker/GPU/死信、`ProviderOperation`根和`ProviderOperationEpoch`历史。根按`tenant_id + side_effect_base_key + execution_generation`幂等唯一，并生成logical_side_effect_key；确认未受理的技术重试在同一根升epoch，已受理后权威运行失败的重新执行必须增加execution_generation并创建带source operation血缘的新根/新预算。Epoch创建时绑定attempt/provider/request/credential但submit lease/fence/site为空；Grant签发时从活动SUBMIT WorkerLease一次固化，后续MONITOR/PERSIST/RECONCILE接管只追加WorkerLease，不覆盖授权快照或旧Epoch四水位。同一epoch仅一活动/已消费Grant。D06还拥有外呼水位、供应商状态核对和reservation引用；Egress不建第二账本；D06不写财务流水。
- **状态：** Job只采用用户/编排聚合态`CREATED/RESERVED/REJECTED/QUEUED/RUNNING/PAUSE_PENDING/PAUSED/RETRY_WAIT/UNKNOWN_REQUIRES_RECONCILIATION/HUMAN_REVIEW/CANCEL_PENDING/CANCELLED/SUCCEEDED/FAILED_FINAL`；Attempt独立采用`CREATED/LEASED/SUBMITTING/RUNNING/PERSISTING/SUCCEEDED/PAUSE_PENDING/PAUSED/FAILED_RETRYABLE/FAILED_FINAL/UNKNOWN_REQUIRES_RECONCILIATION/CANCEL_PENDING/CANCELLED`。当前Attempt状态仅作只读投影。`FAILED_RETRYABLE`后创建新Attempt但重试类型不同：确认未受理则同根新epoch；已受理后有权威终态失败且旧费用收敛，则新execution_generation/根/逻辑键/Provider幂等键/预算；状态不明不得自动重试。质量修复另建Repair Job，不向SUCCEEDED源Job追加Attempt。
- **切换单元：** 任务创建时间 + `execution_backend`；旧任务由旧执行器继续 Poll/下载，但域切换后必须经 `legacy-completion-adapter` 向新所有者提交结果，不能继续写旧任务/资产/财务表；新任务进入新引擎。
- **事件：** 生产 `execution.attempt.execute-requested.v1`、`execution.provider-operation.reconciliation-required.v1` 和 `asset.finalization.requested.v1`，消费 Worker 的 `execution.attempt.lease-reported.v1`/`execution.attempt.result.reported.v1` 及 Asset 的 `asset.finalized/quarantined.v1`；所有Claim/Receipt/Result携带 `provider_operation_id + operation_epoch + attempt_id`。验证当前epoch/fencing、Manifest和匹配定稿事实后，任何Attempt失败均由D06发布带`retryable=true/false`的`execution.attempt.failed.v1`，仅在Job真正成功或最终失败时发布`execution.job.completed.v1`/`execution.job.failed.v1`；job.completed只表示该Job输出已定稿并开启质量门，不等于质量/ProductionRun通过。旧epoch晚到回执只追加历史/触发对账，不推进当前Attempt。Payload以总体架构及D06子计划为唯一Schema来源。
- **测试：** 覆盖五宕机窗口、重复创建、Grant响应丢失、双D06/双Egress、乱序/站点/RPO/账务/取消/GPU故障；PREPARED epoch提交授权为空，Grant事务一次固化SUBMIT lease/fence/site，Grant签发后租约失效或fence换代时Egress拒绝，后续MONITOR/PERSIST/RECONCILE只追加WorkerLease；确认未受理时单事务创建新Attempt+空授权PREPARED epoch/失效旧Grant/CAS根/Outbox；已受理后权威运行失败时先隔离晚到/收敛旧费用，再以新execution_generation/根/键/预算重跑；Provider终态不明时不得新建代次。旧epoch和授权快照不变，D06/D13双向100%守恒。
- **回滚：** 停止新入口并排空；已受理任务继续轮询；不得跨引擎重复提交。
- **退出：** 重启/扩容不丢任务；同一幂等键只有一个付费提交和有效定稿；所有状态可解释。

### 10.2 D07 分镜、镜头与不可变生产合同

- **当前输入：** Storyboard、Shot、Workflow、Production Card、Story Lock、SeriesProductionRun、模型快照。
- **目标服务：** `creative-domain-service` 合同模块。
- **数据所有权：** 分镜、镜头、Episode/Shot Contract、版本、锁以及内容合同依赖/失效关系。
- **切换单元：** 系列运行/单集。
- **事件：** `storyboard.versioned.v1`、`creative.contract.locked.v1`、`shot.contract.versioned.v1`、`shot.contract.invalidated.v1`。
- **测试：** 镜头编号唯一、乐观锁、合同哈希、资产/模型快照完整、影响分析和可重放。
- **回滚：** 新合同失败时新增 superseded 版本；旧运行保持原合同。
- **退出：** 执行任务完全由合同重放，不在运行期读取“当前最新配置”。

### 10.3 D08 Flowable 生产流程与人工门禁

- **输入：** 生产合同、任务状态、质检结果、人工审批和修复决策。
- **目标服务：** `production-orchestrator`。
- **数据所有权：** 流程定义/实例、业务键、人工任务及其完成记录、阶段决策和补偿意图；内容审批结果由 D03 写，媒体任务明细不进入 Flowable 作为真相。
- **事件：** `workflow.stage.requested.v1`、`workflow.stage.completed.v1`、`workflow.stage.blocked.v1`、`workflow.human_review.requested.v1`、`workflow.human_review.completed.v1`。
- **测试：** BPMN 版本、重复回调、超时、补偿、人审并发、权限和进行中实例升级。
- **回滚：** 进行中实例固定原定义；新实例使用回退版本。
- **退出：** 流程状态与执行状态不混用；每个阻断有责任人和恢复动作。

### 10.4 D09 Python AI 执行器与供应商适配

- **当前输入：** `backend/app/features/model_drivers/`、火山/MiniMax/七牛等服务、TTS/图像/视频/媒体代码。
- **目标路径：** `backend/app/workers/` 及稳定公共 Facade；满足独立发布后再拆为独立制品。
- **数据边界：** Worker只持可丢缓存/回执/Manifest，不写企业主表、不持生产Provider凭据且禁止直连Provider。Egress调用D06 CAS，校验请求epoch等于根current_epoch、唯一ACTIVE Grant、合同/逻辑键/Provider/endpoint/凭据版本及epoch固化的submit lease/fence/site、对应SUBMIT WorkerLease仍ACTIVE/fence当前、`outbound_started_at IS NULL`后才外呼。Claim/Receipt携带provider_operation_id+operation_epoch+attempt_id；后续接管凭当前追加式阶段租约鉴权，但不得修改submit授权快照。本地状态不是真相。
- **事件：** 消费按 capability 拆分的 `execution.attempt.execute-requested.v1`；生产 `execution.attempt.lease-reported.v1` 和 `execution.attempt.result.reported.v1`；不直接宣告业务 Job 成功/失败，也不自行定义第二套任务状态。
- **测试：** Provider Fixture、参数白名单、429/5xx/超时分类、限流、脱敏、真实 Canary、Manifest 和驱动回退。
- **回滚：** Worker/模型驱动版本回退，任务合同不变。
- **退出：** 所有供应商调用经过统一驱动；endpoint 不直接调用 SDK；真实与模拟证据清楚区分。

### 10.5 D13/D14 最小付费与审计前置切片

在任何小额真实 Canary 或新付费任务之前，必须先交付：

- D13 唯一写入的预算额度、预留、结算、释放、冲正和最小 Provider Cost/Usage 流水；
- D06 只保存 `reservation_id` 和任务操作状态，不维护余额或成本账本；
- D13 的 Reservation/LedgerEntry/结算/释放/退款/冲正及其 Outbox/Inbox 与 D06 不可丢引用共同进入逻辑 RPO=0 仲裁；恢复后双向 100% 对账，悬空引用或余额/流水回退时保持付费冻结；
- Provider Submit 前完成预留，结果/失败/取消按幂等事件结算或释放；未知状态隔离结算；
- Provider已受理后的权威运行失败若获准重新执行，D13必须先按`source_provider_operation_id + next_execution_generation`幂等收敛旧费用并建立新预留；不得复用旧reservation或把第二次真实执行记为技术重试；
- D14 的追加审计、Trace、Provider ID、模型快照、Manifest 和费用关联；
- 并发预留、重复回调、提交后宕机、部分结算和账单差异测试。

完整预算管理界面、月度对账、经营报表和 SLA 看板仍在 W5 完成，但不能以此为由推迟付费安全基础。

### 10.6 执行清单

- [ ] 创建 D06—D09 子计划和故障注入矩阵。
- [ ] 建立任务/Attempt、`SUBMIT/MONITOR/PERSIST/RECONCILE` 租约、fencing、DLQ、资产定稿回执和对账状态机/合约测试；Attempt 只有消费匹配 `asset.finalized` 后才成功。
- [ ] 建立ProviderOperation根和Epoch表；根按tenant+side_effect_base_key+execution_generation唯一并只CAS切current_epoch。Epoch创建时submit授权为空，绑定attempt/provider/request/credential/Grant/四水位；Grant签发事务从活动SUBMIT WorkerLease一次固化submit lease/fence/site。后续阶段租约写追加式WorkerLease历史，旧Epoch/授权快照不可覆盖。
- [ ] 确认未受理的技术重试仅在旧epoch终态后单事务创建新Attempt+空授权PREPARED epoch、失效旧Grant、切根和写Outbox；已受理后的PROVIDER_FAILED/EXPIRED只有终态/晚到隔离/费用收敛/策略预算全通过，才通过RetryIntent+D13新预留创建新execution_generation/ProviderOperation根/逻辑键/Provider幂等键和source operation血缘；状态不明转人审。
- [ ] Grant签发按provider_operation_id+operation_epoch+request_contract_sha256幂等，同一epoch最多一个ACTIVE/CONSUMED Grant；Claim/Receipt/Callback必须带epoch+attempt，拒绝旧epoch推进当前状态。
- [ ] 建立无第二业务账本的 `provider-egress-service` 和 D06 Grant/ProviderOperation 权威消费 CAS；CAS 仅在 `outbound_started_at IS NULL` 且副作用水位允许时一次成功。五窗口、签发响应丢失、双D06/双Egress及站点分区演练均不得二次提交。
- [ ] 把 ProviderOperation、Grant消费、Attempt外呼水位、活动site_epoch、D06 reservation引用、D13权威Reservation/LedgerEntry/结算/释放/退款/冲正及双方相关Outbox/Inbox纳入逻辑RPO=0安全账本；仲裁不可用或双向100%对账不通过时冻结真实付费派发，并证明旧站点出口/身份/凭据已撤销。
- [ ] 建立 Worker 注册、能力/显存标签和心跳；Provider 凭据仅由 Egress 工作负载身份解析，Worker 不得解析生产长期凭据。
- [ ] 把现有 Provider 调用封装到执行合同后面，不改其已验证参数语义。
- [ ] 建立 Flowable 版本化生产流程和人工门。
- [ ] 使用模拟供应商完成重复/乱序/宕机测试，再以小额真实 Canary 验证。
- [ ] 按任务创建时间切换，旧任务旧引擎跑完。
- [ ] 完成 DEMO-6.4-a—g 新链路预演，后台真实展示任务编号、执行时间、资源消耗、生成/执行状态、进度和异常日志；暂停/恢复/失败重试均与状态机一致。

### 10.7 里程碑 MS-EXEC / MS-06M

`MS-06M` 的法定截止是 BD-001 确认的起算日加 6 个日历月，不自动等于第 26 周。P50 骨架要求开发候选最迟 W22 就绪，W23—W26 留给预演、UAT、整改、复验和签署；若实际日历截止更早，必须前移资源/范围或走合同变更，不得挤掉恢复、安全和质量门。范围为：

- Spring Cloud Alibaba 微服务骨架、Milvus、CI/CD 和目标环境；
- 剧本解析、角色/资产管理、Production Bible 和不可变镜头合同；
- 基础视觉一致性微调控制 MVP 与真实金标检测，不使用占位分；
- 持久任务、GPU 资源、暂停/恢复/取消/安全重试和在途任务登记；
- D13/D14 最小预算、费用、审计和 Trace；
- 一个可实际运行的最小端到端片段、V1 兼容、源码和算法文档；
- `DEL-D15-UI-MIN`：上述MVP页面的采购UI库采用/书面等效结论、响应式断点、入口安全、最小BFF投影及E2E证据；全量页面和退役仍由D15在12个月包闭环。

完整多轨对齐、复杂时间线、自动修复、60 批/1200 分钟和全部工业指标属于第二阶段 W4—W6，除非 `BD-001` 的书面结论另行扩大 6 个月门。MS-EXEC 同时要求旧任务安全收尾、无重复付费，G4/G6 通过。

---

## 11. W4：声音、质量、修复、时间线与交付（功能波次；排期以3.4 IMS为准）

### 11.1 D10 声音、TTS、字幕与强制对齐

- **当前输入：** 角色声线、声音样本、TTS Job、字幕和现有音频处理。
- **目标服务：** `model-factory-service` 写 Voice Profile/模型绑定，`asset-service` 写授权音频对象，`quality-delivery-service` 写 Alignment Contract/Result；Python `speech-worker` 只执行。
- **数据所有权：** 依照 3.1 矩阵分属 D05/D04/D11，不建立 Java/Python 共享声音表。
- **切换单元：** 租户 + Voice Profile 版本 + TTS Pipeline 版本；已创建任务继续原快照。
- **目标：** Voice Profile、授权、零样本情感 TTS、剧本情绪到语调/语速/停连/韵律/拟真语气的版本化映射、画面/对白/BGM/字幕四轨统一时钟、字词时间戳和 Alignment 报告。
- **事件：** `voice.profile.certified.v1`、`speech.generated.v1`、`audio.alignment.completed.v1`。
- **测试：** 授权、零样本音色相似/可懂/情感自然盲评、情绪到TTS参数映射、长文本切分、幂等、四轨锚点和签署的 p50/p95/p99 同步误差。
- **回滚：** 按 Voice/TTS Pipeline 版本路由；旧片段保持只读。
- **退出：** 验收镜头均有真实对齐证据，不以单个音频区间冒充毫秒同步。

### 11.2 D11 一致性质检、动态校准与定向修复

W1 已提供内容合规前置门；本阶段扩展生成结果/成片合规、身份/服饰/动作/坏帧/同步质量及定向修复。

- **当前输入：** QualityEvaluation、StudioReview、现有视觉一致性结构和人工审核。
- **目标服务：** `quality-delivery-service` 质量模块 + `quality-worker`。
- **数据所有权：** 内容合规策略/判定/人工放行、质量策略、检测版本、结果、缺陷、人工金标、动态防漂移校准策略、缺陷到允许参数调整映射和修复决策。
- **状态：** `PENDING → PASS / REPAIRABLE / HUMAN_REVIEW / BLOCKED`。
- **事件：** `quality.evaluation.completed.v1`、`quality.defect.detected.v1`、`quality.repair.requested.v1`、`quality.human_accepted.v1`；RepairRequest携带`source_job_id/source_attempt_id/source_asset_id/repair_plan_id/repair_generation`，D06幂等创建新的Repair Job+首个Attempt，不向SUCCEEDED源Job追加Attempt。
- **测试：** 固定盲测上的准确率/召回率、阈值确定性、角色漂移与算法漂移分离、误报/漏报；注入缺陷后核对参数差异、预算/修复代数/尝试上限、RepairRequest幂等、新Repair Job/Attempt与源血缘、新逻辑副作用键和选择性重生范围；源Job/Attempt/资产终态不改变。
- **回滚：** 可经批准切为“只提示不阻断”，但必须显式标记；合同要求阻断时不能关闭检测过验收。
- **退出：** 占位/RGB 评分不参与放行；所有阈值有数据集和审批；缺陷只重生正确镜头。

### 11.3 D12 时间线、FFmpeg 渲染与交付

- **当前输入：** Timeline、SynthesisJob、镜头媒体、TTS、字幕、`ffmpeg_local_renderer.py`。
- **目标服务：** `quality-delivery-service` 交付模块 + `render-worker`。
- **数据所有权：** 情感/节奏驱动 Camera/Transition Plan、一键粗剪/精剪版本、时间线轨道/片段、SFX生成/检索和BGM匹配/权利/节拍、PIP/多机位/转场/关键帧、渲染任务、交付包和校验和。
- **事件：** `timeline.compiled.v1`、`delivery.render.completed.v1`、`delivery.package.ready.v1`。
- **测试：** 粗剪/精剪无人工运行与首版接受率、情绪/节奏驱动策略、SFX/BGM匹配及权利、PIP/多机位、xfade、关键帧、ducking、响度、字幕、四轨同步；ffprobe 与像素/音频 Golden。
- **回滚：** 通过 `renderer_version` 选择旧渲染器；历史交付物不覆盖。
- **退出：** PIP、转场、多轨等真正进入 FFmpeg 图；成片可由 Timeline Contract + Manifest 重放。

### 11.4 执行清单

- [ ] 创建 D10—D12 子计划、金标数据说明和验收公式。
- [ ] 建立 Voice/Alignment/Quality/Timeline/Delivery 合同和版本。
- [ ] 替换占位质量放行，建立人脸/服饰/动作/坏帧/同步检测器。
- [ ] 建立机器+人审冲突、动态防漂移校准、缺陷分类→批准参数调整→RepairRequest→新Repair Job+Attempt→复检流程；以repair_plan_id+repair_generation幂等，记录source_job/source_attempt/source_asset，禁止向成功源Job追加Attempt；超过幅度/预算/次数进入人审。
- [ ] 建立情绪/节奏驱动运镜转场、一键粗/精剪、SFX生成/BGM自动匹配、完整 Timeline Compiler 和 FFmpeg Golden 测试。
- [ ] 完成 DEMO-6.2-0 及 DEMO-6.2-a—e、DEMO-6.3-a—g、DEMO-6.5-a—k 新链路证据；逐子项关联任务、参数/模型、后台记录、质量/同步结果、修改记录和最终对象哈希。

### 11.5 里程碑 MS-MEDIA

五项业务演示均可由新链路完成；每项均有任务 ID、模型/Prompt/合同、日志/Trace、GPU/供应商记录、质量报告、成片和哈希。

---

## 12. W5：成本、审计、运营、安全和前端（功能波次；排期以3.4 IMS为准）

### 12.1 D13 预算、用量、成本、额度与对账

W3 已完成最小预留/结算/冲正切片；本阶段扩展完整额度、供应商账单、经营和月度对账能力，不迁移财务所有权。

- **当前输入：** 任务成本、预算字段、供应商 Usage/账单及现有商业化表。
- **目标服务：** `usage-audit-report-service` 账务模块。
- **数据所有权：** 预留、结算、释放、退款、冲正、Usage、Quota、Provider Reconciliation；金额使用 Decimal/人民币分。
- **事件：** `budget.reserved.v1`、`budget.settled.v1`、`budget.released.v1`、`usage.recorded.v1`、`provider.cost.reconciled.v1`。
- **测试：** 并发预留、重复回调、失败释放、部分结算、退款、精度和月末对账。
- **回滚：** 可停止收费和新任务；流水只允许冲正，不删除/覆盖。
- **退出：** 每个付费任务贯通预计、预留、供应商消费、结算和差异。

### 12.2 D14 审计、指标、告警与 SLA

W1/W3 已提供生产前置的最小审计和 Trace；本阶段扩展长期指标、告警、SLA、Spark 报表和合规导出。

- **输入：** 所有领域事件、HTTP Trace、GPU、队列、供应商、费用和质量指标。
- **目标服务：** `usage-audit-report-service` 审计/报表模块 + OTel/Prometheus/Grafana/Spark。
- **数据所有权：** 该服务唯一写追加审计事实、SLA 证据和报表定义；运行指标/日志由可观测平台保存且不得反写业务状态。
- **输出：** 追加审计、看板、告警、日报、事故和 SLA 证据。
- **事件：** 消费各领域 `audit.entry.requested.v1` 和受控指标事件；追加持久化成功后生产 `audit.event.recorded.v1`；审计失败不得静默丢弃。
- **测试：** Trace 完整率、日志脱敏、Synthetic 故障、告警到达、RPO/RTO 和日报核对。
- **回滚：** 观测故障不应使安全执行产生重复副作用，但缺少观测证据的版本不得发布。
- **退出：** 请求、流程、镜头、任务、供应商、费用和产物共用关联 ID；支持流程可演练。

### 12.3 D15 Gateway/BFF 与前端兼容迁移

- **当前输入：** Next.js 页面、`frontend/src/lib/api-client.ts`、现有 feature 和 `/api/v1`。
- **目标：** 浏览器只经 CDN/WAF/Ingress，入口再分流 `frontend-web` 和 Gateway；SSR 只经内部 mTLS Gateway；Gateway 按租户/项目/API 路由；前端按领域 Facade/Feature Flag 切换，拆解热点但不同时改业务语义。
- **数据所有权：** 无；Gateway/BFF/前端禁止直写领域数据库或拥有第二份业务真相。BFF 每个投影登记用途/页面、最小字段/数据等级、来源Topic/Group/Offset/aggregate version、最大陈旧度、租户/角色过滤、缓存键、重建顺序及撤权传播时限；未登记视图不得同步扇出或读他域库。
- **测试：** OpenAPI 消费者合同、旧响应快照、入口不可绕过、SSR Cookie/CSRF/CSP、跨租户缓存隔离、BFF全量重建/陈旧度；采购列举的 Element UI/Ant Design 等 UI 库采用情况和组件清单，响应式断点、视觉/可用性/无障碍、Playwright、慢网、长任务断线恢复；若不采用原列库，必须取得书面等效性评审结论。
- **回滚：** 每页面/API 有独立路由开关；前端回滚不能改变已切换的数据写入者。
- **退出：** 核心流程使用新后端；旧客户端在兼容期可用；前端不拥有服务端业务规则；`TEST-UI-STACK`、入口信任边界和BFF投影重建通过。

### 12.4 安全、IP 和运维专项

- [ ] 在 W2 已有租户隔离、基础 OIDC/会话、KMS 和私有媒体上，完成 MFA、细粒度 RBAC/ABAC、mTLS、策略治理和企业安全认证。
- [ ] 完成 SAST、DAST、依赖/SBOM、Secret、容器、镜像签名和渗透测试。
- [ ] 完成数据分类、留存、删除、法律保留和版权撤回演练。
- [ ] 按采购原文建立并演练 7×24 电话/邮件/远程支持；一般故障4小时内解决，远程无法解决时8小时内到场、24小时内解决；安全漏洞“无条件及时修补”保留原文，并在补充协议中只补充计时、地点、严重度、第三方依赖和证据，不得用内部SLA分级弱化原文。
- [ ] 按导演、美术、音频、审核、管理员和运维形成线上+线下课表、环境/练习、考核标准、签到/录屏和不通过补训；只分发手册不得签培训完成。
- [ ] 形成背景 IP、定制 IP、开源/第三方、模型/素材、可转让/仅许可清单。
- [ ] 预制 `DEL-IP-01` 权利转移清单和双方有权主体签署页；原文验收触发后 T+10 工作日内完成归属权转移及证据追加闭包，背景IP/第三方例外只能引用BD-005正式偏离。
- [ ] 与法务形成第三方侵权通知、证据保全、交涉授权、停用/替换、责任/费用/赔偿、保险和采购方协作 Runbook；保持原文义务并由 BD-012 锁定边界。
- [ ] 完成大模型 API、云渲染农场、数字资产版权链三类标准接口的真实受控调用、回调防重放、费用/权利对账和故障降级证据。
- [ ] 建立 `DEL-SVC-EVOLUTION`：持续模型量化、剪枝和推理/渲染性能调优；每轮保存基线、制品版本、精度/质量/时延/成本变化和回退；Prometheus/Grafana/Trace 展示长期趋势，并在服务期末形成最终技术演进报告。

### 12.5 里程碑 MS-OPERATIONS

适用的 G0—G7 在预生产环境通过，G8 的退役准备度（旧调用清单、在途登记、观察/归档/撤权方案）通过；G8 只能在 W6 生产 100% 灰度及两个稳定发布周期后签署。

---

## 13. W6：灰度、60 批/1200 分钟和工业验收（功能波次；排期以3.4 IMS为准）

IMS 中 W38—W52 假定第二阶段截止时间从项目生效累计计算；原文也可能被解释为第二阶段自身不超过 12 个月。`BD-001` 未书面关闭前，第 52 周只是 P50 项目排期，不是对合同起算点的解释。

### 13.1 规模验收前置

- [ ] 双方先保留原文“60 个批次、总计 1200 分钟的漫剧生成测试数据集”，再签署其中批次、分钟、合格/失败/重生、抽样、硬件、并发、质量、成本和人工干预的解释口径。
- [ ] 固定输入数据、内容权利、模型/Prompt/配置和 GPU 规格。
- [ ] 计算生成/API/GPU/存储/CDN/标注/人审预算并确认承担方。
- [ ] 完成小样本门禁和预生产故障门禁。
- [ ] 冻结验收版本、镜像 Digest、数据库版本和配置版本。

### 13.2 三层验收

1. **小样本门禁**：固定剧本、至少 10 镜头、身份/服饰/动作/声音和完整血缘；
2. **预生产门禁**：多批并发、Worker/GPU 故障、暂停/恢复、供应商超时、数据回滚；
3. **最终门禁**：按已签署解释执行 60 批/总计 1200 分钟测试数据集、压力/长稳、质量抽检、成本、人工干预、安全和 SLA；未签署前不得擅自改写为“1200 合格分钟”。

### 13.3 执行清单

- [ ] 按内部、1%、5%、25%、50%、100% 完成租户/项目灰度。
- [ ] 每个灰度阶段核对 API、数据、媒体、任务、费用、质量和告警。
- [ ] 按签署口径执行 60 批/总计 1200 分钟漫剧生成测试数据集并生成不可变 Evidence Manifest。
- [ ] 执行压力、耐久、扩缩容、混沌、备份恢复和安全测试。
- [ ] 计算身份/服饰漂移、坏帧、同步、首过率、返工、GPU、成本和人工干预。
- [ ] 完成采购方 UAT、培训、源码/IP/文档/日志和运维交接。
- [ ] 按 BD-011 确认的规则重验 DEMO-6.1—6.5，每个原文 bullet 均关联任务/版本/日志/媒体/指标，不以早期录像替代当前候选版本。
- [ ] 观察两个稳定发布周期，确认旧写流量为零后退役。

### 13.4 里程碑 MS-INDUSTRIAL/MS-RETIRE

- **MS-INDUSTRIAL：** 需求主追踪矩阵所有在本阶段验收的项目均有原始证据和签署结论；
- **MS-RETIRE：** 旧写入口、旧队列和不安全媒体访问退役；历史查询、归档、法定留存和前向恢复仍可用。

---

## 14. 切换 Runbook

### 14.1 切换前 7—2 日

1. 冻结本批次 Schema 和功能；
2. 确认源/目标备份、恢复演练和回滚负责人；
3. 确认在途供应商任务、账务、对象和 DLQ 清单；
4. 执行全量 Dry-run 和最终增量演练；
5. 为本切换单元生成 `cutover_epoch`；涉及外部副作用时，先在仲裁权威源准备下一全局 `site_epoch`、活动出口和旧站点身份/凭据撤销清单。部署服务端写入者登记和写栅栏；准备按域/表/租户生效的数据库账号权限、保护触发器或应用保护，不能把仍承载其他域的共享旧库整体设为只读；
6. 将旧 Worker/Webhook/XXL-JOB 的在途完成路径改到 `legacy-completion-adapter`，验证其能向新所有者幂等提交且不能绕过写栅栏；旧Worker不得持可复用Provider凭据，晚到Submit必须被Egress的Grant/fence/site校验拒绝；
7. 确认 Feature Flag、Gateway 路由、只读开关、反投影工具和首次新写后的 no-return 分类；
8. 确认监控、告警、支持频道和业务观察人员；
9. 由产品、数据所有者、财务、Provider Owner、SRE、安全、QA 和领域负责人签署 Go/No-Go。

### 14.2 切换窗口

1. 对切换单元进入短暂停写；
2. 激活 `cutover_epoch` 和旧通用写者栅栏，撤销本域旧写权限；涉及Provider时先原子提升 `site_epoch`、封禁旧站点出口/身份/凭据并验证旧Grant无效，再允许新站点签发Submit Grant；旧在途完成只允许通过 Adapter；
3. 验证旧 HTTP、Worker、Webhook、定时任务和直接数据库写均被拒绝，同时未迁移领域仍可正常写；
4. 等待旧事务、CDC/Outbox 和 Kafka 追平；
5. 记录最终高水位、行数、状态、金额、在途登记册和对象 Manifest；
6. 运行零差异核验，并验证重复旧回调只命中 Inbox；
7. 原子切换写入者登记和 Gateway 路由；
8. 在外部流量仍冻结时执行 Smoke：认证、读、写、幂等、权限、媒体、任务、账务和审计；
9. 按灰度逐级恢复流量；
10. 保持本域旧表/写入口只读。只有全部领域退役时才把整个旧数据库设为只读并撤销共享凭据。

### 14.3 切换后观察

- 15 分钟：错误率、鉴权、写入、Kafka、数据库、对象、任务；
- 1 小时：状态守恒、供应商提交、费用、媒体和 Trace；
- 24 小时：影子差异、质量、业务投诉、告警和报表；
- 7/14 天：灰度稳定窗口、恢复演练、兼容调用和退役资格。

### 14.4 立即停止扩大灰度的条件

- 出现无法解释的任务状态；
- 存在未接管的在途供应商任务；
- 发生重复供应商提交、重复扣费或双份定稿；
- 关键 ID/金额/哈希不守恒；
- 媒体缺失、哈希不一致或跨租户访问；
- 新旧响应超出批准差异；
- 凭据无法解密但仍被任务使用；
- 告警/Trace 不可用导致无法判断生产状态；
- 无法在批准 RTO 内恢复服务。

---

## 15. 回滚与前向恢复

### 15.1 回滚边界

| 阶段 | 允许动作 |
|---|---|
| 切换前 | 恢复旧镜像/源数据库；丢弃可重跑的目标影子数据 |
| 已切换但无新业务写入 | 路由切回旧写者并核对高水位 |
| 已有新业务写入 | 默认前向修复；如恢复旧写者，必须先反投影新变化并核对 |
| IAM/财务/审计已新写 | 只允许前向修复或批准的兼容代理，不删除新事实 |
| 供应商已受理 | 继续查询/下载/对账，不重新提交，不通过数据库回滚抹除费用 |

每域切换单必须在首次新写前选择一种恢复类别：

- **R1 路由可回退：** 尚无新写或新写只进入可丢弃影子投影；
- **R2 限时反投影：** 提供已演练的反投影命令、字段映射、最大数据窗口和核对报告，完成后才允许恢复旧写者；
- **R3 只前向修复：** IAM、财务、审计、版权删除/法律保留等默认采用，首次新写即为 no-return point，只能通过新版本、冲正或兼容代理恢复服务。

未明确恢复类别、命令、最大窗口、批准人和演练证据的领域不得切换。

### 15.2 技术回滚

- 应用：蓝绿/Canary 路由回上一镜像 Digest；
- 数据库：只使用向后兼容 Expand 结构；Contract 删除在两个周期后单独执行；
- Kafka：暂停消费者、修复后从已知 Offset 重放；Inbox 防止副作用重复；
- 对象：保留源/目标对象和 Manifest，数据库指针可回切；
- Worker：按 `execution_backend` 和任务创建时间隔离版本；
- 前端：按领域 Feature Flag 回退 UI，数据写入所有权不随页面回退；
- Flowable：进行中实例固定原版本，新实例使用回退定义。

灾备/站点切换不是普通应用回滚：ProviderOperation根/base key/generation/current_epoch、Epoch四水位/submit授权快照、WorkerLease历史、Grant消费、Attempt外呼、活动site_epoch、D06 reservation引用、D13权威财务聚合及双方Outbox/Inbox必须按逻辑RPO=0恢复；一般RPO不得覆盖。恢复后冻结新外呼，扫描Provider/Usage/账单/Manifest，并按旧/新execution_generation对D06引用与D13聚合双向100%核对；代次/纪元断裂、悬空、余额/流水回退或旧站点仍可提交时不得开放。Provider无法覆盖故障窗时保持人工冻结。

### 15.3 退役

退役必须是独立变更：先拒绝旧写、观察、归档、撤销凭据和网络，再移除代码/表/对象。任何删除均需数据所有者、安全、法务/保留策略和恢复方案批准。

退役台账逐项登记：`retirement_id`、旧 API/Worker/Queue/Topic/Table/Bucket/Credential/Caller、所属域和Owner、最后业务调用/写入时间、兼容调用分母、在途/DLQ/回调状态、归档位置与hash、保留期/法律冻结、写权限/网络/凭据撤销、恢复或历史查询方法、观察窗口、G8证据、DATA_OWNER/SEC/LEGAL/FIN/PROVIDER批准人及执行日期。任何调用方未知、最后调用仍在观察窗、在途未闭合或恢复证据缺失的项保持 `BLOCKED`，不得删除。

---

## 16. 团队、RACI、工作量和预算

### 16.1 ROM 工作量

| 成本账户 | 工作包 | 人日 ROM |
|---|---|---:|
| CA-GOV | 项目治理、合同澄清、总体架构 | 80—120 |
| CA-PLATFORM | 平台、K8s、Gateway、Nacos、Kafka、存储 | 160—240 |
| CA-IAM | IAM/组织/RBAC | 120—180 |
| CA-CONTENT | 内容与 Production Bible | 220—320 |
| CA-STORYFLOW | 分镜、合同与 Flowable | 180—260 |
| CA-ASSET | 资产、媒体与版权 | 160—240 |
| CA-MODEL | 模型工厂 | 160—240 |
| CA-EXEC | 持久任务与 GPU 调度 | 240—360 |
| CA-PY | Python 供应商执行器 | 100—160 |
| CA-QUALITY | 一致性质检与修复 | 220—340 |
| CA-AUDIO | TTS、声音与对齐 | 120—180 |
| CA-MEDIA | 时间线、渲染和交付 | 180—280 |
| CA-FIN | 预算、费用和对账 | 100—160 |
| CA-SEC | 安全、审计、观测和 SLA | 160—240 |
| CA-FE | 前端/BFF 兼容迁移 | 180—260 |
| CA-MIG | 数据清洗、迁移、切换和归档 | 180—280 |
| CA-QA | 独立 QA、性能、安全与 UAT | 220—320 |
| **CA-TOTAL** | **合计** | **约 2780—4180 人日** |

该估算误差至少 ±30%，对应约 126—190 人月。3.4 IMS 的 WP 只引用这些成本账户：`MIN/Adapter/组包/UAT` 标记表示包含在对应 CA 中，不得再次求和；任何新增增量必须先建立新 CA/变更单。合理全量周期为 9—14 个月。48.5 万元无法同时覆盖上述开发、GPU/API、1200 分钟样本、标注/质检、测评、驻场、培训和长期 7×24 服务；必须按合同阶段重新限定范围和 OPEX。

### 16.2 推荐团队

峰值 20—21 人：产品/甲方验收 1、项目经理 1、总架构师 1、数据迁移/DBA 1、Java 4—5、Python/AI 3、CV/音视频算法 2、前端 2、SRE 2、QA 2、安全 1；导演、美术、音频和法务/IP 专家按里程碑投入。各波次按依赖分阶段投入，不表示 20—21 人在 9—14 个月内始终满配。

### 16.3 P50 人力装载与风险情景

下表按累计日历而非重叠波次相加，1 人月按 22 人日折算：

| 累计期间 | 主波次/关键门 | 平均核心 FTE | 人月 | 人日 |
|---|---|---:|---:|---:|
| Month-01 | W0 合同/基线/恢复 | 8 | 8 | 176 |
| Month-02—03 | W1/W2 平台与控制面 | 12 | 24 | 528 |
| Month-04—06 | W2/W3、MS-06M | 15 | 45 | 990 |
| Month-07—09 | W4/W5 质量/媒体/运营 | 17 | 51 | 1,122 |
| Month-10—12 | W5/W6 灰度/规模验收 | 13 | 39 | 858 |
| **P50 累计** | **12 个月目标基线** | — | **167** | **3,674** |
| Month-13—14 风险储备 | 算法、采购方等待、GPU/供应商、返工 | ≤10 | ≤20 | ≤440 |
| **风险情景累计** | **14 个月** | — | **≤187** | **≤4,114** |

P50 与 2780—4180 人日 ROM 一致；较低情景依赖高复用和范围收敛。峰值核心 FTE 约 17，叠加采购方验收、导演/美术/音频、法务/IP 等 3—4 名阶段参与者形成 20—21 人峰值项目配置。

12 个月成立的前提是：需求和阈值在 W0 冻结、采购/安全评审按约定时限反馈、GPU/模型账号/数据提前到位、没有双栈中间件、各域按前置门并行、算法 MVP 达到金标、采购方按计划参加 UAT。任一前提失效，使用 Month-13—14 风险储备或正式变更范围，不能通过压缩恢复、安全或质量门追赶日期。

### 16.4 角色×波次装载与非人力资源

下表是平均需求 FTE，不是已确认可用人员；V1.0 必须增加 Named Lead、实际 Available、Gap、入离场日期并做资源平衡：

| 期间/WP | 治理/架构 | Java | Python/CV/Media | FE | DATA/SRE | QA/SEC/SME | 合计 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Month-01 / WP-00 | 2.0 | 1.0 | 1.0 | 0.5 | 1.5 | 2.0 | 8 |
| Month-02—03 / WP-01—04 | 2.0 | 4.0 | 1.5 | 1.0 | 1.5 | 2.0 | 12 |
| Month-04—06 / WP-03—08 | 2.0 | 4.5 | 3.0 | 1.0 | 2.0 | 2.5 | 15 |
| Month-07—09 / WP-09—11 | 2.0 | 3.0 | 5.0 | 2.0 | 2.0 | 3.0 | 17 |
| Month-10—12 / WP-11—13 | 2.0 | 2.0 | 3.0 | 1.5 | 2.0 | 2.5 | 13 |
| Month-13—14风险 | 1.5 | 1.5 | 2.5 | 1.0 | 1.5 | 2.0 | ≤10 |

非人力资源工作表必须按 `阶段×capability/model` 登记 GPU 型号/数量/显存、并发、模型加载、Provider提交/轮询配额、存储/备份/出口、标注/人审、安全测评、采购 Lead Time、成本上限、降级和实测证据。以下项目在 W0 前只能是阻断占位：

| RES/EXT-ID | 提供方 | Needed by | 到位/验收 | 晚到影响 | Fallback | 状态 |
|---|---|---|---|---|---|---|
| EXT-REQ | 采购方/采购 | WP-00 | 完整文件/hash/第五章 | 无法冻结范围/演示/符合性 | 仅做缺口送审 | OPEN |
| EXT-SITE | 采购方/SRE | WP-01 | 地点、网络、证书、DNS、机房/云条件 | 平台/到场/SLA不可排 | 隔离云测试环境 | OPEN |
| EXT-DATA | DATA_OWNER/LEGAL | WP-03/04 | 数据、权利、金标、脱敏/留存 | 迁移/训练/验收阻断 | 合成数据只做工程测试 | OPEN |
| EXT-GPU | 采购方/SRE | WP-05/09/12 | GPU型号/数量/驱动/配额/压测 | 容量/算法/1200分钟延期 | 批准云GPU/缩范围 | OPEN |
| EXT-PROVIDER | PROVIDER/FIN | WP-06/07 | Sandbox/Prod账号、配额、账单/回调 | 无真实Canary/对账 | 替身不作验收 | OPEN |
| EXT-IDP-KMS | SEC/采购方 | WP-01/03 | IdP/KMS/Vault、身份/轮换演练 | IAM/Secret不可投产 | 隔离开发Secret | OPEN |
| EXT-UAT | PO/SME/QA | WP-08/12/13 | 名单、日历、数据集、反馈SLA | 6/12月签署无缓冲 | 正式变更日期 | OPEN |
| EXT-ASSESS | 采购方/SEC/第三方 | WP-11/13 | 测评范围、机构、窗口 | 安全终验延期 | 不声明金融/行业级 | OPEN |

### 16.5 RACI

缩写：PO=采购方/产品验收，PM=项目经理，ARCH=总架构，JAVA=控制面，PY/PY Lead=AI 执行及负责人，DATA=迁移/DBA，DATA_OWNER=业务数据所有者，FE/FE Lead=前端及负责人，SRE/SRE Lead=平台及负责人，SEC=安全，QA/QA Lead=质量验收及负责人，FIN=财务/账务所有者，LEGAL=法务/IP，PROVIDER=供应商关系/账号所有者，SME=导演/美术/音频专家；“领域 Lead”及 Execution/Ledger/Asset Lead 均指相应领域技术负责人。

| 工作 | A | R | C | I |
|---|---|---|---|---|
| 需求、范围、阈值 | PO | PM | ARCH、QA、SME | 全体 |
| 总体架构/边界 | ARCH | ARCH、领域 Lead | DATA、SRE、SEC | PO、PM |
| API/事件/数据合同 | ARCH | JAVA、PY、DATA | QA、FE、SRE | PM |
| 数据分级/迁移 | DATA_OWNER | DATA、领域 Lead | PO、SEC、LEGAL、QA、SME | PM |
| IAM/安全 | SEC | JAVA、SEC | ARCH、QA | PO |
| AI/质检/媒体 | PY Lead | PY、CV/媒体 | SME、QA、SRE | PM |
| 平台/GPU/灾备 | SRE Lead | SRE、JAVA、PY | ARCH、SEC、QA | PM |
| 前端/兼容 | FE Lead | FE、JAVA | QA、产品 | PM |
| 测试/证据 | QA Lead | QA、各 Lead | PO、SEC、SRE、SME | 全体 |
| 预算、费用和供应商对账 | FIN | Ledger Lead、JAVA、DATA | PO、ARCH、PROVIDER、QA | PM |
| 在途付费任务接管 | PROVIDER | Execution Lead、SRE、Ledger/Asset Lead | FIN、DATA、SEC、QA | PO、PM |
| 生产切换 | PO | PM、SRE、DATA | DATA_OWNER、FIN、PROVIDER、ARCH、SEC、QA、领域 Lead | 全体 |
| 旧系统退役 | PO | PM、SRE、DATA | DATA_OWNER、ARCH、SEC、LEGAL、FIN、PROVIDER、QA | 全体 |

RACI 每行只设一个 A；涉及数据删除/归档、法律保留、账务、Provider 在途时，Gate Board 的批准 quorum 仍必须包含相应 DATA_OWNER/LEGAL/FIN/PROVIDER 签署，不能因 RACI 单一 A 省略法定/业务授权。

### 16.6 项目治理、变更与进度计量

受控台账统一使用 ID、Owner、到期、影响 WP/Gate、证据和状态：

- **CR Register**：范围/工期/成本/数据/安全/IP影响、备选方案、CCB结论、基线/合同更新；未批准不得实施；
- **RAID Register**：风险原因—事件—影响、概率/影响度、触发器、缓解、应急、Owner和截止；Issue/Dependency/Assumption分别标识；
- **Decision Register**：BD/ADR/BASE、批准人、决策SLA、生效/失效日和受影响交付物；
- **Defect/Waiver Register**：严重度、复现、需求/证据、修复版本、复验、豁免期限/风险接受；
- **Cutover/Incident Register**：CW/epoch、高水位、Commander、Abort、恢复、复盘和行动项。

节奏：每日执行阻断同步；每周 RAID/IMS/资源/质量；双周架构与契约委员会；每月 Steering/预算/范围；每个 CR/WR/生产灰度/验收/退役由 Gate Board 签署。变更流程为“提出→影响分析→方案/估算→CCB批准/拒绝→更新需求/IMS/预算/测试/合同→实施→证据/关闭”。

进度只按已通过 Gate 的加权交付物计量，例如 CR 15%、RR 20%、SR 20%、WR 25%、EX 20%；代码行数、已建空服务、页面截图或勾选任务数不计完成度。每周报告同时展示计划值/实际值、关键路径浮时、FTE/资源缺口、缺陷和未关闭 BD/ADR。

---

## 17. 必须拆出的执行子计划

每个子计划保存在 `docs/superpowers/plans/`，并遵循 `superpowers:writing-plans`：正式域级 WBS 使用约 0.5—3 人日的可交付工作项，列出精确路径、接口/事件/Schema、失败测试、实现、验证、提交和决策点；具体编码执行时再拆为小步 TDD 清单，不把“2—5分钟”伪装为可排期的项目 WBS。

- [ ] `00-项目治理、需求追踪与验收基线`
- [ ] `01-平台基础、API事件合同与迁移工厂`
- [ ] `02-IAM组织工作区及RBAC迁移`
- [ ] `03-项目内容及Production-Bible迁移`
- [ ] `04-资产媒体对象存储及版权血缘`
- [ ] `05-模型工厂Prompt绑定及制品生命周期`
- [ ] `06-分镜镜头不可变生产合同及Flowable`
- [ ] `07-持久任务Kafka及GPU调度`
- [ ] `08-Python执行器供应商适配及对账`
- [ ] `09-视觉一致性质检及定向修复`
- [ ] `10-声音TTS字幕及强制对齐`
- [ ] `11-时间线FFmpeg渲染及交付`
- [ ] `12-预算用量成本额度及财务流水`
- [ ] `13-安全审计可观测性SLA及灾备`
- [ ] `14-Gateway-BFF与前端兼容迁移`
- [ ] `15-数据清洗回填灰度切换及旧系统退役`
- [ ] `16-在途付费任务登记接管与Legacy-Completion-Adapter`
- [ ] `17-六个月MVP阶段验收`
- [ ] `18-五项演示、60批1200分钟与工业验收`
- [ ] `19-ProviderOperation代次根/Epoch/提交授权与租约历史、唯一Submit-Grant、受理失败新代次、五窗口与站点灾备`
- [ ] `20-动态防漂移校准、缺陷调参重生与质量盲测`
- [ ] `21-大模型API、云渲染农场及数字资产版权链集成`
- [ ] `22-线上线下培训、源码IP移交与第三方侵权处置`
- [ ] `23-持续模型量化剪枝性能调优监控与技术演进报告`

### 17.1 统一子计划域卡模板

每个领域子计划必须按同一顺序填写，缺一项不得进入实现：

1. 意图锁、范围、非目标和对应需求 ID；
2. 当前源路径/运行证据、目标路径和复用/重写/归档清单；
3. 聚合、源写入者、目标写入者、Schema/账号和禁止访问边界；
4. 旧/新 API、事件、状态机、错误码和 V1 兼容映射；
5. 源表—目标表—字段—枚举—时区—精度—PII/IP 映射；
6. 数据画像、A/B/C/D 分级、Dry-run、幂等和核对公式；
7. 影子比较键、容差、切换分母、Feature Flag 和观察窗口；
8. 在途任务/回调/Provider/凭据/Manifest/费用处理；
9. `cutover_epoch`、服务端/数据库写栅栏、切换顺序和 Smoke；
10. R1/R2/R3 恢复类别、反投影命令、no-return point、最大窗口和批准人；
11. 失败测试、实现步骤、目标测试、性能/安全/恢复/UAT 命令；
12. 可观测指标、告警、Runbook、证据 Manifest、RACI、人日、成本和退出门。

每个子计划开始前必须：

1. 重新读取总体架构和主追踪矩阵；
2. 检查最新 Git、运行、数据库和对象存储状态；
3. 锁定源/目标数据所有权和唯一写入者；
4. 列出 API/事件/状态/错误/字段映射；
5. 定义测试前置、回滚开关和退出门；
6. 明确哪些步骤需要采购方、业务、安全、法务或运维批准。

---

## 18. 验证策略与命令框架

### 18.1 当前基线验证

子计划必须从当前工程已有门禁中选择适用项，并记录原始输出：

```bash
cd backend && pytest -q
cd frontend && npm run typecheck
cd frontend && npm run build
```

涉及浏览器流程时执行对应 Playwright spec；涉及 PostgreSQL 行为时使用 PostgreSQL 契约环境。不得用 SQLite 全绿替代生产数据库验证。

### 18.2 目标控制面验证框架

具体命令由 W1 锁定的 Maven/工具版本决定，至少包含：

```text
Maven 单元/集成/架构测试
OpenAPI backward-compatibility check
AsyncAPI/JSON Schema compatibility check
MySQL migration validate + clean restore rehearsal
Kafka duplicate/out-of-order/DLQ contract tests
Kubernetes manifest/Helm lint + policy checks
Container/SBOM/secret/vulnerability scans
Frontend typecheck/build/Playwright
Python worker unit/contract/provider-canary tests
```

### 18.3 每批完成证据

- 变更 Commit SHA 和镜像 Digest；
- 数据迁移 Batch ID、源/目标高水位和核对报告；
- OpenAPI/事件兼容报告；
- 单元、集成、E2E、故障、安全、性能和恢复报告；
- 真实任务/Provider/GPU/对象/费用/质量关联 ID；
- Feature Flag、Gateway 路由、回退步骤和观察记录；
- 风险接受、验收签字和未关闭事项。

### 18.4 TEST / EVID Master Register

| TEST/EVID-ID | 需求/域 | 层级/环境 | 数据集/Provider/硬件 | 用例及Pass口径 | Owner/Reviewer | Gate | 状态 |
|---|---|---|---|---|---|---|---|
| TEST-CONTRACT | API/事件/状态/错误 | 合同/CI+Integration | V1快照/Schema目录 | 无未批准破坏；重复/乱序/版本测试通过 | ARCH/QA | CR/G1/G3 | PLANNED |
| TEST-DATA-6M | DM-00—05中纳入MS-06M的批准范围 | 迁移/Staging | 生产只读画像+脱敏副本 | 批准A/修复B的ID/金额/引用/hash 100%；C/D排除；不等待二期DM-06/07 | DATA/DATA_OWNER/QA | G0/G2/PKG-6M | BLOCKED-BY-PROFILE |
| TEST-DATA-12M | DM-06—07及全部域最终增量 | 迁移/PreProd | 质量/声音/交付/审计历史+最终高水位 | 合同/对象/时间码/审计链和最终增量守恒；占位证据不得迁为PASS | DATA/DATA_OWNER/QA | G2/PKG-12M | BLOCKED-BY-PROFILE |
| TEST-ASSET-MANIFEST | D04/D06 | 合同+数据/PreProd | 固定角色/场景资产、图像/音频/视频输出 | Feature/Taxonomy层级与租户过滤、Recall@K/Precision@K/p95；逐媒体单元ProviderOperation/参数快照/Seed/时长/索引/hash完整 | Asset/DATA/QA | G2/G7 | PLANNED |
| TEST-PROVIDER-5W | D06/D09/D13 | 故障/PreProd | Sandbox+小额Canary+双D06/双Egress/双站点故障 | 同base key/generation一根；PREPARED无submit授权，Grant时固化，签发后租约失效/fence换代则拒绝且接管租约不覆盖；五窗口/竞争下每epoch一Grant/CAS/submit/扣费；未受理同根新epoch；已受理权威失败收敛旧费后用新generation/根/键/预算，终态不明不重跑 | EXEC/FIN/SRE/QA | G4/G6/ORR | PLANNED |
| TEST-IAM-SEC | D01/全域 | 安全/PreProd | 角色矩阵/攻击样本 | 0跨租户；会话/Secret/媒体/出口/审计通过 | SEC/QA | G5 | PLANNED |
| TEST-UI-STACK | RQ-STACK-3.1/D15 | 合同+UI/CI+PreProd | 组件清单、批准浏览器/分辨率、角色账号 | Element UI/Ant Design等采购列举库采用清单或书面等效评审；响应式断点、视觉/可用性/无障碍/E2E、入口不可绕过、SSR安全、租户缓存隔离和BFF投影重建通过；MS-06M以批准MVP页面为分母并出具MIN证据，D15-EX以全量批准页面/组件为分母 | FE/ARCH/PO/QA | MS-06M/G3/G5/G7/D15-EX | PLANNED |
| TEST-QUALITY | D11 | 算法盲测/PreProd | 独立盲测集/检测器Digest | 准确/召回/漂移/坏帧/参数修复按签署阈值；RepairRequest幂等创建新Repair Job/Attempt，source_job/source_attempt/source_asset/repair_plan/generation及新逻辑副作用键完整，源终态不变 | Quality/EXEC/SME/QA | G7 | BLOCKED-BY-THRESHOLD |
| TEST-AUDIO | D10 | 业务/PreProd | 授权声音/文本/四轨金标 | 音色/可懂/情感和四轨p50/p95/p99按签署阈值 | Audio/SME/QA | G7 | BLOCKED-BY-THRESHOLD |
| TEST-AUTOEDIT | D12 | Golden/PreProd | 固定Timeline/SFX/BGM/权利集 | 粗/精剪运行、接受率、FFmpeg/ffprobe/同步/hash通过 | Media/SME/QA | G7 | BLOCKED-BY-THRESHOLD |
| TEST-PERF-CAP | D00/D06/D09/D12 | 性能/Staging+PreProd | 指定GPU/模型/Provider配额 | SLI、扩缩容、长稳、回压/成本按容量报告 | SRE/QA | G6/ORR | BLOCKED-BY-RESOURCE |
| TEST-DR-PLATFORM-MIN | D00平台与迁移工厂最小恢复 | 恢复/CI+Staging | GitOps制品、配置引用、Schema Registry、空/合成非财务Schema、Kafka/Nacos/对象Manifest备份 | 在禁用真实Provider出口和付费派发的条件下，按受控Digest重建平台，恢复配置/Schema/迁移高水位，校验备份完整、一般RPO/RTO、旧实例写栅栏和恢复Runbook；不引用尚未实现的D06/D13业务状态 | SRE/ARCH/SEC/QA | D00-EX/MS-PLATFORM | PLANNED |
| TEST-DR-FIN-MIN | D06/D13最小付费安全切片 | 恢复/Staging+PreProd | 仲裁存储故障、双站点、D06/D13固定流水集 | ProviderOperation根/generation/Epoch/Grant/submit授权快照/WorkerLease历史/Attempt/site_epoch、D06引用及D13财务聚合逻辑RPO=0；current_epoch/代次/历史水位连续，旧/新generation费用双向100%对账、0悬空/回退，仲裁不可用时冻结 | EXEC/FIN/SRE/QA | 首个Canary/G4/MS-06M | PLANNED |
| TEST-DR | D00—D15全状态最终灾备 | 恢复/PreProd+Production演练 | 完整备份/故障注入+站点分区+Provider/账单固定集 | 在TEST-DR-PLATFORM-MIN和TEST-DR-FIN-MIN之上验证全部权威域的一般RPO/RTO与副作用/财务逻辑RPO=0分层；D06 base key/generation/Epoch/提交授权/WorkerLease/reservation与D13聚合双向100%核对，0代次/纪元断裂、悬空或余额回退；site_epoch单调、旧站点撤权、Provider/Usage/账单扫描和全局冻结守恒 | SRE/SEC/FIN/QA | G4/ORR/PKG-12M | PLANNED |
| TEST-SLA | RQ-SVC-01—03 | 工单/演练/服务环境 | 电话/邮件/远程+指定地点演练 | 7×24渠道；一般故障4小时解决；远程不成8小时到场/24小时解决；漏洞无条件及时修补均有计时/工单/签署证据 | SRE/PO/SEC/QA | PKG-SVC/ORR | BLOCKED-BY-BD-006 |
| TEST-DEMO-61-65 | 五项演示 | 业务/BD-011指定环境 | 固定脚本+真实任务/媒体 | DEMO-6.1-0及6.1-a—e、DEMO-6.2-0及6.2-a—e、6.3-a—g、6.4-a—g、6.5-a—k逐项有任务/版本/日志/指标/录像/hash；人物关系/关键事件、原创角色来源/权利和多情绪连续生成不得被汇总录像省略 | PO/SME/QA | G7/PKG | BLOCKED-BY-BD-011 |
| TEST-1200 | 60批/1200分钟 | 工业/PreProd+Prod | 不可变输入/权利/模型/硬件 | 保持原文口径并按签署统计/质量/成本/人工节点公式 | PO/QA/FIN | MS-12M | BLOCKED-BY-BD-001/008/010 |
| TEST-UAT-6M | MS-06M批准范围 | 业务/PreProd+UAT | D00—09、MIN/Adapter、批准MVP页面、角色账号和一期UAT脚本 | 采购方批准的一期角色与端到端流程逐项通过；状态/资产/费用/权限可追溯，回退演练和整改复验通过；P0/P1为0，未纳入一期的D10—15完整能力明确列为后续范围 | PO/SME/QA | MS-06M/PKG-6M | PLANNED |
| TEST-UAT-ORR | D10—15完整用户/运维/交接 | UAT+Production | 全量角色账号/Runbook/工单/最终候选 | 完整端到端、培训考核、SLA/DR/值班/移交和退役准备通过；不得用一期分母或旧候选证据替代 | PO/SRE/QA | PKG-12M/ORR/G8 | PLANNED |
| EVID-DEMO-61-65 | RQ-DEMO-6.1—6.5 | 演示证据Manifest/BD-011指定环境 | TEST-DEMO-61-65逐项原始任务/版本/日志/媒体/指标/录像/hash | DEMO-6.1-0含人物关系/关键事件，DEMO-6.2-0含原创来源/权利/多情绪，且所有a—k子项逐行可重算；不以汇总录像、省略前置语句或旧候选版本代替 | PO/SME/QA | BD-011指定提交包/G7 | BLOCKED-BY-BD-011 |
| EVID-W0 | DEL-W0 | 证据Manifest/Integration | WP-00原始产物 | 逐项关联BASE、恢复、Skeleton、无付费样例和BD状态；不引用完整D00-EX | PM/QA/PO | MS-20D | PLANNED |
| EVID-UAT-6M | WP-08/MS-06M | 阶段UAT证据Manifest/PreProd+UAT | TEST-UAT-6M原始脚本、账号、结果、缺陷、整改与复验记录 | 一期批准分母、候选Digest/Schema/数据集、执行/复核/签署人和每项结果可重算；所有P0/P1关闭且后续范围不冒充通过 | PO/SME/QA | MS-06M/PKG-6M | PLANNED |
| EVID-D00 | D00 | 领域证据Manifest/Staging | TEST-CONTRACT+TEST-DR-PLATFORM-MIN | 平台、契约、迁移工厂和最小恢复证据可重算；不以尚未实现的D06/D13全状态作为前置 | SRE/ARCH/SEC/QA | D00-EX | PLANNED |
| EVID-D01 | D01 | 领域证据Manifest/PreProd | TEST-IAM-SEC+TEST-DATA-6M | IAM所有权、权限、数据和恢复通过 | IAM/SEC/QA | D01-EX | PLANNED |
| EVID-D02 | D02 | 领域证据Manifest/PreProd | TEST-CONTRACT+TEST-DATA-6M | 项目/剧本版本与V1兼容通过 | Creative/QA | D02-EX | PLANNED |
| EVID-D03 | D03 | 领域证据Manifest/PreProd | TEST-CONTRACT+TEST-DATA-6M | Bible/实体/审批/影响图通过 | Creative/PO/QA | D03-EX | PLANNED |
| EVID-D04 | D04 | 领域证据Manifest/PreProd | TEST-ASSET-MANIFEST+TEST-DATA-6M | 对象、权利、Feature/Taxonomy和向量通过 | Asset/LEGAL/QA | D04-EX | PLANNED |
| EVID-D05 | D05 | 领域证据Manifest/PreProd | TEST-CONTRACT+模型认证/回退 | 训练/制品/绑定/Secret/任务快照通过 | Model/SEC/QA | D05-EX | PLANNED |
| EVID-D06 | D06 | 领域证据Manifest/PreProd | TEST-PROVIDER-5W+TEST-DR-FIN-MIN | Job/Attempt、base key+generation根、不可覆盖Epoch/四水位/submit授权与WorkerLease历史、同纪元唯一Grant/CAS、未受理技术重试与已受理失败新代次、无第二账本、D06/D13守恒、站点/定稿闭环通过 | EXEC/FIN/SRE/QA | D06-EX | PLANNED |
| EVID-D07 | D07 | 领域证据Manifest/PreProd | TEST-CONTRACT+TEST-DATA-6M | Shot/Episode合同、版本和影响通过 | Creative/QA | D07-EX | PLANNED |
| EVID-D08 | D08 | 领域证据Manifest/PreProd | TEST-CONTRACT+Flowable故障 | BPMN、人审、补偿和版本固定通过 | Orchestrator/QA | D08-EX | PLANNED |
| EVID-D09 | D09 | 领域证据Manifest/Canary | TEST-PROVIDER-5W | Worker/Adapter/出口/回调/接管通过 | PY/Provider/QA | D09-EX | PLANNED |
| EVID-D10 | D10 | 领域证据Manifest/PreProd | TEST-AUDIO | 情感TTS与四轨对齐通过 | Audio/SME/QA | D10-EX | PLANNED |
| EVID-D11 | D11 | 领域证据Manifest/PreProd | TEST-QUALITY | 合规、质量、校准、Repair Job/Attempt源血缘和定向修复通过 | Quality/EXEC/SME/QA | D11-EX | PLANNED |
| EVID-D12 | D12 | 领域证据Manifest/PreProd | TEST-AUTOEDIT | Timeline/粗精剪/SFX/BGM/交付通过 | Media/SME/QA | D12-EX | PLANNED |
| EVID-D13 | D13 | 领域证据Manifest/PreProd | TEST-PROVIDER-5W+TEST-DATA-6M+TEST-DR | 预算、财务聚合逻辑RPO=0、D06引用双向对账、流水、Usage/账单守恒通过 | FIN/SRE/QA | D13-EX | PLANNED |
| EVID-D14 | D14 | 领域证据Manifest/全环境 | TEST-IAM-SEC+TEST-DR+TEST-SLA | 审计、Trace、报表、告警和SLA证据通过 | SEC/SRE/QA | D14-EX | PLANNED |
| EVID-D15 | D15 | 领域证据Manifest/Prod | TEST-CONTRACT+TEST-UI-STACK+TEST-UAT-ORR | Gateway/BFF/Frontend兼容、入口边界、投影重建、UI库/响应式等效性和路由通过 | FE/Gateway/ARCH/PO/QA | D15-EX | PLANNED |
| EVID-D15-UI-MIN | DEL-D15-UI-MIN | 阶段切片证据Manifest/PreProd+UAT | TEST-UI-STACK的批准MVP页面分母 | 组件/等效结论、断点、入口/SSR/缓存隔离、最小投影和E2E逐项有版本/hash；未覆盖页面显式排入D15 | FE/Gateway/ARCH/PO/QA | MS-06M候选前 | PLANNED |
| EVID-D13-MIN | DEL-D13-MIN | 切片证据/PreProd | TEST-DR-FIN-MIN+小额并发/重复/未知用例 | 首个Canary前D13聚合逻辑RPO=0，D06 reservation引用双向100%核对且金额守恒 | FIN/SRE/QA | MS-LEDGER-MIN | PLANNED |
| EVID-D14-MIN | DEL-D14-MIN | 切片证据/Staging | 审计/Trace/脱敏用例 | 首个生产写前可追溯 | SEC/QA | MS-AUDIT-MIN | PLANNED |
| EVID-D11-COMPLIANCE-MIN | DEL-D11-COMPLIANCE-MIN | 策略证据/Staging | Prompt/剧本/参考资产命中集 | fail-closed与人工放行通过 | Quality/SEC/QA | 首个外部调用前 | PLANNED |
| EVID-LEGACY-ADAPTER | DEL-LEGACY-ADAPTER | 接管证据/PreProd | In-flight Registry/回调/晚到完成 | 无重提、完成/资产/费用守恒 | EXEC/FIN/Asset/QA | MS-ADAPTER-WR | PLANNED |
| EVID-IP-01 | DEL-IP-01 | 移交证据/受控介质 | 源码/文档/日志/构建/SBOM/hash、权利转移清单及双方有权主体签署凭证 | 原文触发后T+10工作日完成介质/密钥/构建/签收并证明归属权转移至采购人；背景IP/第三方例外只以BD-005正式偏离为准 | PM/LEGAL/PO/QA | 合同验收后 | PLANNED |
| EVID-SVC-EVOLUTION | DEL-SVC-EVOLUTION | 服务期证据/Production | 版本/性能/质量/成本/Trace趋势 | 每轮可回退且最终技术演进报告可重算 | Model/SRE/PO/QA | PKG-SVC | PLANNED |
| EVID-REC-01 | D01/D13/D14恢复 | 恢复证据/PreProd | R3前向恢复/冲正/撤销演练 | 身份、流水、审计不删除且服务可恢复 | SEC/FIN/PO/QA | 对应CW前 | PLANNED |
| EVID-REC-02 | D02/D03/D07恢复 | 恢复证据/PreProd | R2反投影+R3新版本 | 最大窗口、命令、核对和no-return通过 | DATA_OWNER/QA | CW-02前 | PLANNED |
| EVID-REC-03 | D04恢复 | 恢复证据/PreProd | 对象引用回切/前向权利修复 | 对象版本、hash、权利和法律保留通过 | Asset/LEGAL/QA | CW-03前 | PLANNED |
| EVID-REC-04 | D05恢复 | 恢复证据/Staging | 绑定回退/旧任务固定快照 | 认证版本回退且旧任务不变 | Model/QA | CW-03前 | PLANNED |
| EVID-REC-05 | D06/D09恢复 | 恢复证据/PreProd | Grant/Egress/site切换、Poll接管、Manifest认领 | 无重提、无重复扣费、状态/对象守恒 | EXEC/FIN/SRE/QA | CW-04前 | PLANNED |
| EVID-REC-06 | D08恢复 | 恢复证据/PreProd | 固定流程定义/补偿 | 进行中实例不被错误升级 | Orchestrator/QA | CW-05前 | PLANNED |
| EVID-REC-07 | D10/D11/D12恢复 | 恢复证据/PreProd | Repair Job/Attempt/Timeline/Renderer回退 | 源Job/Attempt/资产终态与历史产物不覆盖，修复血缘、同步/质量守恒 | EXEC/SME/QA | CW-06前 | PLANNED |
| EVID-REC-08 | D15恢复 | 恢复证据/PreProd | Feature Flag/路由/兼容代理 | UI可回退且后端唯一写者不变 | FE/Gateway/QA | CW-08前 | PLANNED |
| EVID-INDUSTRIAL-READY | WP-12 | 工业证据Manifest/PreProd+Prod | TEST-1200/PERF/DR/SEC/QUALITY | 60批/1200分钟及全部原始证据完成、可重算、可组包 | PM/PO/QA/FIN | WP-12退出 | PLANNED |
| EVID-PKG | DEL-PKG | 验收包Manifest/各阶段 | 各PKG引用DEL/TEST/EVID | 引用闭合、hash/签署/触发点可审计 | PM/PO/QA/LEGAL | 各PKG | PLANNED |

实际台账还必须保存需求、WP、具体环境、数据集/模型/Provider版本、硬件/规模、原始 URI/hash、执行人、复核人、运行时间、结果、DEFECT/WAIVER 和保留期。`PLANNED/BLOCKED` 不能被统计为通过。

### 18.5 缺陷、复验与豁免规则

| 级别 | 定义 | Gate规则 |
|---|---|---|
| P0 Blocker | 数据丢失/越权、重复付费、账务或状态不可解释、不可恢复、★/法律硬阻断 | 立即停测/停灰度；不得豁免进入生产/验收 |
| P1 Critical | 核心流程失败、质量/性能/SLA显著不达、兼容破坏、无有效Runbook/证据 | Production和正式验收PKG前必须为0；仅非生产WR/EX可由PO+QA+风险Owner及适用SEC/LEGAL签署命名Gate、环境/租户和期限的豁免，且不得涉及安全、数据、金钱、重复副作用或采购核心能力 |
| P2 Major | 有受控替代路径且不破坏核心不变量 | 可带期限/Owner/影响范围的条件接受；到期自动重开 |
| P3 Minor | 文案、低影响体验或改进建议 | 可进入后续版本，但保留追踪 |

修复必须关联原 Defect、相同或批准更新后的 TEST/EVID、候选版本和复验结果。Waiver 必须写适用Gate/环境/租户/期限、补偿控制、风险接受人和撤销条件；`WAIVED` 仅在该命名Gate的open count中排除，仍保留在缺陷/风险台账，到期自动恢复OPEN。不能删除失败证据或修改分母“变绿”；P0永不可豁免。

### 18.6 版本化阶段验收包

| PKG-ID | 范围 | 必含 DEL/EVID | 环境/Pass | Owner→Approver | 偏离/状态 |
|---|---|---|---|---|---|
| PKG-20D | ★20日原文；W0基线/设计/恢复/Skeleton/无付费切片；演示仅依BD-011 | DEL-W0、EVID-W0、BASE登记；BD-011适用时引用TEST-DEMO-61-65/EVID-DEMO-61-65 | 隔离/Integration；清单完整且不夸大为完整D00/二代终验 | PM/QA→PO | BD-001/011/013；PLANNED |
| PKG-6M | 原文一期MVP、可运行系统、源码/算法文档；可靠任务和最小Ledger/Audit为建议安全前置 | DEL-D00/DEL-D01/DEL-D02/DEL-D03/DEL-D04/DEL-D05/DEL-D06/DEL-D07/DEL-D08/DEL-D09、DEL-D13-MIN、DEL-D14-MIN、DEL-D11-COMPLIANCE-MIN、DEL-LEGACY-ADAPTER、DEL-D15-UI-MIN；TEST-CONTRACT/TEST-DATA-6M/TEST-ASSET-MANIFEST/TEST-PROVIDER-5W/TEST-DR-PLATFORM-MIN/TEST-DR-FIN-MIN/TEST-IAM-SEC/TEST-UI-STACK/TEST-UAT-6M；EVID-D00/EVID-D01/EVID-D02/EVID-D03/EVID-D04/EVID-D05/EVID-D06/EVID-D07/EVID-D08/EVID-D09/EVID-D13-MIN/EVID-D14-MIN/EVID-D11-COMPLIANCE-MIN/EVID-LEGACY-ADAPTER/EVID-D15-UI-MIN/EVID-UAT-6M；BD-011适用时追加EVID-DEMO-61-65 | PreProd/UAT；D00—D09均达EX且一期UAT签署公式/缺陷门通过；所有MIN/Adapter为独立可签收DEL/EVID，UI-MIN只按批准MVP页面分母 | PM/QA→PO | BD-001/002/011；PLANNED |
| PKG-12M | 原文二期、完整集成、60批/1200分钟；质量/媒体/安全/DR/ORR | DEL-D10/DEL-D11/DEL-D12/DEL-D13/DEL-D14/DEL-D15、DEL-IP-01；TEST-QUALITY/TEST-AUDIO/TEST-AUTOEDIT/TEST-PERF-CAP/TEST-DR/TEST-DATA-12M/TEST-SLA/TEST-UI-STACK/TEST-1200/TEST-UAT-ORR；EVID-D10/EVID-D11/EVID-D12/EVID-D13/EVID-D14/EVID-D15/EVID-INDUSTRIAL-READY/EVID-IP-01及SBOM/退役准备；BD-011适用时追加当前候选版EVID-DEMO-61-65 | PreProd+Prod；D10—D15均达EX、所有适用G0—G7及G8 readiness通过；验收前DEL-IP-01/EVID-IP-01为READY，若本次签署触发原文义务则T+10工作日完成权利转移双方签署凭证并作为PKG-12M追加闭包 | PM/QA→PO/FIN/LEGAL | BD-001/008/010/011/012/013；PLANNED |
| PKG-SVC | 持续优化、7×24、漏洞、培训/到场/技术报告 | DEL-SVC-EVOLUTION、TEST-SLA、EVID-SVC-EVOLUTION、值班/演练/培训补训/IP侵权Runbook | 服务环境；按签署SLA周期 | SRE/PM→PO | BD-004/006/012；PLANNED |

6/12个月包采用倒排：T-6周冻结范围/数据/公式，T-4周完整预演，T-3至T-2周正式UAT，T-2至T-1周整改/复验，T0完整性复核和有权限主体签署。PKG-20D 因周期短，在 C0 当日即锁范围：建议 D10前完成预演、D15前完成UAT、D18前完成整改、D20签署；若完整采购文件/场地/账号未到位，应立即走阻断/变更，而不是压缩证据。

验收流程为“提交版本化包→完整性检查→技术/UAT→缺陷单→整改/同口径复验→正式/部分/条件结论→签署”。部分或条件验收必须列出接受需求、保留项、期限、付款比例和签署权限。付款、服务起算和 IP 移交的触发条件均以双方签署合同/补充协议的原文为准；合同签订、技术测试通过或阶段包提交本身不自动同时触发三者。原文“验收后10个工作日”保持原文，不自行改成每阶段；若触发，按DEL-IP-01执行。若需分批移交，必须另签清单、权利、介质和触发点。

### 18.7 Operational Readiness Review（ORR）

生产100%灰度前必须通过：Owner/On-call/7×24边界、看板/告警/Burn-rate、Provider/费用/容量、备份恢复/全局派发冻结、Incident/安全/侵权/版权撤回Runbook、数据留存/删除/法律保留、Change/Release、支持渠道/到场条件、培训考核、SBOM/IP、Known Issue/Waiver、G8退役准备。ORR失败只允许继续修复或保持较低灰度，不能以“业务已可用”绕过。

---

## 19. Go/No-Go 决策表

### 19.1 条件性 Go

只有同时满足以下条件才建议继续：

- 书面拆分 20 日、6 个月和 12 个月；
- 取得完整采购文件/第五章符合性审查并确认五项视频演示的投标/交付/复验时点；
- 确认 Java 控制面 + Python 执行面符合合同；
- 明确五项演示、质量、性能、安全和 1200 分钟的样本与阈值；
- 48.5 万元对应签署的范围—价格—甲供资源—第三方/OPEX—排除项矩阵，后续阶段、算力和 SLA 有预算；
- 区分背景 IP、定制成果和第三方材料，并由法务书面处理原文侵权交涉、责任/费用/赔偿与责任上限/保险；
- 采购方提供部署/GPU/数据/模型账号/验收人员和到场地点，现场/网络/云上本地条件通过勘察；
- 有阶段付款、变更控制、反馈期限和验收机制。

### 19.2 No-Go

以下任一成立则不承诺全量重构：

- 20 日必须完成全部新架构、算法、1200 分钟和工业指标；
- 在未提供完整第五章/演示规则时要求承建方无条件证明“全部符合”；
- 48.5 万元必须覆盖全量重构、所有推理费用和长期 7×24/现场；
- 指标无公式/阈值，但采购方保留单方判断合格权；
- 合同总金额的100%支付依赖模糊终验，或后续义务没有可执行付款机制；
- 要求转移开源、第三方模型或既有平台全部所有权，或在未明确适用范围/保险/责任上限时承担不可估算无限责任；
- 上游模型、云 GPU、网络或采购方素材故障均由承建方无限承担；
- 不允许数据盘点、影子比较、阶段切换或回滚窗口；
- 要求新旧系统同时写同一业务真相。

---

## 20. 计划完成定义

本总计划本身的完成，不等于工程完成。它的完成定义是：

- 总体架构、主追踪矩阵和本文无内部矛盾；
- 每个领域有范围、输入、所有权、契约、数据、测试、回滚和退出条件；
- BASE/IMS/Domain/DEL/Reuse/DM/CW/恢复/环境/资源/外部依赖/TEST/EVID/RAID/PKG/ORR 登记字段齐全，`TBD/OPEN` 被明确视为阻断而非完成；
- 阶段、依赖、关键路径/浮时、RACI、人日和 Go/No-Go 可执行；
- 合同阻断被显式暴露，没有被技术团队自行解释；
- 用户批准后，能够按第 17 章逐个生成详细子计划，而不是直接开始全仓重写。

在获得批准前，本计划仅用于评审、预算和合同澄清，不授权生产变更、数据迁移、发布、删除、合并或外部交付。
