"""Read and acknowledge series-run recovery without provider submission."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.live_canary_provider_operation import LiveCanaryProviderOperation
from app.models.series_production_run import SeriesProductionRun

from .domain import recovery_for_operation


class RecoveryNotFound(Exception):
    pass


class RecoveryConflict(Exception):
    pass


async def _owned_run(db: AsyncSession, user_id: str, run_id: str) -> SeriesProductionRun:
    run = await db.scalar(select(SeriesProductionRun).where(
        SeriesProductionRun.id == run_id, SeriesProductionRun.user_id == user_id,
    ))
    if run is None:
        raise RecoveryNotFound("series run not found")
    return run


async def get_run_recovery(db: AsyncSession, user_id: str, run_id: str) -> dict:
    run = await _owned_run(db, user_id, run_id)
    operations = list((await db.scalars(select(LiveCanaryProviderOperation).where(
        LiveCanaryProviderOperation.run_id == run.id,
        LiveCanaryProviderOperation.user_id == user_id,
    ).order_by(LiveCanaryProviderOperation.created_at.desc()))).all())
    descriptors = [descriptor for item in operations if (descriptor := recovery_for_operation(item)).actions]
    reference = (run.run_metadata or {}).get("reference_preparation") or {}
    preserved = ([{
        "kind": "reference_image", "asset_id": reference.get("asset_id"),
        "message": "参考图已锁定，不会重新生成",
    }] if reference.get("asset_id") else [])
    return {
        "run_id": run.id,
        "run_version": run.version,
        "blocked": any(item.operation_status in {"accepted", "reserved", "unknown_manual_reconcile"}
                       for item in descriptors),
        "operations": [item.as_dict() for item in descriptors],
        "preserved_artifacts": preserved,
    }


async def acknowledge_recovery_action(
    db: AsyncSession, user_id: str, run_id: str, *, action_code: str,
    operation_id: str, expected_run_version: int,
) -> dict:
    run = await _owned_run(db, user_id, run_id)
    if run.version != expected_run_version:
        raise RecoveryConflict("运行状态已更新，请刷新后再操作")
    operation = await db.scalar(select(LiveCanaryProviderOperation).where(
        LiveCanaryProviderOperation.id == operation_id,
        LiveCanaryProviderOperation.run_id == run.id,
        LiveCanaryProviderOperation.user_id == user_id,
    ))
    if operation is None:
        raise RecoveryNotFound("provider operation not found")
    descriptor = recovery_for_operation(operation)
    if action_code not in {item.code for item in descriptor.actions}:
        raise RecoveryConflict("当前供应商状态不允许执行该恢复操作")
    reference_preparation = None
    if action_code == "recover_reference_artifact":
        from app.services.series_reference_artifact_recovery import PersistedReferenceArtifactAdapter
        from app.services.series_run_reference_preparation import (
            ReferencePreparationBlocked,
            prepare_series_reference,
        )

        try:
            reference_preparation = await prepare_series_reference(
                db, run, adapter=PersistedReferenceArtifactAdapter(),
                recovery_operation_id=operation.id,
            )
        except ReferencePreparationBlocked as error:
            raise RecoveryConflict(str(error)) from error
    return {
        "acknowledged": True, "action_code": action_code, "operation_id": operation.id,
        "retry_scope": descriptor.retry_scope, "requires_provider_submission": False,
        "next_action": (
            "参考图已恢复，可继续生成镜头首帧"
            if reference_preparation else "修改并重新验证配置后，使用“生成已选镜头”继续失败阶段"
        ),
        "reference_preparation": reference_preparation,
    }
