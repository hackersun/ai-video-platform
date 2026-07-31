"""Visual contract helpers for canonical series reference assets."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.models import Asset
from app.models.live_canary_provider_operation import LiveCanaryProviderOperation
from app.models.series_production_run import SeriesProductionRun


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def model_binding_ids(run: SeriesProductionRun) -> dict[str, str]:
    capabilities = (run.model_bindings or {}).get("capabilities") or {}
    return {
        name: str((capabilities.get(name) or {}).get("config_id") or "")
        for name in ("text", "image", "tts", "video")
    }


def provider_operation_payload(operation: LiveCanaryProviderOperation) -> dict[str, Any]:
    return {
        "id": operation.id,
        "status": operation.status,
        "provider_task_id": operation.provider_task_id,
        "reservation_id": operation.reservation_id,
        "actual_rmb": operation.actual_rmb,
        "cost_source": operation.cost_source,
    }


def character_role_bindings(characters: list[Any]) -> list[dict[str, str]]:
    entity_ids = list(dict.fromkeys(str(character.id) for character in characters))
    return [{"role": "character_canonical", "entity_id": entity_id} for entity_id in entity_ids]


def reference_visual_contract_hash(characters: list[Any]) -> str:
    contracts = []
    for character in characters:
        attributes = character.attributes if isinstance(character.attributes, dict) else {}
        contracts.append({
            "entity_id": str(character.id),
            "appearance": str(getattr(character, "appearance", None) or "").strip(),
            "visual_dna": attributes.get("visual_dna") or {},
        })
    return canonical_hash(sorted(contracts, key=lambda item: item["entity_id"]))


def reference_visual_contract_matches(asset: Any, characters: list[Any]) -> bool:
    params = asset.generation_params if isinstance(asset.generation_params, dict) else {}
    evidence = params.get("evidence") if isinstance(params.get("evidence"), dict) else {}
    return evidence.get("visual_contract_hash") == reference_visual_contract_hash(characters)


def reference_artifact_payload(asset: Asset) -> dict[str, Any]:
    evidence = (asset.generation_params or {}).get("evidence") or {}
    return {
        "id": asset.id,
        "url": asset.url,
        "checksum": evidence.get("checksum"),
        "layout_evidence": evidence.get("layout_evidence") or {},
        "width": evidence.get("width"),
        "height": evidence.get("height"),
        "byte_size": evidence.get("byte_size"),
        "public_url_expires_at": evidence.get("public_url_expires_at"),
        "storage_delivery": evidence.get("storage_delivery") or {},
        "prompt_skill": (asset.generation_params or {}).get("prompt_skill") or {},
    }


__all__ = [
    "canonical_hash",
    "character_role_bindings",
    "model_binding_ids",
    "provider_operation_payload",
    "reference_artifact_payload",
    "reference_visual_contract_hash",
    "reference_visual_contract_matches",
]
