"""Non-blocking visual consistency evidence for shot review."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.models import Asset, Shot, VideoJob


VISUAL_CONSISTENCY_REVIEW_THRESHOLD = 80.0


def _json_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _json_list(value: Any) -> List[Any]:
    return list(value) if isinstance(value, list) else []


def _primary_character_entity_id(shot: Shot) -> Optional[str]:
    for ref in _json_list(getattr(shot, "character_refs", None)):
        if not isinstance(ref, dict):
            continue
        entity_id = ref.get("entity_id") or ref.get("id") or ref.get("character_id")
        if entity_id:
            return str(entity_id)

    extra = _json_dict(getattr(shot, "extra_data", None))
    entity_refs = _json_dict(extra.get("entity_refs"))
    for ref in _json_list(entity_refs.get("characters")):
        if not isinstance(ref, dict):
            continue
        entity_id = ref.get("entity_id") or ref.get("id") or ref.get("character_id")
        if entity_id:
            return str(entity_id)
    return None


def _asset_view_key(asset: Asset) -> Optional[str]:
    params = _json_dict(asset.generation_params)
    view_key = params.get("view_key") or params.get("view")
    return str(view_key).strip().lower() if view_key else None


async def find_primary_front_reference_asset(
    db: AsyncSession,
    *,
    user_id: str,
    shot: Shot,
) -> Optional[Asset]:
    """Find the protagonist's locked front-view asset, if one exists."""
    entity_id = _primary_character_entity_id(shot)
    if not entity_id:
        return None

    result = await db.execute(
        select(Asset)
        .where(
            Asset.user_id == user_id,
            Asset.entity_id == entity_id,
            Asset.entity_type == "character",
            Asset.is_active.is_(True),
            Asset.is_locked.is_(True),
        )
        .order_by(desc(Asset.version), desc(Asset.updated_at))
    )
    for asset in result.scalars().all():
        if asset.url and _asset_view_key(asset) == "front":
            return asset
    return None


def _placeholder_score(*, frame_urls: List[str], video_job: VideoJob) -> float:
    if frame_urls:
        return 86.0
    if getattr(video_job, "video_url", None):
        return 72.0
    return 0.0


def _build_visual_consistency_record(
    *,
    score: float,
    reference_asset: Asset,
    frame_urls: List[str],
    model: str,
    issues: Optional[List[str]],
    notes: Optional[str],
) -> Dict[str, Any]:
    normalized_score = round(float(score), 2)
    status = "passed" if normalized_score >= VISUAL_CONSISTENCY_REVIEW_THRESHOLD else "needs_review"
    return {
        "score": normalized_score,
        "status": status,
        "blocking": False,
        "model": model,
        "method": "placeholder_frame_reference",
        "reference_asset_id": reference_asset.id,
        "reference_url": reference_asset.url,
        "frame_count": len(frame_urls),
        "frames": frame_urls[:5],
        "issues": issues or [],
        "notes": notes
        or "非阻断占位评分：已记录主角 front 定稿与成片抽帧证据；真实图像相似度服务接入后可替换此分数。",
        "checked_at": utc_now().isoformat(),
    }


def _append_asset_visual_consistency(asset: Asset, record: Dict[str, Any]) -> None:
    params = _json_dict(asset.generation_params)
    history = _json_list(params.get("visual_consistency_history"))
    history.insert(0, record)
    params["visual_consistency"] = record
    params["visual_consistency_history"] = history[:20]
    asset.generation_params = params
    asset.updated_at = utc_now()


def _merge_shot_visual_consistency(shot: Shot, record: Dict[str, Any]) -> None:
    extra = _json_dict(shot.extra_data)
    quality_report = _json_dict(extra.get("quality_report"))
    quality_report["visual_consistency_score"] = record["score"]
    quality_report["visual_consistency_status"] = record["status"]
    quality_report["visual_consistency"] = record
    extra["quality_report"] = quality_report
    shot.extra_data = extra
    shot.updated_at = utc_now()


def _merge_job_visual_consistency(video_job: VideoJob, record: Dict[str, Any]) -> None:
    extra = _json_dict(video_job.extra_data)
    extra["visual_consistency"] = record
    video_job.extra_data = extra
    video_job.updated_at = utc_now()


async def record_completed_shot_visual_consistency(
    db: AsyncSession,
    *,
    user_id: str,
    shot: Shot,
    video_job: VideoJob,
    frame_urls: Optional[List[str]] = None,
    score: Optional[float] = None,
    model: str = "local-placeholder",
    issues: Optional[List[str]] = None,
    notes: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Record shot visual consistency evidence without blocking generation."""
    reference_asset = await find_primary_front_reference_asset(db, user_id=user_id, shot=shot)
    if not reference_asset:
        return None

    frames = [str(url) for url in (frame_urls or []) if url]
    effective_score = score if score is not None else _placeholder_score(frame_urls=frames, video_job=video_job)
    record = _build_visual_consistency_record(
        score=effective_score,
        reference_asset=reference_asset,
        frame_urls=frames,
        model=model,
        issues=issues,
        notes=notes,
    )

    _append_asset_visual_consistency(reference_asset, record)
    _merge_shot_visual_consistency(shot, record)
    _merge_job_visual_consistency(video_job, record)
    return record
