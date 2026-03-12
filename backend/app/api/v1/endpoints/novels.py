"""
小说相关端点
"""

from typing import List
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
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
    # TODO: 实现小说列表查询
    return {
        "items": [],
        "total": 0,
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
