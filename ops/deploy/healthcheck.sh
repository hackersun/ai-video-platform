#!/usr/bin/env bash
set -euo pipefail

deploy_root="${AI_VIDEO_DEPLOY_ROOT:-/srv/ai-video-platform}"
env_file="${AI_VIDEO_ENV_FILE:-$deploy_root/shared/production.env}"
if [[ ! -f "$env_file" ]]; then
  echo "缺少生产环境文件：$env_file" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$env_file"
set +a
port="${APP_HTTP_PORT:-8080}"
base_url="${AI_VIDEO_BASE_URL:-http://127.0.0.1:$port}"

for attempt in $(seq 1 30); do
  if curl --fail --silent "$base_url/healthz" >/dev/null \
    && curl --fail --silent "$base_url/api/v1/versions" >/dev/null \
    && curl --fail --silent "$base_url/login" >/dev/null; then
    echo "健康检查通过：$base_url"
    exit 0
  fi
  echo "等待服务就绪（$attempt/30）..."
  sleep 2
done

echo "健康检查失败：$base_url 在 60 秒内未就绪。" >&2
exit 1
