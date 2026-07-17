"""Seed and persisted context metadata rules."""

from typing import Optional

from app.features.video_generation.application.consistency_package import (
    derive_stable_seed,
    extract_shot_generation_context,
)
from app.features.video_generation.schemas import VideoGenerateRequest


def resolve_video_seed(
    request: VideoGenerateRequest, lineage: dict, consistency_metadata: dict,
) -> Optional[int]:
    if request.seed is not None:
        return request.seed
    if consistency_metadata.get("seed") is not None:
        return consistency_metadata["seed"]
    if not request.use_consistency_context:
        return None
    return derive_stable_seed([
        consistency_metadata.get("project_id") or lineage.get("project_id"),
        consistency_metadata.get("story_bible_id"), lineage.get("novel_id"),
        lineage.get("chapter_id"), lineage.get("script_id"), lineage.get("storyboard_id"), request.model,
    ])


def build_video_context_metadata(
    lineage: dict,
    consistency_metadata: dict,
    seed: Optional[int],
    shot_context_override: Optional[dict] = None,
) -> dict:
    shot_context = shot_context_override or extract_shot_generation_context(lineage.get("shot"))
    consistency = dict(consistency_metadata or {})
    if seed is not None:
        consistency["seed"] = seed
    if consistency.get("series_seed") is not None:
        consistency.setdefault("style_seed", consistency["series_seed"])
    return {
        **shot_context, "seed": seed, "series_seed": consistency.get("series_seed"),
        "novel_series_seed": consistency.get("novel_series_seed") or consistency.get("series_seed"),
        "chapter_seed": consistency.get("chapter_seed"), "storyboard_seed": consistency.get("storyboard_seed"),
        "style_lock": consistency.get("style_lock"), "continuity_lock": consistency.get("continuity_lock"),
        "previous_chapter_context": consistency.get("previous_chapter_context"),
        "current_chapter_context": consistency.get("current_chapter_context"),
        "next_chapter_constraint": consistency.get("next_chapter_constraint"),
        "previous_chapter_state": consistency.get("previous_chapter_state"),
        "chapter_state_snapshot": consistency.get("chapter_state_snapshot"),
        "state_machine_version": consistency.get("state_machine_version"),
        "state_machine_summary": consistency.get("state_machine_summary"),
        "event_timeline_tail": consistency.get("event_timeline_tail") or [],
        "entity_locks": consistency.get("entity_locks") or {},
        "character_visual_locks": consistency.get("character_visual_locks") or shot_context.get("character_refs") or [],
        "character_multiview_refs": consistency.get("character_multiview_refs") or shot_context.get("character_multiview_refs") or [],
        "reference_image_source": consistency.get("reference_image_source"),
        "invalid_entity_ref_count": consistency.get("invalid_entity_ref_count", 0), "consistency": consistency,
    }


def build_video_extra_data(request: VideoGenerateRequest, lineage: dict) -> dict:
    extra_data = {}
    if request.project_id:
        extra_data["project_id"] = request.project_id
    if request.workflow_id:
        extra_data["workflow_id"] = request.workflow_id
    for key in (
        "novel_id", "novel_title", "chapter_id", "chapter_title", "chapter_number", "script_id",
        "script_title", "storyboard_id", "storyboard_title", "shot_id", "shot_number",
    ):
        if lineage.get(key) is not None:
            extra_data[key] = lineage[key]
    return extra_data
