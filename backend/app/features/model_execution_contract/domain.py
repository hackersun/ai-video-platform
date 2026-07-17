"""Provider-neutral, fail-closed model execution facts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelExecutionContract:
    provider_id: str
    api_model_id: str
    capability: str
    contract_version: str
    supported_inputs: tuple[str, ...]
    response_mode: str
    polling_mode: str
    prompt_profile: str
    reference_limits: dict[str, int]
    retry_policy: str
    verification_status: str


def unverified_contract(provider_id: str, api_model_id: str, capability: str) -> ModelExecutionContract:
    return ModelExecutionContract(
        provider_id=provider_id,
        api_model_id=api_model_id,
        capability=capability,
        contract_version="unverified.v1",
        supported_inputs=(),
        response_mode="sync_or_async",
        polling_mode="operation_reconcile",
        prompt_profile=f"generic.{capability}.compatibility",
        reference_limits={"images": 0, "videos": 0, "audios": 0},
        retry_policy="never",
        verification_status="unverified",
    )


__all__ = ["ModelExecutionContract", "unverified_contract"]
