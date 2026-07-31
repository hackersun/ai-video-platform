"""
工作流 API 端点 - 数据库持久化版本
"""

from app.core.time_utils import utc_now
import json
import shutil
import subprocess
from datetime import timezone
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.api_key_utils import get_user_api_key
from app.core.dev_generation import dev_audio_url, dev_synthesis_url, dev_video_url, is_dev_mode
from app.core.model_registry import get_model_reference_limits, get_task_default
from app.core.security import get_current_user_id
from app.models.llm_config import LLMConfig, LLMModel, LLMProvider
from app.models import Asset, Clip, Project, QualityEvaluation, Timeline, Track, Workflow, VideoJob, TTSJob, SynthesisJob, Shot, StoryBible, Storyboard
from app.models.series_production_run import SeriesProductionRun
from app.features.series_run_media_preflight.public import evaluate_media_preflight
from app.features.workflow_media.public import (
    WorkflowMediaBatchRequest,
    WorkflowMediaBatchResponse,
)
from app.features.workflow_media import public as workflow_media_helper
from app.api.v1.workflow_media_transport import workflow_media_result
from app.features.video_generation import public as video_kernel
from app.services.series_run_orchestrator import mark_run_episode_contracts_superseded
from app.services.live_canary_budget import (
    bind_provider_operation_for_reservation,
    settle_synchronous_provider_operation,
)
from app.models.external_api import ExternalAPIConfig, ExternalAPIProvider
from app.models.media_generation_job import MediaGenerationJob
from app.models.quality_evaluation import QUALITY_DIMENSIONS
from app.models.subtitle import SubtitleSegment, SubtitleTrack
from app.services.consistency_preflight import build_generation_context_package, preflight_failure_detail
from app.services.media_persistence import audit_media_url, local_static_path_for_url
from app.services.media_job_selection import (
    is_superseded as _is_superseded,
    job_created_key as _job_created_key,
    job_lineage_value as _lineage_value,
    job_shot_id as _job_shot_id,
    latest_non_superseded_by_shot as _latest_non_superseded_by_shot,
)
from app.services.audio_route_service import resolve_shot_audio_route
from app.services.episode_contract_service import lock_episode_contract
from app.services.production_bible import build_production_bible_summary
from app.services.production_strategy_routing import resolve_strategy_video_config_id
from app.services.publication_readiness import evaluate_publication_readiness
from app.services.quality_evaluation_service import evaluate_artifact
from app.services.reference_package_builder import bind_reference_package, build_reference_package
from app.services.repair_planner import plan_minimal_repair
from app.services.shot_quality_service import estimate_quality_repair_cost_risk
from app.services.shot_review_projection import shot_reference_review_fields
from app.services.deterministic_provider_fake import deterministic_media_provider_artifacts, deterministic_provider_fake_enabled
from app.services.dialogue_parser import parse_dialogue
from app.services.video_reference_adapter import (
    apply_seedance_contract_limits,
    build_reference_package_metadata,
    build_video_provider_content,
    enrich_prompt_parameters_with_reference_contract,
)
from app.services.visual_consistency_service import record_completed_shot_visual_consistency
router = APIRouter(tags=["工作流"])

_DIALOGUE_SYNC_DURATION_TOLERANCE_SECONDS = 0.75


def _job_ids(values) -> list[str]:
    return [str(value) for value in (values or []) if value]


def _extra(job) -> dict:
    return job.extra_data if isinstance(job.extra_data, dict) else {}


def _job_generation_preflight(job: Any) -> Optional[Dict[str, Any]]:
    preflight = _extra(job).get("generation_preflight")
    return dict(preflight) if isinstance(preflight, dict) else None


def _source_preflight_entry(source_type: str, job: Any) -> Optional[Dict[str, Any]]:
    preflight = _job_generation_preflight(job)
    if preflight is None:
        return None
    return {
        "source_type": source_type,
        "job_id": job.id,
        "task_id": getattr(job, "task_id", None),
        "preflight": preflight,
    }


def _aggregate_source_preflight(sources: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not sources:
        return None
    issues: List[Dict[str, Any]] = []
    blocking_issue_count = 0
    ready = True
    for source in sources:
        preflight = source.get("preflight") if isinstance(source, dict) else None
        if not isinstance(preflight, dict):
            continue
        if preflight.get("ready") is not True:
            ready = False
        blocking_issue_count += int(preflight.get("blocking_issue_count") or 0)
        for issue in preflight.get("issues") or []:
            if isinstance(issue, dict):
                issues.append({
                    **issue,
                    "source_type": source.get("source_type"),
                    "job_id": source.get("job_id"),
                })
    return {
        "ready": ready and blocking_issue_count == 0,
        "blocking_issue_count": blocking_issue_count,
        "issues": issues,
        "sources": sources,
    }


def _write_sequence_manifest(manifest_id: str, payload: Dict[str, Any]) -> str:
    export_dir = Path(__file__).resolve().parents[4] / "static" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = export_dir / f"{manifest_id}.json"
    artifact_path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    return f"/static/exports/{artifact_path.name}"


def _write_export_text(artifact_name: str, content: str) -> str:
    export_dir = Path(__file__).resolve().parents[4] / "static" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = export_dir / artifact_name
    artifact_path.write_text(content, encoding="utf-8")
    return f"/static/exports/{artifact_path.name}"


def _format_srt_time(seconds: float) -> str:
    total_ms = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def _latest_synthesis_job_id(workflow: Workflow) -> Optional[str]:
    ids = _job_ids(workflow.synthesis_job_ids)
    return ids[-1] if ids else None


def _clean_text(value: Any) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _job_has_ready_video(job: Any) -> bool:
    return getattr(job, "status", None) in {"succeeded", "completed"} and bool(
        getattr(job, "video_url", None) or getattr(job, "output_video_url", None)
    )


def _job_has_ready_audio(job: Any) -> bool:
    return getattr(job, "status", None) in {"succeeded", "completed"} and bool(getattr(job, "audio_url", None))


def _job_ready_for_concatenate_score(job: Any) -> int:
    return 1 if (_job_has_ready_video(job) or _job_has_ready_audio(job)) else 0


def _lineage_int(job: Any, key: str) -> Optional[int]:
    value = _lineage_value(job, key)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _workflow_job_sort_key(job: Any, shot_map: Dict[str, Shot], fallback_index: int) -> tuple[int, int, int]:
    shot_id = _job_shot_id(job)
    shot = shot_map.get(shot_id) if shot_id else None
    shot_number = getattr(shot, "shot_number", None) if shot else _lineage_int(job, "shot_number")
    if shot_number is not None:
        return (0, int(shot_number), fallback_index)
    return (1, fallback_index, fallback_index)


def _dedupe_latest_per_shot(jobs: List[Any]) -> List[Any]:
    selected: Dict[str, Any] = {}
    passthrough: List[Any] = []
    for job in jobs:
        shot_id = _job_shot_id(job)
        if not shot_id:
            passthrough.append(job)
            continue
        current = selected.get(shot_id)
        if current is None:
            selected[shot_id] = job
            continue
        current_score = (
            0 if _is_superseded(current) else 1,
            _job_ready_for_concatenate_score(current),
            _job_created_key(current),
        )
        next_score = (
            0 if _is_superseded(job) else 1,
            _job_ready_for_concatenate_score(job),
            _job_created_key(job),
        )
        if next_score >= current_score:
            selected[shot_id] = job

    ordered: List[Any] = []
    seen_shots: set[str] = set()
    for job in jobs:
        shot_id = _job_shot_id(job)
        if not shot_id:
            ordered.append(job)
            continue
        if shot_id in seen_shots:
            continue
        seen_shots.add(shot_id)
        ordered.append(selected[shot_id])
    return ordered


async def _workflow_shots_for_request(
    db: AsyncSession,
    workflow: Workflow,
    user_id: str,
    shot_ids: Optional[List[str]] = None,
) -> List[Shot]:
    query = select(Shot).where(Shot.user_id == user_id)
    if not workflow.storyboard_id:
        return []
    query = query.where(Shot.storyboard_id == workflow.storyboard_id)
    if shot_ids:
        query = query.where(Shot.id.in_(shot_ids))
    result = await db.execute(query.order_by(Shot.shot_number))
    return list(result.scalars().all())


async def _video_jobs_for_workflow_shots(
    db: AsyncSession,
    workflow_id: str,
    user_id: str,
    shot_ids: List[str],
) -> List[VideoJob]:
    if not shot_ids:
        return []
    result = await db.execute(
        select(VideoJob).where(
            VideoJob.workflow_id == workflow_id,
            VideoJob.user_id == user_id,
        ).order_by(desc(VideoJob.created_at))
    )
    return [job for job in result.scalars().all() if _job_shot_id(job) in shot_ids]


async def _tts_jobs_for_workflow_shots(
    db: AsyncSession,
    workflow_id: str,
    user_id: str,
    shot_ids: List[str],
) -> List[TTSJob]:
    if not shot_ids:
        return []
    result = await db.execute(
        select(TTSJob).where(
            TTSJob.workflow_id == workflow_id,
            TTSJob.user_id == user_id,
            TTSJob.shot_id.in_(shot_ids),
        ).order_by(desc(TTSJob.created_at))
    )
    return list(result.scalars().all())


async def _media_jobs_for_workflow_shots(
    db: AsyncSession,
    workflow_id: str,
    user_id: str,
    shot_ids: List[str],
) -> List[MediaGenerationJob]:
    if not shot_ids:
        return []
    result = await db.execute(
        select(MediaGenerationJob).where(
            MediaGenerationJob.workflow_id == workflow_id,
            MediaGenerationJob.user_id == user_id,
            MediaGenerationJob.shot_id.in_(shot_ids),
            MediaGenerationJob.is_active == True,
        ).order_by(desc(MediaGenerationJob.created_at))
    )
    return list(result.scalars().all())


async def _concatenate_job_ids_for_workflow_shots(
    db: AsyncSession,
    *,
    workflow_id: str,
    user_id: str,
    shots: List[Shot],
) -> Dict[str, List[str]]:
    shot_ids = [shot.id for shot in shots]
    video_jobs = await _video_jobs_for_workflow_shots(db, workflow_id, user_id, shot_ids)
    media_jobs = await _media_jobs_for_workflow_shots(db, workflow_id, user_id, shot_ids)
    tts_jobs = await _tts_jobs_for_workflow_shots(db, workflow_id, user_id, shot_ids)
    latest_video_by_shot = _latest_non_superseded_by_shot(video_jobs)
    latest_media_by_shot = _latest_non_superseded_by_shot(media_jobs)
    latest_tts_by_shot = _latest_non_superseded_by_shot(tts_jobs)

    concatenate_video_job_ids: List[str] = []
    concatenate_media_job_ids: List[str] = []
    concatenate_tts_job_ids: List[str] = []
    for shot in shots:
        candidates = [
            job
            for job in (latest_video_by_shot.get(shot.id), latest_media_by_shot.get(shot.id))
            if job is not None and _job_has_ready_video(job)
        ]
        if candidates:
            latest = max(candidates, key=_job_created_key)
            if isinstance(latest, MediaGenerationJob):
                concatenate_media_job_ids.append(latest.id)
            else:
                concatenate_video_job_ids.append(latest.id)

        tts_job = latest_tts_by_shot.get(shot.id)
        if tts_job is not None and _job_has_ready_audio(tts_job):
            concatenate_tts_job_ids.append(tts_job.id)

    return {
        "video_job_ids": concatenate_video_job_ids,
        "media_job_ids": concatenate_media_job_ids,
        "tts_job_ids": concatenate_tts_job_ids,
    }


def _reference_package_mode(extra: Dict[str, Any]) -> Optional[Any]:
    if "reference_package_mode" in extra:
        return extra.get("reference_package_mode")
    package = extra.get("reference_package")
    if isinstance(package, dict):
        return package.get("mode")
    return None


def _shot_quality_report(shot_extra: Dict[str, Any]) -> Dict[str, Any]:
    report = shot_extra.get("quality_report")
    return dict(report) if isinstance(report, dict) else {}


def _visual_consistency_evidence(
    shot_quality: Dict[str, Any],
    video_extra: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    for source in (shot_quality.get("visual_consistency"), video_extra.get("visual_consistency")):
        if isinstance(source, dict):
            return dict(source)
    return None


def _visual_consistency_score(item: Dict[str, Any]) -> Optional[float]:
    score = item.get("visual_consistency_score")
    if score is None:
        evidence = item.get("evidence")
        if isinstance(evidence, dict):
            visual = evidence.get("visual_consistency")
            if isinstance(visual, dict):
                score = visual.get("score")
    try:
        return float(score) if score is not None else None
    except (TypeError, ValueError):
        return None


def _shot_review_sort_key(item: Dict[str, Any]) -> tuple[int, float, int]:
    score = _visual_consistency_score(item)
    if score is None:
        return (1, 0.0, int(item.get("shot_number") or 0))
    return (0, score, int(item.get("shot_number") or 0))


def _shot_review_item(
    shot: Shot,
    *,
    latest_video: Optional[Any],
    latest_tts: Optional[TTSJob],
    regeneration_count: int,
) -> Dict[str, Any]:
    video_extra = _extra(latest_video) if latest_video else {}
    shot_extra = _extra(shot)
    quality_report = _shot_quality_report(shot_extra)
    visual_consistency = _visual_consistency_evidence(quality_report, video_extra)
    visual_consistency_score = (
        quality_report.get("visual_consistency_score")
        if quality_report.get("visual_consistency_score") is not None
        else (visual_consistency or {}).get("score")
    )
    subtitle_text = (
        (latest_tts.text if latest_tts else None)
        or shot_extra.get("subtitle_text")
        or shot.dialogue
        or ""
    )
    return {
        "shot_id": shot.id,
        "shot_number": shot.shot_number,
        "latest_video_job_id": latest_video.id if latest_video else None,
        "latest_tts_job_id": latest_tts.id if latest_tts else None,
        "video_url": getattr(latest_video, "video_url", None) if latest_video else shot.video_url,
        "status": getattr(latest_video, "status", None) if latest_video else (shot.video_status or "pending"),
        "duration": getattr(latest_video, "duration", None) if latest_video else shot.duration,
        "subtitle_text": subtitle_text,
        **shot_reference_review_fields(shot, latest_video=latest_video, video_extra=video_extra, fallback_character_names=workflow_media_helper.shot_character_names(shot)),
        "evidence": {
            "strategy_routing": video_extra.get("strategy_routing"),
            "reference_package_mode": _reference_package_mode(video_extra),
            "reference_package": video_extra.get("reference_package"),
            "generation_preflight": video_extra.get("generation_preflight"),
            "visual_consistency": visual_consistency,
        },
        "quality_report": quality_report,
        "visual_consistency_score": visual_consistency_score,
        "regeneration_count": regeneration_count,
    }


_QUALITY_BLOCKER_CODES = {
    "main_character_identity_mismatch",
    "future_episode_leakage",
    "wrong_prop_owner",
    "wrong_speaker",
    "missing_subtitle",
    "corrupt_mp4",
    "semantic_score_below_blocking",
}

_AUTO_QUALITY_REPAIR_CODES = {
    "wrong_voice", "wrong_speaker", "wrong_prop_state", "wrong_prop_owner",
    "main_character_identity_mismatch", "future_episode_leakage", "corrupt_mp4",
    "missing_subtitle", "subtitle_timing",
}


def _mp4_integrity_evidence(video_url: Optional[str], video_extra: Dict[str, Any]) -> tuple[bool, Dict[str, Any]]:
    recorded = video_extra.get("media_integrity") if isinstance(video_extra.get("media_integrity"), dict) else {}
    if recorded.get("ffprobe_valid") is True and recorded.get("exists") is True:
        return True, {"source": "persisted_media_integrity", **recorded}
    audit = audit_media_url(video_url)
    path = local_static_path_for_url(video_url)
    if not audit.get("exists") or path is None:
        return False, {"source": "media_persistence_audit", **audit}
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return False, {"source": "ffprobe", "exists": True, "ffprobe_available": False}
    probe = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_type", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    valid = probe.returncode == 0 and '"codec_type": "video"' in probe.stdout
    return valid, {"source": "ffprobe", "exists": True, "returncode": probe.returncode, "ffprobe_valid": valid}


def _quality_expected_state(shot: Shot) -> Dict[str, Any]:
    extra = _extra(shot)
    configured = extra.get("quality_expected") if isinstance(extra.get("quality_expected"), dict) else {}
    production_context = extra.get("production_context") if isinstance(extra.get("production_context"), dict) else {}
    refs = shot.character_refs if isinstance(shot.character_refs, list) else []
    first_ref = refs[0] if refs else None
    inferred_character = (
        first_ref.get("entity_id") or first_ref.get("character_id")
        if isinstance(first_ref, dict)
        else first_ref if isinstance(first_ref, str) else None
    )
    return {
        "main_character_id": configured.get("main_character_id") or inferred_character,
        "episode_index": configured.get("episode_index") or production_context.get("episode_index"),
        "prop_owners": configured.get("prop_owners") or production_context.get("prop_owners") or {},
        "speaker_id": configured.get("speaker_id") or configured.get("voice_character_id") or inferred_character,
        "subtitle_required": bool(configured.get("subtitle_required", bool(shot.dialogue))),
        "mp4_required": bool(configured.get("mp4_required", True)),
        "background": configured.get("background"),
        "ambient_audio": configured.get("ambient_audio"),
    }


async def _derive_quality_evidence(
    db: AsyncSession,
    *,
    workflow: Workflow,
    shot: Shot,
    user_id: str,
) -> Dict[str, Any]:
    video_jobs = await _video_jobs_for_workflow_shots(db, workflow.id, user_id, [shot.id])
    tts_jobs = await _tts_jobs_for_workflow_shots(db, workflow.id, user_id, [shot.id])
    latest_video = _latest_non_superseded_by_shot(video_jobs).get(shot.id)
    latest_tts = _latest_non_superseded_by_shot(tts_jobs).get(shot.id)
    latest_media = await db.scalar(
        select(MediaGenerationJob)
        .where(
            MediaGenerationJob.user_id == user_id,
            MediaGenerationJob.workflow_id == workflow.id,
            MediaGenerationJob.shot_id == shot.id,
            MediaGenerationJob.is_active.is_(True),
        )
        .order_by(desc(MediaGenerationJob.created_at))
        .limit(1)
    )
    video_extra = _extra(latest_video) if latest_video else {}
    if not latest_video and latest_media:
        video_extra = _extra(latest_media)
    tts_extra = _extra(latest_tts) if latest_tts else {}
    observed_config = video_extra.get("quality_observed") if isinstance(video_extra.get("quality_observed"), dict) else {}
    tts_observed = tts_extra.get("quality_observed") if isinstance(tts_extra.get("quality_observed"), dict) else {}
    subtitle_track = await db.scalar(
        select(SubtitleTrack)
        .where(
            SubtitleTrack.user_id == user_id,
            SubtitleTrack.workflow_id == workflow.id,
            SubtitleTrack.shot_id == shot.id,
            SubtitleTrack.is_active.is_(True),
        )
        .order_by(desc(SubtitleTrack.created_at))
        .limit(1)
    )
    video_url = (
        getattr(latest_video, "video_url", None) if latest_video
        else getattr(latest_media, "output_video_url", None) if latest_media
        else shot.video_url
    )
    video_status = (
        getattr(latest_video, "status", None) if latest_video
        else getattr(latest_media, "status", None) if latest_media
        else shot.video_status
    )
    mp4_valid, mp4_evidence = _mp4_integrity_evidence(video_url, video_extra)
    expected = _quality_expected_state(shot)
    observed = {
        "main_character_id": observed_config.get("main_character_id") or video_extra.get("observed_main_character_id"),
        "source_episode_indices": observed_config.get("source_episode_indices") or video_extra.get("source_episode_indices") or [],
        "future_episode_leakage": observed_config.get("future_episode_leakage") is True,
        "prop_owners": observed_config.get("prop_owners") or video_extra.get("observed_prop_owners") or {},
        "speaker_id": tts_observed.get("speaker_id") or getattr(latest_tts, "character_id", None) or tts_extra.get("speaker_id"),
        "subtitle_present": subtitle_track is not None,
        "mp4_valid": mp4_valid,
        "background": observed_config.get("background"),
        "ambient_audio": tts_observed.get("ambient_audio"),
    }
    artifact = latest_tts if expected.get("speaker_id") and latest_tts else (latest_video or latest_media)
    return {
        "artifact_id": artifact.id if artifact else shot.id,
        "artifact_type": (
            "tts_job" if artifact is latest_tts and artifact is not None
            else "video_job" if artifact is latest_video and artifact is not None
            else "media_generation_job" if artifact is latest_media and artifact is not None
            else "shot"
        ),
        "provider_id": (
            getattr(artifact, "api_provider", None) or getattr(artifact, "provider_id", None)
            if artifact else None
        ),
        "model_id": getattr(artifact, "model_id", None) if artifact else None,
        "expected_state": expected,
        "observed_state": observed,
        "evidence": {
            "source": "server_deterministic",
            "workflow_id": workflow.id,
            "storyboard_id": workflow.storyboard_id,
            "shot_id": shot.id,
            "video_job_id": latest_video.id if latest_video else None,
            "media_job_id": latest_media.id if latest_media else None,
            "tts_job_id": latest_tts.id if latest_tts else None,
            "subtitle_track_id": subtitle_track.id if subtitle_track else None,
            "mp4_integrity": mp4_evidence,
        },
    }


async def _evaluate_and_persist_server_quality(
    db: AsyncSession,
    *,
    workflow: Workflow,
    shot: Shot,
    user_id: str,
    dev_semantic_fixture: Optional[Dict[str, Any]] = None,
    repair_id: Optional[str] = None,
    resolves_evaluation_ids: Optional[List[str]] = None,
) -> Any:
    derived = await _derive_quality_evidence(db, workflow=workflow, shot=shot, user_id=user_id)
    semantic_scores: Dict[str, Any] = {}
    evidence = dict(derived["evidence"])
    if dev_semantic_fixture is not None:
        if not is_dev_mode():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="语义测试夹具仅允许 DEV_MODE")
        semantic_scores = dev_semantic_fixture.get("scores") if isinstance(dev_semantic_fixture.get("scores"), dict) else {}
        evidence["semantic_audit"] = {
            "source": "trusted_dev_fixture",
            "requested_by": user_id,
            "fixture_id": dev_semantic_fixture.get("fixture_id"),
            "recorded_at": utc_now().isoformat(),
        }
    generation_id = str(uuid4())
    evidence["evaluation_generation_id"] = generation_id
    if repair_id:
        evidence["repair_id"] = repair_id
        evidence["resolves_evaluation_ids"] = list(dict.fromkeys(resolves_evaluation_ids or []))
        evidence["repair_lineage"] = {
            "source": "server_quality_repair",
            "workflow_id": workflow.id,
            "shot_id": shot.id,
        }
    result = evaluate_artifact(
        artifact_id=derived["artifact_id"],
        artifact_type=derived["artifact_type"],
        workflow_id=workflow.id,
        shot_id=shot.id,
        provider_id=derived["provider_id"],
        model_id=derived["model_id"],
        expected_state=derived["expected_state"],
        observed_state=derived["observed_state"],
        evidence=evidence,
        semantic_scores=semantic_scores,
    )
    db.add_all(list(result.dimension_results))
    await db.flush()
    return result


def _quality_issue_payload(issue: Any) -> Dict[str, Any]:
    return {
        "code": issue.code,
        "dimension": issue.dimension,
        "severity": issue.severity,
        "blocking": issue.blocking,
        "message": issue.message,
        "evidence": issue.evidence,
        "repair_action": issue.repair_action,
    }


async def _latest_quality_rows(
    db: AsyncSession,
    *,
    workflow_id: str,
    shot_id: Optional[str] = None,
) -> List[QualityEvaluation]:
    query = select(QualityEvaluation).where(QualityEvaluation.workflow_id == workflow_id)
    if shot_id:
        query = query.where(QualityEvaluation.shot_id == shot_id)
    result = await db.execute(
        query.order_by(desc(QualityEvaluation.evaluated_at), desc(QualityEvaluation.created_at))
    )
    rows = list(result.scalars().all())
    current_generation_by_shot: Dict[str, str] = {}
    for row in rows:
        evidence = row.evidence if isinstance(row.evidence, dict) else {}
        generation_id = str(evidence.get("evaluation_generation_id") or row.evaluated_at or row.created_at)
        current_generation_by_shot.setdefault(str(row.shot_id or ""), generation_id)
    current: List[QualityEvaluation] = []
    resolved_ids: set[str] = set()
    for row in rows:
        evidence = row.evidence if isinstance(row.evidence, dict) else {}
        lineage = evidence.get("repair_lineage") if isinstance(evidence.get("repair_lineage"), dict) else {}
        if (
            evidence.get("repair_id")
            and lineage.get("source") == "server_quality_repair"
            and str(lineage.get("workflow_id")) == str(row.workflow_id)
            and str(lineage.get("shot_id")) == str(row.shot_id)
        ):
            resolved_ids.update(str(value) for value in evidence.get("resolves_evaluation_ids") or [] if value)
    for row in rows:
        evidence = row.evidence if isinstance(row.evidence, dict) else {}
        generation_id = str(evidence.get("evaluation_generation_id") or row.evaluated_at or row.created_at)
        if generation_id != current_generation_by_shot.get(str(row.shot_id or "")):
            continue
        current.append(row)
    current_ids = {row.id for row in current}
    unresolved_prior_blockers = [
        row for row in rows
        if row.blocking and row.id not in current_ids and row.id not in resolved_ids
    ]
    return [*current, *unresolved_prior_blockers]


def _quality_gate_summary(rows: List[QualityEvaluation]) -> Optional[Dict[str, Any]]:
    if not rows:
        return None
    order = {dimension: index for index, dimension in enumerate(QUALITY_DIMENSIONS)}
    ordered = sorted(rows, key=lambda row: order.get(str(row.dimension), len(order)))
    blockers: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    blocker_row: Optional[QualityEvaluation] = None
    blocker_code: Optional[str] = None
    dimensions: List[Dict[str, Any]] = []
    for row in ordered:
        evidence = row.evidence if isinstance(row.evidence, dict) else {}
        issue_codes = [str(code) for code in evidence.get("issue_codes") or [] if code]
        row_blocker_codes = issue_codes if row.blocking else []
        if row.blocking and not row_blocker_codes:
            row_blocker_codes = ["unknown_blocking_quality_issue"]
        row_warning_codes = issue_codes if not row.blocking else []
        for code in row_blocker_codes:
            blockers.append({"code": code, "dimension": row.dimension, "artifact_id": row.artifact_id})
            if blocker_row is None:
                blocker_row = row
                blocker_code = code
        for code in row_warning_codes:
            warnings.append({"code": code, "dimension": row.dimension, "artifact_id": row.artifact_id})
        dimensions.append({
            "id": row.id,
            "dimension": row.dimension,
            "expected_state": row.expected_state or {},
            "observed_state": row.observed_state or {},
            "evidence": evidence,
            "score": row.score,
            "confidence": row.confidence,
            "severity": row.severity,
            "blocking": bool(row.blocking),
            "threshold_version": row.threshold_version,
            "evaluator_version": row.evaluator_version,
            "repair_action": row.repair_action,
            "artifact_id": row.artifact_id,
            "evaluated_at": row.evaluated_at.isoformat() if row.evaluated_at else None,
        })

    suggested_repair = None
    if blocker_row is not None and blocker_code is not None:
        unavailable = blocker_code not in _AUTO_QUALITY_REPAIR_CODES
        plan = plan_minimal_repair(
            issue=blocker_code,
            affected_artifact_ids=(blocker_row.artifact_id,),
            candidate_artifact_ids=(blocker_row.artifact_id,),
        )
        actions = list(plan.actions)
        suggested_repair = {
            "issue_code": blocker_code,
            "actions": actions,
            "affected_artifact_ids": list(plan.affected_artifact_ids),
            "cost_risk": estimate_quality_repair_cost_risk(actions),
            "available": not unavailable,
            "navigation_url": f"/studio/shot-review?workflow_id={blocker_row.workflow_id}&shot_id={blocker_row.shot_id}" if unavailable else None,
        }
    return {
        "ready": not blockers,
        "overall_readiness": "blocked" if blockers else "warning" if warnings else "ready",
        "dimensions": dimensions,
        "blockers": blockers,
        "warnings": warnings,
        "suggested_repair": suggested_repair,
    }


async def _workflow_quality_blocking_issues(
    db: AsyncSession,
    workflow_id: str,
) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    for row in await _latest_quality_rows(db, workflow_id=workflow_id):
        if not row.blocking:
            continue
        evidence = row.evidence if isinstance(row.evidence, dict) else {}
        issue_codes = [str(code) for code in evidence.get("issue_codes") or [] if code]
        if not issue_codes:
            issue_codes = ["unknown_blocking_quality_issue"]
        for code in issue_codes:
            issues.append({
                "code": f"quality_gate_{code}",
                "quality_issue_code": code,
                "severity": "error",
                "message": f"质量门禁未通过：{code}",
                "blocking": True,
                "shot_id": row.shot_id,
                "artifact_id": row.artifact_id,
                "dimension": row.dimension,
                "repair_action": row.repair_action,
            })
    return issues


async def _mark_superseded_for_shots(
    db: AsyncSession,
    *,
    workflow_id: str,
    user_id: str,
    shot_ids: List[str],
) -> None:
    video_jobs = await _video_jobs_for_workflow_shots(db, workflow_id, user_id, shot_ids)
    tts_jobs = await _tts_jobs_for_workflow_shots(db, workflow_id, user_id, shot_ids)
    for job in [*video_jobs, *tts_jobs]:
        extra = dict(_extra(job))
        extra["superseded_by_regeneration"] = True
        extra["superseded_at"] = utc_now().isoformat()
        job.extra_data = extra


def _assert_lineage_matches_workflow(workflow: Workflow, job: Any) -> None:
    labels = {
        "novel_id": "小说",
        "chapter_id": "章节",
        "script_id": "剧本",
        "storyboard_id": "分镜",
    }
    for key, label in labels.items():
        workflow_value = getattr(workflow, key, None)
        job_value = _lineage_value(job, key)
        if workflow_value and job_value and workflow_value != job_value:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"媒体任务 {job.id} 的{label}链路与工作流不匹配",
            )


def _external_base_url(config: ExternalAPIConfig, provider: ExternalAPIProvider) -> str:
    return (config.custom_base_url or provider.base_url or "").rstrip("/")


async def _get_cloud_render_config(
    db: AsyncSession,
    user_id: str,
    config_id: Optional[str],
) -> tuple[Optional[ExternalAPIConfig], Optional[ExternalAPIProvider]]:
    query = (
        select(ExternalAPIConfig, ExternalAPIProvider)
        .join(ExternalAPIProvider, ExternalAPIConfig.provider_id == ExternalAPIProvider.id)
        .where(
            ExternalAPIConfig.user_id == user_id,
            ExternalAPIConfig.is_active == True,
            ExternalAPIProvider.name == "ffmpeg_cloud",
        )
    )
    if config_id:
        query = query.where(ExternalAPIConfig.id == config_id)
    else:
        query = query.order_by(ExternalAPIConfig.is_default.desc(), ExternalAPIConfig.created_at.desc()).limit(1)

    result = await db.execute(query)
    row = result.first()
    if config_id and not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FFmpeg 云渲染配置不存在")
    return (row[0], row[1]) if row else (None, None)


def _is_tts_model(model: LLMModel) -> bool:
    model_type = (model.model_type or "").lower()
    capabilities = [str(item).lower() for item in (model.capabilities or [])]
    return model_type in {"tts", "audio", "speech"} or any(
        item in {"text-to-speech", "speech", "tts"} or "speech" in item or "tts" in item
        for item in capabilities
    )


def _dialogue_segments_for_sync(shot: Shot, subtitle_text: str) -> List[Dict[str, Any]]:
    if not subtitle_text:
        return []

    fallback_speaker = workflow_media_helper.primary_tts_character_name(shot, subtitle_text)
    segments: List[Dict[str, Any]] = []
    for segment in parse_dialogue(subtitle_text):
        text = str(segment.get("text") or "").strip()
        if not text:
            continue
        speaker = workflow_media_helper.clean_character_label(segment.get("character")) or fallback_speaker
        segments.append({"speaker": speaker, "text": text})
    if not segments:
        segments.append({"speaker": fallback_speaker, "text": subtitle_text.strip()})
    return segments


def _dialogue_sync_contract_from_jobs(video_job: Any, tts_job: Optional[TTSJob]) -> Optional[Dict[str, Any]]:
    video_contract = _extra(video_job).get("dialogue_sync_contract")
    tts_contract = _extra(tts_job).get("dialogue_sync_contract") if tts_job else None
    if not isinstance(video_contract, dict) and not isinstance(tts_contract, dict):
        return None

    merged: Dict[str, Any] = {}
    if isinstance(video_contract, dict):
        merged.update(video_contract)
    if isinstance(tts_contract, dict):
        merged.update(tts_contract)
        if not merged.get("subtitle_text") and isinstance(video_contract, dict):
            merged["subtitle_text"] = video_contract.get("subtitle_text")
    return merged


def _dialogue_sync_texts(
    *,
    contract: Optional[Dict[str, Any]],
    tts_job: Optional[TTSJob],
    video_job: Any,
    shot: Optional[Shot],
) -> Dict[str, str]:
    media_extra = _extra(video_job)
    subtitle_text = ""
    spoken_text = ""
    if isinstance(contract, dict):
        subtitle_text = str(contract.get("subtitle_text") or "").strip()
        spoken_text = str(contract.get("spoken_text") or "").strip()
    if not spoken_text and tts_job:
        spoken_text = str(tts_job.text or "").strip()
    if not subtitle_text:
        if contract:
            subtitle_text = (
                str(media_extra.get("subtitle_text") or "").strip()
                or (str(shot.dialogue or "").strip() if shot else "")
                or spoken_text
            )
        else:
            subtitle_text = (
                spoken_text
                or str(media_extra.get("subtitle_text") or "").strip()
                or (str(shot.dialogue or "").strip() if shot else "")
            )
    return {
        "subtitle_text": subtitle_text,
        "spoken_text": spoken_text or subtitle_text,
    }


def _dialogue_sync_diagnostics(
    *,
    segment_index: int,
    video_duration: float,
    audio_duration: float,
    contract: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    mismatch = round(float(audio_duration or 0.0) - float(video_duration or 0.0), 3)
    issues: List[Dict[str, Any]] = []
    if contract and audio_duration and mismatch > _DIALOGUE_SYNC_DURATION_TOLERANCE_SECONDS:
        issues.append({
            "code": "dialogue_audio_timing_mismatch",
            "severity": "warning",
            "message": (
                f"第 {segment_index} 段配音时长 {round(audio_duration, 3)}s 与视频镜头 "
                f"{round(video_duration, 3)}s 偏差 {abs(mismatch)}s，将裁剪到镜头时长。"
            ),
            "segment_index": segment_index,
            "blocking": False,
            "direction": "longer",
            "resolved_by": "trim_to_segment",
        })
    elif contract and audio_duration and mismatch < -_DIALOGUE_SYNC_DURATION_TOLERANCE_SECONDS:
        issues.append({
            "code": "dialogue_audio_tail_padding",
            "severity": "warning",
            "message": (
                f"第 {segment_index} 段配音短于视频镜头 {abs(mismatch)}s，将以尾部静音对齐。"
            ),
            "segment_index": segment_index,
            "blocking": False,
            "direction": "shorter",
            "resolved_by": "pad_silence",
        })
    return {
        "status": "needs_review" if issues else "ok",
        "contract_present": bool(contract),
        "video_duration_seconds": round(float(video_duration or 0.0), 3),
        "audio_duration_seconds": round(float(audio_duration or 0.0), 3) if audio_duration else None,
        "duration_mismatch_seconds": mismatch,
        "tolerance_seconds": _DIALOGUE_SYNC_DURATION_TOLERANCE_SECONDS,
        "issues": issues,
    }


def _duration_delta(left: Optional[float], right: Optional[float]) -> Optional[float]:
    if left is None or right is None:
        return None
    return round(abs(float(left) - float(right)), 3)


def _subtitle_duration_for_segment(segment: Dict[str, Any]) -> Optional[float]:
    subtitle = segment.get("subtitle") if isinstance(segment.get("subtitle"), dict) else {}
    if not subtitle.get("enabled") or not subtitle.get("text"):
        return None
    start = float(subtitle.get("start_seconds") or segment.get("start_seconds") or 0.0)
    end = float(subtitle.get("end_seconds") or start)
    return round(max(0.0, end - start), 3)


def _build_media_sync_health(segments: List[Dict[str, Any]]) -> Dict[str, Any]:
    health_segments: List[Dict[str, Any]] = []
    summary = {"green": 0, "yellow": 0, "red": 0, "segment_count": len(segments)}
    warning_threshold = 0.15
    blocking_threshold = _DIALOGUE_SYNC_DURATION_TOLERANCE_SECONDS

    for fallback_index, segment in enumerate(segments, start=1):
        video = segment.get("video") if isinstance(segment.get("video"), dict) else {}
        audio = segment.get("audio") if isinstance(segment.get("audio"), dict) else {}
        subtitle = segment.get("subtitle") if isinstance(segment.get("subtitle"), dict) else {}
        sync_diagnostics = segment.get("sync_diagnostics") if isinstance(segment.get("sync_diagnostics"), dict) else {}
        sync_issues = [issue for issue in (sync_diagnostics.get("issues") or []) if isinstance(issue, dict)]

        video_duration = float(video.get("render_duration_seconds") or segment.get("duration_seconds") or video.get("duration_seconds") or 0.0)
        audio_source_duration = (
            float(audio.get("duration_seconds"))
            if audio.get("duration_seconds") is not None
            else None
        )
        audio_duration = (
            float(audio.get("render_duration_seconds"))
            if audio.get("render_duration_seconds") is not None
            else audio_source_duration
        )
        subtitle_duration = _subtitle_duration_for_segment(segment)
        audio_video_delta = _duration_delta(audio_duration, video_duration)
        subtitle_video_delta = _duration_delta(subtitle_duration, video_duration)
        audio_subtitle_delta = _duration_delta(audio_duration, subtitle_duration)
        max_delta = max(
            [
                value
                for value in (audio_video_delta, subtitle_video_delta, audio_subtitle_delta)
                if value is not None
            ],
            default=0.0,
        )

        issues: List[Dict[str, Any]] = []
        status_issues: List[Dict[str, Any]] = []
        if not audio.get("url"):
            issue = {"code": "missing_audio", "message": "缺少配音音频"}
            issues.append(issue)
            status_issues.append(issue)
        if not subtitle.get("enabled") or not subtitle.get("text"):
            issue = {"code": "missing_subtitle", "message": "缺少字幕文本"}
            issues.append(issue)
            status_issues.append(issue)
        issues.extend(sync_issues)
        status_issues.extend(issue for issue in sync_issues if not issue.get("resolved_by"))

        has_blocking_issue = any(issue.get("blocking") for issue in status_issues)
        if has_blocking_issue or max_delta > blocking_threshold:
            status_value = "blocking"
            color = "red"
            summary["red"] += 1
        elif status_issues or max_delta > warning_threshold:
            status_value = "warning"
            color = "yellow"
            summary["yellow"] += 1
        else:
            status_value = "ok"
            color = "green"
            summary["green"] += 1

        health_segments.append({
            "index": segment.get("index") or fallback_index,
            "shot_id": (segment.get("lineage") or {}).get("shot_id"),
            "shot_number": (segment.get("lineage") or {}).get("shot_number"),
            "status": status_value,
            "color": color,
            "video_duration_seconds": round(video_duration, 3),
            "audio_duration_seconds": round(audio_duration, 3) if audio_duration is not None else None,
            "audio_source_duration_seconds": round(audio_source_duration, 3) if audio_source_duration is not None else None,
            "audio_duration_strategy": audio.get("duration_strategy"),
            "subtitle_duration_seconds": subtitle_duration,
            "audio_video_delta_seconds": audio_video_delta,
            "subtitle_video_delta_seconds": subtitle_video_delta,
            "audio_subtitle_delta_seconds": audio_subtitle_delta,
            "issues": issues,
        })

    overall = "ok"
    if summary["red"]:
        overall = "blocking"
    elif summary["yellow"]:
        overall = "warning"
    return {
        "status": overall,
        "summary": summary,
        "thresholds": {
            "green_max_delta_seconds": warning_threshold,
            "yellow_max_delta_seconds": blocking_threshold,
        },
        "segments": health_segments,
    }


def _shot_audio_text(shot: Shot) -> str:
    subtitle_text = workflow_media_helper.shot_subtitle_text(shot)
    if subtitle_text:
        return subtitle_text
    fallback = (
        shot.visual_description
        or shot.prompt
        or shot.sfx_cue
        or shot.music_cue
        or f"镜头{shot.shot_number}剧情继续推进。"
    )
    fallback = str(fallback).strip()
    if len(fallback) > 80:
        fallback = f"{fallback[:80].rstrip()}..."
    return f"（旁白）{fallback}"


async def _submit_cloud_render_job(
    *,
    config: ExternalAPIConfig,
    provider: ExternalAPIProvider,
    render_id: str,
    payload: Dict[str, Any],
) -> tuple[Optional[str], str, Dict[str, Any]]:
    extra = config.extra_config or {}
    base_url = _external_base_url(config, provider)
    submit_path = extra.get("submit_path") or "/render"
    if not base_url or not submit_path:
        return None, "adapter_ready", {"message": "缺少 base_url 或 submit_path，云渲染包已生成但尚未提交"}

    headers: Dict[str, str] = {"Content-Type": "application/json"}
    api_key = config.get_api_key_decrypted()
    if api_key and provider.auth_type != "none":
        headers[provider.auth_header or "Authorization"] = f"Bearer {api_key}" if provider.auth_type == "bearer" else api_key

    request_body = {
        "render_id": render_id,
        "workflow_id": payload.get("workflow_id"),
        "synthesis_job_id": payload.get("synthesis_job_id"),
        "manifest_url": payload.get("render_manifest_url"),
        "timeline_url": payload.get("timeline_url"),
        "srt_url": payload.get("srt_url"),
        "burn_subtitles": payload.get("burn_subtitles"),
        "quality_profile": payload.get("quality_profile"),
        "segments": payload.get("segments") or [],
        "metadata": payload,
    }

    async with httpx.AsyncClient(timeout=config.timeout or 60) as client:
        response = await client.post(f"{base_url}{submit_path}", headers=headers, json=request_body)
    if response.status_code >= 400:
        return None, "failed", {"status_code": response.status_code, "body": response.text[:1000]}

    data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    task_id = str(data.get("task_id") or data.get("id") or data.get("render_task_id") or "")
    output_url = data.get("output_url") or data.get("result_url") or data.get("video_url")
    adapter_status = "rendered" if output_url else "cloud_pending"
    return task_id or None, adapter_status, {"response": data, "output_url": output_url}


async def _get_workflow_for_user(db: AsyncSession, workflow_id: str, user_id: str) -> Workflow:
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user_id)
    )
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工作流不存在")
    return workflow


async def _get_synthesis_for_render(
    db: AsyncSession,
    workflow: Workflow,
    user_id: str,
    synthesis_job_id: Optional[str] = None,
) -> Optional[SynthesisJob]:
    target_id = synthesis_job_id or _latest_synthesis_job_id(workflow)
    if not target_id:
        return None
    result = await db.execute(
        select(SynthesisJob).where(
            SynthesisJob.id == target_id,
            SynthesisJob.user_id == user_id,
            SynthesisJob.workflow_id == workflow.id,
            SynthesisJob.is_active == True,
        )
    )
    return result.scalar_one_or_none()


def _segment_list(synthesis_job: Optional[SynthesisJob]) -> List[Dict[str, Any]]:
    if synthesis_job is None:
        return []
    extra = _extra(synthesis_job)
    segments = extra.get("segments")
    return segments if isinstance(segments, list) else []


def _ranges_overlap(start_a: float, end_a: float, start_b: float, end_b: float) -> bool:
    return max(start_a, start_b) < min(end_a, end_b)


async def _load_render_timeline(
    db: AsyncSession,
    *,
    workflow: Workflow,
    synthesis_job: SynthesisJob,
    user_id: str,
    timeline_id: Optional[str] = None,
) -> Optional[Timeline]:
    target_id = timeline_id or _extra(synthesis_job).get("timeline_id") or (workflow.metadata_ or {}).get("latest_timeline_id")
    if not target_id:
        return None
    result = await db.execute(
        select(Timeline).where(
            Timeline.id == target_id,
            Timeline.user_id == user_id,
            Timeline.is_active == True,
        )
    )
    return result.scalar_one_or_none()


async def _build_segments_from_timeline(db: AsyncSession, timeline: Timeline, user_id: str) -> List[Dict[str, Any]]:
    track_result = await db.execute(select(Track).where(Track.timeline_id == timeline.id).order_by(Track.track_index))
    tracks = track_result.scalars().all()
    tracks_by_id = {track.id: track for track in tracks}

    clip_result = await db.execute(
        select(Clip).where(
            Clip.timeline_id == timeline.id,
            Clip.user_id == user_id,
            Clip.is_active == True,
        ).order_by(Clip.position, Clip.sort_order)
    )
    clips = clip_result.scalars().all()

    video_clips = [
        clip for clip in clips
        if tracks_by_id.get(clip.track_id)
        and tracks_by_id[clip.track_id].track_type == "video"
        and not tracks_by_id[clip.track_id].is_hidden
    ]
    audio_clips = [
        clip for clip in clips
        if tracks_by_id.get(clip.track_id)
        and tracks_by_id[clip.track_id].track_type == "audio"
        and not tracks_by_id[clip.track_id].is_hidden
        and not tracks_by_id[clip.track_id].is_muted
    ]
    subtitle_clips = [
        clip for clip in clips
        if tracks_by_id.get(clip.track_id)
        and tracks_by_id[clip.track_id].track_type == "subtitle"
        and not tracks_by_id[clip.track_id].is_hidden
        and (clip.text_content or "").strip()
    ]

    segments: List[Dict[str, Any]] = []
    for index, clip in enumerate(video_clips, start=1):
        start = float(clip.position or 0)
        duration = max(0.1, float(clip.duration or clip.source_duration or 0.1))
        end = start + duration
        overlapping_audio = [
            audio for audio in audio_clips
            if _ranges_overlap(start, end, float(audio.position or 0), float(audio.position or 0) + max(0.1, float(audio.duration or 0.1)))
        ]
        overlapping_subtitles = [
            subtitle for subtitle in subtitle_clips
            if _ranges_overlap(start, end, float(subtitle.position or 0), float(subtitle.position or 0) + max(0.1, float(subtitle.duration or 0.1)))
        ]
        audio_clip = overlapping_audio[0] if overlapping_audio else None
        subtitles = [
            {
                "clip_id": subtitle.id,
                "text": (subtitle.text_content or "").strip(),
                "start_seconds": float(subtitle.position or 0),
                "end_seconds": float(subtitle.position or 0) + max(0.1, float(subtitle.duration or 0.1)),
                "duration_seconds": max(0.1, float(subtitle.duration or 0.1)),
                "font_size": subtitle.font_size,
                "font_color": subtitle.font_color,
            }
            for subtitle in overlapping_subtitles
        ]

        segments.append({
            "index": index,
            "start_seconds": start,
            "end_seconds": end,
            "duration_seconds": duration,
            "lineage": {
                "timeline_id": timeline.id,
                "video_clip_id": clip.id,
                "shot_id": clip.source_id if clip.source_type in {"shot", "video_job", "direct_audio_video"} else None,
            },
            "video": {
                "source_type": clip.source_type,
                "job_id": clip.source_id,
                "clip_id": clip.id,
                "url": clip.source_url,
                "cover_url": clip.source_thumbnail,
                "duration_seconds": duration,
                "name": clip.name,
            },
            "audio": {
                "source_type": audio_clip.source_type if audio_clip else "audio",
                "job_id": audio_clip.source_id if audio_clip else None,
                "clip_id": audio_clip.id if audio_clip else None,
                "url": audio_clip.source_url if audio_clip else None,
                "duration_seconds": float(audio_clip.duration or duration) if audio_clip else duration,
                "text": audio_clip.text_content if audio_clip else None,
            },
            "subtitle": {
                "enabled": bool(subtitles),
                "text": "\n".join(item["text"] for item in subtitles),
                "start_seconds": subtitles[0]["start_seconds"] if subtitles else start,
                "end_seconds": subtitles[-1]["end_seconds"] if subtitles else end,
            },
            "subtitles": subtitles,
            "transition": clip.transitions or {},
            "source": "editable_timeline",
        })
    return segments


def _segments_duration(segments: List[Dict[str, Any]]) -> float:
    return max(
        [float(segment.get("end_seconds") or 0) for segment in segments] +
        [float(segment.get("start_seconds") or 0) + float(segment.get("duration_seconds") or 0) for segment in segments] +
        [0.0]
    )


async def _resolve_render_source(
    db: AsyncSession,
    *,
    workflow: Workflow,
    synthesis_job: Optional[SynthesisJob],
    user_id: str,
    use_editable_timeline: bool,
    timeline_id: Optional[str] = None,
) -> Dict[str, Any]:
    if synthesis_job is None:
        return {"source": "missing", "segments": [], "timeline": None, "source_key": "missing"}

    if use_editable_timeline:
        timeline = await _load_render_timeline(
            db,
            workflow=workflow,
            synthesis_job=synthesis_job,
            user_id=user_id,
            timeline_id=timeline_id,
        )
        if timeline:
            segments = await _build_segments_from_timeline(db, timeline, user_id)
            updated_at = timeline.updated_at.isoformat() if timeline.updated_at else ""
            return {
                "source": "editable_timeline",
                "segments": segments,
                "timeline": timeline,
                "timeline_id": timeline.id,
                "timeline_updated_at": updated_at,
                "source_key": f"editable_timeline:{timeline.id}:{updated_at}:{len(segments)}",
                "duration_seconds": _segments_duration(segments),
            }

    segments = _segment_list(synthesis_job)
    extra = _extra(synthesis_job)
    manifest_url = extra.get("manifest_url")
    return {
        "source": "manifest",
        "segments": segments,
        "timeline": None,
        "manifest_url": manifest_url,
        "source_key": f"manifest:{manifest_url or synthesis_job.id}:{len(segments)}",
        "duration_seconds": extra.get("duration_seconds") or synthesis_job.duration_seconds or _segments_duration(segments),
    }


async def _ensure_workflow_project(
    db: AsyncSession,
    workflow: Workflow,
    synthesis_job: SynthesisJob,
    user_id: str,
) -> Project:
    project_id = synthesis_job.project_id or _extra(synthesis_job).get("project_id") or (workflow.metadata_ or {}).get("project_id")
    if project_id:
        result = await db.execute(select(Project).where(Project.id == project_id, Project.user_id == user_id))
        project = result.scalar_one_or_none()
        if project:
            return project

    project = Project(
        id=str(uuid4()),
        user_id=user_id,
        name=f"{workflow.title} 时间线项目",
        description="由工作流连续成片自动创建，用于承载可编辑 Timeline",
        status="active",
        extra_data={"source": "workflow_timeline_sync", "workflow_id": workflow.id},
    )
    db.add(project)
    workflow.metadata_ = {
        **(workflow.metadata_ or {}),
        "project_id": project.id,
    }
    synthesis_job.project_id = project.id
    extra = _extra(synthesis_job)
    extra["project_id"] = project.id
    synthesis_job.extra_data = extra
    return project


async def _ensure_workflow_timeline(
    db: AsyncSession,
    *,
    workflow: Workflow,
    synthesis_job: SynthesisJob,
    project: Project,
    user_id: str,
    request: Any,
) -> Timeline:
    metadata = workflow.metadata_ or {}
    timeline_id = metadata.get("latest_timeline_id") or _extra(synthesis_job).get("timeline_id")
    timeline = None
    if timeline_id:
        result = await db.execute(select(Timeline).where(Timeline.id == timeline_id, Timeline.user_id == user_id))
        timeline = result.scalar_one_or_none()

    if timeline is None:
        timeline = Timeline(
            id=str(uuid4()),
            user_id=user_id,
            project_id=project.id,
            name=request.name or f"{workflow.title} 可编辑时间线",
            description="由 workflow 成片清单自动生成，可继续编辑视频、音频和字幕轨",
            fps=24,
            aspect_ratio="16:9",
            video_track_count=1,
            audio_track_count=1,
            subtitle_track_count=1,
            status="editing",
            is_default=True,
            extra_data={"workflow_id": workflow.id, "synthesis_job_id": synthesis_job.id},
        )
        db.add(timeline)
        project.timeline_count = (project.timeline_count or 0) + 1
    else:
        timeline.name = request.name or timeline.name
        timeline.status = "editing"
        timeline.extra_data = {
            **(timeline.extra_data or {}),
            "workflow_id": workflow.id,
            "synthesis_job_id": synthesis_job.id,
        }

    timeline.preview_url = synthesis_job.output_url or timeline.preview_url
    return timeline


async def _ensure_named_track(
    db: AsyncSession,
    *,
    timeline_id: str,
    track_type: str,
    track_index: int,
    name: str,
) -> Track:
    result = await db.execute(
        select(Track).where(
            Track.timeline_id == timeline_id,
            Track.track_type == track_type,
            Track.track_index == track_index,
        )
    )
    track = result.scalar_one_or_none()
    if track:
        track.name = name
        return track
    track = Track(
        id=str(uuid4()),
        timeline_id=timeline_id,
        track_type=track_type,
        track_index=track_index,
        name=name,
    )
    db.add(track)
    return track


def _segment_clip_name(segment: Dict[str, Any]) -> str:
    lineage = segment.get("lineage") or {}
    shot_number = lineage.get("shot_number") or segment.get("index")
    return f"镜头 {shot_number}"


def _clip_source_id(data: Dict[str, Any], fallback: Optional[str] = None) -> Optional[str]:
    value = data.get("job_id") or data.get("media_job_id") or data.get("video_job_id") or fallback
    return str(value) if value else None


def _build_timeline_clips(
    *,
    timeline: Timeline,
    user_id: str,
    tracks: Dict[str, Track],
    segments: List[Dict[str, Any]],
) -> List[Clip]:
    clips: List[Clip] = []
    for index, segment in enumerate(segments):
        start = float(segment.get("start_seconds") or 0)
        duration = float(segment.get("duration_seconds") or 0) or 0.1
        video = segment.get("video") or {}
        audio = segment.get("audio") or {}
        subtitle = segment.get("subtitle") or {}
        lineage = segment.get("lineage") or {}

        clips.append(
            Clip(
                id=str(uuid4()),
                user_id=user_id,
                timeline_id=timeline.id,
                track_id=tracks["video"].id,
                source_type=video.get("source_type") or "video_job",
                source_id=_clip_source_id(video, lineage.get("shot_id")),
                source_url=video.get("url"),
                source_thumbnail=video.get("cover_url"),
                source_duration=float(video.get("duration_seconds") or duration),
                position=start,
                duration=duration,
                out_point=duration,
                name=_segment_clip_name(segment),
                sort_order=index,
                transitions=segment.get("transition") or {},
                keyframes=(segment.get("shot_controls") or {}).get("keyframes"),
            )
        )

        if audio.get("url"):
            clips.append(
                Clip(
                    id=str(uuid4()),
                    user_id=user_id,
                    timeline_id=timeline.id,
                    track_id=tracks["audio"].id,
                    source_type=audio.get("source_type") or "audio",
                    source_id=_clip_source_id(audio),
                    source_url=audio.get("url"),
                    source_duration=float(audio.get("duration_seconds") or duration),
                    position=start,
                    duration=duration,
                    out_point=duration,
                    name=f"{_segment_clip_name(segment)} 对白",
                    sort_order=index,
                    text_content=audio.get("text"),
                    volume=1.0,
                )
            )

        if subtitle.get("enabled") and subtitle.get("text"):
            subtitle_start = float(subtitle.get("start_seconds") or start)
            clips.append(
                Clip(
                    id=str(uuid4()),
                    user_id=user_id,
                    timeline_id=timeline.id,
                    track_id=tracks["subtitle"].id,
                    source_type="subtitle",
                    source_id=str(lineage.get("shot_id")) if lineage.get("shot_id") else None,
                    source_duration=duration,
                    position=subtitle_start,
                    duration=max(
                        0.1,
                        float(subtitle.get("end_seconds") or start + duration) - subtitle_start,
                    ),
                    out_point=duration,
                    name=f"{_segment_clip_name(segment)} 字幕",
                    sort_order=index,
                    text_content=subtitle.get("text"),
                    font_size=28,
                    font_color="#FFFFFF",
                )
            )
    return clips


async def _build_render_preflight_payload(
    db: AsyncSession,
    workflow: Workflow,
    synthesis_job: Optional[SynthesisJob],
    user_id: str,
    use_editable_timeline: bool = True,
    timeline_id: Optional[str] = None,
) -> Dict[str, Any]:
    issues: List[Dict[str, Any]] = []
    extra = _extra(synthesis_job) if synthesis_job else {}
    render_source = await _resolve_render_source(
        db,
        workflow=workflow,
        synthesis_job=synthesis_job,
        user_id=user_id,
        use_editable_timeline=use_editable_timeline,
        timeline_id=timeline_id,
    )
    segments = render_source["segments"]
    manifest_url = extra.get("manifest_url") if synthesis_job else None
    source = render_source["source"]

    if synthesis_job is None:
        issues.append({
            "code": "missing_synthesis_job",
            "severity": "error",
            "message": "还没有连续成片任务，请先生成多镜头成片清单",
            "blocking": True,
        })
    elif source == "manifest" and not manifest_url:
        issues.append({
            "code": "missing_manifest",
            "severity": "error",
            "message": "合成任务缺少成片清单 manifest",
            "blocking": True,
        })
    if synthesis_job is not None and source == "editable_timeline" and not segments:
        issues.append({
            "code": "empty_timeline",
            "severity": "error",
            "message": "可编辑 Timeline 中没有可渲染的视频片段",
            "blocking": True,
        })
    elif synthesis_job is not None and not segments:
        issues.append({
            "code": "missing_segments",
            "severity": "error",
            "message": "成片清单中没有镜头段落",
            "blocking": True,
        })

    for index, segment in enumerate(segments, start=1):
        video = segment.get("video") or {}
        audio = segment.get("audio") or {}
        subtitle = segment.get("subtitle") or {}
        if not video.get("url"):
            issues.append({
                "code": "missing_video_url",
                "severity": "error",
                "message": f"第 {index} 段缺少视频 URL",
                "segment_index": index,
                "blocking": True,
            })
        if not audio.get("url"):
            issues.append({
                "code": "missing_audio_url",
                "severity": "warning",
                "message": f"第 {index} 段缺少音频，将按静音轨处理",
                "segment_index": index,
                "blocking": False,
            })
        if subtitle.get("enabled") and not subtitle.get("text"):
            issues.append({
                "code": "empty_subtitle",
                "severity": "warning",
                "message": f"第 {index} 段字幕为空",
                "segment_index": index,
                "blocking": False,
            })
        sync_diagnostics = segment.get("sync_diagnostics") if isinstance(segment, dict) else None
        if isinstance(sync_diagnostics, dict):
            for sync_issue in sync_diagnostics.get("issues") or []:
                if isinstance(sync_issue, dict):
                    if sync_issue.get("resolved_by"):
                        continue
                    issues.append({
                        **sync_issue,
                        "segment_index": sync_issue.get("segment_index") or index,
                    })

    quality_gate_issues = await _workflow_quality_blocking_issues(db, workflow.id)
    issues.extend(quality_gate_issues)

    blocking_count = len([issue for issue in issues if issue.get("blocking")])
    publication_readiness = evaluate_publication_readiness(
        synthesis_job.output_url if synthesis_job else None,
        extra,
    )
    media_sync_health = _build_media_sync_health(segments)
    publication_blockers = [
        *(publication_readiness["publication_blockers"] or []),
        *quality_gate_issues,
    ]
    return {
        "workflow_id": workflow.id,
        "synthesis_job_id": synthesis_job.id if synthesis_job else None,
        "ready": blocking_count == 0,
        "blocking_issue_count": blocking_count,
        "issue_count": len(issues),
        "issues": issues,
        "manifest_url": manifest_url,
        "segment_count": len(segments),
        "duration_seconds": render_source.get("duration_seconds") or extra.get("duration_seconds") or (synthesis_job.duration_seconds if synthesis_job else 0),
        "render_status": extra.get("render_status") if synthesis_job else "missing_synthesis",
        "render_artifacts": extra.get("render_artifacts") or {},
        "render_source": source,
        "timeline_id": render_source.get("timeline_id"),
        "timeline_updated_at": render_source.get("timeline_updated_at"),
        "is_publishable": publication_readiness["is_publishable"] and not quality_gate_issues,
        "output_kind": publication_readiness["output_kind"],
        "publication_blockers": publication_blockers,
        "media_sync_health": media_sync_health,
    }


def _build_srt(segments: List[Dict[str, Any]]) -> str:
    blocks = []
    subtitle_index = 1
    for segment in segments:
        subtitle_items = segment.get("subtitles")
        if isinstance(subtitle_items, list) and subtitle_items:
            for subtitle in subtitle_items:
                text = (subtitle.get("text") or "").strip()
                if not text:
                    continue
                start_seconds = float(subtitle.get("start_seconds") or segment.get("start_seconds") or 0)
                end_seconds = float(subtitle.get("end_seconds") or start_seconds)
                blocks.append(
                    f"{subtitle_index}\n{_format_srt_time(start_seconds)} --> {_format_srt_time(end_seconds)}\n{text}\n"
                )
                subtitle_index += 1
            continue

        subtitle = segment.get("subtitle") or {}
        text = (subtitle.get("text") or "").strip()
        if not text:
            continue
        start_seconds = float(subtitle.get("start_seconds") or segment.get("start_seconds") or 0)
        end_seconds = float(subtitle.get("end_seconds") or segment.get("end_seconds") or start_seconds)
        blocks.append(
            f"{subtitle_index}\n{_format_srt_time(start_seconds)} --> {_format_srt_time(end_seconds)}\n{text}\n"
        )
        subtitle_index += 1
    return "\n".join(blocks)


def _build_timeline_edl(workflow: Workflow, synthesis_job: SynthesisJob, segments: List[Dict[str, Any]]) -> Dict[str, Any]:
    subtitle_clips = []
    for segment in segments:
        subtitle_items = segment.get("subtitles")
        if isinstance(subtitle_items, list) and subtitle_items:
            for subtitle in subtitle_items:
                subtitle_clips.append({
                    "segment_index": segment.get("index"),
                    "clip_id": subtitle.get("clip_id"),
                    "text_content": subtitle.get("text"),
                    "position": subtitle.get("start_seconds"),
                    "duration": round(
                        float(subtitle.get("end_seconds") or 0) - float(subtitle.get("start_seconds") or 0),
                        3,
                    ),
                })
            continue
        subtitle = segment.get("subtitle") or {}
        if subtitle.get("text"):
            subtitle_clips.append({
                "segment_index": segment.get("index"),
                "text_content": subtitle.get("text"),
                "position": subtitle.get("start_seconds"),
                "duration": round(
                    float(subtitle.get("end_seconds") or segment.get("end_seconds") or 0)
                    - float(subtitle.get("start_seconds") or segment.get("start_seconds") or 0),
                    3,
                ),
            })

    return {
        "type": "timeline_edl",
        "version": "1.0",
        "workflow_id": workflow.id,
        "synthesis_job_id": synthesis_job.id,
        "tracks": [
            {
                "name": "V1 主视频",
                "track_type": "video",
                "clips": [
                    {
                        "segment_index": segment.get("index"),
                        "source_type": (segment.get("video") or {}).get("source_type") or "video_job",
                        "source_id": (segment.get("video") or {}).get("job_id") or (segment.get("video") or {}).get("clip_id"),
                        "source_url": (segment.get("video") or {}).get("url"),
                        "position": segment.get("start_seconds"),
                        "duration": segment.get("duration_seconds"),
                        "transition": segment.get("transition") or {},
                    }
                    for segment in segments
                ],
            },
            {
                "name": "A1 对白",
                "track_type": "audio",
                "clips": [
                    {
                        "segment_index": segment.get("index"),
                        "source_type": (segment.get("audio") or {}).get("source_type") or "tts_job",
                        "source_id": (segment.get("audio") or {}).get("job_id") or (segment.get("audio") or {}).get("clip_id"),
                        "source_url": (segment.get("audio") or {}).get("url"),
                        "position": segment.get("start_seconds"),
                        "duration": (segment.get("audio") or {}).get("duration_seconds") or segment.get("duration_seconds"),
                        "volume": 1.0 if (segment.get("audio") or {}).get("url") else 0.0,
                    }
                    for segment in segments
                ],
            },
            {
                "name": "S1 字幕",
                "track_type": "subtitle",
                "clips": subtitle_clips,
            },
        ],
        "duration_seconds": synthesis_job.duration_seconds,
        "created_at": utc_now().isoformat(),
    }


def _build_render_tracks(segments: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    video_tracks: List[Dict[str, Any]] = []
    audio_tracks: List[Dict[str, Any]] = []
    subtitle_tracks: List[Dict[str, Any]] = []
    for segment in segments:
        segment_index = segment.get("index")
        video = segment.get("video") or {}
        audio = segment.get("audio") or {}
        subtitle_items = segment.get("subtitles")
        subtitle = segment.get("subtitle") or {}
        if video.get("url"):
            video_tracks.append({"segment_index": segment_index, **video})
        if audio.get("url"):
            audio_tracks.append({"segment_index": segment_index, **audio})
        if isinstance(subtitle_items, list) and subtitle_items:
            for subtitle_item in subtitle_items:
                if isinstance(subtitle_item, dict) and subtitle_item.get("text"):
                    subtitle_tracks.append({"segment_index": segment_index, **subtitle_item})
        elif subtitle.get("text"):
            subtitle_tracks.append({"segment_index": segment_index, **subtitle})
    return {
        "video": video_tracks,
        "audio": audio_tracks,
        "subtitle": subtitle_tracks,
    }


def _build_render_html(title: str, segments: List[Dict[str, Any]], artifacts: Dict[str, str]) -> str:
    segment_rows = []
    for segment in segments:
        video = segment.get("video") or {}
        audio = segment.get("audio") or {}
        subtitle = segment.get("subtitle") or {}
        audio_link = (
            '<a href="' + escape(audio.get("url")) + '">音频</a>'
            if audio.get("url")
            else "静音"
        )
        segment_rows.append(
            "<tr>"
            f"<td>{escape(str(segment.get('index') or ''))}</td>"
            f"<td>{escape(str(segment.get('start_seconds') or 0))}s - {escape(str(segment.get('end_seconds') or 0))}s</td>"
            f"<td><a href=\"{escape(video.get('url') or '#')}\">视频</a></td>"
            f"<td>{audio_link}</td>"
            f"<td>{escape(subtitle.get('text') or '')}</td>"
            "</tr>"
        )
    artifact_links = "".join(
        f"<li><a href=\"{escape(url)}\">{escape(label)}</a></li>"
        for label, url in artifacts.items()
        if url
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>{escape(title)}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 32px; background: #0f172a; color: #e5e7eb; }}
    a {{ color: #67e8f9; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
    th, td {{ border: 1px solid rgba(255,255,255,.15); padding: 10px; text-align: left; vertical-align: top; }}
    th {{ background: rgba(255,255,255,.08); }}
    .panel {{ border: 1px solid rgba(255,255,255,.14); border-radius: 8px; padding: 16px; background: rgba(255,255,255,.06); }}
  </style>
</head>
<body>
  <h1>{escape(title)}</h1>
  <div class="panel">
    <p>本地渲染包已生成。当前输出是 DEV_MODE 可审阅预览，不代表真实转码后的媒体文件。</p>
    <ul>{artifact_links}</ul>
  </div>
  <table>
    <thead><tr><th>#</th><th>时间</th><th>视频</th><th>音频</th><th>字幕</th></tr></thead>
    <tbody>{''.join(segment_rows)}</tbody>
  </table>
</body>
</html>
"""


# ========== 请求/响应模型 ==========

class WorkflowStep(BaseModel):
    id: str
    name: int
    description: str
    required: bool


class WorkflowStepsResponse(BaseModel):
    steps: List[WorkflowStep]


class WorkflowStartRequest(BaseModel):
    title: Optional[str] = Field(None, description="工作流标题")
    novel_id: Optional[str] = Field(None, description="关联的小说ID")
    chapter_id: Optional[str] = Field(None, description="关联的章节ID")
    script_id: Optional[str] = Field(None, description="关联的剧本ID")
    storyboard_id: Optional[str] = Field(None, description="关联的分镜ID")


class WorkflowStartResponse(BaseModel):
    workflow_id: str
    title: str
    message: str


class WorkflowStatusResponse(BaseModel):
    workflow_id: str
    title: str
    status: str
    current_step: int
    completed_steps: List[int]
    novel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    script_id: Optional[str] = None
    storyboard_id: Optional[str] = None
    video_jobs: List[dict]
    tts_jobs: List[dict]
    media_jobs: List[dict] = Field(default_factory=list)
    subtitle_tracks: List[dict] = Field(default_factory=list)
    synthesis_jobs: List[dict]
    metadata: Dict[str, Any] = Field(default_factory=dict)
    production_bible_summary: Optional[Dict[str, Any]] = None


class WorkflowUpdateStepRequest(BaseModel):
    current_step: int
    completed_steps: Optional[List[int]] = None
    status: Optional[str] = None
    novel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    script_id: Optional[str] = None
    storyboard_id: Optional[str] = None
    video_job_ids: Optional[List[str]] = None
    tts_job_ids: Optional[List[str]] = None
    synthesis_job_ids: Optional[List[str]] = None


class WorkflowDetailResponse(BaseModel):
    workflow_id: str
    title: str
    status: str
    current_step: int
    completed_steps: List[int]
    novel_id: Optional[str]
    chapter_id: Optional[str]
    script_id: Optional[str]
    storyboard_id: Optional[str]
    video_job_ids: List[str]
    tts_job_ids: List[str]
    synthesis_job_ids: List[str]
    metadata: dict
    production_bible_summary: Optional[Dict[str, Any]] = None
    error_message: Optional[str]
    created_at: str
    updated_at: str


class ConcatenateRequest(BaseModel):
    video_job_ids: List[str] = Field(default_factory=list, description="视频任务ID列表")
    media_job_ids: List[str] = Field(default_factory=list, description="直生音视频媒体任务ID列表")
    tts_job_ids: Optional[List[str]] = Field(None, description="TTS任务ID列表")
    title: Optional[str] = Field(None, description="任务标题")
    api_key: Optional[str] = Field(None, description="火山引擎 API Key（可选）")
    transition_style: str = Field("cut", description="镜头转场方式")
    transition_duration_seconds: float = Field(0.3, ge=0, le=3, description="转场时长（秒）")
    include_subtitles: bool = Field(True, description="是否生成字幕轨")
    subtitle_mode: str = Field("dialogue", description="字幕来源：dialogue/tts/off")
    audio_mix_strategy: str = Field("match_by_shot", description="配音匹配策略")
    quality_profile: str = Field("preview", description="成片质量配置")


class ConcatenateResponse(BaseModel):
    job_id: str
    message: str
    output_url: Optional[str] = None
    manifest_url: Optional[str] = None
    segment_count: int = 0
    duration_seconds: float = 0.0


class RenderPreflightResponse(BaseModel):
    workflow_id: str
    synthesis_job_id: Optional[str] = None
    ready: bool
    blocking_issue_count: int
    issue_count: int
    issues: List[Dict[str, Any]]
    manifest_url: Optional[str] = None
    segment_count: int = 0
    duration_seconds: Optional[float] = None
    render_status: Optional[str] = None
    render_artifacts: Dict[str, Any] = Field(default_factory=dict)
    render_source: str = "manifest"
    timeline_id: Optional[str] = None
    timeline_updated_at: Optional[str] = None
    is_publishable: bool = False
    output_kind: str = "missing_final_video"
    publication_blockers: List[Dict[str, Any]] = Field(default_factory=list)
    media_sync_health: Dict[str, Any] = Field(default_factory=dict)


class RenderRequest(BaseModel):
    synthesis_job_id: Optional[str] = Field(None, description="指定合成任务ID，不传则使用当前工作流最新合成任务")
    force: bool = Field(False, description="是否强制重新生成本地渲染包")
    quality_profile: str = Field("review", description="渲染质量配置")
    render_backend: str = Field("local_artifact_package", description="local_artifact_package/ffmpeg_cloud/ffmpeg_local")
    external_config_id: Optional[str] = Field(None, description="FFmpeg 云渲染外部配置ID")
    burn_subtitles: bool = Field(False, description="是否要求真实渲染时烧录字幕")
    use_editable_timeline: bool = Field(True, description="存在可编辑 Timeline 时是否优先按最新 Timeline 渲染")
    timeline_id: Optional[str] = Field(None, description="指定用于渲染的 Timeline ID")


class RenderResponse(BaseModel):
    workflow_id: str
    synthesis_job_id: str
    status: str
    message: str
    render_status: Optional[str] = None
    render_backend: Optional[str] = None
    output_url: Optional[str] = None
    manifest_url: Optional[str] = None
    preview_url: Optional[str] = None
    srt_url: Optional[str] = None
    timeline_url: Optional[str] = None
    render_manifest_url: Optional[str] = None
    segment_count: int = 0
    duration_seconds: Optional[float] = None
    issues: List[Dict[str, Any]] = Field(default_factory=list)
    render_source: str = "manifest"
    timeline_id: Optional[str] = None
    is_publishable: bool = False
    output_kind: str = "missing_final_video"
    publication_blockers: List[Dict[str, Any]] = Field(default_factory=list)
    media_sync_health: Dict[str, Any] = Field(default_factory=dict)


class WorkflowTimelineSyncRequest(BaseModel):
    synthesis_job_id: Optional[str] = Field(None, description="指定合成任务ID，不传则使用当前工作流最新合成任务")
    name: Optional[str] = Field(None, description="时间线名称")
    force: bool = Field(False, description="是否清空并重建已有 workflow 时间线片段")


class WorkflowTimelineSyncResponse(BaseModel):
    workflow_id: str
    synthesis_job_id: str
    timeline_id: str
    project_id: str
    track_count: int
    clip_count: int
    duration_seconds: float
    message: str


class WorkflowShotRegenerateRequest(BaseModel):
    shot_ids: Optional[List[str]] = Field(None, description="指定重生镜头；为空时可结合 filter=failed")
    filter: Optional[str] = Field(None, description="failed/all_selected")
    character_name: Optional[str] = Field(None, description="只重生包含该角色名的镜头")
    production_strategy: Optional[str] = Field(None, description="不传则继承工作流最近一次生产策略")
    model_config_id: Optional[str] = None
    audio_model_config_id: Optional[str] = None
    audio_mode: str = "model_audio"
    native_audio: bool = False


class WorkflowShotRegenerateResponse(BaseModel):
    workflow_id: str
    regenerated_shot_ids: List[str] = Field(default_factory=list)
    created_count: int = 0
    video_job_ids: List[str] = Field(default_factory=list)
    tts_job_ids: List[str] = Field(default_factory=list)
    media_job_ids: List[str] = Field(default_factory=list)
    concatenate_video_job_ids: List[str] = Field(default_factory=list)
    concatenate_tts_job_ids: List[str] = Field(default_factory=list)
    concatenate_media_job_ids: List[str] = Field(default_factory=list)
    subtitle_track_ids: List[str] = Field(default_factory=list)
    skipped: List[Dict[str, Any]] = Field(default_factory=list)
    ready_for_concatenate: bool = True


class WorkflowShotReviewResponse(BaseModel):
    workflow_id: str
    latest_render_artifacts: Optional[Dict[str, Any]] = None
    shots: List[Dict[str, Any]] = Field(default_factory=list)


class WorkflowQualityEvaluateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shot_id: str
    dev_semantic_fixture: Optional[Dict[str, Any]] = Field(
        None,
        description="仅 DEV_MODE 测试夹具使用；不能覆盖服务端确定性证据",
    )


class WorkflowQualityRepairRequest(BaseModel):
    shot_id: str
    issue_code: str


class WorkflowVisualConsistencyRequest(BaseModel):
    shot_ids: Optional[List[str]] = Field(None, description="可选：只检查指定镜头")
    extract_frames: bool = Field(False, description="是否尝试使用本地 ffmpeg 抽帧")


class WorkflowVisualConsistencyResponse(BaseModel):
    workflow_id: str
    checked_count: int = 0
    checked_shot_ids: List[str] = Field(default_factory=list)
    skipped: List[Dict[str, Any]] = Field(default_factory=list)


# ========== API 端点 ==========

@router.get("/steps", response_model=WorkflowStepsResponse)
async def get_workflow_steps():
    """获取工作流步骤定义"""
    return WorkflowStepsResponse(
        steps=[
            WorkflowStep(id="novel", name=1, description="1. 小说", required=True),
            WorkflowStep(id="chapter", name=2, description="2. 章节", required=True),
            WorkflowStep(id="character", name=3, description="3. 角色", required=True),
            WorkflowStep(id="script", name=4, description="4. 剧本", required=True),
            WorkflowStep(id="storyboard", name=5, description="5. 分镜", required=True),
            WorkflowStep(id="shot", name=6, description="6. 镜头", required=True),
            WorkflowStep(id="video", name=7, description="7. 视频", required=True),
            WorkflowStep(id="tts", name=8, description="8. 配音", required=True),
            WorkflowStep(id="synthesis", name=9, description="9. 合成", required=True),
            WorkflowStep(id="export", name=10, description="10. 导出", required=False),
        ]
    )


@router.post("/start", response_model=WorkflowStartResponse, status_code=status.HTTP_201_CREATED)
async def start_workflow(
    request: WorkflowStartRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """创建新工作流（持久化到数据库）"""
    workflow_id = str(uuid4())
    title = request.title or f"工作流 {workflow_id[:8]}"

    workflow = Workflow(
        id=workflow_id,
        user_id=user_id,
        title=title,
        status="active",
        novel_id=request.novel_id,
        chapter_id=request.chapter_id,
        script_id=request.script_id,
        storyboard_id=request.storyboard_id,
        current_step=1,
        completed_steps=[],
        video_job_ids=[],
        tts_job_ids=[],
        synthesis_job_ids=[],
    )
    db.add(workflow)
    await db.commit()

    return WorkflowStartResponse(
        workflow_id=workflow_id,
        title=title,
        message="工作流创建成功",
    )


@router.post("/{workflow_id}/episode-contract/lock", response_model=Dict[str, Any])
async def lock_workflow_episode_contract(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return await lock_episode_contract(db, user_id, workflow_id)


@router.post("/{workflow_id}/generate-media-batch", response_model=WorkflowMediaBatchResponse)
async def generate_workflow_media_batch(
    workflow_id: str,
    request: WorkflowMediaBatchRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """按镜头批量生成视频/音频草稿。"""
    return await workflow_media_result(
        workflow_media_helper.generate_workflow_media_batch(
            workflow_media_helper.WorkflowMediaCommand(db, user_id, workflow_id, request)
        )
    )

@router.post("/{workflow_id}/quality/evaluate")
async def evaluate_workflow_quality(
    workflow_id: str,
    request: WorkflowQualityEvaluateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Persist one append-only six-dimensional evaluation set."""
    workflow = await _get_workflow_for_user(db, workflow_id, user_id)
    shots = await _workflow_shots_for_request(db, workflow, user_id, [request.shot_id])
    if not shots:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="镜头不存在")
    shot = shots[0]
    result = await _evaluate_and_persist_server_quality(
        db,
        workflow=workflow,
        shot=shot,
        user_id=user_id,
        dev_semantic_fixture=request.dev_semantic_fixture,
    )
    aggregate_gate = _quality_gate_summary(
        await _latest_quality_rows(db, workflow_id=workflow.id, shot_id=shot.id)
    ) or {"ready": result.ready, "overall_readiness": result.overall_readiness, "blockers": [], "warnings": []}
    await db.commit()
    return {
        "workflow_id": workflow.id,
        "shot_id": request.shot_id,
        "artifact_id": result.artifact_id,
        "ready": aggregate_gate["ready"],
        "overall_readiness": aggregate_gate["overall_readiness"],
        "dimensions": [
            {
                "id": row.id,
                "dimension": row.dimension,
                "score": row.score,
                "confidence": row.confidence,
                "severity": row.severity,
                "blocking": row.blocking,
            }
            for row in result.dimension_results
        ],
        "blockers": aggregate_gate.get("blockers") or [],
        "warnings": aggregate_gate.get("warnings") or [],
    }


@router.post("/{workflow_id}/quality/repair")
async def repair_workflow_quality(
    workflow_id: str,
    request: WorkflowQualityRepairRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Execute the smallest DEV repair while preserving unrelated current jobs."""
    if not is_dev_mode():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="真实供应商最小返修执行器尚未配置",
        )
    workflow = await _get_workflow_for_user(db, workflow_id, user_id)
    shots = await _workflow_shots_for_request(db, workflow, user_id)
    shot = next((item for item in shots if item.id == request.shot_id), None)
    if shot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="镜头不存在")
    shot_ids = [item.id for item in shots]
    video_jobs = await _video_jobs_for_workflow_shots(db, workflow.id, user_id, shot_ids)
    tts_jobs = await _tts_jobs_for_workflow_shots(db, workflow.id, user_id, shot_ids)
    latest_videos = _latest_non_superseded_by_shot(video_jobs)
    latest_tts = _latest_non_superseded_by_shot(tts_jobs)
    current_jobs = [*latest_videos.values(), *latest_tts.values()]
    candidate_ids = list(dict.fromkeys(job.id for job in current_jobs))
    voice_issues = {"wrong_voice", "wrong_speaker"}
    video_issues = {
        "wrong_prop_state",
        "wrong_prop_owner",
        "main_character_identity_mismatch",
        "future_episode_leakage",
        "corrupt_mp4",
    }
    subtitle_issues = {"missing_subtitle", "subtitle_timing"}
    if request.issue_code in {"semantic_score_below_blocking", "unknown_blocking_quality_issue"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "quality_repair_action_unavailable",
                "message": "当前语义阻断需要人工复审，不能自动执行媒体返修",
                "navigation_url": f"/studio/shot-review?workflow_id={workflow.id}&shot_id={shot.id}",
            },
        )
    affected_job = (
        latest_tts.get(shot.id)
        if request.issue_code in voice_issues
        else latest_videos.get(shot.id) if request.issue_code in video_issues else None
    )
    if affected_job is None and request.issue_code in subtitle_issues:
        affected_job = latest_videos.get(shot.id) or latest_tts.get(shot.id)
    if affected_job is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="当前问题没有可返修媒体任务")
    prior_quality_rows = await _latest_quality_rows(db, workflow_id=workflow.id, shot_id=shot.id)
    resolved_evaluation_ids = [
        row.id for row in prior_quality_rows
        if row.blocking
        and request.issue_code in ((row.evidence or {}).get("issue_codes") or [])
    ]
    plan = plan_minimal_repair(
        issue=request.issue_code,
        affected_artifact_ids=(affected_job.id,),
        candidate_artifact_ids=candidate_ids,
    )
    if request.issue_code not in subtitle_issues:
        old_extra = dict(_extra(affected_job))
        old_extra.update({
            "superseded_by_quality_repair": True,
            "superseded_at": utc_now().isoformat(),
            "quality_repair_issue": request.issue_code,
        })
        affected_job.extra_data = old_extra
    created_video_ids: List[str] = []
    created_tts_ids: List[str] = []
    if request.issue_code in voice_issues:
        new_id = str(uuid4())
        replacement = TTSJob(
            id=new_id,
            user_id=user_id,
            project_id=affected_job.project_id,
            workflow_id=workflow.id,
            task_id=f"dev-quality-tts-{new_id}",
            novel_id=affected_job.novel_id,
            chapter_id=affected_job.chapter_id,
            script_id=affected_job.script_id,
            storyboard_id=affected_job.storyboard_id,
            shot_id=shot.id,
            character_id=_quality_expected_state(shot).get("speaker_id") or affected_job.character_id,
            title=f"{affected_job.title or '镜头配音'} · 最小返修",
            text=affected_job.text,
            model_id=affected_job.model_id,
            model_name=affected_job.model_name,
            voice=affected_job.voice,
            speed=affected_job.speed,
            api_provider=affected_job.api_provider,
            status="succeeded",
            progress=100,
            audio_url=dev_audio_url(new_id),
            duration_seconds=affected_job.duration_seconds,
            extra_data={
                **_extra(affected_job),
                "superseded_by_quality_repair": False,
                "quality_repair_actions": list(plan.actions),
                "replaces_job_id": affected_job.id,
            },
        )
        db.add(replacement)
        created_tts_ids.append(new_id)
        workflow.tts_job_ids = list(dict.fromkeys([*(workflow.tts_job_ids or []), new_id]))
        shot.audio_url = replacement.audio_url
        shot.audio_status = "succeeded"
    elif request.issue_code in video_issues:
        new_id = str(uuid4())
        replacement = VideoJob(
            id=new_id,
            user_id=user_id,
            project_id=affected_job.project_id,
            workflow_id=workflow.id,
            task_id=f"dev-quality-video-{new_id}",
            title=f"{affected_job.title or '镜头视频'} · 最小返修",
            prompt=affected_job.prompt,
            model_id=affected_job.model_id,
            model_name=affected_job.model_name,
            duration=affected_job.duration,
            resolution=affected_job.resolution,
            image_url=affected_job.image_url,
            status="succeeded",
            progress=100,
            video_url=dev_video_url(new_id),
            cover_url=affected_job.cover_url,
            extra_data={
                **_extra(affected_job),
                "superseded_by_quality_repair": False,
                "quality_repair_actions": list(plan.actions),
                "replaces_job_id": affected_job.id,
                "quality_observed": {
                    **((_extra(affected_job).get("quality_observed") or {}) if isinstance(_extra(affected_job).get("quality_observed"), dict) else {}),
                    "main_character_id": _quality_expected_state(shot).get("main_character_id"),
                    "prop_owners": _quality_expected_state(shot).get("prop_owners") or {},
                    "source_episode_indices": [_quality_expected_state(shot).get("episode_index")] if _quality_expected_state(shot).get("episode_index") is not None else [],
                    "future_episode_leakage": False,
                    "mp4_valid": True,
                },
                "media_integrity": {"exists": True, "ffprobe_valid": True, "source": "dev_quality_repair"},
            },
        )
        db.add(replacement)
        created_video_ids.append(new_id)
        workflow.video_job_ids = list(dict.fromkeys([*(workflow.video_job_ids or []), new_id]))
        shot.video_url = replacement.video_url
        shot.video_status = "succeeded"
    else:
        track_id = str(uuid4())
        track = SubtitleTrack(
            id=track_id,
            user_id=user_id,
            workflow_id=workflow.id,
            storyboard_id=workflow.storyboard_id,
            shot_id=shot.id,
            title=f"镜头 {shot.shot_number} 最小返修字幕",
            status="ready",
            source="quality_repair",
            metadata_={"quality_repair_actions": list(plan.actions), "repair_issue": request.issue_code},
            is_active=True,
        )
        segment = SubtitleSegment(
            id=str(uuid4()),
            track_id=track_id,
            user_id=user_id,
            shot_id=shot.id,
            start_seconds=0,
            end_seconds=float(shot.duration or 4),
            text=shot.dialogue or _extra(shot).get("subtitle_text") or "",
            review_status="approved",
            source="quality_repair",
            is_active=True,
        )
        db.add_all([track, segment])
        metadata = dict(workflow.metadata_ or {})
        metadata["subtitle_track_ids"] = list(dict.fromkeys([*(metadata.get("subtitle_track_ids") or []), track_id]))
        workflow.metadata_ = metadata
    await db.flush()
    repair_id = str(uuid4())
    reevaluation = await _evaluate_and_persist_server_quality(
        db,
        workflow=workflow,
        shot=shot,
        user_id=user_id,
        repair_id=repair_id,
        resolves_evaluation_ids=resolved_evaluation_ids,
    )
    aggregate_gate = _quality_gate_summary(
        await _latest_quality_rows(db, workflow_id=workflow.id, shot_id=shot.id)
    ) or {"ready": reevaluation.ready, "overall_readiness": reevaluation.overall_readiness}
    await db.commit()
    return {
        "workflow_id": workflow.id,
        "shot_id": shot.id,
        "issue_code": request.issue_code,
        "actions": list(plan.actions),
        "affected_artifact_ids": list(plan.affected_artifact_ids),
        "unchanged_artifact_ids": list(plan.unchanged_artifact_ids),
        "created_video_job_ids": created_video_ids,
        "created_tts_job_ids": created_tts_ids,
        "repair_id": repair_id,
        "resolved_evaluation_ids": resolved_evaluation_ids,
        "evaluation_ready": aggregate_gate["ready"],
        "overall_readiness": aggregate_gate["overall_readiness"],
        "cost_risk": estimate_quality_repair_cost_risk(list(plan.actions)),
    }


@router.get("/{workflow_id}/shot-review", response_model=WorkflowShotReviewResponse)
async def get_workflow_shot_review(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """聚合工作流镜头审阅所需的最新媒体、证据和重生次数。"""
    workflow = await _get_workflow_for_user(db, workflow_id, user_id)
    shots = await _workflow_shots_for_request(db, workflow, user_id)
    shot_ids = [shot.id for shot in shots]
    video_jobs = await _video_jobs_for_workflow_shots(db, workflow_id, user_id, shot_ids)
    tts_jobs = await _tts_jobs_for_workflow_shots(db, workflow_id, user_id, shot_ids)
    latest_video_by_shot = _latest_non_superseded_by_shot(video_jobs)
    latest_tts_by_shot = _latest_non_superseded_by_shot(tts_jobs)

    regeneration_counts: Dict[str, int] = {}
    for job in video_jobs:
        shot_id = _job_shot_id(job)
        if shot_id and _is_superseded(job):
            regeneration_counts[shot_id] = regeneration_counts.get(shot_id, 0) + 1

    metadata = workflow.metadata_ if isinstance(workflow.metadata_, dict) else {}
    latest_render_artifacts = metadata.get("latest_render_artifacts")
    review_items = [
        _shot_review_item(
            shot,
            latest_video=latest_video_by_shot.get(shot.id),
            latest_tts=latest_tts_by_shot.get(shot.id),
            regeneration_count=regeneration_counts.get(shot.id, 0),
        )
        for shot in shots
    ]
    quality_rows = await _latest_quality_rows(db, workflow_id=workflow.id)
    quality_by_shot: Dict[str, List[QualityEvaluation]] = {}
    for row in quality_rows:
        if row.shot_id:
            quality_by_shot.setdefault(str(row.shot_id), []).append(row)
    for item in review_items:
        item["quality_gate"] = _quality_gate_summary(
            quality_by_shot.get(str(item["shot_id"]), [])
        )
    review_items.sort(key=_shot_review_sort_key)

    return WorkflowShotReviewResponse(
        workflow_id=workflow.id,
        latest_render_artifacts=latest_render_artifacts if isinstance(latest_render_artifacts, dict) else None,
        shots=review_items,
    )


@router.post("/{workflow_id}/visual-consistency", response_model=WorkflowVisualConsistencyResponse)
async def run_workflow_visual_consistency(
    workflow_id: str,
    request: WorkflowVisualConsistencyRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Run non-blocking visual consistency checks for workflow shots."""
    workflow = await _get_workflow_for_user(db, workflow_id, user_id)
    shots = await _workflow_shots_for_request(db, workflow, user_id)
    all_shot_ids = {shot.id for shot in shots}
    requested_ids = set(request.shot_ids or [])
    if requested_ids:
        shots = [shot for shot in shots if shot.id in requested_ids]

    skipped: List[Dict[str, Any]] = [
        {"shot_id": shot_id, "reason": "shot_not_found"}
        for shot_id in sorted(requested_ids - all_shot_ids)
    ]
    shot_ids = [shot.id for shot in shots]
    video_jobs = await _video_jobs_for_workflow_shots(db, workflow_id, user_id, shot_ids)
    latest_video_by_shot = _latest_non_superseded_by_shot(video_jobs)

    checked_shot_ids: List[str] = []
    for shot in shots:
        latest_video = latest_video_by_shot.get(shot.id)
        if not latest_video or getattr(latest_video, "status", None) not in {"succeeded", "completed"} or not latest_video.video_url:
            skipped.append({"shot_id": shot.id, "reason": "no_completed_video"})
            continue

        record = await record_completed_shot_visual_consistency(
            db,
            user_id=user_id,
            shot=shot,
            video_job=latest_video,
            extract_frames=request.extract_frames,
        )
        if not record:
            skipped.append({"shot_id": shot.id, "reason": "missing_front_reference"})
            continue
        checked_shot_ids.append(shot.id)

    await db.commit()
    return WorkflowVisualConsistencyResponse(
        workflow_id=workflow.id,
        checked_count=len(checked_shot_ids),
        checked_shot_ids=checked_shot_ids,
        skipped=skipped,
    )


@router.post("/{workflow_id}/regenerate-shots", response_model=WorkflowShotRegenerateResponse)
async def regenerate_workflow_shots(
    workflow_id: str,
    request: WorkflowShotRegenerateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """按失败、选择或角色过滤，局部重生工作流镜头。"""
    if request.filter and request.filter not in {"failed", "all_selected"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="未知镜头重生过滤器")
    workflow = await _get_workflow_for_user(db, workflow_id, user_id)
    shots = await _workflow_shots_for_request(db, workflow, user_id, request.shot_ids)
    if not shots:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="没有可重生的镜头")

    shot_ids = [shot.id for shot in shots]
    video_jobs = await _video_jobs_for_workflow_shots(db, workflow_id, user_id, shot_ids)
    latest_video_by_shot = _latest_non_superseded_by_shot(video_jobs)

    target_shots: List[Shot] = []
    skipped: List[Dict[str, Any]] = []
    for shot in shots:
        latest_video = latest_video_by_shot.get(shot.id)
        if request.character_name and request.character_name not in workflow_media_helper.shot_character_names(shot):
            skipped.append({"shot_id": shot.id, "reason": "character_mismatch"})
            continue
        if request.filter == "failed":
            status_value = getattr(latest_video, "status", None) if latest_video else shot.video_status
            if status_value != "failed":
                skipped.append({"shot_id": shot.id, "reason": "not_failed"})
                continue
        target_shots.append(shot)

    target_ids = [shot.id for shot in target_shots]
    if not target_ids:
        return WorkflowShotRegenerateResponse(
            workflow_id=workflow.id,
            regenerated_shot_ids=[],
            created_count=0,
            skipped=skipped,
            ready_for_concatenate=True,
        )

    await _mark_superseded_for_shots(
        db,
        workflow_id=workflow.id,
        user_id=user_id,
        shot_ids=target_ids,
    )
    metadata = workflow.metadata_ if isinstance(workflow.metadata_, dict) else {}
    inherited_strategy = request.production_strategy or metadata.get("latest_production_strategy")
    batch_response = await workflow_media_result(
        workflow_media_helper.generate_workflow_media_batch(
        workflow_media_helper.WorkflowMediaCommand(
        db, user_id, workflow_id, WorkflowMediaBatchRequest(
            production_strategy=inherited_strategy,
            strategy="separate_video_tts",
            shot_ids=target_ids,
            audio_mode=request.audio_mode,
            native_audio=request.native_audio,
            model_config_id=request.model_config_id,
            audio_model_config_id=request.audio_model_config_id,
        ))))
    concatenate_shots = await _workflow_shots_for_request(db, workflow, user_id)
    if not concatenate_shots:
        concatenate_shots = shots
    concatenate_ids = await _concatenate_job_ids_for_workflow_shots(
        db,
        workflow_id=workflow.id,
        user_id=user_id,
        shots=concatenate_shots,
    )

    return WorkflowShotRegenerateResponse(
        workflow_id=workflow.id,
        regenerated_shot_ids=target_ids,
        created_count=batch_response.created_count,
        video_job_ids=batch_response.video_job_ids,
        tts_job_ids=batch_response.tts_job_ids,
        media_job_ids=batch_response.media_job_ids,
        concatenate_video_job_ids=concatenate_ids["video_job_ids"],
        concatenate_tts_job_ids=concatenate_ids["tts_job_ids"],
        concatenate_media_job_ids=concatenate_ids["media_job_ids"],
        subtitle_track_ids=batch_response.subtitle_track_ids,
        skipped=skipped,
        ready_for_concatenate=batch_response.ready_for_concatenate,
    )


@router.get("/status/{workflow_id}", response_model=WorkflowStatusResponse)
async def get_workflow_status(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取工作流状态"""
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user_id)
    )
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工作流不存在")

    video_query = select(VideoJob).where(VideoJob.user_id == user_id)
    video_ids = _job_ids(workflow.video_job_ids)
    if video_ids:
        video_query = video_query.where(VideoJob.id.in_(video_ids))
    else:
        video_query = video_query.where(VideoJob.workflow_id == workflow_id)
    video_result = await db.execute(video_query.order_by(desc(VideoJob.created_at)).limit(20))
    raw_video_jobs = video_result.scalars().all()
    if video_ids:
        video_order = {job_id: index for index, job_id in enumerate(video_ids)}
        raw_video_jobs = sorted(raw_video_jobs, key=lambda job: video_order.get(job.id, len(video_order)))
    else:
        raw_video_jobs = sorted(raw_video_jobs, key=lambda job: (_extra(job).get("shot_number") or 9999, str(job.created_at)))
    video_jobs = [
        {
            "id": job.id,
            "task_id": job.task_id,
            "title": job.title,
            "prompt": job.prompt,
            "status": job.status,
            "progress": job.progress,
            "video_url": job.video_url,
            "created_at": str(job.created_at),
            "project_id": job.project_id or _extra(job).get("project_id"),
            "workflow_id": job.workflow_id or _extra(job).get("workflow_id"),
            "novel_id": _extra(job).get("novel_id"),
            "chapter_id": _extra(job).get("chapter_id"),
            "script_id": _extra(job).get("script_id"),
            "storyboard_id": _extra(job).get("storyboard_id"),
            "shot_id": _extra(job).get("shot_id"),
            "chapter_title": _extra(job).get("chapter_title"),
            "shot_number": _extra(job).get("shot_number"),
        }
        for job in raw_video_jobs
    ]

    tts_query = select(TTSJob).where(TTSJob.user_id == user_id)
    tts_ids = _job_ids(workflow.tts_job_ids)
    if tts_ids:
        tts_query = tts_query.where(TTSJob.id.in_(tts_ids))
    else:
        tts_query = tts_query.where(TTSJob.workflow_id == workflow_id)
    tts_result = await db.execute(tts_query.order_by(desc(TTSJob.created_at)).limit(20))
    raw_tts_jobs = tts_result.scalars().all()
    if tts_ids:
        tts_order = {job_id: index for index, job_id in enumerate(tts_ids)}
        raw_tts_jobs = sorted(raw_tts_jobs, key=lambda job: tts_order.get(job.id, len(tts_order)))
    tts_jobs = [
        {
            "id": job.id,
            "task_id": job.task_id,
            "title": job.title,
            "text": job.text,
            "voice": job.voice,
            "speed": job.speed,
            "status": job.status,
            "progress": job.progress,
            "audio_url": job.audio_url,
            "created_at": str(job.created_at),
            "project_id": job.project_id,
            "workflow_id": job.workflow_id,
            "novel_id": job.novel_id,
            "chapter_id": job.chapter_id,
            "script_id": job.script_id,
            "storyboard_id": job.storyboard_id,
            "shot_id": job.shot_id,
            "character_id": job.character_id,
            "extra_data": _extra(job),
        }
        for job in raw_tts_jobs
    ]

    metadata = workflow.metadata_ if isinstance(workflow.metadata_, dict) else {}
    metadata = workflow_media_helper.merge_latest_production_strategy(metadata, metadata.get("latest_production_strategy"))
    media_query = select(MediaGenerationJob).where(MediaGenerationJob.user_id == user_id, MediaGenerationJob.is_active == True)
    media_ids = _job_ids(metadata.get("media_job_ids"))
    if media_ids:
        media_query = media_query.where(MediaGenerationJob.id.in_(media_ids))
    else:
        media_query = media_query.where(MediaGenerationJob.workflow_id == workflow_id)
    media_result = await db.execute(media_query.order_by(desc(MediaGenerationJob.created_at)).limit(50))
    raw_media_jobs = media_result.scalars().all()
    if media_ids:
        media_order = {job_id: index for index, job_id in enumerate(media_ids)}
        raw_media_jobs = sorted(raw_media_jobs, key=lambda job: media_order.get(job.id, len(media_order)))
    else:
        raw_media_jobs = sorted(raw_media_jobs, key=lambda job: (job.shot_id or "", str(job.created_at)))
    media_jobs = [
        {
            "id": job.id,
            "task_id": job.task_id,
            "task_type": job.task_type,
            "media_type": job.media_type,
            "title": job.title,
            "prompt": job.prompt,
            "status": job.status,
            "progress": job.progress,
            "output_video_url": job.output_video_url,
            "output_audio_url": job.output_audio_url,
            "subtitle_track_id": job.subtitle_track_id,
            "duration_seconds": job.duration_seconds,
            "resolution": job.resolution,
            "seed": job.seed,
            "created_at": str(job.created_at),
            "project_id": job.project_id,
            "workflow_id": job.workflow_id,
            "novel_id": job.novel_id,
            "chapter_id": job.chapter_id,
            "script_id": job.script_id,
            "storyboard_id": job.storyboard_id,
            "shot_id": job.shot_id,
            "extra_data": _extra(job),
        }
        for job in raw_media_jobs
    ]

    subtitle_query = select(SubtitleTrack).where(SubtitleTrack.user_id == user_id, SubtitleTrack.is_active == True)
    subtitle_ids = _job_ids(metadata.get("subtitle_track_ids"))
    if subtitle_ids:
        subtitle_query = subtitle_query.where(SubtitleTrack.id.in_(subtitle_ids))
    else:
        subtitle_query = subtitle_query.where(SubtitleTrack.workflow_id == workflow_id)
    subtitle_result = await db.execute(subtitle_query.order_by(desc(SubtitleTrack.created_at)).limit(50))
    raw_subtitle_tracks = subtitle_result.scalars().all()
    if subtitle_ids:
        subtitle_order = {track_id: index for index, track_id in enumerate(subtitle_ids)}
        raw_subtitle_tracks = sorted(raw_subtitle_tracks, key=lambda track: subtitle_order.get(track.id, len(subtitle_order)))
    subtitle_tracks = [
        {
            "id": track.id,
            "title": track.title,
            "language": track.language,
            "kind": track.kind,
            "source": track.source,
            "status": track.status,
            "export_urls": track.export_urls or {},
            "workflow_id": track.workflow_id,
            "novel_id": track.novel_id,
            "chapter_id": track.chapter_id,
            "script_id": track.script_id,
            "storyboard_id": track.storyboard_id,
            "shot_id": track.shot_id,
            "media_job_id": track.media_job_id,
            "created_at": str(track.created_at),
        }
        for track in raw_subtitle_tracks
    ]

    synthesis_query = select(SynthesisJob).where(SynthesisJob.user_id == user_id, SynthesisJob.is_active == True)
    synthesis_ids = _job_ids(workflow.synthesis_job_ids)
    if synthesis_ids:
        synthesis_query = synthesis_query.where(SynthesisJob.id.in_(synthesis_ids))
    else:
        synthesis_query = synthesis_query.where(SynthesisJob.workflow_id == workflow_id)
    synthesis_result = await db.execute(synthesis_query.order_by(desc(SynthesisJob.created_at)).limit(20))
    synthesis_jobs = []
    for job in synthesis_result.scalars().all():
        extra = _extra(job)
        render_artifacts = extra.get("render_artifacts") if isinstance(extra.get("render_artifacts"), dict) else {}
        publication_readiness = evaluate_publication_readiness(job.output_url, extra)
        synthesis_jobs.append({
            "id": job.id,
            "task_id": job.task_id,
            "title": job.title,
            "status": job.status,
            "progress": job.progress,
            "video_url": job.video_url,
            "audio_url": job.audio_url,
            "output_url": job.output_url,
            "duration_seconds": job.duration_seconds,
            "created_at": str(job.created_at),
            "project_id": job.project_id or extra.get("project_id"),
            "workflow_id": job.workflow_id or extra.get("workflow_id"),
            "video_job_id": extra.get("video_job_id"),
            "tts_job_id": extra.get("tts_job_id"),
            "manifest_url": extra.get("manifest_url") or render_artifacts.get("source_manifest_url"),
            "preview_url": render_artifacts.get("preview_url"),
            "srt_url": render_artifacts.get("srt_url"),
            "timeline_url": render_artifacts.get("timeline_url"),
            "render_manifest_url": render_artifacts.get("render_manifest_url"),
            "render_status": extra.get("render_status"),
            "render_backend": extra.get("render_backend"),
            "is_publishable": publication_readiness["is_publishable"],
            "output_kind": publication_readiness["output_kind"],
            "publication_blockers": publication_readiness["publication_blockers"],
            "segment_count": extra.get("segment_count"),
            "extra_data": extra,
        })

    production_bible_summary = None
    snapshot = metadata.get("production_snapshot") if isinstance(metadata.get("production_snapshot"), dict) else {}
    if snapshot:
        production_bible_summary = snapshot.get("summary") if isinstance(snapshot.get("summary"), dict) else None
    elif workflow.novel_id:
        production_bible_summary = await build_production_bible_summary(
            db, user_id, workflow.novel_id, as_of_chapter_id=workflow.chapter_id
        )

    return WorkflowStatusResponse(
        workflow_id=workflow.id,
        title=workflow.title,
        status=workflow.status,
        current_step=workflow.current_step,
        completed_steps=workflow.completed_steps or [],
        novel_id=workflow.novel_id,
        chapter_id=workflow.chapter_id,
        script_id=workflow.script_id,
        storyboard_id=workflow.storyboard_id,
        video_jobs=video_jobs,
        tts_jobs=tts_jobs,
        media_jobs=media_jobs,
        subtitle_tracks=subtitle_tracks,
        synthesis_jobs=synthesis_jobs,
        metadata=metadata,
        production_bible_summary=production_bible_summary,
    )


@router.put("/{workflow_id}/step", response_model=WorkflowDetailResponse)
async def update_workflow_step(
    workflow_id: str,
    request: WorkflowUpdateStepRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """更新工作流步骤进度"""
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user_id)
    )
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工作流不存在")

    if request.current_step is not None:
        workflow.current_step = request.current_step
    if request.status is not None:
        workflow.status = request.status
    if request.completed_steps is not None:
        workflow.completed_steps = request.completed_steps
    if request.novel_id is not None:
        workflow.novel_id = request.novel_id or None
    if request.chapter_id is not None:
        workflow.chapter_id = request.chapter_id or None
    if request.script_id is not None:
        workflow.script_id = request.script_id or None
    if request.storyboard_id is not None:
        workflow.storyboard_id = request.storyboard_id or None
    if request.video_job_ids is not None:
        workflow.video_job_ids = request.video_job_ids
    if request.tts_job_ids is not None:
        workflow.tts_job_ids = request.tts_job_ids
    if request.synthesis_job_ids is not None:
        workflow.synthesis_job_ids = request.synthesis_job_ids

    await db.commit()
    await db.refresh(workflow)

    return WorkflowDetailResponse(
        workflow_id=workflow.id,
        title=workflow.title,
        status=workflow.status,
        current_step=workflow.current_step,
        completed_steps=workflow.completed_steps or [],
        novel_id=workflow.novel_id,
        chapter_id=workflow.chapter_id,
        script_id=workflow.script_id,
        storyboard_id=workflow.storyboard_id,
        video_job_ids=workflow.video_job_ids or [],
        tts_job_ids=workflow.tts_job_ids or [],
        synthesis_job_ids=workflow.synthesis_job_ids or [],
        metadata=workflow_media_helper.merge_latest_production_strategy(
            workflow.metadata_ if isinstance(workflow.metadata_, dict) else {},
            (workflow.metadata_ or {}).get("latest_production_strategy") if isinstance(workflow.metadata_, dict) else None,
        ),
        production_bible_summary=(workflow.metadata_ or {}).get("production_snapshot", {}).get("summary")
        if isinstance((workflow.metadata_ or {}).get("production_snapshot"), dict)
        else None,
        error_message=workflow.error_message,
        created_at=str(workflow.created_at),
        updated_at=str(workflow.updated_at),
    )


@router.get("/{workflow_id}", response_model=WorkflowDetailResponse)
async def get_workflow_detail(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取工作流详情"""
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user_id)
    )
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工作流不存在")

    return WorkflowDetailResponse(
        workflow_id=workflow.id,
        title=workflow.title,
        status=workflow.status,
        current_step=workflow.current_step,
        completed_steps=workflow.completed_steps or [],
        novel_id=workflow.novel_id,
        chapter_id=workflow.chapter_id,
        script_id=workflow.script_id,
        storyboard_id=workflow.storyboard_id,
        video_job_ids=workflow.video_job_ids or [],
        tts_job_ids=workflow.tts_job_ids or [],
        synthesis_job_ids=workflow.synthesis_job_ids or [],
        metadata=workflow_media_helper.merge_latest_production_strategy(
            workflow.metadata_ if isinstance(workflow.metadata_, dict) else {},
            (workflow.metadata_ or {}).get("latest_production_strategy") if isinstance(workflow.metadata_, dict) else None,
        ),
        production_bible_summary=(workflow.metadata_ or {}).get("production_snapshot", {}).get("summary")
        if isinstance((workflow.metadata_ or {}).get("production_snapshot"), dict)
        else None,
        error_message=workflow.error_message,
        created_at=str(workflow.created_at),
        updated_at=str(workflow.updated_at),
    )


@router.post("/{workflow_id}/timeline/sync", response_model=WorkflowTimelineSyncResponse)
async def sync_workflow_timeline(
    workflow_id: str,
    request: WorkflowTimelineSyncRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """把 workflow 连续成片清单落库为可编辑 Timeline/Track/Clip。"""
    workflow = await _get_workflow_for_user(db, workflow_id, user_id)
    synthesis_job = await _get_synthesis_for_render(db, workflow, user_id, request.synthesis_job_id)
    if synthesis_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="合成任务不存在")

    segments = _segment_list(synthesis_job)
    if not segments:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="合成任务缺少可导入的镜头段落")

    project = await _ensure_workflow_project(db, workflow, synthesis_job, user_id)
    timeline = await _ensure_workflow_timeline(
        db,
        workflow=workflow,
        synthesis_job=synthesis_job,
        project=project,
        user_id=user_id,
        request=request,
    )

    await db.flush()
    if request.force:
        result = await db.execute(select(Clip).where(Clip.timeline_id == timeline.id, Clip.user_id == user_id))
        for clip in result.scalars().all():
            clip.is_active = False
            clip.updated_at = utc_now()

    active_result = await db.execute(
        select(func.count(Clip.id)).where(
            Clip.timeline_id == timeline.id,
            Clip.user_id == user_id,
            Clip.is_active == True,
        )
    )
    active_count = active_result.scalar() or 0
    if active_count and not request.force:
        clip_count = int(active_count)
    else:
        tracks = {
            "video": await _ensure_named_track(db, timeline_id=timeline.id, track_type="video", track_index=0, name="V1 - 主视频"),
            "audio": await _ensure_named_track(db, timeline_id=timeline.id, track_type="audio", track_index=1, name="A1 - 对白/直生音频"),
            "subtitle": await _ensure_named_track(db, timeline_id=timeline.id, track_type="subtitle", track_index=2, name="S1 - 中文字幕"),
        }
        await db.flush()
        clips = _build_timeline_clips(timeline=timeline, user_id=user_id, tracks=tracks, segments=segments)
        for clip in clips:
            db.add(clip)
        clip_count = len(clips)

    timeline.total_duration = float(_extra(synthesis_job).get("duration_seconds") or synthesis_job.duration_seconds or 0)
    timeline.updated_at = utc_now()
    workflow.current_step = max(workflow.current_step or 1, 10)
    workflow.completed_steps = workflow_media_helper.complete_steps(workflow.completed_steps, 9, 10)
    workflow.metadata_ = {
        **(workflow.metadata_ or {}),
        "project_id": project.id,
        "latest_timeline_id": timeline.id,
        "latest_timeline_synced_at": utc_now().isoformat(),
    }
    synthesis_extra = dict(_extra(synthesis_job))
    synthesis_extra["timeline_id"] = timeline.id
    synthesis_extra["project_id"] = project.id
    synthesis_extra["timeline_clip_count"] = clip_count
    synthesis_job.extra_data = synthesis_extra

    await db.commit()
    return WorkflowTimelineSyncResponse(
        workflow_id=workflow.id,
        synthesis_job_id=synthesis_job.id,
        timeline_id=timeline.id,
        project_id=project.id,
        track_count=3,
        clip_count=clip_count,
        duration_seconds=timeline.total_duration or 0,
        message="时间线已同步，可进入可编辑轨道视图",
    )


@router.get("/", response_model=List[WorkflowDetailResponse])
async def list_workflows(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """列出用户的所有工作流"""
    result = await db.execute(
        select(Workflow)
        .where(Workflow.user_id == user_id)
        .order_by(desc(Workflow.created_at))
        .limit(limit)
        .offset(offset)
    )
    workflows = result.scalars().all()
    return [
        WorkflowDetailResponse(
            workflow_id=w.id,
            title=w.title,
            status=w.status,
            current_step=w.current_step,
            completed_steps=w.completed_steps or [],
            novel_id=w.novel_id,
            chapter_id=w.chapter_id,
            script_id=w.script_id,
            storyboard_id=w.storyboard_id,
            video_job_ids=w.video_job_ids or [],
            tts_job_ids=w.tts_job_ids or [],
            synthesis_job_ids=w.synthesis_job_ids or [],
            metadata=w.metadata_ or {},
            error_message=w.error_message,
            created_at=str(w.created_at),
            updated_at=str(w.updated_at),
        )
        for w in workflows
    ]


@router.get("/{workflow_id}/render/preflight", response_model=RenderPreflightResponse)
async def preflight_workflow_render(
    workflow_id: str,
    synthesis_job_id: Optional[str] = Query(None),
    use_editable_timeline: bool = Query(True),
    timeline_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """检查当前工作流是否具备生成本地渲染包的条件。"""
    workflow = await _get_workflow_for_user(db, workflow_id, user_id)
    synthesis_job = await _get_synthesis_for_render(db, workflow, user_id, synthesis_job_id)
    payload = await _build_render_preflight_payload(
        db,
        workflow,
        synthesis_job,
        user_id,
        use_editable_timeline=use_editable_timeline,
        timeline_id=timeline_id,
    )
    return RenderPreflightResponse(**payload)


@router.post("/{workflow_id}/render", response_model=RenderResponse)
async def render_workflow_package(
    workflow_id: str,
    request: RenderRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """生成 DEV_MODE 本地渲染包。

    该接口不声明已经完成真实转码；它把连续成片 manifest 转换成用户可下载、
    可审阅、可交给后续 FFmpeg/云剪辑执行器消费的 artifact 包。
    """
    if request.render_backend not in {"local_artifact_package", "ffmpeg_cloud", "ffmpeg_local"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="render_backend 仅支持 local_artifact_package/ffmpeg_cloud/ffmpeg_local",
        )

    workflow = await _get_workflow_for_user(db, workflow_id, user_id)
    synthesis_job = await _get_synthesis_for_render(db, workflow, user_id, request.synthesis_job_id)
    preflight = await _build_render_preflight_payload(
        db,
        workflow,
        synthesis_job,
        user_id,
        use_editable_timeline=request.use_editable_timeline,
        timeline_id=request.timeline_id,
    )
    if synthesis_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="合成任务不存在")
    if not preflight["ready"]:
        extra_data = dict(synthesis_job.extra_data or {})
        extra_data["render_status"] = "preflight_failed"
        extra_data["render_issues"] = preflight["issues"]
        extra_data["media_sync_health"] = preflight.get("media_sync_health") or {}
        failed_readiness = evaluate_publication_readiness(synthesis_job.output_url, extra_data)
        extra_data["is_publishable"] = failed_readiness["is_publishable"]
        extra_data["output_kind"] = failed_readiness["output_kind"]
        extra_data["publication_blockers"] = failed_readiness["publication_blockers"]
        synthesis_job.extra_data = extra_data
        synthesis_job.status = "failed"
        synthesis_job.error_message = "渲染预检失败"
        workflow.error_message = "渲染预检失败"
        workflow.metadata_ = {
            **(workflow.metadata_ or {}),
            "latest_render_preflight": preflight,
        }
        await db.commit()
        return RenderResponse(
            workflow_id=workflow.id,
            synthesis_job_id=synthesis_job.id,
            status="preflight_failed",
            message="渲染预检失败",
            render_status="preflight_failed",
            render_backend=request.render_backend,
            manifest_url=preflight.get("manifest_url"),
            segment_count=preflight.get("segment_count") or 0,
            duration_seconds=preflight.get("duration_seconds"),
            issues=preflight["issues"],
            render_source=preflight.get("render_source") or "manifest",
            timeline_id=preflight.get("timeline_id"),
            is_publishable=failed_readiness["is_publishable"],
            output_kind=failed_readiness["output_kind"],
            publication_blockers=failed_readiness["publication_blockers"],
            media_sync_health=preflight.get("media_sync_health") or {},
        )

    extra_data = dict(synthesis_job.extra_data or {})
    existing_artifacts = extra_data.get("render_artifacts") if isinstance(extra_data.get("render_artifacts"), dict) else {}
    render_source = await _resolve_render_source(
        db,
        workflow=workflow,
        synthesis_job=synthesis_job,
        user_id=user_id,
        use_editable_timeline=request.use_editable_timeline,
        timeline_id=request.timeline_id,
    )
    render_source_key = render_source.get("source_key")
    if (
        existing_artifacts
        and not request.force
        and extra_data.get("render_backend") == request.render_backend
        and extra_data.get("render_source_key") == render_source_key
    ):
        existing_readiness = evaluate_publication_readiness(synthesis_job.output_url, extra_data)
        existing_media_sync_health = extra_data.get("media_sync_health") or preflight.get("media_sync_health") or {}
        return RenderResponse(
            workflow_id=workflow.id,
            synthesis_job_id=synthesis_job.id,
            status=extra_data.get("render_status") or "rendered",
            message="渲染包已存在",
            render_status=extra_data.get("render_status") or "rendered",
            render_backend=extra_data.get("render_backend"),
            output_url=synthesis_job.output_url,
            manifest_url=extra_data.get("manifest_url"),
            preview_url=existing_artifacts.get("preview_url"),
            srt_url=existing_artifacts.get("srt_url"),
            timeline_url=existing_artifacts.get("timeline_url"),
            render_manifest_url=existing_artifacts.get("render_manifest_url"),
            segment_count=extra_data.get("segment_count") or 0,
            duration_seconds=extra_data.get("duration_seconds") or synthesis_job.duration_seconds,
            issues=[],
            render_source=extra_data.get("render_source") or "manifest",
            timeline_id=extra_data.get("render_timeline_id"),
            is_publishable=existing_readiness["is_publishable"],
            output_kind=existing_readiness["output_kind"],
            publication_blockers=existing_readiness["publication_blockers"],
            media_sync_health=existing_media_sync_health,
        )

    segments = render_source["segments"]
    media_sync_health = _build_media_sync_health(segments)
    render_id = str(uuid4())
    title = synthesis_job.title or f"工作流 {workflow.id[:8]} 渲染包"
    srt_content = _build_srt(segments)
    timeline_edl = _build_timeline_edl(workflow, synthesis_job, segments)
    timeline_edl["source"] = render_source.get("source")
    timeline_edl["timeline_id"] = render_source.get("timeline_id")
    timeline_url = _write_export_text(
        f"{render_id}-timeline.json",
        json.dumps(timeline_edl, ensure_ascii=False, sort_keys=True, indent=2),
    )
    srt_url = _write_export_text(f"{render_id}.srt", srt_content)

    if request.render_backend == "ffmpeg_cloud":
        cloud_config, cloud_provider = await _get_cloud_render_config(db, user_id, request.external_config_id)
        if not is_dev_mode() and not cloud_config:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="真实 FFmpeg 云渲染需要先在生产适配管理中配置 ffmpeg_cloud",
            )

        render_manifest = {
            "id": render_id,
            "type": "cloud_render_request_package",
            "version": "1.0",
            "workflow_id": workflow.id,
            "synthesis_job_id": synthesis_job.id,
            "title": title,
            "quality_profile": request.quality_profile,
            "source_manifest_url": extra_data.get("manifest_url"),
            "segment_count": len(segments),
            "duration_seconds": render_source.get("duration_seconds") or synthesis_job.duration_seconds,
            "timeline_url": timeline_url,
            "srt_url": srt_url,
            "burn_subtitles": request.burn_subtitles,
            "render_backend": "ffmpeg_cloud",
            "render_source": render_source.get("source"),
            "timeline_id": render_source.get("timeline_id"),
            "tracks": _build_render_tracks(segments),
            "segments": segments,
            "media_sync_health": media_sync_health,
            "created_at": utc_now().isoformat(),
        }
        render_manifest_url = _write_sequence_manifest(render_id, render_manifest)
        render_artifacts = {
            "render_manifest_url": render_manifest_url,
            "timeline_url": timeline_url,
            "srt_url": srt_url,
            "source_manifest_url": extra_data.get("manifest_url"),
        }
        cloud_payload = {
            **render_manifest,
            "render_manifest_url": render_manifest_url,
            "external_config_id": cloud_config.id if cloud_config else None,
            "external_provider_id": cloud_provider.id if cloud_provider else None,
        }

        provider_task_id = None
        render_status = "adapter_ready"
        adapter_result: Dict[str, Any] = {
            "message": "云渲染请求包已生成，等待外部 FFmpeg 适配器提交",
            "dev_mode": is_dev_mode(),
        }
        if not is_dev_mode() and cloud_config and cloud_provider:
            provider_task_id, render_status, adapter_result = await _submit_cloud_render_job(
                config=cloud_config,
                provider=cloud_provider,
                render_id=render_id,
                payload=cloud_payload,
            )

        output_url = adapter_result.get("output_url")
        extra_data["render_status"] = render_status
        extra_data["render_backend"] = "ffmpeg_cloud"
        extra_data["rendered_at"] = utc_now().isoformat()
        extra_data["render_quality_profile"] = request.quality_profile
        extra_data["render_source"] = render_source.get("source")
        extra_data["render_source_key"] = render_source_key
        extra_data["render_timeline_id"] = render_source.get("timeline_id")
        extra_data["render_artifacts"] = render_artifacts
        extra_data["render_issues"] = []
        extra_data["media_sync_health"] = media_sync_health
        extra_data["cloud_render_payload"] = cloud_payload
        extra_data["cloud_render_result"] = adapter_result
        extra_data["cloud_render_task_id"] = provider_task_id
        extra_data["external_config_id"] = cloud_config.id if cloud_config else request.external_config_id
        extra_data["burn_subtitles"] = request.burn_subtitles
        cloud_readiness = evaluate_publication_readiness(output_url, {
            **extra_data,
            "output_kind": "final_video" if output_url else "cloud_request",
        })
        extra_data["is_publishable"] = cloud_readiness["is_publishable"]
        extra_data["output_kind"] = cloud_readiness["output_kind"]
        extra_data["publication_blockers"] = cloud_readiness["publication_blockers"]
        synthesis_job.extra_data = extra_data
        synthesis_job.task_id = provider_task_id or synthesis_job.task_id
        synthesis_job.status = "succeeded" if output_url else ("failed" if render_status == "failed" else "pending")
        synthesis_job.progress = 100 if output_url else (0 if render_status == "failed" else 20)
        synthesis_job.output_url = output_url
        synthesis_job.error_message = adapter_result.get("body") if render_status == "failed" else None

        workflow.current_step = max(workflow.current_step, 9)
        workflow.completed_steps = workflow_media_helper.complete_steps(workflow.completed_steps, 7, 8, 9)
        workflow.metadata_ = {
            **(workflow.metadata_ or {}),
            "latest_render_job_id": synthesis_job.id,
            "latest_render_status": render_status,
            "latest_render_backend": "ffmpeg_cloud",
            "latest_render_artifacts": render_artifacts,
            "latest_cloud_render_task_id": provider_task_id,
        }
        workflow.error_message = synthesis_job.error_message
        await db.commit()

        return RenderResponse(
            workflow_id=workflow.id,
            synthesis_job_id=synthesis_job.id,
            status=render_status,
            message="云渲染请求包已生成" if render_status != "failed" else "云渲染提交失败",
            render_status=render_status,
            render_backend="ffmpeg_cloud",
            output_url=output_url,
            manifest_url=extra_data.get("manifest_url"),
            srt_url=srt_url,
            timeline_url=timeline_url,
            render_manifest_url=render_manifest_url,
            segment_count=len(segments),
            duration_seconds=render_source.get("duration_seconds") or synthesis_job.duration_seconds,
            issues=[],
            render_source=render_source.get("source") or "manifest",
            timeline_id=render_source.get("timeline_id"),
            is_publishable=cloud_readiness["is_publishable"],
            output_kind=cloud_readiness["output_kind"],
            publication_blockers=cloud_readiness["publication_blockers"],
            media_sync_health=media_sync_health,
        )

    if request.render_backend == "ffmpeg_local":
        from app.services.ffmpeg_local_renderer import (
            FFmpegLocalRenderError,
            render_workflow_package as render_ffmpeg_local_package,
        )

        render_manifest = {
            "id": render_id,
            "type": "ffmpeg_local_render_package",
            "version": "1.0",
            "workflow_id": workflow.id,
            "synthesis_job_id": synthesis_job.id,
            "title": title,
            "quality_profile": request.quality_profile,
            "source_manifest_url": extra_data.get("manifest_url"),
            "segment_count": len(segments),
            "duration_seconds": render_source.get("duration_seconds") or synthesis_job.duration_seconds,
            "timeline_url": timeline_url,
            "srt_url": srt_url,
            "burn_subtitles": request.burn_subtitles,
            "render_backend": "ffmpeg_local",
            "render_source": render_source.get("source"),
            "timeline_id": render_source.get("timeline_id"),
            "tracks": _build_render_tracks(segments),
            "segments": segments,
            "media_sync_health": media_sync_health,
            "created_at": utc_now().isoformat(),
        }
        output_dir = Path(__file__).resolve().parents[4] / "static" / "exports"
        try:
            local_result = await render_ffmpeg_local_package(
                render_manifest,
                output_dir=output_dir,
                burn_subtitles=request.burn_subtitles,
            )
        except FFmpegLocalRenderError as exc:
            extra_data["render_status"] = "failed"
            extra_data["render_backend"] = "ffmpeg_local"
            extra_data["rendered_at"] = utc_now().isoformat()
            extra_data["render_issues"] = [exc.detail]
            synthesis_job.extra_data = extra_data
            synthesis_job.status = "failed"
            synthesis_job.error_message = exc.detail.get("message")
            workflow.error_message = exc.detail.get("message")
            await db.commit()
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.detail) from exc

        output_url = local_result.get("output_url")
        render_artifacts = {
            "output_url": output_url,
            "srt_url": local_result.get("subtitle_url") or srt_url,
            "timeline_url": timeline_url,
            "source_manifest_url": extra_data.get("manifest_url"),
            "ffmpeg_log_tail": local_result.get("log_tail"),
        }
        render_manifest["output_url"] = output_url
        render_manifest["playable_url"] = output_url
        render_manifest["artifacts"] = render_artifacts
        render_manifest["ffmpeg"] = {
            "duration": local_result.get("duration"),
            "width": local_result.get("width"),
            "height": local_result.get("height"),
            "log_tail": local_result.get("log_tail"),
        }
        render_manifest["media_sync_health"] = media_sync_health
        render_manifest_url = _write_sequence_manifest(render_id, render_manifest)
        render_artifacts["render_manifest_url"] = render_manifest_url

        extra_data["render_status"] = "rendered"
        extra_data["render_backend"] = "ffmpeg_local"
        extra_data["rendered_at"] = utc_now().isoformat()
        extra_data["render_quality_profile"] = request.quality_profile
        extra_data["render_source"] = render_source.get("source")
        extra_data["render_source_key"] = render_source_key
        extra_data["render_timeline_id"] = render_source.get("timeline_id")
        extra_data["render_artifacts"] = render_artifacts
        extra_data["render_issues"] = []
        extra_data["media_sync_health"] = media_sync_health
        extra_data["burn_subtitles"] = request.burn_subtitles
        local_readiness = evaluate_publication_readiness(output_url, {
            **extra_data,
            "output_kind": "final_video",
        })
        extra_data["is_publishable"] = local_readiness["is_publishable"]
        extra_data["output_kind"] = local_readiness["output_kind"]
        extra_data["publication_blockers"] = local_readiness["publication_blockers"]
        synthesis_job.extra_data = extra_data
        synthesis_job.status = "succeeded"
        synthesis_job.progress = 100
        synthesis_job.output_url = output_url
        synthesis_job.duration_seconds = local_result.get("duration") or synthesis_job.duration_seconds
        synthesis_job.error_message = None

        workflow.current_step = max(workflow.current_step, 10)
        workflow.completed_steps = workflow_media_helper.complete_steps(workflow.completed_steps, 7, 8, 9, 10)
        workflow.metadata_ = {
            **(workflow.metadata_ or {}),
            "latest_render_job_id": synthesis_job.id,
            "latest_render_status": "rendered",
            "latest_render_backend": "ffmpeg_local",
            "latest_render_artifacts": render_artifacts,
        }
        workflow.error_message = None
        await db.commit()

        return RenderResponse(
            workflow_id=workflow.id,
            synthesis_job_id=synthesis_job.id,
            status="rendered",
            message="本地 FFmpeg 真实成片已生成",
            render_status="rendered",
            render_backend="ffmpeg_local",
            output_url=output_url,
            manifest_url=extra_data.get("manifest_url"),
            srt_url=render_artifacts.get("srt_url"),
            timeline_url=timeline_url,
            render_manifest_url=render_manifest_url,
            segment_count=len(segments),
            duration_seconds=local_result.get("duration") or render_source.get("duration_seconds") or synthesis_job.duration_seconds,
            issues=[],
            render_source=render_source.get("source") or "manifest",
            timeline_id=render_source.get("timeline_id"),
            is_publishable=local_readiness["is_publishable"],
            output_kind=local_readiness["output_kind"],
            publication_blockers=local_readiness["publication_blockers"],
            media_sync_health=media_sync_health,
        )

    render_manifest = {
        "id": render_id,
        "type": "local_render_package",
        "version": "1.0",
        "workflow_id": workflow.id,
        "synthesis_job_id": synthesis_job.id,
        "title": title,
        "quality_profile": request.quality_profile,
        "source_manifest_url": extra_data.get("manifest_url"),
        "segment_count": len(segments),
        "duration_seconds": render_source.get("duration_seconds") or synthesis_job.duration_seconds,
        "artifacts": {
            "timeline_url": timeline_url,
            "srt_url": srt_url,
        },
        "render_backend": "local_artifact_package",
        "render_source": render_source.get("source"),
        "timeline_id": render_source.get("timeline_id"),
        "tracks": _build_render_tracks(segments),
        "segments": segments,
        "media_sync_health": media_sync_health,
        "created_at": utc_now().isoformat(),
    }
    render_manifest_url = _write_sequence_manifest(render_id, render_manifest)
    preview_artifacts = {
        "render_manifest_url": render_manifest_url,
        "timeline_url": timeline_url,
        "srt_url": srt_url,
        "source_manifest_url": extra_data.get("manifest_url"),
    }
    preview_url = _write_export_text(
        f"{render_id}-preview.html",
        _build_render_html(title, segments, preview_artifacts),
    )
    render_artifacts = {
        **preview_artifacts,
        "preview_url": preview_url,
    }
    render_manifest["output_url"] = preview_url
    render_manifest["playable_url"] = preview_url
    render_manifest["artifacts"] = render_artifacts
    render_manifest_url = _write_sequence_manifest(render_id, render_manifest)
    render_artifacts["render_manifest_url"] = render_manifest_url

    extra_data["render_status"] = "rendered"
    extra_data["render_backend"] = "local_artifact_package"
    extra_data["rendered_at"] = utc_now().isoformat()
    extra_data["render_quality_profile"] = request.quality_profile
    extra_data["render_source"] = render_source.get("source")
    extra_data["render_source_key"] = render_source_key
    extra_data["render_timeline_id"] = render_source.get("timeline_id")
    extra_data["render_artifacts"] = render_artifacts
    extra_data["render_issues"] = []
    extra_data["media_sync_health"] = media_sync_health
    extra_data["is_publishable"] = False
    extra_data["output_kind"] = "preview_package"
    extra_data["publication_blockers"] = [{
        "code": "preview_package_not_publishable",
        "message": "当前只有本地审阅包，需要生成真实视频文件后才能发布",
    }]
    synthesis_job.extra_data = extra_data
    synthesis_job.status = "succeeded"
    synthesis_job.progress = 100
    synthesis_job.output_url = preview_url
    synthesis_job.error_message = None

    workflow.current_step = max(workflow.current_step, 10)
    workflow.completed_steps = workflow_media_helper.complete_steps(workflow.completed_steps, 7, 8, 9, 10)
    workflow.metadata_ = {
        **(workflow.metadata_ or {}),
        "latest_render_job_id": synthesis_job.id,
        "latest_render_status": "rendered",
        "latest_render_artifacts": render_artifacts,
    }
    workflow.error_message = None

    await db.commit()

    return RenderResponse(
        workflow_id=workflow.id,
        synthesis_job_id=synthesis_job.id,
        status="rendered",
        message="本地渲染包已生成",
        render_status="rendered",
        render_backend="local_artifact_package",
        output_url=synthesis_job.output_url,
        manifest_url=extra_data.get("manifest_url"),
        preview_url=preview_url,
        srt_url=srt_url,
        timeline_url=timeline_url,
        render_manifest_url=render_manifest_url,
        segment_count=len(segments),
        duration_seconds=render_source.get("duration_seconds") or synthesis_job.duration_seconds,
        issues=[],
        render_source=render_source.get("source") or "manifest",
        timeline_id=render_source.get("timeline_id"),
        is_publishable=False,
        output_kind="preview_package",
        publication_blockers=extra_data["publication_blockers"],
        media_sync_health=media_sync_health,
    )


@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """删除工作流"""
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user_id)
    )
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工作流不存在")

    await db.delete(workflow)
    await db.commit()
    return {"message": "工作流已删除"}


@router.post("/concatenate/{workflow_id}", response_model=ConcatenateResponse)
async def concatenate_videos(
    workflow_id: str,
    request: ConcatenateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """生成多镜头连续成片编排清单。

    DEV_MODE 下直接产出本地 manifest 和可追踪 output_url；生产环境后续可由
    FFmpeg/云剪辑任务执行器消费 manifest，完成真实转码、混音和字幕烧录。
    """
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user_id)
    )
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工作流不存在")

    video_job_ids = list(dict.fromkeys(request.video_job_ids or []))
    media_job_ids = list(dict.fromkeys(request.media_job_ids or []))
    if not video_job_ids and not media_job_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="video_job_ids 或 media_job_ids 不能为空",
        )

    video_by_id: Dict[str, Any] = {}
    if video_job_ids:
        video_result = await db.execute(
            select(VideoJob).where(
                VideoJob.id.in_(video_job_ids),
                VideoJob.user_id == user_id,
            )
        )
        video_by_id.update({job.id: job for job in video_result.scalars().all()})

    media_by_id: Dict[str, MediaGenerationJob] = {}
    if media_job_ids:
        media_result = await db.execute(
            select(MediaGenerationJob).where(
                MediaGenerationJob.id.in_(media_job_ids),
                MediaGenerationJob.user_id == user_id,
                MediaGenerationJob.is_active == True,
            )
        )
        media_by_id = {job.id: job for job in media_result.scalars().all()}
        video_by_id.update(media_by_id)

    ordered_video_ids = video_job_ids + media_job_ids
    missing_video_ids = [job_id for job_id in ordered_video_ids if job_id not in video_by_id]
    if missing_video_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到指定的视频或媒体任务: {', '.join(missing_video_ids)}",
        )

    ordered_video_jobs = _dedupe_latest_per_shot([video_by_id[job_id] for job_id in ordered_video_ids])
    video_job_ids = [job.id for job in ordered_video_jobs if not isinstance(job, MediaGenerationJob)]
    media_job_ids = [job.id for job in ordered_video_jobs if isinstance(job, MediaGenerationJob)]
    for job in ordered_video_jobs:
        _assert_lineage_matches_workflow(workflow, job)
        if job.status not in {"succeeded", "completed"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"视频或媒体任务 {job.id} 尚未成功，当前状态: {job.status}",
            )
        video_url = getattr(job, "video_url", None) or getattr(job, "output_video_url", None)
        if not video_url:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"视频或媒体任务 {job.id} 尚无可用URL",
            )

    ordered_tts_jobs: List[TTSJob] = []
    if request.tts_job_ids:
        tts_result = await db.execute(
            select(TTSJob).where(
                TTSJob.id.in_(request.tts_job_ids),
                TTSJob.user_id == user_id,
            )
        )
        tts_by_id = {job.id: job for job in tts_result.scalars().all()}
        missing_tts_ids = [job_id for job_id in request.tts_job_ids if job_id not in tts_by_id]
        if missing_tts_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到指定的TTS任务: {', '.join(missing_tts_ids)}",
            )
        ordered_tts_jobs = _dedupe_latest_per_shot([tts_by_id[job_id] for job_id in request.tts_job_ids])
        for job in ordered_tts_jobs:
            if job.status not in {"succeeded", "completed"}:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"TTS任务 {job.id} 尚未成功，当前状态: {job.status}",
                )
            if not job.audio_url:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"TTS任务 {job.id} 尚无可用音频URL",
                )

    shot_ids = [value for value in (_lineage_value(job, "shot_id") for job in ordered_video_jobs) if value]
    shot_map: Dict[str, Shot] = {}
    if shot_ids:
        shot_result = await db.execute(
            select(Shot).where(
                Shot.id.in_(shot_ids),
                Shot.user_id == user_id,
            )
        )
        shot_map = {shot.id: shot for shot in shot_result.scalars().all()}

    original_video_order = {job.id: index for index, job in enumerate(ordered_video_jobs)}
    ordered_video_jobs = sorted(
        ordered_video_jobs,
        key=lambda job: _workflow_job_sort_key(job, shot_map, original_video_order[job.id]),
    )
    video_job_ids = [job.id for job in ordered_video_jobs if not isinstance(job, MediaGenerationJob)]
    media_job_ids = [job.id for job in ordered_video_jobs if isinstance(job, MediaGenerationJob)]

    music_assets_by_cue: Dict[str, Asset] = {}
    music_cues = sorted(
        {
            cue
            for shot in shot_map.values()
            if (cue := _clean_text(getattr(shot, "music_cue", None)))
        }
    )
    if music_cues:
        music_result = await db.execute(
            select(Asset)
            .where(
                Asset.user_id == user_id,
                Asset.category == "music",
                Asset.asset_type == "audio",
                Asset.name.in_(music_cues),
                Asset.is_active == True,
            )
            .order_by(desc(Asset.updated_at), desc(Asset.created_at))
        )
        for asset in music_result.scalars().all():
            cue = _clean_text(asset.name)
            if not cue:
                continue
            if asset.novel_id and asset.novel_id != workflow.novel_id:
                continue
            current = music_assets_by_cue.get(cue)
            if current is None or (asset.novel_id == workflow.novel_id and current.novel_id != workflow.novel_id):
                music_assets_by_cue[cue] = asset

    tts_by_shot: Dict[str, TTSJob] = {}
    for tts_job in ordered_tts_jobs:
        if tts_job.shot_id and tts_job.shot_id not in tts_by_shot:
            tts_by_shot[tts_job.shot_id] = tts_job

    segments: List[Dict[str, Any]] = []
    source_preflight_sources: List[Dict[str, Any]] = []
    current_time = 0.0
    first_project_id = ordered_video_jobs[0].project_id or _extra(ordered_video_jobs[0]).get("project_id")
    first_audio_url: Optional[str] = None
    primary_lineage = {
        "project_id": first_project_id,
        "novel_id": _lineage_value(ordered_video_jobs[0], "novel_id") or workflow.novel_id,
        "chapter_id": _lineage_value(ordered_video_jobs[0], "chapter_id") or workflow.chapter_id,
        "script_id": _lineage_value(ordered_video_jobs[0], "script_id") or workflow.script_id,
        "storyboard_id": _lineage_value(ordered_video_jobs[0], "storyboard_id") or workflow.storyboard_id,
    }

    for index, video_job in enumerate(ordered_video_jobs):
        video_extra = _extra(video_job)
        video_preflight = _job_generation_preflight(video_job)
        shot_id = _lineage_value(video_job, "shot_id")
        shot = shot_map.get(shot_id) if shot_id else None
        tts_job = tts_by_shot.get(shot_id) if shot_id else None
        if not tts_job and index < len(ordered_tts_jobs):
            candidate = ordered_tts_jobs[index]
            if not candidate.shot_id or candidate.shot_id == shot_id:
                tts_job = candidate

        audio_url = tts_job.audio_url if tts_job else None
        if audio_url and not first_audio_url:
            first_audio_url = audio_url

        video_url = getattr(video_job, "video_url", None) or getattr(video_job, "output_video_url", None)
        direct_audio_url = getattr(video_job, "output_audio_url", None)
        audio_url = audio_url or direct_audio_url
        if audio_url and not first_audio_url:
            first_audio_url = audio_url

        video_duration = float(
            getattr(video_job, "duration", None)
            or getattr(video_job, "duration_seconds", None)
            or (shot.duration if shot else 4)
            or 4
        )
        audio_duration = float(tts_job.duration_seconds or 0.0) if tts_job else 0.0
        if direct_audio_url and not audio_duration:
            audio_duration = video_duration
        segment_duration = video_duration
        audio_duration_strategy = None
        if audio_url:
            if audio_duration and audio_duration > video_duration + _DIALOGUE_SYNC_DURATION_TOLERANCE_SECONDS:
                audio_duration_strategy = "trim_to_segment"
            elif audio_duration and audio_duration < video_duration - _DIALOGUE_SYNC_DURATION_TOLERANCE_SECONDS:
                audio_duration_strategy = "pad_silence"
            else:
                audio_duration_strategy = "match_segment"
        dialogue_sync_contract = _dialogue_sync_contract_from_jobs(video_job, tts_job)
        dialogue_sync_texts = _dialogue_sync_texts(
            contract=dialogue_sync_contract,
            tts_job=tts_job,
            video_job=video_job,
            shot=shot,
        )
        subtitle_text = ""
        if request.include_subtitles and request.subtitle_mode != "off":
            subtitle_text = dialogue_sync_texts["subtitle_text"]
        spoken_text = dialogue_sync_texts["spoken_text"]
        sync_diagnostics = _dialogue_sync_diagnostics(
            segment_index=index + 1,
            video_duration=video_duration,
            audio_duration=audio_duration,
            contract=dialogue_sync_contract,
        )

        segment = {
            "index": index + 1,
            "start_seconds": round(current_time, 3),
            "duration_seconds": round(segment_duration, 3),
            "end_seconds": round(current_time + segment_duration, 3),
            "video": {
                "job_id": video_job.id,
                "task_id": video_job.task_id,
                "url": video_url,
                "duration_seconds": video_duration,
                "prompt": video_job.prompt,
                "model_id": video_job.model_id,
                "model_name": video_job.model_name,
                "cover_url": video_job.cover_url,
                "source_type": "direct_audio_video" if isinstance(video_job, MediaGenerationJob) else "video_job",
            },
            "audio": {
                "job_id": tts_job.id if tts_job else None,
                "task_id": tts_job.task_id if tts_job else None,
                "url": audio_url,
                "duration_seconds": audio_duration if audio_url else None,
                "render_duration_seconds": segment_duration if audio_url else None,
                "duration_strategy": audio_duration_strategy,
                "voice": tts_job.voice if tts_job else None,
                "text": spoken_text,
                "mix_strategy": request.audio_mix_strategy,
                "source_type": "tts_job" if tts_job else ("direct_audio_video" if direct_audio_url else None),
            },
            "subtitle": {
                "enabled": bool(request.include_subtitles and subtitle_text),
                "mode": request.subtitle_mode,
                "text": subtitle_text,
                "start_seconds": round(current_time, 3),
                "end_seconds": round(current_time + segment_duration, 3),
            },
            "transition": {
                "style": request.transition_style if index > 0 else "none",
                "duration_seconds": request.transition_duration_seconds if index > 0 else 0,
            },
            "lineage": {
                "novel_id": _lineage_value(video_job, "novel_id") or workflow.novel_id,
                "novel_title": video_extra.get("novel_title") or video_extra.get("lineage", {}).get("novel_title"),
                "chapter_id": _lineage_value(video_job, "chapter_id") or workflow.chapter_id,
                "chapter_title": video_extra.get("chapter_title") or video_extra.get("lineage", {}).get("chapter_title"),
                "chapter_number": video_extra.get("chapter_number") or video_extra.get("lineage", {}).get("chapter_number"),
                "script_id": _lineage_value(video_job, "script_id") or workflow.script_id,
                "script_title": video_extra.get("script_title") or video_extra.get("lineage", {}).get("script_title"),
                "storyboard_id": _lineage_value(video_job, "storyboard_id") or workflow.storyboard_id,
                "storyboard_title": video_extra.get("storyboard_title") or video_extra.get("lineage", {}).get("storyboard_title"),
                "shot_id": shot_id,
                "shot_number": video_extra.get("shot_number") or video_extra.get("lineage", {}).get("shot_number") or (shot.shot_number if shot else None),
            },
            "shot_controls": {
                "visual_description": shot.visual_description if shot else None,
                "dialogue": shot.dialogue if shot else None,
                "camera_angle": shot.camera_angle if shot else None,
                "camera_movement": shot.camera_movement if shot else None,
                "emotion": shot.emotion if shot else None,
                "lighting": shot.lighting if shot else None,
                "color_grading": shot.color_grading if shot else None,
                "sfx_cue": shot.sfx_cue if shot else None,
                "music_cue": shot.music_cue if shot else None,
                "ambient_sound": shot.ambient_sound if shot else None,
                "keyframes": shot.keyframes if shot else None,
                "character_refs": shot.character_refs if shot else None,
            },
            "consistency": video_extra.get("consistency") or {},
            "sync_diagnostics": sync_diagnostics,
        }
        if dialogue_sync_contract:
            segment["dialogue_sync_contract"] = dialogue_sync_contract
        music_cue = _clean_text(shot.music_cue if shot else None)
        music_asset = music_assets_by_cue.get(music_cue or "") if music_cue else None
        if music_asset and music_asset.url:
            segment["music"] = {
                "url": music_asset.url,
                "cue": music_cue,
                "volume": 0.18,
            }
        if video_preflight:
            segment["video"]["generation_preflight"] = video_preflight
            source_entry = _source_preflight_entry(
                "direct_audio_video" if isinstance(video_job, MediaGenerationJob) else "video",
                video_job,
            )
            if source_entry:
                source_preflight_sources.append(source_entry)
        if tts_job:
            tts_preflight = _job_generation_preflight(tts_job)
            if tts_preflight:
                segment["audio"]["generation_preflight"] = tts_preflight
                source_entry = _source_preflight_entry("tts", tts_job)
                if source_entry:
                    source_preflight_sources.append(source_entry)
        segments.append(segment)
        current_time += segment_duration

    total_duration = round(current_time, 3)
    synthesis_job_id = str(uuid4())
    source_generation_preflight = _aggregate_source_preflight(source_preflight_sources)
    manifest_payload = {
        "id": synthesis_job_id,
        "type": "multi_shot_final_video_manifest",
        "version": "1.0",
        "title": request.title or f"连续成片-{workflow.title}",
        "workflow_id": workflow_id,
        "user_id": user_id,
        "lineage": primary_lineage,
        "render_backend": "local_manifest",
        "quality_profile": request.quality_profile,
        "audio_mix_strategy": request.audio_mix_strategy,
        "subtitle_mode": request.subtitle_mode,
        "transition_style": request.transition_style,
        "segment_count": len(segments),
        "duration_seconds": total_duration,
        "tracks": {
            "video": [{"segment_index": item["index"], **item["video"]} for item in segments],
            "audio": [{"segment_index": item["index"], **item["audio"]} for item in segments if item["audio"]["url"]],
            "subtitle": [
                {"segment_index": item["index"], **item["subtitle"]}
                for item in segments
                if item["subtitle"]["enabled"]
            ],
        },
        "segments": segments,
        "created_at": utc_now().isoformat(),
    }
    if source_generation_preflight:
        manifest_payload["generation_preflight"] = source_generation_preflight
    manifest_url = _write_sequence_manifest(synthesis_job_id, manifest_payload)
    output_url = dev_synthesis_url(synthesis_job_id) if is_dev_mode() else None
    dev_complete = is_dev_mode()

    synthesis_extra_data = {
        "workflow_id": workflow_id,
        "project_id": first_project_id,
        **primary_lineage,
        "video_job_ids": video_job_ids,
        "media_job_ids": media_job_ids,
        "tts_job_ids": request.tts_job_ids or [],
        "segment_count": len(segments),
        "duration_seconds": total_duration,
        "manifest_url": manifest_url,
        "output_url": output_url,
        "render_backend": "local_manifest",
        "render_status": "ready" if dev_complete else "pending_renderer",
        "quality_profile": request.quality_profile,
        "audio_mix_strategy": request.audio_mix_strategy,
        "subtitle_mode": request.subtitle_mode,
        "transition_style": request.transition_style,
        "segments": segments,
    }
    if source_generation_preflight:
        synthesis_extra_data["generation_preflight"] = source_generation_preflight

    synthesis_job = SynthesisJob(
        id=synthesis_job_id,
        user_id=user_id,
        workflow_id=workflow_id,
        task_id=None,
        title=request.title or f"视频拼接-{workflow_id[:8]}",
        project_id=first_project_id,
        model_id="sequence-manifest",
        model_name="DEV_MODE 多镜头连续成片" if dev_complete else "多镜头连续成片清单",
        video_url=getattr(ordered_video_jobs[0], "video_url", None) or getattr(ordered_video_jobs[0], "output_video_url", None),
        audio_url=first_audio_url,
        status="succeeded" if dev_complete else "pending",
        progress=100 if dev_complete else 20,
        output_url=output_url,
        duration_seconds=total_duration,
        cost=0,
        extra_data=synthesis_extra_data,
    )
    db.add(synthesis_job)

    workflow.novel_id = workflow.novel_id or primary_lineage.get("novel_id")
    workflow.chapter_id = workflow.chapter_id or primary_lineage.get("chapter_id")
    workflow.script_id = workflow.script_id or primary_lineage.get("script_id")
    workflow.storyboard_id = workflow.storyboard_id or primary_lineage.get("storyboard_id")
    workflow.video_job_ids = list(dict.fromkeys((workflow.video_job_ids or []) + video_job_ids))
    workflow.tts_job_ids = list(dict.fromkeys((workflow.tts_job_ids or []) + (request.tts_job_ids or [])))
    workflow.synthesis_job_ids = list(dict.fromkeys((workflow.synthesis_job_ids or []) + [synthesis_job_id]))
    workflow.current_step = max(workflow.current_step, 9)
    workflow.completed_steps = workflow_media_helper.complete_steps(workflow.completed_steps, 7, 8, 9)
    workflow.metadata_ = {
        **(workflow.metadata_ or {}),
        "latest_sequence_manifest_url": manifest_url,
        "latest_synthesis_job_id": synthesis_job_id,
        "latest_segment_count": len(segments),
        "latest_duration_seconds": total_duration,
        "media_job_ids": list(dict.fromkeys(((workflow.metadata_ or {}).get("media_job_ids") or []) + media_job_ids)),
    }

    await db.commit()

    return ConcatenateResponse(
        job_id=synthesis_job_id,
        message="多镜头连续成片清单已创建",
        output_url=output_url,
        manifest_url=manifest_url,
        segment_count=len(segments),
        duration_seconds=total_duration,
    )
