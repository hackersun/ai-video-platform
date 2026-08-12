"""Ownership rules for the shared provider and model catalog."""

from __future__ import annotations

import os


class CatalogPermissionError(PermissionError):
    """Raised when a user tries to mutate the shared catalog."""


def catalog_admin_user_ids() -> frozenset[str]:
    configured = {
        item.strip()
        for item in os.getenv("MODEL_CATALOG_ADMIN_USER_IDS", "").split(",")
        if item.strip()
    }
    if os.getenv("DEV_MODE", "true").lower() in {"true", "1", "yes"}:
        configured.add(os.getenv("DEV_USER_ID", "dev-user-001"))
    return frozenset(configured)


def is_catalog_admin(user_id: str) -> bool:
    return user_id in catalog_admin_user_ids()


def require_catalog_admin(user_id: str) -> None:
    if is_catalog_admin(user_id):
        return
    raise CatalogPermissionError("只有模型目录管理员可以维护共享供应商和模型。")
