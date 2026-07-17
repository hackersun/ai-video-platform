"""Secret-safe classification of image-provider response envelopes."""

from __future__ import annotations

import hashlib
from typing import Any

from app.services.image_generation_pipeline import provider_task_id
from app.services.image_result_parser import extract_image_urls_from_provider_result


def _count(value: Any) -> int | None:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return None


def _kind(value: Any) -> str:
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if value is None:
        return "missing"
    return type(value).__name__


def classify_image_provider_response(result: Any, provider_name: str) -> dict[str, Any]:
    mapping = result if isinstance(result, dict) else {}
    images = extract_image_urls_from_provider_result(result)
    task_id = provider_task_id(result, provider_name=provider_name)
    metadata = mapping.get("metadata") if isinstance(mapping.get("metadata"), dict) else {}
    base_resp = mapping.get("base_resp") if isinstance(mapping.get("base_resp"), dict) else {}
    message = str(base_resp.get("status_msg") or "")
    url_count = sum(not item.startswith("data:image/") for item in images)
    base64_count = len(images) - url_count
    evidence = {
        "schema_version": "image-provider-response-shape-v1",
        "provider": str(provider_name or "").lower(),
        "response_kind": _kind(result),
        "data_kind": _kind(mapping.get("data")),
        "provider_task_id_present": bool(task_id),
        "artifact_returned": bool(images),
        "payload_counts": {"base64": base64_count, "url": url_count},
        "metadata_counts": {
            "failed": _count(metadata.get("failed_count")),
            "success": _count(metadata.get("success_count")),
        },
        "base_status_code": str(base_resp.get("status_code")) if "status_code" in base_resp else None,
        "base_status_message_sha256": hashlib.sha256(message.encode()).hexdigest() if message else None,
    }
    return {
        "status": "completed" if images else ("accepted" if task_id else "unknown"),
        "provider_task_id": str(task_id) if task_id else None,
        "image_urls": images,
        "evidence": evidence,
    }


async def persist_image_response_evidence(
    db: Any,
    run: Any,
    *,
    operation_id: str,
    evidence: dict[str, Any],
) -> None:
    allowed = {
        "schema_version", "provider", "response_kind", "data_kind",
        "provider_task_id_present", "artifact_returned", "payload_counts",
        "metadata_counts", "base_status_code", "base_status_message_sha256",
    }
    safe = {key: value for key, value in evidence.items() if key in allowed}
    metadata = dict(run.run_metadata or {})
    records = dict(metadata.get("provider_response_evidence") or {})
    records[str(operation_id)] = safe
    metadata["provider_response_evidence"] = dict(list(records.items())[-20:])
    run.run_metadata = metadata
    await db.commit()


__all__ = ["classify_image_provider_response", "persist_image_response_evidence"]
