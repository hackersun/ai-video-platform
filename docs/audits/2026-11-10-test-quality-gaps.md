# 测试与质量缺口审计（2026-11-10）

- **范围**：只读审计。不改业务代码、不 commit、不 push、不开 PR、不 git stash。
- **工程**：`/Users/sunqinyue/Documents/work/BJDEV/claude/ai-video-platform`
- **分支 / HEAD**：`feat/series-run-redis-queue-and-tail-fsm` @ `c91fc5f9`（docs: P1 实施结果 + p1-after screenshots）
- **审计时区**：Asia/Shanghai（CST）
- **基线（对话已知）**：backend ~1902 pass / 1 skip；Playwright ~301 pass / 21 skip；typecheck/lint 干净；`assets.spec` 高压偶发；假模式 `/tmp/avp-e2e`
- **对照门禁**：`docs/release/commercial-release-gates.md`（G0–G8）
- **原则**：缺口用新测试补齐；**不放宽现有断言**；假模式通过 ≠ 商用就绪。

---

## 1. 结论（先看这里）

1. **假模式主链路可用**（注册→试用→粘贴→一键生成→看片→下载→发布）已有大量手工截图与部分后端/UI 用例支撑，**不能**据此宣称商用就绪。
2. **CI 门禁偏弱**：触发分支不含本功能分支；无 Playwright；无 lint；无 Redis/worker 集成；PostgreSQL 仅跑 2 个契约文件。
3. **新手路径 Playwright 几乎全是 `page.route` Mock**：欢迎页、保存并检测、¥50/¥200、排队文案、粘贴导入等**未证明真实后端 + Redis worker + 媒体落盘**。
4. **真模型失败映射**主要覆盖「连接测试」路径；生成中失败→中文可执行修复动作（G5）缺口大。
5. **费用上限**后端 ledger 测试扎实；**前端到真实扣费/触顶阻断**仍靠 Mock，缺「触顶后不可再提交」的端到端证明。
6. **多角色**有后端回归（归档再激活 / 自动绑音色相关修复），**无**「多说话角色一键到成片」的 Playwright 真链路。
7. **队列恢复**有 fakeredis 单测；**无**「worker 停机→排队提示→重启自动续跑」的自动化门禁。
8. **下载/发布**：有附件头与 Mock 下载用例；**缺**跨域前后端部署、私有桶签名过期、发布后对外可见性的商用级证明。
9. 宣称商用前必须拿到 **§6 最小商用门禁套件** 的证据；缺任一项 = No-Go。

---

## 2. Pytest 布局与隔离

### 2.1 布局

| 位置 | 规模 | 说明 |
|---|---|---|
| `backend/tests/test_*.py` | ~200 文件 | 主树：队列、billing、publication pipeline、model center、series run… |
| `backend/test_*.py`（根目录） | ~51 文件 | 历史/路由级用例，与 `tests/` **双树并存** |
| `backend/conftest.py` | 会话级隔离 | 唯一仓库级 conftest（不含 venv） |
| 无 `pytest.ini` / `pyproject` testpaths | — | 默认收集两棵树；CI 用 `pytest` 在 `backend/` 下跑 |

**风险**：双树增加「改一处漏一处」与重复夹具成本；根目录用例更容易误用共享引擎/路径习惯（虽已被 conftest 挡大部分）。

### 2.2 隔离（做得对的部分）

`backend/conftest.py` 在 import 时：

1. **清掉环境 e2e 污染**：`DETERMINISTIC_PROVIDER_FAKE`、`REDIS_URL`、`SERIES_RUN_QUEUE_BACKEND`、`PUBLICATION_PIPELINE_*`、`E2E_REQUIRE_ISOLATED_DB` 等。
2. **每会话独立 SQLite**：`/tmp/avp-pytest-*/test.db`，并设 `E2E_REQUIRE_ISOLATED_DB=true`。
3. 可用 `AVP_TEST_DATABASE_URL` 显式覆盖（PostgreSQL 契约）。

`app/core/database.py` 对 `E2E_REQUIRE_ISOLATED_DB` 强制要求 SQLite 路径在 `/tmp`，防止写回 `backend/ai_video.db`。

生产守卫：`runtime_env.assert_production_safe` 在生产拒绝 `DETERMINISTIC_PROVIDER_FAKE` / `DEV_MODE` 等。

### 2.3 仍在的隔离缺口

| 缺口 | 严重度 | 说明 |
|---|---|---|
| 仓库根仍有 `ai_video.db`（约 64MB） | P1 | 开发库与历史测试残留并存；UI 曾隐藏 live-* 供应商，**库内数据未清** |
| 根级 `test_*.py` 与 `tests/` 双树 | P2 | 收集路径、命名与夹具不统一 |
| Redis 队列单测用 **fake/AsyncMock**，CI **无 Redis service** | P0 | reclaim/单飞有单测，但无真实 Redis + worker 进程联调门禁 |
| PostgreSQL CI 仅 `test_postgresql_runtime_contract.py` + `test_script_chapter_lineage_migration.py` | P0 | 商用目标库几乎未跑主链路 |
| 假模式需测试主动 `monkeypatch.setenv` | OK | 设计正确；但本地 `/tmp/avp-e2e` 与 pytest 并行时若忘记清环境，曾导致假阴性/假阳性——conftest 已修，需保持 |

---

## 3. Playwright 覆盖现状

### 3.1 规模与配置

- `frontend/e2e/*.spec.ts`：**101** 个文件；对话基线约 **301 pass / 21 skip**。
- `playwright.config.ts`：自启 `next dev`；默认 `E2E_API_URL=http://localhost:8000/api/v1`；CI retries=2、workers=1；**但 GitHub Actions 根本不跑 Playwright**。
- 大量 live/canary 用例 `test.skip`，需 `E2E_LIVE=1` / `PRODUCTION_OS_LIVE=1` 等显式开关。
- 根 `package.json`：`verify:e2e` **只跑 smoke**；完整 e2e / 新手套件不在 `verify:quick`。

### 3.2 关键旅程覆盖图

图例：✅ 有自动化且较可信｜🟡 Mock/UI 层有、真链路弱｜❌ 缺失或仅手工｜⛔ 依赖真 Key/预算，默认 skip

| 旅程步骤 | 后端 pytest | Playwright（默认 CI/本地全量） | 假模式手工 `/tmp/avp-e2e` | 真模型小额 | 商用证明够不够 |
|---|---|---|---|---|---|
| 注册 / 登录 / 条款 | 部分 auth | 🟡 smoke + login-redesign（部分 skip） | ✅ | ❌ | 不够 |
| 欢迎二选一（试用 / Key） | 弱 | 🟡 `onboarding-simplification`（全 Mock） | ✅ | ❌ | 不够 |
| 保存并检测 + 默认开真实调用 ¥50/¥200 | ✅ billing API/ledger | 🟡 同上 Mock 断言 PUT body | ✅（无效 Key 文案） | ⛔ 未正式跑 | 不够 |
| 粘贴小说 / 自动标题 | ✅ import 相关 | 🟡 `novel-paste-import` Mock | ✅ | ❌ | 不够 |
| 一键生成（演示无确认） | ✅ publication/one-click 等 | 🟡 `one-click-confirm-and-queue` Mock | ✅ | ⛔ | 不够 |
| 真实模式费用确认框 | — | 🟡 Mock 文案 ¥50/¥200 | ✅ 文案 | ⛔ 触顶未证 | 不够 |
| 多说话角色不卡住 | ✅ multi-char reactivation 等 | ❌ 无对应 e2e | ✅ 曾手工踩中并修复 | ⛔ | **关键缺口** |
| 进度 4 段 / 排队中提示 | 弱 | 🟡 排队文案 Mock | ✅ | ❌ | 不够 |
| Worker 停机 → 恢复续跑 | 🟡 fakeredis reclaim | ❌ 无端到端 | ✅ 手工 | ❌ | **关键缺口** |
| 成片可播（H.264） | ✅ ffmpeg 相关 | 🟡 media-player Mock | ✅ | ⛔ | 不够 |
| 下载（attachment / 跨域） | ✅ private_media download 标志 | 🟡 full-flow / media-player | ✅ 本机 | ❌ 跨域部署 | 不够 |
| 发布记录 / 不可发原因 | ✅ commercial gates 单元 | 🟡 synthesis-history Mock | ✅ | ❌ | 不够 |
| 私有对象存储 + 签名 URL | 🟡 qiniu 单测 | ❌ | ❌ | ❌ | **关键缺口** |
| 失败中文映射（生成时） | 🟡 连接测试映射 | ❌ | 部分 | ⛔ | **关键缺口** |
| 费用触顶阻断再提交 | ✅ ledger SpendCap | ❌ 无真链路 e2e | ❌ | ⛔ | **关键缺口** |
| PostgreSQL 主链路 | 🟡 2 文件契约 | ❌ | ❌ | ❌ | **关键缺口** |
| 网关限流 | ❌ | ❌ | ❌ | ❌ | **关键缺口** |

### 3.3 「有测试」但虚假信心的来源

1. **`DETERMINISTIC_PROVIDER_FAKE=1`**：`deterministic_config_test_result` **任意配置检测直接 success**（「模拟模式：连接正常」）→ 无效 Key 在假模式下也会「通过」。
2. **Playwright 新手套件 `page.route('**/api/v1/**')`**：页面文案可以全绿，后端/队列/计费零执行。
3. **CI `verify` 路径**：Actions 跑 pytest + typecheck + build，**不跑** 101 个 e2e；本地 `verify:quick` 仅 smoke。
4. **live canary 默认 skip**：仓库里有 four/five-chapter live 规格，但日常绿并不能代表实模。
5. **生产库残留 live-\***：UI 过滤 ≠ 数据干净（G7「正式环境不出现验收模型」未自动化）。

---

## 4. 缺口排序（不放宽断言）

### P0 — 挡商用宣称

| ID | 缺口 | 现状 | 建议补法（新断言，不放松旧的） |
|---|---|---|---|
| Q-P0-1 | CI 无 Playwright / 无 lint；功能分支不触发 | `ci.yml` 仅 main/releases/dev；frontend-tests 无 e2e、无 `next lint` | 增加门禁 job：typecheck + lint + **最小商用 e2e 套件**；PR 到 protected 分支必跑 |
| Q-P0-2 | 新手关键路径无「真后端」e2e | onboarding / one-click / paste 全 Mock | 新增 `e2e/commercial-novice-fake.spec.ts`：起 `/tmp/avp-e2e` 同款假模式 API+worker，禁止 route mock，跑通到可播 mp4 |
| Q-P0-3 | 真模型失败映射未覆盖生成路径 | `connection_failure_message` 仅连接测试 | 为 series-run / publication 失败码→中文修复动作加表驱动测试；实模用无效 Key/欠费 Key 各 1 次取证 |
| Q-P0-4 | 多角色一键无前端自动化 | 仅后端 + 历史手工 | Playwright 假模式：≥2 说话角色小说一键到 completed；断言无 `required_entity_state_invalid` |
| Q-P0-5 | 队列恢复无端到端门禁 | fakeredis reclaim 单测 | 脚本：enqueue → kill worker → UI「排队中」→ 拉起 worker → completed；CI 用 Redis service |
| Q-P0-6 | 费用上限无「触顶阻断」e2e | ledger 单测强；UI Mock | 假账本或注入已用额度：确认框展示已用；二次提交返回阻断且 ledger `blocked_cap` |
| Q-P0-7 | 下载/发布商用路径不完整 | 本机 download OK；跨域/私有桶弱 | 后端 Content-Disposition 契约保留；加「API 与前端不同源」下载用例；发布后签名 URL 过期与私有可见性 |
| Q-P0-8 | PostgreSQL / 对象存储 / 限流未证 | PG 仅 2 文件；无网关限流测试 | 扩 PG 契约到 publication one-click；对象存储用 minio/契约；限流用集成测试 |

### P1 — 质量与防回归

| ID | 缺口 | 建议 |
|---|---|---|
| Q-P1-1 | `assets.spec` 高压偶发（共享全局资产侧栏计数） | 资产列表 API 按 owner 严格隔离；e2e 断言改为精确 testid，避免全局计数；加 flake quarantine 标签但**失败仍计失败** |
| Q-P1-2 | 双 pytest 树 | 迁移根 `test_*.py` → `tests/`，统一收集 |
| Q-P1-3 | 共享 `ai_video.db` 测试残留 | 一次性清理脚本（需人工确认）+ 启动时拒绝生产加载 live-* |
| Q-P1-4 | `verify:e2e` 过窄 | `verify:commercial-min` 绑定 §6 套件 |
| Q-P1-5 | TTS/生成错误细分 | 运行时错误统一走 `connection_failure_message`（或同级映射表），避免通用文案 |

### P2 — 清理与文档

| ID | 缺口 | 建议 |
|---|---|---|
| Q-P2-1 | 旧 `e2e/` 目录与 `frontend/e2e` 并存 | 文档标明废弃；CI 不跑 legacy |
| Q-P2-2 | live 规格环境变量矩阵复杂 | 一张「实模开关矩阵」表进 docs/testing |
| Q-P2-3 | code-health 92 blockers 基线 | 保持 baseline；新债零增长 |

---

## 5. Flake 清单

| 用例 / 场景 | 现象 | 已知原因 | 状态 | 处置 |
|---|---|---|---|---|
| `frontend/e2e/assets.spec.ts` | `--repeat-each=4 --workers=8` 偶发：保存超时 / 侧栏计数混入全局资产 | 并发用户隔离不足 + 全局资产列表 | **仍偶发**（正常全量未复现） | P1：收紧列表过滤；精确断言；不要用 retry 掩盖 |
| `production-os-frontend-acceptance` #6 | 与后端全量并行时 `ERR_ABORTED` | Mock 缺 `shots` → 页面 map 崩溃（已修容错） | **已修**；曾单独重跑 3/3 绿 | 保持断言；并行时仍建议分 job |
| 历史「12 个后端失败」 | 环境假模式污染 + 脏 DB | 已由 `conftest.py` 隔离 | **已修** | 禁止再放宽断言「适应脏环境」 |
| live canary 默认 skip | 全量绿但不含实模 | 设计如此 | 预期 skip | 不得把 skip 当 pass 汇报商用 |

**纪律**：flake 用隔离/确定性修复；**禁止** `test.fix` / 放宽 timeout 当长期方案；CI retry 仅作缓冲，根因必须立项。

---

## 6. 最小商用门禁套件（命令 + 预期）

> 目标：在宣称「可商用」之前，下列命令在干净环境全部按预期通过，并保留日志/截图/产物哈希。

### 6.1 每次 PR / 合并前（无真 Key）

```bash
# A. 后端全量（隔离 DB）
cd backend
tmp_db=$(mktemp /tmp/avp-ci-XXXXXX.db)
DATABASE_URL="sqlite+aiosqlite:///$tmp_db" E2E_REQUIRE_ISOLATED_DB=true \
  ../venv或./venv/bin/python -m pytest -q
# 预期：~1902+ passed，failed=0；skip 仅 ffmpeg/PG 等显式条件

# B. 前端静态
cd frontend && npm run typecheck && npm run lint
# 预期：exit 0

# C. 最小商用 Playwright（假模式真后端，禁止 API mock）— 待补文件后：
# DETERMINISTIC_PROVIDER_FAKE=1 REDIS_URL=redis://127.0.0.1:6379/0 \
#   SERIES_RUN_QUEUE_BACKEND=redis \
#   npx playwright test e2e/commercial-novice-fake.spec.ts \
#     e2e/commercial-multichar-fake.spec.ts \
#     e2e/commercial-queue-recovery-fake.spec.ts \
#     e2e/one-click-confirm-and-queue.spec.ts \
#     e2e/onboarding-simplification.spec.ts \
#     --project=chromium --workers=1
# 预期：passed；0 failed（其中 commercial-* 为待新增真后端套件）

# 现阶段可跑的「弱替代」（仍不够商用）：
cd frontend && npm run e2e:smoke
# 预期：smoke 全绿（仅证明壳与登录 CTA）
```

### 6.2 发布候选额外（仍可无真 Key）

```bash
# D. PostgreSQL 契约（扩展前至少）：
DATABASE_URL=postgresql://... DEV_MODE=true \
  pytest -q tests/test_postgresql_runtime_contract.py \
         tests/test_script_chapter_lineage_migration.py
# 预期：pass；随后应扩到 publication/billing 子集

# E. 生产拒绝假模式：
APP_ENV=production DETERMINISTIC_PROVIDER_FAKE=1 python -c \
  "from app.core.runtime_env import assert_production_safe; assert_production_safe()"
# 预期：抛错，含 DETERMINISTIC_PROVIDER_FAKE

# F. 假模式一键（本机 harness）
# source /tmp/avp-e2e/env.sh && ./serve.sh && ./run_e2e_8000.sh && ./poll.sh
# 预期：pipeline completed；产物 mp4 可播（H.264）；下载 Content-Disposition=attachment
```

### 6.3 宣称商用前强制（真 Key，预算封顶）

```bash
# G. 实模小额（用户确认后；Key 走密钥通道，不进聊天）
# VOLC_API_KEY 来自 secret；预算：单次 ≤ ¥5～¥10，账户观察 ≤ ¥50 试验额度
# 只跑 1 章；全程截图；记录 ledger reserved/settled/blocked
# 预期：
#   1) 有效 Key：1 章完成或失败有中文可执行提示；费用 ≤ 预算
#   2) 无效 Key：检测失败文案含「API Key 无效」；live_calls 不误开或生成被拒
#   3) 触顶：提交被拒，ledger 有 blocked_cap，UI 可见

# H. 多角色实模或假模式强制自动化（至少假模式 CI）
# 预期：≥2 说话角色不卡在故事设定锁定

# I. Worker 恢复
# 预期：停 worker 见「排队中」；恢复后同一 run 完成，无重复计费

# J. 对象存储 + PG + 限流
# 预期：私有桶签名播放/下载；PG 上跑通同一新手路径；超限返回 429 且不丢任务状态
```

### 6.4 套件与 G 门禁映射

| 套件步骤 | 主要映射 |
|---|---|
| A–B | G1 |
| C、F、H、I | G4、G7 |
| E | G2 |
| D、J | G3、G4 |
| G | G5、G6 |
| 监控/回滚（本审计未展开） | G8 — 仍为开放项 |

---

## 7. 假模式带来的虚假信心（专门列出）

| 假象 | 实际 | 如何拆穿 |
|---|---|---|
| 「保存并检测」全绿 | 假模式不调用供应商 | 生产/非 fake 下用无效 Key；断言 fail 文案 |
| 一键 8 秒出片 | 本地确定性媒体 | 看 provider_task_id / ledger is_fake |
| Playwright 301 绿 | 多数关键新手用例 Mock | 查 spec 是否 `page.route`；加无 mock 套件 |
| CI 绿 | 无 e2e、无 Redis、功能分支不跑 | 看 `ci.yml` |
| 模型中心「干净」 | 只是 UI 隐藏 live-* | 查 DB 供应商行数 |
| 费用上限「已接」 | UI 文案 + ledger 单测 | 缺触顶 e2e 与实模对账 |

---

## 8. 宣称商用就绪前必须证明什么

对照 `commercial-release-gates.md`，**至少**具备下列证据包（缺一则只能写「假模式可用 / 受限试用」）：

1. **构建**：typecheck、lint、production build、镜像摘要；pytest 全绿（隔离 DB）。
2. **新手真链路**：无 API mock 的注册→配置→粘贴→一键→可播→下载→发布（假模式可先过，但不能止步于此）。
3. **多角色**：≥2 说话角色同一路径不卡死（自动化）。
4. **队列**：真实 Redis；worker 崩溃恢复；单飞不双花。
5. **费用**：opt-in、¥50/次与 ¥200/账户默认值、触顶阻断、假行不计入总额、生产环境忽略 fake 逃逸。
6. **失败体验**：无效 Key / 欠费 / 缺 App ID / 网络超时 → 中文原因 + 下一步（生成路径，不只是连接测试）。
7. **媒体**：H.264 可播；下载 attachment；私有存储签名；发布门禁（preview 不可发）。
8. **数据面**：PostgreSQL 上主链路或等价契约扩面；备份恢复演练记录。
9. **实模小额**：1 章、预算封顶、截图与 ledger 对账。
10. **安全/运维**：无 DEV_MODE/fake 进生产；限流；密钥不进仓；监控与回滚（G8）。

**明确不允许的表述**：

- 「Playwright 全绿所以商用就绪」
- 「假模式跑通所以供应商已验证」
- 「ledger 单测在所以用户不会超花」

---

## 9. 建议落地顺序（仍不改本审计之代码）

1. 先加 **CI**：lint + 最小假模式真后端 e2e + Redis service（对应 Q-P0-1/2/5）。
2. 补 **多角色 / 排队恢复 / 费用触顶** 三条自动化（Q-P0-4/5/6）。
3. 扩 **失败映射到生成路径**（Q-P0-3）。
4. 用户授权后做 **¥5 实模**（Q 文档外执行，密钥走 secret）。
5. PG + 对象存储 + 限流（Q-P0-8）。
6. 清理双树与脏 DB（Q-P1-2/3），**不放宽任何断言**。

---

## 10. 审计产物

| 路径 | 说明 |
|---|---|
| `docs/audits/2026-11-10-test-quality-gaps.md` | 本文 |
| `~/Documents/avp-audit-qa.tgz` | 打包副本 |
| `/workspace/audit110/qa/`（box） | CopyToBox 目标 |

---

## 11. 元数据

- 审计执行：Grok Bot executor subagent（只读）
- 机器：`7fb36126-8274-451d-b39c-f965b1eda55e`
- 时间：2026-11-10（Asia/Shanghai）
