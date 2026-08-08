"""Application rules for safely retiring user-owned provider connections."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.model_config.connection_management_repository import remove_connection_if_unused
from app.features.model_config.management import ManagementOperationError


async def remove_connection(
    db: AsyncSession, *, user_id: str, connection_id: str,
    expected_revision: int, reason: str,
) -> dict:
    async with db.begin():
        outcome = await remove_connection_if_unused(
            db, connection_id=connection_id, user_id=user_id,
            expected_revision=expected_revision, reason=reason,
        )
        if outcome.state == "not_found":
            raise ManagementOperationError(
                "resource_not_found", "供应商账号不存在或已移除。", "refresh", 404,
            )
        if outcome.state == "in_use":
            raise ManagementOperationError(
                "resource_in_use",
                f"该账号正被 {outcome.active_bindings} 个默认模型使用，请先到“默认模型”更换相关模型。",
                "replace_active_bindings",
                409,
            )
        if outcome.state != "removed":
            raise ManagementOperationError(
                "revision_conflict", "账号配置已更新，请刷新后重试。", "refresh_and_retry", 409,
            )
    return {
        "id": connection_id,
        "status": "disabled",
        "revision": outcome.revision,
        "credentials_removed": True,
    }
