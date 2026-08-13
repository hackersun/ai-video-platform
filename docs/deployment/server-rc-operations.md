# 服务器试部署操作与回滚手册

## 版本定位

此版本是 `v1.0.0-rc.1` 服务器试部署候选，用于验证安装、启动、登录、模型配置和核心生产流程。它不是商业正式发布；商业结论仍以 `docs/release/commercial-release-gates.md` 为准。

## 目录约定

- `/srv/ai-video-platform/packages/incoming`：待部署归档。
- `/srv/ai-video-platform/releases/<版本>`：不可变源码版本。
- `/srv/ai-video-platform/shared/production.env`：服务器独有密钥，权限必须为 `600`。
- `/srv/ai-video-platform/backups`：升级前 PostgreSQL 备份。
- `/srv/ai-video-platform/data`：数据库、缓存和正式媒体持久化数据。
- `/srv/ai-video-platform/runtime`：允许按保留策略清理的临时数据。
- `current` / `previous`：当前和上一版本软链接。

## 首次安装

1. 使用具备 sudo 权限的账号执行：`sudo bash ops/deploy/install-docker-ubuntu.sh`。
2. 重新登录 SSH，运行 `docker version` 和 `docker compose version`。
3. 复制 `ops/deploy/production.env.example` 到 `/srv/ai-video-platform/shared/production.env`。
4. 生成强随机值：数据库和 JWT 使用至少 32 字节随机值；Fernet 使用 `python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`，也可在可信机器生成后安全写入服务器。
5. 执行 `chmod 600 /srv/ai-video-platform/shared/production.env`。

## 发布

```bash
ops/deploy/deploy.sh \
  /srv/ai-video-platform/packages/incoming/ai-video-platform-v1.0.0-rc.1-<commit>.tar.gz
```

默认入口为 `http://服务器IP:8080`。发布脚本会校验 SHA-256、备份现有数据库、构建镜像、启动容器并验证前端、API 和版本接口。

## 验收

```bash
AI_VIDEO_BASE_URL=http://127.0.0.1:8080 ops/deploy/healthcheck.sh
docker compose --env-file /srv/ai-video-platform/shared/production.env \
  -f /srv/ai-video-platform/current/compose.production.yml ps
```

随后通过浏览器验证登录、供应商账号、模型目录、默认模型、提示词使用地图、小说/章节/实体/剧本/分镜/镜头和受控视频任务。

## 回滚

```bash
/srv/ai-video-platform/current/ops/deploy/rollback.sh
```

应用回滚不会自动倒退数据库迁移。当前迁移为向前兼容的增量迁移；如需恢复数据，应先停写，再使用 `backups/*-predeploy.dump` 经人工确认后恢复，禁止在有新业务数据时自动覆盖数据库。

## 安全要求

- PostgreSQL 和 Redis 不发布主机端口。
- 只对外开放应用端口；获得域名后再配置 HTTPS。
- Provider Key 只能写入服务器环境或在平台中按用户配置，不得写入归档和 Git。
- 首次部署完成后立即轮换聊天中出现过的 SSH 密码，并保留 SSH Key 登录。
