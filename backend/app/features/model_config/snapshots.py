"""Immutable, secret-free evidence for a model generation submission."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any, Mapping
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.model_config.domain import ModelCapability, ResolvedModelBinding
from app.models.model_center import ModelExecutionSnapshot


_FORBIDDEN_KEYS = frozenset({"api_key", "api_secret", "authorization", "prompt", "text", "token", "secret"})
_CREDENTIAL_VALUE_PREFIXES = ("bearer ", "basic ", "sk-", "ak", "gaaaaa")
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")
_SAFE_RESOLUTION = re.compile(r"^(?:[1-9][0-9]{2,3}p|[1248]K)$")
_SAFE_IMAGE_SIZE = re.compile(r"^(?:[1-9][0-9]{2,4}[xX][1-9][0-9]{2,4}|[1-8][kK](?:_[wh])?)$")
_SAFE_ASPECT_RATIO = re.compile(r"^[1-9][0-9]?:[1-9][0-9]?$")
SNAPSHOT_PARAM_ALLOWLIST = frozenset({
    "duration", "resolution", "aspect_ratio", "native_audio", "reference_image_count",
    "reference_video_count", "reference_audio_count", "voice_id", "output_contract", "seed",
    "speed", "image_count", "image_size", "parameter_normalization",
    "provider_prompt_sanitized", "reference_image_strategy",
})


class UnsafeSnapshotError(ValueError):
    """A caller attempted to retain credentials or content in trace evidence."""


@dataclass(frozen=True)
class ExecutionSnapshotCommand:
    user_id: str
    run_id: str | None
    job_id: str | None
    task: str
    capability: ModelCapability
    binding: ResolvedModelBinding
    recipe_version_id: str | None = None
    prompt_profile_version_id: str | None = None
    sanitized_params: Mapping[str, Any] | None = None


def _forbidden_keys(value: Any) -> set[str]:
    if not isinstance(value, Mapping):
        if isinstance(value, (list, tuple)):
            return set().union(*(_forbidden_keys(item) for item in value)) if value else set()
        return set()
    found = {
        str(key) for key in value
        if _is_forbidden_key(str(key))
    }
    return found | set().union(*(_forbidden_keys(item) for item in value.values())) if value else found


def _is_forbidden_key(value: str) -> bool:
    normalized = value.strip().lower().replace("-", "_")
    return (
        normalized in _FORBIDDEN_KEYS
        or normalized.startswith(("api_key_", "api_secret_", "authorization_", "token_", "secret_"))
        or normalized.endswith(("_api_key", "_api_secret", "_authorization", "_token", "_secret"))
    )


def _is_int(value: Any, *, minimum: int = 0, maximum: int = 2**32 - 1) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and minimum <= value <= maximum


def _safe_identifier(value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(_SAFE_IDENTIFIER.fullmatch(value))
        and not value.lower().startswith(_CREDENTIAL_VALUE_PREFIXES)
    )


def _valid_param(key: str, value: Any) -> bool:
    if key == "duration":
        return _is_int(value, minimum=1, maximum=600)
    if key == "resolution":
        return isinstance(value, str) and bool(_SAFE_RESOLUTION.fullmatch(value))
    if key == "aspect_ratio":
        return isinstance(value, str) and bool(_SAFE_ASPECT_RATIO.fullmatch(value))
    if key in {"native_audio", "provider_prompt_sanitized"}:
        return isinstance(value, bool)
    if key in {"reference_image_count", "reference_video_count", "reference_audio_count"}:
        return _is_int(value, maximum=100)
    if key == "image_count":
        return _is_int(value, minimum=1, maximum=16)
    if key == "image_size":
        return isinstance(value, str) and bool(_SAFE_IMAGE_SIZE.fullmatch(value))
    if key == "seed":
        return _is_int(value)
    if key == "speed":
        return isinstance(value, (int, float)) and not isinstance(value, bool) and 0.1 <= value <= 4
    if key in {"voice_id", "output_contract", "reference_image_strategy"}:
        return _safe_identifier(value)
    if key == "parameter_normalization":
        return (
            isinstance(value, Mapping)
            and set(value) <= {"prompt_compacted", "reference_contract_applied"}
            and all(isinstance(item, bool) for item in value.values())
        )
    return False


def sanitize_snapshot_params(params: Mapping[str, Any] | None) -> dict[str, Any]:
    values = dict(params or {})
    forbidden = sorted(_forbidden_keys(values))
    if forbidden:
        raise UnsafeSnapshotError(", ".join(forbidden))
    sanitized = {
        key: values[key]
        for key in sorted(SNAPSHOT_PARAM_ALLOWLIST & values.keys())
        if values[key] is not None
    }
    invalid = sorted(key for key, value in sanitized.items() if not _valid_param(key, value))
    if invalid:
        raise UnsafeSnapshotError("invalid_snapshot_params: " + ", ".join(invalid))
    try:
        json.dumps(sanitized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as error:
        raise UnsafeSnapshotError("snapshot_params_not_json_serializable") from error
    return sanitized


def _binding_id(binding: ResolvedModelBinding) -> str:
    return binding.binding_id or f"legacy:{binding.connection_id or binding.profile.profile_version_id}"


def _snapshot_params(command: ExecutionSnapshotCommand) -> dict[str, Any]:
    params = sanitize_snapshot_params(command.sanitized_params)
    profile = command.binding.profile
    params["resolved_model"] = {
        "api_model_id": profile.api_model_id,
        "contract_version": profile.contract_version,
        "driver_key": profile.driver_key,
        "provider_id": profile.provider_id,
        "source_scope": command.binding.source_scope,
    }
    return params


def _checksum(command: ExecutionSnapshotCommand, params: Mapping[str, Any]) -> str:
    payload = {
        "run_id": command.run_id, "job_id": command.job_id, "task": command.task,
        "capability": command.capability, "profile_version_id": command.binding.profile.profile_version_id,
        "connection_id": command.binding.connection_id, "binding_id": _binding_id(command.binding),
        "binding_version": command.binding.binding_version, "recipe_version_id": command.recipe_version_id,
        "prompt_profile_version_id": command.prompt_profile_version_id,
        "model_contract_version": command.binding.profile.contract_version, "sanitized_params": params,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


async def create_execution_snapshot(
    db: AsyncSession, command: ExecutionSnapshotCommand,
) -> ModelExecutionSnapshot:
    """Add immutable evidence to the current transaction before provider submission."""
    params = _snapshot_params(command)
    snapshot = ModelExecutionSnapshot(
        id=str(uuid4()), user_id=command.user_id, run_id=command.run_id, job_id=command.job_id,
        task=command.task, capability=command.capability,
        profile_version_id=command.binding.profile.profile_version_id,
        connection_id=command.binding.connection_id or "",
        binding_id=_binding_id(command.binding), binding_version=command.binding.binding_version,
        recipe_version_id=command.recipe_version_id,
        prompt_profile_version_id=command.prompt_profile_version_id,
        model_contract_version=command.binding.profile.contract_version,
        sanitized_params=params, checksum=_checksum(command, params),
    )
    db.add(snapshot)
    await db.flush()
    return snapshot


async def load_execution_snapshot(
    db: AsyncSession, snapshot_id: str, *, user_id: str,
) -> ModelExecutionSnapshot | None:
    result = await db.execute(select(ModelExecutionSnapshot).where(
        ModelExecutionSnapshot.id == snapshot_id,
        ModelExecutionSnapshot.user_id == user_id,
    ))
    return result.scalar_one_or_none()


__all__ = [
    "ExecutionSnapshotCommand", "SNAPSHOT_PARAM_ALLOWLIST", "UnsafeSnapshotError",
    "create_execution_snapshot", "load_execution_snapshot", "sanitize_snapshot_params",
]
