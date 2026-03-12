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
from app.models.novel import Novel

router = APIRouter()


@router.get("/")
async def list_novels(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """获取小说列表"""
    # 从数据库查询
    result = await db.execute(
        select(Novel).offset(skip).limit(limit)
    )
    novels = result.scalars().all()
    
    items = []
    for novel in novels:
        items.append({
            "id": str(novel.id),
            "title": novel.title,
            "description": novel.description,
            "genre": novel.genre,
            "status": novel.status,
            "word_count": novel.word_count,
            "author_id": str(novel.author_id),
            "created_at": novel.created_at.isoformat() if novel.created_at else None
        })
    
    # 获取总数
    from sqlalchemy import func
    total_result = await db.execute(select(func.count(Novel.id)))
    total = total_result.scalar()
    
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.post("/")
async def create_novel(
    title: str,
    description: str = "",
    genre: str = "未分类",
    author_id: str = "",
    db: AsyncSession = Depends(get_db)
):
    """创建小说"""
    from uuid import UUID
    # 转换 author_id 为 UUID
    author_uuid = UUID(author_id) if author_id else UUID("df9f3e6c-63ef-4e29-bdd1-130f2579ca23")
    
    novel = Novel(
        id=uuid4(),
        title=title,
        description=description,
        genre=genre,
        author_id=author_uuid,
        status="draft",
        word_count=0,
        ai_generated=False
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
    db: AsyncSession = Depends(get_db)
):
    """获取当前用户的小说列表"""
    # 默认使用测试用户ID
    author_uuid = UUID("df9f3e6c-63ef-4e29-bdd1-130f2579ca23")
    
    # 构建查询
    query = select(Novel).where(Novel.author_id == author_uuid)
    if status:
        query = query.where(Novel.status == status)
    
    result = await db.execute(
        query.offset(skip).limit(limit)
    )
    novels = result.scalars().all()
    
    items = []
    for novel in novels:
        items.append({
            "id": str(novel.id),
            "title": novel.title,
            "description": novel.description,
            "genre": novel.genre,
            "status": novel.status,
            "word_count": novel.word_count,
            "author_id": str(novel.author_id),
            "created_at": novel.created_at.isoformat() if novel.created_at else None
        })
    
    # 获取总数
    from sqlalchemy import func
    total_result = await db.execute(select(func.count(Novel.id)).where(Novel.author_id == author_uuid))
    total = total_result.scalar()
    
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/{novel_id}")
async def get_novel(
    novel_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """获取小说详情"""
    # TODO: 实现小说详情查询
    raise HTTPException(status_code=404, detail="小说不存在")


@router.put("/{novel_id}")
async def update_novel(
    novel_id: UUID,
    # novel_update: NovelUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新小说"""
    # TODO: 实现小说更新
    raise HTTPException(status_code=404, detail="小说不存在")


@router.delete("/{novel_id}")
async def delete_novel(
    novel_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """删除小说"""
    # TODO: 实现小说删除
    raise HTTPException(status_code=404, detail="小说不存在")


# 章节相关
@router.get("/{novel_id}/chapters")
async def list_chapters(
    novel_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """获取章节列表"""
    # TODO: 实现章节列表查询
    return {"items": [], "novel_id": novel_id}


@router.post("/{novel_id}/chapters")
async def create_chapter(
    novel_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """创建章节"""
    # TODO: 实现章节创建
    return {"message": "创建章节功能待实现"}


# 剧本相关
@router.post("/{novel_id}/generate-script")
async def generate_script(
    novel_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """AI生成剧本"""
    # TODO: 实现AI剧本生成
    return {"message": "AI剧本生成功能待实现"}
