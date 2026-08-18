#!/usr/bin/env bash
set -euo pipefail

deploy_root="${AI_VIDEO_DEPLOY_ROOT:-/srv/ai-video-platform}"
env_file="${AI_VIDEO_ENV_FILE:-$deploy_root/shared/production.env}"
[[ -L "$deploy_root/previous" ]] || { echo "没有可回滚的 previous 版本。" >&2; exit 1; }
previous="$(readlink -f "$deploy_root/previous")"
current=""
[[ -L "$deploy_root/current" ]] && current="$(readlink -f "$deploy_root/current")"
[[ -f "$previous/compose.production.yml" ]] || { echo "previous 版本不完整：$previous" >&2; exit 1; }

set -a
# shellcheck disable=SC1090
source "$env_file"
set +a
(cd "$previous" && docker compose --env-file "$env_file" -f compose.production.yml up -d --build --remove-orphans)
AI_VIDEO_DEPLOY_ROOT="$deploy_root" AI_VIDEO_ENV_FILE="$env_file" "$previous/ops/deploy/healthcheck.sh"
ln -sfn "$previous" "$deploy_root/current"
[[ -n "$current" ]] && ln -sfn "$current" "$deploy_root/previous"
echo "已回滚到：$(basename "$previous")"
