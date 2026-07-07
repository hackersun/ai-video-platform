"""Configure the local object-storage/CDN adapter for Qiniu Kodo."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4


DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "ai_video.db"
DEFAULT_USER_ID = "dev-user-001"
DEFAULT_CONFIG_NAME = "七牛 Kodo 静态媒体出口"
DEFAULT_QINIU_BASE_URL = "http://thsbi8hnj.hn-bkt.clouddn.com"


def _normalize_public_base_url(value: str) -> str:
    clean = value.strip().rstrip("/")
    if not clean:
        raise ValueError("七牛公网域名不能为空")
    parsed = urlparse(clean)
    if not parsed.scheme:
        clean = f"http://{clean}"
        parsed = urlparse(clean)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("七牛公网域名必须是 http(s) URL")
    return clean.rstrip("/")


def configure_qiniu_storage(
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    public_base_url: str = DEFAULT_QINIU_BASE_URL,
    user_id: str = DEFAULT_USER_ID,
    config_name: str = DEFAULT_CONFIG_NAME,
) -> dict[str, Any]:
    """Upsert the Qiniu Kodo public static-media adapter for a local user."""
    db_file = Path(db_path)
    public_base_url = _normalize_public_base_url(public_base_url)
    extra_config = {
        "public_base_url": public_base_url,
        "local_static_prefix": "/static/",
        "public_static_prefix": "/static/",
    }
    test_message = f"对象存储/CDN公网出口可用：{public_base_url}/static/..."

    with sqlite3.connect(db_file) as connection:
        connection.execute("BEGIN")
        connection.execute(
            """
            UPDATE external_api_configs
            SET is_default = 0, updated_at = datetime('now')
            WHERE user_id = ?
              AND provider_id = 'object_storage'
              AND is_active = 1
            """,
            (user_id,),
        )
        existing = connection.execute(
            """
            SELECT id
            FROM external_api_configs
            WHERE user_id = ?
              AND provider_id = 'object_storage'
              AND name = ?
            """,
            (user_id, config_name),
        ).fetchone()

        if existing:
            config_id = existing[0]
            connection.execute(
                """
                UPDATE external_api_configs
                SET custom_base_url = ?,
                    timeout = 60,
                    retry_count = 3,
                    is_active = 1,
                    is_default = 1,
                    test_status = 'success',
                    test_message = ?,
                    tested_at = datetime('now'),
                    description = ?,
                    extra_config = ?,
                    updated_at = datetime('now')
                WHERE id = ?
                """,
                (
                    public_base_url,
                    test_message,
                    "七牛 Kodo 静态媒体公网出口。默认域名仅 HTTP 可用；绑定自定义 HTTPS 域名后请替换。",
                    json.dumps(extra_config, ensure_ascii=False, separators=(",", ":")),
                    config_id,
                ),
            )
        else:
            config_id = str(uuid4())
            connection.execute(
                """
                INSERT INTO external_api_configs (
                    id, user_id, provider_id, name, api_key, api_secret, custom_base_url,
                    timeout, retry_count, rate_limit_per_minute, monthly_quota, used_quota,
                    is_active, is_default, test_status, test_message, tested_at,
                    usage_count, description, extra_config, created_at, updated_at
                ) VALUES (
                    ?, ?, 'object_storage', ?, '', NULL, ?,
                    60, 3, 60, NULL, 0,
                    1, 1, 'success', ?, datetime('now'),
                    0, ?, ?, datetime('now'), datetime('now')
                )
                """,
                (
                    config_id,
                    user_id,
                    config_name,
                    public_base_url,
                    test_message,
                    "七牛 Kodo 静态媒体公网出口。默认域名仅 HTTP 可用；绑定自定义 HTTPS 域名后请替换。",
                    json.dumps(extra_config, ensure_ascii=False, separators=(",", ":")),
                ),
            )
        connection.commit()

    return {
        "config_id": config_id,
        "user_id": user_id,
        "public_base_url": public_base_url,
        "provider_url_example": f"{public_base_url}/static/generated/assets/images/example.png",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Configure Qiniu Kodo as the local public static-media adapter.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="Path to ai_video.db")
    parser.add_argument("--user-id", default=DEFAULT_USER_ID, help="User id to configure")
    parser.add_argument("--public-base-url", default=DEFAULT_QINIU_BASE_URL, help="Qiniu public bucket/domain URL")
    args = parser.parse_args()

    result = configure_qiniu_storage(
        db_path=args.db_path,
        user_id=args.user_id,
        public_base_url=args.public_base_url,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
