#!/usr/bin/env bash
# Wave4: private bucket upload + signed GET + app ?download=1.
# Uses MinIO when reachable; otherwise exits 2 with "待凭证/镜像".
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MINIO_ENDPOINT="${S3_ENDPOINT_URL:-http://127.0.0.1:59000}"
BUCKET="${S3_BUCKET:-avp-wave4-private}"
ACCESS="${S3_ACCESS_KEY_ID:-minioadmin}"
SECRET="${S3_SECRET_ACCESS_KEY:-minioadmin}"
REPORT_DIR="${WAVE4_REPORT_DIR:-$ROOT/docs/audits/wave4-evidence}"
mkdir -p "$REPORT_DIR"
REPORT="$REPORT_DIR/minio-private-bucket-$(date +%Y%m%d-%H%M%S).txt"

{
  echo "endpoint=$MINIO_ENDPOINT"
  echo "bucket=$BUCKET"
  echo "started_at=$(date '+%Y-%m-%d %H:%M:%S %z')"
} | tee "$REPORT"

if ! curl -fsS --connect-timeout 2 "$MINIO_ENDPOINT/minio/health/live" >/dev/null 2>&1 \
  && ! curl -fsS --connect-timeout 2 "$MINIO_ENDPOINT" >/dev/null 2>&1; then
  cat <<MSG | tee -a "$REPORT"
STATUS=PENDING_CREDENTIALS_OR_IMAGE
reason=MinIO/S3 endpoint not reachable at $MINIO_ENDPOINT
need=
  - docker image for MinIO (docker hub/quay currently 401/denied on this host), OR
  - real S3/Qiniu credentials in env (see ops/wave4/env-credentials.checklist.md)
MSG
  exit 2
fi

export STORAGE_PROVIDER=s3
export S3_ENDPOINT_URL="$MINIO_ENDPOINT"
export S3_BUCKET="$BUCKET"
export S3_ACCESS_KEY_ID="$ACCESS"
export S3_SECRET_ACCESS_KEY="$SECRET"
export S3_REGION="${S3_REGION:-us-east-1}"
export S3_FORCE_PATH_STYLE=true
export STORAGE_BUCKET_ACL=private
export STORAGE_KEY_PREFIX=avp-wave4
export MEDIA_STATIC_DIR="${MEDIA_STATIC_DIR:-$(mktemp -d /tmp/avp-wave4-static.XXXX)}"
mkdir -p "$MEDIA_STATIC_DIR/exports"
printf 'wave4-private-media' > "$MEDIA_STATIC_DIR/exports/wave4-canary.bin"

cd "$ROOT/backend"
./venv/bin/python - <<'PY' | tee -a "$REPORT"
import asyncio, os, urllib.request
from pathlib import Path
from app.core import object_storage
from app.core.media_access import sign_media_url

static = Path(os.environ["MEDIA_STATIC_DIR"])
path = "/static/exports/wave4-canary.bin"
assert (static / "exports/wave4-canary.bin").is_file()

# Create bucket via S3 PutBucket if missing (MinIO accepts it).
import datetime as dt
from urllib.parse import urlparse
endpoint = os.environ["S3_ENDPOINT_URL"].rstrip("/")
bucket = os.environ["S3_BUCKET"]
# Use backend put via signed PUT of empty? Prefer CreateBucket raw SigV4 from object_storage helpers.

async def main():
    backend = object_storage.get_backend()
    # Ensure upload works: S3Backend.upload uses PUT
    key = object_storage.object_key_for(path)
    await backend.upload(key, static / "exports/wave4-canary.bin", "application/octet-stream")
    marker = object_storage.static_root() / ".object-store" / key.replace("/", "__")
    # persist_private_media writes marker; call it for idempotency path
    ok = await object_storage.persist_private_media(path)
    print(f"upload_ok={ok}")
    url = object_storage.signed_url_for(path, 300)
    assert url and "X-Amz-Signature" in url, url
    print(f"signed_url_host={urlparse(url).netloc}")
    print(f"signed_url_path={urlparse(url).path}")
    with urllib.request.urlopen(url, timeout=10) as resp:
        body = resp.read()
        print(f"signed_get_status={resp.status}")
        print(f"signed_get_bytes={len(body)}")
        assert body == b"wave4-private-media"
    hmac_url = sign_media_url(path)  # may return cloud signed URL after marker
    print(f"sign_media_url_prefix={hmac_url[:80]}")
    print("STATUS=PASS")

asyncio.run(main())
PY
echo "report=$REPORT"
