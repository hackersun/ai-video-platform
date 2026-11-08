# 二代平台 V1.0-FC 冻结候选包设计

> 文档编号：`DES-FRZ-001`
> 文档状态：设计送审稿（`DRAFT`，不构成冻结包）
> 编制日期：2026-08-20
> 时区：Asia/Shanghai
> 现有工程基线：`main@9a3c8bfb`
> 需求来源：`需求文件.pdf`
> 需求文件 SHA-256：`52ae0db5b5010a867a766de27cb4f5ddf3b7c5c7f7b32a9bafc5a99fd4a5bbd5`
> 总体架构送审稿 SHA-256：`5d1a76b22441ef4b0633ef9d2237d71376b33ec66be6e95cab695b61c61d340f`
> 分域迁移总计划 SHA-256：`95b7cfcbe514baf949b66b2bbc8f60977e590ae8791dc8cdff09bb7dd9781746`
> 适用范围：总体架构与分域迁移计划从 V0.95 送审稿进入可控实施基线前的冻结、签署和生效设计

## 0. 文档控制

### 0.1 文档目的

本文定义二代平台 `V1.0-FC`（Freeze Candidate，冻结候选包）的组成、状态、签署、差异合并、基线生效和后续详细设计准入规则。它解决以下问题：

1. 把采购原文、正式澄清、技术派生控制、技术事实和计划假设分开管理；
2. 把“内容已经稳定”“内部技术可执行”“合同已经生效”“生产动作已获批准”分成不同 Gate；
3. 将 `BD-001`—`BD-013` 变成可签署、可追踪、可回灌的独立决策卡；
4. 使总体架构、迁移计划、ADR、附件、验收指标和商务资源在同一 Manifest 下可核验；
5. 为后续领域详细设计和执行子计划提供稳定输入，避免一边编码一边解释合同。

本文是**冻结候选包的设计规格**，不是已经完成的 `V1.0-FC` 包，更不是 `V1.0` 生效基线。

### 0.2 当前结论

当前两份 V0.95 主文档已经完成内部一致性终审，未发现剩余 P0/P1；但完整采购文件、13 项合同阻断、验收阈值、资源、费用、IP、SLA 和签署授权尚未外部关闭。因此当前最合理的下一步是：

> 先实例化 `V1.0-FC`，把全部已知内容冻结成“可送签、可拒绝、可合并”的候选包；在此之前不把送审稿升级为实施生效基线。

### 0.3 范围

本文覆盖：

- `FRZ-00`—`FRZ-06` 七个主件及机器可读索引；
- `BD-001`—`BD-013` 十三张决策卡；
- 采购/合同来源、派生控制和计划假设三本账；
- `V1.0-FC`、`V1.0-IB`、`V1.0-EB` 三级基线；
- 附件 A—N 的成熟度，以及新增候选附件 O；
- `BASE-CONTRACT/ARCH/DATA/ACCEPT/RESOURCE` 的关闭与生效规则；
- 签署件归档、差异回灌、重新计算哈希、独立复核和冻结后变更；
- 后续详细设计与首批执行子计划的准入和交接。

### 0.4 非目标

本文不执行以下动作：

- 不代替采购方、承建方、法务、财务或验收主体填写任何外部决定；
- 不把技术推荐写成采购原文、合同解释或签署结论；
- 不创建微服务、数据库、Topic、Kubernetes 资源或生产配置；
- 不授权真实 Provider 付费调用、生产写入、数据迁移、数据删除或正式交付；
- 不一次性生成全部附件、全部服务详细设计或 24 份执行子计划；
- 不修改、覆盖或删除现有 V0.95 两份主文档；
- 不提交 Git、不推送远端、不创建发布或生产变更单。

### 0.5 当前来源完整性声明

当前取得的 `需求文件.pdf` 为 9 页。文件首页引用“第五章符合性审查”，但当前文件集中未见完整第五章；§6.1—§6.5 又使用“投标人/需提供视频演示”措辞。因此：

- 当前采购源基线必须标记为 `INCOMPLETE`；
- 五项演示的首次提交时点不能由技术团队推断；
- 当前需求追踪矩阵只能称“基于已取得文件的追踪”，不能称“完整采购符合性矩阵”；
- 后续取得的正式澄清、合同、补充协议和通知必须作为新来源追加，不能覆盖原始 PDF。

### 0.6 角色代码

本文只登记角色，不预填个人姓名。签署时必须另附授权依据。

| 代码 | 角色 |
|---|---|
| `AUTH-B` / `AUTH-S` | 采购方 / 承建方有权代表 |
| `PROC-B` | 采购方采购或合同负责人 |
| `COMM-S` | 承建方商务负责人 |
| `LEGAL-B/S` | 双方法务或知识产权授权角色 |
| `FIN-B/S` | 双方财务或预算授权角色 |
| `PO-B` | 采购方业务、产品或验收责任人 |
| `PM-B/S` | 双方项目负责人 |
| `ARCH-B/S` | 双方技术或架构负责人 |
| `QA-B/S` | 双方测试、质量或验收负责人 |
| `SEC-B/S` | 双方安全负责人 |
| `DATA-B/S` | 双方数据责任人 |
| `SRE-B/S` | 双方运行、场地或服务负责人 |
| `SME-B/S` | 双方算法、导演、美术、音频等领域专家 |

角色名称本身不证明签署权限。任何决定达到 `impact_status=VERIFIED + effectivity_status=EFFECTIVE` 前，必须保存授权依据、签署件 URI 和签署件 SHA-256。

---

## 1. 设计原则与核心不变量

### 1.1 四类批准必须分开

| 层次 | 回答的问题 | 典型输出 | 是否授权生产 |
|---|---|---|---|
| 内容成熟度 | 文档是否完整、一致、可评审 | `V1.0-FC` | 否 |
| 内部技术批准 | 架构、接口、不变量和验证方法是否可实施 | `V1.0-IB` | 否 |
| 外部生效批准 | 合同、资源、法务、验收和适用范围是否已签署 | `V1.0-EB` | 仍否 |
| 动作批准 | 本次变更是否可在指定环境、租户、流量执行 | ORR、Gate、Cutover/Change 单 | 仅批准范围内 |

任何文档出现“V1.0 已批准”时，必须带完整后缀和范围；禁止用一个“已批准”同时代替以上四层。

### 1.2 不变量

1. `V1.0-FC` 只表示候选内容可送审，不表示外部决定已形成；
2. `V1.0-IB` 只授权内部、非生产、可逆、无付费的批准范围；
3. `V1.0-EB` 只对明确领域、环境、期限和外部依赖生效，不自动外推；
4. 任何生产写入、真实付费调用、迁移、删除和正式验收仍需独立动作批准；
5. 采购原文永不被 ADR、技术建议、会议印象或计划假设覆盖；
6. 一个外部决定只有在签署验真、影响回灌、独立复核和哈希更新后才算关闭；
7. `OPEN`、`SIGNED_DEFERRAL`、普通占位词或仅有会议纪要均不算关闭；
8. 未决参数必须有稳定 ID、Owner、截止、影响范围和 fail-closed 行为；
9. 签署件不可编辑，只能追加新版本并将旧版本标为 `SUPERSEDED`；
10. 基线批准不降低现有总体架构中的唯一写者、Provider 不重复提交、账务守恒、租户隔离和可恢复性要求。

---

## 2. 三级基线与状态模型

### 2.1 基线定义

| 基线 | 定义 | 允许行为 | 明确禁止 |
|---|---|---|---|
| `V1.0-FC` | 七个 FRZ 主件、13 张 BD 卡和索引已具备送审条件；开放项均显式登记 | 评审、已授权的文档/仓库只读盘点、模型化验证、候选值比较；数据/对象盘点另受 `FC-G4-DATA` 限制 | 不授权编码实施、真实 Provider、生产写入、迁移、正式验收 |
| `V1.0-IB` | 内部可决定的架构、Schema、不变量、安全、参考部署、容量公式和验证方法已获技术批准；外部参数已隔离 | 在批准范围内生成详细设计和子计划，开展编码、CI、模拟 Provider、Sandbox、Integration、Staging 验证 | 不得把建议值解释为合同值；不得真实付费、生产迁移、正式 UAT/验收或不可逆副作用 |
| `V1.0-EB` | 对应范围的技术附件、合同、资源、法务、验收和外部依赖均已签署并完成影响回灌 | 进入命名领域和环境的 ORR、Canary、Cutover 审批流程 | 不得绕过具体 Gate、变更单、灰度、回滚/前向恢复和生产审批 |

完整二代平台 `V1.0-EB` 要求 `BD-001`—`BD-013` 全部关闭。若双方签署的是阶段性范围，只能形成带范围后缀的 `V1.0-EB-SCOPED`；未纳入范围继续阻断，且不得宣传为全平台 V1.0。

`V1.0-IB` 是本设计提出的新治理状态，不是现有总体架构 §0.3 或迁移计划 §0.1/§0.5 所称“实施基线”。本设计当前不修改那两份主文档；在其生效条件通过受控 Diff 明确吸收 IB 定义之前，旧文档的更严格规则优先，**不得依据本文单独启动编码**。若组织不批准该 Diff，则 IB 只允许详细设计、计划和模型化验证，编码仍须等待旧文档定义的完整实施基线。

### 2.2 制品内容与技术批准状态

```text
content_status:
  DRAFT -> IN_REVIEW -> REVIEWED -> FC_FROZEN -> SUPERSEDED
  FC_FROZEN --dependency_change--> IMPACT_REVIEW -> IN_REVIEW | FC_FROZEN | SUPERSEDED

technical_status:
  NOT_REVIEWED -> REVIEWED -> TECH_APPROVED -> SUPERSEDED
  TECH_APPROVED --dependency_change--> IMPACT_REVIEW -> REVIEWED | TECH_APPROVED | SUPERSEDED
```

- 评审失败返回 `DRAFT`；
- 来源、BD、关键 ADR 或依赖主版本变化时进入 `IMPACT_REVIEW`；
- `FC_FROZEN` 只说明候选包内容稳定；
- `TECH_APPROVED` 是独立技术批准维度，不是 FC 的前置或替代；
- 签署后的生效状态由另一维度管理。

### 2.3 外部决定与影响合并状态

```text
decision_status:
  OPEN -> CARD_READY -> SIGNED_DECISION
                     -> SIGNED_DEFERRAL
                     -> REJECTED_REDESIGN_REQUIRED

routing_status:
  NOT_STARTED -> ROUTING -> COMPLETED | RETURNED

impact_status:
  NOT_READY -> PENDING -> APPLIED -> VERIFIED

effectivity_status:
  INTERNAL_ONLY / BLOCKED_BY_BD / BLOCKED_BY_ASSUMPTION / EFFECTIVE / EXPIRED

base_result:
  OPEN / BLOCKED / VERIFIED_EFFECTIVE / EXPIRED
```

只有以下组合才表示一个 BD 已关闭：

```text
SIGNED_DECISION
AND impact_status = VERIFIED
AND effectivity_status = EFFECTIVE
AND signature_authority_verified = true
```

`SIGNED_DEFERRAL` 只说明双方签署了延期或排除，不等于该问题已解决；受影响范围必须继续 `BLOCKED_BY_BD`，除非签署文本明确形成一个可执行、有限范围的替代决定。

### 2.4 授权矩阵

| 动作 | FC | IB | EB | EB + 对应 ORR/CW/Gate |
|---|---:|---:|---:|---:|
| 阅读、评审、来源核验 | 是 | 是 | 是 | 是 |
| 只读文档和不含受限数据的仓库盘点 | 是 | 是 | 是 | 是 |
| 只读数据库、对象、Provider任务或Secret元数据盘点 | 仅在 `FC-G4-DATA` 批准范围 | 仅在数据授权范围 | 仅在数据授权范围 | 仅在数据授权范围 |
| 编制 00 号治理计划 | 仅在 `FC-G0` 后 | 是 | 是 | 是 |
| 编制严格只读 Discovery 计划 | 仅在 `FC-G1 + FC-G4-DATA` 后 | 是 | 是 | 是 |
| 编制不含代码/DDL/部署实施步骤的详细设计或协议计划 | 仅在适用 `FC-G3 + FC-G4` 后 | 是 | 是 | 是 |
| 生成含精确代码路径、DDL、部署、TDD和提交边界的实现执行计划 | 否 | 仅在 `IB_READY` 且直接附件分片 `TECH_APPROVED` 后 | 是 | 是 |
| CI、模拟 Provider、合成数据验证 | 否 | 是 | 是 | 是 |
| Sandbox 小额真实调用 | 否 | 否；除非另有专项书面授权 | 否；仍需动作批准 | 按批准范围 |
| 生产写入或迁移 | 否 | 否 | 否 | 按批准范围 |
| 生产数据删除/退役 | 否 | 否 | 否 | 仅独立退役变更 |
| 正式 UAT/合同验收 | 否 | 否 | 否 | 按验收包和签署流程 |

---

## 3. 候选包结构

### 3.1 建议实例化目录

本设计获批后，候选包建议实例化为：

```text
docs/program-baseline/v1.0-fc/
├── README.md
├── FRZ-00-freeze-control-and-manifest.md
├── FRZ-01-procurement-source-baseline.md
├── FRZ-02-bd-decision-index.md
├── decisions/
│   ├── BD-001-stage-and-calendar.md
│   ├── BD-002-payment-trigger.md
│   ├── BD-003-algorithm-obligation.md
│   ├── BD-004-continuous-service.md
│   ├── BD-005-ip-and-rights.md
│   ├── BD-006-sla-site-and-support.md
│   ├── BD-007-metric-definition.md
│   ├── BD-008-industrial-validation-cost.md
│   ├── BD-009-stack-equivalence.md
│   ├── BD-010-minute-evidence-scope.md
│   ├── BD-011-procurement-source-and-demo.md
│   ├── BD-012-infringement-liability.md
│   └── BD-013-scope-price-resource.md
├── FRZ-03-requirement-derived-assumption-ledgers.md
├── FRZ-04-architecture-approval-baseline.md
├── FRZ-05-acceptance-and-evidence-baseline.md
├── FRZ-06-commercial-resource-and-final-signoff.md
├── manifests/
│   ├── artifact-manifest.csv
│   ├── source-manifest.csv
│   ├── decision-manifest.csv
│   └── evidence-index.csv
└── signed/
    └── README.md
```

本节仅定义目标结构；当前不声称上述文件已经存在。`signed/` 只保存签署件的不可编辑副本或受控档案引用，不接收手工改写的“签署版 Markdown”。

### 3.2 通用文控字段

每个 FRZ、BD、ADR、附件和机器索引至少登记：

```text
artifact_id / title / artifact_type / version
content_status / technical_status / decision_status / impact_status / effectivity_status
owner / reviewers / approver_roles
source_baseline_id / dependency_ids / open_parameter_ids
repository_uri / content_sha256 / source_commit_or_digest
applicable_domain / environment / gate / authorization_scope
prepared_at / reviewed_at / approved_at / effective_at / expires_at
supersedes / superseded_by / change_request_id
evidence_uri / signature_artifact_uri / signature_artifact_sha256
```

时间字段使用带时区的 ISO 8601；金额使用明确币种和精度；持续时间注明日历日、工作日或运行小时；普通文本 `TBD` 不能作为关键字段值。

---

## 4. FRZ-00—FRZ-06 主件设计

### 4.1 总览

| 主件 | 目的 | 主责 | FC 内容复核 | IB 技术批准 | EB 外部签署 | FC 退出条件 | 阻断层级 |
|---|---|---|---|---|---|---|---|
| `FRZ-00` | 冻结总控、制品清单、哈希和授权边界 | PM-S / ARCH-S | PM-B/S、ARCH-B/S、QA-B/S | ARCH-B/S、PM-B/S | AUTH-B/S及适用职能角色 | 所有制品有稳定 ID、版本、Owner、状态和 hash 生成规则 | 结构缺失阻断FC；授权缺失阻断EB/动作 |
| `FRZ-01` | 采购源、条款、缺失文件和正式澄清基线 | PROC-B / PM-S | PROC-B、PM-B/S、LEGAL-B/S | 不适用技术批准；只做来源验真 | AUTH-B、PROC-B、LEGAL-B/S | 已取得文件逐份验真；缺失项和冲突显式登记 | 未登记缺口阻断FC；第五章/正式文本缺失阻断EB |
| `FRZ-02` | 13 张 BD 决策卡、路由、签署和回灌索引 | PM-B/S、LEGAL-B/S | PM-B/S、LEGAL-B/S、ARCH/QA影响复核 | 仅技术影响部分由ARCH/QA批准 | 各卡要求的有权角色 | 事实、选项、影响、fail-closed 和签署栏完整；外部决定栏未代填 | 卡片不完整阻断FC；未签决定阻断适用EB/动作 |
| `FRZ-03` | 需求原文、派生控制、计划假设三本账 | ARCH-S / QA-S | ARCH-B/S、QA-B/S、LEGAL抽检 | ARCH-B/S、QA-B/S | 被正式来源吸收的部分由相应有权角色签署 | 来源标签互斥；每个派生项和假设可反向追踪 | 混写阻断FC；外部影响未签阻断EB |
| `FRZ-04` | 架构、ADR、附件、所有权、不变量和 ACR 基线 | ARCH-S | ARCH-B/S、SEC、DATA、SRE | 架构委员会/ARCH-B/S | 合同等效和实际资源边界由AUTH/PROC及适用Owner签署 | 技术可批准内容及外部阻断均闭环登记；批准状态不冒进 | 内容缺口阻断FC/IB；等效或资源未签阻断EB |
| `FRZ-05` | 阶段、指标、数据集、演示、TEST/EVID/DEL/PKG | QA-B/S、PO-B | QA-B/S、PO-B、SME-B/S | QA-B/S、ARCH-B/S | PO-B、AUTH-B及合同要求的验收角色 | 候选值与签署值分列；证据链可重算 | 公式缺失阻断FC/IB；阈值/演示时点未签阻断EB/验收 |
| `FRZ-06` | 范围、价格、资源、日历、IP、SLA、Go/No-Go 和最终签署 | PM/FIN/LEGAL | PM-B/S、FIN-B/S、LEGAL-B/S | 资源模型由PM/ARCH/SRE技术批准 | AUTH-B/S、FIN-B/S、LEGAL-B/S及适用职能角色 | 所有 BASE 有当前状态、所需输入、批准角色和阻断范围；未签项保持开放 | 结构缺失阻断FC；预算/OPEX/甲供/IP/SLA/付款未签阻断EB |

### 4.2 FRZ-00：冻结总控与 Manifest

`FRZ-00` 是唯一冻结入口，至少包含：

- 候选基线身份、源文件/源码/主文档版本，以及工程、镜像、配置、数据库/对象存储画像的受控快照引用；
- 纳入范围、排除范围和不授权事项；
- 受控制品清单、签署件清单和保留等级；
- 开放项、阻断项、到期假设和受影响 Gate 摘要；
- FC/IB/EB 检查结果；
- 冻结后变更、重新哈希和 supersede 规则。

Manifest 行至少包含：

```text
artifact_id / artifact_type / title / path_or_uri
version / sha256 / owner
content_status / effectivity_status
depends_on / open_item_count / blocking_scope
effective_at / supersedes / retention_class
```

`FRZ-00` 不能通过以下方式“完成”：把未存在附件登记为已批准、用目录存在替代内容审查、用 Git commit 替代签署、或用当前设计文件的 hash 替代整个候选包的 Manifest。

### 4.3 FRZ-01：采购源与条款基线

采购源文件表只允许以下正式来源类型：

- `SRC-PROCUREMENT`
- `SRC-CLARIFICATION`
- `SRC-CONTRACT`
- `SRC-AMENDMENT`
- `SRC-OFFICIAL-NOTICE`

每项记录：`source_id`、标题、出具方、编号、版本/日期、接收时间、URI、SHA-256、页数、适用页、完整性、法律状态、替代关系、核验人和核验时间。

条款目录至少记录：

```text
clause_id / source_id / page / section
requirement_nature / star_flag / subject / trigger
required_action / output / deadline_or_period / acceptance_phrase
lossless_summary / ambiguity / bd_refs / rq_refs / verified_by
```

不同正式文件存在冲突时只登记冲突和受影响范围，不由技术团队推断法律优先级。缺失文件必须有 `missing_source_id`、引用位置、索取责任人、所需日期、阻断的 RQ/BD/PKG 和未取得时的限制。

### 4.4 FRZ-02：BD 决策包

`FRZ-02` 保存索引、路由和影响回灌状态。每张卡遵循第 6 章模板，并满足“一卡一个核心问题”。卡片可以给出技术建议和多个可选方案，但不得预先勾选外部决定。

### 4.5 FRZ-03：三本账

`FRZ-03` 按第 5 章维护三本互斥台账。任何记录同时声称“采购原文”和“派生控制”即为冻结失败；任何假设没有验证方式、到期日或失败回退，同样不能进入 IB。

### 4.6 FRZ-04：架构批准基线

`FRZ-04` 至少包含：

- 架构意图、范围和部署边界；
- ADR-001—025 的完整决定、备选项、后果、Owner、验证和状态；
- D00—D15 的服务、聚合、唯一写者、权威存储和禁止写者；
- OpenAPI、AsyncAPI、Schema、状态、错误和兼容目录；
- 数据、对象、权利、安全、容量、灾备和迁移不变量；
- 附件 A—O 的成熟度和依赖；
- Detailed Design Review 与 Architecture Conformance Review 规则。

`BD-009` 未签时，Kafka/Milvus/Java-Python 等价方案最多标为 `TECH_APPROVED + BLOCKED_BY_BD`，不得标为“合同已认可”。

### 4.7 FRZ-05：验收与证据基线

`FRZ-05` 至少包含：

- 20 日、6 个月、12 个月和持续服务的原文范围与候选映射；
- 指标字典、数据集、金标、五项演示逐项脚本；
- TEST、EVID、DEL、PKG 目录及外键；
- 缺陷分级、整改、复验、豁免和签署权限；
- 原始日志、任务、模型、Prompt、Manifest、费用、Trace、媒体和 hash 的保留规则。

所有指标必须分列 `candidate_threshold` 与 `signed_threshold`。后者未签时保持空值并标记 `BLOCKED_BY_BD`，不能复制候选值充当签署值。

### 4.8 FRZ-06：商务、资源与最终签署

`FRZ-06` 至少包含：

- 范围—价格—资源—排除项—变更计价矩阵；
- 实名负责人、团队装载、GPU、Provider、环境、场地和网络；
- 使用实际 `C0/T0`、日历、前置、浮时和签署缓冲的 IMS；
- 背景 IP、定制成果、SBOM、模型/素材/字体/音乐和第三方权利；
- 7×24、4 小时、8 小时到场、24 小时、安全漏洞、培训和持续服务；
- 五个 BASE 登记、Go/No-Go 结论和最终签署页。

其中授权—资源矩阵必须按 `plan_id + action + environment + data_class` 逐项登记只读、写入、Provider Egress、费用上限/币种/付款方、破坏性动作、批准角色和有效期。至少分别管理：只读画像、合成数据验证、Sandbox 调用、小额真实 Canary、生产写入、数据回填、切换、删除/退役和正式交付；禁止用一个“项目已批准”覆盖全部动作。

`FRZ-06` 不得仅用 W26/W52 代替合同日历日期，也不得把 48.5 万元限价自动分摊为未经双方确认的阶段预算。

---

## 5. 来源、派生控制与假设三本账

### 5.1 分类命名空间

| 标签 | 含义 | 能否直接形成合同义务 |
|---|---|---:|
| `SRC-*` | 采购、澄清、合同、补充协议、正式通知 | 以来源法律效力为准 |
| `FACT-OBSERVED` | 仓库、数据、运行或测试核验事实 | 否 |
| `DEC-ADR` | 已批准的内部技术决定 | 否；除非合同另行吸收 |
| `CTRL-DERIVED` | 为安全、可靠、可迁移、可验收而派生的控制 | 否 |
| `ASM-PLANNING` | 排期、资源、容量或实施假设 | 否 |

`FACT-OBSERVED` 作为证据引用，不另建第四本需求账；ADR 进入 `FRZ-04`。三本账只管理来源需求、派生控制和计划假设。

### 5.2 需求原文账

字段：

```text
rq_id / clause_id / source_id / source_sha256 / page_section
requirement_nature / star_flag / lossless_summary
subject / trigger / required_output / deadline / acceptance_language
ambiguity / bd_refs / design_domain
del_refs / test_refs / evid_refs / pkg_refs / trace_status
```

约束：

- 不允许把 `DR-*`、`ADR-*`、建议阈值或当前系统事实放入来源字段；
- 原文变化通过新正式来源和版本关联表达，不修改历史记录；
- 页码、章节和 hash 缺一不可；缺页必须进入 `FRZ-01` 缺失源登记。

### 5.3 派生控制账

字段：

```text
dr_id / control_name / control_statement / risk_or_need
supports_rq_ids / not_source_clause_flag
owning_domain / adr_refs / implementation_boundary
verification_method / test_refs / evid_refs
approval_type / contract_scope_impact / owner / status
effective_at / retirement_condition
```

约束：

- `not_source_clause_flag` 必须恒为 `TRUE`；
- 若派生控制增加成本、范围、验收或外部义务，必须进入 BD/CR，而不能只由技术审批；
- 安全、金钱、租户、权利和不可逆副作用控制在外部参数未知时必须 fail-closed。

### 5.4 计划假设账

字段：

```text
asm_id / assumption_statement / basis / confidence / owner
used_by_artifacts / affected_scope_schedule_cost
allowed_use / prohibited_use / validation_method
external_decision_needed / bd_ref / needed_by / expires_at
fallback / rework_if_false / status
```

约束：

- 假设不能进入 `signed_threshold`、付款条件或正式验收结论；
- 到期未验证时，所有依赖项自动转为 `BLOCKED_BY_ASSUMPTION`；
- W26/W52、反馈 SLA、GPU 数量、Provider 配额和 OPEX 等必须保持假设，直至有正式依据。

### 5.5 三账交叉检查

每个冻结候选版本运行以下检查：

1. 每个强制 RQ 有唯一正式来源、页码和 hash；
2. 每个 DR 至少支持一个 RQ 或已登记风险；
3. 每个 ASM 有 Owner、到期、验证和失败回退；
4. 每个 RQ/DR/ASM 能反查 BD、ADR、DEL、TEST、EVID、PKG；
5. 不存在来源标签混写、循环追踪或悬空外键；
6. 所有从“采购要求”推导出的句子均可区分是原文还是工程解释。

---

## 6. BD-001—BD-013 决策包

### 6.1 独立决策卡模板

每张卡固定包含：

1. 文档控制；
2. 原始事实与来源；
3. 唯一待决问题；
4. 本卡明确不决定的事项；
5. 至少两个可执行选项及影响；
6. 技术建议、依据、限制和有效期；
7. 范围、进度、成本、验收、法律、数据、安全、运行影响；
8. 受影响的 RQ/DR/ASM/ADR/BASE/WP/MS/DEL/TEST/EVID/PKG；
9. 外部决定栏；
10. 生效、失效、过渡和旧版本处理；
11. 签署角色、授权依据和签署件；
12. 证据、版本和保留；
13. 差异合并、独立复核和回灌结果。

外部决定栏固定显示：

> 【留空，由有权主体填写，或引用已验真的正式签署附件。编制方不得代填。】

每个选项记录：`option_id`、范围、进度、成本、验收、法律/IP、安全/数据、运行、后续动作和可行性。技术建议节固定显示“本节不构成采购原文、合同解释或外部决定”。

### 6.2 决策索引

当前 13 项均为 `decision_status=OPEN / routing_status=NOT_STARTED`。下表定义送签问题、签署角色和未决时的最小安全边界，不代表任何选项已被接受。

| BD | 唯一待决问题 | 最低签署角色 | 最迟影响门 | 未决时允许 | 未决时禁止 |
|---|---|---|---|---|---|
| `BD-001` | 20 日、一期≤6个月、二期≤12个月的关系、起算点和验收层级 | AUTH-B/S、PROC-B、LEGAL-B/S、PM-B/S | BASE-CONTRACT、MS-20D/06M/12M | 设计、只读盘点、无付费验证 | 承诺完整重构期限或用 W26/W52解释日历月 |
| `BD-002` | 100%付款触发点与后续阶段义务、验收和IP触发关系 | AUTH-B/S、FIN-B/S、LEGAL-B/S | BASE-CONTRACT、FRZ-06、各PKG | 编制付款/交付候选矩阵 | 启动未明确付款范围或自行改称尾款 |
| `BD-003` | 算法研究目标、最低验收值和尽力义务边界 | PO-B、QA-B/S、SME-B/S、LEGAL-B/S | BASE-ACCEPT、FRZ-05 | 建候选指标、固定数据集和技术实验 | 承诺未签效果、把实验均值当合同阈值 |
| `BD-004` | 持续优化与固定总价、固定范围、质保/服务期的关系 | AUTH-B/S、FIN-B/S、LEGAL-B/S、SRE-B/S | BASE-CONTRACT/RESOURCE、PKG-SVC | 设计版本/报告/监控方法 | 把无限期优化当免费附带义务或擅自弱化原文 |
| `BD-005` | 背景IP、定制代码、开源、模型权重和第三方素材权利 | AUTH-B/S、LEGAL-B/S、PROC-B | BASE-DATA、DEL-IP-01、FRZ-06 | 盘点、SBOM、权利未知资产隔离 | 投产/移交权利未知资产或转移不可转让权利 |
| `BD-006` | 7×24、4小时、8小时到场、24小时、安全漏洞、交付地点、期限和成本 | AUTH-B/S、LEGAL-B/S、SRE-B/S、FIN-B/S | BASE-RESOURCE、TEST-SLA、PKG-SVC | 设计工单、演练和参考SLA | 承诺未知地点可达性、无限期免费服务或以建议弱化原文 |
| `BD-007` | 工业级、金融/行业级、毫秒级、人工干预减少60%的公式和阈值 | PO-B、QA-B/S、SEC-B/S、SME-B/S | BASE-ACCEPT、G7、PKG-12M | 定义候选公式、采集点和测试方法 | 进入终验承诺或更换原文“节点”口径 |
| `BD-008` | 60批/1200分钟的GPU、API、素材、标注、质检和重试成本归属 | AUTH-B/S、FIN-B/S、PM-B/S、SRE-B/S | BASE-RESOURCE、TEST-1200 | 仿真、容量模型、小样本无付费验证 | 启动规模生产或无预算真实调用 |
| `BD-009` | Kafka/RocketMQ、Milvus/Chroma、Java/Python边界及合同等效性 | ARCH-B/S、PROC-B、AUTH-B/S | BASE-ARCH、D00实施前 | 技术选型、模拟器、可替换合同 | 声称推荐栈已获合同认可或做不可逆绑定 |
| `BD-010` | 1000+分钟目标与60批/1200分钟测试是否共用分母和证据 | PO-B、QA-B/S、DATA-B/S | BASE-ACCEPT、TEST-1200 | 分开统计并保存原始数据 | 合并分母、重复计数或只报“合格分钟” |
| `BD-011` | 缺失第五章/完整附件及五项视频演示的提交时点、格式和复验规则 | AUTH-B、PROC-B、LEGAL-B/S、PO-B | FRZ-01、PKG-20D/6M/12M、G7 | 按已见条款做逐项可重放脚本 | 声称文件完整、默认演示属于20日或任一付款门 |
| `BD-012` | 第三方侵权保证、交涉、责任、费用、赔偿、上限、保险和处置权限 | AUTH-B/S、LEGAL-B/S、FIN-B/S | FRZ-06、DEL-IP-01、PKG-SVC | 权利台账、事件处置和证据保全设计 | 技术文档弱化原文或默认接受不可估算无限责任 |
| `BD-013` | 48.5万元覆盖范围、甲供资源、OPEX、第三方费用、排除项和变更计价 | AUTH-B/S、PROC-B、COMM-S、FIN-B/S | BASE-CONTRACT/RESOURCE、IMS、全部实施WP | W0设计、只读盘点、无付费验证 | 承诺全量重构、1200分钟和长期SLA均含在限价内 |

### 6.3 决策回灌要求

每个签署决定必须生成影响清单，至少覆盖：

```text
affected_rq_dr_asm / affected_adr / affected_base
affected_architecture_sections / affected_plan_sections
affected_wp_ms_gate / affected_del_test_evid_pkg
affected_scope_schedule_cost / affected_security_data_ip
merge_owner / reviewer / verification / effective_date
```

不得只把签署件放入目录而不更新主文档，也不得更新主文档后丢失签署件、原始来源或差异报告。

---

## 7. 技术基线、附件成熟度与 ACR

### 7.1 五个 BASE 的分层关闭

| BASE | IB 最低条件 | EB 新增条件 | 未满足的默认行为 |
|---|---|---|---|
| `BASE-CONTRACT` | 所有条款、冲突、BD和安全默认已登记 | 完整采购文件和适用 BD 取得有效签署并完成回灌 | 只做设计/只读/无付费验证 |
| `BASE-ARCH` | ADR、所有权、API/事件/状态/数据/安全不变量技术批准 | 合同等效、实际组织和生效范围确认 | 可做中立技术骨架，不做不可逆实现 |
| `BASE-DATA` | 只读画像方法、A/B/C/D、hash和隔离规则获批 | 生产分母、权利、保留、迁移批次和责任人签署 | 不回填生产，不迁移未知权利资产 |
| `BASE-ACCEPT` | 指标公式、候选数据集、证据格式、缺陷规则获批 | 正式数据集、阈值、执行/复核/签署角色生效 | 不声称 UAT/验收通过 |
| `BASE-RESOURCE` | 容量公式、参考Profile和资源登记方法获批 | 人员、GPU、Provider、场地、网络、预算、日期到位 | 不做真实付费、生产灰度或期限承诺 |

`V1.0-IB` 允许五个 BASE 处于“技术已批准、外部仍阻断”的组合；`V1.0-EB` 必须按适用范围全部达到 `base_result=VERIFIED_EFFECTIVE`。

### 7.2 附件 A—O 成熟度

附件 O 是本设计新增的**派生候选附件**，用于集中承载 Provider 不可逆副作用协议；它不是采购原文，也未在 V0.95 附件目录中实例化。

| 附件 | 内容 | IB 最低成熟度 | EB/生产前新增条件 |
|---|---|---|---|
| A | 服务、聚合、唯一写者、投影、数据所有权 | 首批服务卡和所有权 `TECH_APPROVED` | 实际Owner、账号、On-call和生产Schema生效 |
| B | REST/OpenAPI、鉴权、幂等、兼容和退役 | V1快照、目标契约、差异可自动校验 | 外部调用方、限流、SLA和退役日期确认 |
| C | Kafka/AsyncAPI/Schema、Topic、ACL、重试/DLQ | 核心流Payload、Key、顺序、Producer/Consumer锁定 | 生产分区、Retention、配额和托管形态生效 |
| D | Job/Attempt/Provider/Asset/Quality状态和错误 | 状态、守卫、事件、副作用、终态无歧义 | 生产处置、支持升级和验收映射生效 |
| E | MySQL字典、DDL、事务、唯一约束、分片、迁移 | 核心ERD、精度、Outbox/Inbox、路由和保留获批 | 生产数据画像、分片、备份和迁移批次批准 |
| F | Milvus、Embedding、Feature、Taxonomy | Collection、版本、重建、隔离、固定查询集获批 | 模型、规模、Recall@K/p95和资源生效 |
| G | Object/Result/Delivery Manifest和定稿 | Schema、哈希、签名、暂存—定稿、回收获批 | Bucket/地域、保留、权利和生产密钥生效 |
| H | 威胁、权限、数据分类、Secret、供应链 | DFD/STRIDE、RBAC/ABAC、租户、mTLS、Egress控制获批 | 安全标准、DPA、KMS/Vault和应急人员生效 |
| I | SLI/SLO、容量、成本、RPO/RTO、告警 | 公式、采集点、窗口、容量工作簿可复算 | 合同阈值、GPU/Provider配额、预算和告警责任生效 |
| J | 环境、BOM、部署、端口、网络、HA | 本地/云/混合参考Profile和配置Schema获批 | 指定地点、区域、GPU、证书、域名和副本生效 |
| K | 复用资产、SBOM、背景IP、第三方权利 | 来源、版本、许可证、复用/隔离方式完成盘点 | 法务完成权利、移交和责任结论 |
| L | 数据迁移、Cutover、Adapter、恢复、退役 | 写者、映射、影子、栅栏、在途和R1/R2/R3方法获批 | 生产分母、窗口、no-return和退役批准 |
| M | TEST/EVID/PKG、证据保存和重算 | 每项不变量有环境、输入、公式、Owner | 正式阈值、执行/复核/签署人和验收触发生效 |
| N | ADR、风险、假设、开放参数、决策日志 | ADR-001—025有完整内容和受控状态 | 涉及生产/合同的决定取得相应外部批准 |
| O | ProviderOperation Root/Epoch、Lease、Grant、Egress、财务和DR | 通用协议、五窗口、双实例/双站点性质测试设计获批 | 每个真实Provider的能力、账号、费用、地域和Canary批准 |

附件 N 是治理前置。首批实现前至少完成 A/B/C/D/E/H/N/O；真实媒体前完成 G；PreProd 前完成 I/J；迁移前完成 L；任何阶段包冻结前完成 M。依赖主版本变化时，受影响附件自动回到 `IMPACT_REVIEW`。

附件采用分段成熟，避免“必须先有完整附件才能编写产生该附件的计划”：

1. `00` 号治理计划先为 A/B/C/D/H/N/O 建立 `REVIEWED` 骨架，锁定 ID、范围、Owner、依赖、开放参数、禁止事项和目标成熟度；骨架不等于技术批准；
2. `01A` 消费上述骨架和 `FC-G3` 架构边界，将平台范围的 A/B/C/D/E/H/N 推进到 `TECH_APPROVED`，并形成 D00-CR 所需合同；
3. `19` 消费 O 骨架和平台合同，将 ProviderOperation 通用协议推进到 `TECH_APPROVED`；
4. 各领域计划只推进自身范围的附件分片；跨域合并由 FRZ-04 Manifest 验证，不要求一个计划一次完成全部 A—O；
5. 任何实现步骤开始前，其直接依赖的附件分片必须已达 `TECH_APPROVED`，不能以同一计划稍后会补为由越过。

### 7.3 首批关键服务卡

以下服务卡构成无付费垂直切片和未来小额真实 Canary 的安全脊柱：

- Gateway 与 Experience BFF；
- IAM；
- Creative Contract 最小模块；
- Asset；
- Model Factory；
- Production Orchestrator；
- Execution Control；
- Provider Egress；
- 首个 Generation Worker；
- D13 Ledger-Min；
- D14 Audit-Min；
- Compliance Policy-Min；
- Legacy Completion Adapter。

每张卡必须锁定唯一写者、禁止拥有的事实、API/事件/Schema、权威表/约束、调用身份/Secret/Egress、Deadline/回压、部署/Profile、迁移栅栏、恢复类别、TEST/EVID/Runbook 和准入 Gate。

### 7.4 Architecture Conformance Review

ACR 分为三个 Profile，防止在编码前要求只有运行后才能产生的证据：

| Profile | 输入 | 适用时点 | 能证明什么 |
|---|---|---|---|
| `ACR-DESIGN` | 批准候选附件、ADR、状态/不变量、威胁、容量/恢复模型和计划测试 | `V1.0-FC -> V1.0-IB` | 设计内部一致、可实施、外部参数已隔离；不证明代码或运行已达标 |
| `ACR-IMPLEMENTATION` | 代码/镜像/配置/Schema、合同测试、安全扫描、故障注入和恢复演练 | 每个领域 WR/EX、首次环境晋级或实现扩围前；CR 前只使用 DDR/`ACR-DESIGN` | 实现符合批准设计并具备目标环境准入条件 |
| `ACR-PRODUCTION` | 生产候选配置、真实监控/对账/DR/迁移证据、Runbook和变更单 | Canary、扩灰、ORR、100%和退役前 | 命名范围具备动作审批所需运行证据 |

ACR 在以下时点强制执行：

1. `V1.0-FC -> V1.0-IB`；
2. 每个领域 CR 前执行 DDR/`ACR-DESIGN`，WR/EX及首次环境晋级前执行 `ACR-IMPLEMENTATION`；
3. 首个真实 Provider/GPU 小额 Canary 前；
4. 每个 Cutover Wave 扩大生产写比例前；
5. ORR、100% 灰度和旧系统退役前；
6. ADR、主版本、所有权、数据路由、Provider协议、安全区、RPO/RTO或生产拓扑实质变化后。

ACR 结论只允许 `PASS`、`PASS_WITH_CONDITIONS`、`FAIL`。对 `ACR-DESIGN`，若设计允许下列模式、缺少对应防护或没有可执行验证方案即 `FAIL`；对后两种 Profile，若实现或运行证据出现下列事实即 `FAIL` 且不得豁免：第二写者、跨服务直写真相库、Worker绕过Egress、Provider/Grant/费用无法解释、未知状态自动重提、D06/D13不能100%对账、跨租户、Secret泄漏、权利未知资产投产、关键Schema未批准、无恢复路径、旧站点仍有外呼能力、或模拟证据冒充生产/UAT。

---

## 8. 验收与证据冻结

### 8.1 指标字典

每项指标登记：

```text
metric_id / rq_id / name / definition
numerator / denominator / unit / direction / aggregation
window / population / exclusions / data_source / environment
hardware_provider_model / candidate_threshold / signed_threshold
bd_ref / owner / approver / evidence_ref / status
```

重点指标必须保持原始口径并可追加辅助指标。例如“人工干预节点减少60%以上”以节点为主口径；人工分钟/成片分钟只能作为辅助，除非有正式书面变更。

### 8.2 数据集与演示

数据集必须有版本、hash、来源、权利、样本/时长、拆分、标注、金标Owner、冻结日、访问级别和保留期。五项演示必须拆到采购原文每个 bullet，关联固定输入、操作者、步骤、可见结果、后台任务/模型/Prompt/日志/指标/Trace/媒体、录像要求和证据 ID。

`BD-011` 未关闭时，演示脚本可以达到 `REVIEWED`，但 `submission_stage` 保持 `BLOCKED_BY_BD-011`，不得默认放入 20 日、6 个月或 12 个月包。

### 8.3 Evidence 状态

证据状态只允许：

```text
PLANNED
BLOCKED
NOT_RUN
RUN_FAILED
RUN_PASSED_UNREVIEWED
REVIEWED_PASSED
SIGNED_ACCEPTED
SUPERSEDED
```

只有 `REVIEWED_PASSED` 可证明内部技术门通过；只有 `SIGNED_ACCEPTED` 可进入正式验收结论。页面存在、容器健康、测试历史记录或口头确认均不能替代所需证据状态。

### 8.4 Evidence Manifest

每项正式证据至少包含：

```text
evidence_id / rq_dr_test_del_pkg_ids / source_baseline_id
environment / time_window / commit_image_config_schema
model_prompt_dataset_versions / hardware_provider_mode
sample_denominator_exclusions / raw_log_uri_hash
metric_trace_uri_hash / media_uri_hash / pass_formula
executor / reviewer / approver / result
defect_waiver_refs / retention / signed_at
```

签署值、正式数据集和签署人未生效前，Evidence Manifest 可以设计和演练，但不能生成 `SIGNED_ACCEPTED`。

---

## 9. 签署、差异合并与冻结流程

### 9.1 标准流程

1. **固化来源：** 登记正式文件、hash、页码、版本、缺失项和冲突；
2. **实例化候选：** 创建 FRZ-00—06、13 张卡、三本账和机器索引；
3. **内部交叉评审：** ARCH、QA、PM、SEC、DATA、FIN、LEGAL 按职责复核；
4. **形成 FC：** 内容稳定、开放项受控、外部决定栏保持空白；
5. **IB治理受控 Diff：** 若采用 IB，先修订总体架构 §0.3 与迁移计划 §0.1/§0.5，明确 IB 不等于外部生效基线且只允许批准的非生产范围；修订未生效时旧规则优先；
6. **技术批准：** 可内部决定的部分完成 DDR/`ACR-DESIGN`，形成 IB；
7. **生成签署副本：** 锁定版本和 hash，登记要求的签署角色和授权依据；
8. **外部路由：** 有权主体选择、改写或拒绝，编制方不得代填；
9. **验真归档：** 核对授权、签名、时间、附件和 hash；
10. **追加正式来源：** 决定作为澄清/合同/补充协议/通知登记，不覆盖原采购源；
11. **三方 Diff：** 比较 V0.95、FC 候选值和签署决定；
12. **生成影响清单：** 更新 RQ/DR/ASM/ADR/BASE/WP/MS/DEL/TEST/EVID/PKG、预算和风险；
13. **窄范围回灌：** 每个变更关联 `merge_id + bd_id + signed_hash`；
14. **独立复核：** 检查是否误改原文、越权解释或产生新冲突；
15. **重新哈希：** 更新 Manifest，旧候选 `SUPERSEDED`；
16. **EB 评审：** 五个 BASE 关闭后形成相应范围的生效基线；
17. **动作审批：** 具体实现、Canary、Cutover、验收和退役继续走独立 Gate。

### 9.2 差异类型

差异只允许以下类型：

```text
EDITORIAL
SOURCE
INTERPRETATION
SCOPE
SCHEDULE
ACCEPTANCE
ARCHITECTURE
DATA_SECURITY
COMMERCIAL_IP
AUTHORIZATION
```

`SOURCE/INTERPRETATION/SCOPE/SCHEDULE/ACCEPTANCE/COMMERCIAL_IP/AUTHORIZATION` 不得只由技术负责人批准。

### 9.3 冻结后变更

- 新正式来源先进入 FRZ-01，再触发 BD/影响分析；
- 受影响制品进入 `IMPACT_REVIEW`，不直接覆盖已签署件；
- 变更单必须列影响范围、兼容、数据、安全、成本、迁移、验收和恢复；
- 主版本变化重新运行引用、Schema、证据和 ACR 检查；
- 到期决定、到期假设或撤销授权使相应范围自动失效；
- 历史版本、签署件和 Manifest 按保留策略继续可追溯。

---

## 10. 从冻结设计到详细设计与执行计划

### 10.1 本文的交付边界

本设计经用户评审确认后，下一步才进入 `superpowers:writing-plans`，先生成“候选包实例化与 00 号治理计划”草案，而不是直接编码。该计划必须逐文件列出：路径、输入、输出、Owner、检查命令、签署停点和提交边界。用户对本规格的确认不自动代替组织内 PM/ARCH/QA 的正式 Gate 登记，更不代替采购、合同或法务签署；正式启用该计划仍以 `FC-G0` 为准。严格只读的 `01B-Discovery` 可以在来源和授权 Gate 满足后并行规划；其余详细计划按下述 Gate 分段生成。

### 10.2 FC Gate

| Gate | 必须通过的事实 | 通过后允许 |
|---|---|---|
| `FC-G0 SPEC-APPROVED` | 本设计的目的、边界、字段、状态机、批准权限经用户及内部 PM/ARCH/QA 评审认可 | 编制 `00` 治理计划，由其建立并运营来源/FRZ登记；不授权编码 |
| `FC-G1 SOURCE-VERIFIED` | 已取得采购/主文档/工程/运行来源有版本、hash和完整性；缺失附件有 `missing_source_id`、引用位置、索取责任/期限和阻断范围 | 使用已核验事实写计划；不得为缺失来源虚构版本/hash或用假设补齐 |
| `FC-G2 CONTRACT-ACCEPTANCE` | 适用 BD、阶段、付款、IP、SLA、演示、数据集/公式/阈值和签署权关闭 | 编制承诺性阶段、财务和验收计划 |
| `FC-G3 ARCH-BOUNDARY` | 适用 ADR、所有权、版本、安全区、DR和外部副作用边界获批 | 编制 `01A` 和 `19` 的无代码协议/详细设计计划 |
| `FC-G4 DATA-RESOURCE-AUTH` | 数据只读权限、分类/保留、环境、人员、GPU、Provider和预算授权明确 | 编制精确 `01B` 及相应非生产计划 |
| `FC-G5 BASELINE-FROZEN` | G0—G4通过，适用 BASE 无阻断，Digest 和变更控制签署 | 编制涉及付费副作用、迁移、切换的设计/演练计划；实现级计划仍需IB Ready，且不授权实施 |

`FC-G4` 可按严格范围形成 `FC-G4-DATA` 等子结果，但必须明确只授权何种数据、环境和动作；局部结果不能冒充完整 G4。Gate Register 至少登记：`gate_id`、`criteria_id`、所需证据、`PASS/FAIL/BLOCKED`、复核/批准角色、决定时间、是否允许豁免、豁免范围/到期和下一步允许动作。

P0、安全、数据、金钱、重复副作用和采购核心要求不得通过豁免放行。`writing-plans` 准入不等于编码授权；子计划还必须通过自身 DoR 和决策点。

### 10.3 首批计划波次

首批应沿安全关键路径滚动展开，不同时生成全部 24 份。下表在 IB Ready 前均指**设计阶段计划**，只产出受控合同、附件和验证设计，不包含生产代码实施步骤：

| 顺序 | 子计划 | 对应总计划 | 最早计划准入 | 额外前置 | 退出物 |
|---:|---|---|---|---|---|
| 1 | 实施基线、来源、BD、三账与验收治理 | `00-项目治理、需求追踪与验收基线` | `FC-G0` | 无需BD全部关闭；本计划建立G1来源登记并推动后续Gate关闭 | FRZ实例化、BASE/BD路由、机器索引；A/B/C/D/H/N/O `REVIEWED`骨架 |
| 1B | 数据迁移工厂严格只读 Discovery | `01` + `15`的只读前置 | `FC-G0 + FC-G1 + FC-G4-DATA` | 数据Owner、只读权限、安全/法务范围 | 数据/媒体/Provider/Secret画像方法和 `PROFILED` 门；不写目标库 |
| 2A | D00平台基础、API/事件合同设计 | `01-平台基础、API事件合同与迁移工厂` | `FC-G3 + FC-G4` | A/B/C/D/H/N `REVIEWED`骨架及适用ADR | 平台范围 A/B/C/D/E/H/N `TECH_APPROVED`；D00-CR所需详细合同，不创建空壳服务 |
| 2B | ProviderOperation不可逆副作用协议 | `19` | `FC-G3` | O `REVIEWED`骨架；先做协议Spec；实现级计划需 `01A-CR` | O通用协议 `TECH_APPROVED`；Root/Epoch/Lease/Grant/Egress/D13/DR接口和性质测试设计 |
| 3A | D13 Ledger-Min | `12` 最小切片 | `FC-G2 + FC-G3 + FC-G5` | `19-CR`，D01/D05/D06接口达到CR | 首个真实调用前的财务唯一写者详细设计 |
| 3B | D14 Audit-Min | `13` 最小切片 | `FC-G2 + FC-G3` | `01A-CR`，审计/Trace/保留规则获批 | 首个真实写入前的追加审计详细设计 |
| 4 | 在途任务Registry与Legacy Completion Adapter | `16` | Charter可在`FC-G3 + FC-G4` | 精确计划需 `01B PROFILED`、D04/D06/D13接口CR及`19-CR` | 旧任务接管、晚到、费用、Manifest和禁止重提协议 |

日历窗口不能覆盖依赖 Gate。以上七项不是同一时点全部精确编写：`FC-G0` 后立即可写的只有 `00`；来源登记和数据只读授权分别达到 `FC-G1`、`FC-G4-DATA` 后，才可写严格只读的 `01B-Discovery`；架构/资源 Gate 后可写 `01A` 和 `19` 协议层；CR 和适用冻结条件满足后再写 `12A/13A`；生产画像和跨域接口 CR 后才写 `16A` 精确计划。“同一波次”只表示容量可并行，不表示依赖已满足。

当 `IB_READY` 且某一直接依赖附件分片已达 `TECH_APPROVED` 后，才为相应子计划生成独立的实现级版本；该版本必须重新做 Freshness Check，并增加精确代码/Schema路径、失败测试、TDD步骤、验证命令和提交边界。设计阶段计划不得通过后续章节夹带实现任务。

### 10.4 FC Handoff Register

候选包必须对每个消费者计划登记：

```text
consumer_plan_id
required_fc_artifacts_and_versions
required_upstream_cr_or_profiled
locked_inputs / open_inputs_allowed / blocking_inputs
consumer_outputs / consumer_exit_gate
reopen_condition / invalidation_notification_owner
```

消费者计划不得复制一份静态 FC 结论后脱离变更控制。来源、BD、ADR、Schema、预算、阈值或数据范围变化时，Handoff Register 必须通知受影响计划重新做 Freshness Check。

### 10.5 写计划前的必备输入

每份后续子计划必须读取并锁定：

- 本设计的批准版本和 hash；
- 最新总体架构、迁移总计划和相关附件；
- 适用 RQ/DR/ASM/BD/ADR/BASE；
- 当前仓库 commit、工作区状态、运行/数据/对象证据；
- 源/目标唯一写者、API/事件/状态/错误/字段映射；
- 恢复类别、no-return、外部副作用和批准停点；
- DEL/TEST/EVID/PKG 与精确验证命令。

缺任何一项时，子计划只能输出调查或设计任务，不得伪装为可执行编码计划。

---

## 11. 完成定义与 Go/No-Go

### 11.1 本设计评审通过条件

- [ ] FC/IB/EB 与生产动作批准边界无歧义；
- [ ] FRZ-00—06 的职责、字段、Owner、批准角色和退出门完整；
- [ ] BD-001—013 均有唯一问题、签署角色、最迟 Gate 和 fail-closed 行为；
- [ ] 三本账来源互斥，未把派生控制或假设写成采购原文；
- [ ] 附件 O 明确为派生候选，不冒充已有或采购要求；
- [ ] 签署、回灌、独立复核、重新哈希和 supersede 闭环；
- [ ] 后续计划波次有依赖、有输入输出，但尚未越过设计评审点；
- [ ] 文档中没有代填外部决定、伪造签署或擅自关闭 OPEN 项；
- [ ] Markdown、表格、状态、ID和引用检查通过；
- [ ] 文档级 P0/P1 为 0。

### 11.2 V1.0-FC Ready

```text
FC_READY =
  FRZ_00_TO_06_EXIST
  AND BD_001_TO_013_CARD_READY
  AND SOURCE_LABELS_EXCLUSIVE
  AND ACQUIRED_SOURCE_TRACE_VALID
  AND MISSING_SOURCE_REGISTERED_AND_FAIL_CLOSED
  AND OPEN_ITEMS_OWNED_AND_FAIL_CLOSED
  AND DOCUMENT_P0_P1_ZERO
  AND NO_EXTERNAL_DECISION_FABRICATED
  AND FINAL_MANIFEST_HASHED
```

FC Ready 时必须继续显式声明：**不授权生产写入、真实付费调用、数据迁移、数据删除、正式交付或合同验收。**

### 11.3 V1.0-IB Ready

```text
IB_READY =
  FC_READY
  AND INTERNAL_TECH_ARTIFACTS_TECH_APPROVED
  AND ACR_DESIGN_PASS
  AND PARENT_BASELINE_DIFF_EFFECTIVE
  AND EXTERNAL_PARAMETERS_ISOLATED
  AND NONPROD_FAIL_CLOSED_CONTROLS_VERIFIED
  AND NO_UNOWNED_OPEN_PARAMETER
```

IB 仅允许批准范围的详细设计、执行计划、编码和非生产验证。

### 11.4 V1.0-EB Ready

```text
EB_READY =
  IB_READY
  AND PROCUREMENT_SOURCE_COMPLETE
  AND APPLICABLE_BD_SIGNED_DECISION
  AND ALL_APPLICABLE_BD_IMPACTS_VERIFIED
  AND APPLICABLE_BASE_VERIFIED_EFFECTIVE
  AND SIGNATURE_AUTHORITY_VERIFIED
  AND SCOPE_PRICE_RESOURCE_IP_SLA_ACCEPTANCE_ALIGNED
  AND EFFECTIVE_MANIFEST_HASHED
```

全平台 EB 还要求 `BD-001`—`BD-013` 全部满足以上条件。EB 不等于生产变更批准。

### 11.5 条件性 Go

本阶段建议 **Go：编制并评审 V1.0-FC 候选包**。以下事项继续 No-Go：

- 把 V0.95 或本设计直接改名为已生效 V1.0；
- 未取得完整采购文件即宣称采购符合性完整；
- 未签 BD 即启动承诺性实施、真实付费或规模生产；
- 未形成附件 O 和 D13/D14 最小安全脊柱即开展真实 Provider Canary；
- 未完成数据画像、权利分级和恢复设计即迁移本地/生产数据；
- 未取得范围—价格—资源—排除项结论即承诺 48.5 万元覆盖全量重构、1200分钟和长期SLA；
- 用技术评审、Git hash、会议纪要或测试全绿代替有权主体签署和正式验收。

---

## 12. 当前评审请求

本文件当前只请求确认以下设计决定：

1. 是否采用 `V1.0-FC -> V1.0-IB -> V1.0-EB -> 动作批准` 四层控制；
2. 是否按 `FRZ-00`—`FRZ-06` 实例化冻结候选包；
3. 是否将 13 个 BD 拆成独立、外部决定栏留空的签署卡；
4. 是否采用来源需求、派生控制、计划假设三本账；
5. 是否把附件 O 作为 Provider 不可逆副作用的派生候选详细设计；
6. 是否在本设计确认后，先生成候选包实例化/00号治理计划，并按 `FC-G0`—`FC-G5` 分段生成其余首批子计划，而不是一次性假精确或直接批量编码。

在以上设计获得确认前，本文保持 `DRAFT`，不创建候选包实例、不进入 writing-plans 执行阶段，也不对现有工程做实现性修改。
