"""
时间线编辑 API 端点 - Timeline/Track/Clip CRUD
"""
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, desc, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.timeline import Timeline, Track, Clip
from app.models.project import Project

router = APIRouter(tags=["时间线编辑"])


# ========== Timeline 模型 ==========

class TimelineCreate(BaseModel):
    project_id: str = Field(..., description="所属项目ID")
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    fps: int = Field(24, ge=1, le=120)
    aspect_ratio: str = Field("16:9")
    video_track_count: int = Field(2, ge=1, le=10)
    audio_track_count: int = Field(3, ge=1, le=10)
    subtitle_track_count: int = Field(1, ge=0, le=5)


class TimelineUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    fps: Optional[int] = None
    aspect_ratio: Optional[str] = None
    status: Optional[str] = None
    thumbnail_url: Optional[str] = None
    preview_url: Optional[str] = None


class TimelineResponse(BaseModel):
    id: str
    project_id: str
    user_id: str
    name: str
    description: Optional[str] = None
    fps: int
    aspect_ratio: str
    total_duration: float
    width: int
    height: int
    video_track_count: int
    audio_track_count: int
    subtitle_track_count: int
    status: str
    is_active: bool
    is_default: bool
    thumbnail_url: Optional[str] = None
    preview_url: Optional[str] = None
    created_at: str
    updated_at: str


# ========== Track 模型 ==========

class TrackCreate(BaseModel):
    timeline_id: str
    track_type: str = Field(..., description="video/audio/subtitle/effect")
    track_index: int = Field(..., ge=0)
    name: Optional[str] = None
    is_locked: bool = False
    is_muted: bool = False


class TrackUpdate(BaseModel):
    name: Optional[str] = None
    track_index: Optional[int] = None
    is_locked: Optional[bool] = None
    is_muted: Optional[bool] = None
    is_hidden: Optional[bool] = None
    opacity: Optional[float] = None
    volume: Optional[float] = None
    effects: Optional[List[dict]] = None


class TrackResponse(BaseModel):
    id: str
    timeline_id: str
    track_type: str
    track_index: int
    name: Optional[str] = None
    is_locked: bool
    is_muted: bool
    is_hidden: bool
    opacity: float
    volume: float
    effects: Optional[List[dict]] = None


# ========== Clip 模型 ==========

class ClipCreate(BaseModel):
    timeline_id: str
    track_id: str
    source_type: str = Field(..., description="shot/asset/video_job/tts_job/synthesis_job/image")
    source_id: Optional[str] = None
    source_url: Optional[str] = None
    source_thumbnail: Optional[str] = None
    position: float = Field(0, ge=0)
    duration: float = Field(5, ge=0.1)
    name: Optional[str] = None
    speed: float = Field(1.0, ge=0.1, le=4.0)
    opacity: float = Field(1.0, ge=0, le=1)
    volume: float = Field(1.0, ge=0, le=2)
    in_point: float = Field(0, ge=0)
    out_point: Optional[float] = None
    position_x: float = Field(0, ge=-100, le=100)
    position_y: float = Field(0, ge=-100, le=100)
    scale: float = Field(1.0, ge=0.1, le=4.0)
    rotation: float = Field(0)
    transitions: Optional[dict] = None
    filters: Optional[List[dict]] = None
    keyframes: Optional[List[dict]] = None
    # 字幕字段
    text_content: Optional[str] = None
    font_family: Optional[str] = None
    font_size: Optional[int] = None
    font_color: Optional[str] = None


class ClipUpdate(BaseModel):
    track_id: Optional[str] = None
    position: Optional[float] = None
    duration: Optional[float] = None
    in_point: Optional[float] = None
    out_point: Optional[float] = None
    speed: Optional[float] = None
    opacity: Optional[float] = None
    volume: Optional[float] = None
    position_x: Optional[float] = None
    position_y: Optional[float] = None
    scale: Optional[float] = None
    rotation: Optional[float] = None
    transitions: Optional[dict] = None
    filters: Optional[List[dict]] = None
    keyframes: Optional[List[dict]] = None
    text_content: Optional[str] = None
    is_locked: Optional[bool] = None
    name: Optional[str] = None
    sort_order: Optional[int] = None


class ClipResponse(BaseModel):
    id: str
    timeline_id: str
    track_id: str
    source_type: str
    source_id: Optional[str] = None
    source_url: Optional[str] = None
    source_thumbnail: Optional[str] = None
    source_duration: float
    position: float
    duration: float
    in_point: float
    out_point: Optional[float] = None
    speed: float
    opacity: float
    volume: float
    position_x: float
    position_y: float
    scale: float
    rotation: float
    transitions: Optional[dict] = None
    filters: Optional[List[dict]] = None
    keyframes: Optional[List[dict]] = None
    text_content: Optional[str] = None
    font_family: Optional[str] = None
    font_size: Optional[int] = None
    font_color: Optional[str] = None
    name: Optional[str] = None
    sort_order: int
    is_active: bool
    is_locked: bool
    created_at: str


def build_timeline_response(t: Timeline) -> TimelineResponse:
    return TimelineResponse(
        id=str(t.id),
        project_id=str(t.project_id),
        user_id=str(t.user_id),
        name=t.name,
        description=t.description,
        fps=t.fps or 24,
        aspect_ratio=t.aspect_ratio or "16:9",
        total_duration=t.total_duration or 0.0,
        width=t.width or 1920,
        height=t.height or 1080,
        video_track_count=t.video_track_count or 2,
        audio_track_count=t.audio_track_count or 3,
        subtitle_track_count=t.subtitle_track_count or 1,
        status=t.status or "draft",
        is_active=t.is_active if t.is_active is not None else True,
        is_default=t.is_default or False,
        thumbnail_url=t.thumbnail_url,
        preview_url=t.preview_url,
        created_at=str(t.created_at),
        updated_at=str(t.updated_at),
    )


def build_track_response(t: Track) -> TrackResponse:
    return TrackResponse(
        id=str(t.id),
        timeline_id=str(t.timeline_id),
        track_type=t.track_type,
        track_index=t.track_index or 0,
        name=t.name,
        is_locked=t.is_locked or False,
        is_muted=t.is_muted or False,
        is_hidden=t.is_hidden or False,
        opacity=t.opacity or 1.0,
        volume=t.volume or 1.0,
        effects=t.effects,
    )


def build_clip_response(c: Clip) -> ClipResponse:
    return ClipResponse(
        id=str(c.id),
        timeline_id=str(c.timeline_id),
        track_id=str(c.track_id),
        source_type=c.source_type,
        source_id=str(c.source_id) if c.source_id else None,
        source_url=c.source_url,
        source_thumbnail=c.source_thumbnail,
        source_duration=c.source_duration or 0,
        position=c.position or 0,
        duration=c.duration or 5,
        in_point=c.in_point or 0,
        out_point=c.out_point,
        speed=c.speed or 1.0,
        opacity=c.opacity or 1.0,
        volume=c.volume or 1.0,
        position_x=c.position_x or 0,
        position_y=c.position_y or 0,
        scale=c.scale or 1.0,
        rotation=c.rotation or 0,
        transitions=c.transitions,
        filters=c.filters,
        keyframes=c.keyframes,
        text_content=c.text_content,
        font_family=c.font_family,
        font_size=c.font_size,
        font_color=c.font_color,
        name=c.name,
        sort_order=c.sort_order or 0,
        is_active=c.is_active if c.is_active is not None else True,
        is_locked=c.is_locked or False,
        created_at=str(c.created_at),
    )


async def get_timeline_for_user(db, timeline_id, user_id):
    result = await db.execute(
        select(Timeline).where(and_(Timeline.id == timeline_id, Timeline.user_id == user_id))
    )
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="时间线不存在")
    return t


# ========== Timeline API ==========

@router.get("/project/{project_id}", response_model=List[TimelineResponse])
async def list_timelines_by_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取项目的所有时间线"""
    result = await db.execute(
        select(Timeline).where(
            and_(Timeline.project_id == project_id, Timeline.user_id == user_id)
        ).order_by(desc(Timeline.is_default), desc(Timeline.updated_at))
    )
    timelines = result.scalars().all()
    return [build_timeline_response(t) for t in timelines]


@router.get("/{timeline_id}", response_model=TimelineResponse)
async def get_timeline(
    timeline_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取时间线详情"""
    t = await get_timeline_for_user(db, timeline_id, user_id)
    return build_timeline_response(t)


@router.post("", response_model=TimelineResponse, status_code=status.HTTP_201_CREATED)
async def create_timeline(
    request: TimelineCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """创建时间线"""
    # 验证项目
    proj_result = await db.execute(
        select(Project).where(and_(Project.id == request.project_id, Project.user_id == user_id))
    )
    if not proj_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="项目不存在")

    # 检查是否已有默认时间线
    existing_default = await db.execute(
        select(Timeline).where(
            and_(Timeline.project_id == request.project_id, Timeline.is_default == True)
        )
    )
    is_default = existing_default.scalar_one_or_none() is None

    timeline = Timeline(
        id=str(uuid4()),
        user_id=user_id,
        project_id=request.project_id,
        name=request.name,
        description=request.description,
        fps=request.fps or 24,
        aspect_ratio=request.aspect_ratio or "16:9",
        video_track_count=request.video_track_count or 2,
        audio_track_count=request.audio_track_count or 3,
        subtitle_track_count=request.subtitle_track_count or 1,
        is_default=is_default,
    )
    db.add(timeline)

    # 自动创建默认轨道
    for i in range(request.video_track_count or 2):
        track_type_name = "V1" if i == 0 else f"V{i + 1}"
        track = Track(
            id=str(uuid4()),
            timeline_id=timeline.id,
            track_type="video",
            track_index=i,
            name=f"{track_type_name} - 主视频",
        )
        db.add(track)

    for i in range(request.audio_track_count or 3):
        track_type_name = ["A1 - 背景音乐", "A2 - 对白", "A3 - 音效"][i] if i < 3 else f"A{i + 1}"
        track = Track(
            id=str(uuid4()),
            timeline_id=timeline.id,
            track_type="audio",
            track_index=request.video_track_count + i,
            name=track_type_name,
        )
        db.add(track)

    for i in range(request.subtitle_track_count or 1):
        track = Track(
            id=str(uuid4()),
            timeline_id=timeline.id,
            track_type="subtitle",
            track_index=request.video_track_count + request.audio_track_count + i,
            name=f"S{i + 1} - 字幕",
        )
        db.add(track)

    await db.commit()
    await db.refresh(timeline)
    return build_timeline_response(timeline)


@router.put("/{timeline_id}", response_model=TimelineResponse)
async def update_timeline(
    timeline_id: str,
    request: TimelineUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """更新时间线"""
    t = await get_timeline_for_user(db, timeline_id, user_id)
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(t, key, value)
    t.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(t)
    return build_timeline_response(t)


@router.delete("/{timeline_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_timeline(
    timeline_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """删除时间线"""
    t = await get_timeline_for_user(db, timeline_id, user_id)
    if t.is_default:
        raise HTTPException(status_code=400, detail="不能删除默认时间线")
    await db.delete(t)
    await db.commit()


# ========== Track API ==========

@router.get("/{timeline_id}/tracks", response_model=List[TrackResponse])
async def list_tracks(
    timeline_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取时间线的所有轨道"""
    await get_timeline_for_user(db, timeline_id, user_id)
    result = await db.execute(
        select(Track).where(Track.timeline_id == timeline_id).order_by(Track.track_index)
    )
    tracks = result.scalars().all()
    return [build_track_response(t) for t in tracks]


@router.post("/{timeline_id}/tracks", response_model=TrackResponse, status_code=status.HTTP_201_CREATED)
async def create_track(
    timeline_id: str,
    request: TrackCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """添加轨道"""
    await get_timeline_for_user(db, timeline_id, user_id)
    track = Track(
        id=str(uuid4()),
        timeline_id=timeline_id,
        track_type=request.track_type,
        track_index=request.track_index,
        name=request.name or f"{request.track_type}_{request.track_index}",
        is_locked=request.is_locked,
        is_muted=request.is_muted,
    )
    db.add(track)
    await db.commit()
    await db.refresh(track)
    return build_track_response(track)


@router.put("/{timeline_id}/tracks/{track_id}", response_model=TrackResponse)
async def update_track(
    timeline_id: str,
    track_id: str,
    request: TrackUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """更新轨道"""
    await get_timeline_for_user(db, timeline_id, user_id)
    result = await db.execute(
        select(Track).where(and_(Track.id == track_id, Track.timeline_id == timeline_id))
    )
    track = result.scalar_one_or_none()
    if not track:
        raise HTTPException(status_code=404, detail="轨道不存在")
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(track, key, value)
    await db.commit()
    await db.refresh(track)
    return build_track_response(track)


@router.delete("/{timeline_id}/tracks/{track_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_track(
    timeline_id: str,
    track_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """删除轨道"""
    await get_timeline_for_user(db, timeline_id, user_id)
    result = await db.execute(
        select(Track).where(and_(Track.id == track_id, Track.timeline_id == timeline_id))
    )
    track = result.scalar_one_or_none()
    if not track:
        raise HTTPException(status_code=404, detail="轨道不存在")
    await db.delete(track)
    await db.commit()


# ========== Clip API ==========

@router.get("/{timeline_id}/clips", response_model=List[ClipResponse])
async def list_clips(
    timeline_id: str,
    track_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取时间线的片段"""
    await get_timeline_for_user(db, timeline_id, user_id)
    conditions = [Clip.timeline_id == timeline_id, Clip.is_active == True]
    if track_id:
        conditions.append(Clip.track_id == track_id)
    result = await db.execute(
        select(Clip).where(*conditions).order_by(Clip.position)
    )
    clips = result.scalars().all()
    return [build_clip_response(c) for c in clips]


@router.post("", response_model=ClipResponse, status_code=status.HTTP_201_CREATED)
async def create_clip(
    request: ClipCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """添加片段"""
    # 验证时间线
    await get_timeline_for_user(db, request.timeline_id, user_id)

    # 验证轨道
    track_result = await db.execute(
        select(Track).where(and_(Track.id == request.track_id, Track.timeline_id == request.timeline_id))
    )
    if not track_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="轨道不存在")

    clip = Clip(
        id=str(uuid4()),
        user_id=user_id,
        timeline_id=request.timeline_id,
        track_id=request.track_id,
        source_type=request.source_type,
        source_id=request.source_id,
        source_url=request.source_url,
        source_thumbnail=request.source_thumbnail,
        source_duration=request.duration,
        position=request.position,
        duration=request.duration,
        name=request.name,
        speed=request.speed or 1.0,
        opacity=request.opacity or 1.0,
        volume=request.volume or 1.0,
        in_point=request.in_point or 0,
        out_point=request.out_point,
        position_x=request.position_x,
        position_y=request.position_y,
        scale=request.scale or 1.0,
        rotation=request.rotation or 0,
        transitions=request.transitions,
        filters=request.filters,
        keyframes=request.keyframes,
        text_content=request.text_content,
        font_family=request.font_family,
        font_size=request.font_size,
        font_color=request.font_color,
    )
    db.add(clip)
    await db.commit()
    await db.refresh(clip)
    return build_clip_response(clip)


@router.put("/{timeline_id}/clips/{clip_id}", response_model=ClipResponse)
async def update_clip(
    timeline_id: str,
    clip_id: str,
    request: ClipUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """更新片段"""
    await get_timeline_for_user(db, timeline_id, user_id)
    result = await db.execute(
        select(Clip).where(and_(Clip.id == clip_id, Clip.timeline_id == timeline_id, Clip.user_id == user_id))
    )
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="片段不存在")
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(clip, key, value)
    clip.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(clip)
    return build_clip_response(clip)


@router.delete("/{timeline_id}/clips/{clip_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_clip(
    timeline_id: str,
    clip_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """删除片段（软删除）"""
    await get_timeline_for_user(db, timeline_id, user_id)
    result = await db.execute(
        select(Clip).where(and_(Clip.id == clip_id, Clip.timeline_id == timeline_id, Clip.user_id == user_id))
    )
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="片段不存在")
    clip.is_active = False
    clip.updated_at = datetime.utcnow()
    await db.commit()


@router.post("/{timeline_id}/clips/reorder")
async def reorder_clips(
    timeline_id: str,
    clip_orders: List[dict],  # [{"clip_id": "...", "position": 0.0, "track_id": "..."}]
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """批量更新片段位置（拖拽排序）"""
    await get_timeline_for_user(db, timeline_id, user_id)
    for order in clip_orders:
        result = await db.execute(
            select(Clip).where(and_(
                Clip.id == order["clip_id"],
                Clip.timeline_id == timeline_id,
                Clip.user_id == user_id
            ))
        )
        clip = result.scalar_one_or_none()
        if clip:
            clip.position = order.get("position", clip.position)
            clip.track_id = order.get("track_id", clip.track_id)
            clip.updated_at = datetime.utcnow()
    await db.commit()
    return {"message": "排序已更新"}
