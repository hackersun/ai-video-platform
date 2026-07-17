"""
分镜管理 API 端点
"""
from app.core.time_utils import utc_now
import asyncio
import uuid
import json
import os
import re
import shutil
import subprocess
from typing import Any, List, Optional
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.api_key_utils import create_text_generation_service, get_user_text_model_config, get_user_volcano_api_key
from app.core.dev_generation import dev_synthesis_url, is_dev_mode
from app.core.security import get_current_user_id
from app.models import Asset, Storyboard, Shot, Novel, Chapter, Script, SynthesisJob
from app.services.consistency_context import build_consistency_prompt, build_shot_entity_context, auto_fill_shot_entity_refs
from app.services.novel_continuity import build_novel_continuity_package
from app.services.prompt_skill_service import apply_active_prompt_skill_template
from app.services.story_prompt_context import (
    build_shot_dialogue_context,
    build_story_context_block,
    load_story_prompt_context,
)
from app.services.chapter_naming import format_chapter_label, normalize_duplicate_chapter_label_text
from app.services.storyboard_template_service import (
    build_template_shots,
    list_templates,
    match_storyboard_template,
    merge_template_overrides,
    plan_storyboard_shot_count,
)

router = APIRouter(tags=["分镜管理"])


# ============== Pydantic 模型 ==============

class StoryboardCreate(BaseModel):
    """创建分镜请求"""
    script_id: str = Field(..., description="所属剧本ID")
    title: str = Field(..., min_length=1, max_length=200, description="分镜标题")
    description: Optional[str] = Field(None, description="分镜描述")
    content: Optional[dict] = Field(None, description="分镜内容")


class StoryboardUpdate(BaseModel):
    """更新分镜请求"""
    title: Optional[str] = None
    description: Optional[str] = None
    content: Optional[dict] = None
    shot_count: Optional[int] = None
    total_duration: Optional[int] = None
    status: Optional[str] = None


class StoryboardResponse(BaseModel):
    """分镜响应"""
    id: str
    script_id: str
    user_id: str
    novel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    title: str
    script_title: Optional[str] = None
    description: Optional[str] = None
    content: Optional[dict] = None
    shot_count: int
    total_duration: int
    status: str
    created_at: str
    updated_at: str


class StoryboardGenerateRequest(BaseModel):
    """AI生成分镜请求"""
    script_id: str = Field(..., description="剧本ID")
    shot_count: Optional[int] = Field(None, ge=1, le=50, description="镜头数量（默认自动）")
    style: str = Field(default="anime", description="分镜风格（anime/realistic/cartoon等）")
    story_bible_id: Optional[str] = Field(None, description="用于一致性约束的 Story Bible ID")
    project_id: Optional[str] = Field(None, description="项目ID，用于注入项目全局风格")
    novel_id: Optional[str] = Field(None, description="小说ID，用于自动匹配 Story Bible")
    use_consistency_context: bool = Field(True, description="是否自动注入 Story Bible/项目一致性上下文")
    model_config_id: Optional[str] = Field(None, description="已保存的文本模型配置ID")


class StoryboardSmartGenerateRequest(BaseModel):
    """从小说或章节智能生成分镜请求"""
    novel_id: str = Field(..., description="小说ID")
    chapter_id: Optional[str] = Field(None, description="章节ID，不传则使用小说最近章节或小说简介")
    script_id: Optional[str] = Field(None, description="复用指定剧本生成分镜；不传则自动创建改编脚本")
    template_id: Optional[str] = Field(None, description="指定模板ID，不传则自动匹配")
    shot_count: Optional[int] = Field(None, ge=1, le=50, description="镜头数量，不传则按模板")
    style: str = Field(default="anime", description="分镜风格")
    title: Optional[str] = Field(None, max_length=200, description="生成的分镜标题")
    story_bible_id: Optional[str] = Field(None, description="用于一致性约束的 Story Bible ID")
    project_id: Optional[str] = Field(None, description="项目ID，用于注入项目全局风格")
    use_ai_refine: bool = Field(True, description="有文本模型配置时是否让AI细化模板草案")
    use_consistency_context: bool = Field(True, description="是否注入 Story Bible/项目一致性上下文")
    model_config_id: Optional[str] = Field(None, description="已保存的文本模型配置ID")


class ShotBriefResponse(BaseModel):
    """镜头简要响应（嵌套在分镜生成响应中）"""
    id: str
    shot_number: int
    duration: int
    prompt: Optional[str]
    dialogue: Optional[str]
    visual_description: Optional[str]
    camera_angle: Optional[str]
    character_refs: Optional[List[dict]] = None
    extra_data: Optional[dict] = None


class StoryboardGenerateResponse(BaseModel):
    """AI生成分镜响应"""
    id: str
    script_id: str
    user_id: str
    novel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    title: str
    script_title: Optional[str] = None
    description: Optional[str] = None
    content: Optional[dict] = None
    shot_count: int
    total_duration: int
    status: str
    shots: List[ShotBriefResponse]
    created_at: str
    updated_at: str


class StoryboardTemplateResponse(BaseModel):
    id: str
    name: str
    description: str
    genre_tags: List[str]
    keywords: List[str]
    shot_count: int
    is_system: bool = True
    is_overridden: bool = False
    override_asset_id: Optional[str] = None
    prompt_template: Optional[str] = None
    shot_template: Optional[dict] = None


class StoryboardTemplateMatchResponse(BaseModel):
    template: StoryboardTemplateResponse
    score: int
    reason: str


class StoryboardMergeVideosRequest(BaseModel):
    """按当前分镜镜头顺序合并已生成视频。"""
    shot_ids: Optional[List[str]] = Field(None, description="指定要合并的镜头ID；不传则合并当前分镜下已有视频的镜头")
    title: Optional[str] = Field(None, max_length=200, description="成片标题")
    transition_style: str = Field("cut", description="转场方式")
    transition_duration_seconds: float = Field(0, ge=0, le=3, description="转场时长")
    include_subtitles: bool = Field(True, description="是否导出字幕")
    subtitle_mode: str = Field("soft", description="字幕模式: soft/burn/off")
    audio_mix_strategy: str = Field("shot_audio_first", description="音频混合策略")
    quality_profile: str = Field("review", description="合成质量配置")
    render_strategy: str = Field("auto", pattern="^(auto|ffmpeg|manifest_only)$", description="渲染策略：auto/ffmpeg/manifest_only")
    parent_job_id: Optional[str] = Field(None, description="重新合成时关联的上一版合成任务ID")


class StoryboardMergeVideosResponse(BaseModel):
    job_id: str
    storyboard_id: str
    message: str
    output_url: Optional[str] = None
    manifest_url: str
    srt_url: Optional[str] = None
    segment_count: int
    duration_seconds: float
    segments: List[dict]
    selected_shot_ids: List[str] = Field(default_factory=list)
    selected_shot_numbers: List[int] = Field(default_factory=list)
    skipped_shot_numbers: List[int] = Field(default_factory=list)
    version_number: int = 1
    parent_job_id: Optional[str] = None
    render_backend: str = "local_manifest"
    is_real_merged: bool = False
    render_message: Optional[str] = None


class StoryboardMergeVersionResponse(BaseModel):
    job_id: str
    storyboard_id: str
    title: Optional[str] = None
    output_url: Optional[str] = None
    manifest_url: Optional[str] = None
    srt_url: Optional[str] = None
    segment_count: int = 0
    duration_seconds: Optional[float] = None
    selected_shot_ids: List[str] = Field(default_factory=list)
    selected_shot_numbers: List[int] = Field(default_factory=list)
    skipped_shot_numbers: List[int] = Field(default_factory=list)
    version_number: int = 1
    parent_job_id: Optional[str] = None
    render_backend: str = "local_manifest"
    is_real_merged: bool = False
    render_message: Optional[str] = None
    created_at: str


# ============== LLM API Key 辅助函数 ==============

async def get_user_qwen_api_key(
    db: AsyncSession,
    user_id: str,
    model_config_id: Optional[str] = None,
) -> tuple[str, str, str, Optional[str]]:
    """获取用户默认文本模型配置。"""
    api_key, provider_name, model_id, base_url = await get_user_text_model_config(
        db,
        user_id,
        config_id=model_config_id,
    )
    return api_key or "", provider_name or "", model_id or "", base_url


def _compact_prompt_context_value(value: Optional[str], limit: int = 2400) -> str:
    text = (value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def _extract_first_dialogue_line(content: Optional[str]) -> str:
    for line in (content or "").splitlines():
        text = line.strip()
        if re.match(r"^(.{1,16}[：:].+|（旁白）.+)", text):
            return text
    return ""


async def get_script_for_user(db: AsyncSession, script_id: str, user_id: str):
    result = await db.execute(
        select(Script).where(and_(Script.id == script_id, Script.user_id == user_id))
    )
    script = result.scalar_one_or_none()
    if script is None:
        raise HTTPException(status_code=404, detail="剧本不存在")
    return script


async def get_novel_for_user(db: AsyncSession, novel_id: str, user_id: str) -> Novel:
    result = await db.execute(
        select(Novel).where(and_(Novel.id == novel_id, Novel.user_id == user_id))
    )
    novel = result.scalar_one_or_none()
    if novel is None:
        raise HTTPException(status_code=404, detail="小说不存在")
    return novel


async def get_chapter_for_user(db: AsyncSession, chapter_id: str, novel_id: str, user_id: str) -> Chapter:
    result = await db.execute(
        select(Chapter).where(
            and_(Chapter.id == chapter_id, Chapter.novel_id == novel_id, Chapter.user_id == user_id)
        )
    )
    chapter = result.scalar_one_or_none()
    if chapter is None:
        raise HTTPException(status_code=404, detail="章节不存在")
    return chapter


def build_generation_source_title(novel: Novel, chapter: Optional[Chapter]) -> str:
    if not chapter:
        return novel.title
    return f"{novel.title} - {format_chapter_label(chapter.title, chapter.chapter_number)}"


async def get_generation_source(
    db: AsyncSession,
    user_id: str,
    novel_id: str,
    chapter_id: Optional[str],
    *,
    fallback_to_first_chapter: bool = True,
) -> tuple[Novel, Optional[Chapter], str, str]:
    novel = await get_novel_for_user(db, novel_id, user_id)
    chapter: Optional[Chapter] = None
    if chapter_id:
        chapter = await get_chapter_for_user(db, chapter_id, novel_id, user_id)
    elif fallback_to_first_chapter:
        result = await db.execute(
            select(Chapter)
            .where(and_(Chapter.novel_id == novel_id, Chapter.user_id == user_id))
            .order_by(Chapter.chapter_number)
        )
        chapters = result.scalars().all()
        if chapters:
            chapter = chapters[0]

    source_title = build_generation_source_title(novel, chapter)
    source_content = (chapter.content if chapter else None) or novel.description or novel.title
    if not source_content:
        raise HTTPException(status_code=400, detail="小说或章节内容为空，无法生成分镜")
    return novel, chapter, source_title, source_content


async def load_user_storyboard_templates(db: AsyncSession, user_id: str) -> list[dict[str, Any]]:
    result = await db.execute(
        select(Asset).where(
            and_(
                Asset.user_id == user_id,
                Asset.category == "template",
                Asset.is_active == True,
            )
        )
    )
    override_assets = []
    for asset in result.scalars().all():
        shot_template = asset.shot_template if isinstance(asset.shot_template, dict) else {}
        style_tags = asset.style_tags if isinstance(asset.style_tags, list) else []
        if shot_template.get("system_template_id") or "system_override" in style_tags:
            override_assets.append(asset)
    return merge_template_overrides(list_templates(), override_assets)


def build_template_response(template: dict) -> StoryboardTemplateResponse:
    return StoryboardTemplateResponse(
        id=template["id"],
        name=template["name"],
        description=template["description"],
        genre_tags=template["genre_tags"],
        keywords=template["keywords"],
        shot_count=len(template["shots"]),
        is_system=template.get("is_system", True),
        is_overridden=template.get("is_overridden", False),
        override_asset_id=template.get("override_asset_id"),
        prompt_template=template.get("prompt_template"),
        shot_template=template.get("shot_template") or {
            "system_template_id": template["id"],
            "shot_count": len(template["shots"]),
            "shots": template["shots"],
        },
    )


def _exports_dir() -> Path:
    export_dir = Path(__file__).resolve().parents[4] / "static" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    return export_dir


def _static_root() -> Path:
    return Path(__file__).resolve().parents[4] / "static"


def _write_storyboard_export_json(artifact_id: str, payload: dict[str, Any]) -> str:
    artifact_path = _exports_dir() / f"{artifact_id}.json"
    artifact_path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    return f"/static/exports/{artifact_path.name}"


def _write_storyboard_export_text(artifact_name: str, content: str) -> str:
    artifact_path = _exports_dir() / artifact_name
    artifact_path.write_text(content, encoding="utf-8")
    return f"/static/exports/{artifact_path.name}"


def _format_srt_time(seconds: float) -> str:
    total_ms = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def _build_storyboard_srt(segments: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    subtitle_index = 1
    for segment in segments:
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


def _storyboard_content(storyboard: Storyboard) -> dict[str, Any]:
    return storyboard.content if isinstance(storyboard.content, dict) else {}


def _script_extra(script: Optional[Script]) -> dict[str, Any]:
    return script.extra_data if script and isinstance(script.extra_data, dict) else {}


def _shot_extra(shot: Shot) -> dict[str, Any]:
    return shot.extra_data if isinstance(shot.extra_data, dict) else {}


def _media_url_to_local_static_path(url: Optional[str]) -> Optional[Path]:
    if not url:
        return None
    raw_url = str(url).strip()
    parsed = urlparse(raw_url)
    media_path = parsed.path if parsed.scheme else raw_url
    media_path = unquote(media_path)
    if media_path.startswith("/static/"):
        relative = media_path[len("/static/"):]
    elif media_path.startswith("static/"):
        relative = media_path[len("static/"):]
    else:
        return None
    static_root = _static_root().resolve()
    candidate = (static_root / relative).resolve()
    try:
        candidate.relative_to(static_root)
    except ValueError:
        return None
    return candidate


def _ffmpeg_candidates() -> list[str]:
    candidates = [
        os.getenv("FFMPEG_BINARY"),
        shutil.which("ffmpeg"),
        "/Applications/NAMIAI.app/Contents/Frameworks/NAMIAI Framework.framework/Versions/1.3.1223.64/ffmpeg",
        "/Applications/VideoFusion-macOS.app/Contents/Resources/ffmpeg",
        "/Applications/Trae CN.app/Contents/Resources/app/bin/ffmpeg",
        "/Applications/360Chrome.app/Contents/Frameworks/360Chrome Framework.framework/Versions/16.0.1090.0/ffmpeg",
    ]
    return [candidate for candidate in candidates if candidate]


def _resolve_ffmpeg_binary() -> Optional[str]:
    for candidate in _ffmpeg_candidates():
        path = Path(candidate)
        if path.exists() and os.access(path, os.X_OK):
            return str(path)
    return None


def _probe_video_duration_seconds(path: Path) -> Optional[float]:
    ffmpeg_binary = _resolve_ffmpeg_binary()
    if not ffmpeg_binary or not path.exists():
        return None
    try:
        result = subprocess.run(
            [ffmpeg_binary, "-hide_banner", "-i", str(path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:
        return None
    output = f"{result.stderr or ''}\n{result.stdout or ''}"
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", output)
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    return round(duration, 3) if duration > 0 else None


def _concat_file_line(path: Path) -> str:
    escaped = str(path).replace("'", "'\\''")
    return f"file '{escaped}'"


def _run_ffmpeg_concat(video_paths: list[Path], output_path: Path) -> tuple[bool, str]:
    ffmpeg_binary = _resolve_ffmpeg_binary()
    if not ffmpeg_binary:
        return False, "未找到 FFmpeg 可执行文件，请配置 FFMPEG_BINARY 或安装 FFmpeg"
    missing_paths = [str(path) for path in video_paths if not path.exists()]
    if missing_paths:
        return False, f"以下视频文件不存在，无法真实拼接：{', '.join(missing_paths)}"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    concat_path = output_path.with_suffix(".concat.txt")
    concat_path.write_text("\n".join(_concat_file_line(path) for path in video_paths), encoding="utf-8")
    command = [
        ffmpeg_binary,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_path),
        "-fflags",
        "+genpts",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return False, "FFmpeg 拼接超时，请减少镜头数量或检查源视频"
    except Exception as exc:
        return False, f"FFmpeg 执行失败: {str(exc)}"
    if result.returncode != 0:
        error = (result.stderr or result.stdout or "").strip()
        return False, f"FFmpeg 拼接失败: {error[-1200:] or '未知错误'}"
    if not output_path.exists() or output_path.stat().st_size <= 0:
        return False, "FFmpeg 未生成有效输出文件"
    return True, "已使用 FFmpeg 真实拼接生成 MP4"


def _build_storyboard_merge_version_response(job: SynthesisJob) -> StoryboardMergeVersionResponse:
    extra = job.extra_data if isinstance(job.extra_data, dict) else {}
    return StoryboardMergeVersionResponse(
        job_id=job.id,
        storyboard_id=str(extra.get("storyboard_id") or ""),
        title=job.title,
        output_url=job.output_url,
        manifest_url=extra.get("manifest_url"),
        srt_url=extra.get("srt_url"),
        segment_count=int(extra.get("segment_count") or 0),
        duration_seconds=job.duration_seconds or extra.get("duration_seconds"),
        selected_shot_ids=list(extra.get("selected_shot_ids") or extra.get("shot_ids") or []),
        selected_shot_numbers=list(extra.get("selected_shot_numbers") or []),
        skipped_shot_numbers=list(extra.get("skipped_shot_numbers") or []),
        version_number=int(extra.get("version_number") or 1),
        parent_job_id=extra.get("parent_job_id"),
        render_backend=extra.get("render_backend") or "local_manifest",
        is_real_merged=bool(extra.get("is_real_merged")),
        render_message=extra.get("render_message"),
        created_at=str(job.created_at),
    )


def parse_shots_json(content: str) -> list[dict]:
    json_str = content.strip()
    if json_str.startswith("```json"):
        json_str = json_str[7:]
    if json_str.startswith("```"):
        json_str = json_str[3:]
    if json_str.endswith("```"):
        json_str = json_str[:-3]
    parsed = json.loads(json_str.strip())
    return parsed if isinstance(parsed, list) else [parsed]


NARRATOR_SPEAKERS = {"旁白", "画外音", "解说", "系统"}


def extract_dialogue_speaker(dialogue: Optional[str]) -> Optional[str]:
    text = (dialogue or "").strip()
    if not text:
        return None
    narrator_match = re.match(r"^（\s*([^）]{1,12})\s*）", text)
    if narrator_match:
        speaker = narrator_match.group(1).strip()
        return "旁白" if speaker in NARRATOR_SPEAKERS else speaker
    match = re.match(r"^\s*[-—]?\s*([^：:（）()，。！？\n]{1,24})\s*[：:]", text)
    if not match:
        return None
    speaker = match.group(1).strip().strip("“”\"'")
    if speaker in {"角色A", "角色B", "某人"}:
        return speaker
    return speaker or None


def strip_dialogue_speaker(dialogue: Optional[str]) -> str:
    text = (dialogue or "").strip()
    if not text:
        return ""
    text = re.sub(r"^（\s*[^）]{1,12}\s*）", "", text).strip()
    text = re.sub(r"^\s*[-—]?\s*[^：:（）()，。！？\n]{1,24}\s*[：:]", "", text).strip()
    return text.strip("“”\"' ")


def _speaker_tokens(ref: dict) -> list[str]:
    values = [ref.get("name"), ref.get("character_name")]
    values.extend(ref.get("aliases") or [])
    return [str(value).strip() for value in values if isinstance(value, str) and value.strip()]


def resolve_dialogue_speaker_ref(speaker: Optional[str], character_refs: list[dict]) -> dict:
    if not speaker or speaker in NARRATOR_SPEAKERS:
        return {}
    for ref in character_refs:
        if not isinstance(ref, dict):
            continue
        if speaker in _speaker_tokens(ref):
            return {
                "speaker_entity_id": ref.get("entity_id"),
                "speaker_character_id": ref.get("character_id"),
                "speaker_voice": ref.get("voice"),
            }
    return {}


def build_dialogue_metadata(
    shot_data: dict,
    character_refs: list[dict],
    *,
    dialogue_source: Optional[str],
) -> dict:
    extra = shot_data.get("extra_data") if isinstance(shot_data.get("extra_data"), dict) else {}
    dialogue = shot_data.get("dialogue") or extra.get("subtitle_text")
    if not dialogue:
        return {}

    speaker = (
        shot_data.get("dialogue_speaker")
        or extra.get("dialogue_speaker")
        or extra.get("speaker_name")
        or extract_dialogue_speaker(dialogue)
    )
    inference_source = "explicit"
    if not speaker:
        candidate_refs = [ref for ref in character_refs if isinstance(ref, dict) and ref.get("name")]
        if len(candidate_refs) == 1:
            speaker = candidate_refs[0].get("name")
            inference_source = "single_character_ref"

    spoken_text = strip_dialogue_speaker(dialogue)
    speaker_ref = resolve_dialogue_speaker_ref(speaker, character_refs)
    return {
        "dialogue_speaker": speaker,
        "dialogue_spoken_text": spoken_text,
        "dialogue_source": extra.get("dialogue_source") or shot_data.get("dialogue_source") or dialogue_source or "generated",
        "dialogue_inference_source": inference_source if speaker else None,
        "speaker_entity_id": speaker_ref.get("speaker_entity_id"),
        "speaker_character_id": speaker_ref.get("speaker_character_id"),
        "speaker_voice": speaker_ref.get("speaker_voice"),
    }


async def refine_template_shots_with_ai(
    db: AsyncSession,
    user_id: str,
    request: StoryboardSmartGenerateRequest,
    source_title: str,
    source_content: str,
    template: dict,
    draft_shots: list[dict],
    effective_chapter_id: Optional[str] = None,
) -> list[dict]:
    api_key, provider_name, model_id, base_url = await get_user_text_model_config(
        db,
        user_id,
        raise_if_missing=True,
        config_id=request.model_config_id,
    )
    service = create_text_generation_service(api_key or "", provider_name or "", base_url)
    consistency_prompt = ""
    story_prompt_context = await load_story_prompt_context(
        db,
        user_id,
        novel_id=request.novel_id,
        chapter_id=effective_chapter_id if effective_chapter_id is not None else request.chapter_id,
        title=source_title,
        genre="",
        description=source_content,
        style=request.style,
    )
    dialogue_sample = _extract_first_dialogue_line(source_content)
    prompt_skill_context = {
        "title": source_title,
        "source_title": source_title,
        "source_content": _compact_prompt_context_value(source_content),
        "style": request.style,
        "shot_count": request.shot_count or len(draft_shots),
        "template_name": template["name"],
        "dialogue": dialogue_sample,
        "subtitle_text": dialogue_sample,
    }
    if request.use_consistency_context:
        novel_continuity = await build_novel_continuity_package(
            db,
            user_id,
            novel_id=request.novel_id,
            chapter_id=effective_chapter_id if effective_chapter_id is not None else request.chapter_id,
            story_bible_id=request.story_bible_id,
            project_id=request.project_id,
            task="storyboard_generation",
        )
        context = await build_consistency_prompt(
            db,
            user_id,
            task="storyboard_generation",
            base_prompt=source_content,
            story_bible_id=request.story_bible_id,
            project_id=request.project_id,
            novel_id=request.novel_id,
            extra_context={
                **prompt_skill_context,
                "分镜风格": request.style,
                "匹配模板": template["name"],
                "镜头数量": request.shot_count or len(draft_shots),
                "整部小说连续性锁": novel_continuity.get("prompt_block"),
            },
        )
        consistency_prompt = context["prompt"]

    system_prompt = f"""你是小说改编动漫的分镜导演。请基于给定模板草案，把小说内容转成可执行镜头。

要求：
1. 严格输出 JSON 数组，不要输出 markdown。
2. 保留每个镜头的 shot_number。
3. 每个镜头必须包含：duration、shot_type、prompt、dialogue、visual_description、camera_angle、camera_movement、movement_speed、emotion、emotion_intensity、lighting、color_grading、sound_effect、music_mood、ambient_sound、keyframes。
4. prompt、dialogue、visual_description、sound_effect、music_mood、ambient_sound 必须中文。
5. camera_angle/camera_movement/emotion/lighting/color_grading 使用草案里的枚举值，不要翻译成中文。
6. 保持人物、场景、道具、事件顺序一致，给人工审核提供高质量初稿。
7. 台词必须服务于小说章节和剧本内容：有原剧本对白时优先提炼原对白，允许压缩但不得更换说话人、不得新增无关角色；没有原对白时才补写短句。
8. dialogue 必须使用“角色名：台词”或“（旁白）台词”格式，禁止使用角色A/角色B/某人等占位称呼。
9. 每个有 dialogue 的镜头可在 extra_data 中输出 dialogue_speaker、dialogue_source、dialogue_intent，便于后续配音和字幕绑定。
10. 短视频节奏：开头镜头优先保留冲突钩子或关键疑问；每句对白尽量短，避免长篇解释，把信息拆到多个镜头。

匹配模板：{template["name"]} - {template["description"]}
风格：{request.style}
"""
    if consistency_prompt:
        system_prompt += f"\n全局一致性约束：\n{consistency_prompt}\n"
    else:
        prompt_result = await apply_active_prompt_skill_template(
            db,
            user_id,
            task="storyboard_generation",
            internal_prompt=system_prompt,
            context=prompt_skill_context,
        )
        system_prompt = prompt_result["prompt"]

    response = await service.safe_chat_completion(
        model=model_id or "",
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"【来源标题】{source_title}\n\n"
                    f"【小说/章节内容】\n{source_content[:12000]}\n\n"
                    f"【人物/场景/道具/事件清单】\n{build_story_context_block(story_prompt_context)}\n\n"
                    f"【模板草案】\n{json.dumps(draft_shots, ensure_ascii=False)}"
                ),
            },
        ],
        temperature=0.6,
        max_tokens=8000,
    )
    refined = parse_shots_json(response["choices"][0]["message"]["content"])
    return refined or draft_shots


def normalize_shot_data(shot_data: dict, index: int, template: Optional[dict] = None) -> dict:
    extra_data = {
        **(shot_data.get("extra_data") or {}),
        "shot_type": shot_data.get("shot_type"),
        "template_id": (template or {}).get("id") or (shot_data.get("extra_data") or {}).get("template_id"),
        "template_name": (template or {}).get("name") or (shot_data.get("extra_data") or {}).get("template_name"),
        "review_status": (shot_data.get("extra_data") or {}).get("review_status", "pending_review"),
    }
    if shot_data.get("dialogue"):
        extra_data.setdefault("subtitle_text", shot_data.get("dialogue"))

    return {
        "shot_number": shot_data.get("shot_number") or index + 1,
        "duration": shot_data.get("duration") or 4,
        "prompt": shot_data.get("prompt") or shot_data.get("visual_description") or "",
        "dialogue": shot_data.get("dialogue"),
        "visual_description": shot_data.get("visual_description"),
        "camera_angle": shot_data.get("camera_angle") or "medium",
        "camera_movement": shot_data.get("camera_movement") or "static",
        "movement_speed": shot_data.get("movement_speed") or 1.0,
        "emotion": shot_data.get("emotion") or "neutral",
        "emotion_intensity": shot_data.get("emotion_intensity") if shot_data.get("emotion_intensity") is not None else 0.5,
        "lighting": shot_data.get("lighting") or "natural",
        "color_grading": shot_data.get("color_grading") or "cinematic",
        "sfx_cue": shot_data.get("sfx_cue") or shot_data.get("sound_effect"),
        "music_cue": shot_data.get("music_cue") or shot_data.get("music_mood"),
        "ambient_sound": shot_data.get("ambient_sound"),
        "keyframes": shot_data.get("keyframes") or [],
        "character_refs": shot_data.get("character_refs") or [],
        "extra_data": extra_data,
    }


def ensure_shot_dialogue_subtitle(shot_data: dict) -> None:
    """Ensure generated shots have subtitle text for production readiness."""
    extra_data = shot_data.get("extra_data") if isinstance(shot_data.get("extra_data"), dict) else {}
    existing = (extra_data.get("subtitle_text") or shot_data.get("dialogue") or "").strip()
    if existing:
        shot_data["extra_data"] = extra_data
        extra_data.setdefault("subtitle_text", existing)
        return

    source_text = (
        extra_data.get("source_beat")
        or extra_data.get("source_scene_beat")
        or shot_data.get("visual_description")
        or shot_data.get("prompt")
        or ""
    )
    subtitle_text = _compact_scene_text(source_text, 72)
    if not subtitle_text:
        return

    narration = f"（旁白）{subtitle_text}"
    shot_data["dialogue"] = narration
    extra_data["subtitle_text"] = narration
    extra_data.setdefault("dialogue_speaker", "旁白")
    extra_data.setdefault("dialogue_source", "story_beat_narration_fallback")
    extra_data.setdefault("dialogue_intent", "旁白")
    shot_data["extra_data"] = extra_data


def _parse_storyboard_dialogue_lines(dialogue: Optional[str], fallback_speaker: Optional[str]) -> list[dict[str, str]]:
    lines = [line.strip() for line in (dialogue or "").splitlines() if line.strip()]
    parsed: list[dict[str, str]] = []
    for line in lines:
        narrator = re.match(r"^（\s*([^）]{1,12})\s*）\s*(.+)$", line)
        if narrator:
            speaker = narrator.group(1).strip()
            parsed.append({"speaker": "旁白" if speaker in NARRATOR_SPEAKERS else speaker, "text": narrator.group(2).strip()})
            continue
        match = re.match(r"^\s*([^：:（）()，。！？\n]{1,24})\s*[：:]\s*(.+)$", line)
        if match:
            parsed.append({"speaker": match.group(1).strip(), "text": match.group(2).strip()})
            continue
        parsed.append({"speaker": fallback_speaker or "", "text": line})
    return [item for item in parsed if item["text"]]


def _format_storyboard_dialogue_line(speaker: str, text: str) -> str:
    clean_text = text.strip()
    if not speaker or speaker == "旁白":
        return f"（旁白）{clean_text}"
    return f"{speaker}：{clean_text}"


def split_multi_speaker_dialogue_shots(shots_data: list[dict]) -> list[dict]:
    """Split generated shots so each shot carries at most one speaker voice."""
    split_shots: list[dict] = []
    for raw_shot in shots_data:
        extra_data = raw_shot.get("extra_data") if isinstance(raw_shot.get("extra_data"), dict) else {}
        fallback_speaker = extra_data.get("dialogue_speaker") or raw_shot.get("dialogue_speaker")
        segments = _parse_storyboard_dialogue_lines(raw_shot.get("dialogue"), fallback_speaker)
        distinct_speakers = {segment["speaker"] for segment in segments if segment.get("speaker")}
        if len(distinct_speakers) <= 1:
            split_shots.append(raw_shot)
            continue

        grouped: list[dict[str, Any]] = []
        for segment in segments:
            speaker = segment.get("speaker") or fallback_speaker or ""
            text = segment.get("text") or ""
            if grouped and grouped[-1]["speaker"] == speaker:
                grouped[-1]["texts"].append(text)
            else:
                grouped.append({"speaker": speaker, "texts": [text]})

        segment_count = len(grouped)
        segment_duration = max(3, int(round(float(raw_shot.get("duration") or 4) / max(1, segment_count))))
        for segment_index, group in enumerate(grouped, start=1):
            speaker = str(group.get("speaker") or "").strip()
            text = "".join(str(item).strip() for item in group.get("texts") or [] if str(item).strip())
            if not text:
                continue
            shot = {
                **raw_shot,
                "duration": segment_duration,
                "dialogue": _format_storyboard_dialogue_line(speaker, text),
                "prompt": f"{raw_shot.get('prompt') or ''}，对白段{segment_index}/{segment_count}，{speaker or '旁白'}说话".strip("，"),
                "visual_description": (
                    f"{raw_shot.get('visual_description') or raw_shot.get('prompt') or ''}"
                    f" 本镜头只表现{speaker or '旁白'}这一段台词，口型与字幕同步。"
                ).strip(),
                "extra_data": {
                    **extra_data,
                    "dialogue_speaker": speaker or extra_data.get("dialogue_speaker"),
                    "dialogue_source": extra_data.get("dialogue_source") or "split_multi_speaker_dialogue",
                    "subtitle_text": _format_storyboard_dialogue_line(speaker, text),
                    "dialogue_segment_index": segment_index,
                    "dialogue_segment_count": segment_count,
                    "split_from_shot_number": raw_shot.get("shot_number"),
                    "split_reason": "multi_speaker_dialogue",
                },
            }
            split_shots.append(shot)

    for index, shot in enumerate(split_shots, start=1):
        shot["shot_number"] = index
    return split_shots


def _dialogue_dedupe_key(dialogue: Optional[str]) -> str:
    text = re.sub(r"\s+", "", dialogue or "")
    text = re.sub(r"^（旁白）", "旁白：", text)
    return text.strip("。！？!?,，；;")


def _fallback_dialogue_from_shot_context(shot: dict) -> str:
    extra_data = shot.get("extra_data") if isinstance(shot.get("extra_data"), dict) else {}
    source = (
        extra_data.get("source_beat")
        or extra_data.get("source_scene_beat")
        or shot.get("prompt")
        or shot.get("visual_description")
        or ""
    )
    text = _compact_scene_text(str(source), 42)
    if not text:
        return ""
    if not text.endswith(("。", "！", "？", "；", "!", "?", ";")):
        text = f"{text}。"
    return f"（旁白）{text}"


def dedupe_repeated_shot_dialogues(shots_data: list[dict]) -> list[dict]:
    """Rewrite duplicate shot dialogue to shot-specific narration."""
    seen: set[str] = set()
    for shot in shots_data:
        dialogue = (shot.get("dialogue") or "").strip()
        key = _dialogue_dedupe_key(dialogue)
        if not key:
            continue
        if key not in seen:
            seen.add(key)
            continue
        replacement = _fallback_dialogue_from_shot_context(shot)
        replacement_key = _dialogue_dedupe_key(replacement)
        if not replacement or replacement_key in seen:
            continue
        extra_data = shot.get("extra_data") if isinstance(shot.get("extra_data"), dict) else {}
        shot["dialogue"] = replacement
        shot["extra_data"] = {
            **extra_data,
            "subtitle_text": replacement,
            "dialogue_speaker": "旁白",
            "dialogue_rewritten_reason": "duplicate_dialogue",
            "original_dialogue": dialogue,
        }
        seen.add(replacement_key)
    return shots_data


def prepare_storyboard_shots_for_production(shots_data: list[dict]) -> list[dict]:
    return dedupe_repeated_shot_dialogues(split_multi_speaker_dialogue_shots(shots_data))


def _compact_scene_text(value: Optional[str], limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", value or "").strip(" -：:，。")
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


SCRIPT_SCENE_SECTION_LABELS = (
    "场景类型",
    "时长",
    "地点",
    "人物",
    "戏剧核心",
    "画面描述",
    "对话/旁白",
    "镜头序列",
    "音效/音乐提示",
    "字幕要点",
)


def _extract_plain_script_scene_section(block: str, label: str) -> str:
    labels = "|".join(re.escape(item) for item in SCRIPT_SCENE_SECTION_LABELS)
    match = re.search(
        rf"^\s*{re.escape(label)}\s*[：:]\s*(?P<body>.*?)(?=^\s*(?:{labels})\s*[：:]|\Z)",
        block,
        flags=re.S | re.M,
    )
    return match.group("body") if match else ""


def _extract_script_scene_field(block: str, label: str) -> str:
    match = re.search(
        rf"【{re.escape(label)}】(?P<body>.*?)(?=【(?:画面描述|对话/旁白|镜头序列|音效/音乐提示|字幕要点)】|$)",
        block,
        flags=re.S,
    )
    body = match.group("body") if match else _extract_plain_script_scene_section(block, label)
    return _compact_scene_text(body)


def _extract_script_scene_people(block: str) -> str:
    match = re.search(r"^\s*(?:-\s*)?人物[：:]\s*(.+?)\s*$", block, flags=re.M)
    return _compact_scene_text(match.group(1) if match else "")


def _clean_script_dialogue_text(value: str) -> str:
    text = (value or "").strip()
    text = re.sub(r"^(?:【[^】]{1,30}】|\[[^\]]{1,30}\])\s*", "", text)
    return text.strip()


def _extract_script_scene_dialogues(block: str) -> list[str]:
    dialogues: list[str] = []
    section_match = re.search(
        r"【对话/旁白】(?P<body>.*?)(?=【(?:画面描述|镜头序列|音效/音乐提示|字幕要点)】|$)",
        block,
        flags=re.S,
    )
    source = (
        section_match.group("body")
        if section_match
        else _extract_plain_script_scene_section(block, "对话/旁白") or block
    )
    for line in source.splitlines() or [source]:
        text = line.strip()
        if not text or re.search(r"无对白|纯音效", text):
            continue
        narrator = re.match(r"^\s*[-—]?\s*（\s*([^）]{1,12})\s*）\s*[：:]?\s*(.+)$", text)
        if narrator:
            speaker = narrator.group(1).strip()
            dialogue_text = _clean_script_dialogue_text(narrator.group(2))
            if speaker in NARRATOR_SPEAKERS and dialogue_text:
                dialogues.append(f"（旁白）{dialogue_text}")
            continue
        match = re.match(r"^\s*[-—]?\s*([^：:（）()，。！？\n]{1,16})\s*[：:]\s*(.+)$", text)
        if not match:
            continue
        speaker = match.group(1).strip()
        dialogue_text = match.group(2).strip()
        if speaker in {"环境音", "背景音乐", "字幕要点", "场景类型", "时长", "地点", "人物", "戏剧核心"}:
            continue
        dialogue_text = _clean_script_dialogue_text(dialogue_text)
        if speaker and dialogue_text:
            dialogues.append(f"{speaker}：{dialogue_text}")
    return dialogues


def extract_script_scene_beats(content: Optional[str]) -> list[dict[str, Any]]:
    script_text = content or ""
    scene_matches = list(re.finditer(r"^\s*(?:【\s*)?第\s*[\d一二三四五六七八九十]+\s*场(?:\s*】)?[^\n]*", script_text, flags=re.M))
    scenes: list[dict[str, Any]] = []
    for index, match in enumerate(scene_matches):
        next_start = scene_matches[index + 1].start() if index + 1 < len(scene_matches) else len(script_text)
        scene_label = f"第{index + 1}场"
        raw_title = re.sub(r"^\s*(?:【\s*)?第\s*[\d一二三四五六七八九十]+\s*场(?:\s*】)?", "", match.group(0)).strip()
        block = script_text[match.end():next_start]
        visual = _extract_script_scene_field(block, "画面描述")
        people = _extract_script_scene_people(block)
        dialogues = _extract_script_scene_dialogues(block)
        beat_parts = [
            raw_title or scene_label,
            f"人物：{people}" if people else None,
            f"画面：{visual}" if visual else None,
            f"对白：{' / '.join(dialogues)}" if dialogues else None,
        ]
        scenes.append(
            {
                "title": raw_title or scene_label,
                "people": people,
                "visual": visual,
                "dialogues": dialogues,
                "beat": "。".join(part for part in beat_parts if part),
            }
        )
    return [scene for scene in scenes if scene["beat"]]


def apply_script_scene_beats_to_template_shots(
    shots_data: list[dict],
    scenes: list[dict[str, Any]],
    *,
    source_title: str,
) -> list[dict]:
    if not scenes:
        return shots_data
    for index, shot in enumerate(shots_data):
        scene = scenes[min(index, len(scenes) - 1)]
        dialogues = scene.get("dialogues") or []
        dialogue = "\n".join(dialogues) if dialogues else shot.get("dialogue")
        scene_visual = scene.get("visual") or scene.get("beat") or ""
        shot["prompt"] = f"{source_title}，{scene.get('title')}，{_compact_scene_text(scene_visual, 80)}"
        shot["visual_description"] = (
            f"{scene_visual}。保持人物、场景、道具状态和对白顺序连续，动漫电影质感。"
        )
        shot["dialogue"] = dialogue
        extra_data = shot.get("extra_data") if isinstance(shot.get("extra_data"), dict) else {}
        shot["extra_data"] = {
            **extra_data,
            "source_scene_title": scene.get("title"),
            "source_scene_beat": scene.get("beat"),
            "dialogue_source": "script_scene_dialogue" if dialogues else extra_data.get("dialogue_source"),
            "subtitle_text": dialogue or extra_data.get("subtitle_text"),
            "script_scene_dialogues": dialogues,
        }
    return shots_data


async def persist_storyboard_with_shots(
    db: AsyncSession,
    *,
    user_id: str,
    script_id: str,
    script_title: Optional[str],
    storyboard_title: str,
    novel_id: Optional[str],
    genre: Optional[str],
    style: str,
    description: str,
    content: dict,
    shots_data: list[dict],
    template: Optional[dict] = None,
    source_content: Optional[str] = None,
    continuity_context: Optional[dict] = None,
    dialogue_source: Optional[str] = None,
) -> tuple[Storyboard, list[dict]]:
    storyboard_id = str(uuid.uuid4())
    total_duration = sum(int(s.get("duration") or 4) for s in shots_data)
    db_storyboard = Storyboard(
        id=storyboard_id,
        script_id=script_id,
        user_id=user_id,
        title=storyboard_title,
        novel_id=novel_id,
        style=style,
        genre=genre,
        description=description,
        content=content,
        shot_count=len(shots_data),
        total_duration=total_duration,
        status="draft",
    )
    db.add(db_storyboard)

    created_shots: list[dict] = []
    chapter_id = (content or {}).get("chapter_id")
    for index, raw_shot in enumerate(shots_data):
        shot_data = normalize_shot_data(raw_shot, index, template)
        ensure_shot_dialogue_subtitle(shot_data)
        shot_text = " ".join(
            value
            for value in (
                shot_data.get("prompt"),
                shot_data.get("dialogue"),
                shot_data.get("visual_description"),
                shot_data.get("ambient_sound"),
                shot_data.get("sfx_cue"),
                shot_data.get("music_cue"),
            )
            if value
        )
        entity_context = await build_shot_entity_context(
            db,
            user_id,
            novel_id=novel_id,
            chapter_id=chapter_id,
            source_text=source_content,
            shot_text=shot_text,
        )
        shot_data["character_refs"] = shot_data["character_refs"] or entity_context["character_refs"]
        dialogue_metadata = build_dialogue_metadata(
            shot_data,
            shot_data["character_refs"],
            dialogue_source=dialogue_source,
        )
        shot_data["extra_data"] = {
            **shot_data["extra_data"],
            **{key: value for key, value in dialogue_metadata.items() if value is not None},
            "novel_continuity": continuity_context or None,
            "novel_series_seed": (continuity_context or {}).get("novel_series_seed"),
            "chapter_seed": (continuity_context or {}).get("chapter_seed"),
            "continuity_lock": (continuity_context or {}).get("continuity_lock"),
            "chapter_state_snapshot": (continuity_context or {}).get("chapter_state_snapshot"),
            "previous_chapter_context": (continuity_context or {}).get("previous_chapter_context"),
            "entity_refs": entity_context["entity_refs"],
            "scene_refs": entity_context["scene_refs"],
            "prop_refs": entity_context["prop_refs"],
            "event_refs": entity_context["event_refs"],
            "environment_context": entity_context["environment_context"],
            "subtitle_text": shot_data["extra_data"].get("subtitle_text") or shot_data.get("dialogue"),
        }
        db_shot = Shot(
            id=str(uuid.uuid4()),
            storyboard_id=storyboard_id,
            user_id=user_id,
            shot_number=shot_data["shot_number"],
            duration=shot_data["duration"],
            prompt=shot_data["prompt"],
            dialogue=shot_data["dialogue"],
            visual_description=shot_data["visual_description"],
            camera_angle=shot_data["camera_angle"],
            camera_movement=shot_data["camera_movement"],
            movement_speed=shot_data["movement_speed"],
            emotion=shot_data["emotion"],
            emotion_intensity=shot_data["emotion_intensity"],
            lighting=shot_data["lighting"],
            color_grading=shot_data["color_grading"],
            sfx_cue=shot_data["sfx_cue"],
            music_cue=shot_data["music_cue"],
            ambient_sound=shot_data["ambient_sound"],
            keyframes=shot_data["keyframes"],
            video_status="pending",
            audio_status="pending",
            image_status="pending",
            version=1,
            character_refs=shot_data["character_refs"],
            extra_data=shot_data["extra_data"],
        )
        db.add(db_shot)
        created_shots.append(
            {
                "id": db_shot.id,
                "shot_number": db_shot.shot_number,
                "duration": db_shot.duration,
                "prompt": db_shot.prompt,
                "dialogue": db_shot.dialogue,
                "visual_description": db_shot.visual_description,
                "camera_angle": db_shot.camera_angle,
                "character_refs": db_shot.character_refs,
                "extra_data": db_shot.extra_data,
            }
        )

    await db.commit()
    await db.refresh(db_storyboard)
    return db_storyboard, created_shots


def build_storyboard_response(
    storyboard: Storyboard,
    script_title: Optional[str] = None,
) -> StoryboardResponse:
    content = storyboard.content if isinstance(storyboard.content, dict) else {}
    return StoryboardResponse(
        id=str(storyboard.id),
        script_id=str(storyboard.script_id),
        user_id=str(storyboard.user_id),
        novel_id=str(storyboard.novel_id) if storyboard.novel_id else None,
        chapter_id=content.get("chapter_id"),
        title=normalize_duplicate_chapter_label_text(storyboard.title) or storyboard.title,
        script_title=script_title,
        description=storyboard.description,
        content=storyboard.content,
        shot_count=storyboard.shot_count or 0,
        total_duration=storyboard.total_duration or 0,
        status=storyboard.status or "draft",
        created_at=str(storyboard.created_at),
        updated_at=str(storyboard.updated_at),
    )


# ============== API 端点 ==============

@router.get("/templates", response_model=List[StoryboardTemplateResponse])
async def list_storyboard_templates(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取预制分镜模板库。"""
    templates = await load_user_storyboard_templates(db, user_id)
    return [build_template_response(template) for template in templates]


@router.post("/templates/match", response_model=StoryboardTemplateMatchResponse)
async def match_storyboard_template_endpoint(
    request: StoryboardSmartGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """根据小说/章节内容自动匹配最合适的分镜模板。"""
    novel, _chapter, source_title, source_content = await get_generation_source(
        db, user_id, request.novel_id, request.chapter_id
    )
    templates = await load_user_storyboard_templates(db, user_id)
    match = match_storyboard_template(
        title=source_title,
        genre=novel.genre or "",
        content=source_content,
        template_id=request.template_id,
        templates=templates,
    )
    return StoryboardTemplateMatchResponse(
        template=build_template_response(match["template"]),
        score=match["score"],
        reason=match["reason"],
    )


@router.get("", response_model=List[StoryboardResponse])
async def list_storyboards(
    script_id: Optional[str] = Query(None, description="按剧本过滤"),
    novel_id: Optional[str] = Query(None, description="按小说过滤"),
    chapter_id: Optional[str] = Query(None, description="按章节过滤"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取分镜列表，支持小说/章节/剧本过滤。"""
    query = select(Storyboard).where(Storyboard.user_id == user_id)
    script_title = None
    if script_id:
        script = await get_script_for_user(db, script_id, user_id)
        script_title = script.title
        query = query.where(Storyboard.script_id == script_id)
    if novel_id:
        query = query.where(Storyboard.novel_id == novel_id)
    result = await db.execute(query.order_by(desc(Storyboard.created_at)).limit(200))
    storyboards = list(result.scalars().all())
    if chapter_id:
        storyboards = [
            storyboard for storyboard in storyboards
            if isinstance(storyboard.content, dict) and storyboard.content.get("chapter_id") == chapter_id
        ]
    script_ids = {storyboard.script_id for storyboard in storyboards}
    script_title_map = {}
    if script_ids:
        script_result = await db.execute(
            select(Script).where(and_(Script.user_id == user_id, Script.id.in_(script_ids)))
        )
        script_title_map = {script.id: script.title for script in script_result.scalars().all()}
    if script_id and script_title:
        script_title_map[script_id] = script_title
    return [
        build_storyboard_response(storyboard, script_title_map.get(storyboard.script_id))
        for storyboard in storyboards
    ]


@router.get("/script/{script_id}", response_model=List[StoryboardResponse])
async def list_storyboards_by_script(
    script_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取指定剧本的所有分镜"""
    script = await get_script_for_user(db, script_id, user_id)

    result = await db.execute(
        select(Storyboard)
        .where(and_(Storyboard.script_id == script_id, Storyboard.user_id == user_id))
        .order_by(desc(Storyboard.created_at))
    )
    storyboards = result.scalars().all()

    return [build_storyboard_response(storyboard, script.title) for storyboard in storyboards]


@router.get("/{storyboard_id}", response_model=StoryboardResponse)
async def get_storyboard(
    storyboard_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取单个分镜"""
    result = await db.execute(
        select(Storyboard).where(and_(Storyboard.id == storyboard_id, Storyboard.user_id == user_id))
    )
    storyboard = result.scalar_one_or_none()

    if not storyboard:
        raise HTTPException(status_code=404, detail="分镜不存在")

    script = await get_script_for_user(db, storyboard.script_id, user_id)
    return build_storyboard_response(storyboard, script.title)


@router.post("", response_model=StoryboardResponse, status_code=status.HTTP_201_CREATED)
async def create_storyboard(
    storyboard: StoryboardCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """创建分镜"""
    script = await get_script_for_user(db, storyboard.script_id, user_id)
    script_extra = script.extra_data if isinstance(script.extra_data, dict) else {}
    storyboard_content = storyboard.content or {}
    if script_extra.get("chapter_id") and "chapter_id" not in storyboard_content:
        storyboard_content["chapter_id"] = script_extra["chapter_id"]

    storyboard_id = str(uuid.uuid4())

    db_storyboard = Storyboard(
        id=storyboard_id,
        script_id=storyboard.script_id,
        user_id=user_id,
        title=storyboard.title,
        novel_id=script.novel_id,
        description=storyboard.description,
        content=storyboard_content,
        status="draft"
    )

    db.add(db_storyboard)
    await db.commit()
    await db.refresh(db_storyboard)

    return build_storyboard_response(db_storyboard, script.title)


@router.put("/{storyboard_id}", response_model=StoryboardResponse)
async def update_storyboard(
    storyboard_id: str,
    storyboard_update: StoryboardUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """更新分镜"""
    result = await db.execute(
        select(Storyboard).where(and_(Storyboard.id == storyboard_id, Storyboard.user_id == user_id))
    )
    db_storyboard = result.scalar_one_or_none()

    if not db_storyboard:
        raise HTTPException(status_code=404, detail="分镜不存在")

    update_data = storyboard_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_storyboard, key, value)

    await db.commit()
    await db.refresh(db_storyboard)

    script = await get_script_for_user(db, db_storyboard.script_id, user_id)
    return build_storyboard_response(db_storyboard, script.title)


@router.delete("/{storyboard_id}")
async def delete_storyboard(
    storyboard_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """删除分镜"""
    result = await db.execute(
        select(Storyboard).where(and_(Storyboard.id == storyboard_id, Storyboard.user_id == user_id))
    )
    db_storyboard = result.scalar_one_or_none()

    if not db_storyboard:
        raise HTTPException(status_code=404, detail="分镜不存在")

    shots_result = await db.execute(
        select(Shot).where(and_(Shot.storyboard_id == storyboard_id, Shot.user_id == user_id))
    )
    shots = list(shots_result.scalars().all())
    for shot in shots:
        await db.delete(shot)

    await db.delete(db_storyboard)
    await db.commit()

    return {"message": "分镜已删除", "deleted_shot_count": len(shots)}


@router.post("/{storyboard_id}/merge-videos", response_model=StoryboardMergeVideosResponse)
async def merge_storyboard_videos(
    storyboard_id: str,
    request: StoryboardMergeVideosRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """将当前分镜下已生成的镜头视频合并为一个可追踪成片任务。"""
    result = await db.execute(
        select(Storyboard).where(and_(Storyboard.id == storyboard_id, Storyboard.user_id == user_id))
    )
    storyboard = result.scalar_one_or_none()
    if not storyboard:
        raise HTTPException(status_code=404, detail="分镜不存在")

    script_result = await db.execute(
        select(Script).where(and_(Script.id == storyboard.script_id, Script.user_id == user_id))
    )
    script = script_result.scalar_one_or_none()
    if not script:
        raise HTTPException(status_code=404, detail="分镜关联的剧本不存在")

    shots_result = await db.execute(
        select(Shot)
        .where(and_(Shot.storyboard_id == storyboard_id, Shot.user_id == user_id))
        .order_by(Shot.shot_number, Shot.created_at)
    )
    shots = list(shots_result.scalars().all())
    if not shots:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="当前分镜没有镜头，无法合并视频")

    requested_shot_ids = list(dict.fromkeys(request.shot_ids or []))
    shot_by_id = {shot.id: shot for shot in shots}
    if requested_shot_ids:
        missing_ids = [shot_id for shot_id in requested_shot_ids if shot_id not in shot_by_id]
        if missing_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"以下镜头不存在或不属于当前分镜：{', '.join(missing_ids)}",
            )
        selected_shots = [shot_by_id[shot_id] for shot_id in requested_shot_ids]
        skipped_shot_numbers: list[int] = []
    else:
        selected_shots = [shot for shot in shots if (shot.video_url or "").strip()]
        skipped_shot_numbers = [
            int(shot.shot_number or index + 1)
            for index, shot in enumerate(shots)
            if not (shot.video_url or "").strip()
        ]
    if not selected_shots:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="没有可合并的视频镜头，请先选择已有视频的镜头或生成镜头视频",
        )

    missing_video_numbers = [
        f"镜头 {shot.shot_number or index + 1}"
        for index, shot in enumerate(selected_shots)
        if not (shot.video_url or "").strip()
    ]
    if missing_video_numbers:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"以下已选镜头缺少可合并的视频URL：{', '.join(missing_video_numbers)}。请先生成这些镜头的视频。",
        )

    local_video_paths_by_shot_id = {
        shot.id: _media_url_to_local_static_path(shot.video_url)
        for shot in selected_shots
    }
    probed_durations_by_shot_id: dict[str, float] = {}
    if request.render_strategy in {"auto", "ffmpeg"}:
        for shot in selected_shots:
            local_path = local_video_paths_by_shot_id.get(shot.id)
            if local_path is None:
                continue
            probed_duration = await asyncio.to_thread(_probe_video_duration_seconds, local_path)
            if probed_duration:
                probed_durations_by_shot_id[shot.id] = probed_duration

    content = _storyboard_content(storyboard)
    script_extra = _script_extra(script)
    novel_id = storyboard.novel_id or script.novel_id or content.get("novel_id")
    chapter_id = content.get("chapter_id") or script.chapter_id or script_extra.get("chapter_id")
    novel_title: Optional[str] = None
    chapter_title: Optional[str] = None
    chapter_number: Optional[int] = None
    if novel_id:
        novel_result = await db.execute(
            select(Novel).where(and_(Novel.id == novel_id, Novel.user_id == user_id))
        )
        novel = novel_result.scalar_one_or_none()
        novel_title = novel.title if novel else None
    if chapter_id:
        chapter_result = await db.execute(
            select(Chapter).where(and_(Chapter.id == chapter_id, Chapter.user_id == user_id))
        )
        chapter = chapter_result.scalar_one_or_none()
        if chapter:
            chapter_title = chapter.title
            chapter_number = chapter.chapter_number

    segments: list[dict[str, Any]] = []
    current_time = 0.0
    first_audio_url: Optional[str] = None
    for index, shot in enumerate(selected_shots, start=1):
        shot_extra = _shot_extra(shot)
        configured_duration_seconds = float(shot.duration or 4)
        if configured_duration_seconds <= 0:
            configured_duration_seconds = 4.0
        duration_seconds = probed_durations_by_shot_id.get(shot.id) or configured_duration_seconds
        duration_source = "media_probe" if shot.id in probed_durations_by_shot_id else "shot_duration"
        audio_url = (shot.audio_url or "").strip() or None
        if audio_url and not first_audio_url:
            first_audio_url = audio_url
        subtitle_text = ""
        if request.include_subtitles and request.subtitle_mode != "off":
            subtitle_text = (shot_extra.get("subtitle_text") or shot.dialogue or "").strip()
        segment = {
            "index": index,
            "shot_id": shot.id,
            "shot_number": shot.shot_number or index,
            "start_seconds": round(current_time, 3),
            "duration_seconds": round(duration_seconds, 3),
            "end_seconds": round(current_time + duration_seconds, 3),
            "video": {
                "url": shot.video_url,
                "duration_seconds": duration_seconds,
                "configured_duration_seconds": configured_duration_seconds,
                "duration_source": duration_source,
                "prompt": shot.prompt,
                "cover_url": shot.image_url,
                "source_type": "shot_video_url",
            },
            "audio": {
                "url": audio_url,
                "duration_seconds": duration_seconds if audio_url else None,
                "text": subtitle_text or shot.dialogue,
                "mix_strategy": request.audio_mix_strategy,
                "source_type": "shot_audio_url" if audio_url else None,
            },
            "subtitle": {
                "enabled": bool(subtitle_text),
                "mode": request.subtitle_mode,
                "text": subtitle_text,
                "start_seconds": round(current_time, 3),
                "end_seconds": round(current_time + duration_seconds, 3),
            },
            "transition": {
                "style": request.transition_style if index > 1 else "none",
                "duration_seconds": request.transition_duration_seconds if index > 1 else 0,
            },
            "lineage": {
                "novel_id": novel_id,
                "novel_title": novel_title,
                "chapter_id": chapter_id,
                "chapter_title": chapter_title,
                "chapter_number": chapter_number,
                "script_id": script.id,
                "script_title": script.title,
                "storyboard_id": storyboard.id,
                "storyboard_title": storyboard.title,
                "shot_id": shot.id,
                "shot_number": shot.shot_number or index,
            },
            "shot_controls": {
                "visual_description": shot.visual_description,
                "dialogue": shot.dialogue,
                "camera_angle": shot.camera_angle,
                "camera_movement": shot.camera_movement,
                "emotion": shot.emotion,
                "lighting": shot.lighting,
                "color_grading": shot.color_grading,
                "sfx_cue": shot.sfx_cue,
                "music_cue": shot.music_cue,
                "ambient_sound": shot.ambient_sound,
                "keyframes": shot.keyframes,
                "character_refs": shot.character_refs,
                "entity_refs": shot_extra.get("entity_refs"),
                "scene_refs": shot_extra.get("scene_refs"),
                "prop_refs": shot_extra.get("prop_refs"),
                "event_refs": shot_extra.get("event_refs"),
            },
            "consistency": {
                "novel_series_seed": shot_extra.get("novel_series_seed") or content.get("novel_series_seed"),
                "chapter_seed": shot_extra.get("chapter_seed") or content.get("chapter_seed"),
                "continuity_lock": shot_extra.get("continuity_lock") or content.get("continuity_lock"),
                "production_context": shot_extra.get("production_context") or {},
            },
        }
        segments.append(segment)
        current_time += duration_seconds

    total_duration = round(current_time, 3)
    synthesis_job_id = str(uuid.uuid4())
    title = request.title or f"{storyboard.title} - 分镜成片"
    primary_lineage = {
        "project_id": storyboard.project_id or script.project_id,
        "novel_id": novel_id,
        "chapter_id": chapter_id,
        "script_id": script.id,
        "storyboard_id": storyboard.id,
    }
    version_result = await db.execute(
        select(SynthesisJob).where(
            and_(
                SynthesisJob.user_id == user_id,
                SynthesisJob.model_id == "storyboard-sequence-manifest",
                SynthesisJob.is_active == True,
            )
        )
    )
    existing_versions = [
        job
        for job in version_result.scalars().all()
        if isinstance(job.extra_data, dict)
        and job.extra_data.get("storyboard_id") == storyboard_id
        and job.extra_data.get("merge_type") == "storyboard_shot_merge"
    ]
    version_number = max(
        [int((job.extra_data or {}).get("version_number") or 0) for job in existing_versions] or [0]
    ) + 1

    srt_content = _build_storyboard_srt(segments) if request.include_subtitles and request.subtitle_mode != "off" else ""
    srt_url = _write_storyboard_export_text(f"{synthesis_job_id}.srt", srt_content) if srt_content else None
    output_url: Optional[str] = None
    render_backend = "local_manifest"
    is_real_merged = False
    render_message: Optional[str] = None
    if request.render_strategy in {"auto", "ffmpeg"}:
        local_video_paths = [local_video_paths_by_shot_id.get(str(segment["shot_id"])) for segment in segments]
        missing_local_urls = [
            str(segment["video"]["url"])
            for segment, path in zip(segments, local_video_paths)
            if path is None
        ]
        if missing_local_urls:
            render_message = f"部分视频URL不是本地 /static 文件，无法直接 FFmpeg 真拼接：{', '.join(missing_local_urls)}"
        else:
            output_path = _exports_dir() / f"{synthesis_job_id}.mp4"
            success, message = await asyncio.to_thread(
                _run_ffmpeg_concat,
                [path for path in local_video_paths if path is not None],
                output_path,
            )
            render_message = message
            if success:
                render_backend = "ffmpeg"
                is_real_merged = True
                output_url = f"/static/exports/{output_path.name}"
        if request.render_strategy == "ffmpeg" and not is_real_merged:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=render_message or "FFmpeg 真实拼接失败",
            )

    if not output_url:
        output_url = dev_synthesis_url(synthesis_job_id) if is_dev_mode() else None
        render_backend = "local_manifest"
        render_message = render_message or "已生成合成清单；当前未执行真实视频拼接"

    manifest_payload = {
        "id": synthesis_job_id,
        "type": "storyboard_final_video_manifest",
        "version": "1.0",
        "title": title,
        "user_id": user_id,
        "storyboard_id": storyboard_id,
        "lineage": primary_lineage,
        "render_backend": render_backend,
        "is_real_merged": is_real_merged,
        "render_message": render_message,
        "quality_profile": request.quality_profile,
        "audio_mix_strategy": request.audio_mix_strategy,
        "subtitle_mode": request.subtitle_mode,
        "transition_style": request.transition_style,
        "segment_count": len(segments),
        "duration_seconds": total_duration,
        "selected_shot_ids": [shot.id for shot in selected_shots],
        "selected_shot_numbers": [int(shot.shot_number or index + 1) for index, shot in enumerate(selected_shots)],
        "skipped_shot_numbers": skipped_shot_numbers,
        "version_number": version_number,
        "parent_job_id": request.parent_job_id,
        "output_url": output_url,
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
        "srt_url": srt_url,
        "created_at": utc_now().isoformat(),
    }
    manifest_url = _write_storyboard_export_json(synthesis_job_id, manifest_payload)
    dev_complete = is_dev_mode() or is_real_merged

    synthesis_job = SynthesisJob(
        id=synthesis_job_id,
        user_id=user_id,
        project_id=primary_lineage["project_id"],
        workflow_id=None,
        task_id=None,
        title=title,
        model_id="storyboard-sequence-manifest",
        model_name="FFmpeg 分镜多镜头成片" if is_real_merged else ("DEV_MODE 分镜多镜头成片清单" if dev_complete else "分镜多镜头成片清单"),
        video_url=selected_shots[0].video_url,
        audio_url=first_audio_url,
        status="succeeded" if dev_complete else "pending",
        progress=100 if is_real_merged or output_url else 20,
        output_url=output_url,
        cover_url=selected_shots[0].image_url,
        duration_seconds=total_duration,
        cost=0,
        extra_data={
            **primary_lineage,
            "merge_type": "storyboard_shot_merge",
            "storyboard_id": storyboard_id,
            "storyboard_title": storyboard.title,
            "selected_shot_ids": [shot.id for shot in selected_shots],
            "selected_shot_numbers": [int(shot.shot_number or index + 1) for index, shot in enumerate(selected_shots)],
            "skipped_shot_numbers": skipped_shot_numbers,
            "version_number": version_number,
            "parent_job_id": request.parent_job_id,
            "segment_count": len(segments),
            "duration_seconds": total_duration,
            "manifest_url": manifest_url,
            "srt_url": srt_url,
            "output_url": output_url,
            "render_backend": render_backend,
            "render_status": "ready" if is_real_merged else ("placeholder" if output_url else "pending_renderer"),
            "is_real_merged": is_real_merged,
            "render_message": render_message,
            "quality_profile": request.quality_profile,
            "audio_mix_strategy": request.audio_mix_strategy,
            "subtitle_mode": request.subtitle_mode,
            "transition_style": request.transition_style,
            "segments": segments,
        },
    )
    db.add(synthesis_job)

    storyboard.content = {
        **content,
        "latest_final_video": {
            "synthesis_job_id": synthesis_job_id,
            "output_url": output_url,
            "manifest_url": manifest_url,
            "srt_url": srt_url,
            "segment_count": len(segments),
            "duration_seconds": total_duration,
            "version_number": version_number,
            "is_real_merged": is_real_merged,
            "render_backend": render_backend,
            "render_message": render_message,
            "updated_at": utc_now().isoformat(),
        },
    }
    await db.commit()

    return StoryboardMergeVideosResponse(
        job_id=synthesis_job_id,
        storyboard_id=storyboard_id,
        message="分镜多镜头成片清单已创建",
        output_url=output_url,
        manifest_url=manifest_url,
        srt_url=srt_url,
        segment_count=len(segments),
        duration_seconds=total_duration,
        segments=segments,
        selected_shot_ids=[shot.id for shot in selected_shots],
        selected_shot_numbers=[int(shot.shot_number or index + 1) for index, shot in enumerate(selected_shots)],
        skipped_shot_numbers=skipped_shot_numbers,
        version_number=version_number,
        parent_job_id=request.parent_job_id,
        render_backend=render_backend,
        is_real_merged=is_real_merged,
        render_message=render_message,
    )


@router.get("/{storyboard_id}/merge-videos", response_model=List[StoryboardMergeVersionResponse])
async def list_storyboard_video_merge_versions(
    storyboard_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """列出当前分镜的成片合并版本。"""
    result = await db.execute(
        select(Storyboard).where(and_(Storyboard.id == storyboard_id, Storyboard.user_id == user_id))
    )
    storyboard = result.scalar_one_or_none()
    if not storyboard:
        raise HTTPException(status_code=404, detail="分镜不存在")

    jobs_result = await db.execute(
        select(SynthesisJob)
        .where(
            and_(
                SynthesisJob.user_id == user_id,
                SynthesisJob.model_id == "storyboard-sequence-manifest",
                SynthesisJob.is_active == True,
            )
        )
        .order_by(desc(SynthesisJob.created_at))
        .limit(100)
    )
    jobs = [
        job
        for job in jobs_result.scalars().all()
        if isinstance(job.extra_data, dict)
        and job.extra_data.get("storyboard_id") == storyboard_id
        and job.extra_data.get("merge_type") == "storyboard_shot_merge"
    ]
    return [_build_storyboard_merge_version_response(job) for job in jobs]


async def generate_script_storyboard_template_fallback(
    *,
    request: StoryboardGenerateRequest,
    script: Script,
    script_title: str,
    db: AsyncSession,
    user_id: str,
) -> StoryboardGenerateResponse:
    """DEV_MODE-only deterministic storyboard fallback for script-driven generation."""
    script_scene_beats = extract_script_scene_beats(script.content)
    scene_source_content = (
        "\n".join(scene["beat"] for scene in script_scene_beats)
        if script_scene_beats
        else script.content or ""
    )
    templates = await load_user_storyboard_templates(db, user_id)
    template_match = match_storyboard_template(
        title=script_title,
        genre=script.genre or "",
        content=scene_source_content,
        templates=templates,
    )
    template = template_match["template"]
    shot_count_plan = plan_storyboard_shot_count(
        template=template,
        source_content=scene_source_content,
        requested_shot_count=request.shot_count or (len(script_scene_beats) if script_scene_beats else None),
    )
    if script_scene_beats and request.shot_count is None:
        shot_count_plan = {
            **shot_count_plan,
            "source": "script_scene_count",
            "reason": "根据剧本场次自动规划镜头数量",
        }
    inferred_novel_id = request.novel_id or script.novel_id
    script_extra = script.extra_data if isinstance(script.extra_data, dict) else {}
    source_chapter_id = script.chapter_id or script_extra.get("chapter_id")
    story_prompt_context = await load_story_prompt_context(
        db,
        user_id,
        novel_id=inferred_novel_id,
        chapter_id=source_chapter_id,
        script_id=script.id,
        title=script_title,
        genre=script.genre,
        description=script.content,
        style=request.style,
    )
    novel_continuity = await build_novel_continuity_package(
        db,
        user_id,
        novel_id=inferred_novel_id,
        chapter_id=source_chapter_id,
        story_bible_id=request.story_bible_id,
        project_id=request.project_id,
        task="storyboard_generation",
    )
    shots_data = build_template_shots(
        template=template,
        source_title=script_title,
        source_content=scene_source_content,
        shot_count=shot_count_plan["shot_count"],
        story_context=build_shot_dialogue_context(story_prompt_context),
    )
    shots_data = apply_script_scene_beats_to_template_shots(
        shots_data,
        script_scene_beats,
        source_title=script_title,
    )
    # Script template fallback should preserve the requested/scene shot count;
    # segmented TTS can still split multi-speaker dialogue later if needed.
    shots_data = dedupe_repeated_shot_dialogues(shots_data)

    storyboard_title = f"{script_title} - 分镜"
    title_index = 2
    while True:
        title_result = await db.execute(
            select(Storyboard).where(
                and_(
                    Storyboard.user_id == user_id,
                    Storyboard.script_id == request.script_id,
                    Storyboard.title == storyboard_title,
                )
            )
        )
        if title_result.scalar_one_or_none() is None:
            break
        storyboard_title = f"{script_title} - 分镜 {title_index}"
        title_index += 1

    content = {
        "source": "script_storyboard_template_fallback",
        "shots_summary": f"共{len(shots_data)}个镜头",
        "novel_id": inferred_novel_id,
        "chapter_id": source_chapter_id,
        "story_bible_id": request.story_bible_id,
        "project_id": request.project_id,
        "template_id": template["id"],
        "template_name": template["name"],
        "template_match_score": template_match["score"],
        "template_match_reason": template_match["reason"],
        "shot_count_plan": shot_count_plan,
        "script_scene_count": len(script_scene_beats),
        "ai_refined": False,
        "review_status": "pending_review",
        "automation_level": "template_draft",
        "novel_continuity": novel_continuity,
        "novel_series_seed": novel_continuity.get("novel_series_seed"),
        "chapter_seed": novel_continuity.get("chapter_seed"),
        "continuity_lock": novel_continuity.get("continuity_lock"),
    }
    description = f"模板兜底：{template['name']}，{template_match['reason']}，共{len(shots_data)}个镜头"
    db_storyboard, created_shots = await persist_storyboard_with_shots(
        db,
        user_id=user_id,
        script_id=request.script_id,
        script_title=script_title,
        storyboard_title=storyboard_title,
        novel_id=inferred_novel_id,
        genre=script.genre,
        style=request.style,
        description=description,
        content=content,
        shots_data=shots_data,
        template=template,
        source_content=script.content,
        continuity_context=novel_continuity,
        dialogue_source="script",
    )

    return StoryboardGenerateResponse(
        id=str(db_storyboard.id),
        script_id=str(request.script_id),
        user_id=str(user_id),
        novel_id=inferred_novel_id,
        chapter_id=source_chapter_id,
        title=storyboard_title,
        script_title=script_title,
        description=description,
        content=content,
        shot_count=len(shots_data),
        total_duration=db_storyboard.total_duration or 0,
        status=db_storyboard.status or "draft",
        shots=[ShotBriefResponse(**s) for s in created_shots],
        created_at=str(db_storyboard.created_at),
        updated_at=str(db_storyboard.updated_at),
    )


@router.post("/generate", response_model=StoryboardGenerateResponse, status_code=status.HTTP_201_CREATED)
async def generate_storyboard(
    request: StoryboardGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """AI生成分镜 - 将剧本内容转换为详细的分镜列表（含镜头信息）"""
    # 获取剧本信息
    script = await get_script_for_user(db, request.script_id, user_id)
    script_title = normalize_duplicate_chapter_label_text(script.title) or script.title

    if not script.content:
        raise HTTPException(status_code=400, detail="剧本内容为空，无法生成分镜")

    # 获取用户的API密钥
    try:
        api_key, provider_name, model_id, base_url = await get_user_qwen_api_key(
            db,
            user_id,
            request.model_config_id,
        )
    except HTTPException:
        if not is_dev_mode():
            raise
        return await generate_script_storyboard_template_fallback(
            request=request,
            script=script,
            script_title=script_title,
            db=db,
            user_id=user_id,
        )

    service = create_text_generation_service(api_key, provider_name, base_url)

    templates = await load_user_storyboard_templates(db, user_id)
    template_match = match_storyboard_template(
        title=script_title,
        genre=script.genre or "",
        content=script.content,
        templates=templates,
    )
    shot_count_plan = plan_storyboard_shot_count(
        template=template_match["template"],
        source_content=script.content,
        requested_shot_count=request.shot_count,
    )
    planned_shot_count = shot_count_plan["shot_count"]

    # 构建分镜生成提示词
    shot_count_hint = f"生成{planned_shot_count}个镜头"
    style_hint = f"风格：{request.style}"
    consistency_prompt = ""
    inferred_novel_id = request.novel_id or script.novel_id
    script_extra = script.extra_data if isinstance(script.extra_data, dict) else {}
    source_chapter_id = script.chapter_id or script_extra.get("chapter_id")
    novel_continuity = await build_novel_continuity_package(
        db,
        user_id,
        novel_id=inferred_novel_id,
        chapter_id=source_chapter_id,
        story_bible_id=request.story_bible_id,
        project_id=request.project_id,
        model_id=model_id,
        task="storyboard_generation",
    )
    dialogue_sample = _extract_first_dialogue_line(script.content)
    prompt_skill_context = {
        "title": script_title,
        "script_title": script_title,
        "source_title": script_title,
        "source_content": _compact_prompt_context_value(script.content),
        "genre": script.genre or "",
        "style": request.style,
        "shot_count": planned_shot_count,
        "shot_count_plan": shot_count_plan,
        "dialogue": dialogue_sample,
        "subtitle_text": dialogue_sample,
    }
    if request.use_consistency_context:
        context = await build_consistency_prompt(
            db,
            user_id,
            task="storyboard_generation",
            base_prompt=script.content,
            story_bible_id=request.story_bible_id,
            project_id=request.project_id,
            novel_id=inferred_novel_id,
            extra_context={
                **prompt_skill_context,
                "分镜风格": request.style,
                "镜头数量": planned_shot_count,
                "镜头数量规划": shot_count_plan.get("reason"),
                "剧本标题": script_title,
                "整部小说连续性锁": novel_continuity.get("prompt_block"),
            },
        )
        consistency_prompt = context["prompt"]

    # 风格详细配置
    style_configs = {
        "anime": "动画风格：鲜艳色彩、夸张表情、流畅动作、幻想元素，镜头节奏明快",
        "anime_cartoon": "动画卡通风格：简化造型、可爱角色，明快节奏，适合轻松剧情",
        "realistic": "写实风格：真实光影、细腻表演，自然对话，电影感镜头",
        "cyberpunk": "赛博朋克风格：霓虹光效、高科技设定，未来城市感，冷色调",
        "fantasy": "奇幻风格：魔法效果、异世界设定、史诗场景，大场面调度",
    }
    style_detail = style_configs.get(request.style, f"风格：{request.style or '默认'}")

    system_prompt = f"""你是一个专业的电影分镜导演。你需要将剧本内容转换为详细的、可执行的分镜列表。

【基本信息】
- 书名：《{script_title or '未知'}》
- 剧本风格：{style_detail}
- 镜头数量：{shot_count_hint}
- **全程使用中文输出所有内容**

【分镜要求】
每个镜头包含以下字段（严格JSON数组格式）：

1. shot_number: 镜头序号（从1开始）
2. duration: 镜头时长（秒），通常3-8秒
3. shot_type: 镜头类型（establishing/action/reaction/dialogue/transition/summary）
4. prompt: 视频生成Prompt（AI视频生成核心描述，20-50字，画面感强，中文）
5. dialogue: 台词/配音（如有，中文）
6. visual_description: 视觉描述（构图、光线、色彩、人物位置、表情、动作细节，50-100字，中文）
7. camera_angle: 镜头角度（wide/medium/close-up/extreme-close-up/over-shoulder/dutch/two-shot/aerial）
8. camera_movement: 运镜方式（固定/推/拉/摇/移/跟/手持/升降）
9. sound_effect: 音效提示（风声、雨声、脚步、武器碰撞等，中文）
10. music_mood: 配乐氛围（紧张悬疑/轻松愉悦/史诗大气/悲伤抒情/战斗激烈，中文）
11. extra_data: 可选，包含 dialogue_speaker、dialogue_source、dialogue_intent

【输出格式】
严格按JSON数组格式输出，不要包含markdown代码块或其他任何额外文字：
[{{"shot_number":1,...}},...]

【示例】
[{{"shot_number":1,"duration":5,"shot_type":"establishing","prompt":"清晨山顶，少年剑客负手而立，远眺云海翻涌","dialogue":"（旁白）江湖之大，何处是我归途？","visual_description":"远景镜头，少年剑客背对观众，白色长袍随风飘动，脚下云海翻涌，朝阳初升，光线金色","camera_angle":"wide","camera_movement":"缓慢拉远","sound_effect":"风声、山谷回响","music_mood":"史诗大气"}},...]

【创作要点】
1. **戏剧冲突优先**：每个镜头必须推动剧情，不能有冗余的过渡镜头
2. **视觉节奏**：紧张动作场景用短镜头（2-4秒），舒缓场景可用长镜头（8-12秒）
3. **画面连贯**：相邻镜头的角度和运动要有逻辑衔接
4. **玄幻特效**：修仙/奇幻类注意功法光效、灵气色彩、武器特效描写
5. **对白继承**：优先从剧本原对白中提炼和压缩台词，不要改变说话人；缺少原对白时才按角色性格补写短句
6. **说话人格式**：dialogue 必须使用“角色名：台词”或“（旁白）台词”，禁止使用角色A/角色B/某人
7. **短剧节奏**：首镜头保留冲突钩子或关键疑问，单句对白尽量短，适合字幕和配音
8. **中文输出**：所有描述、台词、音效、氛围必须使用中文"""

    if consistency_prompt:
        system_prompt += f"\n\n【全局一致性约束】\n{consistency_prompt}"
    if novel_continuity:
        system_prompt += f"\n\n{novel_continuity.get('prompt_block')}"
    if not consistency_prompt:
        prompt_result = await apply_active_prompt_skill_template(
            db,
            user_id,
            task="storyboard_generation",
            internal_prompt=system_prompt,
            context=prompt_skill_context,
        )
        system_prompt = prompt_result["prompt"]

    try:
        response = await service.safe_chat_completion(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"请为以下剧本生成分镜：\n\n【剧本标题】{script_title}\n【剧本内容】\n{script.content}"}
            ],
            temperature=0.7,
            max_tokens=8000
        )

        content = response["choices"][0]["message"]["content"]

        # 解析JSON
        import json
        json_str = content.strip()
        if json_str.startswith("```json"):
            json_str = json_str[7:]
        if json_str.startswith("```"):
            json_str = json_str[3:]
        if json_str.endswith("```"):
            json_str = json_str[:-3]
        json_str = json_str.strip()

        shots_data = json.loads(json_str)
        if not isinstance(shots_data, list):
            shots_data = [shots_data]

    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI返回内容解析失败: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI生成分镜失败: {str(e)}"
    )
    if request.shot_count is not None:
        shots_data = dedupe_repeated_shot_dialogues(shots_data)
    else:
        shots_data = prepare_storyboard_shots_for_production(shots_data)

    now = utc_now()
    storyboard_title = f"{script_title} - 分镜"
    title_index = 2
    while True:
        title_result = await db.execute(
            select(Storyboard).where(
                and_(
                    Storyboard.user_id == user_id,
                    Storyboard.script_id == request.script_id,
                    Storyboard.title == storyboard_title,
                )
            )
        )
        if title_result.scalar_one_or_none() is None:
            break
        storyboard_title = f"{script_title} - 分镜 {title_index}"
        title_index += 1
    storyboard_content = {
        "shots_summary": f"共{len(shots_data)}个镜头",
        "story_bible_id": request.story_bible_id,
        "project_id": request.project_id,
        "novel_id": inferred_novel_id,
        "chapter_id": source_chapter_id,
        "novel_continuity": novel_continuity,
        "template_id": template_match["template"]["id"],
        "template_name": template_match["template"]["name"],
        "template_match_score": template_match["score"],
        "template_match_reason": template_match["reason"],
        "shot_count_plan": shot_count_plan,
        "novel_series_seed": novel_continuity.get("novel_series_seed"),
        "chapter_seed": novel_continuity.get("chapter_seed"),
        "continuity_lock": novel_continuity.get("continuity_lock"),
    }
    db_storyboard, created_shots = await persist_storyboard_with_shots(
        db,
        user_id=user_id,
        script_id=request.script_id,
        script_title=script_title,
        storyboard_title=storyboard_title,
        novel_id=inferred_novel_id,
        genre=script.genre,
        style=request.style,
        description=f"{style_hint}，共{len(shots_data)}个镜头",
        content=storyboard_content,
        shots_data=shots_data,
        source_content=script.content,
        continuity_context=novel_continuity,
        dialogue_source="script",
    )

    return StoryboardGenerateResponse(
        id=str(db_storyboard.id),
        script_id=str(request.script_id),
        user_id=str(user_id),
        novel_id=inferred_novel_id,
        chapter_id=source_chapter_id,
        title=storyboard_title,
        script_title=script_title,
        description=f"{style_hint}，共{len(shots_data)}个镜头",
        content=storyboard_content,
        shot_count=len(shots_data),
        total_duration=db_storyboard.total_duration or 0,
        status="draft",
        shots=[ShotBriefResponse(**s) for s in created_shots],
        created_at=str(now),
        updated_at=str(now)
    )


@router.post("/generate-smart", response_model=StoryboardGenerateResponse, status_code=status.HTTP_201_CREATED)
async def generate_smart_storyboard(
    request: StoryboardSmartGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """从小说/章节智能匹配模板并生成可审核的分镜和镜头。"""
    source_script: Optional[Script] = None
    script_chapter_id: Optional[str] = None
    if request.script_id:
        source_script = await get_script_for_user(db, request.script_id, user_id)
        script_extra = source_script.extra_data if isinstance(source_script.extra_data, dict) else {}
        script_chapter_id = source_script.chapter_id or script_extra.get("chapter_id")
        if source_script.novel_id and source_script.novel_id != request.novel_id:
            raise HTTPException(status_code=422, detail="剧本不属于指定小说")
        if request.chapter_id and script_chapter_id and script_chapter_id != request.chapter_id:
            raise HTTPException(status_code=422, detail="剧本不属于指定章节")
        if not source_script.content:
            raise HTTPException(status_code=400, detail="剧本内容为空，无法生成分镜")

    effective_chapter_id = request.chapter_id or script_chapter_id
    novel, chapter, source_title, source_content = await get_generation_source(
        db,
        user_id,
        request.novel_id,
        effective_chapter_id,
        fallback_to_first_chapter=not bool(source_script),
    )
    if source_script:
        source_script_title = normalize_duplicate_chapter_label_text(source_script.title) or source_script.title
        if source_script.novel_id and source_script.novel_id != novel.id:
            raise HTTPException(status_code=422, detail="剧本不属于指定小说")
        if chapter:
            source_title = build_generation_source_title(novel, chapter)
        else:
            source_title = source_script_title or source_title
        source_content = source_script.content

    templates = await load_user_storyboard_templates(db, user_id)
    match = match_storyboard_template(
        title=source_title,
        genre=novel.genre or "",
        content=source_content,
        template_id=request.template_id,
        templates=templates,
    )
    template = match["template"]
    story_prompt_context = await load_story_prompt_context(
        db,
        user_id,
        novel_id=novel.id,
        chapter_id=chapter.id if chapter else None,
        title=source_title,
        genre=novel.genre,
        description=source_content,
        style=request.style,
    )
    novel_continuity = await build_novel_continuity_package(
        db,
        user_id,
        novel_id=novel.id,
        chapter_id=chapter.id if chapter else None,
        story_bible_id=request.story_bible_id,
        project_id=request.project_id,
        task="storyboard_generation",
    )
    shot_count_plan = plan_storyboard_shot_count(
        template=template,
        source_content=source_content,
        requested_shot_count=request.shot_count,
    )
    shots_data = build_template_shots(
        template=template,
        source_title=source_title,
        source_content=source_content,
        shot_count=shot_count_plan["shot_count"],
        story_context=build_shot_dialogue_context(story_prompt_context),
    )
    if source_script:
        script_scene_beats = extract_script_scene_beats(source_content)
        shots_data = apply_script_scene_beats_to_template_shots(
            shots_data,
            script_scene_beats,
            source_title=source_title,
        )

    ai_refined = False
    if request.use_ai_refine:
        try:
            shots_data = await refine_template_shots_with_ai(
                db=db,
                user_id=user_id,
                request=request,
                source_title=source_title,
                source_content=source_content,
                template=template,
                draft_shots=shots_data,
                effective_chapter_id=chapter.id if chapter else None,
            )
            ai_refined = True
        except HTTPException:
            from app.core.dev_generation import is_dev_mode

            if not is_dev_mode():
                raise
        except Exception as exc:
            from app.core.dev_generation import is_dev_mode

            if not is_dev_mode():
                raise HTTPException(status_code=500, detail=f"AI细化分镜失败: {str(exc)}")
    if request.shot_count is not None:
        shots_data = dedupe_repeated_shot_dialogues(shots_data)
    else:
        shots_data = prepare_storyboard_shots_for_production(shots_data)

    if source_script:
        script_id = source_script.id
        script_title = normalize_duplicate_chapter_label_text(source_script.title) or source_script.title
        script_genre = source_script.genre or novel.genre
    else:
        script_id = str(uuid.uuid4())
        script_title = f"{source_title} - 自动改编脚本"
        script_genre = novel.genre
        script = Script(
            id=script_id,
            user_id=user_id,
            novel_id=novel.id,
            chapter_id=chapter.id if chapter else None,
            title=script_title,
            description=f"由小说/章节智能生成，模板：{template['name']}",
            content=source_content,
            genre=script_genre,
            style=request.style,
            status="draft",
            extra_data={
                "source": "smart_storyboard_generation",
                "chapter_id": chapter.id if chapter else None,
                "template_id": template["id"],
                "template_match_reason": match["reason"],
                "generation_context": {
                    "novel_series_seed": novel_continuity.get("novel_series_seed"),
                    "chapter_seed": novel_continuity.get("chapter_seed"),
                    "continuity_lock": novel_continuity.get("continuity_lock"),
                    "previous_chapter_context": novel_continuity.get("previous_chapter_context"),
                    "chapter_state_snapshot": novel_continuity.get("chapter_state_snapshot"),
                },
            },
        )
        db.add(script)

    storyboard_title = request.title or f"{source_title} - 智能分镜"
    content = {
        "source": "smart_storyboard_generation",
        "novel_id": novel.id,
        "chapter_id": chapter.id if chapter else None,
        "template_id": template["id"],
        "template_name": template["name"],
        "template_match_score": match["score"],
        "template_match_reason": match["reason"],
        "ai_refined": ai_refined,
        "shot_count_plan": shot_count_plan,
        "review_status": "pending_review",
        "automation_level": "smart_draft",
        "novel_continuity": novel_continuity,
        "novel_series_seed": novel_continuity.get("novel_series_seed"),
        "chapter_seed": novel_continuity.get("chapter_seed"),
        "continuity_lock": novel_continuity.get("continuity_lock"),
    }
    db_storyboard, created_shots = await persist_storyboard_with_shots(
        db,
        user_id=user_id,
        script_id=script_id,
        script_title=script_title,
        storyboard_title=storyboard_title,
        novel_id=novel.id,
        genre=script_genre,
        style=request.style,
        description=f"智能生成：{template['name']}，{match['reason']}，共{len(shots_data)}个镜头",
        content=content,
        shots_data=shots_data,
        template=template,
        source_content=source_content,
        continuity_context=novel_continuity,
        dialogue_source="script" if source_script else "chapter",
    )

    return StoryboardGenerateResponse(
        id=str(db_storyboard.id),
        script_id=str(script_id),
        user_id=str(user_id),
        novel_id=novel.id,
        chapter_id=chapter.id if chapter else None,
        title=db_storyboard.title,
        script_title=script_title,
        description=db_storyboard.description,
        content=db_storyboard.content,
        shot_count=db_storyboard.shot_count or 0,
        total_duration=db_storyboard.total_duration or 0,
        status=db_storyboard.status or "draft",
        shots=[ShotBriefResponse(**s) for s in created_shots],
        created_at=str(db_storyboard.created_at),
        updated_at=str(db_storyboard.updated_at),
    )


@router.post("/{storyboard_id}/shots/generate-images")
async def generate_storyboard_shot_images(
    storyboard_id: str,
    payload: Any = Body(...),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """批量为指定镜头生成参考图"""
    result = await db.execute(
        select(Storyboard).where(and_(Storyboard.id == storyboard_id, Storyboard.user_id == user_id))
    )
    storyboard = result.scalar_one_or_none()
    if not storyboard:
        raise HTTPException(status_code=404, detail="分镜不存在")

    style = None
    model_config_id = None
    if isinstance(payload, list):
        shot_ids = [str(item) for item in payload if item]
    elif isinstance(payload, dict):
        raw_ids = payload.get("shot_ids") or payload.get("shots") or []
        shot_ids = [str(item) for item in raw_ids if item]
        style = payload.get("style")
        model_config_id = payload.get("model_config_id")
    else:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="请求体必须是镜头ID数组或包含 shot_ids 的对象")

    if not shot_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="至少选择一个镜头")

    storyboard_content = storyboard.content if isinstance(storyboard.content, dict) else {}
    image_style = style or storyboard_content.get("style") or "anime"

    results = []
    for shot_id in shot_ids:
        shot_result = await db.execute(
            select(Shot).where(and_(Shot.id == shot_id, Shot.storyboard_id == storyboard_id))
        )
        shot = shot_result.scalar_one_or_none()
        if not shot:
            results.append({"shot_id": shot_id, "status": "skipped", "reason": "not found or not in this storyboard"})
            continue

        try:
            from app.api.v1.endpoints.shots import ShotImageGenerateRequest, generate_shot_image

            image_result = await generate_shot_image(
                shot_id=shot_id,
                request=ShotImageGenerateRequest(style=image_style, model_config_id=model_config_id),
                db=db,
                user_id=user_id,
            )
            results.append(image_result)
        except HTTPException as exc:
            results.append({"shot_id": shot_id, "status": "error", "reason": exc.detail})
        except Exception as exc:
            results.append({"shot_id": shot_id, "status": "error", "reason": str(exc)})

    return {"storyboard_id": storyboard_id, "results": results}


@router.post("/{storyboard_id}/fill-entity-refs")
async def fill_storyboard_shot_entity_refs(
    storyboard_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """填充分镜下所有镜头的实体引用。

    遍历分镜的所有镜头，为每个镜头重新匹配并填充 character_refs、
    entity_refs、scene_refs、prop_refs、event_refs、environment_context。
    用于分镜生成后批量刷新实体引用，或修复遗漏的实体匹配。
    """
    # 验证分镜所有权
    result = await db.execute(
        select(Storyboard).where(
            and_(Storyboard.id == storyboard_id, Storyboard.user_id == user_id)
        )
    )
    storyboard = result.scalar_one_or_none()
    if not storyboard:
        raise HTTPException(status_code=404, detail="分镜不存在")

    # 获取 chapter_id
    content = storyboard.content if isinstance(storyboard.content, dict) else {}
    chapter_id = content.get("chapter_id")

    # 获取所有镜头
    shots_result = await db.execute(
        select(Shot).where(
            and_(Shot.storyboard_id == storyboard_id, Shot.user_id == user_id)
        )
    )
    shots = list(shots_result.scalars().all())

    updated_count = 0
    for shot in shots:
        await auto_fill_shot_entity_refs(
            db,
            shot,
            storyboard.novel_id,
            chapter_id,
        )
        updated_count += 1

    await db.commit()
    return {
        "status": "success",
        "storyboard_id": storyboard_id,
        "count": updated_count,
        "message": f"已更新 {updated_count} 个镜头的实体引用",
    }
