from __future__ import annotations

import sqlite3

from scripts.configure_qiniu_storage import configure_qiniu_storage


def _create_external_api_tables(db_path):
    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE external_api_providers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                name_cn TEXT,
                api_type TEXT NOT NULL,
                base_url TEXT NOT NULL,
                api_version TEXT,
                auth_type TEXT,
                auth_header TEXT,
                is_active INTEGER,
                is_builtin INTEGER,
                description TEXT,
                doc_url TEXT,
                icon_url TEXT,
                supported_models TEXT,
                created_at TEXT,
                updated_at TEXT
            );
            CREATE TABLE external_api_configs (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                provider_id TEXT NOT NULL,
                name TEXT NOT NULL,
                api_key TEXT NOT NULL,
                api_secret TEXT,
                custom_base_url TEXT,
                timeout INTEGER,
                retry_count INTEGER,
                rate_limit_per_minute INTEGER,
                monthly_quota INTEGER,
                used_quota INTEGER,
                is_active INTEGER,
                is_default INTEGER,
                test_status TEXT,
                test_message TEXT,
                tested_at TEXT,
                usage_count INTEGER,
                last_used_at TEXT,
                description TEXT,
                extra_config TEXT,
                created_at TEXT,
                updated_at TEXT
            );
            INSERT INTO external_api_providers (
                id, name, name_cn, api_type, base_url, auth_type, is_active, is_builtin, supported_models
            ) VALUES (
                'object_storage', 'object_storage', '对象存储 / CDN', 'storage', '', 'none', 1, 1, '[]'
            );
            INSERT INTO external_api_configs (
                id, user_id, provider_id, name, api_key, custom_base_url, timeout, retry_count,
                rate_limit_per_minute, used_quota, is_active, is_default, test_status, usage_count,
                extra_config
            ) VALUES (
                'old-config', 'dev-user-001', 'object_storage', '旧 CDN', '', 'https://old.example.com',
                60, 3, 60, 0, 1, 1, 'success', 0,
                '{"public_base_url":"https://old.example.com","local_static_prefix":"/static/","public_static_prefix":"/static/"}'
            );
            """
        )


def test_configure_qiniu_storage_sets_default_and_preserves_old_configs(tmp_path):
    db_path = tmp_path / "ai_video.db"
    _create_external_api_tables(db_path)

    result = configure_qiniu_storage(
        db_path=db_path,
        public_base_url="thsbi8hnj.hn-bkt.clouddn.com",
        user_id="dev-user-001",
    )

    assert result["public_base_url"] == "http://thsbi8hnj.hn-bkt.clouddn.com"

    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT name, custom_base_url, is_default, test_status, extra_config
            FROM external_api_configs
            WHERE user_id = 'dev-user-001' AND provider_id = 'object_storage'
            ORDER BY name
            """
        ).fetchall()

    rows_by_name = {row[0]: row for row in rows}
    assert len(rows_by_name) == 2
    assert ("旧 CDN", "https://old.example.com", 0, "success") == rows_by_name["旧 CDN"][:4]
    qiniu_row = rows_by_name["七牛 Kodo 静态媒体出口"]
    assert qiniu_row[1] == "http://thsbi8hnj.hn-bkt.clouddn.com"
    assert qiniu_row[2] == 1
    assert qiniu_row[3] == "success"
    assert '"public_base_url":"http://thsbi8hnj.hn-bkt.clouddn.com"' in qiniu_row[4]
    assert '"local_static_prefix":"/static/"' in qiniu_row[4]
    assert '"public_static_prefix":"/static/"' in qiniu_row[4]


def test_configure_qiniu_storage_is_idempotent(tmp_path):
    db_path = tmp_path / "ai_video.db"
    _create_external_api_tables(db_path)

    configure_qiniu_storage(db_path=db_path, public_base_url="http://thsbi8hnj.hn-bkt.clouddn.com")
    configure_qiniu_storage(db_path=db_path, public_base_url="http://thsbi8hnj.hn-bkt.clouddn.com")

    with sqlite3.connect(db_path) as connection:
        count = connection.execute(
            """
            SELECT COUNT(*)
            FROM external_api_configs
            WHERE user_id = 'dev-user-001'
              AND provider_id = 'object_storage'
              AND name = '七牛 Kodo 静态媒体出口'
            """
        ).fetchone()[0]

    assert count == 1
