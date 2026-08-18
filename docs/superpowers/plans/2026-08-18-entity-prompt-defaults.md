# 实体提取默认提示词补齐计划

## 执行合同

- **目标锁定：** 让角色提取、场景/道具提取分别命中可发布、全用户共享的中文默认提示词，不再回退到代码内置提示词。
- **范围边界：** 不修改提示词路由优先级，不覆盖用户自定义模板，不调整模型密钥、默认模型、字幕或成片合成逻辑。
- **约束：** 两个模板继续使用 `entity_extraction` 任务键，通过 `character` 与 `scene_prop` 子阶段区分；启动初始化必须幂等。
- **验收标准：** 两个子阶段均存在独立内置模板；恢复后生成两份已发布系统模板；远程使用地图由 2 个 `internal_fallback` 变为 0。

## 实施步骤

1. 增加失败测试，覆盖两个子阶段的模板标识、中文内容和幂等恢复。
2. 在默认提示词目录增加角色提取、场景/道具提取模板，保留旧通用实体模板兼容既有调用。
3. 运行提示词路由、模型中心和生产启动相关测试。
4. 更新生产操作与回滚文档，部署远程 API 并核对使用地图。

## 验证命令

```bash
cd backend
pytest -q tests/test_default_prompt_skills.py tests/test_prompt_usage_map.py tests/test_prompt_usage_contract.py tests/test_production_deployment_contract.py
```
