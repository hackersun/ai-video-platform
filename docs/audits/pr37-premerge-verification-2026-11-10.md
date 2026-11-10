# PR #37 合并前全量验证（2026-11-10）

- **分支**：`feat/series-run-redis-queue-and-tail-fsm`
- **验证开始 HEAD**：`a7593145`（W1 pack+stop）
- **机器**：`7fb36126-8274-451d-b39c-f965b1eda55e`，路径 `/Users/sunqinyue/Documents/work/BJDEV/claude/ai-video-platform`
- **约束**：不 stash、不改写历史、不索要 Key、不跑实模扣费

## 套件结果

| 套件 | 结果 | 说明 |
|---|---|---|
| 工作区 | 干净；`git pull --rebase` 已与远端同步 | 验证开始时已与 `origin` 同为 `a7593145` |
| backend pytest | **2470 passed, 3 skipped, 0 failed**（约 4m17s） | 隔离 SQLite；`DEV_MODE` 测试 Fernet；见下方环境坑 |
| frontend typecheck | 通过（`tsc --noEmit`） | 修 banner 后再跑仍绿 |
| frontend lint | 通过（No ESLint warnings or errors） | |
| Playwright chromium 全量 | **306 passed, 21 skipped, 0 failed**（约 2.6m） | 需本机 DEV_MODE API（`localhost:8000`）。21 skip 为实模/live canary（无 Key，按设计跳过） |

## 过程中发现并已修

1. **pytest 环境泄漏（假失败）**  
   首次全量出现 257 failed / 54 errors，根因不是产品回归：  
   - 环境里残留非法 `FERNET_KEY`（非 32-byte url-safe base64）→ `test_model_center_api` setup error；  
   - `tests/test_commercial_rate_limit.py` 在 **import 时**写入 `API_RATE_LIMIT_GENERATE=2` 等，污染后续所有生成类用例 → 大量 429。  
   **修复**：`backend/conftest.py` 丢弃非法 Fernet、默认 memory 限流与测试额度、用例间 `reset_rate_limits`；商业闸门测试改为只在 fixture 里 monkeypatch 低限额。

2. **Playwright 专家页横幅（W1 真实缺口）**  
   全量（有 API、`E2E_API_URL=http://localhost:8000/api/v1`、不复用脏 Next）后仅剩 2 红：  
   - `series-studio-end-to-end` 仍断言旧文案「这是高级工具…回到工作室统一管控」，且需要「回到工作室」按钮；  
   - `studio-smart-console` 命令条被 in-flow 横幅顶出 1058px 视口（约 +84px）。  
   **修复**：横幅改为导航下固定细条（不占 studio 文档流），保留 W1 文案与「去小说页」，非 `/studio` 路径补「回到工作室」；e2e 文案对齐 W1（未放宽几何断言）。复跑 6 条定点 + 全量 306/21/0 通过。

## 建议

**可以合并**（在本轮修复 commit 推上后）。未跑真实模型付费验收；21 条 live/canary Playwright 与 3 条 pytest skip 不阻塞。首次 pytest 红是环境泄漏，修复后全绿，合并前请勿再在全量 pytest 外壳里 source e2e `env.sh` 或留下非法 `FERNET_KEY`。
