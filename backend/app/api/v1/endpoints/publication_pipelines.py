"""Novel → platform Publication pipeline API (P1 post-tail glue)."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import require_project_role
from app.core.security import get_current_user_id
from app.core.time_utils import utc_now
from app.models.novel import Novel
from app.models.publication import Publication
from app.models.publication_pipeline import NovelPublicationPipeline
from app.models.series_production_run import SeriesProductionRun
from app.services.publication_pipeline_queue import (
    publication_pipeline_execution_active,
    signal_publication_pipeline_pause,
    start_publication_pipeline_execution,
)

router = APIRouter()

EXTERNAL_PLATFORM_KEYS = {
    "douyin",
    "bilibili",
    "weixin",
    "wechat",
    "youtube",
    "tiktok",
    "external_publish",
    "external_platform",
}


class DeliveryConfig(BaseModel):
    mode: str = "whole_book_single_mp4"
    render_backend: str = "ffmpeg_local"
    visibility: str = "private"
    title: Optional[str] = None
    publish_status: str = "published"


class CreatePublicationPipelineRequest(BaseModel):
    idempotency_key: str = Field(..., min_length=1, max_length=200)
    series_plan_version: Optional[str] = None
    series_run_id: Optional[str] = None
    ensure_series_plan: bool = False
    model_bindings: Dict[str, Any] = Field(default_factory=dict)
    budget_policy: Dict[str, Any] = Field(default_factory=dict)
    delivery: DeliveryConfig = Field(default_factory=DeliveryConfig)
    media_policy: Dict[str, Any] = Field(default_factory=dict)
    quality_policy: Dict[str, Any] = Field(default_factory=dict)
    gates: Dict[str, Any] = Field(default_factory=dict)
    project_id: Optional[str] = None

    model_config = {"extra": "allow"}


def _pipeline_enabled() -> bool:
    return (os.getenv("PUBLICATION_PIPELINE_ENABLED") or "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _reject_external_platforms(payload: Dict[str, Any]) -> None:
    stack = [payload]
    while stack:
        current = stack.pop()
        if not isinstance(current, dict):
            continue
        for key, value in current.items():
            lowered = str(key).lower()
            if lowered in EXTERNAL_PLATFORM_KEYS or any(
                token in lowered for token in ("douyin", "bilibili", "tiktok")
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "external_distribution_not_supported",
                        "message": "仅支持平台 Publication，不对接抖音/Bilibili 等外发平台",
                        "field": key,
                    },
                )
            if isinstance(value, dict):
                stack.append(value)


def _serialize_pipeline(pipeline: NovelPublicationPipeline) -> Dict[str, Any]:
    publication_url = None
    if pipeline.publication_id:
        publication_url = f"/api/v1/synthesis/publications/{pipeline.publication_id}"
    return {
        "pipeline_id": pipeline.id,
        "novel_id": pipeline.novel_id,
        "series_run_id": pipeline.series_run_id,
        "status": pipeline.status,
        "stage": pipeline.stage,
        "series_plan_version": pipeline.series_plan_version,
        "idempotency_key": pipeline.idempotency_key,
        "episodes": pipeline.episodes or [],
        "final_video_url": pipeline.final_video_url,
        "publication_id": pipeline.publication_id,
        "publication_url": publication_url,
        "gate_summary": pipeline.gate_summary or {},
        "blocker_code": pipeline.blocker_code,
        "blocker_detail": pipeline.blocker_detail,
        "delivery": pipeline.delivery or {},
        "updated_at": pipeline.updated_at.isoformat() if pipeline.updated_at else None,
        "created_at": pipeline.created_at.isoformat() if pipeline.created_at else None,
        "links": {
            "self": f"/api/v1/publication-pipelines/{pipeline.id}",
            "series_run": (
                f"/api/v1/series-runs/{pipeline.series_run_id}" if pipeline.series_run_id else None
            ),
        },
    }


async def _get_novel_or_404(db: AsyncSession, novel_id: str, user_id: str) -> Novel:
    novel = await db.scalar(select(Novel).where(Novel.id == novel_id, Novel.user_id == user_id))
    if novel is None:
        raise HTTPException(status_code=404, detail="小说不存在")
    return novel


async def _get_pipeline_or_404(
    db: AsyncSession, pipeline_id: str, user_id: str
) -> NovelPublicationPipeline:
    pipeline = await db.scalar(
        select(NovelPublicationPipeline).where(
            NovelPublicationPipeline.id == pipeline_id,
            NovelPublicationPipeline.user_id == user_id,
        )
    )
    if pipeline is None:
        raise HTTPException(status_code=404, detail="发布流水线不存在")
    return pipeline


async def _resolve_series_plan_version(
    db: AsyncSession, novel: Novel, requested: Optional[str]
) -> str:
    if requested:
        return requested
    # Prefer novel.extra_data series plan fields when present.
    meta = novel.extra_data if isinstance(getattr(novel, "extra_data", None), dict) else {}
    for key in ("series_plan_version", "current_series_plan_version"):
        if meta.get(key):
            return str(meta[key])
    # Fall back to latest run version for this novel.
    run = await db.scalar(
        select(SeriesProductionRun)
        .where(
            SeriesProductionRun.user_id == novel.user_id,
            SeriesProductionRun.novel_id == novel.id,
        )
        .order_by(SeriesProductionRun.created_at.desc())
    )
    if run is not None:
        return run.series_plan_version
    return "unspecified"


async def _resolve_completed_run(
    db: AsyncSession,
    *,
    user_id: str,
    novel_id: str,
    series_plan_version: str,
    series_run_id: Optional[str],
) -> Optional[SeriesProductionRun]:
    if series_run_id:
        run = await db.scalar(
            select(SeriesProductionRun).where(
                SeriesProductionRun.id == series_run_id,
                SeriesProductionRun.user_id == user_id,
                SeriesProductionRun.novel_id == novel_id,
            )
        )
        return run
    rows = (
        await db.execute(
            select(SeriesProductionRun).where(
                SeriesProductionRun.user_id == user_id,
                SeriesProductionRun.novel_id == novel_id,
                SeriesProductionRun.series_plan_version == series_plan_version,
                SeriesProductionRun.status == "completed",
            )
        )
    ).scalars().all()
    if len(rows) == 1:
        return rows[0]
    return None


@router.post("/novels/{novel_id}/publication-pipelines", status_code=status.HTTP_202_ACCEPTED)
async def create_publication_pipeline(
    novel_id: str,
    request: CreatePublicationPipelineRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    if not _pipeline_enabled():
        raise HTTPException(status_code=503, detail="PUBLICATION_PIPELINE_ENABLED is false")

    raw = request.model_dump() if hasattr(request, "model_dump") else request.dict()
    _reject_external_platforms(raw)

    novel = await _get_novel_or_404(db, novel_id, user_id)
    if request.project_id:
        await require_project_role(db, request.project_id, user_id, "editor")

    series_plan_version = await _resolve_series_plan_version(db, novel, request.series_plan_version)

    existing = await db.scalar(
        select(NovelPublicationPipeline).where(
            NovelPublicationPipeline.user_id == user_id,
            NovelPublicationPipeline.novel_id == novel_id,
            NovelPublicationPipeline.series_plan_version == series_plan_version,
            NovelPublicationPipeline.idempotency_key == request.idempotency_key,
        )
    )
    if existing is not None:
        execution_status = "not_required" if existing.status == "succeeded" else "already_running"
        if existing.status in {"queued", "blocked", "failed"} and existing.status != "succeeded":
            # Re-enqueue runnable / retryable pipelines.
            if existing.status in {"queued", "failed"} or (
                existing.status == "blocked" and existing.blocker_code != "series_run_not_completed"
            ):
                try:
                    started = await start_publication_pipeline_execution(existing.id, user_id)
                    execution_status = "queued" if started else "already_running"
                except Exception as exc:
                    raise HTTPException(status_code=503, detail=str(exc)) from exc
        body = _serialize_pipeline(existing)
        body["execution_status"] = execution_status
        return JSONResponse(status_code=202, content=body)

    run = await _resolve_completed_run(
        db,
        user_id=user_id,
        novel_id=novel_id,
        series_plan_version=series_plan_version,
        series_run_id=request.series_run_id,
    )

    pipeline = NovelPublicationPipeline(
        id=str(uuid4()),
        user_id=user_id,
        novel_id=novel_id,
        series_run_id=run.id if run is not None else request.series_run_id,
        series_plan_version=series_plan_version,
        idempotency_key=request.idempotency_key,
        status="queued",
        stage="accepted",
        delivery=request.delivery.model_dump() if hasattr(request.delivery, "model_dump") else request.delivery.dict(),
        media_policy=request.media_policy or {"shot_scope": "all_episode_shots"},
        quality_policy=request.quality_policy or {},
        gates=request.gates or {"require_commercial_gates": False},
        gate_summary={},
        episodes=[],
        pipeline_metadata={
            "project_id": request.project_id,
            "ensure_series_plan": request.ensure_series_plan,
        },
    )

    execution_status = "queued"
    if run is None or run.status != "completed":
        pipeline.status = "blocked"
        pipeline.blocker_code = "series_run_not_completed"
        pipeline.blocker_detail = (
            "P1 requires a completed SeriesProductionRun; provide series_run_id "
            "or complete a matching run first (P2 automates front-to-shots)"
        )
        execution_status = "not_required"
    else:
        pipeline.series_run_id = run.id

    db.add(pipeline)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = await db.scalar(
            select(NovelPublicationPipeline).where(
                NovelPublicationPipeline.user_id == user_id,
                NovelPublicationPipeline.novel_id == novel_id,
                NovelPublicationPipeline.series_plan_version == series_plan_version,
                NovelPublicationPipeline.idempotency_key == request.idempotency_key,
            )
        )
        if existing is None:
            raise
        body = _serialize_pipeline(existing)
        body["execution_status"] = "already_running"
        return JSONResponse(status_code=202, content=body)

    await db.refresh(pipeline)

    if pipeline.status == "queued":
        try:
            started = await start_publication_pipeline_execution(pipeline.id, user_id)
            execution_status = "queued" if started else "already_running"
        except Exception as exc:
            pipeline.status = "failed"
            pipeline.blocker_code = "queue_unavailable"
            pipeline.blocker_detail = str(exc)
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "redis_unavailable", "message": str(exc)},
            ) from exc

    body = _serialize_pipeline(pipeline)
    body["execution_status"] = execution_status
    return JSONResponse(status_code=202, content=body)


@router.get("/publication-pipelines/{pipeline_id}")
async def get_publication_pipeline(
    pipeline_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    pipeline = await _get_pipeline_or_404(db, pipeline_id, user_id)
    body = _serialize_pipeline(pipeline)
    if pipeline.series_run_id:
        run = await db.scalar(
            select(SeriesProductionRun).where(SeriesProductionRun.id == pipeline.series_run_id)
        )
        body["series_run_status"] = run.status if run else None
    else:
        body["series_run_status"] = None
    return body


@router.get("/novels/{novel_id}/publication-pipelines")
async def list_publication_pipelines(
    novel_id: str,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    await _get_novel_or_404(db, novel_id, user_id)
    limit = max(1, min(int(limit or 20), 100))
    rows = (
        await db.execute(
            select(NovelPublicationPipeline)
            .where(
                NovelPublicationPipeline.user_id == user_id,
                NovelPublicationPipeline.novel_id == novel_id,
            )
            .order_by(NovelPublicationPipeline.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [_serialize_pipeline(item) for item in rows]


@router.post("/publication-pipelines/{pipeline_id}/pause")
async def pause_publication_pipeline(
    pipeline_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    pipeline = await _get_pipeline_or_404(db, pipeline_id, user_id)
    if pipeline.status in {"succeeded", "cancelled"}:
        raise HTTPException(status_code=409, detail="流水线已结束，无法暂停")
    pipeline.status = "paused"
    await db.commit()
    try:
        await signal_publication_pipeline_pause(pipeline_id)
    except Exception:
        # Pause signal is best-effort; DB status remains authority.
        pass
    return _serialize_pipeline(pipeline)


@router.post("/publication-pipelines/{pipeline_id}/resume")
async def resume_publication_pipeline(
    pipeline_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    pipeline = await _get_pipeline_or_404(db, pipeline_id, user_id)
    if pipeline.status == "cancelled":
        raise HTTPException(status_code=409, detail="已取消的流水线不可恢复")
    if pipeline.status == "succeeded":
        body = _serialize_pipeline(pipeline)
        body["execution_status"] = "not_required"
        return body
    if pipeline.blocker_code == "series_run_not_completed":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "series_run_not_completed",
                "message": "仍缺少已完成的 Series Run；P2 才会自动推进到 shots",
            },
        )
    pipeline.status = "queued"
    pipeline.blocker_code = None
    pipeline.blocker_detail = None
    await db.commit()
    try:
        started = await start_publication_pipeline_execution(pipeline.id, user_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    body = _serialize_pipeline(pipeline)
    body["execution_status"] = "queued" if started else "already_running"
    return body


@router.post("/publication-pipelines/{pipeline_id}/cancel")
async def cancel_publication_pipeline(
    pipeline_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    pipeline = await _get_pipeline_or_404(db, pipeline_id, user_id)
    if pipeline.status == "succeeded":
        raise HTTPException(status_code=409, detail="已成功流水线不可取消（保留 Publication）")
    pipeline.status = "cancelled"
    await db.commit()
    return _serialize_pipeline(pipeline)
