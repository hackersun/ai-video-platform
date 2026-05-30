"""
镜头管理 API 端点
"""
from app.core.time_utils import utc_now
import asyncio
import uuid
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.dev_generation import dev_image_url, is_dev_mode
from app.services.shot_quality_service import build_shot_quality_report, estimate_shot_generation_budget
from app.core.security import get_current_user_id
from app.models import Asset, Chapter, Script, Shot, StoryEntity, Storyboard
from app.services.consistency_context import build_consistency_prompt, build_shot_entity_context

router = APIRouter(tags=["镜头管理"])


# ============== Pydantic 模型 ==============

class ShotCreate(BaseModel):
    """创建镜头请求"""
    storyboard_id: str = Field(..., description="所属分镜ID")
    shot_number: int = Field(..., description="镜头序号")
    duration: Optional[int] = Field(4, description="镜头时长（秒）")
    prompt: str = Field(..., description="视频生成Prompt")
    dialogue: Optional[str] = Field(None, description="台词")
    visual_description: Optional[str] = Field(None, description="视觉描述")
    camera_angle: Optional[str] = Field(None, description="镜头角度")
    # 精细化字段
    camera_movement: Optional[str] = Field(None, description="运镜方式")
    movement_speed: Optional[float] = Field(1.0, ge=0.1, le=4.0)
    emotion: Optional[str] = Field(None, description="情绪")
    emotion_intensity: Optional[float] = Field(0.5, ge=0, le=1)
    lighting: Optional[str] = Field(None, description="光线")
    color_grading: Optional[str] = Field(None, description="调色")
    music_cue: Optional[str] = Field(None, description="配乐提示")
    sfx_cue: Optional[str] = Field(None, description="音效提示")
    keyframes: Optional[List[dict]] = Field(None, description="关键帧列表")
    character_refs: Optional[List[dict]] = Field(None, description="角色引用")


class ShotUpdate(BaseModel):
    """更新镜头请求"""
    shot_number: Optional[int] = None
    duration: Optional[int] = None
    prompt: Optional[str] = None
    dialogue: Optional[str] = None
    visual_description: Optional[str] = None
    camera_angle: Optional[str] = None
    video_url: Optional[str] = None
    audio_url: Optional[str] = None
    video_status: Optional[str] = None
    audio_status: Optional[str] = None
    # 精细化字段
    camera_movement: Optional[str] = None
    movement_speed: Optional[float] = None
    movement_start_pos: Optional[str] = None
    movement_end_pos: Optional[str] = None
    emotion: Optional[str] = None
    emotion_intensity: Optional[float] = None
    lighting: Optional[str] = None
    color_grading: Optional[str] = None
    music_cue: Optional[str] = None
    sfx_cue: Optional[str] = None
    ambient_sound: Optional[str] = None
    keyframes: Optional[List[dict]] = None
    version: Optional[int] = None
    version_note: Optional[str] = None
    character_refs: Optional[List[dict]] = None
    extra_data: Optional[dict] = None


class ShotReorderRequest(BaseModel):
    """重排镜头请求"""
    shot_ids: List[str] = Field(..., min_length=1, description="按新顺序排列的镜头ID")


class ShotResponse(BaseModel):
    """镜头响应"""
    id: str
    storyboard_id: str
    user_id: str
    storyboard_title: Optional[str] = None
    shot_number: int
    duration: int
    prompt: Optional[str] = None
    dialogue: Optional[str] = None
    visual_description: Optional[str] = None
    camera_angle: Optional[str] = None
    video_url: Optional[str] = None
    audio_url: Optional[str] = None
    video_status: str
    audio_status: str
    image_url: Optional[str] = None
    image_status: Optional[str] = None
    image_asset_id: Optional[str] = None
    # 精细化字段
    camera_movement: Optional[str] = None
    movement_speed: Optional[float] = None
    movement_start_pos: Optional[str] = None
    movement_end_pos: Optional[str] = None
    emotion: Optional[str] = None
    emotion_intensity: Optional[float] = None
    lighting: Optional[str] = None
    color_grading: Optional[str] = None
    music_cue: Optional[str] = None
    sfx_cue: Optional[str] = None
    ambient_sound: Optional[str] = None
    keyframes: Optional[List[dict]] = None
    version: Optional[int] = None
    parent_shot_id: Optional[str] = None
    version_note: Optional[str] = None
    character_refs: Optional[List[dict]] = None
    extra_data: Optional[dict] = None
    created_at: str
    updated_at: str


class AssetVersionLock(BaseModel):
    asset_id: str = Field(..., description="锁定的资产ID")
    role: str = Field("reference", description="用途: character_front/character_side/scene/prop/keyframe/reference")
    version: Optional[int] = Field(None, description="资产版本号")
    name: Optional[str] = None
    url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    locked_at: Optional[str] = None
    notes: Optional[str] = None


class ShotProductionContextUpdate(BaseModel):
    asset_version_locks: Optional[List[AssetVersionLock]] = Field(None, description="资产版本锁")
    keyframes: Optional[List[dict]] = Field(None, description="关键帧 start/end/reference 控制")
    character_multiview_refs: Optional[List[dict]] = Field(None, description="角色正面/侧面/背面/表情参考")
    entity_reference_bindings: Optional[List[dict]] = Field(None, description="镜头绑定的角色/场景/道具/事件实体引用")
    lip_sync: Optional[dict] = Field(None, description="口型/唇形配置")
    review_state: Optional[str] = Field(None, description="pending_review/changes_requested/approved")
    review_notes: Optional[str] = None
    review_assignees: Optional[List[str]] = None
    provider_hints: Optional[dict] = Field(None, description="Sora/Veo/ComfyUI/FFmpeg 等适配提示")


class ShotProductionContextResponse(BaseModel):
    shot_id: str
    production_context: dict


class ShotQualityResponse(BaseModel):
    shot_id: str
    quality_report: dict
    budget_estimate: dict


class ShotQualityBatchRequest(BaseModel):
    shot_ids: List[str] = Field(..., min_length=1, max_length=100, description="需要重检的镜头ID")


class ShotQualityBatchItem(BaseModel):
    shot_id: str
    quality_report: dict
    budget_estimate: dict


class ShotQualityBatchResponse(BaseModel):
    total: int
    refreshed: int
    missing_ids: List[str]
    items: List[ShotQualityBatchItem]


async def get_storyboard_for_user(db: AsyncSession, storyboard_id: str, user_id: str):
    from app.models import Storyboard

    result = await db.execute(
        select(Storyboard).where(and_(Storyboard.id == storyboard_id, Storyboard.user_id == user_id))
    )
    storyboard = result.scalar_one_or_none()
    if storyboard is None:
        raise HTTPException(status_code=404, detail="分镜不存在")
    return storyboard


def _json_dict(value):
    return value if isinstance(value, dict) else {}


def _shot_text_from_values(*values: Optional[str]) -> str:
    return " ".join(value for value in values if value)


async def _source_text_for_storyboard(db: AsyncSession, storyboard: Storyboard, user_id: str) -> tuple[Optional[str], Optional[str]]:
    content = _json_dict(storyboard.content)
    chapter_id = content.get("chapter_id")
    if chapter_id:
        chapter_result = await db.execute(
            select(Chapter).where(and_(Chapter.id == chapter_id, Chapter.user_id == user_id))
        )
        chapter = chapter_result.scalar_one_or_none()
        if chapter:
            return chapter.id, chapter.content or chapter.title

    script_result = await db.execute(
        select(Script).where(and_(Script.id == storyboard.script_id, Script.user_id == user_id))
    )
    script = script_result.scalar_one_or_none()
    return chapter_id, script.content if script else None


async def _build_manual_shot_extra_data(
    db: AsyncSession,
    user_id: str,
    storyboard: Storyboard,
    *,
    shot_text: str,
    dialogue: Optional[str],
    existing_extra_data: Optional[dict] = None,
) -> tuple[dict, list[dict]]:
    chapter_id, source_text = await _source_text_for_storyboard(db, storyboard, user_id)
    entity_context = await build_shot_entity_context(
        db,
        user_id,
        novel_id=storyboard.novel_id,
        chapter_id=chapter_id,
        source_text=source_text,
        shot_text=shot_text,
    )
    extra_data = {
        **(existing_extra_data or {}),
        "entity_refs": entity_context["entity_refs"],
        "scene_refs": entity_context["scene_refs"],
        "prop_refs": entity_context["prop_refs"],
        "event_refs": entity_context["event_refs"],
        "environment_context": entity_context["environment_context"],
        "subtitle_text": (existing_extra_data or {}).get("subtitle_text") or dialogue,
    }
    return extra_data, entity_context["character_refs"]


async def _resolve_asset_locks(
    db: AsyncSession,
    user_id: str,
    locks: Optional[List[AssetVersionLock]],
) -> List[dict]:
    if not locks:
        return []

    resolved: List[dict] = []
    for lock in locks:
        result = await db.execute(select(Asset).where(Asset.id == lock.asset_id, Asset.is_active == True))
        asset = result.scalar_one_or_none()
        if asset is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"资产不存在: {lock.asset_id}")
        if not asset.is_public and asset.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"无权锁定资产: {lock.asset_id}")
        resolved.append(
            {
                "asset_id": asset.id,
                "role": lock.role,
                "version": lock.version or asset.usage_count or 1,
                "name": lock.name or asset.name,
                "url": lock.url or asset.url,
                "thumbnail_url": lock.thumbnail_url or asset.thumbnail_url,
                "locked_at": lock.locked_at or utc_now().isoformat(),
                "notes": lock.notes,
                "asset_updated_at": str(asset.updated_at),
                "asset_type": asset.asset_type,
                "category": asset.category,
            }
        )
    return resolved


async def _resolve_entity_reference_bindings(
    db: AsyncSession,
    user_id: str,
    bindings: Optional[List[dict]],
) -> List[dict]:
    if not bindings:
        return []

    entity_ids = [
        str(binding.get("entity_id"))
        for binding in bindings
        if isinstance(binding, dict) and binding.get("entity_id")
    ]
    if not entity_ids:
        return []

    result = await db.execute(
        select(StoryEntity).where(StoryEntity.id.in_(entity_ids), StoryEntity.user_id == user_id)
    )
    entities = {entity.id: entity for entity in result.scalars().all()}
    missing = [entity_id for entity_id in entity_ids if entity_id not in entities]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"实体不存在或无权限: {', '.join(missing)}",
        )

    resolved = []
    for binding in bindings:
        if not isinstance(binding, dict) or not binding.get("entity_id"):
            continue
        entity = entities[str(binding["entity_id"])]
        attrs = entity.attributes if isinstance(entity.attributes, dict) else {}
        resolved.append({
            **binding,
            "entity_id": entity.id,
            "entity_type": entity.entity_type,
            "name": entity.name,
            "description": entity.description,
            "visual_dna": attrs.get("visual_dna") or attrs.get("prop_dna") or attrs.get("scene_dna") or {},
            "asset_pack": attrs.get("asset_pack") or attrs.get("reference_assets") or {},
        })
    return resolved


def build_shot_response(shot: Shot, storyboard_title: Optional[str] = None) -> ShotResponse:
    return ShotResponse(
        id=str(shot.id),
        storyboard_id=str(shot.storyboard_id),
        user_id=str(shot.user_id),
        storyboard_title=storyboard_title,
        shot_number=shot.shot_number or 1,
        duration=shot.duration or 4,
        prompt=shot.prompt,
        dialogue=shot.dialogue,
        visual_description=shot.visual_description,
        camera_angle=shot.camera_angle,
        video_url=shot.video_url,
        audio_url=shot.audio_url,
        video_status=shot.video_status or "pending",
        audio_status=shot.audio_status or "pending",
        image_url=shot.image_url,
        image_status=shot.image_status,
        image_asset_id=str(shot.image_asset_id) if shot.image_asset_id else None,
        camera_movement=shot.camera_movement,
        movement_speed=shot.movement_speed,
        movement_start_pos=shot.movement_start_pos,
        movement_end_pos=shot.movement_end_pos,
        emotion=shot.emotion,
        emotion_intensity=shot.emotion_intensity,
        lighting=shot.lighting,
        color_grading=shot.color_grading,
        music_cue=shot.music_cue,
        sfx_cue=shot.sfx_cue,
        ambient_sound=shot.ambient_sound,
        keyframes=shot.keyframes,
        version=shot.version,
        parent_shot_id=str(shot.parent_shot_id) if shot.parent_shot_id else None,
        version_note=shot.version_note,
        character_refs=shot.character_refs,
        extra_data=shot.extra_data,
        created_at=str(shot.created_at),
        updated_at=str(shot.updated_at),
    )


def _refresh_shot_quality_payload(shot: Shot) -> tuple[dict, dict]:
    quality_report = build_shot_quality_report(shot)
    budget_estimate = estimate_shot_generation_budget(shot)
    extra_data = dict(_json_dict(shot.extra_data))
    extra_data["quality_report"] = quality_report
    extra_data["budget_estimate"] = budget_estimate
    shot.extra_data = extra_data
    shot.updated_at = utc_now()
    return quality_report, budget_estimate


# ============== API 端点 ==============

@router.get("/storyboard/{storyboard_id}", response_model=List[ShotResponse])
async def list_shots_by_storyboard(
    storyboard_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取指定分镜的所有镜头"""
    storyboard = await get_storyboard_for_user(db, storyboard_id, user_id)

    result = await db.execute(
        select(Shot)
        .where(and_(Shot.storyboard_id == storyboard_id, Shot.user_id == user_id))
        .order_by(Shot.shot_number)
    )
    shots = result.scalars().all()

    return [build_shot_response(shot, storyboard.title) for shot in shots]


@router.put("/reorder")
async def reorder_shots(
    storyboard_id: str,
    request: ShotReorderRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """批量重排镜头顺序"""
    await get_storyboard_for_user(db, storyboard_id, user_id)

    for idx, shot_id in enumerate(request.shot_ids):
        result = await db.execute(
            select(Shot).where(
                and_(
                    Shot.id == shot_id,
                    Shot.storyboard_id == storyboard_id,
                    Shot.user_id == user_id,
                )
            )
        )
        db_shot = result.scalar_one_or_none()
        if db_shot:
            db_shot.shot_number = idx + 1

    await db.commit()
    return {"message": "镜头顺序已更新"}


@router.get("/{shot_id}", response_model=ShotResponse)
async def get_shot(
    shot_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取单个镜头"""
    result = await db.execute(
        select(Shot).where(and_(Shot.id == shot_id, Shot.user_id == user_id))
    )
    shot = result.scalar_one_or_none()

    if not shot:
        raise HTTPException(status_code=404, detail="镜头不存在")

    storyboard = await get_storyboard_for_user(db, shot.storyboard_id, user_id)
    return build_shot_response(shot, storyboard.title)


@router.get("/{shot_id}/production-context", response_model=ShotProductionContextResponse)
async def get_shot_production_context(
    shot_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取镜头的可选生产适配上下文。"""
    result = await db.execute(select(Shot).where(and_(Shot.id == shot_id, Shot.user_id == user_id)))
    shot = result.scalar_one_or_none()
    if not shot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="镜头不存在")
    extra_data = _json_dict(shot.extra_data)
    return ShotProductionContextResponse(
        shot_id=shot.id,
        production_context=extra_data.get("production_context") or {},
    )


@router.get("/{shot_id}/quality", response_model=ShotQualityResponse)
async def get_shot_quality(
    shot_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取镜头的质量检查和预算估算。"""
    result = await db.execute(select(Shot).where(and_(Shot.id == shot_id, Shot.user_id == user_id)))
    shot = result.scalar_one_or_none()
    if not shot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="镜头不存在")
    return ShotQualityResponse(
        shot_id=shot.id,
        quality_report=build_shot_quality_report(shot),
        budget_estimate=estimate_shot_generation_budget(shot),
    )


@router.post("/quality/batch", response_model=ShotQualityBatchResponse)
async def refresh_shots_quality_batch(
    request: ShotQualityBatchRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """批量重新计算镜头质量检查和预算估算，并写回 extra_data。"""
    unique_shot_ids = list(dict.fromkeys(request.shot_ids))
    result = await db.execute(select(Shot).where(and_(Shot.id.in_(unique_shot_ids), Shot.user_id == user_id)))
    shots = result.scalars().all()
    shot_map = {shot.id: shot for shot in shots}
    items: List[ShotQualityBatchItem] = []

    for shot_id in unique_shot_ids:
        shot = shot_map.get(shot_id)
        if shot is None:
            continue
        quality_report, budget_estimate = _refresh_shot_quality_payload(shot)
        items.append(
            ShotQualityBatchItem(
                shot_id=shot.id,
                quality_report=quality_report,
                budget_estimate=budget_estimate,
            )
        )

    if items:
        await db.commit()

    return ShotQualityBatchResponse(
        total=len(unique_shot_ids),
        refreshed=len(items),
        missing_ids=[shot_id for shot_id in unique_shot_ids if shot_id not in shot_map],
        items=items,
    )


@router.post("/{shot_id}/quality", response_model=ShotQualityResponse)
async def refresh_shot_quality(
    shot_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """重新计算镜头质量检查和预算估算，并写回 extra_data。"""
    result = await db.execute(select(Shot).where(and_(Shot.id == shot_id, Shot.user_id == user_id)))
    shot = result.scalar_one_or_none()
    if not shot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="镜头不存在")
    quality_report, budget_estimate = _refresh_shot_quality_payload(shot)
    await db.commit()
    await db.refresh(shot)
    return ShotQualityResponse(
        shot_id=shot.id,
        quality_report=quality_report,
        budget_estimate=budget_estimate,
    )


@router.put("/{shot_id}/production-context", response_model=ShotProductionContextResponse)
async def update_shot_production_context(
    shot_id: str,
    request: ShotProductionContextUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """更新镜头的资产锁、关键帧、多视图角色参考、口型和审核状态。"""
    result = await db.execute(select(Shot).where(and_(Shot.id == shot_id, Shot.user_id == user_id)))
    shot = result.scalar_one_or_none()
    if not shot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="镜头不存在")

    extra_data = _json_dict(shot.extra_data)
    production_context = dict(extra_data.get("production_context") or {})
    if request.asset_version_locks is not None:
        production_context["asset_version_locks"] = await _resolve_asset_locks(db, user_id, request.asset_version_locks)
    if request.keyframes is not None:
        shot.keyframes = request.keyframes
        production_context["keyframes"] = request.keyframes
    if request.character_multiview_refs is not None:
        production_context["character_multiview_refs"] = request.character_multiview_refs
    if request.entity_reference_bindings is not None:
        production_context["entity_reference_bindings"] = await _resolve_entity_reference_bindings(
            db,
            user_id,
            request.entity_reference_bindings,
        )
    if request.lip_sync is not None:
        production_context["lip_sync"] = request.lip_sync
    if request.review_state is not None:
        if request.review_state not in {"pending_review", "changes_requested", "approved", "locked"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="review_state 仅支持 pending_review/changes_requested/approved/locked",
            )
        production_context["review_state"] = request.review_state
    if request.review_notes is not None:
        production_context["review_notes"] = request.review_notes
    if request.review_assignees is not None:
        production_context["review_assignees"] = request.review_assignees
    if request.provider_hints is not None:
        production_context["provider_hints"] = request.provider_hints

    production_context["updated_at"] = utc_now().isoformat()
    extra_data["production_context"] = production_context
    shot.extra_data = extra_data
    _refresh_shot_quality_payload(shot)
    shot.updated_at = utc_now()
    await db.commit()
    await db.refresh(shot)
    return ShotProductionContextResponse(shot_id=shot.id, production_context=production_context)


@router.post("", response_model=ShotResponse, status_code=status.HTTP_201_CREATED)
async def create_shot(
    shot: ShotCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """创建镜头"""
    storyboard = await get_storyboard_for_user(db, shot.storyboard_id, user_id)

    shot_id = str(uuid.uuid4())
    shot_text = _shot_text_from_values(shot.prompt, shot.dialogue, shot.visual_description, shot.sfx_cue, shot.music_cue)
    extra_data, inferred_character_refs = await _build_manual_shot_extra_data(
        db,
        user_id,
        storyboard,
        shot_text=shot_text,
        dialogue=shot.dialogue,
    )

    shot_kwargs = {
        "id": shot_id,
        "storyboard_id": shot.storyboard_id,
        "user_id": user_id,
        "shot_number": shot.shot_number,
        "duration": shot.duration or 4,
        "prompt": shot.prompt,
        "dialogue": shot.dialogue,
        "visual_description": shot.visual_description,
        "camera_angle": shot.camera_angle,
        "video_status": "pending",
        "audio_status": "pending",
        "extra_data": extra_data,
    }
    # 精细化字段
    shot_kwargs["camera_movement"] = shot.camera_movement
    shot_kwargs["movement_speed"] = shot.movement_speed or 1.0
    shot_kwargs["emotion"] = shot.emotion
    shot_kwargs["emotion_intensity"] = shot.emotion_intensity or 0.5
    shot_kwargs["lighting"] = shot.lighting
    shot_kwargs["color_grading"] = shot.color_grading
    shot_kwargs["music_cue"] = shot.music_cue
    shot_kwargs["sfx_cue"] = shot.sfx_cue
    shot_kwargs["keyframes"] = shot.keyframes
    shot_kwargs["character_refs"] = shot.character_refs or inferred_character_refs
    shot_kwargs["version"] = 1
    db_shot = Shot(**shot_kwargs)
    _refresh_shot_quality_payload(db_shot)

    db.add(db_shot)
    await db.commit()
    await db.refresh(db_shot)

    return build_shot_response(db_shot, storyboard.title)


@router.put("/{shot_id}", response_model=ShotResponse)
async def update_shot(
    shot_id: str,
    shot_update: ShotUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """更新镜头"""
    result = await db.execute(
        select(Shot).where(and_(Shot.id == shot_id, Shot.user_id == user_id))
    )
    db_shot = result.scalar_one_or_none()

    if not db_shot:
        raise HTTPException(status_code=404, detail="镜头不存在")

    update_data = shot_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_shot, key, value)

    if any(key in update_data for key in ("prompt", "dialogue", "visual_description", "music_cue", "sfx_cue", "character_refs")):
        storyboard = await get_storyboard_for_user(db, db_shot.storyboard_id, user_id)
        shot_text = _shot_text_from_values(
            db_shot.prompt,
            db_shot.dialogue,
            db_shot.visual_description,
            db_shot.sfx_cue,
            db_shot.music_cue,
        )
        extra_data, inferred_character_refs = await _build_manual_shot_extra_data(
            db,
            user_id,
            storyboard,
            shot_text=shot_text,
            dialogue=db_shot.dialogue,
            existing_extra_data=_json_dict(db_shot.extra_data),
        )
        db_shot.extra_data = extra_data
        if not db_shot.character_refs:
            db_shot.character_refs = inferred_character_refs

    _refresh_shot_quality_payload(db_shot)

    await db.commit()
    await db.refresh(db_shot)

    storyboard = await get_storyboard_for_user(db, db_shot.storyboard_id, user_id)
    return build_shot_response(db_shot, storyboard.title)


@router.delete("/{shot_id}")
async def delete_shot(
    shot_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """删除镜头"""
    result = await db.execute(
        select(Shot).where(and_(Shot.id == shot_id, Shot.user_id == user_id))
    )
    db_shot = result.scalar_one_or_none()

    if not db_shot:
        raise HTTPException(status_code=404, detail="镜头不存在")

    await db.delete(db_shot)
    await db.commit()

    return {"message": "镜头已删除"}


@router.post("/batch", response_model=List[ShotResponse], status_code=status.HTTP_201_CREATED)
async def create_shots_batch(
    storyboard_id: str,
    shots: List[ShotCreate],
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """批量创建镜头"""
    storyboard = await get_storyboard_for_user(db, storyboard_id, user_id)

    created_shots = []

    for shot_data in shots:
        if shot_data.storyboard_id != storyboard_id:
            raise HTTPException(status_code=422, detail="请求体中的storyboard_id必须与查询参数一致")

        shot_id = str(uuid.uuid4())
        shot_kwargs = {
            "id": shot_id,
            "storyboard_id": storyboard_id,
            "user_id": user_id,
            "shot_number": shot_data.shot_number,
            "duration": shot_data.duration or 4,
            "prompt": shot_data.prompt,
            "dialogue": shot_data.dialogue,
            "visual_description": shot_data.visual_description,
            "camera_angle": shot_data.camera_angle,
            "video_status": "pending",
            "audio_status": "pending",
        }
        shot_text = _shot_text_from_values(
            shot_data.prompt,
            shot_data.dialogue,
            shot_data.visual_description,
            shot_data.sfx_cue,
            shot_data.music_cue,
        )
        extra_data, inferred_character_refs = await _build_manual_shot_extra_data(
            db,
            user_id,
            storyboard,
            shot_text=shot_text,
            dialogue=shot_data.dialogue,
        )
        shot_kwargs["extra_data"] = extra_data
        # 精细化字段
        shot_kwargs["camera_movement"] = shot_data.camera_movement
        shot_kwargs["movement_speed"] = shot_data.movement_speed or 1.0
        shot_kwargs["emotion"] = shot_data.emotion
        shot_kwargs["emotion_intensity"] = shot_data.emotion_intensity or 0.5
        shot_kwargs["lighting"] = shot_data.lighting
        shot_kwargs["color_grading"] = shot_data.color_grading
        shot_kwargs["music_cue"] = shot_data.music_cue
        shot_kwargs["sfx_cue"] = shot_data.sfx_cue
        shot_kwargs["keyframes"] = shot_data.keyframes
        shot_kwargs["character_refs"] = shot_data.character_refs or inferred_character_refs
        shot_kwargs["version"] = 1
        db_shot = Shot(**shot_kwargs)
        _refresh_shot_quality_payload(db_shot)
        db.add(db_shot)
        created_shots.append(db_shot)

    await db.commit()

    return [build_shot_response(s, storyboard.title) for s in created_shots]


@router.post("/{shot_id}/generate-image")
async def generate_shot_image(
    shot_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """为指定镜头生成参考图"""
    from sqlalchemy import select, and_
    from app.services.volcano_service import VolcanoService
    from app.core.api_key_utils import get_user_volcano_api_key
    from app.models.asset import Asset

    result = await db.execute(
        select(Shot).where(and_(Shot.id == shot_id, Shot.user_id == user_id))
    )
    shot = result.scalar_one_or_none()
    if not shot:
        raise HTTPException(status_code=404, detail="镜头不存在")

    context = await build_consistency_prompt(
        db,
        user_id,
        task="scene_reference_image",
        base_prompt=shot.visual_description or shot.prompt or "cinematic scene",
        shot_id=shot_id,
        extra_context={
            "camera": shot.camera_angle,
            "emotion": shot.emotion,
            "lighting": shot.lighting,
            "color_grading": shot.color_grading,
        },
    )
    prompt = context["prompt"]

    # Get API key and call image generation service
    try:
        api_key = await get_user_volcano_api_key(db, user_id)
        volcano = VolcanoService(api_key)
        result = await volcano.generate_image(prompt=prompt)
        task_id = result.get("id") or result.get("task_id", str(uuid.uuid4()))
    except HTTPException:
        if not is_dev_mode():
            raise
        task_id = f"dev-shot-image-{shot_id}"
        result = {"data": [{"url": dev_image_url(shot_id, f"shot-{shot.shot_number}")}]}

    # Parse image URL from response
    image_url = None
    if "data" in result and result["data"]:
        items = result["data"]
        if isinstance(items, list) and len(items) > 0:
            first = items[0]
            if isinstance(first, dict) and first.get("url"):
                image_url = first.get("url")

    # Update shot status immediately
    if image_url:
        shot.image_url = image_url
        shot.image_status = "succeeded"

        # Create asset
        asset = Asset(
            id=str(uuid.uuid4()),
            user_id=user_id,
            category="scene",
            name=f"镜头{shot.shot_number}参考图",
            asset_type="image",
            url=image_url,
            generation_params={
                "shot_id": shot_id,
                "prompt": prompt,
                "consistency": context["metadata"],
            },
        )
        db.add(asset)
        shot.image_asset_id = asset.id
        await db.commit()
    else:
        # API returned but no image URL yet (edge case for async models)
        shot.image_status = "generating"
        await db.commit()
        # Start background poll with user_id - creates its own DB session
        from app.services.image_poll_service import poll_and_update_shot_image
        asyncio.create_task(poll_and_update_shot_image(shot_id, task_id, user_id))

    return {"shot_id": shot_id, "task_id": task_id, "status": shot.image_status}


# ============== 镜头质量检查 & 重试API ==============

class ShotQualityReportResponse(BaseModel):
    """增强版镜头质量报告响应"""
    shot_id: str
    shot_number: int
    score: int
    status: str
    issues: List[dict]
    blockers: List[str]
    warnings: List[str]
    suggestions: List[str]
    summary: Optional[dict] = None
    metadata: dict


class RetryResponse(BaseModel):
    """重试响应"""
    shot_id: str
    success: bool
    job_id: Optional[str] = None
    task_id: Optional[str] = None
    attempts: int
    message: str


class StoryboardQualitySummaryResponse(BaseModel):
    """分镜质量汇总响应"""
    storyboard_id: str
    storyboard_title: Optional[str] = None
    total_shots: int
    avg_score: float
    shots_by_status: dict
    error_count: int
    warning_count: int
    ready_count: int
    blocked_shots: List[dict]
    warning_shots: List[dict]


@router.get("/{shot_id}/quality-report", response_model=ShotQualityReportResponse)
async def get_shot_quality_report(
    shot_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    获取增强版镜头质量报告（使用新质量检查服务）

    返回详细的质量问题和评分
    """
    from app.services.shot_quality_service import ShotQualityService

    result = await db.execute(
        select(Shot).where(and_(Shot.id == shot_id, Shot.user_id == user_id))
    )
    shot = result.scalar_one_or_none()
    if not shot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="镜头不存在")

    service = ShotQualityService()
    report = service.check_shot_quality(shot)

    return ShotQualityReportResponse(
        shot_id=str(shot.id),
        shot_number=shot.shot_number or 1,
        score=report.score,
        status=report.status,
        issues=[issue.to_dict() for issue in report.issues],
        blockers=report.blockers,
        warnings=report.warnings,
        suggestions=report.suggestions,
        summary=report.summary,
        metadata=report.metadata,
    )


@router.post("/{shot_id}/retry", response_model=RetryResponse)
async def retry_shot_video(
    shot_id: str,
    max_attempts: Optional[int] = Query(None, description="最大重试次数，默认3"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    重试失败的视频生成

    最多重试3次（可配置），通过 VideoGenerateRequest 提交新任务
    """
    from app.services.shot_quality_service import ShotQualityService
    from app.api.v1.endpoints.video import VideoGenerateRequest, generate_video

    result = await db.execute(
        select(Shot).where(and_(Shot.id == shot_id, Shot.user_id == user_id))
    )
    shot = result.scalar_one_or_none()
    if not shot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="镜头不存在")

    service = ShotQualityService(max_retry=max_attempts or 3)

    if shot.video_status == "succeeded":
        return RetryResponse(
            shot_id=shot_id,
            success=True,
            job_id=None,
            task_id=None,
            attempts=0,
            message="视频已生成成功，无需重试"
        )

    extra_data = shot.extra_data if isinstance(shot.extra_data, dict) else {}
    retry_count = (extra_data.get("video_retry_count") or 0)

    if retry_count >= (max_attempts or service.max_retry):
        return RetryResponse(
            shot_id=shot_id,
            success=False,
            job_id=None,
            task_id=None,
            attempts=retry_count,
            message=f"已达最大重试次数({max_attempts or service.max_retry})，请手动检查问题"
        )

    prompt = shot.prompt or shot.visual_description or "shot video"
    request = VideoGenerateRequest(
        prompt=prompt,
        duration=shot.duration or 4,
        shot_id=shot_id,
        storyboard_id=shot.storyboard_id,
        image_url=shot.image_url,
        use_consistency_context=True,
    )

    try:
        response = await generate_video(request, db, user_id)

        extra_data["video_retry_count"] = retry_count + 1
        extra_data["retry_attempt"] = retry_count + 1
        shot.extra_data = extra_data
        shot.video_status = "pending"
        await db.commit()

        return RetryResponse(
            shot_id=shot_id,
            success=True,
            job_id=response.job_id,
            task_id=response.task_id,
            attempts=retry_count + 1,
            message="视频重试任务已提交"
        )
    except Exception as e:
        return RetryResponse(
            shot_id=shot_id,
            success=False,
            job_id=None,
            task_id=None,
            attempts=retry_count,
            message=f"视频重试失败: {str(e)}"
        )


@router.get("/storyboard/{storyboard_id}/quality-summary", response_model=StoryboardQualitySummaryResponse)
async def get_storyboard_quality_summary(
    storyboard_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    获取分镜质量汇总

    遍历所有镜头，计算平均分和各类问题统计
    """
    from app.services.shot_quality_service import build_storyboard_quality_summary

    storyboard = await get_storyboard_for_user(db, storyboard_id, user_id)

    result = await db.execute(
        select(Shot)
        .where(and_(Shot.storyboard_id == storyboard_id, Shot.user_id == user_id))
        .order_by(Shot.shot_number)
    )
    shots = result.scalars().all()

    summary = build_storyboard_quality_summary(storyboard_id, shots)

    return StoryboardQualitySummaryResponse(
        storyboard_id=storyboard_id,
        storyboard_title=storyboard.title,
        total_shots=summary.total_shots,
        avg_score=summary.avg_score,
        shots_by_status=summary.shots_by_status,
        error_count=summary.error_count,
        warning_count=summary.warning_count,
        ready_count=summary.ready_count,
        blocked_shots=summary.blocked_shots,
        warning_shots=summary.warning_shots,
    )


# ============== Prompt重建API ==============

class BatchRebuildPromptsRequest(BaseModel):
    """批量重建prompt请求"""
    use_locked_assets: bool = Field(True, description="是否锁定资产")
    use_entity_refs: bool = Field(True, description="是否重新填充实体引用")


class BatchRebuildPromptsResponse(BaseModel):
    """批量重建prompt响应"""
    status: str
    total_shots: int
    rebuilt_count: int
    skipped_count: int
    rebuilt_ids: List[str]
    skipped_ids: List[str]
    errors: List[dict]


class RebuildShotPromptResponse(BaseModel):
    """重建单个镜头prompt响应"""
    status: str
    shot_id: str
    prompt: str


@router.post("/shots/batch-rebuild-prompts")
async def batch_rebuild_consistency_prompts(
    storyboard_id: str = Body(..., description="分镜ID"),
    use_locked_assets: bool = Body(True, description="是否锁定资产"),
    use_entity_refs: bool = Body(True, description="是否重新填充实体引用"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """批量重新构建镜头的连贯性prompt"""
    # 验证分镜所有权
    result = await db.execute(
        select(Storyboard).where(and_(Storyboard.id == storyboard_id, Storyboard.user_id == user_id))
    )
    storyboard = result.scalar_one_or_none()
    if not storyboard:
        raise HTTPException(status_code=404, detail="分镜不存在")

    # 获取所有镜头
    shots_result = await db.execute(
        select(Shot).where(and_(Shot.storyboard_id == storyboard_id, Shot.user_id == user_id))
    )
    shots = list(shots_result.scalars().all())

    rebuilt = []
    skipped = []
    errors = []

    for shot in shots:
        try:
            # 重新填充entity_refs
            if use_entity_refs:
                from app.services.consistency_context import auto_fill_shot_entity_refs
                await auto_fill_shot_entity_refs(
                    db, shot, storyboard.novel_id, storyboard.chapter_id
                )

            # 锁定资产
            if use_locked_assets:
                from app.services.asset_lock_service import AssetLockService
                asset_service = AssetLockService()
                await asset_service.lock_shot_assets(db, shot)

            # 重新构建prompt
            context = await build_consistency_prompt(
                db=db,
                user_id=user_id,
                task="shot_video",
                story_bible_id=storyboard.story_bible_id,
                novel_id=storyboard.novel_id,
                shot_id=shot.id
            )
            new_prompt = context.get("prompt", "")

            if new_prompt:
                shot.prompt = new_prompt

            # 清除审查标记
            if shot.extra_data and isinstance(shot.extra_data, dict):
                shot.extra_data.pop("needs_review", None)
                shot.extra_data.pop("review_reason", None)
                shot.extra_data.pop("review_at", None)

            rebuilt.append(str(shot.id))

        except Exception as e:
            errors.append({"shot_id": str(shot.id), "error": str(e)})
            skipped.append(str(shot.id))

    if rebuilt:
        await db.commit()

    return {
        "status": "success",
        "total_shots": len(shots),
        "rebuilt_count": len(rebuilt),
        "skipped_count": len(skipped),
        "rebuilt_ids": rebuilt,
        "skipped_ids": skipped,
        "errors": errors
    }


@router.post("/{shot_id}/rebuild-prompt", response_model=RebuildShotPromptResponse)
async def rebuild_shot_prompt(
    shot_id: str,
    use_locked_assets: bool = True,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """重新构建单个镜头的连贯性prompt"""
    result = await db.execute(
        select(Shot).where(and_(Shot.id == shot_id, Shot.user_id == user_id))
    )
    shot = result.scalar_one_or_none()
    if not shot:
        raise HTTPException(status_code=404, detail="镜头不存在")

    # 获取storyboard
    storyboard = await get_storyboard_for_user(db, shot.storyboard_id, user_id)

    # 锁定资产
    if use_locked_assets:
        from app.services.asset_lock_service import AssetLockService
        asset_service = AssetLockService()
        await asset_service.lock_shot_assets(db, shot)

    # 重新构建prompt
    context = await build_consistency_prompt(
        db=db,
        user_id=user_id,
        task="shot_video",
        story_bible_id=storyboard.story_bible_id,
        novel_id=storyboard.novel_id,
        shot_id=shot.id
    )
    new_prompt = context.get("prompt", "")

    shot.prompt = new_prompt

    # 清除审查标记
    if shot.extra_data and isinstance(shot.extra_data, dict):
        shot.extra_data.pop("needs_review", None)
        shot.extra_data.pop("review_reason", None)
        shot.extra_data.pop("review_at", None)

    await db.commit()

    return {
        "status": "success",
        "shot_id": shot_id,
        "prompt": new_prompt
    }
