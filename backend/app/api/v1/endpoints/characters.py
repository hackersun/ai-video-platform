"""
角色管理 API 端点
"""

from app.core.time_utils import utc_now
from typing import List, Optional
from datetime import datetime
from uuid import uuid4
import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, or_
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.api_key_utils import (
    create_image_generation_service,
    create_text_generation_service,
    get_user_image_model_config,
    get_user_text_model_config,
)
from app.core.dev_generation import dev_image_url, is_dev_mode
from app.core.security import get_current_user_id
from app.models import Chapter, ImageJob, Novel
from app.models.character import Character
from app.api.v1.endpoints.dashboard import log_activity
from app.services.media_persistence import persist_remote_media_url
from app.services.story_prompt_context import compact_text, load_story_prompt_context

router = APIRouter(tags=["角色管理"])


# ============== 数据模型 ==============

class CharacterCreate(BaseModel):
    """创建角色请求"""
    novel_id: Optional[str] = Field(None, description="所属小说ID")
    chapter_id: Optional[str] = Field(None, description="来源章节ID")
    name: str = Field(..., min_length=1, max_length=100, description="角色名称")
    description: Optional[str] = Field(None, description="角色描述")
    appearance: Optional[str] = Field(None, description="外貌特征")
    personality: Optional[str] = Field(None, description="性格特点")
    voice: Optional[str] = Field(None, description="声音特征")
    avatar: Optional[str] = Field(None, description="头像URL")
    tags: List[str] = Field(default_factory=list, description="标签")


class CharacterUpdate(BaseModel):
    """更新角色请求"""
    novel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    appearance: Optional[str] = None
    personality: Optional[str] = None
    voice: Optional[str] = None
    avatar: Optional[str] = None
    tags: Optional[List[str]] = None


class CharacterResponse(BaseModel):
    """角色响应"""
    id: str
    user_id: str
    novel_id: Optional[str]
    chapter_id: Optional[str]
    name: str
    description: Optional[str]
    appearance: Optional[str]
    personality: Optional[str]
    voice: Optional[str]
    avatar: Optional[str]
    tags: List[str]
    created_at: datetime
    updated_at: datetime
    
    @classmethod
    def from_orm(cls, character: Character) -> "CharacterResponse":
        tags = []
        if character.tags:
            try:
                tags = json.loads(character.tags) if isinstance(character.tags, str) else character.tags
            except:
                tags = []
        return cls(
            id=character.id,
            user_id=character.user_id,
            novel_id=character.novel_id,
            chapter_id=character.chapter_id,
            name=character.name,
            description=character.description,
            appearance=character.appearance,
            personality=character.personality,
            voice=character.voice,
            avatar=character.avatar,
            tags=tags,
            created_at=character.created_at,
            updated_at=character.updated_at
        )


class CharacterExtractRequest(BaseModel):
    """AI提取角色请求"""
    novel_id: Optional[str] = Field(None, description="小说ID（优先使用，会自动获取小说和章节内容）")
    chapter_id: Optional[str] = Field(None, description="章节ID（可选，单独提取某章角色）")
    text: Optional[str] = Field(None, description="待分析文本（直接传入文本时使用）")
    character_count: int = Field(default=10, ge=1, le=30, description="提取角色数量")
    auto_generate_avatar: bool = Field(default=True, description="提取后自动生成头像图片")
    model_config_id: Optional[str] = Field(None, description="已保存的文本模型配置ID")
    image_model_config_id: Optional[str] = Field(None, description="已保存的图像模型配置ID")


class CharacterAvatarGenerateRequest(BaseModel):
    """生成角色头像请求"""
    style: str = Field("anime", description="头像风格")
    model_config_id: Optional[str] = Field(None, description="已保存的图像模型配置ID")


class CharacterAvatarGenerateResponse(BaseModel):
    """生成角色头像响应"""
    character: CharacterResponse
    avatar_url: str
    job_id: str
    status: str
    message: str


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


# ============== API端点 ==============

async def _resolve_character_scope(
    db: AsyncSession,
    user_id: str,
    *,
    novel_id: Optional[str] = None,
    chapter_id: Optional[str] = None,
) -> tuple[Optional[str], Optional[str]]:
    """Validate and normalize character scope."""
    if not novel_id and not chapter_id:
        return None, None

    from app.models import Chapter, Novel

    if chapter_id:
        result = await db.execute(
            select(Chapter).where(and_(Chapter.id == chapter_id, Chapter.user_id == user_id))
        )
        chapter = result.scalar_one_or_none()
        if chapter is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="章节不存在")
        if novel_id and chapter.novel_id != novel_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="章节不属于指定小说")
        novel_id = chapter.novel_id

    if novel_id:
        result = await db.execute(
            select(Novel).where(and_(Novel.id == novel_id, Novel.user_id == user_id))
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="小说不存在")

    return novel_id, chapter_id


def _character_name_key(name: Optional[str]) -> str:
    return "".join(ch for ch in (name or "").strip().lower() if not ch.isspace() and ch not in "·・-—_，,。.")


def _json_tags(value) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            return [item.strip() for item in value.split(",") if item.strip()]
    return []


async def _find_character_by_name_scope(
    db: AsyncSession,
    user_id: str,
    *,
    name: Optional[str],
    novel_id: Optional[str],
) -> Optional[Character]:
    name_key = _character_name_key(name)
    if not name_key:
        return None

    result = await db.execute(
        select(Character).where(
            and_(
                Character.user_id == user_id,
                Character.novel_id == novel_id if novel_id else Character.novel_id.is_(None),
            )
        )
    )
    for character in result.scalars().all():
        if _character_name_key(character.name) == name_key:
            return character
    return None


def _merge_text(current: Optional[str], incoming: Optional[str], limit: int = 1600) -> Optional[str]:
    incoming_text = (incoming or "").strip()
    current_text = (current or "").strip()
    if not incoming_text:
        return current
    if not current_text:
        return incoming_text
    if incoming_text in current_text:
        return current
    if current_text in incoming_text:
        return incoming_text
    merged = f"{current_text}\n{incoming_text}"
    return merged[:limit]


def _merge_tags(current, incoming) -> List[str]:
    merged: List[str] = []
    seen: set[str] = set()
    for tag in [*_json_tags(current), *_json_tags(incoming)]:
        key = tag.lower()
        if tag and key not in seen:
            merged.append(tag)
            seen.add(key)
    return merged


async def _upsert_extracted_character(
    db: AsyncSession,
    user_id: str,
    *,
    novel_id: Optional[str],
    chapter_id: Optional[str],
    char_data: dict,
) -> Character:
    name = (char_data.get("name") or "未知角色").strip() or "未知角色"
    existing = await _find_character_by_name_scope(db, user_id, name=name, novel_id=novel_id)
    if existing:
        existing.chapter_id = existing.chapter_id or chapter_id
        existing.description = _merge_text(existing.description, char_data.get("description"))
        existing.appearance = _merge_text(existing.appearance, char_data.get("appearance"))
        existing.personality = _merge_text(existing.personality, char_data.get("personality"))
        existing.voice = _merge_text(existing.voice, char_data.get("voice"), limit=500)
        existing.tags = json.dumps(_merge_tags(existing.tags, char_data.get("tags") or []), ensure_ascii=False)
        existing.updated_at = utc_now()
        db.add(existing)
        return existing

    new_character = Character(
        id=str(uuid4()),
        user_id=user_id,
        novel_id=novel_id,
        chapter_id=chapter_id,
        name=name,
        description=char_data.get("description"),
        appearance=char_data.get("appearance"),
        personality=char_data.get("personality"),
        voice=char_data.get("voice"),
        tags=json.dumps(_json_tags(char_data.get("tags") or []), ensure_ascii=False),
    )
    db.add(new_character)
    return new_character


def _infer_gender_hint(character: Character) -> str:
    text = " ".join(
        value
        for value in (
            character.name,
            character.description,
            character.appearance,
            character.personality,
            character.voice,
            " ".join(_json_tags(character.tags)),
        )
        if value
    )
    female_markers = ("女性", "女生", "女孩", "少女", "女子", "女主", "女主角", "姐姐", "妹妹", "母亲", "公主", "圣女", "她")
    male_markers = ("男性", "男生", "男孩", "少年", "男子", "男主", "男主角", "哥哥", "弟弟", "父亲", "王子", "师兄", "他")
    female_score = sum(1 for marker in female_markers if marker in text)
    male_score = sum(1 for marker in male_markers if marker in text)
    if female_score > male_score:
        return "性别锚点：女性。"
    if male_score > female_score:
        return "性别锚点：男性。"
    return "性别锚点：未明确时不要擅自改变文本暗示的性别。"


async def _build_character_avatar_prompt(
    db: AsyncSession,
    user_id: str,
    character: Character,
    style: str,
) -> str:
    context = await load_story_prompt_context(
        db,
        user_id,
        novel_id=character.novel_id,
        chapter_id=character.chapter_id,
        style=style,
        limit_chapters=2,
    )
    story_lines = [
        f"作品：《{context.get('title') or '未绑定小说'}》",
        f"题材：{context.get('genre') or '通用'}",
    ]
    if context.get("description"):
        story_lines.append(f"简介：{compact_text(context.get('description'), 220)}")

    return "\n".join(
        part
        for part in [
            "动漫角色头像生成任务。",
            "\n".join(story_lines),
            f"角色姓名：{character.name}",
            f"角色描述：{compact_text(character.description, 420)}" if character.description else "",
            f"外貌特征：{compact_text(character.appearance, 420)}" if character.appearance else "",
            f"性格与气质：{compact_text(character.personality, 260)}" if character.personality else "",
            f"声音/语言风格：{compact_text(character.voice, 180)}" if character.voice else "",
            f"角色标签：{'、'.join(_json_tags(character.tags))}" if _json_tags(character.tags) else "",
            _infer_gender_hint(character),
            (
                "画面要求：单人半身头像，正面或三分之二侧面，角色设定图质感，"
                "脸部清晰，发型、服饰、年龄感、身份气质必须与角色描述一致。"
            ),
            (
                "硬约束：不要生成多人，不要改变角色性别、年龄、身份、服装气质，"
                "不要添加小说无关角色、文字、水印、logo 或现代摄影棚背景。"
            ),
        ]
        if part
    )


def _extract_first_image_url(result: dict) -> Optional[str]:
    if "data" in result and result["data"]:
        item = result["data"][0]
        if isinstance(item, dict):
            return item.get("url") or item.get("image_url")
        if isinstance(item, str):
            return item
    items = result.get("images") or result.get("image_urls") or []
    if isinstance(items, dict):
        items = items.get("items") or items.get("images") or items.get("image_urls") or []
    if items:
        first = items[0]
        if isinstance(first, dict):
            return first.get("url") or first.get("image_url")
        if isinstance(first, str):
            return first
    local_urls = result.get("local_urls") or []
    return local_urls[0] if local_urls else None


async def _generate_avatar_for_character(
    db: AsyncSession,
    user_id: str,
    character: Character,
    *,
    style: str = "anime",
    model_config_id: Optional[str] = None,
) -> tuple[str, str, str]:
    job_id = str(uuid4())
    prompt = await _build_character_avatar_prompt(db, user_id, character, style)
    task_id = None
    model_id = "dev-placeholder"
    message = "头像生成成功"

    try:
        api_key, provider_name, model_id, base_url = await get_user_image_model_config(
            db,
            user_id,
            config_id=model_config_id,
        )
        service = create_image_generation_service(api_key or "", provider_name or "", base_url)
        if provider_name in ("volcano", "volcano_agent_plan"):
            result = await service.generate_image(prompt=prompt, model=model_id, size="2K", num=1)
        elif provider_name == "minimax":
            result = await service.generate_image(
                prompt=prompt,
                model=model_id,
                aspect_ratio="1:1",
                n=1,
                response_format="url",
            )
        elif provider_name == "openai":
            result = await service.generate_image(
                prompt=prompt,
                model=model_id,
                size="1024x1024",
                n=1,
                save_local=False,
            )
        else:
            raise HTTPException(status_code=400, detail=f"不支持的图像模型服务商: {provider_name}")
        task_id = result.get("id") or result.get("task_id")
        image_url = _extract_first_image_url(result)
    except HTTPException:
        if not is_dev_mode():
            raise
        image_url = dev_image_url(job_id, character.name or "character-avatar")
        task_id = f"dev-avatar-{job_id}"
        message = "DEV_MODE 本地头像已生成，未调用云端图像模型"

    if not image_url:
        raise HTTPException(status_code=500, detail="头像生成失败：图像模型未返回图片地址")

    persistence_error = None
    try:
        image_url = await persist_remote_media_url(
            image_url,
            media_type="image",
            subdir="images",
            prefix=f"character-avatar-{job_id[:8]}",
            max_bytes=20 * 1024 * 1024,
        ) or image_url
    except Exception as exc:
        persistence_error = str(exc)
        message = f"{message}，但本地持久化失败，将暂用供应商图片地址"

    character.avatar = image_url
    character.updated_at = utc_now()
    db.add(character)

    image_job = ImageJob(
        id=job_id,
        user_id=user_id,
        task_id=task_id,
        prompt=prompt,
        model=model_id or "",
        size="2K",
        num=1,
        style=style,
        character_id=character.id,
        status="succeeded",
        image_urls=[image_url],
        error_message=persistence_error,
        completed_at=utc_now(),
    )
    db.add(image_job)
    return job_id, image_url, message


@router.get("", response_model=List[CharacterResponse])
async def list_characters(
    novel_id: Optional[str] = Query(None, description="按小说过滤角色"),
    chapter_id: Optional[str] = Query(None, description="按章节过滤角色"),
    include_global: bool = Query(False, description="按小说过滤时是否包含未绑定小说的全局角色"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取用户角色；传 novel_id 时默认只返回该小说角色。"""
    scoped_novel_id, scoped_chapter_id = await _resolve_character_scope(
        db,
        user_id,
        novel_id=novel_id,
        chapter_id=chapter_id,
    )
    query = select(Character).where(Character.user_id == user_id)
    if scoped_novel_id:
        if include_global:
            query = query.where(or_(Character.novel_id == scoped_novel_id, Character.novel_id.is_(None)))
        else:
            query = query.where(Character.novel_id == scoped_novel_id)
    if scoped_chapter_id:
        query = query.where(or_(Character.chapter_id == scoped_chapter_id, Character.chapter_id.is_(None)))
    result = await db.execute(query.order_by(desc(Character.created_at)))
    characters = result.scalars().all()
    return [CharacterResponse.from_orm(char) for char in characters]


@router.get("/count")
async def get_character_count(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取角色数量（用于Dashboard统计）"""
    result = await db.execute(
        select(Character).where(Character.user_id == user_id)
    )
    characters = result.scalars().all()
    
    return {"count": len(characters)}


@router.get("/{character_id}", response_model=CharacterResponse)
async def get_character(
    character_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取单个角色详情"""
    result = await db.execute(
        select(Character).where(
            and_(Character.id == character_id, Character.user_id == user_id)
        )
    )
    character = result.scalar_one_or_none()
    
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="角色不存在"
        )
    
    return CharacterResponse.from_orm(character)


@router.post("", response_model=CharacterResponse, status_code=status.HTTP_201_CREATED)
async def create_character(
    character: CharacterCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """创建新角色"""
    novel_id, chapter_id = await _resolve_character_scope(
        db,
        user_id,
        novel_id=character.novel_id,
        chapter_id=character.chapter_id,
    )
    new_character = Character(
        id=str(uuid4()),
        user_id=user_id,
        novel_id=novel_id,
        chapter_id=chapter_id,
        name=character.name,
        description=character.description,
        appearance=character.appearance,
        personality=character.personality,
        voice=character.voice,
        avatar=character.avatar,
        tags=json.dumps(character.tags) if character.tags else "[]",
    )
    
    db.add(new_character)
    await db.commit()
    await db.refresh(new_character)

    await log_activity(
        db=db,
        user_id=user_id,
        activity_type="created",
        entity_type="character",
        entity_id=new_character.id,
        title=f"创建角色: {new_character.name}",
    )
    await db.commit()

    return CharacterResponse.from_orm(new_character)


@router.put("/{character_id}", response_model=CharacterResponse)
async def update_character(
    character_id: str,
    character: CharacterUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """更新角色信息"""
    result = await db.execute(
        select(Character).where(
            and_(Character.id == character_id, Character.user_id == user_id)
        )
    )
    db_character = result.scalar_one_or_none()
    
    if not db_character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="角色不存在"
        )
    
    # 更新非空字段
    update_data = character.model_dump(exclude_unset=True)
    if "novel_id" in update_data or "chapter_id" in update_data:
        next_novel_id, next_chapter_id = await _resolve_character_scope(
            db,
            user_id,
            novel_id=update_data.get("novel_id", db_character.novel_id),
            chapter_id=update_data.get("chapter_id", db_character.chapter_id),
        )
        update_data["novel_id"] = next_novel_id
        update_data["chapter_id"] = next_chapter_id
    for field, value in update_data.items():
        if field == 'tags' and value is not None:
            setattr(db_character, field, json.dumps(value))
        else:
            setattr(db_character, field, value)
    
    db_character.updated_at = utc_now()
    
    await db.commit()
    await db.refresh(db_character)
    
    return CharacterResponse.from_orm(db_character)


@router.delete("/{character_id}")
async def delete_character(
    character_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """删除角色"""
    result = await db.execute(
        select(Character).where(
            and_(Character.id == character_id, Character.user_id == user_id)
        )
    )
    character = result.scalar_one_or_none()
    
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="角色不存在"
        )
    
    await db.delete(character)
    await db.commit()

    return {"message": "角色已删除"}


@router.post("/{character_id}/generate-avatar", response_model=CharacterAvatarGenerateResponse)
async def generate_character_avatar(
    character_id: str,
    request: CharacterAvatarGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """根据角色和小说上下文生成头像，并回写角色头像。"""
    result = await db.execute(
        select(Character).where(and_(Character.id == character_id, Character.user_id == user_id))
    )
    character = result.scalar_one_or_none()
    if not character:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色不存在")

    try:
        job_id, avatar_url, message = await _generate_avatar_for_character(
            db,
            user_id,
            character,
            style=request.style,
            model_config_id=request.model_config_id,
        )
        await db.commit()
        await db.refresh(character)
        return CharacterAvatarGenerateResponse(
            character=CharacterResponse.from_orm(character),
            avatar_url=avatar_url,
            job_id=job_id,
            status="succeeded",
            message=message,
        )
    except HTTPException:
        await db.rollback()
        raise
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"头像生成失败: {str(exc)}")


# ============== 头像生成辅助函数 ==============

def build_avatar_prompt(char: Character) -> str:
    """Construct an image generation prompt from character data."""
    parts = []
    if char.name:
        parts.append(f"character: {char.name}")
    if char.appearance:
        parts.append(f"appearance: {char.appearance}")
    if char.personality:
        parts.append(f"personality: {char.personality}")
    parts.append("anime style, high quality, portrait")
    return ", ".join(parts)


@router.post("/extract", response_model=List[CharacterResponse], status_code=status.HTTP_201_CREATED)
async def extract_characters(
    request: CharacterExtractRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """AI提取角色 - 从小说/章节文本中分析并提取角色信息"""
    # 获取待分析的文本内容
    analysis_text = request.text
    novel_title = "未知小说"
    scoped_novel_id, scoped_chapter_id = await _resolve_character_scope(
        db,
        user_id,
        novel_id=request.novel_id,
        chapter_id=request.chapter_id,
    )

    if not analysis_text and scoped_chapter_id:
        # 根据章节ID获取内容
        from app.models import Novel, Chapter

        chapter_result = await db.execute(
            select(Chapter, Novel)
            .join(Novel, Chapter.novel_id == Novel.id)
            .where(and_(Chapter.id == scoped_chapter_id, Chapter.user_id == user_id))
        )
        row = chapter_result.first()
        if not row:
            raise HTTPException(status_code=404, detail="章节不存在")
        chapter, novel = row
        novel_title = novel.title

        parts = []
        if novel.description:
            parts.append(f"【小说简介】{novel.description}")
        parts.append(f"\n=== 第{chapter.chapter_number}章《{chapter.title}》 ===\n{chapter.content or ''}")
        analysis_text = "\n".join(parts)

    elif not analysis_text and scoped_novel_id:
        # 根据小说ID获取小说信息和所有章节内容
        from app.models import Novel, Chapter

        # 获取小说信息
        novel_result = await db.execute(
            select(Novel).where(and_(Novel.id == scoped_novel_id, Novel.user_id == user_id))
        )
        novel = novel_result.scalar_one_or_none()
        if not novel:
            raise HTTPException(status_code=404, detail="小说不存在")

        novel_title = novel.title

        # 获取所有章节内容
        chapters_result = await db.execute(
            select(Chapter)
            .where(and_(Chapter.novel_id == scoped_novel_id, Chapter.user_id == user_id))
            .order_by(Chapter.chapter_number)
        )
        chapters = chapters_result.scalars().all()

        if not chapters:
            raise HTTPException(status_code=400, detail="该小说暂无章节内容，请先生成或编写章节后再提取角色")

        # 拼接小说简介和所有章节内容
        parts = []
        if novel.description:
            parts.append(f"【小说简介】{novel.description}")
        if novel.genre:
            parts.append(f"【小说类型】{novel.genre}")

        for ch in chapters:
            if ch.content:
                parts.append(f"\n=== 第{ch.chapter_number}章《{ch.title}》 ===\n{ch.content}")

        analysis_text = "\n".join(parts)

    elif not analysis_text:
        raise HTTPException(status_code=400, detail="请提供 novel_id、chapter_id 或 text 参数")

    if len(analysis_text) < 50:
        raise HTTPException(status_code=400, detail="文本内容太少，无法提取角色，请先生成章节内容")

    # 获取用户的API密钥
    api_key, provider_name, model_id, base_url = await get_user_qwen_api_key(
        db,
        user_id,
        request.model_config_id,
    )

    service = create_text_generation_service(api_key, provider_name, base_url)

    # 构建提取提示词
    system_prompt = f"""你是一个专业的小说角色分析专家。你需要从给定的小说文本中识别和提取所有重要角色。

【小说信息】
书名：《{novel_title}》

【任务要求】
请为每个识别出的角色提取以下信息：
1. name: 角色名称（中文）
2. description: 角色背景、身份、与主角的关系等描述（中文）
3. appearance: 外貌特征描述（中文）
4. personality: 性格特点描述（中文）
5. voice: 声音、语言风格特征描述（中文）
6. tags: 角色标签列表，如：主角、女主角、反派、师父、妖兽等（中文标签）

【重要】
1. **必须全程使用中文输出**，包括所有角色名称、描述、标签
2. 严格按照JSON数组格式输出，不要包含任何额外文字、解释或markdown标记
3. 仔细分析文本中出现的每个人物，包括主角、配角、反派、路人等
4. 同一角色不要重复出现
5. tags数组中的标签必须全部是中文

【输出格式】
直接输出JSON数组，不要用markdown代码块包裹："""

    # 截断过长的文本（模型上下文有限）
    max_chars = 30000
    if len(analysis_text) > max_chars:
        analysis_text = analysis_text[:max_chars] + "\n\n[内容已截断]"

    try:
        response = await service.safe_chat_completion(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"请从以下文本中提取角色信息（最多{request.character_count}个重要角色），直接输出JSON数组：\n\n{analysis_text}"}
            ],
            temperature=0.3,
            max_tokens=4000
        )

        content = response["choices"][0]["message"]["content"]

        # 解析JSON
        import json
        json_str = content.strip()
        # 去掉可能的markdown代码块
        if "```json" in json_str:
            json_str = json_str.split("```json")[1]
        elif "```" in json_str:
            json_str = json_str.split("```")[1]
        if "```" in json_str:
            json_str = json_str.split("```")[0]
        json_str = json_str.strip()

        characters_data = json.loads(json_str)

        # 限制数量
        if not isinstance(characters_data, list):
            characters_data = [characters_data]
        characters_data = characters_data[:request.character_count]

    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI返回内容解析失败: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI角色提取失败: {str(e)}"
        )

    # 创建或更新角色记录。同一小说内同名角色复用，避免重复提取造成角色库膨胀。
    created_characters: List[Character] = []
    seen_keys: set[str] = set()
    for char_data in characters_data:
        name_key = _character_name_key(char_data.get("name"))
        if not name_key or name_key in seen_keys:
            continue
        seen_keys.add(name_key)
        character = await _upsert_extracted_character(
            db,
            user_id,
            novel_id=scoped_novel_id,
            chapter_id=scoped_chapter_id,
            char_data=char_data,
        )
        created_characters.append(character)

    await db.commit()

    # 自动生成头像。失败不阻断角色提取，但角色详情页仍可手动重试。
    if request.auto_generate_avatar and created_characters:
        for char in created_characters:
            if char.avatar:
                continue
            try:
                await _generate_avatar_for_character(
                    db,
                    user_id,
                    char,
                    style="anime",
                    model_config_id=request.image_model_config_id,
                )
                await db.commit()
            except Exception:
                await db.rollback()

    # 刷新并返回
    for char in created_characters:
        await db.refresh(char)

    return [CharacterResponse.from_orm(char) for char in created_characters]
