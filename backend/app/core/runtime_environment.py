"""Runtime environment boundary for development and commercial deployments."""

from __future__ import annotations

import os
from enum import Enum


class AppEnvironment(str, Enum):
    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


_PRODUCTION_REQUIRED_SETTINGS = {
    "JWT_SECRET_KEY": "JWT 签名密钥",
    "DATABASE_URL": "数据库连接",
    "REDIS_URL": "Redis 连接",
    "FERNET_KEY": "凭据加密密钥",
    "OBJECT_STORAGE_PROVIDER": "对象存储提供商",
    "AUTH_EMAIL_PROVIDER": "认证邮件提供商",
    "SMTP_HOST": "SMTP 服务器",
    "SMTP_USERNAME": "SMTP 用户名",
    "SMTP_PASSWORD": "SMTP 密码",
    "AUTH_EMAIL_FROM": "认证邮件发件人",
    "PUBLIC_APP_URL": "前端公开地址",
    "CUSTOMER_BILLING_MODE": "客户计费模式",
}


def effective_environment() -> AppEnvironment:
    """Return the explicit environment, retaining local legacy compatibility."""
    configured = os.getenv("APP_ENV", "").strip().lower()
    if not configured:
        return AppEnvironment.LOCAL
    try:
        return AppEnvironment(configured)
    except ValueError as error:
        allowed = "、".join(item.value for item in AppEnvironment)
        raise RuntimeError(f"APP_ENV 配置无效，只能使用：{allowed}") from error


def development_mode_enabled() -> bool:
    return os.getenv("DEV_MODE", "true").strip().lower() in {"true", "1", "yes"}


def allows_development_identity() -> bool:
    return effective_environment() in {AppEnvironment.LOCAL, AppEnvironment.TEST} and development_mode_enabled()


def validate_runtime_environment() -> None:
    """Fail closed before a staging or production process accepts traffic."""
    environment = effective_environment()
    if environment in {AppEnvironment.STAGING, AppEnvironment.PRODUCTION} and development_mode_enabled():
        label = "生产环境" if environment is AppEnvironment.PRODUCTION else "预发布环境"
        raise RuntimeError(f"{label}不能启用开发模式，请设置 DEV_MODE=false")
    if environment not in {AppEnvironment.STAGING, AppEnvironment.PRODUCTION}:
        return

    missing = [
        description
        for name, description in _PRODUCTION_REQUIRED_SETTINGS.items()
        if not os.getenv(name, "").strip()
    ]
    if missing:
        raise RuntimeError("生产配置不完整，缺少：" + "、".join(missing))

    jwt_secret = os.environ["JWT_SECRET_KEY"]
    if len(jwt_secret.encode("utf-8")) < 32:
        raise RuntimeError("JWT 签名密钥长度不足，至少需要 32 字节")
    if os.environ["AUTH_EMAIL_PROVIDER"].strip().lower() != "smtp":
        raise RuntimeError("认证邮件提供商当前必须配置为 smtp")
    if os.environ["CUSTOMER_BILLING_MODE"].strip().lower() != "enforced":
        raise RuntimeError("正式环境的客户计费模式必须设置为 enforced")
