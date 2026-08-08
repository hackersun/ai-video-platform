"""
章节管理 API 端点
"""
from app.core.time_utils import utc_now
import uuid
import re
from typing import Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.api_key_utils import (
    extract_chat_content,
    get_user_text_generation_service,
)
from app.core.dev_generation import is_dev_mode
from app.core.security import get_current_user_id
from app.models import Novel, Chapter, StoryBible, StoryEntity, Script, Storyboard, Shot
from app.services.consistency_context import build_consistency_prompt
from app.services.entity_extraction_service import (
    build_story_bible_sections,
    extract_story_entities,
)
from app.services.story_entity_lifecycle import set_entity_review_status
from app.services.ai_generation_feedback import build_ai_generation_feedback
from app.services.story_prompt_context import (
    build_chapter_continuity_block,
    load_story_prompt_context,
)
from app.services.chapter_naming import format_chapter_label
from app.services.chapter_story_context import persist_chapter_story_context

router = APIRouter(tags=["章节管理"])


# ============== Pydantic 模型 ==============

class ChapterCreate(BaseModel):
    """创建章节请求"""
    novel_id: str = Field(..., description="所属小说ID")
    title: str = Field(..., min_length=1, max_length=200, description="章节标题")
    content: Optional[str] = Field(None, description="章节内容")
    chapter_number: Optional[int] = Field(1, description="章节序号")


class ChapterUpdate(BaseModel):
    """更新章节请求"""
    title: Optional[str] = None
    content: Optional[str] = None
    chapter_number: Optional[int] = None
    status: Optional[str] = None


class ChapterResponse(BaseModel):
    """章节响应"""
    id: str
    novel_id: str
    user_id: str
    title: str
    novel_title: Optional[str] = None
    content: Optional[str] = None
    chapter_number: int
    word_count: int
    status: str
    ai_generation: Optional[dict[str, Any]] = None
    created_at: str
    updated_at: str


class ChapterGenerateRequest(BaseModel):
    """AI生成章节请求"""
    novel_id: str = Field(..., description="所属小说ID")
    chapter_title: Optional[str] = Field(None, min_length=1, max_length=200, description="章节标题（不提供则自动生成）")
    prev_chapter_content: Optional[str] = Field(None, description="上一章内容（用于上下文）")
    target_word_count: int = Field(1800, ge=300, le=8000, description="目标字数")
    instruction: Optional[str] = Field(None, description="额外创作指令")
    model_config_id: Optional[str] = Field(None, description="已保存的文本模型配置ID")


class ChapterAIAssistRequest(BaseModel):
    """章节编辑页 AI 辅助请求"""
    mode: str = Field("rewrite", description="rewrite/extend/polish")
    instruction: Optional[str] = Field(None, description="额外修改指令")
    target_word_count: int = Field(1800, ge=300, le=8000, description="目标字数")
    sync_story_bible: bool = Field(True, description="生成后是否同步实体和 Story Bible")
    model_config_id: Optional[str] = Field(None, description="已保存的文本模型配置ID")


async def get_novel_for_user(db: AsyncSession, novel_id: str, user_id: str):
    from app.models import Novel

    result = await db.execute(
        select(Novel).where(and_(Novel.id == novel_id, Novel.user_id == user_id))
    )
    novel = result.scalar_one_or_none()
    if novel is None:
        raise HTTPException(status_code=404, detail="小说不存在")
    return novel


def build_chapter_response(
    chapter: Chapter,
    novel_title: Optional[str] = None,
    ai_generation: Optional[dict[str, Any]] = None,
) -> ChapterResponse:
    return ChapterResponse(
        id=str(chapter.id),
        novel_id=str(chapter.novel_id),
        user_id=str(chapter.user_id),
        title=chapter.title,
        novel_title=novel_title,
        content=chapter.content,
        chapter_number=chapter.chapter_number or 1,
        word_count=chapter.word_count or 0,
        status=chapter.status or "draft",
        ai_generation=ai_generation,
        created_at=str(chapter.created_at),
        updated_at=str(chapter.updated_at),
    )


def clean_generated_content(content: str) -> str:
    """Remove common model wrappers and reasoning residue from chapter text."""
    lines = (content or "").split("\n")
    clean_lines: list[str] = []
    skip_mode = False
    for line in lines:
        stripped = line.strip()
        lowered = stripped.lower()
        if (
            "<think>" in lowered
            or "</think>" in lowered
            or "thinking process" in lowered
            or "思考过程" in stripped
            or (lowered.startswith("[") and "]" in lowered and len(lowered) < 50)
        ):
            skip_mode = True
            continue
        if skip_mode:
            if len(stripped) > 20 and not stripped.startswith(("**", "#")):
                skip_mode = False
            else:
                continue
        if stripped.startswith("```"):
            continue
        clean_lines.append(line)
    return "\n".join(clean_lines).strip()


def suggest_generated_chapter_title(
    *,
    content: str,
    chapter_number: int,
    instruction: Optional[str] = None,
    fallback: Optional[str] = None,
) -> str:
    """Create a readable Chinese chapter title when the user did not provide one."""
    explicit = re.search(r"(?:章节标题|标题|题目)\s*[：:]\s*《?([^》\n。！？!?；;]{2,24})", instruction or "")
    if explicit:
        title = explicit.group(1).strip(" 《》“”\"'")
        if title:
            return f"第{chapter_number}章 {title[:18]}"

    skip_prefixes = (
        "这是《",
        "小说类型",
        "上一段剧情",
        "当前核心内容",
        "本章中段",
        "本章结尾",
        "目标字数",
        "额外要求",
        "请作为",
        "用户提供",
    )
    for raw_line in (content or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith(skip_prefixes):
            continue
        if any(marker in line for marker in ("AI", "草稿", "任务", "要求", "小说信息", "Story Bible")):
            continue
        candidate = re.sub(r"^第[一二三四五六七八九十百千万\d]+\s*[章节卷集回]?[：:、.\s-]*", "", line)
        candidate = re.split(r"[。！？!?；;，,]", candidate)[0]
        candidate = candidate.strip(" #【】[]《》“”\"'")
        if 2 <= len(candidate) <= 28:
            return f"第{chapter_number}章 {candidate[:18]}"

    return fallback or f"第{chapter_number}章 新的转折"


_CHAPTER_NUMERAL_PATTERN = r"[一二三四五六七八九十百千万两\d]+"


def is_generic_chapter_title(title: Optional[str]) -> bool:
    """Return true when a title is only a chapter number or placeholder."""
    value = (title or "").strip()
    if not value:
        return True
    normalized = re.sub(r"\s+", "", value)
    if normalized in {"新章节", "未命名章节", "待命名章节", "章节", "草稿章节"}:
        return True
    return bool(re.fullmatch(rf"第{_CHAPTER_NUMERAL_PATTERN}[章节卷集回]?", normalized))


def apply_generated_chapter_title(
    chapter: Chapter,
    *,
    content: str,
    instruction: Optional[str] = None,
    force: bool = False,
) -> dict[str, Any]:
    """Suggest a content-aware chapter title and update generic titles only."""
    suggested_title = suggest_generated_chapter_title(
        content=content,
        chapter_number=chapter.chapter_number or 1,
        instruction=instruction,
        fallback=chapter.title or f"第{chapter.chapter_number or 1}章",
    )
    should_update = force or is_generic_chapter_title(chapter.title)
    if should_update and suggested_title and suggested_title != chapter.title:
        chapter.title = suggested_title
        return {"title_suggested": suggested_title, "title_updated": True}
    return {"title_suggested": suggested_title, "title_updated": False}


def compact_text(value: Optional[str], limit: int = 800) -> str:
    text_value = " ".join((value or "").split())
    if len(text_value) <= limit:
        return text_value
    return f"{text_value[:limit]}..."


async def list_chapters_for_novel(db: AsyncSession, novel_id: str, user_id: str) -> list[Chapter]:
    result = await db.execute(
        select(Chapter)
        .where(and_(Chapter.novel_id == novel_id, Chapter.user_id == user_id))
        .order_by(Chapter.chapter_number)
    )
    return list(result.scalars().all())


def chapter_neighbors(chapters: list[Chapter], chapter: Optional[Chapter]) -> tuple[Optional[Chapter], Optional[Chapter]]:
    if not chapter:
        return (chapters[-1] if chapters else None), None
    for index, item in enumerate(chapters):
        if item.id == chapter.id:
            prev_chapter = chapters[index - 1] if index > 0 else None
            next_chapter = chapters[index + 1] if index < len(chapters) - 1 else None
            return prev_chapter, next_chapter
    return None, None


def build_chapter_outline(chapters: list[Chapter], current_chapter_id: Optional[str] = None) -> str:
    if not chapters:
        return "暂无已保存章节。"
    lines = []
    for chapter in chapters:
        marker = "（当前章节）" if chapter.id == current_chapter_id else ""
        preview = compact_text(chapter.content, 420) if chapter.content else "暂无正文"
        lines.append(f"{format_chapter_label(chapter.title, chapter.chapter_number)}{marker}：{preview}")
    return "\n".join(lines)


def build_story_bible_context(story_bibles: list[StoryBible]) -> str:
    if not story_bibles:
        return "暂无 Story Bible，请优先遵循小说简介和已保存章节。"

    def item_names(items: Any, key: str = "name") -> str:
        if not isinstance(items, list):
            return ""
        names = [str(item.get(key) or item.get("title") or "") for item in items if isinstance(item, dict)]
        return "、".join([name for name in names if name][:20])

    lines = []
    for story_bible in story_bibles[:3]:
        lines.append(f"Story Bible：《{story_bible.title}》")
        if story_bible.worldview:
            lines.append(f"- 世界观：{compact_text(story_bible.worldview, 500)}")
        if story_bible.style:
            lines.append(f"- 风格：{compact_text(story_bible.style, 300)}")
        character_names = item_names(story_bible.character_rules)
        scene_names = item_names(story_bible.scene_rules)
        prop_names = item_names(story_bible.prop_rules)
        event_names = item_names(story_bible.event_timeline, "title")
        if character_names:
            lines.append(f"- 已有人物：{character_names}")
        if scene_names:
            lines.append(f"- 已有场景：{scene_names}")
        if prop_names:
            lines.append(f"- 已有道具：{prop_names}")
        if event_names:
            lines.append(f"- 事件线：{event_names}")
    return "\n".join(lines)


async def get_story_bibles_for_novel(db: AsyncSession, novel_id: str, user_id: str) -> list[StoryBible]:
    result = await db.execute(
        select(StoryBible)
        .where(and_(StoryBible.novel_id == novel_id, StoryBible.user_id == user_id))
        .order_by(desc(StoryBible.updated_at))
    )
    return list(result.scalars().all())


def build_dev_chapter_content(
    *,
    novel: Novel,
    chapter_title: str,
    mode: str,
    target_word_count: int,
    current_content: Optional[str],
    prev_chapter: Optional[Chapter],
    next_chapter: Optional[Chapter],
    instruction: Optional[str],
    continuity_block: Optional[str] = None,
) -> str:
    """Deterministic DEV_MODE fallback for tests and local full-flow checks."""
    prev_hint = compact_text(getattr(prev_chapter, "content", None), 180) or "故事开端"
    next_hint = compact_text(getattr(next_chapter, "content", None), 160) or "后续剧情尚未确定"
    current_hint = compact_text(current_content, 220) or "当前章节等待创作"
    instruction_hint = f"本次额外要求：{instruction}\n" if instruction else ""
    action = {"rewrite": "重写", "extend": "续写", "polish": "润色"}.get(mode, "创作")
    paragraphs = [
        f"{instruction_hint}这是《{novel.title}》的章节《{chapter_title}》AI{action}草稿。",
        f"小说类型是{novel.genre or '通用'}，整体设定为：{compact_text(novel.description, 260) or '主线设定待完善'}。",
        compact_text(continuity_block, 900) if continuity_block else "",
        f"上一段剧情延续自：{prev_hint}。本章开场会承接已有情绪和事件结果，避免人物动机突然改变。",
        f"当前核心内容依据：{current_hint}。人物会围绕既有目标继续行动，场景、道具和冲突保持前后连续。",
        f"本章中段推进关键事件：角色先确认上一章留下的线索，再在主要场景中遭遇新的阻力，关键道具、对白信息和事件结果会被再次提及。",
        f"本章结尾需要衔接：{next_hint}。结尾保留清晰悬念，让下一章可以继续推进同一条事件线。",
        f"目标字数约{target_word_count}字；当前为开发模式可验证草稿，真实环境会使用默认文本模型生成更完整正文。",
    ]
    if mode == "extend" and current_content:
        return f"{current_content.rstrip()}\n\n" + "\n\n".join(part for part in paragraphs[2:] if part)
    return "\n\n".join(part for part in paragraphs if part)


async def generate_chapter_text(
    *,
    db: AsyncSession,
    user_id: str,
    novel: Novel,
    chapter_title: str,
    chapters: list[Chapter],
    current_chapter: Optional[Chapter] = None,
    mode: str = "rewrite",
    current_content: Optional[str] = None,
    instruction: Optional[str] = None,
    target_word_count: int = 1800,
    model_config_id: Optional[str] = None,
) -> tuple[str, dict[str, Any]]:
    if mode not in {"rewrite", "extend", "polish"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="mode 仅支持 rewrite/extend/polish")

    prev_chapter, next_chapter = chapter_neighbors(chapters, current_chapter)
    story_bibles = await get_story_bibles_for_novel(db, novel.id, user_id)
    story_prompt_context = await load_story_prompt_context(
        db,
        user_id,
        novel_id=novel.id,
        chapter_id=current_chapter.id if current_chapter else None,
        title=novel.title,
        genre=novel.genre,
        description=novel.description,
    )
    continuity_block = build_chapter_continuity_block(story_prompt_context)
    consistency_context = await build_consistency_prompt(
        db,
        user_id,
        task="chapter_writing",
        base_prompt=current_content or novel.description or novel.title,
        novel_id=novel.id,
        extra_context={
            "小说标题": novel.title,
            "小说类型": novel.genre,
            "章节标题": chapter_title,
            "生成模式": mode,
            "目标字数": target_word_count,
            "额外要求": instruction,
            "上一章": f"{prev_chapter.title}: {compact_text(prev_chapter.content, 700)}" if prev_chapter else None,
            "下一章": f"{next_chapter.title}: {compact_text(next_chapter.content, 500)}" if next_chapter else None,
            "小说连续性上下文": continuity_block,
        },
    )
    metadata = {
        "mode": mode,
        "target_word_count": target_word_count,
        "story_bible_id": consistency_context["metadata"].get("story_bible_id"),
        "default_model_id": consistency_context["metadata"].get("default_model_id"),
        "prev_chapter_id": prev_chapter.id if prev_chapter else None,
        "next_chapter_id": next_chapter.id if next_chapter else None,
        "story_prompt_context": story_prompt_context,
    }

    try:
        service, provider_name, model_id, base_url = await get_user_text_generation_service(
            db, user_id, config_id=model_config_id,
        )
    except HTTPException as exc:
        detail = str(exc.detail)
        if (
            not is_dev_mode()
            or model_config_id
            or "无法解密" in detail
            or "为空" in detail
            or "缺少 API Key" in detail
        ):
            raise
        content = build_dev_chapter_content(
            novel=novel,
            chapter_title=chapter_title,
            mode=mode,
            target_word_count=target_word_count,
            current_content=current_content,
            prev_chapter=prev_chapter,
            next_chapter=next_chapter,
            instruction=instruction,
            continuity_block=continuity_block,
        )
        metadata["provider"] = "dev_mode"
        metadata["ai_refined"] = False
        return content, metadata

    mode_instruction = {
        "rewrite": "重写当前章节，允许重构段落和情节细节，但必须保留本章在全书中的功能。",
        "extend": "在当前正文基础上续写，不能改写已有正文，续写内容必须自然承接最后一段。",
        "polish": "润色当前正文，提升画面感、节奏和人物表达，不能改变关键事件结果。",
    }[mode]
    system_prompt = f"""你是专业中文小说主笔，负责把小说章节写到可直接进入后续分镜和视频生成的质量。

【写作任务】
- 模式：{mode_instruction}
- 章节：《{chapter_title}》
- 目标字数：约 {target_word_count} 字
- 输出必须是中文小说正文，不要输出标题、说明、列表、Markdown 或推理过程。

【连续性硬约束】
1. 必须承接小说简介、上一章结果、当前章节位置和 Story Bible 中的人物、场景、道具、事件。
2. 不能凭空更改人物姓名、身份、关系、道具状态、场景位置和事件结果。
3. 如果有下一章内容，需要让本章结尾能自然衔接下一章，不要写出与下一章矛盾的结局。
4. 正文要保留可影视化信息：人物动作、表情、场景空间、关键道具、事件因果和对话。
5. 如果是续写，只输出新增续写段落；如果是润色或重写，输出完整章节正文。
"""
    user_prompt = f"""【小说信息】
书名：《{novel.title}》
类型：{novel.genre or '未知'}
简介：{novel.description or '暂无'}

【Story Bible/实体上下文】
{build_story_bible_context(story_bibles)}

{continuity_block}

【全书章节顺序与摘要】
{build_chapter_outline(chapters, current_chapter.id if current_chapter else None)}

【上一章结尾】
{compact_text(prev_chapter.content, 1200) if prev_chapter and prev_chapter.content else '无'}

【当前章节原文】
{current_content or '当前章节为空，请创作完整正文。'}

【下一章开头】
{compact_text(next_chapter.content, 1000) if next_chapter and next_chapter.content else '无'}

【一致性组合提示】
{consistency_context["prompt"]}

【额外要求】
{instruction or '无'}
"""
    try:
        request_options = {"request_timeout": 300} if provider_name.startswith("volcano") else {}
        response = await service.safe_chat_completion(
            model=model_id or "",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.78 if mode != "polish" else 0.45,
            max_tokens=min(max(target_word_count * 3, 2400), 12000),
            **request_options,
        )
        content = clean_generated_content(extract_chat_content(response))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"AI生成章节失败: {str(exc)}")

    if not content:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="AI未返回有效章节内容")
    metadata.update({"provider": provider_name, "model_id": model_id, "ai_refined": True})
    return content, metadata


async def persist_story_context_from_chapter(
    db: AsyncSession,
    user_id: str,
    novel: Novel,
    chapter: Chapter,
    *,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    return await persist_chapter_story_context(
        db, user_id, novel, chapter, extractor=extract_story_entities, metadata=metadata,
    )


async def refresh_novel_word_count(db: AsyncSession, novel: Novel, user_id: str) -> None:
    chapters = await list_chapters_for_novel(db, novel.id, user_id)
    novel.word_count = sum(chapter.word_count or len(chapter.content or "") for chapter in chapters)
    novel.updated_at = utc_now()


# ============== API 端点 ==============

@router.get("/novel/{novel_id}", response_model=List[ChapterResponse])
async def list_chapters_by_novel(
    novel_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取指定小说的所有章节"""
    novel = await get_novel_for_user(db, novel_id, user_id)

    result = await db.execute(
        select(Chapter)
        .where(and_(Chapter.novel_id == novel_id, Chapter.user_id == user_id))
        .order_by(Chapter.chapter_number)
    )
    chapters = result.scalars().all()

    return [build_chapter_response(c, novel.title) for c in chapters]


@router.get("/{chapter_id}", response_model=ChapterResponse)
async def get_chapter(
    chapter_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取单个章节"""
    result = await db.execute(
        select(Chapter).where(and_(Chapter.id == chapter_id, Chapter.user_id == user_id))
    )
    chapter = result.scalar_one_or_none()

    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    novel = await get_novel_for_user(db, chapter.novel_id, user_id)
    return build_chapter_response(chapter, novel.title)


@router.post("", response_model=ChapterResponse, status_code=status.HTTP_201_CREATED)
async def create_chapter(
    chapter: ChapterCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """创建章节"""
    novel = await get_novel_for_user(db, chapter.novel_id, user_id)

    chapter_id = str(uuid.uuid4())
    word_count = len(chapter.content or "")

    db_chapter = Chapter(
        id=chapter_id,
        novel_id=chapter.novel_id,
        user_id=user_id,
        title=chapter.title,
        content=chapter.content,
        chapter_number=chapter.chapter_number or 1,
        word_count=word_count,
        status="draft"
    )

    db.add(db_chapter)
    await db.flush()
    metadata: dict[str, Any] = {"source": "manual_chapter_create"}
    if db_chapter.content:
        await persist_story_context_from_chapter(db, user_id, novel, db_chapter, metadata=metadata)
    await refresh_novel_word_count(db, novel, user_id)
    await db.commit()
    await db.refresh(db_chapter)

    return build_chapter_response(db_chapter, novel.title)


@router.put("/{chapter_id}", response_model=ChapterResponse)
async def update_chapter(
    chapter_id: str,
    chapter_update: ChapterUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """更新章节"""
    result = await db.execute(
        select(Chapter).where(and_(Chapter.id == chapter_id, Chapter.user_id == user_id))
    )
    db_chapter = result.scalar_one_or_none()

    if not db_chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    update_data = chapter_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "content":
            setattr(db_chapter, "word_count", len(value or ""))
        setattr(db_chapter, key, value)

    await db.commit()
    await db.refresh(db_chapter)

    novel = await get_novel_for_user(db, db_chapter.novel_id, user_id)
    return build_chapter_response(db_chapter, novel.title)


@router.delete("/{chapter_id}")
async def delete_chapter(
    chapter_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """删除章节"""
    result = await db.execute(
        select(Chapter).where(and_(Chapter.id == chapter_id, Chapter.user_id == user_id))
    )
    db_chapter = result.scalar_one_or_none()

    if not db_chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    await db.delete(db_chapter)
    await db.commit()

    return {"message": "章节已删除"}


@router.post("/generate", response_model=ChapterResponse, status_code=status.HTTP_201_CREATED)
async def generate_chapter(
    request: ChapterGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """AI生成章节 - 根据小说上下文生成新章节内容"""
    novel = await get_novel_for_user(db, request.novel_id, user_id)
    existing_chapters = await list_chapters_for_novel(db, request.novel_id, user_id)
    next_chapter_number = (existing_chapters[-1].chapter_number + 1) if existing_chapters else 1
    provided_chapter_title = request.chapter_title.strip() if request.chapter_title else None
    chapter_title = provided_chapter_title or f"第{next_chapter_number}章"
    if request.prev_chapter_content:
        virtual_prev = Chapter(
            id=f"provided-prev-{uuid.uuid4()}",
            novel_id=request.novel_id,
            user_id=user_id,
            title="用户提供的上一章",
            content=request.prev_chapter_content,
            chapter_number=next_chapter_number - 1,
            word_count=len(request.prev_chapter_content),
            status="completed",
        )
        existing_chapters = existing_chapters + [virtual_prev]

    chapter_content, metadata = await generate_chapter_text(
        db=db,
        user_id=user_id,
        novel=novel,
        chapter_title=chapter_title,
        chapters=existing_chapters,
        mode="rewrite",
        instruction=request.instruction,
        target_word_count=request.target_word_count,
        model_config_id=request.model_config_id,
    )
    final_chapter_title = provided_chapter_title or suggest_generated_chapter_title(
        content=chapter_content,
        chapter_number=next_chapter_number,
        instruction=request.instruction,
    )
    metadata["title_suggested"] = final_chapter_title
    metadata["title_updated"] = not bool(provided_chapter_title)
    metadata["chapter_title"] = final_chapter_title

    now = utc_now()
    db_chapter = Chapter(
        id=str(uuid.uuid4()),
        novel_id=request.novel_id,
        user_id=user_id,
        title=final_chapter_title,
        content=chapter_content,
        chapter_number=next_chapter_number,
        word_count=len(chapter_content),
        status="completed",
        created_at=now,
        updated_at=now,
    )
    db.add(db_chapter)
    await db.flush()
    await persist_story_context_from_chapter(db, user_id, novel, db_chapter, metadata=metadata)
    await refresh_novel_word_count(db, novel, user_id)
    await db.commit()
    await db.refresh(db_chapter)

    ai_generation = build_ai_generation_feedback(
        stage="completed",
        message="章节已生成、保存，并已同步实体/Story Bible 上下文",
        context=metadata.get("story_prompt_context"),
        provider=metadata.get("provider"),
        model=metadata.get("model_id") or metadata.get("default_model_id"),
        extra={
            "mode": metadata.get("mode"),
            "entity_count": metadata.get("entity_count"),
            "story_bible_count": metadata.get("story_bible_count"),
            "title_suggested": metadata.get("title_suggested"),
            "title_updated": metadata.get("title_updated"),
        },
    )
    return build_chapter_response(db_chapter, novel.title, ai_generation=ai_generation)


@router.post("/{chapter_id}/ai-assist", response_model=ChapterResponse)
async def ai_assist_chapter(
    chapter_id: str,
    request: ChapterAIAssistRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """AI 辅助编辑章节，生成结果会立即持久化到数据库。"""
    result = await db.execute(
        select(Chapter).where(and_(Chapter.id == chapter_id, Chapter.user_id == user_id))
    )
    chapter = result.scalar_one_or_none()
    if chapter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="章节不存在")

    novel = await get_novel_for_user(db, chapter.novel_id, user_id)
    chapters = await list_chapters_for_novel(db, chapter.novel_id, user_id)
    generated_content, metadata = await generate_chapter_text(
        db=db,
        user_id=user_id,
        novel=novel,
        chapter_title=chapter.title,
        chapters=chapters,
        current_chapter=chapter,
        mode=request.mode,
        current_content=chapter.content,
        instruction=request.instruction,
        target_word_count=request.target_word_count,
        model_config_id=request.model_config_id,
    )

    if request.mode == "extend":
        new_content = generated_content if generated_content.startswith((chapter.content or "").rstrip()) else (
            f"{(chapter.content or '').rstrip()}\n\n{generated_content.strip()}"
        ).strip()
    else:
        new_content = generated_content

    chapter.content = new_content
    metadata.update(apply_generated_chapter_title(chapter, content=new_content, instruction=request.instruction))
    chapter.word_count = len(new_content)
    chapter.status = "completed"
    chapter.updated_at = utc_now()
    sync_result = {}
    if request.sync_story_bible:
        sync_result = await persist_story_context_from_chapter(db, user_id, novel, chapter, metadata=metadata)
    await refresh_novel_word_count(db, novel, user_id)
    await db.commit()
    await db.refresh(chapter)
    ai_generation = build_ai_generation_feedback(
        stage="completed",
        message="章节 AI 处理完成，内容已保存并刷新连续性上下文",
        context=metadata.get("story_prompt_context"),
        provider=metadata.get("provider"),
        model=metadata.get("model_id") or metadata.get("default_model_id"),
        extra={
            "mode": metadata.get("mode"),
            "entity_count": sync_result.get("entity_count"),
            "story_bible_count": sync_result.get("story_bible_count"),
            "title_suggested": metadata.get("title_suggested"),
            "title_updated": metadata.get("title_updated"),
        },
    )
    return build_chapter_response(chapter, novel.title, ai_generation=ai_generation)

class ChapterRegenerateRequest(BaseModel):
    """章节内容重生成请求"""
    chapter_id: str = Field(..., description="章节ID")
    prompt: Optional[str] = Field(None, description="额外补充指令（可选）")


class ProductionChainRequest(BaseModel):
    """一键生产链路请求"""
    style: str = Field(default="anime", description="分镜风格")
    genre: Optional[str] = Field(None, description="剧本类型")
    model_config_id: Optional[str] = Field(None, description="已保存的文本模型配置ID")
    shot_count: Optional[int] = Field(None, ge=1, le=50, description="镜头数量")


class ProductionStatusResponse(BaseModel):
    """生产状态响应"""
    chapter_id: str
    script_id: Optional[str] = None
    storyboard_id: Optional[str] = None
    shot_count: int = 0
    has_script: bool = False
    has_storyboard: bool = False
    script_status: Optional[str] = None
    storyboard_status: Optional[str] = None
    storyboard_shot_count: int = 0


async def get_latest_chapter_script(
    db: AsyncSession,
    user_id: str,
    chapter_id: str,
) -> Optional[Script]:
    """Return the latest script version for a chapter without assuming uniqueness."""
    result = await db.execute(
        select(Script)
        .where(
            and_(
                Script.chapter_id == chapter_id,
                Script.user_id == user_id,
            )
        )
        .order_by(desc(Script.updated_at), desc(Script.created_at))
        .limit(1)
    )
    return result.scalars().first()


async def get_latest_script_storyboard(
    db: AsyncSession,
    user_id: str,
    script_id: str,
) -> Optional[Storyboard]:
    """Return the latest storyboard for a script without assuming uniqueness."""
    result = await db.execute(
        select(Storyboard)
        .where(
            and_(
                Storyboard.script_id == script_id,
                Storyboard.user_id == user_id,
            )
        )
        .order_by(desc(Storyboard.updated_at), desc(Storyboard.created_at))
        .limit(1)
    )
    return result.scalars().first()


@router.get("/{chapter_id}/production-status", response_model=ProductionStatusResponse)
async def get_chapter_production_status(
    chapter_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取章节的生产状态（剧本、分镜、镜头状态）"""
    result = await db.execute(
        select(Chapter).where(and_(Chapter.id == chapter_id, Chapter.user_id == user_id))
    )
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    script = await get_latest_chapter_script(db, user_id, chapter_id)

    # 查询分镜
    storyboard = None
    shot_count = 0
    if script:
        storyboard = await get_latest_script_storyboard(db, user_id, script.id)
        if storyboard:
            shot_result = await db.execute(
                select(Shot).where(
                    and_(
                        Shot.storyboard_id == storyboard.id,
                        Shot.user_id == user_id
                    )
                )
            )
            shots = shot_result.scalars().all()
            shot_count = len(list(shots))

    return ProductionStatusResponse(
        chapter_id=chapter_id,
        script_id=script.id if script else None,
        storyboard_id=storyboard.id if storyboard else None,
        shot_count=shot_count,
        has_script=script is not None,
        has_storyboard=storyboard is not None,
        script_status=script.status if script else None,
        storyboard_status=storyboard.status if storyboard else None,
        storyboard_shot_count=shot_count,
    )


@router.post("/{chapter_id}/generate-script", response_model=dict)
async def generate_chapter_script(
    chapter_id: str,
    request: ProductionChainRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """从章节生成剧本 - 仅生成剧本不生成分镜"""
    from app.api.v1.endpoints.scripts import ScriptGenerateRequest as ScriptRequest

    result = await db.execute(
        select(Chapter).where(and_(Chapter.id == chapter_id, Chapter.user_id == user_id))
    )
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    if not chapter.content:
        raise HTTPException(status_code=400, detail="章节内容为空，无法生成剧本")

    # 调用剧本生成接口
    script_request = ScriptRequest(
        chapter_id=chapter_id,
        style=request.style,
        genre=request.genre,
        model_config_id=request.model_config_id,
    )

    # 直接复用 scripts.py 的 generate_script 函数逻辑
    from app.api.v1.endpoints.scripts import generate_script as generate_script_func

    # 由于 generate_script 是异步函数，我们需要包装请求
    class FakeRequest:
        def __init__(self, chapter_id, style, genre, model_config_id):
            self.chapter_id = chapter_id
            self.style = style
            self.genre = genre
            self.model_config_id = model_config_id

    fake_request = FakeRequest(
        chapter_id=chapter_id,
        style=request.style,
        genre=request.genre,
        model_config_id=request.model_config_id,
    )

    # 直接调用内部函数
    script_response = await generate_script_func(
        request=fake_request,
        db=db,
        user_id=user_id
    )

    return {
        "message": "剧本生成完成",
        "script_id": script_response.id,
        "script_title": script_response.title,
        "script_status": script_response.status,
    }


@router.post("/{chapter_id}/generate-storyboard", response_model=dict)
async def generate_chapter_storyboard(
    chapter_id: str,
    request: ProductionChainRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """从章节生成剧本和分镜"""
    # 先检查章节是否存在
    result = await db.execute(
        select(Chapter).where(and_(Chapter.id == chapter_id, Chapter.user_id == user_id))
    )
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    if not chapter.content:
        raise HTTPException(status_code=400, detail="章节内容为空，无法生成")

    script = await get_latest_chapter_script(db, user_id, chapter_id)

    script_id = script.id if script else None

    # 生成智能分镜
    from app.api.v1.endpoints.storyboards import (
        StoryboardSmartGenerateRequest,
        generate_smart_storyboard as generate_smart_storyboard_func,
    )

    class FakeStoryboardRequest:
        def __init__(self, novel_id, chapter_id, shot_count, style, model_config_id):
            self.novel_id = novel_id
            self.chapter_id = chapter_id
            self.script_id = script_id
            self.shot_count = shot_count
            self.style = style
            self.story_bible_id = None
            self.project_id = None
            self.use_ai_refine = True
            self.use_consistency_context = True
            self.template_id = None
            self.title = None
            self.model_config_id = model_config_id

    fake_storyboard_request = FakeStoryboardRequest(
        novel_id=chapter.novel_id,
        chapter_id=chapter_id,
        shot_count=request.shot_count,
        style=request.style,
        model_config_id=request.model_config_id,
    )

    storyboard_response = await generate_smart_storyboard_func(
        request=fake_storyboard_request,
        db=db,
        user_id=user_id,
    )

    return {
        "message": "剧本和分镜生成完成",
        "script_id": storyboard_response.script_id,
        "storyboard_id": storyboard_response.id,
        "script_title": storyboard_response.script_title,
        "storyboard_title": storyboard_response.title,
        "shot_count": storyboard_response.shot_count,
        "storyboard_status": storyboard_response.status,
    }


@router.post("/{chapter_id}/generate-all", response_model=dict)
async def generate_chapter_all(
    chapter_id: str,
    request: ProductionChainRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """从章节一键生成全部（剧本+分镜+镜头）"""
    # 先检查章节是否存在
    result = await db.execute(
        select(Chapter).where(and_(Chapter.id == chapter_id, Chapter.user_id == user_id))
    )
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    if not chapter.content:
        raise HTTPException(status_code=400, detail="章节内容为空，无法生成")

    script = await get_latest_chapter_script(db, user_id, chapter_id)
    script_id = script.id if script else None

    # 智能分镜会在缺少剧本时基于章节创建可审核草稿脚本。
    from app.api.v1.endpoints.storyboards import (
        StoryboardSmartGenerateRequest,
        generate_smart_storyboard as generate_smart_storyboard_func,
    )

    class FakeStoryboardRequest:
        def __init__(self, novel_id, chapter_id, shot_count, style, model_config_id):
            self.novel_id = novel_id
            self.chapter_id = chapter_id
            self.script_id = script_id
            self.shot_count = shot_count
            self.style = style
            self.story_bible_id = None
            self.project_id = None
            self.use_ai_refine = True
            self.use_consistency_context = True
            self.template_id = None
            self.title = None
            self.model_config_id = model_config_id

    fake_storyboard_request = FakeStoryboardRequest(
        novel_id=chapter.novel_id,
        chapter_id=chapter_id,
        shot_count=request.shot_count,
        style=request.style,
        model_config_id=request.model_config_id,
    )

    storyboard_response = await generate_smart_storyboard_func(
        request=fake_storyboard_request,
        db=db,
        user_id=user_id,
    )
    script_id = storyboard_response.script_id
    script_title = storyboard_response.script_title or (script.title if script else "")

    # 查询生成的镜头
    shot_result = await db.execute(
        select(Shot).where(
            and_(
                Shot.storyboard_id == storyboard_response.id,
                Shot.user_id == user_id
            )
        )
    )
    shots = list(shot_result.scalars().all())

    # 记录活动
    from app.api.v1.endpoints.dashboard import log_activity
    await log_activity(
        db=db,
        user_id=user_id,
        activity_type="generated",
        entity_type="production_chain",
        entity_id=chapter_id,
        title=f"一键生成: {script_title} -> {storyboard_response.title}",
    )
    await db.commit()

    return {
        "message": "一键生成完成",
        "chapter_id": chapter_id,
        "script_id": script_id,
        "script_title": script_title,
        "storyboard_id": storyboard_response.id,
        "storyboard_title": storyboard_response.title,
        "shot_count": len(shots),
        "shots": [
            {
                "id": shot.id,
                "shot_number": shot.shot_number,
                "prompt": shot.prompt,
                "duration": shot.duration,
            }
            for shot in shots
        ],
        "production_status": {
            "has_script": True,
            "has_storyboard": True,
            "has_shots": len(shots) > 0,
            "shot_count": len(shots),
        },
    }


@router.post("/regenerate", response_model=ChapterResponse)
async def regenerate_chapter_content(
    request: ChapterRegenerateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """AI重生成章节内容 - 基于当前章节重新生成，替换原有内容"""
    result = await db.execute(
        select(Chapter).where(and_(Chapter.id == request.chapter_id, Chapter.user_id == user_id))
    )
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    novel = await get_novel_for_user(db, chapter.novel_id, user_id)
    chapters = await list_chapters_for_novel(db, chapter.novel_id, user_id)
    new_content, metadata = await generate_chapter_text(
        db=db,
        user_id=user_id,
        novel=novel,
        chapter_title=chapter.title,
        chapters=chapters,
        current_chapter=chapter,
        mode="rewrite",
        current_content=chapter.content,
        instruction=request.prompt,
    )
    chapter.content = new_content
    metadata.update(apply_generated_chapter_title(chapter, content=new_content, instruction=request.prompt))
    chapter.word_count = len(new_content)
    chapter.status = "completed"
    chapter.updated_at = utc_now()
    sync_result = await persist_story_context_from_chapter(db, user_id, novel, chapter, metadata=metadata)
    await refresh_novel_word_count(db, novel, user_id)
    await db.commit()
    await db.refresh(chapter)

    ai_generation = build_ai_generation_feedback(
        stage="completed",
        message="章节已重新生成、保存，并同步实体/Story Bible 上下文",
        context=metadata.get("story_prompt_context"),
        provider=metadata.get("provider"),
        model=metadata.get("model_id") or metadata.get("default_model_id"),
        extra={
            "mode": metadata.get("mode"),
            "entity_count": sync_result.get("entity_count"),
            "story_bible_count": sync_result.get("story_bible_count"),
            "title_suggested": metadata.get("title_suggested"),
            "title_updated": metadata.get("title_updated"),
        },
    )
    return build_chapter_response(chapter, novel.title, ai_generation=ai_generation)
