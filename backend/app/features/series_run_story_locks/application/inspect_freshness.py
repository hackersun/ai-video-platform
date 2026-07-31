"""Compute and, when requested, invalidate stale Story Lock lineage."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.models import Chapter, StoryBible, StoryEntity
from app.models.series_production_run import SeriesProductionRun
from .visual_style import resolve_novel_visual_style
from ..domain.errors import RequiredEntityBlocked, StoryLockSourceStale

from ..repositories.lineage_repository import StoryLockLineageRepository
from ..repositories.story_lock_repository import StoryLockRepository


class StoryLockFreshnessBlocked(StoryLockSourceStale):
    """The persisted run no longer describes a valid contiguous chapter source."""


def run_chapter_ids(run: SeriesProductionRun) -> list[str]:
    ordered = sorted(run.episodes or [], key=lambda item: int(item.get("episode_number") or 0))
    episode_numbers = [int(item.get("episode_number") or 0) for item in ordered]
    if not ordered or episode_numbers != list(range(1, len(ordered) + 1)):
        raise StoryLockFreshnessBlocked("episode_order_invalid")
    chapter_ids = [str(value) for episode in ordered for value in (episode.get("chapter_ids") or [])]
    if len(chapter_ids) != len(ordered) or len(set(chapter_ids)) != len(ordered):
        raise StoryLockFreshnessBlocked("episode_chapter_shape_invalid")
    return chapter_ids


async def ordered_run_chapters(
    repository: StoryLockLineageRepository, run: SeriesProductionRun,
) -> list[Chapter]:
    chapter_ids = run_chapter_ids(run)
    rows = await repository.chapters(ids=chapter_ids, user_id=run.user_id, novel_id=run.novel_id)
    by_id = {item.id: item for item in rows}
    if set(by_id) != set(chapter_ids):
        raise StoryLockFreshnessBlocked("run_chapter_missing_or_unowned")
    return [by_id[chapter_id] for chapter_id in chapter_ids]


async def approved_entities(
    repository: StoryLockLineageRepository, run: SeriesProductionRun,
) -> list[StoryEntity]:
    return await repository.approved_entities(novel_id=run.novel_id, user_id=run.user_id)


def chapter_input_hash(chapters: list[Chapter]) -> str:
    return "|".join(f"{item.id}:{item.updated_at.isoformat() if item.updated_at else ''}" for item in chapters)


def fingerprint(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


async def current_story_source(
    repository: StoryLockLineageRepository, run: SeriesProductionRun,
) -> tuple[dict[str, Any], bool]:
    from .prepare_story_locks import load_required_context

    chapters = await ordered_run_chapters(repository, run)
    novel = await repository.novel(novel_id=run.novel_id, user_id=run.user_id)
    if novel is None:
        raise StoryLockFreshnessBlocked("run_novel_missing_or_unowned")
    required = await load_required_context(StoryLockRepository(repository.db), run)
    entities = list(required.required_entities)
    ordered = sorted(run.episodes or [], key=lambda item: int(item.get("episode_number") or 0))
    inputs_valid = all(str(episode.get("input_hash") or "") == chapter_input_hash([
        chapter for chapter in chapters if chapter.id in set(episode.get("chapter_ids") or [])
    ]) for episode in ordered)
    selected_ids = [str(value) for value in (run.run_metadata or {}).get("selected_anchor_shot_ids", [])]
    shot_refs = [{
        "shot_id": str(shot.id),
        "chapter_id": str((shot.extra_data or {}).get("chapter_id") or ""),
        "entity_refs": _canonical_refs((shot.extra_data or {}).get("entity_refs") or {}),
    } for shot in required.selected_shots]
    facts = StoryLockRepository.facts(entities)
    source = {
        "run_id": run.id,
        "selection": {
            "ordered_shot_ids": selected_ids,
            "revision": (run.run_metadata or {}).get("anchor_selection_revision"),
            "mode": (run.run_metadata or {}).get("selected_anchor_mode"),
            "shots": shot_refs,
        },
        "required_closure": {
            "closure_hash": required.closure.closure_hash,
            "required_entity_ids": list(required.closure.required_entity_ids),
            "identity_keys": [{"entity_id": fact.id, "canonical": fact.canonical_identity_key,
                               "keys": list(fact.identity_keys)} for fact in facts],
        },
        "voice_selection": _voice_snapshot(run),
        "model_bindings": _model_snapshots(run),
        "episode_inputs": [{
            "episode_number": item.get("episode_number"), "chapter_ids": list(item.get("chapter_ids") or []),
            "input_hash": item.get("input_hash"),
        } for item in ordered],
        "chapters": [{
            "id": item.id, "number": item.chapter_number, "title": item.title,
            "content_sha256": hashlib.sha256(str(item.content or "").encode()).hexdigest(),
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        } for item in chapters],
        "entities": [{
            "id": item.id, "version": item.version, "type": item.entity_type,
            "name": item.canonical_name or item.name, "chapter_id": item.chapter_id,
            "attributes": item.attributes, "evidence": item.evidence,
        } for item in sorted(entities, key=lambda entity: (entity.entity_type, entity.id))],
        "style": resolve_novel_visual_style(novel),
    }
    return source, inputs_valid


def _canonical_refs(value: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    return {kind: sorted(
        [{"entity_id": str(item.get("entity_id") or "")} for item in (value.get(plural) or [])],
        key=lambda item: item["entity_id"],
    ) for plural, kind in (("characters", "characters"), ("scenes", "scenes"),
                           ("props", "props"), ("events", "events"))}


def _voice_snapshot(run: SeriesProductionRun) -> dict[str, Any]:
    selection = dict((run.run_metadata or {}).get("voice_selection") or {})
    keys = ("config_id", "db_model_id", "api_model_id", "provider_id", "voice_id",
            "version", "tested_at", "selection_hash")
    return {key: selection.get(key) for key in keys}


def _model_snapshots(run: SeriesProductionRun) -> dict[str, dict[str, Any]]:
    capabilities = dict((run.model_bindings or {}).get("capabilities") or {})
    keys = ("config_id", "db_model_id", "api_model_id", "provider_id", "tested_at")
    return {capability: {key: dict(capabilities.get(capability) or {}).get(key) for key in keys}
            for capability in ("text", "image", "tts", "video")}


def bible_snapshot_hash(bible: StoryBible) -> str:
    extra = dict(bible.extra_data or {})
    extra.pop("series_story_lock", None)
    return fingerprint({
        "id": bible.id, "title": bible.title, "style": bible.style, "worldview": bible.worldview,
        "character_rules": bible.character_rules, "scene_rules": bible.scene_rules,
        "prop_rules": bible.prop_rules, "event_timeline": bible.event_timeline,
        "negative_prompt": bible.negative_prompt, "extra_data": extra,
    })


async def inspect(
    repository: StoryLockLineageRepository, run: SeriesProductionRun, *, supersede: bool = False,
    commit_invalidation: bool = True,
) -> dict[str, Any]:
    lock = (run.run_metadata or {}).get("story_locks") or {}
    bible_id = str(lock.get("story_bible_id") or "")
    bible = await repository.bible(bible_id) if bible_id else None
    if bible is None:
        return {"ready": False, "code": "story_lock_missing"}
    if lock.get("closure_contract_version") == "required_entity_closure_v2":
        return await _inspect_v2(repository, run, bible, lock, supersede=supersede,
                                 commit_invalidation=commit_invalidation)
    try:
        source, inputs_valid = await current_story_source(repository, run)
    except (RequiredEntityBlocked, StoryLockSourceStale) as error:
        if supersede:
            from .invalidate_lineage import invalidate_lineage

            await invalidate_lineage(repository, run, reason="story_lock_stale", commit=commit_invalidation)
        return {"ready": False, "code": "story_lock_stale", "inputs_valid": False,
                "story_blocker_code": error.code}
    source_hash, snapshot_hash = fingerprint(source), bible_snapshot_hash(bible)
    embedded_hash = ((bible.extra_data or {}).get("series_story_lock") or {}).get("source_hash")
    ready = bool(inputs_valid and lock.get("source_hash") == source_hash
                 and lock.get("bible_snapshot_hash") == snapshot_hash and embedded_hash == source_hash)
    if ready:
        return {"ready": True, "source_hash": source_hash, "bible_snapshot_hash": snapshot_hash}
    if supersede:
        from .invalidate_lineage import invalidate_lineage

        await invalidate_lineage(repository, run, reason="story_lock_stale", commit=commit_invalidation)
    return {"ready": False, "code": "story_lock_stale", "inputs_valid": inputs_valid,
            "current_source_hash": source_hash, "current_bible_snapshot_hash": snapshot_hash}


async def _inspect_v2(
    repository: StoryLockLineageRepository, run: SeriesProductionRun, bible: StoryBible,
    lock: dict[str, Any], *, supersede: bool, commit_invalidation: bool,
) -> dict[str, Any]:
    from .closure_v2_request import ENTITY_EXTRACTION_CONTRACT_VERSION, build_closure_v2_request
    from .closure_versioning import preview_v2_lock
    from ..domain.scoped_reference import canonical_json_sha256

    embedded = dict((bible.extra_data or {}).get("series_story_lock") or {})
    if any(source.get("entity_extraction_contract_version") != ENTITY_EXTRACTION_CONTRACT_VERSION
           for source in (lock, embedded)):
        if supersede:
            from .invalidate_lineage import invalidate_lineage
            await invalidate_lineage(repository, run, reason="story_lock_stale",
                                     commit=commit_invalidation)
        return {"ready": False, "code": "story_lock_stale", "inputs_valid": False,
                "story_blocker_code": "entity_extraction_contract_stale",
                "unresolved_entity_ids": []}

    unresolved_ids: list[str] = []
    try:
        run_chapter_ids(run)
        request = await build_closure_v2_request(
            repository.db, run.id, expected_run_version=run.version, user_id=run.user_id)
        preview = preview_v2_lock(request)
        persisted_fingerprint = canonical_json_sha256({
            "closure_contract_version": "required_entity_closure_v2",
            "source_hash": preview["source_hash"], "closure_hash": preview["closure_hash"],
            "snapshot_hash": preview["snapshot_hash"], "subjects": request["subjects"],
            "evidence_edges": request["evidence_edges"],
            "entity_extraction_contract_version": request["entity_extraction_contract_version"],
            "candidate_counts": request["candidate_counts"]})
        expected = {"closure_contract_version": "required_entity_closure_v2",
            "entity_extraction_contract_version": request["entity_extraction_contract_version"],
            "request_fingerprint": persisted_fingerprint,
            "source_hash": preview["source_hash"], "closure_hash": preview["closure_hash"],
            "snapshot_hash": preview["snapshot_hash"], "subjects": request["subjects"],
            "evidence_edges": request["evidence_edges"]}
        required_lifecycle = list((request.get("drift_factors") or {}).get("required_entity_lifecycle") or [])
        unresolved_ids = [str(entity_id) for entity_id, status in required_lifecycle if status != "approved"]
        selected = await StoryLockRepository(repository.db).selected_shots(run)
        lineage = {"story_bible_id": bible.id,
            "closure_contract_version": "required_entity_closure_v2",
            "source_hash": preview["source_hash"], "closure_hash": preview["closure_hash"],
            "snapshot_hash": preview["snapshot_hash"],
            "evidence_edge_count": len(request["evidence_edges"])}
        shots_current = all((shot.extra_data or {}).get("story_lock_lineage") == lineage
                            for shot in selected)
        episodes_current = all(item.get("story_bible_id") == bible.id
            and item.get("closure_contract_version") == "required_entity_closure_v2"
            and item.get("contract_version") == preview["snapshot_hash"] for item in run.episodes or [])
        bible_current = (
            str(bible.style or "") == str((request.get("drift_factors") or {}).get("visual_style") or "")
            and all(getattr(bible, field) in (None, "", {}, []) for field in (
                "worldview", "character_rules", "scene_rules", "prop_rules",
                "event_timeline", "negative_prompt"))
        )
        ready = all(lock.get(key) == value and embedded.get(key) == value
                    for key, value in expected.items()) and shots_current and episodes_current and bible_current
    except (KeyError, RequiredEntityBlocked, StoryLockSourceStale, ValueError):
        ready = False
    if ready:
        return {"ready": True, "source_hash": preview["source_hash"],
                "closure_hash": preview["closure_hash"], "snapshot_hash": preview["snapshot_hash"]}
    if supersede:
        from .invalidate_lineage import invalidate_lineage
        await invalidate_lineage(repository, run, reason="story_lock_stale",
                                 commit=commit_invalidation)
    return {"ready": False, "code": "story_lock_stale", "inputs_valid": False,
            "story_blocker_code": "production_entities_unapproved" if unresolved_ids else None,
            "unresolved_entity_ids": unresolved_ids}
