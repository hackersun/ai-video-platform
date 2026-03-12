"""
小说路由模块
"""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.schemas.novel import (
    NovelCreate,
    NovelUpdate,
    NovelResponse,
    NovelDetail,
    NovelListResponse,
    ChapterCreate,
    ChapterUpdate,
    ChapterResponse,
    ChapterListResponse,
    NovelGenerateRequest,
    GenerationStatus
)
from app.services.novel_service import novel_service, chapter_service

router = APIRouter(prefix="/novels", tags=["小说"])


# ==================== 小说CRUD ====================

@router.get("", response_model=NovelListResponse)
async def list_novels(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    genre: Optional[str] = Query(None),
    search: Optional[str] = Query(None, description="搜索标题或描述"),
    db: Session = Depends(get_db)
):
    """获取小说列表（公开）"""
    novels, total = novel_service.get_novels(
        db,
        skip=skip,
        limit=limit,
        status="published",  # 只显示已发布的
        genre=genre,
        search=search
    )
    
    return NovelListResponse(
        items=novels,
        total=total,
        page=skip // limit + 1,
        page_size=limit,
        pages=(total + limit - 1) // limit
    )


@router.get("/my", response_model=NovelListResponse)
async def list_my_novels(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, pattern="^(draft|published|archived)$"),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取我的小说列表"""
    novels, total = novel_service.get_novels(
        db,
        skip=skip,
        limit=limit,
        author_id=UUID(user_id),
        status=status
    )
    
    return NovelListResponse(
        items=novels,
        total=total,
        page=skip // limit + 1,
        page_size=limit,
        pages=(total + limit - 1) // limit
    )


@router.post("", response_model=NovelResponse, status_code=status.HTTP_201_CREATED)
async def create_novel(
    novel_data: NovelCreate,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """创建小说"""
    novel = novel_service.create_novel(db, novel_data, UUID(user_id))
    return novel


@router.get("/{novel_id}", response_model=NovelDetail)
async def get_novel(
    novel_id: UUID,
    db: Session = Depends(get_db)
):
    """获取小说详情"""
    novel = novel_service.get_novel_by_id(db, novel_id)
    if not novel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="小说不存在"
        )
    
    # 获取章节
    chapters, _ = chapter_service.get_chapters_by_novel(db, novel_id)
    
    return NovelDetail(
        id=novel.id,
        title=novel.title,
        description=novel.description,
        genre=novel.genre,
        cover_image=novel.cover_image,
        author_id=novel.author_id,
        status=novel.status,
        word_count=novel.word_count,
        ai_generated=novel.ai_generated,
        created_at=novel.created_at,
        updated_at=novel.updated_at,
        chapter_count=len(chapters),
        chapters=chapters
    )


@router.put("/{novel_id}", response_model=NovelResponse)
async def update_novel(
    novel_id: UUID,
    novel_data: NovelUpdate,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """更新小说"""
    novel = novel_service.update_novel(db, novel_id, novel_data, UUID(user_id))
    return novel


@router.delete("/{novel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_novel(
    novel_id: UUID,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """删除小说"""
    novel_service.delete_novel(db, novel_id, UUID(user_id))
    return None


@router.post("/{novel_id}/publish")
async def publish_novel(
    novel_id: UUID,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """发布小说"""
    novel = novel_service.update_novel(
        db, novel_id,
        NovelUpdate(status="published"),
        UUID(user_id)
    )
    return {"message": "小说已发布", "novel_id": str(novel.id)}


@router.post("/{novel_id}/archive")
async def archive_novel(
    novel_id: UUID,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """归档小说"""
    novel = novel_service.update_novel(
        db, novel_id,
        NovelUpdate(status="archived"),
        UUID(user_id)
    )
    return {"message": "小说已归档", "novel_id": str(novel.id)}


# ==================== 章节CRUD ====================

@router.get("/{novel_id}/chapters", response_model=ChapterListResponse)
async def list_chapters(
    novel_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """获取小说章节列表"""
    # 检查小说是否存在
    novel = novel_service.get_novel_by_id(db, novel_id)
    if not novel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="小说不存在"
        )
    
    chapters, total = chapter_service.get_chapters_by_novel(db, novel_id, skip, limit)
    
    return ChapterListResponse(
        items=chapters,
        total=total,
        page=skip // limit + 1,
        page_size=limit,
        pages=(total + limit - 1) // limit
    )


@router.post("/{novel_id}/chapters", response_model=ChapterResponse, status_code=status.HTTP_201_CREATED)
async def create_chapter(
    novel_id: UUID,
    chapter_data: ChapterCreate,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """创建章节"""
    # 检查权限
    novel = novel_service.get_novel_by_id(db, novel_id)
    if not novel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="小说不存在"
        )
    
    if str(novel.author_id) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权为此小说添加章节"
        )
    
    chapter = chapter_service.create_chapter(db, chapter_data, novel_id)
    return chapter


@router.get("/{novel_id}/chapters/{chapter_id}", response_model=ChapterResponse)
async def get_chapter(
    novel_id: UUID,
    chapter_id: UUID,
    db: Session = Depends(get_db)
):
    """获取章节详情"""
    chapter = chapter_service.get_chapter_by_id(db, chapter_id)
    if not chapter or chapter.novel_id != novel_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="章节不存在"
        )
    
    return chapter


@router.put("/{novel_id}/chapters/{chapter_id}", response_model=ChapterResponse)
async def update_chapter(
    novel_id: UUID,
    chapter_id: UUID,
    chapter_data: ChapterUpdate,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """更新章节"""
    chapter = chapter_service.update_chapter(db, chapter_id, chapter_data, UUID(user_id))
    return chapter


@router.delete("/{novel_id}/chapters/{chapter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chapter(
    novel_id: UUID,
    chapter_id: UUID,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """删除章节"""
    chapter_service.delete_chapter(db, chapter_id, UUID(user_id))
    return None


# ==================== AI生成相关 ====================

@router.post("/generate", response_model=GenerationStatus)
async def generate_novel(
    generate_data: NovelGenerateRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    AI生成小说
    
    提交生成任务，返回任务ID用于查询状态
    """
    # TODO: 实现AI生成逻辑
    # 1. 检查用户配额
    # 2. 提交Celery任务
    # 3. 返回任务ID
    
    return GenerationStatus(
        task_id="demo-task-id",
        status="pending",
        progress=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


@router.get("/generate/{task_id}", response_model=GenerationStatus)
async def get_generation_status(
    task_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """查询生成任务状态"""
    # TODO: 查询任务状态
    
    return GenerationStatus(
        task_id=task_id,
        status="processing",
        progress=50,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


from datetime import datetime
