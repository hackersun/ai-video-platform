"""Transaction-neutral production persistence around the closure-v2 adapter."""

from __future__ import annotations

from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models import Shot, StoryEntity
from app.models.series_production_run import SeriesProductionRun
from app.services.story_entity_lifecycle import APPROVED, get_entity_review_status

from ..repositories.closure_versioning_async import AsyncClosureVersioningAdapter
from .closure_versioning import preview_v2_lock


async def persist_production_closure_v2(
    db: AsyncSession, run_id: str, request: Mapping[str, Any], *, expected_run_version: int,
    fail_at: str | None = None, enrich_shots: bool = True,
) -> dict[str, Any]:
    """Persist v2 and dependent shot lineage inside the caller's transaction."""
    if not db.in_transaction():
        raise RuntimeError("top-level Story Lock transaction is required")
    result = await AsyncClosureVersioningAdapter(db).apply_in_transaction(
        run_id, request, expected_run_version=expected_run_version, fail_at=fail_at,
    )
    preview = preview_v2_lock(request)
    shot_ids = sorted({str(item["reference"]["shot_id"]) for item in request["scoped_inputs"]}) if enrich_shots else []
    shots = list((await db.scalars(select(Shot).where(Shot.id.in_(shot_ids)).with_for_update())).all())
    if enrich_shots and len(shots) != len(shot_ids):
        raise ValueError("dependent scoped shot is missing")
    lineage = {"story_bible_id":result["story_bible_id"],
        "closure_contract_version":"required_entity_closure_v2",
        "source_hash":result["source_hash"],"closure_hash":result["closure_hash"],
        "snapshot_hash":result["snapshot_hash"],"evidence_edge_count":len(request["evidence_edges"])}
    for shot in shots:
        extra = dict(shot.extra_data or {})
        if extra.get("story_lock_lineage") != lineage:
            shot.extra_data = {**extra,"story_lock_lineage":lineage}
            flag_modified(shot,"extra_data")
    run = await db.get(SeriesProductionRun,run_id)
    if run is None:
        raise ValueError("persisted v2 run disappeared")
    episodes=[]
    for episode in run.episodes or []:
        item=dict(episode); ids=set((item.get("canonical_ids") or {}).get("shot_ids") or [])
        if ids.intersection(shot_ids): item["story_lock_lineage"]=lineage
        episodes.append(item)
    run.episodes=episodes; flag_modified(run,"episodes")
    version=int(((run.run_metadata or {}).get("story_locks") or {}).get("version") or 0)
    required_ids = [item["canonical_entity_id"] for item in request["subjects"]]
    entities = list((await db.scalars(select(StoryEntity).where(
        StoryEntity.id.in_(required_ids), StoryEntity.user_id == run.user_id,
        StoryEntity.novel_id == run.novel_id,
    ))).all())
    approved = [item for item in entities if get_entity_review_status(item) == APPROVED]
    unresolved = [item for item in entities if get_entity_review_status(item) != APPROVED]
    automatic_reasons = {"deterministic_verified_required_fact", "rule_based_explicit_dialogue_v1"}
    auto = sum(((item.attributes or {}).get("approval_record") or {}).get("reason")
               in automatic_reasons for item in approved)
    return {**result,"status":"locked",
        "entity_extraction_contract_version": request.get("entity_extraction_contract_version"),
        "candidate_counts":preview["candidate_counts"],
        "unrelated_candidate_count":preview["unrelated_candidate_count"],
        "auto_approved_count":auto,"manual_approved_count":len(approved)-auto,
        "unresolved_count":len(unresolved),
        "version":version,
        "required_entity_ids":required_ids,
        "unresolved_entity_ids":sorted(item.id for item in unresolved),
        "subjects":request["subjects"],"evidence_edges":request["evidence_edges"]}
