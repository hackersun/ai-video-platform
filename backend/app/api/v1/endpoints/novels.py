"""
小说管理 API 端点
"""

from typing import List, Optional
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.llm_config import LLMProvider, LLMModel, LLMConfig
from app.models import Novel, Chapter
from app.api.v1.endpoints.dashboard import log_activity

router = APIRouter(tags=["小说管理"])


# ============== Pydantic 模型 ==============

class NovelCreate(BaseModel):
    """创建小说"""
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    genre: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    cover_url: Optional[str] = None


class NovelUpdate(BaseModel):
    """更新小说"""
    title: Optional[str] = None
    description: Optional[str] = None
    genre: Optional[str] = None
    status: Optional[str] = None
    word_count: Optional[int] = None
    tags: Optional[List[str]] = None
    cover_url: Optional[str] = None


class NovelResponse(BaseModel):
    """小说响应"""
    id: str
    user_id: str
    title: str
    description: Optional[str]
    genre: Optional[str]
    status: str
    word_count: int
    tags: List[str]
    cover_url: Optional[str]
    source: str
    created_at: datetime
    updated_at: datetime


class NovelGenerateRequest(BaseModel):
    """AI生成小说请求"""
    prompt: str = Field(..., min_length=1, description="创作主题/提示词")
    genre: str = Field(..., description="小说类型（玄幻、都市、仙侠、科幻等）")
    chapter_count: int = Field(default=3, ge=1, le=20, description="章节数量")
    style: Optional[str] = Field(None, description="写作风格（可选）")


class ChapterBriefResponse(BaseModel):
    """章节简要响应（嵌套在小说生成响应中）"""
    id: str
    title: str
    chapter_number: int
    content: Optional[str]
    word_count: int


class NovelGenerateResponse(BaseModel):
    """AI生成小说响应"""
    id: str
    user_id: str
    title: str
    description: Optional[str]
    genre: Optional[str]
    status: str
    word_count: int
    tags: List[str]
    cover_url: Optional[str]
    source: str
    chapters: List[ChapterBriefResponse]
    created_at: datetime
    updated_at: datetime


# ============== LLM API Key 辅助函数 ==============

async def get_user_qwen_api_key(db: AsyncSession, user_id: str) -> tuple[str, str, str, Optional[str]]:
    """
    获取用户的千问/DashScope API密钥

    Returns:
        tuple: (api_key, provider_name, model_id)

    Raises:
        HTTPException: 如果未找到有效配置
    """
    # 查找用户的千问/百炼LLM配置（过滤provider）
    result = await db.execute(
        select(LLMConfig, LLMModel, LLMProvider)
        .join(LLMModel, LLMConfig.model_id == LLMModel.id)
        .join(LLMProvider, LLMModel.provider_id == LLMProvider.id)
        .where(
            and_(
                LLMConfig.user_id == user_id,
                LLMConfig.is_active == True,
                LLMProvider.name.in_(["qianlian", "dashscope", "qwen"]),
            )
        )
        .order_by(desc(LLMConfig.is_default), desc(LLMConfig.last_used_at))
    )
    row = result.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先配置千问/百炼大模型API密钥"
        )

    config, model, provider = row

    if not config.api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="大模型API密钥未设置"
        )

    return config.api_key, provider.name, model.model_id, model.base_url


# ============== API 端点 ==============

@router.get("", response_model=List[NovelResponse])
async def list_novels(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取用户的所有小说"""
    result = await db.execute(
        select(Novel)
        .where(Novel.user_id == user_id)
        .order_by(desc(Novel.updated_at))
    )
    novels = result.scalars().all()

    return [
        NovelResponse(
            id=n.id,
            user_id=n.user_id,
            title=n.title,
            description=n.description,
            genre=n.genre,
            status=n.status or "draft",
            word_count=n.word_count or 0,
            tags=n.tags or [],
            cover_url=n.cover_url,
            source=n.source or "manual",
            created_at=n.created_at,
            updated_at=n.updated_at
        )
        for n in novels
    ]


@router.get("/{novel_id}", response_model=NovelResponse)
async def get_novel(
    novel_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取单个小说"""
    result = await db.execute(
        select(Novel).where(and_(Novel.id == novel_id, Novel.user_id == user_id))
    )
    novel = result.scalar_one_or_none()

    if not novel:
        raise HTTPException(status_code=404, detail="小说不存在")

    return NovelResponse(
        id=novel.id,
        user_id=novel.user_id,
        title=novel.title,
        description=novel.description,
        genre=novel.genre,
        status=novel.status or "draft",
        word_count=novel.word_count or 0,
        tags=novel.tags or [],
        cover_url=novel.cover_url,
        source=novel.source or "manual",
        created_at=novel.created_at,
        updated_at=novel.updated_at
    )


@router.post("", response_model=NovelResponse, status_code=status.HTTP_201_CREATED)
async def create_novel(
    novel: NovelCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """创建小说"""
    db_novel = Novel(
        id=str(uuid4()),
        user_id=user_id,
        title=novel.title,
        description=novel.description,
        genre=novel.genre,
        tags=novel.tags or [],
        cover_url=novel.cover_url,
        status="draft"
    )
    db.add(db_novel)
    await db.commit()
    await db.refresh(db_novel)

    await log_activity(
        db=db,
        user_id=user_id,
        activity_type="created",
        entity_type="novel",
        entity_id=db_novel.id,
        title=f"创建小说: {db_novel.title}",
    )
    await db.commit()

    return NovelResponse(
        id=db_novel.id,
        user_id=db_novel.user_id,
        title=db_novel.title,
        description=db_novel.description,
        genre=db_novel.genre,
        status=db_novel.status or "draft",
        word_count=db_novel.word_count or 0,
        tags=db_novel.tags or [],
        cover_url=db_novel.cover_url,
        source=db_novel.source or "manual",
        created_at=db_novel.created_at,
        updated_at=db_novel.updated_at
    )


@router.put("/{novel_id}", response_model=NovelResponse)
async def update_novel(
    novel_id: str,
    novel_update: NovelUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """更新小说"""
    result = await db.execute(
        select(Novel).where(and_(Novel.id == novel_id, Novel.user_id == user_id))
    )
    db_novel = result.scalar_one_or_none()

    if not db_novel:
        raise HTTPException(status_code=404, detail="小说不存在")

    # 更新字段
    update_data = novel_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_novel, key, value)

    await db.commit()
    await db.refresh(db_novel)

    return NovelResponse(
        id=db_novel.id,
        user_id=db_novel.user_id,
        title=db_novel.title,
        description=db_novel.description,
        genre=db_novel.genre,
        status=db_novel.status or "draft",
        word_count=db_novel.word_count or 0,
        tags=db_novel.tags or [],
        cover_url=db_novel.cover_url,
        source=db_novel.source or "manual",
        created_at=db_novel.created_at,
        updated_at=db_novel.updated_at
    )


@router.delete("/{novel_id}")
async def delete_novel(
    novel_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """删除小说"""
    result = await db.execute(
        select(Novel).where(and_(Novel.id == novel_id, Novel.user_id == user_id))
    )
    db_novel = result.scalar_one_or_none()

    if not db_novel:
        raise HTTPException(status_code=404, detail="小说不存在")

    await db.delete(db_novel)
    await db.commit()

    return {"message": "小说已删除"}


@router.post("/generate", response_model=NovelGenerateResponse, status_code=status.HTTP_201_CREATED)
async def generate_novel(
    request: NovelGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """AI生成小说 - 根据主题和类型生成完整小说结构及章节内容"""
    # 获取用户的API密钥
    api_key, provider_name, model_id, base_url = await get_user_qwen_api_key(db, user_id)

    # 根据提供商选择服务
    if provider_name == "qianlian":
        from app.services.qianlian_service import QianlianService
        service = QianlianService(api_key, base_url)
    elif provider_name in ("dashscope", "qwen"):
        from app.services.dashscope_service import DashScopeService
        service = DashScopeService(api_key, base_url)
    else:
        from app.services.qianlian_service import QianlianService
        service = QianlianService(api_key, base_url)

    # 构建创作提示词
    style_hint = f"写作风格：{request.style}。" if request.style else ""
    generation_prompt = f"""请根据以下要求创作一部{request.genre}类型的小说：

主题：{request.prompt}
类型：{request.genre}
{style_hint}
章节数量：{request.chapter_count}章

请生成：
1. 小说标题（简洁有吸引力）
2. 小说简介（100字以内）
3. 每个章节的标题和内容（每章约1500-2000字）

请确保：
- 情节连贯，人物性格鲜明
- 每章有独立的小高潮
- 适当埋设伏笔和悬念
- 遵循{request.genre}类型的典型叙事结构

请以JSON格式输出，格式如下：
{{
    "title": "小说标题",
    "description": "简介",
    "chapters": [
        {{"title": "第一章标题", "content": "第一章内容"}},
        {{"title": "第二章标题", "content": "第二章内容"}}
    ]
}}"""

    # 调用LLM生成小说
    try:
        response = await service.chat_completion(
            model=model_id,
            messages=[
                {"role": "system", "content": "你是一个专业的小说作家，擅长创作各种类型的小说。请严格按照JSON格式输出，不要包含其他内容。"},
                {"role": "user", "content": generation_prompt}
            ],
            temperature=0.8,
            max_tokens=16000
        )

        content = response["choices"][0]["message"]["content"]

        # 尝试解析JSON
        import json
        # 提取JSON部分（处理可能的markdown代码块）
        json_str = content.strip()
        if json_str.startswith("```json"):
            json_str = json_str[7:]
        if json_str.startswith("```"):
            json_str = json_str[3:]
        if json_str.endswith("```"):
            json_str = json_str[:-3]
        json_str = json_str.strip()

        novel_data = json.loads(json_str)

    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI返回内容解析失败: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI生成失败: {str(e)}"
        )

    # 创建小说记录
    novel_id = str(uuid4())
    db_novel = Novel(
        id=novel_id,
        user_id=user_id,
        title=novel_data.get("title", request.prompt[:50]),
        description=novel_data.get("description", ""),
        genre=request.genre,
        tags=[request.genre],
        source="ai_generated",
        status="writing"
    )
    db.add(db_novel)

    # 创建章节记录
    created_chapters = []
    chapters_data = novel_data.get("chapters", [])

    for idx, chapter_data in enumerate(chapters_data):
        chapter_id = str(uuid4())
        chapter_content = chapter_data.get("content", "")
        word_count = len(chapter_content)
        chapter_title = chapter_data.get("title", f"第{idx + 1}章")

        db_chapter = Chapter(
            id=chapter_id,
            novel_id=novel_id,
            user_id=user_id,
            title=chapter_title,
            content=chapter_content,
            chapter_number=idx + 1,
            word_count=word_count,
            status="completed"
        )
        db.add(db_chapter)
        created_chapters.append({
            "id": chapter_id,
            "title": chapter_title,
            "chapter_number": idx + 1,
            "content": chapter_content,
            "word_count": word_count
        })

    # 更新小说的总字数
    total_word_count = sum(c["word_count"] for c in created_chapters)
    db_novel.word_count = total_word_count

    # 如果所有章节都创建了，将小说状态设为completed
    if len(created_chapters) >= request.chapter_count:
        db_novel.status = "completed"

    await db.commit()
    await db.refresh(db_novel)

    return NovelGenerateResponse(
        id=db_novel.id,
        user_id=db_novel.user_id,
        title=db_novel.title,
        description=db_novel.description,
        genre=db_novel.genre,
        status=db_novel.status,
        word_count=db_novel.word_count,
        tags=db_novel.tags or [],
        cover_url=db_novel.cover_url,
        source=db_novel.source or "ai_generated",
        chapters=[ChapterBriefResponse(**c) for c in created_chapters],
        created_at=db_novel.created_at,
        updated_at=db_novel.updated_at
    )
