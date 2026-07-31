"""User-triggered deterministic cleanup for pre-media series assets."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models import Chapter, Shot, StoryEntity
from app.models.series_production_run import SeriesProductionRun
from app.services.entity_extraction_service import ENTITY_TYPES, extract_story_entities
from app.services.entity_review_service import run_candidate_entity_extraction
from app.services.dialogue_lineage_service import extract_explicit_dialogue
from app.services.story_entity_lifecycle import APPROVED, ARCHIVED, get_entity_review_status, set_entity_review_status

from ..domain.scoped_reference import canonical_identity_sha256, sign_merge_edge
from ..repositories import StoryLockLineageRepository
from .inspect_freshness import ordered_run_chapters
from .invalidate_lineage import invalidate_lineage


class StoryAssetRepairBlocked(ValueError):
    pass


def _safe_automatic_entity(entity: StoryEntity) -> bool:
    lifecycle = dict((entity.extra_data or {}).get("lifecycle") or {})
    return bool(
        entity.source == "deterministic"
        and lifecycle.get("reason") == "entity_extraction_v2:auto_approve"
        and not (entity.extra_data or {}).get("manual_review")
        and not (entity.attributes or {}).get("merged_into_entity_id")
    )


async def _archive_stale_automatic_entities(
    db: AsyncSession, *, run: SeriesProductionRun, chapter: object,
    valid_keys: set[tuple[str, str]],
) -> int:
    rows = list((await db.scalars(select(StoryEntity).where(
        StoryEntity.user_id == run.user_id,
        StoryEntity.novel_id == run.novel_id,
        StoryEntity.chapter_id == str(getattr(chapter, "id")),
        StoryEntity.entity_type.in_(sorted(ENTITY_TYPES)),
    ).with_for_update())).all())
    archived = 0
    for entity in rows:
        key = (str(entity.entity_type), str(entity.name or "").strip())
        if key in valid_keys or not _safe_automatic_entity(entity):
            continue
        set_entity_review_status(
            entity, ARCHIVED, changed_by=run.user_id,
            reason="asset_normalization_repair:deterministic_noise",
        )
        archived += 1
    return archived


def _chapter_order(run: SeriesProductionRun) -> dict[str, int]:
    return {
        str(chapter_id): int(episode.get("episode_number") or 0)
        for episode in (run.episodes or [])
        for chapter_id in (episode.get("chapter_ids") or [])
    }


def _safe_character_candidate(entity: StoryEntity) -> bool:
    attributes = dict(entity.attributes or {})
    lifecycle = dict((entity.extra_data or {}).get("lifecycle") or {})
    evidence = dict(attributes.get("evidence_contract") or {})
    return bool(
        entity.source == "deterministic"
        and get_entity_review_status(entity) == "candidate"
        and lifecycle.get("reason") == "entity_extraction_v2:needs_review"
        and evidence.get("status") == "verified"
        and not entity.appearance
        and not attributes.get("approval_record")
        and not (entity.extra_data or {}).get("manual_review")
        and not attributes.get("merged_into_entity_id")
    )


def _approved_character_target(entity: StoryEntity) -> bool:
    attributes = dict(entity.attributes or {})
    return bool(
        get_entity_review_status(entity) == APPROVED
        and entity.appearance
        and attributes.get("approval_record")
        and not attributes.get("merged_into_entity_id")
    )


def _mark_merged(
    source: StoryEntity, canonical: StoryEntity, *,
    run: SeriesProductionRun, entity_type: str, name: str,
) -> None:
    edge = sign_merge_edge({
        "source_entity_id": source.id, "canonical_entity_id": canonical.id,
        "user_id": run.user_id, "novel_id": run.novel_id,
        "entity_type": entity_type,
        "canonical_identity_sha256": canonical_identity_sha256(
            entity_type=entity_type, canonical_name=name,
        ),
    })
    source.attributes = {**(source.attributes or {}), "merged_into_entity_id": canonical.id}
    source.extra_data = {
        **(source.extra_data or {}), "merge_edges": [edge],
        "normalized_merge": {"status": "merged_superseded", "canonical_entity_id": canonical.id},
    }
    set_entity_review_status(
        source, ARCHIVED, changed_by=run.user_id,
        reason="asset_normalization_repair:exact_cross_chapter_merge",
    )


async def _merge_exact_cross_chapter_assets(db: AsyncSession, run: SeriesProductionRun) -> int:
    rows = list((await db.scalars(select(StoryEntity).where(
        StoryEntity.user_id == run.user_id,
        StoryEntity.novel_id == run.novel_id,
        StoryEntity.entity_type.in_(["character", "scene", "prop"]),
    ).with_for_update())).all())
    groups: dict[tuple[str, str], list[StoryEntity]] = defaultdict(list)
    for entity in rows:
        name = str(entity.canonical_name or entity.name or "").strip()
        if name:
            groups[(str(entity.entity_type), name)].append(entity)
    chapter_order = _chapter_order(run)
    merged_count = 0
    for (entity_type, name), values in groups.items():
        if entity_type == "character":
            targets = [item for item in values if _approved_character_target(item)]
            candidates = [item for item in values if _safe_character_candidate(item)]
            if len(targets) != 1:
                continue
            for source in candidates:
                _mark_merged(source, targets[0], run=run, entity_type=entity_type, name=name)
                merged_count += 1
            continue
        values = [
            item for item in values
            if _safe_automatic_entity(item) and get_entity_review_status(item) == APPROVED
        ]
        if len(values) < 2:
            continue
        ordered = sorted(values, key=lambda item: (chapter_order.get(str(item.chapter_id), 10**9), item.id))
        canonical = ordered[0]
        for source in ordered[1:]:
            _mark_merged(source, canonical, run=run, entity_type=entity_type, name=name)
            merged_count += 1
    return merged_count


async def _clear_derived_shot_references(db: AsyncSession, run: SeriesProductionRun) -> tuple[int, int]:
    shot_ids = {
        str(shot_id)
        for episode in (run.episodes or [])
        for shot_id in ((episode.get("canonical_ids") or {}).get("shot_ids") or [])
    }
    if not shot_ids:
        return 0, 0
    shots = list((await db.scalars(select(Shot).where(
        Shot.id.in_(shot_ids), Shot.user_id == run.user_id,
    ).with_for_update())).all())
    chapter_ids = {str((shot.extra_data or {}).get("chapter_id") or "") for shot in shots}
    chapters = {
        str(chapter.id): chapter
        for chapter in (await db.scalars(select(Chapter).where(Chapter.id.in_(chapter_ids)))).all()
    }
    repaired_dialogue_count = 0
    for shot in shots:
        extra = dict(shot.extra_data or {})
        extra.pop("entity_refs", None)
        extra.pop("environment_context", None)
        chapter = chapters.get(str(extra.get("chapter_id") or ""))
        spoken = str(shot.dialogue or "").split("：", 1)[-1].strip()
        if spoken and chapter and not (extra.get("dialogue_speaker") or extra.get("parsed_speaker")):
            matches = [
                line for line in extract_explicit_dialogue(str(chapter.content or ""))
                if str(line.get("spoken_text") or "").strip() == spoken
            ]
            if len(matches) == 1:
                line = matches[0]
                extra.update({
                    "dialogue_speaker": line["speaker"], "parsed_speaker": line["speaker"],
                    "dialogue_spoken_text": line["spoken_text"],
                    "dialogue_source": {"chapter_id": chapter.id, "source_span": line["source_span"]},
                })
                repaired_dialogue_count += 1
        shot.extra_data = extra
        shot.character_refs = []
        flag_modified(shot, "extra_data")
    return len(shots), repaired_dialogue_count


async def repair_story_assets(db: AsyncSession, run: SeriesProductionRun) -> dict[str, Any]:
    """Re-extract and supersede stale locks without replacing paid reference media."""
    reference_preserved = bool((run.run_metadata or {}).get("reference_preparation"))
    chapters = await ordered_run_chapters(StoryLockLineageRepository(db), run)
    archived_noise_count = 0
    extraction_runs: list[dict[str, Any]] = []
    for chapter in chapters:
        candidates = extract_story_entities(
            str(chapter.content or ""), set(ENTITY_TYPES),
            source_chapter_id=chapter.id, source_chapter_index=int(chapter.chapter_number),
        )
        valid_keys = {(str(item["entity_type"]), str(item["name"]).strip()) for item in candidates}
        archived_noise_count += await _archive_stale_automatic_entities(
            db, run=run, chapter=chapter, valid_keys=valid_keys,
        )
        extraction = await run_candidate_entity_extraction(
            db, user_id=run.user_id, text=str(chapter.content or ""),
            source_type="chapter", source_id=chapter.id, novel_id=run.novel_id,
            chapter_id=chapter.id, entity_types=sorted(ENTITY_TYPES),
            persist=True, commit=False, allow_auto_approve=True,
            candidate_items=candidates,
        )
        extraction_runs.append({
            "chapter_id": chapter.id, "run_id": extraction["run_id"],
            "stats": extraction["stats"], "prompt_routing": extraction["prompt_routing"],
        })
    merged_duplicate_count = await _merge_exact_cross_chapter_assets(db, run)
    cleared_shot_count, repaired_dialogue_count = await _clear_derived_shot_references(db, run)
    await invalidate_lineage(
        StoryLockLineageRepository(db), run,
        reason="asset_normalization_repair", commit=False,
        preserve_reference=reference_preserved,
    )
    metadata = dict(run.run_metadata or {})
    metadata["asset_repair"] = {
        "status": "completed", "archived_noise_count": archived_noise_count,
        "merged_duplicate_count": merged_duplicate_count,
        "cleared_shot_count": cleared_shot_count, "repaired_dialogue_count": repaired_dialogue_count,
        "extraction_runs": extraction_runs,
    }
    run.run_metadata = metadata
    flag_modified(run, "run_metadata")
    await db.commit()
    return {
        "status": "completed", "archived_noise_count": archived_noise_count,
        "merged_duplicate_count": merged_duplicate_count,
        "cleared_shot_count": cleared_shot_count, "repaired_dialogue_count": repaired_dialogue_count,
        "chapter_count": len(chapters), "retry_story_lock": True,
        "reference_preserved": reference_preserved,
    }


__all__ = ["StoryAssetRepairBlocked", "repair_story_assets"]
