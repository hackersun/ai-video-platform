"""Database-authoritative AsyncSession adapter for scoped-reference backfill."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only
from sqlalchemy.orm.attributes import flag_modified

from app.models import Chapter, Shot, StoryEntity, Storyboard, Workflow
from app.models.series_production_run import SeriesProductionRun
from app.services.entity_ref_normalizer import ENTITY_REF_KEYS, normalize_entity_refs

from ..application.backfill_scoped_refs import (
    IMMUTABLE_DIAGNOSTIC, _manifest, _read_manifest, _ref_decisions,
    _validate_current, _write_manifest,
)
from ..domain.scoped_reference import (
    build_scoped_reference, canonical_json_sha256, resolve_scoped_reference,
)


def _json(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else copy.deepcopy(value)


def _entity(row: Mapping[str, Any]) -> dict[str, Any]:
    extra = _json(row["extra_data"]) or {}
    return {"id": row["id"], "user_id": row["user_id"], "novel_id": row["novel_id"],
            "chapter_id": row["chapter_id"], "entity_type": row["entity_type"],
            "name": row["name"], "canonical_name": row["canonical_name"],
            "evidence_contract": copy.deepcopy(extra.get("evidence_contract") or {}),
            "row_version": int(row["version"] or 0), "extra_data": extra}


def _episode_for_shot(episodes: list[dict[str, Any]], shot_id: str) -> dict[str, Any]:
    matches = [episode for episode in episodes if shot_id in ((episode.get("canonical_ids") or {}).get("shot_ids") or [])]
    if len(matches) != 1:
        raise ValueError("shot is missing or ambiguous in run episodes")
    return matches[0]


REF_BUCKETS = ENTITY_REF_KEYS


def _categorized_refs(extra: Mapping[str, Any]) -> list[dict[str, Any]]:
    value = extra.get("entity_refs")
    if not isinstance(value, dict) or any(key not in REF_BUCKETS for key in value):
        raise ValueError("entity_refs shape is unknown or malformed")
    refs: list[dict[str, Any]] = []
    for bucket, entity_type in REF_BUCKETS.items():
        rows = value.get(bucket, [])
        if not isinstance(rows, list):
            raise ValueError("entity_refs bucket is malformed")
        for row in rows:
            if isinstance(row, dict) and row.get("contract_version") == "chapter_evidence_ref_v1":
                refs.append(dict(row))
                continue
            normalized = normalize_entity_refs({bucket: [row]})[bucket]
            if len(normalized) != 1 or normalized[0].get("entity_type") != entity_type:
                raise ValueError("legacy entity reference is malformed")
            refs.append(normalized[0])
    if not refs:
        raise ValueError("zero recognized entity references")
    return refs


@dataclass(frozen=True)
class _AuthorityRows:
    db: AsyncSession
    run: Mapping[str, Any]
    episodes: list[dict[str, Any]]
    workflows: dict[str, Mapping[str, Any]]
    shots: list[Mapping[str, Any]]
    chapters: dict[str, Mapping[str, Any]]
    boards: dict[str, Mapping[str, Any]]


def _context(run: Mapping[str, Any], episode: Mapping[str, Any], workflow: Mapping[str, Any],
             shot: Mapping[str, Any], chapter: Mapping[str, Any]) -> dict[str, Any]:
    return {"run_id": run["id"], "series_run_id": run["id"], "shot_id": shot["id"],
            "episode_number": episode.get("episode_number"), "episode_input_hash": episode.get("input_hash"),
            "chapter_id": chapter["id"], "chapter_ids": list(episode.get("chapter_ids") or []),
            "script_id": workflow["script_id"], "storyboard_id": workflow["storyboard_id"],
            "prompt": shot["prompt"], "dialogue": shot["dialogue"],
            "visual_description": shot["visual_description"], "source_text": chapter["content"],
            "shot_text": " ".join(str(value or "") for value in
                                   (shot["prompt"], shot["dialogue"], shot["visual_description"]))}


def _owned(run: Mapping[str, Any], shot: Mapping[str, Any], chapter: dict[str, Any],
           context: dict[str, Any], source: dict[str, Any], entities: list[dict[str, Any]]) -> dict[str, Any]:
    histories, edges = [], []
    for entity in entities:
        extra = entity["extra_data"]
        histories.extend(copy.deepcopy(extra.get("canonical_histories") or []))
        edges.extend(copy.deepcopy(extra.get("merge_edges") or []))
    return {"user_id": run["user_id"], "novel_id": run["novel_id"], "run_id": run["id"],
            "shot_id": shot["id"], "chapter_id": chapter["id"], "entity_type": source["entity_type"],
            "current_context": context, "authoritative_chapters": {chapter["id"]: chapter},
            "source_rows": [source], "canonical_histories": histories, "merge_edges": edges,
            "canonical_subjects": entities}


async def _authority(db: AsyncSession, run_id: str, database_path: Path) -> dict[str, Any]:
    run = (await db.execute(select(
        SeriesProductionRun.id, SeriesProductionRun.user_id, SeriesProductionRun.novel_id,
        SeriesProductionRun.series_plan_version, SeriesProductionRun.version,
        SeriesProductionRun.run_metadata, SeriesProductionRun.episodes,
    ).where(SeriesProductionRun.id == run_id).with_for_update())).mappings().one_or_none()
    if run is None:
        raise ValueError("required authoritative run row missing")
    episodes = _json(run["episodes"]) or []
    workflow_ids = [str((item.get("canonical_ids") or {}).get("workflow_id") or "") for item in episodes]
    workflows = list((await db.execute(select(
        Workflow.id, Workflow.user_id, Workflow.novel_id, Workflow.chapter_id,
        Workflow.script_id, Workflow.storyboard_id,
    ).where(Workflow.id.in_(workflow_ids)).with_for_update())).mappings().all())
    by_workflow = {row["id"]: row for row in workflows}
    shot_ids = sorted({str(value) for item in episodes for value in
                       ((item.get("canonical_ids") or {}).get("shot_ids") or [])})
    shots = list((await db.execute(select(
        Shot.id, Shot.storyboard_id, Shot.user_id, Shot.version, Shot.prompt,
        Shot.dialogue, Shot.visual_description, Shot.extra_data,
    ).where(Shot.id.in_(shot_ids)).with_for_update())).mappings().all())
    chapter_ids = sorted({str(value) for item in episodes for value in (item.get("chapter_ids") or [])})
    chapters = list((await db.execute(select(
        Chapter.id, Chapter.novel_id, Chapter.user_id, Chapter.chapter_number,
        Chapter.content, Chapter.updated_at,
    ).where(Chapter.id.in_(chapter_ids)).with_for_update())).mappings().all())
    by_chapter = {row["id"]: row for row in chapters}
    storyboards = list((await db.execute(select(
        Storyboard.id, Storyboard.user_id, Storyboard.novel_id, Storyboard.script_id,
    ).where(Storyboard.id.in_(sorted({str(row["storyboard_id"]) for row in workflows}))).with_for_update()
    )).mappings().all())
    by_board = {row["id"]: row for row in storyboards}
    return await _assemble(_AuthorityRows(db, run, episodes, by_workflow, shots, by_chapter, by_board), database_path)


async def _assemble(rows: _AuthorityRows, database_path: Path) -> dict[str, Any]:
    db, run, episodes = rows.db, rows.run, rows.episodes
    entity_rows = (await db.execute(select(
        StoryEntity.id, StoryEntity.user_id, StoryEntity.novel_id, StoryEntity.chapter_id,
        StoryEntity.entity_type, StoryEntity.name, StoryEntity.canonical_name,
        StoryEntity.version, StoryEntity.extra_data,
    ).where(StoryEntity.novel_id == run["novel_id"], StoryEntity.user_id == run["user_id"]).with_for_update())).mappings().all()
    entities = [_entity(row) for row in entity_rows]
    by_entity = {row["id"]: row for row in entities}
    refs, shot_versions, chapter_versions = [], {}, {}
    no_op = True
    for shot in rows.shots:
        episode = _episode_for_shot(episodes, str(shot["id"]))
        workflow_id = str((episode.get("canonical_ids") or {}).get("workflow_id") or "")
        workflow, board = rows.workflows.get(workflow_id), None
        if workflow:
            board = rows.boards.get(str(workflow["storyboard_id"]))
        allowed = list(episode.get("chapter_ids") or [])
        if not workflow or not board or shot["storyboard_id"] != board["id"]:
            raise ValueError("run workflow storyboard shot chain missing")
        if any(value != run["user_id"] for value in (workflow["user_id"], board["user_id"], shot["user_id"])):
            raise ValueError("run chain owner mismatch")
        if any(value != run["novel_id"] for value in (workflow["novel_id"], board["novel_id"])):
            raise ValueError("run chain novel mismatch")
        extra = _json(shot["extra_data"]) or {}
        chapter_id = str(extra.get("chapter_id") or workflow["chapter_id"] or "")
        if chapter_id not in allowed or chapter_id not in rows.chapters:
            raise ValueError("shot chapter outside run episode")
        raw_chapter = rows.chapters[chapter_id]
        if raw_chapter["user_id"] != run["user_id"] or raw_chapter["novel_id"] != run["novel_id"]:
            raise ValueError("chapter owner or novel mismatch")
        content = str(raw_chapter["content"] or "")
        chapter = {"id": chapter_id, "chapter_number": raw_chapter["chapter_number"], "content": content,
                   "content_hash": __import__("hashlib").sha256(content.encode()).hexdigest(), "content_length": len(content),
                   "row_updated_at": str(raw_chapter["updated_at"])}
        chapter_versions[chapter_id] = canonical_json_sha256(chapter)
        context = _context(run, episode, workflow, shot, chapter)
        for legacy in _categorized_refs(extra):
            if legacy.get("contract_version") == "chapter_evidence_ref_v1":
                resolve_scoped_reference(legacy, _owned(run, shot, chapter, context,
                    by_entity.get(str(legacy.get("source_entity_id") or "")) or {}, entities))
                continue
            no_op = False
            source = by_entity.get(str(legacy.get("entity_id") or ""))
            if not source:
                raise ValueError("source entity missing")
            evidence = source.get("evidence_contract") or {}
            competitors = [row for row in entities if row["id"] != source["id"]
                and row["entity_type"] == source["entity_type"] and row["chapter_id"] == source["chapter_id"]
                and (row.get("evidence_contract") or {}) == evidence]
            if competitors:
                raise ValueError("ambiguous authoritative source evidence")
            proposed = build_scoped_reference(context=context, source=source, chapter=chapter)
            resolve_scoped_reference(proposed, _owned(run, shot, chapter, context, source, entities))
            refs.append({"shot_id": shot["id"], "chapter_id": chapter_id,
                         "entity_type": source["entity_type"], "source_entity_id": source["id"],
                         "legacy_ref": legacy, "eligible": True,
                         "reason_code": "eligible_verified_chapter_evidence", "proposed_ref": proposed})
        shot_versions[str(shot["id"])] = {"row_version": int(shot["version"] or 0)}
    metadata = _json(run["run_metadata"]) or {}
    history = {row["id"]: canonical_json_sha256({"row_version": row["row_version"],
        "records": row["extra_data"].get("canonical_histories") or []}) for row in entities}
    merges = {row["id"]: canonical_json_sha256({"row_version": row["row_version"],
        "records": row["extra_data"].get("merge_edges") or []}) for row in entities}
    return {"database_identity": canonical_json_sha256({"path": str(Path(database_path).resolve())}),
            "run_id": run["id"], "user_id": run["user_id"], "novel_id": run["novel_id"],
            "run_row_version": int(run["version"]), "series_plan_version": run["series_plan_version"],
            "source_version": metadata.get("source_version"), "lock_contract_version": metadata.get("lock_contract_version"),
            "episode_fingerprint": canonical_json_sha256(episodes),
            "chapters": chapter_versions, "shots": shot_versions, "history_fingerprints": history,
            "merge_audit_fingerprints": merges, "legacy_refs": refs,
            "no_op": no_op,
            "audit": copy.deepcopy(metadata.get("scoped_ref_backfill_audit") or []), "run_metadata": metadata}


async def write_scoped_ref_manifest(db: AsyncSession, *, run_id: str, manifest_path: Path,
                                    database_path: Path) -> dict[str, Any]:
    state = await _authority(db, run_id, database_path)
    manifest = _manifest(state)
    _write_manifest(Path(manifest_path), manifest)
    await db.rollback()
    return {"eligible": True, "eligible_ref_count": len(manifest["ref_decisions"]),
            "manifest_sha256": manifest["manifest_sha256"]}


async def apply_scoped_ref_manifest(db: AsyncSession, *, manifest_path: Path, expected_manifest_hash: str,
                                    database_path: Path, fail_at: str | None = None) -> dict[str, Any]:
    if Path(database_path).resolve() == IMMUTABLE_DIAGNOSTIC.resolve():
        raise ValueError("diagnostic original is immutable")
    manifest = _read_manifest(Path(manifest_path), expected_manifest_hash)
    async with db.begin():
        state = await _authority(db, str(manifest.get("run_id")), database_path)
        if any(row.get("manifest_sha256") == expected_manifest_hash and row.get("outcome") == "applied" for row in state["audit"]):
            return {"idempotent": True, "updated_ref_count": 0}
        _validate_current(state, manifest)
        if _ref_decisions(state) != list(manifest.get("ref_decisions") or []):
            raise ValueError("manifest decisions stale or forged")
        if state.get("no_op"):
            return {"idempotent": True, "updated_ref_count": 0}
        affected = []
        grouped: dict[str, list[Mapping[str, Any]]] = {}
        for decision in manifest["ref_decisions"]:
            grouped.setdefault(str(decision["shot_id"]), []).append(decision)
        decision_index = 0
        for shot_id, decisions in grouped.items():
            shot = await db.scalar(select(Shot).options(load_only(
                Shot.id, Shot.version, Shot.extra_data,
            )).where(Shot.id == shot_id).with_for_update())
            if shot is None or int(shot.version or 0) != state["shots"][shot_id]["row_version"]:
                raise ValueError("shot row version drift")
            extra = copy.deepcopy(shot.extra_data or {})
            categorized = copy.deepcopy(extra.get("entity_refs") or {})
            old_hash = canonical_json_sha256(categorized)
            changed_ids = []
            for decision in decisions:
                bucket = next(key for key, value in REF_BUCKETS.items() if value == decision["entity_type"])
                original = list(categorized.get(bucket) or [])
                source_id = str(decision["source_entity_id"])
                positions = [index for index, item in enumerate(original) if str(
                    (item.get("entity_id") or item.get("id") or item.get("story_entity_id")
                     or item.get("source_entity_id")) if isinstance(item, dict) else item
                ) == source_id]
                if len(positions) != 1:
                    raise ValueError("manifest target reference missing or ambiguous")
                original[positions[0]] = copy.deepcopy(decision["proposed_ref"])
                categorized[bucket] = original
                changed_ids.append(source_id)
                decision_index += 1
                if fail_at == "after_first_ref" and decision_index == 1:
                    raise RuntimeError("injected failure after_first_ref")
            shot.extra_data = {**extra, "entity_refs": categorized, "refs_version": "chapter_evidence_ref_v1"}
            shot.version = int(shot.version or 0) + 1
            flag_modified(shot, "extra_data")
            affected.append({"shot_id": shot_id, "old_ref_sha256": old_hash,
                "new_ref_sha256": canonical_json_sha256(categorized), "affected_entity_ids": sorted(changed_ids)})
        if fail_at == "after_last_ref": raise RuntimeError("injected failure after_last_ref")
        run = await db.scalar(select(SeriesProductionRun).options(load_only(
            SeriesProductionRun.id, SeriesProductionRun.user_id, SeriesProductionRun.version,
            SeriesProductionRun.run_metadata,
        )).where(SeriesProductionRun.id == state["run_id"]).with_for_update())
        if run is None or int(run.version) != state["run_row_version"] or run.user_id != state["user_id"]:
            raise ValueError("run row version or actor drift")
        metadata = copy.deepcopy(run.run_metadata or {})
        metadata.setdefault("scoped_ref_backfill_audit", []).append({"actor_user_id": state["user_id"],
            "timestamp_utc": datetime.now(timezone.utc).isoformat(), "affected_shots": sorted(affected, key=lambda row: row["shot_id"]),
            "manifest_sha256": expected_manifest_hash, "database_snapshot_sha256": state["database_identity"],
            "run_snapshot_sha256": manifest["preapply_fingerprint"], "outcome": "applied",
            "updated_ref_count": len(manifest["ref_decisions"]),
            "updated_shot_count": len(affected)})
        run.run_metadata = metadata
        flag_modified(run, "run_metadata")
        if fail_at in {"after_audit", "before_commit"}: raise RuntimeError(f"injected failure {fail_at}")
    return {"idempotent": False, "updated_ref_count": len(manifest["ref_decisions"])}
