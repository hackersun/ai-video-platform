"""Canonical, non-secret proof metadata for isolated live-canary staging."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any


PROOF_KEY = "canary_staging_v1"
PROOF_FIELDS = {
    "staged_at", "source_test_status", "source_tested_at", "config_id",
    "model_id", "provider_id", "target_user_id", "canonical_sha256",
}


def _naive_utc(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def normalized_timestamp(value: Any) -> str:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    return _naive_utc(parsed).isoformat()


def _digest(payload: dict[str, str]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def build_staging_proof(
    *, staged_at: datetime, source_test_status: str, source_tested_at: Any,
    config_id: str, model_id: str, provider_id: str, target_user_id: str,
) -> dict[str, str]:
    payload = {
        "staged_at": normalized_timestamp(staged_at),
        "source_test_status": str(source_test_status),
        "source_tested_at": normalized_timestamp(source_tested_at),
        "config_id": str(config_id),
        "model_id": str(model_id),
        "provider_id": str(provider_id),
        "target_user_id": str(target_user_id),
    }
    return {**payload, "canonical_sha256": _digest(payload)}


def validate_staging_proof(
    proof: Any, *, config_id: str, model_id: str, provider_id: str,
    target_user_id: str, test_status: Any, tested_at: Any,
    now: datetime | None = None, max_age_seconds: int = 900,
) -> datetime:
    if not isinstance(proof, dict) or set(proof) != PROOF_FIELDS:
        raise ValueError("isolated staging proof is missing or malformed")
    expected = build_staging_proof(
        staged_at=datetime.fromisoformat(str(proof["staged_at"])),
        source_test_status=str(test_status), source_tested_at=tested_at,
        config_id=config_id, model_id=model_id, provider_id=provider_id,
        target_user_id=target_user_id,
    )
    if proof != expected or proof["source_test_status"] != "success":
        raise ValueError("isolated staging proof does not match the bound configuration")
    staged_at = datetime.fromisoformat(expected["staged_at"])
    current = _naive_utc(now or datetime.now(timezone.utc))
    if staged_at > current + timedelta(seconds=30):
        raise ValueError("isolated staging proof timestamp is in the future")
    if staged_at < current - timedelta(seconds=max_age_seconds):
        raise ValueError("isolated staging proof has expired")
    return staged_at
