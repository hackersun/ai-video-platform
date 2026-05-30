"""
分镜管理 API 端点
"""
from app.core.time_utils import utc_now
import asyncio
import uuid
import json
from typing import Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.api_key_utils import create_text_generation_service, get_user_text_model_config, get_user_volcano_api_key
from app.core.security import get_current_user_id
from app.models import Asset, Storyboard, Shot, Novel, Chapter, Script
from app.services.consistency_context import build_consistency_prompt, build_shot_entity_context
from app.services.novel_continuity import build_novel_continuity_package
from app.services.story_prompt_context import (
    build_shot_dialogue_context,
    build_story_context_block,
    load_story_prompt_context,
)
from app.services.storyboard_template_service import (
    build_template_shots,
    list_templates,
    match_storyboard_template,
    merge_template_overrides,
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


async def get_generation_source(
    db: AsyncSession,
    user_id: str,
    novel_id: str,
    chapter_id: Optional[str],
) -> tuple[Novel, Optional[Chapter], str, str]:
    novel = await get_novel_for_user(db, novel_id, user_id)
    chapter: Optional[Chapter] = None
    if chapter_id:
        chapter = await get_chapter_for_user(db, chapter_id, novel_id, user_id)
    else:
        result = await db.execute(
            select(Chapter)
            .where(and_(Chapter.novel_id == novel_id, Chapter.user_id == user_id))
            .order_by(Chapter.chapter_number)
        )
        chapters = result.scalars().all()
        if chapters:
            chapter = chapters[0]

    source_title = f"{novel.title} - {chapter.title}" if chapter else novel.title
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


async def refine_template_shots_with_ai(
    db: AsyncSession,
    user_id: str,
    request: StoryboardSmartGenerateRequest,
    source_title: str,
    source_content: str,
    template: dict,
    draft_shots: list[dict],
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
        chapter_id=request.chapter_id,
        title=source_title,
        genre="",
        description=source_content,
        style=request.style,
    )
    if request.use_consistency_context:
        novel_continuity = await build_novel_continuity_package(
            db,
            user_id,
            novel_id=request.novel_id,
            chapter_id=request.chapter_id,
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

匹配模板：{template["name"]} - {template["description"]}
风格：{request.style}
"""
    if consistency_prompt:
        system_prompt += f"\n全局一致性约束：\n{consistency_prompt}\n"

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
        shot_data["extra_data"] = {
            **shot_data["extra_data"],
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
        title=storyboard.title,
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


@router.post("/generate", response_model=StoryboardGenerateResponse, status_code=status.HTTP_201_CREATED)
async def generate_storyboard(
    request: StoryboardGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """AI生成分镜 - 将剧本内容转换为详细的分镜列表（含镜头信息）"""
    # 获取剧本信息
    script = await get_script_for_user(db, request.script_id, user_id)

    if not script.content:
        raise HTTPException(status_code=400, detail="剧本内容为空，无法生成分镜")

    # 获取用户的API密钥
    api_key, provider_name, model_id, base_url = await get_user_qwen_api_key(
        db,
        user_id,
        request.model_config_id,
    )

    service = create_text_generation_service(api_key, provider_name, base_url)

    # 构建分镜生成提示词
    shot_count_hint = f"生成约{request.shot_count}个镜头" if request.shot_count else "自动确定镜头数量"
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
                "分镜风格": request.style,
                "镜头数量": request.shot_count or "自动",
                "剧本标题": script.title,
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
- 书名：《{script.title or '未知'}》
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
5. **中文输出**：所有描述、台词、音效、氛围必须使用中文"""

    if consistency_prompt:
        system_prompt += f"\n\n【全局一致性约束】\n{consistency_prompt}"
    if novel_continuity:
        system_prompt += f"\n\n{novel_continuity.get('prompt_block')}"

    try:
        response = await service.safe_chat_completion(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"请为以下剧本生成分镜：\n\n【剧本标题】{script.title}\n【剧本内容】\n{script.content}"}
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

    now = utc_now()
    storyboard_title = f"{script.title} - 分镜"
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
        storyboard_title = f"{script.title} - 分镜 {title_index}"
        title_index += 1
    storyboard_content = {
        "shots_summary": f"共{len(shots_data)}个镜头",
        "story_bible_id": request.story_bible_id,
        "project_id": request.project_id,
        "novel_id": inferred_novel_id,
        "chapter_id": source_chapter_id,
        "novel_continuity": novel_continuity,
        "novel_series_seed": novel_continuity.get("novel_series_seed"),
        "chapter_seed": novel_continuity.get("chapter_seed"),
        "continuity_lock": novel_continuity.get("continuity_lock"),
    }
    db_storyboard, created_shots = await persist_storyboard_with_shots(
        db,
        user_id=user_id,
        script_id=request.script_id,
        script_title=script.title,
        storyboard_title=storyboard_title,
        novel_id=inferred_novel_id,
        genre=script.genre,
        style=request.style,
        description=f"{style_hint}，共{len(shots_data)}个镜头",
        content=storyboard_content,
        shots_data=shots_data,
        source_content=script.content,
        continuity_context=novel_continuity,
    )

    return StoryboardGenerateResponse(
        id=str(db_storyboard.id),
        script_id=str(request.script_id),
        user_id=str(user_id),
        novel_id=inferred_novel_id,
        chapter_id=source_chapter_id,
        title=storyboard_title,
        script_title=script.title,
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
    novel, chapter, source_title, source_content = await get_generation_source(
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
    shots_data = build_template_shots(
        template=template,
        source_title=source_title,
        source_content=source_content,
        shot_count=request.shot_count,
        story_context=build_shot_dialogue_context(story_prompt_context),
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

    script_id = str(uuid.uuid4())
    script = Script(
        id=script_id,
        user_id=user_id,
        novel_id=novel.id,
        title=f"{source_title} - 自动改编脚本",
        description=f"由小说/章节智能生成，模板：{template['name']}",
        content=source_content,
        genre=novel.genre,
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
        script_title=script.title,
        storyboard_title=storyboard_title,
        novel_id=novel.id,
        genre=novel.genre,
        style=request.style,
        description=f"智能生成：{template['name']}，{match['reason']}，共{len(shots_data)}个镜头",
        content=content,
        shots_data=shots_data,
        template=template,
        source_content=source_content,
        continuity_context=novel_continuity,
    )

    return StoryboardGenerateResponse(
        id=str(db_storyboard.id),
        script_id=str(script_id),
        user_id=str(user_id),
        novel_id=novel.id,
        chapter_id=chapter.id if chapter else None,
        title=db_storyboard.title,
        script_title=script.title,
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
    shot_ids: List[str] = Body(...),
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

    results = []
    for shot_id in shot_ids:
        shot_result = await db.execute(
            select(Shot).where(and_(Shot.id == shot_id, Shot.storyboard_id == storyboard_id))
        )
        shot = shot_result.scalar_one_or_none()
        if not shot:
            results.append({"shot_id": shot_id, "status": "skipped", "reason": "not found or not in this storyboard"})
            continue

        prompt_parts = []
        if shot.visual_description:
            prompt_parts.append(shot.visual_description)
        if shot.prompt:
            prompt_parts.append(shot.prompt)
        if shot.lighting:
            prompt_parts.append(f"lighting: {shot.lighting}")
        prompt = " ".join(prompt_parts) if prompt_parts else shot.visual_description or shot.prompt or "cinematic scene"

        try:
            api_key = await get_user_volcano_api_key(db, user_id)
            from app.services.volcano_service import VolcanoService
            volcano = VolcanoService(api_key)
            result_img = await volcano.generate_image(prompt=prompt)
            task_id = result_img.get("task_id")

            shot.image_status = "generating"
            await db.commit()

            from app.services.image_poll_service import poll_and_update_shot_image
            asyncio.create_task(poll_and_update_shot_image(shot_id, task_id, user_id))

            results.append({"shot_id": shot_id, "task_id": task_id, "status": "generating"})
        except Exception as e:
            results.append({"shot_id": shot_id, "status": "error", "reason": str(e)})

    return {"storyboard_id": storyboard_id, "results": results}
