"""
章节管理 API 端点
"""
import uuid
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, text
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models import Novel, Chapter
from app.models.llm_config import LLMProvider, LLMModel, LLMConfig

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
    created_at: str
    updated_at: str


class ChapterGenerateRequest(BaseModel):
    """AI生成章节请求"""
    novel_id: str = Field(..., description="所属小说ID")
    chapter_title: Optional[str] = Field(None, min_length=1, max_length=200, description="章节标题（不提供则自动生成）")
    prev_chapter_content: Optional[str] = Field(None, description="上一章内容（用于上下文）")


# ============== LLM API Key 辅助函数 ==============

async def get_user_qwen_api_key(db: AsyncSession, user_id: str) -> tuple[str, str, str, Optional[str]]:
    """
    获取用户的千问/DashScope API密钥

    Returns:
        tuple: (api_key, provider_name, model_id, base_url)

    Raises:
        HTTPException: 如果未找到有效配置
    """
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
            detail="请先配置千问/百炼大模型API密钥（LLM配置页面）"
        )

    config, model, provider = row

    if not config.api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="大模型API密钥未设置，请在LLM配置中填入有效的API Key"
        )

    model_id_str = model.model_id
    base_url = model.base_url
    return config.api_key, provider.name, model_id_str, base_url


async def get_novel_for_user(db: AsyncSession, novel_id: str, user_id: str):
    from app.models import Novel

    result = await db.execute(
        select(Novel).where(and_(Novel.id == novel_id, Novel.user_id == user_id))
    )
    novel = result.scalar_one_or_none()
    if novel is None:
        raise HTTPException(status_code=404, detail="小说不存在")
    return novel


def build_chapter_response(chapter: Chapter, novel_title: Optional[str] = None) -> ChapterResponse:
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
        created_at=str(chapter.created_at),
        updated_at=str(chapter.updated_at),
    )


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
    # 获取小说信息
    novel = await get_novel_for_user(db, request.novel_id, user_id)

    # 获取已有章节作为上下文
    result = await db.execute(
        select(Chapter)
        .where(and_(Chapter.novel_id == request.novel_id, Chapter.user_id == user_id))
        .order_by(Chapter.chapter_number)
    )
    existing_chapters = result.scalars().all()
    next_chapter_number = (existing_chapters[-1].chapter_number + 1) if existing_chapters else 1

    # 如果没有提供上一章内容，但有现有章节，使用最后一章
    context_content = request.prev_chapter_content
    if not context_content and existing_chapters:
        context_content = existing_chapters[-1].content or ""

    # 如果没有提供章节标题，自动生成
    chapter_title = request.chapter_title
    if not chapter_title:
        chapter_title = f"第{next_chapter_number}章"

    # 获取用户的API密钥
    api_key, provider_name, model_id, base_url = await get_user_qwen_api_key(db, user_id)

    if provider_name == "qianlian":
        from app.services.qianlian_service import QianlianService
        service = QianlianService(api_key, base_url)
    elif provider_name in ("dashscope", "qwen"):
        from app.services.dashscope_service import DashScopeService
        service = DashScopeService(api_key, base_url)
    else:
        from app.services.qianlian_service import QianlianService
        service = QianlianService(api_key, base_url)

    # 构建提示词
    # 小说简介
    desc_section = f"\n\n【小说简介】\n{novel.description}\n" if novel.description else ""

    # 已有章节内容（用于保持剧情连贯）
    chapters_context = ""
    if existing_chapters:
        chapters_context = "\n\n【已有章节梗概】\n"
        for ch in existing_chapters:
            if ch.content:
                preview = ch.content[:500]
                chapters_context += f"第{ch.chapter_number}章《{ch.title}》：{preview}...\n"

    # 上一章内容（用于续写）
    prev_section = f"\n\n【上一章结尾内容】\n{context_content}\n" if context_content else "\n\n这是小说的第一章，请直接开始创作。"

    system_prompt = f"""你是一个专业的中文小说作家，擅长创作各种类型的网络小说。

【小说信息】
- 书名：《{novel.title}》
- 类型：{novel.genre or '未知'}
- 简介：{novel.description or '暂无简介'}{desc_section}

【本章创作要求】
- 章节标题：{chapter_title}
- 内容要有画面感，描写细腻，情节生动
- 保持与已有剧情的连贯性
- 每章应有完整的起承转合（开端、发展、高潮、结尾）
- 章节字数约1500-3000字
- 适当埋设悬念和伏笔
- **必须全程使用中文创作，包括标题、正文、标点符号全部使用中文**

【重要】
1. 只输出章节正文内容，不要输出标题、思考过程、英文翻译等任何额外内容
2. 不要输出"Thinking Process"、"思考过程"等模型推理痕迹
3. 直接输出小说正文即可"""

    try:
        response = await service.safe_chat_completion(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"{desc_section}{chapters_context}{prev_section}\n\n请创作本章《{chapter_title}》的正文内容，直接输出小说正文，不要包含标题："}
            ],
            temperature=0.8,
            max_tokens=8000
        )

        chapter_content = response["choices"][0]["message"]["content"]

        # 清理内容：去掉可能残留的思考过程等英文内容
        # 如果内容以思考过程开头，尝试提取正文部分
        lines = chapter_content.split('\n')
        clean_lines = []
        skip_mode = False
        for line in lines:
            stripped = line.strip().lower()
            # 跳过思考过程相关行
            if 'thinking process' in stripped or '**thinking' in stripped or stripped.startswith('thinking process') or stripped.startswith('[') and ']' in stripped and len(stripped) < 50:
                skip_mode = True
                continue
            if skip_mode:
                # 找到正文开始
                if len(line.strip()) > 20 and not line.strip().startswith('**'):
                    skip_mode = False
                else:
                    continue
            clean_lines.append(line)
        chapter_content = '\n'.join(clean_lines).strip()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI生成章节失败: {str(e)}"
        )

    # 创建章节记录
    chapter_id = str(uuid.uuid4())
    word_count = len(chapter_content)
    now = datetime.utcnow().isoformat()

    await db.execute(
        text("""
            INSERT INTO chapters (id, novel_id, user_id, title, content, chapter_number, word_count, status, created_at, updated_at)
            VALUES (:id, :novel_id, :user_id, :title, :content, :chapter_number, :word_count, :status, :created_at, :updated_at)
        """),
        {
            "id": chapter_id,
            "novel_id": request.novel_id,
            "user_id": user_id,
            "title": chapter_title,
            "content": chapter_content,
            "chapter_number": next_chapter_number,
            "word_count": word_count,
            "status": "completed",
            "created_at": now,
            "updated_at": now,
        }
    )

    # 更新小说的总字数
    new_total = (novel.word_count or 0) + word_count
    await db.execute(
        text("UPDATE novels SET word_count = :wc, updated_at = :updated WHERE id = :id"),
        {"wc": new_total, "updated": now, "id": request.novel_id}
    )

    await db.commit()

    # 返回生成的章节响应
    return ChapterResponse(
        id=chapter_id,
        novel_id=request.novel_id,
        user_id=user_id,
        title=chapter_title,
        novel_title=novel.title,
        content=chapter_content,
        chapter_number=next_chapter_number,
        word_count=word_count,
        status="completed",
        created_at=now,
        updated_at=now
    )

class ChapterRegenerateRequest(BaseModel):
    """章节内容重生成请求"""
    chapter_id: str = Field(..., description="章节ID")
    prompt: Optional[str] = Field(None, description="额外补充指令（可选）")


@router.post("/regenerate", response_model=ChapterResponse)
async def regenerate_chapter_content(
    request: ChapterRegenerateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """AI重生成章节内容 - 基于当前章节重新生成，替换原有内容"""
    # 获取章节信息
    result = await db.execute(
        select(Chapter).where(and_(Chapter.id == request.chapter_id, Chapter.user_id == user_id))
    )
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    # 获取小说信息
    novel = await get_novel_for_user(db, chapter.novel_id, user_id)

    # 获取所有章节用于上下文
    all_chapters_result = await db.execute(
        select(Chapter)
        .where(and_(Chapter.novel_id == chapter.novel_id, Chapter.user_id == user_id))
        .order_by(Chapter.chapter_number)
    )
    all_chapters = all_chapters_result.scalars().all()

    # 找到上一章和下一章内容
    prev_content = None
    next_content = None
    for i, ch in enumerate(all_chapters):
        if ch.id == chapter.id:
            if i > 0:
                prev_content = all_chapters[i - 1].content
            if i < len(all_chapters) - 1:
                next_content = all_chapters[i + 1].content
            break

    # 获取用户的API密钥
    api_key, provider_name, model_id, base_url = await get_user_qwen_api_key(db, user_id)

    if provider_name == "qianlian":
        from app.services.qianlian_service import QianlianService
        service = QianlianService(api_key, base_url)
    elif provider_name in ("dashscope", "qwen"):
        from app.services.dashscope_service import DashScopeService
        service = DashScopeService(api_key, base_url)
    else:
        from app.services.qianlian_service import QianlianService
        service = QianlianService(api_key, base_url)

    # 构建提示词
    desc_section = f"\n\n【小说简介】\n{novel.description}\n" if novel.description else ""
    prev_section = f"\n\n【上一章结尾内容】\n{prev_content}\n" if prev_content else "\n\n这是小说的第一章，请直接开始创作。"
    next_section = f"\n\n【下一章开头（供参考）】\n{next_content}\n" if next_content else ""
    extra_section = f"\n\n【额外要求】\n{request.prompt}\n" if request.prompt else ""

    system_prompt = f"""你是一个专业的中文小说作家，擅长创作各种类型的网络小说。

【小说信息】
- 书名：《{novel.title}》
- 类型：{novel.genre or '未知'}
{desc_section}

【本章创作要求】
- 章节标题：{chapter.title}
- 内容要有画面感，描写细腻，情节生动
- 保持与已有剧情的连贯性
- 每章应有完整的起承转合
- 章节字数约1500-3000字
- 适当埋设悬念和伏笔
- **必须全程使用中文创作，包括标题、正文、标点符号全部使用中文**

【重要】
1. 只输出章节正文内容，不要输出标题、思考过程、英文翻译等任何额外内容
2. 不要输出"Thinking Process"、"思考过程"等模型推理痕迹
3. 直接输出小说正文即可"""

    try:
        response = await service.chat_completion(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"{desc_section}\n\n【上一章结尾】\n{prev_content or '（无上一章）'}\n{next_section}\n\n请基于以上上下文，创作本章《{chapter.title}》的正文内容，直接输出小说正文，不要包含标题：{extra_section}"}
            ],
            temperature=0.8,
            max_tokens=8000
        )

        new_content = response["choices"][0]["message"]["content"]

        # 清理内容
        lines = new_content.split('\n')
        clean_lines = []
        skip_mode = False
        for line in lines:
            stripped = line.strip().lower()
            if 'thinking process' in stripped or '**thinking' in stripped or stripped.startswith('thinking process') or (stripped.startswith('[') and ']' in stripped and len(stripped) < 50):
                skip_mode = True
                continue
            if skip_mode:
                if len(line.strip()) > 20 and not line.strip().startswith('**'):
                    skip_mode = False
                else:
                    continue
            clean_lines.append(line)
        new_content = '\n'.join(clean_lines).strip()

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI生成章节失败: {str(e)}"
        )

    # 更新章节内容
    word_count = len(new_content)
    now = datetime.utcnow().isoformat()
    await db.execute(
        text("UPDATE chapters SET content = :content, word_count = :wc, status = :status, updated_at = :updated WHERE id = :id"),
        {"content": new_content, "wc": word_count, "status": "completed", "updated": now, "id": chapter.id}
    )

    # 更新小说总字数
    await db.commit()

    return ChapterResponse(
        id=str(chapter.id),
        novel_id=str(chapter.novel_id),
        user_id=user_id,
        title=chapter.title,
        novel_title=novel.title,
        content=new_content,
        chapter_number=chapter.chapter_number,
        word_count=word_count,
        status="completed",
        created_at=str(chapter.created_at),
        updated_at=now
    )

