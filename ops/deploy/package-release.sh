#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
version="$(tr -d '[:space:]' < "$repo_root/ops/deploy/VERSION")"
commit="$(git -C "$repo_root" rev-parse --short=12 HEAD)"
output_dir="${1:-$repo_root/dist/releases}"
release_name="ai-video-platform-${version}-${commit}"
archive="$output_dir/$release_name.tar.gz"

[[ -z "$(git -C "$repo_root" status --porcelain)" ]] || {
  echo "工作区不干净，拒绝生成发布包。" >&2
  exit 1
}
mkdir -p "$output_dir"
git -C "$repo_root" archive \
  --format=tar.gz \
  --prefix="$release_name/" \
  -o "$archive" \
  HEAD \
  -- . \
  ':(exclude)backend/static/**' \
  ':(exclude)backend/backend/static/**' \
  ':(exclude)e2e/test-results/**' \
  ':(exclude)test-results/**' \
  ':(exclude)tmp/**'
(cd "$output_dir" && sha256sum "$(basename "$archive")" > "$(basename "$archive").sha256")
echo "$archive"
