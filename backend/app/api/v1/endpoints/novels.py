"""
小说相关端点
"""

from typing import List
from uuid import UUID, uuid4
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.novel import Novel, Chapter
from app.models.user import User

router = APIRouter()


@router.get("/")
async def list_novels(
    skip: int = 0, limit: int = 20, db: AsyncSession = Depends(get_db)
):
    """获取小说列表"""
    # 从数据库查询
    result = await db.execute(select(Novel).offset(skip).limit(limit))
    novels = result.scalars().all()

    items = []
    for novel in novels:
        items.append(
            {
                "id": str(novel.id),
                "title": novel.title,
                "description": novel.description,
                "genre": novel.genre,
                "status": novel.status,
                "word_count": novel.word_count,
                "author_id": str(novel.author_id),
                "created_at": novel.created_at.isoformat()
                if novel.created_at
                else None,
            }
        )

    # 获取总数
    from sqlalchemy import func

    total_result = await db.execute(select(func.count(Novel.id)))
    total = total_result.scalar()

    return {"items": items, "total": total, "skip": skip, "limit": limit}


from pydantic import BaseModel


class NovelCreateRequest(BaseModel):
    title: str
    description: str = ""
    genre: str = "未分类"
    cover_image: str = ""


@router.post("/")
async def create_novel(
    request: NovelCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """创建小说"""
    from uuid import UUID
    from sqlalchemy import select
    
    # 获取第一个用户作为作者（临时解决方案）
    result = await db.execute(select(User).limit(1))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=400, detail="请先创建用户")
    
    author_uuid = user.id

    novel = Novel(
        id=uuid4(),
        title=request.title,
        description=request.description,
        genre=request.genre,
        author_id=author_uuid,
        status="draft",
        word_count=0,
        ai_generated=False,
        cover_image=request.cover_image or None,
    )
    db.add(novel)
    await db.commit()
    await db.refresh(novel)
    return {"id": str(novel.id), "title": novel.title, "status": novel.status}


@router.get("/my")
async def get_my_novels(
    skip: int = 0,
    limit: int = 20,
    status: str = None,
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的小说列表"""
    # 默认使用测试用户ID
    author_uuid = UUID("df9f3e6c-63ef-4e29-bdd1-130f2579ca23")

    # 构建查询
    query = select(Novel).where(Novel.author_id == author_uuid)
    if status:
        query = query.where(Novel.status == status)

    result = await db.execute(query.offset(skip).limit(limit))
    novels = result.scalars().all()

    items = []
    for novel in novels:
        items.append(
            {
                "id": str(novel.id),
                "title": novel.title,
                "description": novel.description,
                "genre": novel.genre,
                "status": novel.status,
                "word_count": novel.word_count,
                "author_id": str(novel.author_id),
                "created_at": novel.created_at.isoformat()
                if novel.created_at
                else None,
            }
        )

    # 获取总数
    from sqlalchemy import func

    total_result = await db.execute(
        select(func.count(Novel.id)).where(Novel.author_id == author_uuid)
    )
    total = total_result.scalar()

    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.get("/{novel_id}")
async def get_novel(novel_id: UUID, db: AsyncSession = Depends(get_db)):
    """获取小说详情"""
    result = await db.execute(select(Novel).where(Novel.id == novel_id))
    novel = result.scalar_one_or_none()

    if not novel:
        raise HTTPException(status_code=404, detail="小说不存在")

    return {
        "id": str(novel.id),
        "title": novel.title,
        "description": novel.description,
        "genre": novel.genre,
        "cover_image": novel.cover_image,
        "status": novel.status,
        "word_count": novel.word_count,
        "author_id": str(novel.author_id),
        "created_at": novel.created_at.isoformat() if novel.created_at else None,
        "updated_at": novel.updated_at.isoformat() if novel.updated_at else None,
    }


@router.put("/{novel_id}")
async def update_novel(
    novel_id: UUID,
    request: NovelCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """更新小说"""
    result = await db.execute(select(Novel).where(Novel.id == novel_id))
    novel = result.scalar_one_or_none()

    if not novel:
        raise HTTPException(status_code=404, detail="小说不存在")

    novel.title = request.title
    novel.description = request.description
    novel.genre = request.genre
    if request.cover_image:
        novel.cover_image = request.cover_image

    await db.commit()
    await db.refresh(novel)

    return {"id": str(novel.id), "title": novel.title, "status": novel.status}


@router.delete("/{novel_id}")
async def delete_novel(novel_id: UUID, db: AsyncSession = Depends(get_db)):
    """删除小说"""
    result = await db.execute(select(Novel).where(Novel.id == novel_id))
    novel = result.scalar_one_or_none()

    if not novel:
        raise HTTPException(status_code=404, detail="小说不存在")

    await db.delete(novel)
    await db.commit()

    return {"message": "删除成功"}


@router.post("/{novel_id}/publish")
async def publish_novel(novel_id: UUID, db: AsyncSession = Depends(get_db)):
    """发布小说"""
    result = await db.execute(select(Novel).where(Novel.id == novel_id))
    novel = result.scalar_one_or_none()

    if not novel:
        raise HTTPException(status_code=404, detail="小说不存在")

    novel.status = "published"
    await db.commit()
    await db.refresh(novel)

    return {"id": str(novel.id), "title": novel.title, "status": novel.status}


# 章节相关
from uuid import uuid4 as new_uuid


class ChapterCreateRequest(BaseModel):
    title: str
    content: str = ""
    chapter_number: int = 1


@router.get("/{novel_id}/chapters")
async def list_chapters(novel_id: UUID, db: AsyncSession = Depends(get_db)):
    """获取章节列表"""
    result = await db.execute(
        select(Chapter)
        .where(Chapter.novel_id == novel_id)
        .order_by(Chapter.chapter_number)
    )
    chapters = result.scalars().all()

    items = []
    for chapter in chapters:
        items.append(
            {
                "id": str(chapter.id),
                "title": chapter.title,
                "content": chapter.content,
                "chapter_number": chapter.chapter_number,
                "word_count": chapter.word_count,
                "status": chapter.status,
                "novel_id": str(chapter.novel_id),
                "created_at": chapter.created_at.isoformat()
                if chapter.created_at
                else None,
            }
        )

    return {"items": items, "novel_id": str(novel_id), "total": len(items)}


@router.post("/{novel_id}/chapters")
async def create_chapter(
    novel_id: UUID, request: ChapterCreateRequest, db: AsyncSession = Depends(get_db)
):
    """创建章节"""
    # 获取当前章节数
    result = await db.execute(
        select(func.count(Chapter.id)).where(Chapter.novel_id == novel_id)
    )
    chapter_count = result.scalar() or 0

    chapter = Chapter(
        id=new_uuid(),
        novel_id=novel_id,
        title=request.title,
        content=request.content,
        chapter_number=request.chapter_number or (chapter_count + 1),
        word_count=len(request.content) if request.content else 0,
        status="draft",
    )
    db.add(chapter)
    await db.commit()
    await db.refresh(chapter)

    return {
        "id": str(chapter.id),
        "title": chapter.title,
        "chapter_number": chapter.chapter_number,
        "status": chapter.status,
    }


@router.get("/{novel_id}/chapters/{chapter_id}")
async def get_chapter(
    novel_id: UUID, chapter_id: UUID, db: AsyncSession = Depends(get_db)
):
    """获取章节详情"""
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = result.scalar_one_or_none()

    if not chapter or chapter.novel_id != novel_id:
        raise HTTPException(status_code=404, detail="章节不存在")

    return {
        "id": str(chapter.id),
        "title": chapter.title,
        "content": chapter.content,
        "chapter_number": chapter.chapter_number,
        "word_count": chapter.word_count,
        "status": chapter.status,
        "novel_id": str(chapter.novel_id),
        "created_at": chapter.created_at.isoformat() if chapter.created_at else None,
    }


@router.put("/{novel_id}/chapters/{chapter_id}")
async def update_chapter(
    novel_id: UUID,
    chapter_id: UUID,
    request: ChapterCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """更新章节"""
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = result.scalar_one_or_none()

    if not chapter or chapter.novel_id != novel_id:
        raise HTTPException(status_code=404, detail="章节不存在")

    chapter.title = request.title
    chapter.content = request.content
    if request.chapter_number:
        chapter.chapter_number = request.chapter_number
    chapter.word_count = len(request.content) if request.content else 0

    await db.commit()
    await db.refresh(chapter)

    return {
        "id": str(chapter.id),
        "title": chapter.title,
        "chapter_number": chapter.chapter_number,
        "status": chapter.status,
    }


@router.delete("/{novel_id}/chapters/{chapter_id}")
async def delete_chapter(
    novel_id: UUID, chapter_id: UUID, db: AsyncSession = Depends(get_db)
):
    """删除章节"""
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = result.scalar_one_or_none()

    if not chapter or chapter.novel_id != novel_id:
        raise HTTPException(status_code=404, detail="章节不存在")

    await db.delete(chapter)
    await db.commit()

    return {"message": "删除成功"}


from pydantic import BaseModel


class CoverGenerateRequest(BaseModel):
    title: str
    description: str = None
    genre: str = None


@router.post("/generate-cover")
async def generate_cover(
    request: CoverGenerateRequest, db: AsyncSession = Depends(get_db)
):
    """AI生成小说封面"""
    from app.services.ai_service import ai_service

    prompt_parts = []
    if request.title:
        prompt_parts.append(request.title)
    if request.description:
        prompt_parts.append(request.description[:200])
    if request.genre:
        prompt_parts.append(request.genre)

    prompt = " ".join(prompt_parts) if prompt_parts else "fantasy novel cover"

    cover_url = await ai_service.generate_cover_image(prompt)

    if cover_url:
        return {"cover_url": cover_url, "success": True, "message": "封面生成成功"}
    else:
        return {
            "cover_url": None,
            "success": False,
            "message": "封面生成失败，请稍后重试",
        }


@router.post("/{novel_id}/chapters")
async def create_chapter(novel_id: UUID, db: AsyncSession = Depends(get_db)):
    """创建章节"""
    # TODO: 实现章节创建
    return {"message": "创建章节功能待实现"}


# 剧本相关
@router.post("/{novel_id}/generate-script")
async def generate_script(novel_id: UUID, db: AsyncSession = Depends(get_db)):
    """AI生成剧本"""
    # TODO: 实现AI剧本生成
    return {"message": "AI剧本生成功能待实现"}
