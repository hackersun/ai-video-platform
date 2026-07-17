"""Minimal cross-feature facade for selected-anchor Story Locks."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from app.core.time_utils import utc_now
from app.models.series_production_run import SeriesProductionRun

from .application.prepare_story_locks import referenced_entity_ids
from .application.story_transaction import prepare_story_locks as prepare_transaction
from .application.inspect_freshness import StoryLockFreshnessBlocked, inspect
from .domain import RequiredEntityBlocked, StoryLockSourceStale, build_closure
from .repositories import CaptureStoryLockResponseCommand, StoryLockLineageRepository, StoryLockRepository
from .public_errors import StoryLockPreparationBlocked
from .application.voice_contract import provider_voice_allowlist, selection_hash, valid_voice_selection
from .application.deterministic_acceptance import (
    apply_deterministic_voice_binding, deterministic_anchor_entity_refs, deterministic_evidence_contract,
    seed_deterministic_local_mentions,
)
from .application.invalidate_lineage import invalidate_lineage


def build_required_entity_closure(*, selected_shots: list[object], candidates: list[object]) -> dict[str, object]:
    facts = StoryLockRepository.facts(candidates)
    return build_closure(referenced_entity_ids(selected_shots), facts).as_dict()


async def prepare_story_locks(db: AsyncSession, run: SeriesProductionRun) -> dict[str, object]:
    repository = StoryLockRepository(db)
    try:
        return await prepare_transaction(db, run)
    except RequiredEntityBlocked as error:
        await db.rollback()
        raise StoryLockPreparationBlocked(
            code=error.code, blocker_category=error.blocker_category, field=error.field,
            values=error.values, required_counts=error.required_counts,
        ) from error
    except StoryLockSourceStale as error:
        await db.rollback()
        first_lock_codes = {
            "selected_ids_missing_or_duplicate": "anchor_selection_required",
            "selected_typed_refs_missing": "anchor_entity_closure_required",
        }
        raise StoryLockPreparationBlocked(
            code=first_lock_codes.get(error.code, "story_lock_source_invalid"),
            blocker_category="selection_state", field=(
                "selected_anchor_shot_ids" if error.code in first_lock_codes else "story_source"
            ),
        ) from error
    except ValueError as error:
        await db.rollback()
        raise


async def inspect_story_lock_freshness(
    db: AsyncSession, run: SeriesProductionRun, *, supersede: bool = False,
) -> dict[str, Any]:
    try:
        return await inspect(StoryLockLineageRepository(db), run, supersede=supersede)
    except StoryLockFreshnessBlocked as error:
        raise StoryLockPreparationBlocked(str(error)) from error
    except Exception:
        await db.rollback()
        raise


async def invalidate_story_lock_lineage(
    db: AsyncSession, run: SeriesProductionRun, *, reason: str,
) -> None:
    await invalidate_lineage(StoryLockLineageRepository(db), run, reason=reason)


def safe_story_lock_error_detail(error: StoryLockPreparationBlocked) -> dict[str, object]:
    legacy = _safe_legacy_detail(error.safe_detail.get("conflict_fields") or [])
    if legacy is not None:
        return legacy
    categories = {"identity_state", "character_state", "scene_state", "prop_state", "event_state", "selection_state"}
    if error.blocker_category not in categories or not _safe_field(error.field):
        return {"code": "story_lock_preparation_blocked"}
    try:
        hashes = sorted({_canonical_hash(value) for value in error.values})
    except (TypeError, ValueError, OverflowError):
        return {"code": "story_lock_preparation_blocked"}
    return {
        "code": error.code, "blocker_category": error.blocker_category, "field": error.field,
        "required_counts": error.required_counts, "value_hashes": hashes,
    }


async def capture_story_lock_response(
    db: AsyncSession,
    run: SeriesProductionRun,
    *,
    status_code: int,
    response_body: dict[str, Any],
) -> dict[str, object]:
    return await StoryLockRepository(db).capture_response(CaptureStoryLockResponseCommand(
        run=run, status_code=status_code, body=response_body,
        body_sha256=_canonical_hash(response_body), captured_at=utc_now().isoformat(),
    ))


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def _safe_field(value: object) -> bool:
    text = str(value)
    return bool(text and len(text) <= 64 and text[0].islower() and all(char.islower() or char.isdigit() or char == "_" for char in text))


def _safe_legacy_detail(conflicts: list[object]) -> dict[str, object] | None:
    if not conflicts:
        return None
    allowed = {"identity_attribute", "identity_column", "identity_relation", "identity_state",
               "identity_tag", "entity_lifecycle", "voice_binding"}
    sanitized = []
    try:
        for item in conflicts:
            if not isinstance(item, dict) or item.get("category") not in allowed or not _safe_field(item.get("field")):
                return {"code": "story_lock_preparation_blocked"}
            values = item.get("values", item.get("value_hashes"))
            if not isinstance(values, list) or not values:
                return {"code": "story_lock_preparation_blocked"}
            sanitized.append({"category": item["category"], "field": item["field"],
                              "value_hashes": sorted({_canonical_hash(value) for value in values})})
    except (TypeError, ValueError, OverflowError):
        return {"code": "story_lock_preparation_blocked"}
    return {"code": "story_lock_preparation_blocked", "message": "story lock preparation blocked",
            "conflict_fields": sanitized}


__all__ = [
    "StoryLockPreparationBlocked", "build_required_entity_closure", "capture_story_lock_response", "inspect_story_lock_freshness",
    "prepare_story_locks", "safe_story_lock_error_detail",
    "provider_voice_allowlist", "selection_hash", "valid_voice_selection",
    "deterministic_anchor_entity_refs", "deterministic_evidence_contract",
    "apply_deterministic_voice_binding",
    "seed_deterministic_local_mentions",
    "invalidate_story_lock_lineage",
]
