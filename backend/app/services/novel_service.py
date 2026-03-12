"""
小说服务层
"""

from typing import Optional, List, Tuple
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from fastapi import HTTPException, status

from app.models.novel import Novel, Chapter
from app.schemas.novel import NovelCreate, NovelUpdate, ChapterCreate, ChapterUpdate


class NovelService:
    """小说服务类"""
    
    @staticmethod
    def get_novel_by_id(db: Session, novel_id: UUID) -> Optional[Novel]:
        """根据ID获取小说"""
        return db.query(Novel).filter(Novel.id == novel_id).first()
    
    @staticmethod
    def get_novels(
        db: Session,
        skip: int = 0,
        limit: int = 20,
        author_id: Optional[UUID] = None,
        genre: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None
    ) -> Tuple[List[Novel], int]:
        """获取小说列表"""
        query = db.query(Novel)
        
        # 过滤条件
        if author_id:
            query = query.filter(Novel.author_id == author_id)
        if genre:
            query = query.filter(Novel.genre == genre)
        if status:
            query = query.filter(Novel.status == status)
        if search:
            query = query.filter(
                (Novel.title.ilike(f"%{search}%")) |
                (Novel.description.ilike(f"%{search}%"))
            )
        
        total = query.count()
        novels = query.order_by(desc(Novel.created_at)).offset(skip).limit(limit).all()
        
        return novels, total
    
    @staticmethod
    def create_novel(db: Session, novel_data: NovelCreate, author_id: UUID) -> Novel:
        """创建小说"""
        novel = Novel(
            title=novel_data.title,
            description=novel_data.description,
            genre=novel_data.genre,
            cover_image=novel_data.cover_image,
            author_id=author_id,
            status="draft",
            word_count=0
        )
        
        db.add(novel)
        db.commit()
        db.refresh(novel)
        
        return novel
    
    @staticmethod
    def update_novel(
        db: Session,
        novel_id: UUID,
        novel_data: NovelUpdate,
        author_id: UUID
    ) -> Novel:
        """更新小说"""
        novel = NovelService.get_novel_by_id(db, novel_id)
        if not novel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="小说不存在"
            )
        
        # 检查权限
        if novel.author_id != author_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权修改此小说"
            )
        
        # 更新字段
        update_data = novel_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(novel, field, value)
        
        db.commit()
        db.refresh(novel)
        
        return novel
    
    @staticmethod
    def delete_novel(db: Session, novel_id: UUID, author_id: UUID) -> bool:
        """删除小说"""
        novel = NovelService.get_novel_by_id(db, novel_id)
        if not novel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="小说不存在"
            )
        
        # 检查权限
        if novel.author_id != author_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权删除此小说"
            )
        
        db.delete(novel)
        db.commit()
        
        return True
    
    @staticmethod
    def update_word_count(db: Session, novel_id: UUID) -> int:
        """更新小说字数"""
        total_words = db.query(func.sum(Chapter.word_count)).filter(
            Chapter.novel_id == novel_id
        ).scalar() or 0
        
        novel = NovelService.get_novel_by_id(db, novel_id)
        if novel:
            novel.word_count = total_words
            db.commit()
        
        return total_words


class ChapterService:
    """章节服务类"""
    
    @staticmethod
    def get_chapter_by_id(db: Session, chapter_id: UUID) -> Optional[Chapter]:
        """根据ID获取章节"""
        return db.query(Chapter).filter(Chapter.id == chapter_id).first()
    
    @staticmethod
    def get_chapters_by_novel(
        db: Session,
        novel_id: UUID,
        skip: int = 0,
        limit: int = 50
    ) -> Tuple[List[Chapter], int]:
        """获取小说的章节列表"""
        query = db.query(Chapter).filter(Chapter.novel_id == novel_id)
        total = query.count()
        chapters = query.order_by(Chapter.chapter_number).offset(skip).limit(limit).all()
        
        return chapters, total
    
    @staticmethod
    def create_chapter(
        db: Session,
        chapter_data: ChapterCreate,
        novel_id: UUID
    ) -> Chapter:
        """创建章节"""
        # 检查小说是否存在
        novel = db.query(Novel).filter(Novel.id == novel_id).first()
        if not novel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="小说不存在"
            )
        
        # 计算字数
        word_count = len(chapter_data.content) if chapter_data.content else 0
        
        chapter = Chapter(
            novel_id=novel_id,
            title=chapter_data.title,
            content=chapter_data.content,
            chapter_number=chapter_data.chapter_number,
            status="draft",
            word_count=word_count
        )
        
        db.add(chapter)
        db.commit()
        db.refresh(chapter)
        
        # 更新小说字数
        NovelService.update_word_count(db, novel_id)
        
        return chapter
    
    @staticmethod
    def update_chapter(
        db: Session,
        chapter_id: UUID,
        chapter_data: ChapterUpdate,
        author_id: UUID
    ) -> Chapter:
        """更新章节"""
        chapter = ChapterService.get_chapter_by_id(db, chapter_id)
        if not chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="章节不存在"
            )
        
        # 检查权限
        if chapter.novel.author_id != author_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权修改此章节"
            )
        
        # 更新字段
        update_data = chapter_data.model_dump(exclude_unset=True)
        
        # 如果更新了内容，重新计算字数
        if "content" in update_data:
            update_data["word_count"] = len(update_data["content"]) if update_data["content"] else 0
        
        for field, value in update_data.items():
            setattr(chapter, field, value)
        
        db.commit()
        db.refresh(chapter)
        
        # 更新小说字数
        NovelService.update_word_count(db, chapter.novel_id)
        
        return chapter
    
    @staticmethod
    def delete_chapter(db: Session, chapter_id: UUID, author_id: UUID) -> bool:
        """删除章节"""
        chapter = ChapterService.get_chapter_by_id(db, chapter_id)
        if not chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="章节不存在"
            )
        
        # 检查权限
        if chapter.novel.author_id != author_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权删除此章节"
            )
        
        novel_id = chapter.novel_id
        
        db.delete(chapter)
        db.commit()
        
        # 更新小说字数
        NovelService.update_word_count(db, novel_id)
        
        return True


# 服务实例
novel_service = NovelService()
chapter_service = ChapterService()
