"""
镜头管理 API 端点
"""
import asyncio
import uuid
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models import Shot, Storyboard

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
    created_at: str
    updated_at: str


async def get_storyboard_for_user(db: AsyncSession, storyboard_id: str, user_id: str):
    from app.models import Storyboard

    result = await db.execute(
        select(Storyboard).where(and_(Storyboard.id == storyboard_id, Storyboard.user_id == user_id))
    )
    storyboard = result.scalar_one_or_none()
    if storyboard is None:
        raise HTTPException(status_code=404, detail="分镜不存在")
    return storyboard


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
        created_at=str(shot.created_at),
        updated_at=str(shot.updated_at),
    )


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


@router.post("", response_model=ShotResponse, status_code=status.HTTP_201_CREATED)
async def create_shot(
    shot: ShotCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """创建镜头"""
    storyboard = await get_storyboard_for_user(db, shot.storyboard_id, user_id)

    shot_id = str(uuid.uuid4())

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
    shot_kwargs["character_refs"] = shot.character_refs
    shot_kwargs["version"] = 1
    db_shot = Shot(**shot_kwargs)

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


@router.put("/reorder")
async def reorder_shots(
    storyboard_id: str,
    shot_ids: List[str],
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """批量重排镜头顺序"""
    storyboard = await get_storyboard_for_user(db, storyboard_id, user_id)

    for idx, shot_id in enumerate(shot_ids):
        result = await db.execute(
            select(Shot).where(and_(Shot.id == shot_id, Shot.user_id == user_id))
        )
        db_shot = result.scalar_one_or_none()
        if db_shot:
            db_shot.shot_number = idx + 1

    await db.commit()
    return {"message": "镜头顺序已更新"}


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
        shot_kwargs["character_refs"] = shot_data.character_refs
        shot_kwargs["version"] = 1
        db_shot = Shot(**shot_kwargs)
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

    # Build prompt (include lighting and color_grading for better results)
    prompt_parts = []
    if shot.visual_description:
        prompt_parts.append(shot.visual_description)
    if shot.prompt:
        prompt_parts.append(shot.prompt)
    if shot.camera_angle:
        prompt_parts.append(f"camera: {shot.camera_angle}")
    if shot.emotion:
        prompt_parts.append(f"emotion: {shot.emotion}")
    if shot.lighting:
        prompt_parts.append(f"lighting: {shot.lighting}")
    if shot.color_grading:
        prompt_parts.append(f"color grading: {shot.color_grading}")
    prompt = " ".join(prompt_parts) if prompt_parts else shot.visual_description or shot.prompt or "cinematic scene"

    # Get API key and call image generation service
    api_key = await get_user_volcano_api_key(db, user_id)
    volcano = VolcanoService(api_key)
    result = await volcano.generate_image(prompt=prompt)
    task_id = result.get("id") or result.get("task_id", str(uuid.uuid4()))

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
            extra_data={"shot_id": shot_id},
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
