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

## 2026-08-18 最新版直替验收记录

- 部署版本：`v1.0.0-rc.1`，源码基线 `cee0757d`，并包含当次工作区已验证的最新改动。
- 生效目录：`/srv/ai-video-platform/releases/ai-video-platform-v1.0.0-rc.1-20260818121333-latest`。
- 发布方式：按本次明确要求直接替换应用版本，不创建应用或数据库备份；PostgreSQL、Redis 和媒体持久化卷原地保留，未执行清库、删卷或数据恢复。
- 服务验收：代理、前端、API、PostgreSQL、Redis 共 5 个容器均为 `healthy`；服务器本机 `/healthz`、`/login`、`/api/v1/versions` 均通过。
- 业务验收：通过公网 `http://112.6.25.76:8080` 使用 `sunqy` 完成真实浏览器登录，并创建小说、章节、Story Bible、剧本、6 个分镜/镜头和 1 条工作流；DeepSeek 文本生产链已实际执行成功。
- 火山配置：从本机配置导入的 API Key 只保存为 `sunqy` 的加密供应商账号，未写入全局环境或 Git。`doubao-seedream-5-0-260128` 连接认证成功，并已绑定为“参考资产生成”生产默认模型。
- 视频配置：相同 Key 对 `doubao-seedance-1-5-pro-251215` 的真实任务提交已被火山接受，模型中心连接认证通过，并已绑定为“镜头视频生成”生产默认模型。Seedance 2.0、1.0-lite 和既有旧 Endpoint 仍返回模型/接入点不存在或无权限，不得作为该账号的可用模型展示。
- 数据核对：验收前业务表为空，因此没有执行破坏性清理；当前保留本轮验收产生的 1 部小说及其章节、设定本、剧本、分镜、镜头和工作流，便于继续补齐媒体阶段。
- 网络结论：公网 `112.6.25.76:8080` 当前可访问；管理地址 `112.6.25.77:17322` 继续用于 SSH 运维，两条网络路径应分别检查。
- 回滚边界：本次没有生成可用于数据恢复的新备份。若要回退应用，只能切换到服务器已有旧发布目录；不得倒退数据库结构或覆盖当前持久化数据。

### Seedance 2.0 开通复核

- 2026-08-18 使用本机火山账号刷新 SSO 后复核：账号已实名，API Key 有效，模型目录中的正式 ID 为 `doubao-seedance-2-0-260128`。
- 本机直调和远端 `sunqy` 模型中心连接认证均未被供应商受理；随后调用模型开通接口，火山返回账户余额及可用代金券低于下单预留金额，模型服务仍未激活。
- 在供应商真实调用成功前，不得把 Seedance 2.0 设为生产默认；远端继续保留已验证的 Seedance 1.5 Pro 作为“镜头视频生成”默认模型。
- 充值或补足可用代金券后，重新执行模型开通、真实任务提交、远端连接认证和默认绑定四项验收；只有四项全部通过后才能切换生产默认。

### MiniMax H3 默认模型配置复核

- 2026-08-18 将本机已保存的 MiniMax API Key 以用户级加密连接方式配置到远端 `sunqy`，未写入全局环境、发布包或 Git；生产启动会持续投影 MiniMax 公共供应商与模型目录。
- 本机与远端 `sunqy` 的“镜头视频生成”默认绑定均已切换为 `MiniMax-H3`，原 Seedance 绑定被同一用户级绑定的新版本替代，没有删除历史模型、连接或业务数据。
- 真实供应商验证结果：H3 请求到达 MiniMax 后返回“Token Plan 或 Credit 暂不支持 MiniMax-H3”；兼容视频模型 `MiniMax-Hailuo-2.3` 请求通过鉴权，但返回 Token Plan 用量已达上限。两次响应均未创建计费任务。
- 因此连接保留为失败/需处理状态，默认绑定可见但不得宣称生产可用。更换支持 H3 的付费类型或补充视频额度后，必须重新完成真实任务提交、连接认证、生成结果轮询与文件下载验收。

### MiniMax H3 公网实模全流程验收（2026-08-18 晚间）

本节是对上方早期额度结论的后续复验，以本节结果为准。

- `sunqy` 用户的 MiniMax H3 连接、模型认证和“镜头视频生成”默认绑定均已通过；用户密钥仍只保存在用户级加密连接中。
- 验收业务链：小说 `8c63341f-fe71-41db-9606-99ca3126b6ba`、章节 `e86a838f-5909-4309-81d7-79eea9218ccb`、Story Bible `e6790fb8-4692-43a0-b26a-c7b83ae9e9f7`、剧本 `8c329f02-3632-4c23-a3d1-2807afda8d91`、分镜 `e735bccf-93cb-470a-8dff-85908b1f4523` 和工作流 `d63480cf-080e-4d74-9720-fc96925ee5aa` 均已落库并保持用户隔离。
- 场景参考图已生成、锁定并通过一致性预检；H3 任务 `432133665689907` 成功接收公网参考图，模型输入快照记录 `image_url_sent=true`，生成结果已回写镜头。
- 原始 H3 视频：`/static/generated/videos/video-cdf97965-aad9829161ee4524be7af82204700a5a.mp4`，公网 HTTP 200，H.264 1344×768、AAC、4.458 秒。
- 修复了分镜提示词重建时把旧提示词再次递归嵌套的问题；重建后任务段、当前镜头段和锁定资产段均只出现一次。
- 修复了 FFmpeg 成片落到临时目录、缺少最终渲染状态以及中文字体缺失三个问题。最终字幕成片任务 `cb3fe1c2-a3df-4e3c-bb98-51379e9d4874` 状态为 `rendered`、`is_publishable=true`，公网文件为 `/static/generated/synthesis/final-2040f5fd2ca54464b95dd21a0fd22272.mp4`。
- 远程 API 容器只读挂载宿主机 `${AI_VIDEO_FONT_ROOT:-/usr/share/fonts/opentype/noto}`，验收时 `fc-match` 命中 `Noto Sans CJK SC`；抽取第 2 秒画面确认中文旁白字幕完整可读。
- 服务器无法回环访问自身公网地址时，对象存储“云端读取”测试可能报假失败；外部网络对同一参考图和视频均返回 HTTP 200。该网络限制不能替代外部可达性检查。
- 本轮三个中间合成记录已设为 `is_active=false`，未删除正式业务数据、最终视频或供应商任务。

### 实体提取提示词补齐（2026-08-18）

- 远程提示词使用地图实测发现：角色提取、场景/道具提取均回退到代码内置提示词，原因是原共享实体模板阶段为 `analysis`，与生产子阶段 `character`、`scene_prop` 不匹配。
- 新增两份系统共享中文模板，分别约束角色证据、别名合并、错误类型过滤，以及场景/道具分类、状态连续性和 JSON 数组输出。
- 补丁通过幂等恢复生成已发布模板，不修改 `sunqy` 或其他用户的自定义模板、模型绑定与供应商密钥。
- 发布验收以提示词使用地图 `internal_fallback=0` 为准；对白配音缺少默认语音模型仍作为独立配置问题处理。
