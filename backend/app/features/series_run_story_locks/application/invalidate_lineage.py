"""Single owner for Story/reference/shot/contract/quality invalidation."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from app.core.time_utils import utc_now
from app.models.series_production_run import SeriesProductionRun

from ..repositories.lineage_repository import StoryLockLineageRepository
from .inspect_freshness import fingerprint


def _invalidate_bible(bible: object | None, lock: dict[str, Any], reason: str, now: str) -> bool:
    if bible is None:
        return False
    extra = dict(getattr(bible, "extra_data", None) or {})
    machine = dict(extra.get("state_machine") or {})
    status = "superseded" if reason == "voice_binding_snapshot_drift" else "superseded_review_required"
    machine["status"] = status
    extra.update(production_status=status, superseded_reason=reason,
                 superseded_hash=fingerprint(lock), superseded_at=now, state_machine=machine)
    bible.extra_data = extra
    flag_modified(bible, "extra_data")
    return True


def _invalidate_reference(asset: object | None, bindings: list[object], reference: dict[str, Any], reason: str, now: str) -> bool:
    if asset is None:
        return False
    audit = dict(getattr(asset, "generation_params", None) or {})
    audit.update(status="superseded", superseded_reason=reason,
                 superseded_hash=fingerprint(reference), superseded_at=now)
    asset.generation_params = audit
    asset.is_active = asset.is_final = asset.is_locked = False
    asset.locked_at = None
    flag_modified(asset, "generation_params")
    for binding in bindings:
        binding.is_active, binding.verified_at = False, None
        binding.invalidated_at, binding.invalidation_reason = utc_now(), reason
    return True


def _invalidate_shots(shots: list[object], reason: str, now: str) -> bool:
    changed = False
    keys = ("voice_binding", "story_bible_id", "story_bible_version", "speaker_entity_id",
            "production_context", "story_lock_lineage")
    for shot in shots:
        extra = dict(getattr(shot, "extra_data", None) or {})
        historical = {key: extra.get(key) for key in keys if extra.get(key) is not None}
        if not historical:
            continue
        extra.setdefault("superseded_voice_lineage", []).append({**historical, "reason": reason, "superseded_at": now})
        for key in historical:
            extra.pop(key, None)
        extra["quality_lineage_status"] = "superseded"
        shot.extra_data = extra
        flag_modified(shot, "extra_data")
        changed = True
    return changed


def _invalidate_contracts(workflows: list[object], reason: str, now: str) -> bool:
    changed = False
    for workflow in workflows:
        metadata = dict(getattr(workflow, "metadata_", None) or {})
        contract = dict(metadata.get("episode_contract") or {})
        if not contract:
            continue
        previous = {**contract, "status": "superseded", "superseded_reason": reason,
                    "superseded_hash": fingerprint(contract), "superseded_at": now}
        metadata["episode_contract_versions"] = [*(metadata.get("episode_contract_versions") or []), previous]
        metadata["episode_contract"] = previous
        workflow.metadata_ = metadata
        flag_modified(workflow, "metadata_")
        changed = True
    return changed


def _invalidate_run_metadata(run: SeriesProductionRun, reason: str, now: str) -> None:
    metadata = dict(run.run_metadata or {})
    for current_key, history_key in (("story_locks", "superseded_story_locks"),
                                     ("reference_preparation", "superseded_references")):
        current = metadata.pop(current_key, None)
        if current:
            metadata.setdefault(history_key, []).append({**current, "reason": reason, "superseded_at": now})
    reports = metadata.pop("anchor_quality_reports", None)
    if reports:
        metadata.setdefault("superseded_anchor_quality_reports", []).append(
            {"reason": reason, "superseded_at": now, "reports": reports})
    run.run_metadata = metadata
    episodes = []
    for item in run.episodes or []:
        current = dict(item)
        lineage = current.pop("story_lock_lineage", None)
        if lineage:
            current.setdefault("superseded_story_lock_lineage", []).append(
                {**lineage, "reason": reason, "superseded_at": now})
        current.update(contract_status="superseded", contract_superseded_reason=reason)
        episodes.append(current)
    run.episodes = episodes
    flag_modified(run, "run_metadata")
    flag_modified(run, "episodes")


async def invalidate_lineage(
    repository: StoryLockLineageRepository, run: SeriesProductionRun, *, reason: str, commit: bool = True,
) -> None:
    now = utc_now().isoformat()
    metadata = dict(run.run_metadata or {})
    lock, reference = dict(metadata.get("story_locks") or {}), dict(metadata.get("reference_preparation") or {})
    bible = await repository.bible(str(lock.get("story_bible_id") or "")) if lock.get("story_bible_id") else None
    asset, bindings = await repository.reference_asset(run)
    workflows, shots = await repository.workflows_and_shots(run)
    _invalidate_bible(bible, lock, reason, now)
    _invalidate_reference(asset, bindings, reference, reason, now)
    _invalidate_shots(shots, reason, now)
    _invalidate_contracts(workflows, reason, now)
    _invalidate_run_metadata(run, reason, now)
    if commit:
        await repository.commit()
