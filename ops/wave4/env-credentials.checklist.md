# Wave4 云凭证清单（待提供 · 不写入聊天）

本清单只列 **环境变量名**。请通过保密通道注入，禁止贴到聊天/提交到 git。

## A. 真实模型小额验收（约 ¥5 / 1 章）

| 变量 | 用途 | 状态 |
|---|---|---|
| `VOLC_API_KEY` 或 `VOLCENGINE_API_KEY` | 火山文本/图像/视频（按现有配置页绑定） | **待用户通过保密表单提供** |
| TTS 侧 `app_id`（若语音配置需要） | 豆包语音 OpenSpeech | 待配置页填写；缺时界面高亮 |
| 预算闸 | 每次 ≤ ¥50、账号 ≤ ¥200；本轮 canary 建议硬顶 **¥5** | 代码已有闸；canary 另限 |

**禁止**：在聊天索要明文 Key；禁止无预算跑全量多章。

## B. 对象存储私有桶（生产）

任选其一：

### B1. S3 兼容（AWS / MinIO / R2 / COS / OSS S3 API）

| 变量 | 示例含义 |
|---|---|
| `STORAGE_PROVIDER=s3` | |
| `S3_ENDPOINT_URL` | 如 `https://s3.amazonaws.com` 或 MinIO `http://minio:9000` |
| `S3_BUCKET` | 私有桶名 |
| `S3_ACCESS_KEY_ID` | |
| `S3_SECRET_ACCESS_KEY` | |
| `S3_REGION` | 默认 `us-east-1` |
| `S3_FORCE_PATH_STYLE=true` | MinIO / 部分国产云需要 |
| `STORAGE_BUCKET_ACL=private` | 必须 private |
| `STORAGE_KEY_PREFIX` | 可选前缀 |
| `STORAGE_SIGNED_URL_TTL_SECONDS=900` | |

### B2. 七牛 Kodo

| 变量 | 示例含义 |
|---|---|
| `STORAGE_PROVIDER=qiniu` | |
| `QINIU_BUCKET` | |
| `QINIU_DOMAIN` | 私有域名 |
| `QINIU_ACCESS_KEY` | |
| `QINIU_SECRET_KEY` | |
| `QINIU_UPLOAD_URL` | 可选 |

## C. 本机 Wave4 契约（无需云凭证）

```bash
docker compose -f ops/wave4/docker-compose.contracts.yml up -d postgres redis
# MinIO 镜像若可拉取：
docker compose -f ops/wave4/docker-compose.contracts.yml --profile minio up -d
export REDIS_URL=redis://127.0.0.1:56379/0
export AVP_TEST_DATABASE_URL=postgresql+asyncpg://avp:avp_wave4_local@127.0.0.1:55432/ai_video_platform
```

当前主机若 `minio/minio` / `quay.io/minio/minio` 拉取 401/denied，对象存储实桶验收停在 **待镜像或待云凭证**。
