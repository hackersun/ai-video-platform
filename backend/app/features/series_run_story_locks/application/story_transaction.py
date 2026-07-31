"""Atomic Story Lock versioning and selected-shot enrichment."""
from __future__ import annotations
from typing import Any
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from app.models import Chapter, Shot, StoryEntity
from app.models.media_generation_job import MediaGenerationJob
from app.models.series_production_run import SeriesProductionRun
from app.services.dialogue_lineage_service import extract_explicit_dialogue
from app.services.live_canary_budget import BindingValidationError, required_tested_at_for_run, validate_model_bindings
from app.services.episode_production_service import create_or_resolve_shots_stage
from app.services.series_run_skill_routing import (
    resolve_required_series_run_skill,
    skill_audit_evidence,
)
from app.services.deterministic_provider_fake import deterministic_provider_fake_enabled
from app.services.story_entity_lifecycle import APPROVED, CANDIDATE, get_entity_review_status, set_entity_review_status
from app.core.time_utils import utc_now
from ..domain import ProductionRequiredEntityBlocked, StoryLockSourceStale
from ..domain.scoped_reference import evidence_ref_id
from .prepare_story_locks import load_required_context
from .inspect_freshness import StoryLockFreshnessBlocked, ordered_run_chapters
from ..public_errors import StoryLockPreparationBlocked
from ..repositories import StoryLockLineageRepository, StoryLockRepository
from .closure_v2_request import build_closure_v2_request, refresh_scoped_for_shot
from .explicit_dialogue_approval import _prepare_explicit_dialogue_facts
from .production_closure_v2 import persist_production_closure_v2
from .production_scoped_inputs import _is_signed_merged_competitor
async def _ordered_run_chapters(db: AsyncSession, run: SeriesProductionRun) -> list[Chapter]:
    try:
        return await ordered_run_chapters(StoryLockLineageRepository(db), run)
    except StoryLockFreshnessBlocked as error:
        raise StoryLockPreparationBlocked(str(error)) from error


async def _reset_selected_refs_to_signed_sources(
    db: AsyncSession, run: SeriesProductionRun, selected: set[str], episode: dict[str, Any],
    trusted_reference_ids: set[str],
) -> None:
    for shot_id in selected.intersection((episode.get("canonical_ids") or {}).get("shot_ids") or []):
        shot = await db.get(Shot, shot_id)
        extra, changed = dict(shot.extra_data or {}), False
        refs = {key: [dict(value) for value in values]
                for key, values in dict(extra.get("entity_refs") or {}).items()}
        for values in refs.values():
            for reference in values:
                source_id = reference.get("source_entity_id")
                canonical_id = reference.get("canonical_entity_id") or reference.get("entity_id")
                complete = reference.get("contract_version") == "chapter_evidence_ref_v1"
                if complete and (
                    reference.get("evidence_ref_id") != evidence_ref_id(reference)
                    or (reference.get("evidence") or {}).get("source_entity_id") != source_id
                    or reference.get("entity_id") != reference.get("canonical_entity_id")
                ):
                    raise ValueError("persisted scoped reference is stale forged or legacy")
                rebuild = complete and reference.get("evidence_ref_id") in trusted_reference_ids \
                    and source_id == canonical_id
                if rebuild or not complete:
                    entity_type = reference.get("entity_type")
                    if not entity_type and canonical_id:
                        canonical = await db.get(StoryEntity, str(canonical_id))
                        if (canonical is not None and canonical.user_id == run.user_id
                                and canonical.novel_id == run.novel_id):
                            entity_type = canonical.entity_type
                    candidates = list((await db.scalars(select(StoryEntity).where(
                        StoryEntity.user_id == run.user_id, StoryEntity.novel_id == run.novel_id,
                        StoryEntity.chapter_id == (
                            extra.get("chapter_id") or (episode.get("chapter_ids") or [None])[0]
                        ),
                        StoryEntity.entity_type == entity_type,
                    ))).all())
                    local = [candidate for candidate in candidates
                             if _is_signed_merged_competitor(candidate, str(canonical_id))]
                    if len(local) > 1:
                        raise ValueError("chapter-local merged source is ambiguous")
                    if local:
                        source_id = local[0].id
                        rebuild = True
                if rebuild and source_id:
                    reference.clear()
                    reference["entity_id"] = source_id
                    changed = True
        if changed:
            shot.extra_data = {**extra, "entity_refs": refs}


async def _selected_reference_ids(
    db: AsyncSession, run: SeriesProductionRun, selected: set[str],
) -> set[str]:
    reference_ids: set[str] = set()
    for episode in run.episodes or []:
        for shot_id in selected.intersection((episode.get("canonical_ids") or {}).get("shot_ids") or []):
            shot = await db.get(Shot, shot_id)
            if shot is None:
                raise ValueError("selected shot is missing")
            refs = (shot.extra_data or {}).get("entity_refs") or {}
            if not isinstance(refs, dict):
                raise ValueError("selected shot entity references are malformed")
            for values in refs.values():
                if not isinstance(values, list):
                    raise ValueError("selected shot entity reference bucket is malformed")
                for reference in values or []:
                    if not isinstance(reference, dict):
                        raise ValueError("selected shot entity reference is malformed")
                    source_id = reference.get("source_entity_id")
                    canonical_id = reference.get("canonical_entity_id") or reference.get("entity_id")
                    source = await db.get(StoryEntity, str(source_id or "")) if source_id else None
                    if (reference.get("contract_version") == "chapter_evidence_ref_v1"
                            and source_id == canonical_id and source is not None
                            and source.user_id == run.user_id and source.novel_id == run.novel_id):
                        reference_ids.add(str(reference.get("evidence_ref_id") or ""))
    return reference_ids


def _approve_deterministic_required(entities: list[Any], user_id: str) -> None:
    if not deterministic_provider_fake_enabled():
        return
    for entity in entities:
        if get_entity_review_status(entity) != CANDIDATE:
            continue
        entity.attributes = {**(entity.attributes or {}), "approval_record": {
            "approved_by": user_id, "approved_at": utc_now().isoformat(),
            "reason": "deterministic_verified_required_fact"}}
        set_entity_review_status(entity, APPROVED, changed_by=user_id,
                                 reason="deterministic_verified_required_fact")


async def _backfill_verified_auto_approval_records(
    db: AsyncSession, run: SeriesProductionRun,
) -> None:
    entities = list((await db.scalars(select(StoryEntity).where(
        StoryEntity.user_id == run.user_id,
        StoryEntity.novel_id == run.novel_id,
        StoryEntity.source == "deterministic",
    ).with_for_update())).all())
    for entity in entities:
        attributes = dict(entity.attributes or {})
        lifecycle = dict((entity.extra_data or {}).get("lifecycle") or {})
        evidence = dict(attributes.get("evidence_contract") or {})
        if (
            get_entity_review_status(entity) == APPROVED
            and not attributes.get("approval_record")
            and lifecycle.get("reason") == "entity_extraction_v2:auto_approve"
            and evidence.get("status") == "verified"
        ):
            attributes["approval_record"] = {
                "approved_by": lifecycle.get("changed_by") or run.user_id,
                "approved_at": lifecycle.get("changed_at") or utc_now().isoformat(),
                "reason": "entity_extraction_v2:auto_approve",
            }
            entity.attributes = attributes


async def apply_closure_v2_transaction(db: AsyncSession, run_id: str, request: dict[str, Any] | None,
                                       expected_run_version: int, fail_at: str | None = None,
                                       user_id: str | None = None,
                                       tts_snapshot: dict[str, str] | None = None,
                                       native_audio: bool = False) -> dict[str, Any]:
    async with db.begin():
        transaction_run_version = expected_run_version
        if request is None:
            fresh_run = await db.scalar(select(SeriesProductionRun).where(
                SeriesProductionRun.id == run_id).with_for_update())
            if fresh_run is None: raise StoryLockPreparationBlocked("run missing")
            selected = set((fresh_run.run_metadata or {}).get("selected_anchor_shot_ids") or [])
            await _backfill_verified_auto_approval_records(db, fresh_run)
            if tts_snapshot or native_audio:
                first_lock = not bool(
                    (((fresh_run.run_metadata or {}).get("story_locks") or {}).get("story_bible_id"))
                )
                migration_ids = (
                    await _selected_reference_ids(db, fresh_run, selected)
                    if first_lock else set()
                )
                if migration_ids:
                    for episode in fresh_run.episodes or []:
                        if selected.intersection((episode.get("canonical_ids") or {}).get("shot_ids") or []):
                            await create_or_resolve_shots_stage(db, run=fresh_run, episode=episode)
                trusted_reference_ids = migration_ids
                await _prepare_explicit_dialogue_facts(
                    db, fresh_run, await _ordered_run_chapters(db, fresh_run), tts_snapshot,
                    native_audio=native_audio,
                )
                for episode in fresh_run.episodes or []:
                    if selected.intersection((episode.get("canonical_ids") or {}).get("shot_ids") or []):
                        await _reset_selected_refs_to_signed_sources(
                            db, fresh_run, selected, episode, trusted_reference_ids)
                        await create_or_resolve_shots_stage(db, run=fresh_run, episode=episode)
            metadata = fresh_run.run_metadata or {}
            has_existing_lock = bool(
                ((metadata.get("story_locks") or {}).get("story_bible_id"))
            )
            has_superseded_lock = bool(metadata.get("superseded_story_locks"))
            should_refresh_refs = getattr(fresh_run, "status", None) == "media_running" or (
                not has_existing_lock and has_superseded_lock
            ) or bool(tts_snapshot or native_audio)
            if has_existing_lock and not should_refresh_refs:
                await build_closure_v2_request(
                    db, fresh_run.id, expected_run_version=fresh_run.version,
                    user_id=fresh_run.user_id,
                )
            if should_refresh_refs:
                for shot_id in selected:
                    shot = await db.get(Shot, shot_id)
                    if shot is None:
                        raise ValueError("selected shot is missing")
                    await refresh_scoped_for_shot(db, fresh_run, shot)
                await db.flush()
            required = await load_required_context(StoryLockRepository(db),fresh_run)
            _approve_deterministic_required(list(required.required_entities), fresh_run.user_id)
            transaction_run_version = int(fresh_run.version)
        effective = request or await build_closure_v2_request(
            db,run_id,expected_run_version=transaction_run_version,user_id=user_id)
        return await persist_production_closure_v2(db, run_id, effective,
            expected_run_version=transaction_run_version, fail_at=fail_at, enrich_shots=request is None)


async def _ensure_story_lock_preparation_state(
    db: AsyncSession, run: SeriesProductionRun,
) -> None:
    if run.status in {"shots_ready", "anchor_ready"}:
        return
    if run.status != "media_running":
        raise StoryLockPreparationBlocked(f"stale run status: {run.status}")
    selected = list((run.run_metadata or {}).get("selected_anchor_shot_ids") or [])
    if not selected:
        raise StoryLockPreparationBlocked("media retry has no selected anchor shots")
    active_count = await db.scalar(
        select(func.count()).select_from(MediaGenerationJob).where(
            MediaGenerationJob.user_id == run.user_id,
            MediaGenerationJob.shot_id.in_(selected),
            MediaGenerationJob.is_active.is_(True),
            MediaGenerationJob.status.in_(("unknown", "reserved", "accepted", "processing", "pending")),
        )
    )
    if int(active_count or 0):
        raise StoryLockPreparationBlocked("selected media jobs are still active")


async def prepare_story_locks(
    db: AsyncSession, run: SeriesProductionRun, *, native_audio: bool = False,
) -> dict[str, Any]:
    """Validate external binding state first, then atomically persist every story-lock mutation."""
    await _ensure_story_lock_preparation_state(db, run)
    chapters = await _ordered_run_chapters(db, run)
    has_explicit_dialogue = any(extract_explicit_dialogue(str(chapter.content or "")) for chapter in chapters)
    tts_snapshot: dict[str, str] | None = None
    if has_explicit_dialogue and not native_audio:
        bindings = {
            capability: str((((run.model_bindings or {}).get("capabilities") or {}).get(capability) or {}).get("config_id") or "")
            for capability in ("text", "image", "tts", "video")
        }
        try:
            snapshots = await validate_model_bindings(
                db, run, bindings, required_tested_at=required_tested_at_for_run(run), freshness_seconds=900,
            )
            tts_snapshot = snapshots["tts"]
        except BindingValidationError as error:
            await db.rollback()
            raise StoryLockPreparationBlocked(str(error)) from error
    run_id, user_id, expected_version = run.id, run.user_id, int(run.version)
    await db.rollback()
    try:
        result = await apply_closure_v2_transaction(
            db, run_id, None, expected_version, user_id=user_id,
            tts_snapshot=tts_snapshot, native_audio=native_audio,
        )
        persisted_run = await db.get(SeriesProductionRun, run_id)
        if persisted_run is None:
            raise StoryLockPreparationBlocked("series run disappeared after story lock")
        entity_skill_route = await resolve_required_series_run_skill(
            db,
            user_id=user_id,
            task="entity_extraction",
            stage="analysis",
            context={
                "entity_types": "character、scene、prop、event",
                "source_type": "series_run_chapters",
                "source_content": "\n\n".join(str(chapter.content or "") for chapter in chapters),
                "output_format": "JSON 数组",
            },
            internal_prompt="从四章原文抽取可跨章追踪的角色、场景、道具和事件。",
        )
        entity_skill_evidence = skill_audit_evidence(entity_skill_route)
        metadata = dict(persisted_run.run_metadata or {})
        previous_skill_evidence = dict(metadata.get("skill_evidence") or {})
        previous_entity_evidence = dict(previous_skill_evidence.get("entity_extraction") or {})
        metadata["skill_evidence"] = {
            **previous_skill_evidence,
            "entity_extraction": {**previous_entity_evidence, **entity_skill_evidence},
        }
        persisted_run.run_metadata = metadata
        flag_modified(persisted_run, "run_metadata")
        await db.commit()
        return result
    except StoryLockPreparationBlocked:
        raise
    except StoryLockSourceStale:
        await db.rollback()
        raise
    except ProductionRequiredEntityBlocked:
        await db.rollback()
        raise
    except ValueError as error:
        await db.rollback()
        raise StoryLockPreparationBlocked(code="story_lock_source_invalid",
            blocker_category="selection_state",field="story_source") from error
