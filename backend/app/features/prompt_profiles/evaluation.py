"""Secret-safe deterministic Prompt Profile evaluation evidence."""

from __future__ import annotations

from hashlib import sha256
import re
from typing import Any, Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.prompt_profiles.repository import get_profile_version


FORBIDDEN_EVIDENCE_KEYS = frozenset({
    "api_key", "api_secret", "authorization", "credential", "prompt", "text", "output",
})
_DROP = object()
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")
_SAFE_HASH = re.compile(r"^[a-f0-9]{64}$")


def _hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _sanitize_metric(value: Any) -> Any:
    if isinstance(value, Mapping):
        sanitized = {}
        for key, item in value.items():
            if str(key).lower() in FORBIDDEN_EVIDENCE_KEYS:
                continue
            safe_item = _sanitize_metric(item)
            if safe_item is not _DROP:
                sanitized[str(key)] = safe_item
        return sanitized
    if isinstance(value, (list, tuple)):
        sanitized = [_sanitize_metric(item) for item in value]
        return [item for item in sanitized if item is not _DROP]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return _DROP


def sanitize_evaluation_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    result = {"metrics": _sanitize_metric(evidence.get("metrics") or {})}
    fixture_id = str(evidence.get("fixture_id") or "")
    status = str(evidence.get("status") or "")
    if _SAFE_IDENTIFIER.fullmatch(fixture_id):
        result["fixture_id"] = fixture_id
    if status in {"passed", "failed"}:
        result["status"] = status
    for key in ("prompt_hash", "output_hash"):
        value = str(evidence.get(key) or "").lower()
        if _SAFE_HASH.fullmatch(value):
            result[key] = value
    return result


def build_evaluation_evidence(
    *, fixture_id: str, status: str, prompt: str, output: str,
    metrics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "fixture_id": fixture_id, "status": status,
        "prompt_hash": _hash(prompt), "output_hash": _hash(output),
        "metrics": _sanitize_metric(metrics or {}),
    }


async def record_prompt_evaluation(
    db: AsyncSession, version_id: str, evidence: Mapping[str, Any],
):
    version = await get_profile_version(db, version_id)
    if version.status != "draft":
        raise ValueError("evaluation evidence can only be recorded on a draft")
    version.evaluation = sanitize_evaluation_evidence(evidence)
    await db.flush()
    return version
