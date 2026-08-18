# 服务器部署运维与回滚手册

## 运行边界

- 应用：`/srv/ai-video-platform/current`。
- 配置：`/srv/ai-video-platform/shared/production.env`，权限 `600`。
- 持久化数据：`/srv/ai-video-platform/data`，包含 PostgreSQL、Redis、Caddy 和媒体文件。
- 临时数据：`/srv/ai-video-platform/runtime`。
- 中文字体：宿主机 `/usr/share/fonts/opentype/noto`，通过 `AI_VIDEO_FONT_ROOT` 只读挂载到 API 容器。

任何应用替换都不得删除 PostgreSQL、Redis、媒体目录和用户级加密模型连接。供应商 Key 不得进入源码、镜像、日志或发布包。

## 发布步骤

1. 校验发布包哈希和当前 `production.env` 权限。
2. 默认先执行 PostgreSQL 备份；只有用户明确要求直接替换时才能跳过，并记录没有数据库恢复点。
3. 执行 `docker compose --env-file /srv/ai-video-platform/shared/production.env -f compose.production.yml up -d --build`。
4. 等待代理、前端、API、PostgreSQL、Redis 全部 healthy。
5. 验证 `/healthz`、登录、模型默认绑定、实模任务、媒体公网 URL 和字幕成片。
6. 使用 `docker exec ai-video-platform-api-1 fc-match 'Noto Sans CJK SC'` 验证中文字体；抽帧检查字幕，不能只检查文件存在。

## 回滚

应用回滚使用：

```bash
/srv/ai-video-platform/current/ops/deploy/rollback.sh
```

回滚只切换应用版本，不自动倒退数据库。若本次按要求跳过备份，只能回退应用代码，不能覆盖发布后新增业务数据。发现新版本异常时先停止新任务写入，再确认数据兼容性后回滚。

## H3 补丁回滚点

- 代码涉及提示词组合、H3 提交/轮询、媒体持久化、合成发布状态和中文字体挂载。
- 回退字体挂载会导致中文字幕重新出现方框，因此回滚后必须重新执行字幕抽帧检查。
- 已生成媒体位于持久化卷，不随容器重建删除；历史失败草稿仅设为停用，可恢复审计。

## 健康检查

```bash
docker compose --env-file /srv/ai-video-platform/shared/production.env \
  -f /srv/ai-video-platform/current/compose.production.yml ps
curl -fsS http://127.0.0.1:8080/healthz
curl -fsSI http://127.0.0.1:8080/login
```

公网 `8080` 与 SSH 管理口属于不同网络路径；本机健康但公网失败时，先检查 NAT、防火墙和上游转发，不要通过重装应用掩盖网络问题。

## 默认提示词目录补丁

API 启动时会幂等执行 `bootstrap_production.py`，补齐系统共享提示词并投影为已发布版本。本补丁新增角色提取与场景/道具提取两个子阶段模板，只新增系统目录记录，不覆盖用户模板、模型绑定或用户密钥。

部署后必须验证：

```bash
curl -fsS -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8080/api/v1/model-center/prompt-usage-map
```

预期两个实体提取环节均返回 `status=effective`、模板非空，汇总中的 `internal_fallback=0`。如需回滚应用代码，新增的已发布系统模板可保留，不执行数据库删除；旧版本会忽略无法使用的新子阶段模板。
