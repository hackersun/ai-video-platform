"""Production control APIs for final packs, media audit and AI producer."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models import Shot, TTSJob, Workflow
from app.services.audio_route_service import has_dialogue_text, has_voice_lock
from app.services.production_control import (
    apply_asset_locks_to_workflow,
    audit_and_persist_workflow_media,
    build_ai_producer_assistant,
    build_novel_production_pack,
    build_workflow_quality_report,
)

router = APIRouter(tags=["生产控制"])


class ProductionPackRequest(BaseModel):
    create_missing_assets: bool = Field(True, description="缺少定稿资产时自动创建占位资产")
    persist: bool = Field(True, description="是否保存到小说 extra_data.production_pack")


class WorkflowAssetLocksRequest(BaseModel):
    create_missing_assets: bool = Field(True, description="缺少定稿资产时自动创建占位资产")
    persist: bool = Field(True, description="是否写入 Shot.production_context")


class MediaAuditRequest(BaseModel):
    persist_remote: bool = Field(True, description="是否尝试把远端临时 URL 转存到本地 static")
    dry_run: bool = Field(False, description="只检查不写入")


class QualityCheckRequest(BaseModel):
    persist: bool = Field(True, description="是否把质量报告写回 Shot 和 Workflow")


class ProducerAssistantRequest(BaseModel):
    auto_fix: bool = Field(False, description="是否自动执行安全的补齐动作")
    action_code: Optional[str] = Field(None, description="只执行指定安全动作；不传时按原逻辑执行全部安全补齐")


def _json_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _clean_text(value: Any) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _tts_job_has_story_bible_voice_lock(job: TTSJob) -> bool:
    extra = _json_dict(job.extra_data)
    if extra.get("voice_source") == "story_bible":
        return True
    return has_voice_lock(_json_dict(extra.get("voice_lock_snapshot"))) or has_voice_lock(_json_dict(extra.get("voice_lock")))


def _character_name_from_refs(refs: Any) -> Optional[str]:
    if isinstance(refs, dict):
        for key in ("voice_character_name", "character_name", "name"):
            name = _clean_text(refs.get(key))
            if name:
                return name
        refs = list(refs.values())
    if not isinstance(refs, list) and not isinstance(refs, tuple):
        return None
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        for key in ("voice_character_name", "character_name", "name"):
            name = _clean_text(ref.get(key))
            if name:
                return name
    return None


def _best_effort_character_name(shot: Shot, tts_jobs: list[TTSJob]) -> Optional[str]:
    for job in tts_jobs:
        name = _clean_text(_json_dict(job.extra_data).get("voice_character_name"))
        if name:
            return name

    extra = _json_dict(shot.extra_data)
    for key in ("dialogue_speaker", "speaker"):
        name = _clean_text(extra.get(key))
        if name:
            return name
    for refs in (
        shot.character_refs,
        extra.get("character_refs"),
        extra.get("characters"),
        _json_dict(extra.get("entity_refs")).get("characters"),
    ):
        name = _character_name_from_refs(refs)
        if name:
            return name

    dialogue = _clean_text(shot.dialogue) or _clean_text(extra.get("subtitle_text"))
    if dialogue:
        for separator in ("：", ":"):
            if separator in dialogue:
                speaker = dialogue.split(separator, 1)[0].strip()
                if speaker and len(speaker) <= 30:
                    return speaker
    return None


@router.get("/novels/{novel_id}/production-pack", response_model=Dict[str, Any])
async def get_novel_production_pack(
    novel_id: str,
    create_missing_assets: bool = Query(False, description="GET 默认不创建资产，设为 true 可补占位"),
    persist: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """生成或读取小说级资产定稿包。"""
    return await build_novel_production_pack(
        db,
        user_id,
        novel_id,
        create_missing_assets=create_missing_assets,
        persist=persist,
    )


@router.post("/novels/{novel_id}/production-pack", response_model=Dict[str, Any])
async def create_novel_production_pack(
    novel_id: str,
    request: ProductionPackRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """创建并保存小说级资产定稿包。"""
    return await build_novel_production_pack(
        db,
        user_id,
        novel_id,
        create_missing_assets=request.create_missing_assets,
        persist=request.persist,
    )


@router.get("/workflow/{workflow_id}/voice-lock-stats", response_model=Dict[str, Any])
async def get_workflow_voice_lock_stats(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """统计工作流对白镜头的故事圣经音色锁命中率。"""
    workflow_result = await db.execute(select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user_id))
    workflow = workflow_result.scalar_one_or_none()
    if workflow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工作流不存在")

    shots: list[Shot] = []
    if workflow.storyboard_id:
        shot_result = await db.execute(
            select(Shot)
            .where(Shot.user_id == user_id, Shot.storyboard_id == workflow.storyboard_id)
            .order_by(Shot.shot_number)
        )
        shots = list(shot_result.scalars().all())

    dialogue_shots = [shot for shot in shots if has_dialogue_text(shot)]
    shot_ids = [shot.id for shot in dialogue_shots]
    current_tts_by_shot: dict[str, TTSJob] = {}
    latest_tts_ids_by_shot = {
        shot.id: latest_tts_job_id
        for shot in dialogue_shots
        if (latest_tts_job_id := _clean_text(_json_dict(shot.extra_data).get("latest_tts_job_id")))
    }
    if latest_tts_ids_by_shot:
        latest_tts_result = await db.execute(
            select(TTSJob).where(
                TTSJob.user_id == user_id,
                TTSJob.workflow_id == workflow.id,
                TTSJob.id.in_(latest_tts_ids_by_shot.values()),
                TTSJob.is_active == True,
            )
        )
        latest_jobs_by_id = {job.id: job for job in latest_tts_result.scalars().all()}
        for shot_id, latest_tts_job_id in latest_tts_ids_by_shot.items():
            job = latest_jobs_by_id.get(latest_tts_job_id)
            if job and job.shot_id == shot_id:
                current_tts_by_shot[shot_id] = job

    fallback_shot_ids = [shot_id for shot_id in shot_ids if shot_id not in current_tts_by_shot]
    workflow_tts_job_ids = [str(job_id) for job_id in (workflow.tts_job_ids or []) if job_id]
    if fallback_shot_ids and workflow_tts_job_ids:
        filters = [
            TTSJob.user_id == user_id,
            TTSJob.workflow_id == workflow.id,
            TTSJob.shot_id.in_(fallback_shot_ids),
            TTSJob.is_active == True,
            TTSJob.id.in_(workflow_tts_job_ids),
        ]
        tts_result = await db.execute(
            select(TTSJob)
            .where(*filters)
            .order_by(TTSJob.created_at.desc())
        )
        for job in tts_result.scalars().all():
            if job.shot_id in fallback_shot_ids and job.shot_id not in current_tts_by_shot:
                current_tts_by_shot[job.shot_id] = job

    voice_locked = 0
    misses: list[Dict[str, Any]] = []
    for shot in dialogue_shots:
        current_tts_job = current_tts_by_shot.get(shot.id)
        shot_tts_jobs = [current_tts_job] if current_tts_job else []
        if current_tts_job and _tts_job_has_story_bible_voice_lock(current_tts_job):
            voice_locked += 1
            continue

        misses.append(
            {
                "shot_id": shot.id,
                "shot_number": shot.shot_number,
                "character_name": _best_effort_character_name(shot, shot_tts_jobs),
            }
        )

    total = len(dialogue_shots)
    return {
        "workflow_id": workflow.id,
        "total_dialogue_shots": total,
        "voice_locked": voice_locked,
        "hit_rate": round(voice_locked / total, 2) if total else 0.0,
        "misses": misses,
    }


@router.post("/workflow/{workflow_id}/asset-locks", response_model=Dict[str, Any])
async def create_workflow_asset_locks(
    workflow_id: str,
    request: WorkflowAssetLocksRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """把小说定稿包中的资产锁应用到工作流镜头。"""
    return await apply_asset_locks_to_workflow(
        db,
        user_id,
        workflow_id,
        persist=request.persist,
        create_missing_assets=request.create_missing_assets,
    )


@router.post("/workflow/{workflow_id}/media-audit", response_model=Dict[str, Any])
async def create_workflow_media_audit(
    workflow_id: str,
    request: MediaAuditRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """巡检并可选转存工作流媒体历史。"""
    return await audit_and_persist_workflow_media(
        db,
        user_id,
        workflow_id,
        persist_remote=request.persist_remote,
        dry_run=request.dry_run,
    )


@router.post("/workflow/{workflow_id}/quality-check", response_model=Dict[str, Any])
async def create_workflow_quality_check(
    workflow_id: str,
    request: QualityCheckRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """执行工作流生产质量检查。"""
    return await build_workflow_quality_report(
        db,
        user_id,
        workflow_id,
        persist=request.persist,
    )


@router.post("/workflow/{workflow_id}/producer-assistant", response_model=Dict[str, Any])
async def create_producer_assistant(
    workflow_id: str,
    request: ProducerAssistantRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """AI 制片助手：判断缺失项、推荐下一步，并可自动补齐安全项。"""
    return await build_ai_producer_assistant(
        db,
        user_id,
        workflow_id,
        auto_fix=request.auto_fix,
        action_code=request.action_code,
    )
