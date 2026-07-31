"""Execute free contract checks and explicit provider connection checks."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.model_config.certification_repository import complete_certification_run
from app.features.model_config.domain import ModelProfileContract
from app.features.model_config.management import ManagementOperationError
from app.features.model_drivers.public import (
    DriverContext,
    DriverError,
    build_builtin_driver_registry,
    execute_connection_test,
)
from app.models.model_center import ModelConnection, ModelProfile, ModelProfileVersion, ModelProvider


@dataclass(frozen=True)
class CertificationTarget:
    version: ModelProfileVersion
    profile: ModelProfile
    provider: ModelProvider
    connection: ModelConnection


async def _load_target(
    db: AsyncSession, *, user_id: str, profile_version_id: str, connection_id: str,
) -> CertificationTarget:
    row = (await db.execute(select(
        ModelProfileVersion, ModelProfile, ModelProvider, ModelConnection,
    ).join(
        ModelProfile, ModelProfile.id == ModelProfileVersion.model_id,
    ).join(ModelProvider, ModelProvider.id == ModelProfile.provider_id).join(
        ModelConnection, ModelConnection.provider_id == ModelProvider.id,
    ).where(
        ModelProfileVersion.id == profile_version_id,
        ModelConnection.id == connection_id,
        ModelConnection.user_id == user_id,
    ))).one_or_none()
    if row is None:
        raise ManagementOperationError(
            "resource_not_found", "模型版本或连接不存在。", "refresh", 404,
        )
    return CertificationTarget(*row)


def _profile_contract(target: CertificationTarget) -> ModelProfileContract:
    version = target.version
    return ModelProfileContract(
        profile_version_id=version.id, provider_id=target.provider.id,
        api_model_id=version.api_model_id, driver_key=version.driver_key,
        capabilities=frozenset(version.capabilities or []),
        input_contract=version.input_contract or {}, output_contract=version.output_contract or {},
        parameter_schema=version.parameter_schema or {}, default_params=version.default_params or {},
        limits=version.limits or {}, pricing=version.pricing or {},
        prompt_profile_key=version.prompt_profile_key, contract_version=version.contract_version,
    )


def _context(target: CertificationTarget) -> DriverContext:
    params = dict(target.connection.connection_params or {})
    provider_name = params.get("legacy_provider_id")
    if not provider_name:
        provider_name = target.provider.provider_family
        if provider_name in {"cloud", "legacy"}:
            provider_name = target.provider.code
    params.setdefault("provider_name", str(provider_name).replace("-", "_"))
    endpoint = dict(target.connection.endpoint_overrides or {})
    return DriverContext(
        profile=_profile_contract(target), driver_key=target.version.driver_key,
        connection_id=target.connection.id,
        secrets={
            "api_key": target.connection.get_api_key_decrypted(),
            "api_secret": target.connection.get_api_secret_decrypted(),
        },
        base_url=str(endpoint.get("base_url") or "") or None,
        connection_params=params,
    )


async def execute_certification(
    db: AsyncSession, *, user_id: str, run_id: str,
    profile_version_id: str, connection_id: str, level: str,
):
    target = await _load_target(
        db, user_id=user_id, profile_version_id=profile_version_id,
        connection_id=connection_id,
    )
    registry = build_builtin_driver_registry()
    if level == "contract":
        try:
            driver = registry.require(target.version.driver_key)
        except DriverError as error:
            raise ManagementOperationError(
                "driver_not_installed", f"驱动 {target.version.driver_key} 尚未安装。",
                "install_or_select_driver", 422,
            ) from error
        unsupported = set(target.version.capabilities or []) - set(
            driver.capabilities
        )
        if unsupported:
            raise ManagementOperationError(
                "driver_capability_mismatch", "模型能力与驱动不匹配。",
                "select_compatible_driver", 422,
            )
        evidence = {
            "execution_mode": "local_contract_validation", "valid": True,
            "driver_key": target.version.driver_key,
            "contract_version": target.version.contract_version,
        }
        return await complete_certification_run(
            db, user_id=user_id, run_id=run_id, status="success", evidence=evidence,
        )
    if level != "connection":
        return None
    return await _execute_connection(db, user_id=user_id, run_id=run_id, target=target, registry=registry)


async def _execute_connection(db, *, user_id: str, run_id: str, target, registry):
    try:
        result = await execute_connection_test(registry, target.version.driver_key, _context(target))
        passed = result.status in {"success", "passed", "verified", "connection_verified"}
        evidence = {
            "execution_mode": "driver_connection_test", "driver_key": target.version.driver_key,
            "plain_reason": result.message, "response_evidence": dict(result.sanitized_evidence),
        }
    except (DriverError, ValueError) as error:
        passed = False
        evidence = {
            "execution_mode": "driver_connection_test", "driver_key": target.version.driver_key,
            "error_code": type(error).__name__,
            "plain_reason": "连接测试失败，请检查凭证、地址和模型配置。",
            "retry_eligible": True,
        }
    return await complete_certification_run(
        db, user_id=user_id, run_id=run_id, status="success" if passed else "failed",
        evidence=evidence, connection_status="connection_verified" if passed else "failed",
    )


__all__ = ["execute_certification"]
