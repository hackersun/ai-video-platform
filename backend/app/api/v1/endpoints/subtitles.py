"""
Subtitle track API.

Subtitles are editable production assets used by direct audio-video generation,
TTS workflows, timelines, render packages, and publication exports.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.media_generation_job import MediaGenerationJob
from app.models.shot import Shot
from app.models.subtitle import SubtitleSegment, SubtitleTrack
from app.models.tts_job import TTSJob

router = APIRouter(tags=["字幕轨"])

STATIC_ROOT = Path(__file__).resolve().parents[4] / "static"


class SubtitleSegmentCreate(BaseModel):
    shot_id: Optional[str] = None
    speaker_entity_id: Optional[str] = None
    speaker_name: Optional[str] = None
    start_seconds: float = Field(0.0, ge=0)
    end_seconds: float = Field(0.0, ge=0)
    text: str = Field(..., min_length=1)
    original_text: Optional[str] = None
    source: str = "manual"
    confidence: Optional[float] = None
    review_status: str = "pending_review"
    style: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SubtitleSegmentUpdate(BaseModel):
    speaker_entity_id: Optional[str] = None
    speaker_name: Optional[str] = None
    start_seconds: Optional[float] = Field(None, ge=0)
    end_seconds: Optional[float] = Field(None, ge=0)
    text: Optional[str] = Field(None, min_length=1)
    review_status: Optional[str] = None
    style: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class SubtitleSegmentResponse(BaseModel):
    id: str
    track_id: str
    shot_id: Optional[str] = None
    speaker_entity_id: Optional[str] = None
    speaker_name: Optional[str] = None
    start_seconds: float
    end_seconds: float
    text: str
    original_text: Optional[str] = None
    source: str
    confidence: Optional[float] = None
    review_status: str
    style: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    sort_order: int
    created_at: datetime
    updated_at: datetime


class SubtitleTrackResponse(BaseModel):
    id: str
    user_id: str
    project_id: Optional[str] = None
    workflow_id: Optional[str] = None
    novel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    script_id: Optional[str] = None
    storyboard_id: Optional[str] = None
    shot_id: Optional[str] = None
    media_job_id: Optional[str] = None
    title: Optional[str] = None
    language: str
    kind: str
    source: str
    status: str
    export_urls: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    segments: List[SubtitleSegmentResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class CreateTrackFromShotRequest(BaseModel):
    shot_id: str
    language: str = "zh-CN"
    kind: str = "dialogue"
    title: Optional[str] = None
    duration_seconds: Optional[float] = None


class CreateTrackFromMediaRequest(BaseModel):
    media_job_id: str
    language: str = "zh-CN"
    kind: str = "dialogue"
    title: Optional[str] = None
    text: Optional[str] = None


class CreateTrackFromTTSRequest(BaseModel):
    tts_job_id: str
    language: str = "zh-CN"
    kind: str = "dialogue"
    title: Optional[str] = None


class ExportSubtitleRequest(BaseModel):
    format: str = Field("srt", pattern="^(srt|vtt|ass)$")


def _format_srt_time(seconds: float) -> str:
    total_ms = int(max(0, seconds) * 1000)
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, ms = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{ms:03}"


def _format_vtt_time(seconds: float) -> str:
    return _format_srt_time(seconds).replace(",", ".")


def _json_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _build_segment_response(segment: SubtitleSegment) -> SubtitleSegmentResponse:
    return SubtitleSegmentResponse(
        id=segment.id,
        track_id=segment.track_id,
        shot_id=segment.shot_id,
        speaker_entity_id=segment.speaker_entity_id,
        speaker_name=segment.speaker_name,
        start_seconds=float(segment.start_seconds or 0.0),
        end_seconds=float(segment.end_seconds or 0.0),
        text=segment.text,
        original_text=segment.original_text,
        source=segment.source or "manual",
        confidence=segment.confidence,
        review_status=segment.review_status or "pending_review",
        style=_json_dict(segment.style),
        metadata=_json_dict(segment.metadata_),
        sort_order=segment.sort_order or 0,
        created_at=segment.created_at,
        updated_at=segment.updated_at,
    )


async def _build_track_response(db: AsyncSession, track: SubtitleTrack, include_segments: bool = True) -> SubtitleTrackResponse:
    segments: List[SubtitleSegmentResponse] = []
    if include_segments:
        result = await db.execute(
            select(SubtitleSegment)
            .where(
                SubtitleSegment.track_id == track.id,
                SubtitleSegment.user_id == track.user_id,
                SubtitleSegment.is_active == True,
            )
            .order_by(SubtitleSegment.start_seconds, SubtitleSegment.sort_order)
        )
        segments = [_build_segment_response(segment) for segment in result.scalars().all()]
    return SubtitleTrackResponse(
        id=track.id,
        user_id=track.user_id,
        project_id=track.project_id,
        workflow_id=track.workflow_id,
        novel_id=track.novel_id,
        chapter_id=track.chapter_id,
        script_id=track.script_id,
        storyboard_id=track.storyboard_id,
        shot_id=track.shot_id,
        media_job_id=track.media_job_id,
        title=track.title,
        language=track.language or "zh-CN",
        kind=track.kind or "dialogue",
        source=track.source or "manual",
        status=track.status or "draft",
        export_urls=_json_dict(track.export_urls),
        metadata=_json_dict(track.metadata_),
        segments=segments,
        created_at=track.created_at,
        updated_at=track.updated_at,
    )


async def _get_track(db: AsyncSession, track_id: str, user_id: str) -> SubtitleTrack:
    result = await db.execute(
        select(SubtitleTrack).where(
            SubtitleTrack.id == track_id,
            SubtitleTrack.user_id == user_id,
            SubtitleTrack.is_active == True,
        )
    )
    track = result.scalar_one_or_none()
    if not track:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="字幕轨不存在")
    return track


async def _get_segment(db: AsyncSession, track_id: str, segment_id: str, user_id: str) -> SubtitleSegment:
    result = await db.execute(
        select(SubtitleSegment).where(
            SubtitleSegment.id == segment_id,
            SubtitleSegment.track_id == track_id,
            SubtitleSegment.user_id == user_id,
            SubtitleSegment.is_active == True,
        )
    )
    segment = result.scalar_one_or_none()
    if not segment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="字幕段不存在")
    return segment


def _write_subtitle_export(track_id: str, fmt: str, content: str) -> str:
    export_dir = STATIC_ROOT / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    path = export_dir / f"subtitle-{track_id}.{fmt}"
    path.write_text(content, encoding="utf-8")
    return f"/static/exports/{path.name}"


def _segments_to_srt(segments: List[SubtitleSegment]) -> str:
    blocks = []
    for index, segment in enumerate(segments, start=1):
        blocks.append(
            f"{index}\n"
            f"{_format_srt_time(float(segment.start_seconds or 0))} --> {_format_srt_time(float(segment.end_seconds or 0))}\n"
            f"{segment.text.strip()}\n"
        )
    return "\n".join(blocks).strip() + "\n"


def _segments_to_vtt(segments: List[SubtitleSegment]) -> str:
    blocks = ["WEBVTT\n"]
    for segment in segments:
        blocks.append(
            f"{_format_vtt_time(float(segment.start_seconds or 0))} --> {_format_vtt_time(float(segment.end_seconds or 0))}\n"
            f"{segment.text.strip()}\n"
        )
    return "\n".join(blocks).strip() + "\n"


def _segments_to_ass(segments: List[SubtitleSegment]) -> str:
    header = """[Script Info]
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, Bold, Italic, Alignment
Style: Default,Arial,36,&H00FFFFFF,&H00000000,0,0,2

[Events]
Format: Layer, Start, End, Style, Text
"""
    lines = []
    for segment in segments:
        start = _format_vtt_time(float(segment.start_seconds or 0)).replace(".", ".")[:-1]
        end = _format_vtt_time(float(segment.end_seconds or 0)).replace(".", ".")[:-1]
        lines.append(f"Dialogue: 0,{start},{end},Default,{segment.text.strip()}")
    return header + "\n".join(lines) + "\n"


@router.get("/tracks", response_model=List[SubtitleTrackResponse])
async def list_subtitle_tracks(
    workflow_id: Optional[str] = None,
    media_job_id: Optional[str] = None,
    shot_id: Optional[str] = None,
    novel_id: Optional[str] = None,
    chapter_id: Optional[str] = None,
    storyboard_id: Optional[str] = None,
    include_segments: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    query = select(SubtitleTrack).where(SubtitleTrack.user_id == user_id, SubtitleTrack.is_active == True)
    if workflow_id:
        query = query.where(SubtitleTrack.workflow_id == workflow_id)
    if media_job_id:
        query = query.where(SubtitleTrack.media_job_id == media_job_id)
    if shot_id:
        query = query.where(SubtitleTrack.shot_id == shot_id)
    if novel_id:
        query = query.where(SubtitleTrack.novel_id == novel_id)
    if chapter_id:
        query = query.where(SubtitleTrack.chapter_id == chapter_id)
    if storyboard_id:
        query = query.where(SubtitleTrack.storyboard_id == storyboard_id)
    result = await db.execute(query.order_by(desc(SubtitleTrack.created_at)).limit(100))
    return [await _build_track_response(db, track, include_segments) for track in result.scalars().all()]


@router.get("/tracks/{track_id}", response_model=SubtitleTrackResponse)
async def get_subtitle_track(
    track_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    track = await _get_track(db, track_id, user_id)
    return await _build_track_response(db, track, True)


@router.post("/from-shot", response_model=SubtitleTrackResponse, status_code=status.HTTP_201_CREATED)
async def create_subtitle_track_from_shot(
    request: CreateTrackFromShotRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    result = await db.execute(select(Shot).where(Shot.id == request.shot_id, Shot.user_id == user_id))
    shot = result.scalar_one_or_none()
    if not shot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="镜头不存在")

    extra = _json_dict(shot.extra_data)
    lineage = _json_dict(extra.get("lineage"))
    text = (extra.get("subtitle_text") or shot.dialogue or "").strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="镜头缺少可生成字幕的对白")

    duration = float(request.duration_seconds or shot.duration or 4)
    track = SubtitleTrack(
        id=str(uuid4()),
        user_id=user_id,
        project_id=lineage.get("project_id"),
        workflow_id=lineage.get("workflow_id"),
        novel_id=lineage.get("novel_id") or extra.get("novel_id"),
        chapter_id=lineage.get("chapter_id") or extra.get("chapter_id"),
        script_id=lineage.get("script_id") or extra.get("script_id"),
        storyboard_id=shot.storyboard_id,
        shot_id=shot.id,
        title=request.title or f"镜头 {shot.shot_number} 字幕",
        language=request.language,
        kind=request.kind,
        source="shot_dialogue",
        status="draft",
        metadata_={"shot_number": shot.shot_number},
    )
    segment = SubtitleSegment(
        id=str(uuid4()),
        track_id=track.id,
        user_id=user_id,
        shot_id=shot.id,
        start_seconds=0.0,
        end_seconds=duration,
        text=text,
        original_text=text,
        source="shot_dialogue",
        review_status="pending_review",
        sort_order=1,
    )
    db.add(track)
    db.add(segment)
    await db.commit()
    await db.refresh(track)
    return await _build_track_response(db, track, True)


@router.post("/from-tts", response_model=SubtitleTrackResponse, status_code=status.HTTP_201_CREATED)
async def create_subtitle_track_from_tts(
    request: CreateTrackFromTTSRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    result = await db.execute(select(TTSJob).where(TTSJob.id == request.tts_job_id, TTSJob.user_id == user_id))
    tts_job = result.scalar_one_or_none()
    if not tts_job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TTS任务不存在")

    text = (tts_job.text or "").strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="TTS任务缺少文本")
    duration = float(tts_job.duration_seconds or max(1.0, len(text) / 4.5))
    track = SubtitleTrack(
        id=str(uuid4()),
        user_id=user_id,
        project_id=tts_job.project_id,
        workflow_id=tts_job.workflow_id,
        novel_id=tts_job.novel_id,
        chapter_id=tts_job.chapter_id,
        script_id=tts_job.script_id,
        storyboard_id=tts_job.storyboard_id,
        shot_id=tts_job.shot_id,
        title=request.title or f"{tts_job.title or 'TTS'} 字幕",
        language=request.language,
        kind=request.kind,
        source="tts_segments",
        status="draft",
        metadata_={"tts_job_id": tts_job.id, "audio_url": tts_job.audio_url},
    )
    segment = SubtitleSegment(
        id=str(uuid4()),
        track_id=track.id,
        user_id=user_id,
        shot_id=tts_job.shot_id,
        start_seconds=0.0,
        end_seconds=duration,
        text=text,
        original_text=text,
        source="tts_segments",
        review_status="pending_review",
        sort_order=1,
    )
    db.add(track)
    db.add(segment)
    await db.commit()
    await db.refresh(track)
    return await _build_track_response(db, track, True)


@router.post("/from-media", response_model=SubtitleTrackResponse, status_code=status.HTTP_201_CREATED)
async def create_subtitle_track_from_media(
    request: CreateTrackFromMediaRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    result = await db.execute(
        select(MediaGenerationJob).where(MediaGenerationJob.id == request.media_job_id, MediaGenerationJob.user_id == user_id)
    )
    media_job = result.scalar_one_or_none()
    if not media_job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="媒体任务不存在")
    extra = _json_dict(media_job.extra_data)
    text = (request.text or extra.get("subtitle_text") or "").strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="媒体任务缺少可生成字幕的文本")

    track = SubtitleTrack(
        id=str(uuid4()),
        user_id=user_id,
        project_id=media_job.project_id,
        workflow_id=media_job.workflow_id,
        novel_id=media_job.novel_id,
        chapter_id=media_job.chapter_id,
        script_id=media_job.script_id,
        storyboard_id=media_job.storyboard_id,
        shot_id=media_job.shot_id,
        media_job_id=media_job.id,
        title=request.title or f"{media_job.title or '音视频'} 字幕",
        language=request.language,
        kind=request.kind,
        source="direct_av_model",
        status="draft",
        metadata_={"media_job_id": media_job.id},
    )
    segment = SubtitleSegment(
        id=str(uuid4()),
        track_id=track.id,
        user_id=user_id,
        shot_id=media_job.shot_id,
        start_seconds=0.0,
        end_seconds=float(media_job.duration_seconds or 4),
        text=text,
        original_text=text,
        source="direct_av_model",
        review_status="pending_review",
        confidence=1.0,
        sort_order=1,
    )
    media_job.subtitle_track_id = track.id
    db.add(track)
    db.add(segment)
    await db.commit()
    await db.refresh(track)
    return await _build_track_response(db, track, True)


@router.post("/tracks/{track_id}/segments", response_model=SubtitleSegmentResponse, status_code=status.HTTP_201_CREATED)
async def create_subtitle_segment(
    track_id: str,
    request: SubtitleSegmentCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    await _get_track(db, track_id, user_id)
    result = await db.execute(
        select(SubtitleSegment).where(SubtitleSegment.track_id == track_id, SubtitleSegment.user_id == user_id)
    )
    existing_count = len(result.scalars().all())
    segment = SubtitleSegment(
        id=str(uuid4()),
        track_id=track_id,
        user_id=user_id,
        shot_id=request.shot_id,
        speaker_entity_id=request.speaker_entity_id,
        speaker_name=request.speaker_name,
        start_seconds=request.start_seconds,
        end_seconds=request.end_seconds,
        text=request.text,
        original_text=request.original_text or request.text,
        source=request.source,
        confidence=request.confidence,
        review_status=request.review_status,
        style=request.style,
        metadata_=request.metadata,
        sort_order=existing_count + 1,
    )
    db.add(segment)
    await db.commit()
    await db.refresh(segment)
    return _build_segment_response(segment)


@router.put("/tracks/{track_id}/segments/{segment_id}", response_model=SubtitleSegmentResponse)
async def update_subtitle_segment(
    track_id: str,
    segment_id: str,
    request: SubtitleSegmentUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    await _get_track(db, track_id, user_id)
    segment = await _get_segment(db, track_id, segment_id, user_id)
    update_data = request.model_dump(exclude_unset=True)
    metadata = update_data.pop("metadata", None)
    if metadata is not None:
        segment.metadata_ = metadata
    for key, value in update_data.items():
        setattr(segment, key, value)
    if segment.end_seconds < segment.start_seconds:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="字幕结束时间不能早于开始时间")
    await db.commit()
    await db.refresh(segment)
    return _build_segment_response(segment)


@router.delete("/tracks/{track_id}/segments/{segment_id}")
async def delete_subtitle_segment(
    track_id: str,
    segment_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    await _get_track(db, track_id, user_id)
    segment = await _get_segment(db, track_id, segment_id, user_id)
    segment.is_active = False
    await db.commit()
    return {"message": "字幕段已归档", "segment_id": segment_id}


@router.post("/tracks/{track_id}/export")
async def export_subtitle_track(
    track_id: str,
    request: ExportSubtitleRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    track = await _get_track(db, track_id, user_id)
    result = await db.execute(
        select(SubtitleSegment)
        .where(
            SubtitleSegment.track_id == track_id,
            SubtitleSegment.user_id == user_id,
            SubtitleSegment.is_active == True,
        )
        .order_by(SubtitleSegment.start_seconds, SubtitleSegment.sort_order)
    )
    segments = result.scalars().all()
    if not segments:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="字幕轨没有可导出的字幕段")

    if request.format == "srt":
        content = _segments_to_srt(segments)
    elif request.format == "vtt":
        content = _segments_to_vtt(segments)
    else:
        content = _segments_to_ass(segments)
    export_url = _write_subtitle_export(track_id, request.format, content)
    export_urls = _json_dict(track.export_urls)
    export_urls[request.format] = export_url
    track.export_urls = export_urls
    track.status = "exported"
    await db.commit()
    await db.refresh(track)
    return {"track_id": track.id, "format": request.format, "url": export_url, "export_urls": export_urls}
