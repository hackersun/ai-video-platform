#!/usr/bin/env bash
set -euo pipefail

archive="${1:?用法：deploy.sh <release.tar.gz> [sha256-file]}"
checksum_file="${2:-$archive.sha256}"
deploy_root="${AI_VIDEO_DEPLOY_ROOT:-/srv/ai-video-platform}"
env_file="${AI_VIDEO_ENV_FILE:-$deploy_root/shared/production.env}"
releases_dir="$deploy_root/releases"
backups_dir="$deploy_root/backups"

backup_database() {
  local active="$1" backup="$2"
  [[ -n "$active" && -f "$active/compose.production.yml" ]] || return 0
  (cd "$active" && docker compose --env-file "$env_file" -f compose.production.yml \
    exec -T postgres pg_dump -U ai_video -d ai_video_platform -Fc) > "$backup"
}

prepare_storage_permissions() {
  chown 70:70 "$deploy_root/data/postgres"
  chown 999:999 "$deploy_root/data/redis"
  chown -R 10001:10001 "$deploy_root/data/media" "$deploy_root/runtime/api-tmp"
  chown -R 1000:1000 "$deploy_root/data/caddy"
}

command -v docker >/dev/null || { echo "服务器尚未安装 Docker。" >&2; exit 1; }
docker compose version >/dev/null
command -v sha256sum >/dev/null || { echo "缺少 sha256sum。" >&2; exit 1; }
[[ -f "$archive" && -f "$checksum_file" ]] || { echo "缺少发布包或校验文件。" >&2; exit 1; }
[[ -f "$env_file" ]] || { echo "缺少生产环境文件：$env_file" >&2; exit 1; }
grep -q 'CHANGE_ME_' "$env_file" && { echo "生产环境文件仍包含 CHANGE_ME，占位符必须全部替换。" >&2; exit 1; }

mkdir -p "$releases_dir" "$backups_dir/database/pre-deploy" "$deploy_root/shared" \
  "$deploy_root/data/postgres" "$deploy_root/data/redis" "$deploy_root/data/media" \
  "$deploy_root/data/caddy/data" "$deploy_root/data/caddy/config" \
  "$deploy_root/runtime/api-tmp" "$deploy_root/logs/deployment"
prepare_storage_permissions
(cd "$(dirname "$archive")" && sha256sum -c "$(basename "$checksum_file")")
release_id="$(basename "$archive" .tar.gz)"
release_dir="$releases_dir/$release_id"
[[ ! -e "$release_dir" ]] || { echo "发布目录已存在：$release_dir" >&2; exit 1; }
mkdir "$release_dir"
tar -xzf "$archive" -C "$release_dir" --strip-components=1

active=""
if [[ -L "$deploy_root/current" ]]; then
  active="$(readlink -f "$deploy_root/current")"
  ln -sfn "$active" "$deploy_root/previous"
fi
backup="$backups_dir/database/pre-deploy/${release_id}-predeploy.dump"
backup_database "$active" "$backup"

set -a
# shellcheck disable=SC1090
source "$env_file"
set +a
(cd "$release_dir" && docker compose --env-file "$env_file" -f compose.production.yml up -d --build --remove-orphans)
AI_VIDEO_DEPLOY_ROOT="$deploy_root" AI_VIDEO_ENV_FILE="$env_file" "$release_dir/ops/deploy/healthcheck.sh"
ln -sfn "$release_dir" "$deploy_root/current"
echo "发布成功：$release_id"
[[ -s "$backup" ]] && echo "数据库备份：$backup"
