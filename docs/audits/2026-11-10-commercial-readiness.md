# 商用就绪审计（只读）

- **审计日期**：2026-11-10（Asia/Shanghai）
- **分支**：`feat/series-run-redis-queue-and-tail-fsm`
- **HEAD**：`c91fc5f923fc4f90a4ef49a6f7cd0b1598279d52`（2026-11-08 17:46 +0800，docs: P1 实施结果）
- **范围**：鉴权与密钥、费用上限、正式环境试用/额度、限流网关、多租户隔离、PostgreSQL vs SQLite、对象存储、可观测性、部署手册、ToS/隐私草稿、滥用防护、视频分发、备份、生产 vs 假模式、代码健康阻塞项
- **方法**：只读审代码与现有门禁文档；**不改代码、不 commit、不 push、不开 PR、不 git stash**
- **对照文档**：`docs/release/commercial-release-gates.md`、`docs/security/commercial-security-baseline.md`、`docs/product/commercial-gap-analysis.md`（2026-08-08 基线）、本分支 11 月前端全流程验证与 P0/P1 简化结果

---

## 1. 总结论（Go / No-Go）

| 场景 | 结论 | 说明 |
|---|---|---|
| 内测 / 演示（模拟模型 + 本机或受控 staging） | **有条件 Go** | 一键小说→成片主链路在 `DETERMINISTIC_PROVIDER_FAKE=1` 下已可走通；P0/P1 UI 简化后新手点击约 6 次 |
| 邀请制小流量实模（自带 Key，不公开注册收费） | **有条件 Go（窄口）** | 需强制 `APP_ENV=production`、私有对象存储、Redis worker、费用 opt-in + ¥50/¥200 上限、关闭假模式；仍缺网关限流与深度健康检查 |
| **公开注册 + 收费运营** | **No-Go** | 会话安全、邮箱验证、API 限流、企业级多租户、可观测性/告警、法务终稿、正式试用额度与对账闭环均未达标 |

**一句话**：产品主链路与费用硬闸已具备“可商用候选”的技术底座，但按仓库自身 G0–G8 门禁，**仍不能宣称可公开收费上线**。

---

## 2. 分项现状矩阵

图例：✅ 已具备可用实现 · ⚠️ 部分具备/有缺口 · ❌ 缺失或生产不安全

| 主题 | 状态 | 关键证据 | 收费前判定 |
|---|---|---|---|
| 鉴权与密钥 | ⚠️ | JWT 默认密钥仍存在代码路径；Access 24h；Refresh 不轮换/不撤销；token 在 `localStorage`；密码最少 6 位、注册即激活、无邮箱验证；生产 Compose 强制 `JWT_SECRET_KEY`/`FERNET_KEY`，`assert_production_safe()` 拒绝 DEV_MODE/假模式/弱存储 | **必须项** |
| 费用上限（¥50 / ¥200） | ✅ | `billing_guard.DEFAULT_PIPELINE_CAP_RMB=50`、`DEFAULT_USER_CAP_RMB=200`；可被 `BILLING_PER_*_CAP_RMB` 覆盖；ledger 预扣/结算/释放/blocked_cap；假数据不计费；Key 检测通过后前端可自动 opt-in | 已落地；正式收费仍缺钱包/退款/供应商对账（应做） |
| 正式环境试用/额度 | ⚠️ | 「免费试用」依赖非生产 + `DETERMINISTIC_PROVIDER_FAKE`；生产拒绝假模式 → **正式环境无零成本试用路径**；无平台侧赠送额度/钱包 | **必须项**（产品决策：赠送额度 / 示例片 / 仅自带 Key） |
| 限流网关 | ❌ | Caddy 仅反代 `/api` `/static` `/healthz`，无 rate limit；应用层无 slowapi/登录注册限流；仅供应商 429 文案映射 | **必须项** |
| 多租户隔离 | ⚠️ | 资源普遍 `user_id` 过滤；`ProjectMember` owner/editor/viewer 部分 API；无组织/工作区/统一权限矩阵；DEV_MODE 无令牌可落 `dev-user-001` | 个人自带 Key 可暂缓企业 RBAC；公开收费前 **必须** 关闭 DEV 旁路并补越权合同测试 |
| PostgreSQL vs SQLite | ⚠️ | 默认 SQLite；`compose.production.yml` 使用 PostgreSQL + 持久卷；有 PG 契约测试（需真实 PG job）；迁移仍是 `db_migrations`/`create_all` 伴侣，**无 Alembic 标准链** | 生产 **必须** PG；Alembic/升级演练为应做 |
| 对象存储 | ⚠️ | G4：`STORAGE_PROVIDER=s3|qiniu`、私有桶、签名 URL、生产拒 local（除非显式允许）；七牛交付与发布路径有测试；生产 Compose 默认仍 `STORAGE_PROVIDER=${...:-local}`，运维若未改 env 会踩坑 | **必须项**：生产 env 配私有桶并做真实上传/播放验收 |
| 可观测性 | ❌ | `/health` 静态 healthy；Caddy `/healthz` 静态 ok；无统一 request id、指标、追踪、告警、依赖 readiness | **必须项**（至少 liveness/readiness + 结构化日志 + 关键告警） |
| 部署手册 | ✅ | `docs/deployment/*`、`ops/deploy/{deploy,rollback,healthcheck,package-release}.sh`；部署前 `pg_dump`；拒绝 `CHANGE_ME_` | 手册可用；需按真实环境补一次演练记录（应做） |
| ToS / 隐私 | ⚠️ | 前后端 `2026-11-05-draft`；注册强制同意；页面标明「草案，需法务审核」 | 公开收费前 **必须** 法务终稿 |
| 滥用防护 | ⚠️ | `provider_prompt_safety` 对视频提示词做敏感词改写；无注册/登录验证码、无内容审核队列、无滥用举报后台 | 公开注册前 **必须** 至少登录/注册/生成限流 + 基础内容策略 |
| 视频分发 | ⚠️ | 发布走 readiness 门禁；`sign_media_url` / 私有签名；`?download=1` Content-Disposition；无独立 CDN 策略与热链防护文档化 SLA | 自用可；对外分发应做 CDN/过期/盗链策略 |
| 备份 | ⚠️ | `deploy.sh` 升级前 `pg_dump -Fc`；手册写明不自动回滚 DB；**缺**对象存储备份、定期备份、恢复演练 RPO/RTO 证据 | 收费前 **必须** DB+媒体备份与至少一次恢复演练 |
| 生产 vs 假模式 | ✅/⚠️ | `assert_production_safe` 拒 `DETERMINISTIC_PROVIDER_FAKE`、DEV_MODE、DEV_TOKEN；假模式与 live opt-in 分离；Compose `DEV_MODE=false` | 配置正确则安全；本地默认 DEV 仍易误配到“像生产”的环境 |
| 代码健康 | ⚠️ | 2026-11-06 记录约 **92** 个相对基线阻塞；本审计扫描 **109** 个阻塞（721 文件 / 154919 有效行）。基线内 `known_violations` 约 **252**。以 `legacy_file_grew` 与超长页面为主，**不直接阻断功能**，但增加商用维护风险 | 可延后收敛；禁止继续扩大热点（棘轮应守住） |

---

## 3. 相对 2026-08 差距分析：已消化 vs 仍阻塞

### 已明显改善（本分支证据）

1. **持久队列**：`series-run-worker` / `publication-pipeline-worker` + Redis 进入生产 Compose；不再只靠进程内 `create_task` 作为唯一路径。
2. **费用硬闸**：不可变倾向的 `billing_ledger` + 用户 opt-in + 默认 ¥50/次、¥200/账号。
3. **生产启动 fail-closed**：`APP_ENV=production` 下拒绝假模式与 DEV 旁路；存储私有化校验。
4. **私有媒体路径**：对象存储抽象 + 签名访问 + 生产 env 示例。
5. **部署拓扑**：单公网入口（Caddy）、PG/Redis/Worker 不暴露端口；备份优先脚本。
6. **产品易用性（P0/P1）**：欢迎二选一、保存并检测、粘贴小说、单入口一键生成、进度 4 步、试用无确认框等（见 UI 简化文档）。

### 仍为公开收费 No-Go 的核心阻塞

1. 会话与账号安全（短 Access + HttpOnly Refresh 轮换/撤销、邮箱验证、强密码、限流）。
2. 网关/应用限流与滥用面。
3. 可观测性（真实 readiness、指标、告警）。
4. 正式环境试用/平台额度产品方案。
5. 法务终稿与数据导出/删除闭环。
6. 真实模型小额验收 + 真实桶 + PG 恢复演练的**运行证据**（代码契约 ≠ 线上验收）。

---

## 4. 收费前清单

### 4.1 必须项（Must，任一未完成 → 维持 No-Go）

| ID | 项 | 验收标准 |
|---|---|---|
| M1 | 生产密钥与 DEV 旁路 | `APP_ENV=production`；无默认 JWT；无 DEV_TOKEN；启动自检失败即退出；FERNET/MEDIA_SIGNING 独立强随机 |
| M2 | 会话加固（最小集） | Access ≤15min；Refresh HttpOnly+Secure+轮换/可撤销；前端不再长期依赖 localStorage 存长期令牌 |
| M3 | 注册登录防护 | 密码 ≥12 + 弱口令检查；邮箱验证或邀请码；登录/注册/重置 **限流** |
| M4 | 网关限流 | 对 `/api/v1/auth/*`、生成/上传/轮询分档限流（Caddy 或 API 中间件） |
| M5 | PostgreSQL 生产库 | 禁用 SQLite 作为生产；迁移升级与回滚手册演练通过 |
| M6 | 私有对象存储实配 | `STORAGE_PROVIDER=s3|qiniu` 凭证齐全；成片/封面签名播放与下载；跨租户 403/404 |
| M7 | 费用闸实跑 | 实模小额（建议 ≤¥5 canary）验证 opt-in、¥50/¥200 阻断、假数据不计费 |
| M8 | 备份恢复 | 升级前 DB 备份 + 媒体备份策略；至少一次 restore 演练并记录 RPO/RTO |
| M9 | 健康与告警最小集 | readiness 检查 DB/Redis/存储；进程挂/队列积压告警有人值守 |
| M10 | 法律文本 | ToS/隐私法务终稿替换 draft；注册同意版本号与后端一致 |
| M11 | 正式试用策略落地 | 明确三选一并实现：**平台赠送额度** / **仅示例片** / **必须自带 Key**（当前生产实际接近第三种，但欢迎页文案仍提免费试用） |

### 4.2 应做项（Should，上线后 30–60 天内）

| ID | 项 |
|---|---|
| S1 | Alembic 成为唯一迁移通道；废弃散落 companion migration 的双轨 |
| S2 | 组织/工作区 RBAC + API 权限矩阵合同测试 |
| S3 | 供应商账单 vs 内部 ledger 对账；退款/冲正流程 |
| S4 | CDN/防盗链、成片保留期、删除回执 |
| S5 | 统一审计事件（登录失败、密钥变更、额度调整、发布、导出） |
| S6 | 依赖锁定与高危 CVE 清零；Next/后端可复现构建 |
| S7 | 内容安全：异步审核、用户举报、违规下架 |
| S8 | 代码健康：拆分 `workflow.py` / 小说详情超长页等热点，阻塞项压回基线以下 |

### 4.3 可延后（Defer）

| ID | 项 |
|---|---|
| D1 | 企业 SSO/OIDC、MFA |
| D2 | 完整财务套餐/席位/合同计费 |
| D3 | 多区域容灾与自动故障切换 |
| D4 | 历史 Git 大对象/媒体瘦身（约数百 MB 级历史，需单独确认） |
| D5 | 运营后台全家桶（客服工单、状态页） |
| D6 | 基线内全部 252 个 known_violations 清零 |

---

## 5. 生产配置矩阵（推荐）

| 变量 | 生产值 | 说明 |
|---|---|---|
| `APP_ENV` | `production` | 触发 fail-closed |
| `DEV_MODE` | `false`（或不设，由 production 默认 false） | 禁止无令牌用户 |
| `DETERMINISTIC_PROVIDER_FAKE` | **unset / 非 1** | 生产启动直接拒绝 =1 |
| `DATABASE_URL` | `postgresql://...` | 禁止生产 SQLite |
| `REDIS_URL` | `redis://redis:6379/0` | Series Run / Pipeline worker 必需 |
| `JWT_SECRET_KEY` | 强随机，非 CHANGE_ME、非代码默认值 | Compose 已 `:?` 强制 |
| `FERNET_KEY` | 合法 Fernet 32B | 模型 Key 加密；丢钥则旧密文不可解 |
| `MEDIA_SIGNING_KEY` | 独立强随机 | 勿回落到 JWT 默认 |
| `STORAGE_PROVIDER` | `s3` 或 `qiniu` | **不要**依赖 Compose 默认 local |
| `ALLOW_LOCAL_STORAGE_IN_PRODUCTION` | `0` | 除非应急且有书面例外 |
| `STORAGE_BUCKET_ACL` | `private` | 禁止 public-read |
| `STORAGE_SIGNED_URL_TTL_SECONDS` | `900`（可按播放调整） | 短时签名 |
| `BILLING_PER_PIPELINE_CAP_RMB` | `50.00` | 与产品确认一致 |
| `BILLING_PER_USER_CAP_RMB` | `200.00` | 与产品确认一致 |
| `POSTGRES_PASSWORD` | 强随机 | deploy.sh 拒 CHANGE_ME_ |
| 供应商 Key | 用户自带或 Secret Manager | 不进镜像/日志/前端 |

**假模式 vs 生产对照**

| 能力 | 假模式（内测） | 生产 |
|---|---|---|
| 模型调用 | 本地确定性产物 | 真实供应商 |
| 费用 | ledger `is_fake`，不计上限 | 必须 opt-in + 上限 |
| 试用入口 | 「免费试用」可用 | 不可用假模式；需 M11 方案 |
| 存储 | 可为 local | 私有桶 |
| 数据库 | SQLite 可 | PostgreSQL |

---

## 6. 风险表

| ID | 等级 | 风险 | 现状 | 缓解 |
|---|---|---|---|---|
| CR-01 | P0 | 令牌窃取 / 无法可靠登出 | localStorage + 长 Access + Refresh 不撤销 | M2 |
| CR-02 | P0 | 撞库 / 批量注册 | 无限流、弱密码、无邮箱验证 | M3/M4 |
| CR-03 | P0 | 费用失控 | 上限代码在，但实模验收与对账未做；测试 helper 可把 cap 提到极大 | M7；禁止生产调用测试 opt_in helper |
| CR-04 | P0 | 媒体越权或公网裸奔 | 代码支持私有桶，Compose 默认 local 易误配 | M6；部署检查清单勾选存储 |
| CR-05 | P0 | 故障不可见 | 静态 health | M9 |
| CR-06 | P0 | 正式环境“免费试用”名不副实或误导 | 生产拒假模式 | M11；文案与能力对齐 |
| CR-07 | P1 | 租户越权 | 主要靠 user_id，权限矩阵不全 | S2；先补关键资源越权测试 |
| CR-08 | P1 | Schema 漂移 | 无 Alembic 标准链 | S1 |
| CR-09 | P1 | 法律/合规 | draft ToS/隐私 | M10 |
| CR-10 | P2 | 代码健康恶化 | 阻塞 92→**109** | 棘轮禁止净增；S8 分期拆文件 |
| CR-11 | P1 | 备份不完整 | 仅有升级时 pg_dump | M8 |
| CR-12 | P2 | 提示词安全仅替换词 | 可被绕过 | S7 |

---

## 7. 分阶段上线建议

### 阶段 A — 内测加固（1–2 周）

- 配齐生产 env：PG、Redis、私有桶、密钥；关闭假模式。
- 完成 M1、M5、M6、M8、M9 最小集。
- 实模 canary ≤¥5，验证 M7。
- 前端保持当前简化主路径；不扩专业入口。

**出口**：邀请用户可稳定一键出片；费用不超过上限；备份可恢复。

### 阶段 B — 受限公开（邀请码 / 等候名单）

- 完成 M2、M3、M4、M10、M11。
- 打开有限注册；强限流；内容安全底线。
- 仍不宣称「平台代收费」，优先「用户自带 Key + 平台上限保护」。

**出口**：有条件 Go（窄口公开）。

### 阶段 C — 收费运营候选

- 完成 S1–S5、供应商对账、客服/退款路径。
- 走完 `commercial-release-gates.md` G0–G8 取证。
- 代码健康阻塞回落到约定阈值。

**出口**：门禁全绿后方可营销「可商用收费」。

---

## 8. Go/No-Go 检查清单（签字用）

- [ ] M1 生产密钥与 DEV 旁路
- [ ] M2 会话加固
- [ ] M3 注册登录防护
- [ ] M4 网关限流
- [ ] M5 PostgreSQL 生产 + 迁移演练
- [ ] M6 私有对象存储实配验收
- [ ] M7 费用闸实模验收（含 ¥50/¥200）
- [ ] M8 备份恢复演练记录
- [ ] M9 readiness + 告警
- [ ] M10 法务终稿
- [ ] M11 正式试用/额度产品方案已实现且文案一致
- [ ] 实模 + 前端关键路径截图/日志归档
- [ ] 发布负责人 / 安全负责人 / 法务 签字

**当前审计 ent：上述勾选均为未完成或证据不足 → 公开收费 = No-Go。**

---

## 9. 代码健康附注（2026-11-10 扫描）

```text
扫描文件: 721
有效代码行: 154919
相对基线阻塞项: 109
分类概览: legacy_file_grew 65, react_component_too_long 14,
          react_page_too_long 12, function_too_long 11,
          service_imports_endpoint 5, route_too_long 1, new_file_too_long 1
基线 known_violations（历史快照）: ~252
```

与 2026-11-06 维护记录中的「约 92 个既有阻塞」相比，本分支后续功能（一键管道、计费、UI 简化等）使相对基线阻塞增至 **109**。建议：商用功能优先；结构收敛单开批次，避免与功能 PR 混提。

---

## 10. 审计产物

- 本文：`docs/audits/2026-11-10-commercial-readiness.md`
- 打包：`~/Documents/avp-audit-ops.tgz` → CopyToBox `/workspace/audit110/ops/`
- 机器可读代码健康报告（本机临时）：`/tmp/avp-code-health-20261110.json`（未入库）

---

*本文件为只读审计产出，不构成法务或财务意见；上线决策以门禁证据与负责人签字为准。*
