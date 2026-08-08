from __future__ import annotations

import asyncio

import pytest

from app.core.runtime_environment import (
    AppEnvironment,
    effective_environment,
    validate_runtime_environment,
)


def test_production_rejects_development_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEV_MODE", "true")

    with pytest.raises(RuntimeError, match="生产环境不能启用开发模式"):
        validate_runtime_environment()


@pytest.mark.parametrize(
    ("missing_name", "expected_message"),
    [
        ("JWT_SECRET_KEY", "JWT 签名密钥"),
        ("DATABASE_URL", "数据库连接"),
        ("REDIS_URL", "Redis 连接"),
        ("FERNET_KEY", "凭据加密密钥"),
        ("OBJECT_STORAGE_PROVIDER", "对象存储提供商"),
        ("AUTH_EMAIL_PROVIDER", "认证邮件提供商"),
        ("SMTP_HOST", "SMTP 服务器"),
        ("SMTP_USERNAME", "SMTP 用户名"),
        ("SMTP_PASSWORD", "SMTP 密码"),
        ("AUTH_EMAIL_FROM", "认证邮件发件人"),
        ("PUBLIC_APP_URL", "前端公开地址"),
        ("CUSTOMER_BILLING_MODE", "客户计费模式"),
    ],
)
def test_production_rejects_each_missing_security_setting(
    monkeypatch: pytest.MonkeyPatch,
    missing_name: str,
    expected_message: str,
) -> None:
    configured = {
        "APP_ENV": "production",
        "DEV_MODE": "false",
        "JWT_SECRET_KEY": "production-jwt-key-that-is-longer-than-32-bytes",
        "DATABASE_URL": "postgresql+asyncpg://app:secret@postgres/app",
        "REDIS_URL": "redis://:secret@redis:6379/0",
        "FERNET_KEY": "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
        "OBJECT_STORAGE_PROVIDER": "qiniu",
        "AUTH_EMAIL_PROVIDER": "smtp",
        "SMTP_HOST": "smtp.example.test",
        "SMTP_USERNAME": "mailer",
        "SMTP_PASSWORD": "secret",
        "AUTH_EMAIL_FROM": "no-reply@example.test",
        "PUBLIC_APP_URL": "https://app.example.test",
        "CUSTOMER_BILLING_MODE": "enforced",
    }
    for name, value in configured.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv(missing_name, raising=False)

    with pytest.raises(RuntimeError, match=expected_message):
        validate_runtime_environment()


def test_local_environment_keeps_explicit_development_compatibility(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("DEV_MODE", "true")

    assert effective_environment() is AppEnvironment.LOCAL
    validate_runtime_environment()


def test_production_rejects_disabled_customer_billing(monkeypatch: pytest.MonkeyPatch) -> None:
    configured = {
        "APP_ENV": "production", "DEV_MODE": "false",
        "JWT_SECRET_KEY": "production-jwt-key-that-is-longer-than-32-bytes",
        "DATABASE_URL": "postgresql+asyncpg://app:secret@postgres/app",
        "REDIS_URL": "redis://:secret@redis:6379/0",
        "FERNET_KEY": "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
        "OBJECT_STORAGE_PROVIDER": "qiniu", "AUTH_EMAIL_PROVIDER": "smtp",
        "SMTP_HOST": "smtp.example.test", "SMTP_USERNAME": "mailer",
        "SMTP_PASSWORD": "secret", "AUTH_EMAIL_FROM": "no-reply@example.test",
        "PUBLIC_APP_URL": "https://app.example.test", "CUSTOMER_BILLING_MODE": "off",
    }
    for name, value in configured.items():
        monkeypatch.setenv(name, value)
    with pytest.raises(RuntimeError, match="客户计费模式必须设置为 enforced"):
        validate_runtime_environment()


def test_auth_notification_worker_rejects_invalid_fernet_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured = {
        "APP_ENV": "production",
        "DEV_MODE": "false",
        "JWT_SECRET_KEY": "production-jwt-key-that-is-longer-than-32-bytes",
        "DATABASE_URL": "postgresql+asyncpg://app:secret@postgres/app",
        "REDIS_URL": "redis://:secret@redis:6379/0",
        "FERNET_KEY": "not-a-valid-fernet-key",
        "OBJECT_STORAGE_PROVIDER": "qiniu",
        "AUTH_EMAIL_PROVIDER": "smtp",
        "SMTP_HOST": "smtp.example.test",
        "SMTP_USERNAME": "mailer",
        "SMTP_PASSWORD": "secret",
        "AUTH_EMAIL_FROM": "no-reply@example.test",
        "PUBLIC_APP_URL": "https://app.example.test",
        "CUSTOMER_BILLING_MODE": "enforced",
    }
    for name, value in configured.items():
        monkeypatch.setenv(name, value)

    from scripts.run_auth_notification_worker import run

    with pytest.raises(RuntimeError, match="FERNET_KEY"):
        asyncio.run(run())
