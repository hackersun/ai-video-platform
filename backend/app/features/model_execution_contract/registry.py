"""Explicit contracts for model versions exercised by this repository."""

from __future__ import annotations

from app.features.model_execution_contract.domain import ModelExecutionContract, unverified_contract


def _contract(
    provider_id: str,
    api_model_id: str,
    capability: str,
    contract_version: str,
    *,
    inputs: tuple[str, ...],
    response_mode: str,
    polling_mode: str,
    prompt_profile: str,
    references: tuple[int, int, int] = (0, 0, 0),
    retry_policy: str = "confirmed_pre_acceptance_only",
) -> ModelExecutionContract:
    return ModelExecutionContract(
        provider_id=provider_id,
        api_model_id=api_model_id,
        capability=capability,
        contract_version=contract_version,
        supported_inputs=inputs,
        response_mode=response_mode,
        polling_mode=polling_mode,
        prompt_profile=prompt_profile,
        reference_limits=dict(zip(("images", "videos", "audios"), references)),
        retry_policy=retry_policy,
        verification_status="verified",
    )


_CONTRACTS = [
    _contract("minimax", "MiniMax-M3", "text", "minimax.text.m3.v1", inputs=("text", "json"),
              response_mode="sync", polling_mode="none", prompt_profile="minimax.text.m3"),
    _contract("minimax", "MiniMax-M2.7", "text", "minimax.text.m27.v1", inputs=("text", "json"),
              response_mode="sync", polling_mode="none", prompt_profile="minimax.text.m27"),
    _contract("minimax", "image-01", "image", "minimax.image.image01.v1", inputs=("text",),
              response_mode="sync_or_async", polling_mode="operation_reconcile",
              prompt_profile="minimax.image.image01"),
    _contract("minimax", "speech-2.6-hd", "tts", "minimax.tts.v2.v1", inputs=("text", "voice"),
              response_mode="sync", polling_mode="none", prompt_profile="minimax.tts.v2"),
    _contract("volcano", "seed-tts-2.0", "tts", "volcano.seed_tts.v3.v1", inputs=("text", "voice"),
              response_mode="sync", polling_mode="none", prompt_profile="volcano.seed_tts.v3"),
    _contract("volcano", "doubao-seedance-1-5-pro-251215", "video", "volcano.seedance15.v1",
              inputs=("text", "image"), response_mode="async", polling_mode="provider_task",
              prompt_profile="volcano.seedance15", references=(1, 0, 0), retry_policy="status_poll_only"),
    _contract("alibaba", "happyhorse-1.1-i2v", "video", "alibaba.happyhorse11.i2v.v1",
              inputs=("text", "image"), response_mode="async", polling_mode="provider_task",
              prompt_profile="alibaba.happyhorse11.i2v", references=(1, 0, 0), retry_policy="status_poll_only"),
    _contract("alibaba", "happyhorse-1.1-r2v", "video", "alibaba.happyhorse11.r2v.v1",
              inputs=("text", "image"), response_mode="async", polling_mode="provider_task",
              prompt_profile="alibaba.happyhorse11.r2v", references=(1, 0, 0), retry_policy="status_poll_only"),
    _contract("alibaba", "happyhorse-1.1-t2v", "video", "alibaba.happyhorse11.t2v.v1",
              inputs=("text",), response_mode="async", polling_mode="provider_task",
              prompt_profile="alibaba.happyhorse11.t2v", retry_policy="status_poll_only"),
]

_BY_ID = {(item.provider_id.lower(), item.api_model_id.lower(), item.capability): item for item in _CONTRACTS}
_ALIASES = {("minimax", "minimax-speech-2-6-hd", "tts"): ("minimax", "speech-2.6-hd", "tts")}


def resolve_model_execution_contract(
    provider_id: str, api_model_id: str, capability: str,
) -> ModelExecutionContract:
    key = (str(provider_id).lower(), str(api_model_id).lower(), str(capability).lower())
    contract = _BY_ID.get(_ALIASES.get(key, key))
    return contract or unverified_contract(*key)


__all__ = ["resolve_model_execution_contract"]
