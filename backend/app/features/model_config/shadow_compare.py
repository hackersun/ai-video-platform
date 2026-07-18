"""Sanitized comparison for reversible legacy-to-canonical read cutover."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Mapping
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model_center import ModelConfigAuditEvent


_HIGH_SEVERITY_FIELDS = (
    "capability",
    "provider_id",
    "api_model_id",
    "connection_id",
    "prompt_profile_version_id",
    "native_audio",
    "output_contract",
)


def _fingerprint(value: object) -> str:
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return sha256(body.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class ResolutionComparison:
    high_severity_fields: tuple[str, ...]
    comparison_fingerprint: str

    @property
    def has_high_severity(self) -> bool:
        return bool(self.high_severity_fields)

    def sanitized_dict(self) -> dict[str, object]:
        return {
            "has_high_severity": self.has_high_severity,
            "high_severity_fields": list(self.high_severity_fields),
            "comparison_fingerprint": self.comparison_fingerprint,
        }


def compare_resolutions(
    *, legacy: Mapping[str, object], canonical: Mapping[str, object]
) -> ResolutionComparison:
    differing = tuple(
        field for field in _HIGH_SEVERITY_FIELDS
        if legacy.get(field) != canonical.get(field)
    )
    return ResolutionComparison(
        high_severity_fields=differing,
        comparison_fingerprint=_fingerprint({
            "legacy": {field: legacy.get(field) for field in _HIGH_SEVERITY_FIELDS},
            "canonical": {field: canonical.get(field) for field in _HIGH_SEVERITY_FIELDS},
        }),
    )


async def record_shadow_difference(
    db: AsyncSession,
    *,
    user_id: str,
    resource_id: str,
    comparison: ResolutionComparison,
) -> ModelConfigAuditEvent | None:
    """Persist only field names and a fingerprint, never resolved IDs or secrets."""
    if not comparison.has_high_severity:
        return None
    event = ModelConfigAuditEvent(
        id=str(uuid4()), user_id=user_id, resource_type="model_binding",
        resource_id=resource_id, action="shadow_difference", reason="shadow_high_severity_diff",
        sanitized_change_summary=comparison.sanitized_dict(),
    )
    try:
        async with db.begin_nested():
            db.add(event)
            await db.flush()
    except Exception:
        return None
    return event


__all__ = ["ResolutionComparison", "compare_resolutions", "record_shadow_difference"]
