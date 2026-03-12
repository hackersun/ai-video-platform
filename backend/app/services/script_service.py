"""
剧本服务层
"""

from typing import Optional, List, Tuple, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import desc
from fastapi import HTTPException, status

from app.models.novel import Script, Scene
from app.schemas.script import ScriptCreate, ScriptUpdate, SceneCreate, SceneUpdate


class ScriptService:
    """剧本服务类"""
    
    @staticmethod
    def get_script_by_id(db: Session, script_id: UUID) -> Optional[Script]:
        """根据ID获取剧本"""
        return db.query(Script).filter(Script.id == script_id).first()
    
    @staticmethod
    def get_scripts(
        db: Session,
        skip: int = 0,
        limit: int = 20,
        novel_id: Optional[UUID] = None,
        chapter_id: Optional[UUID] = None,
        status: Optional[str] = None
    ) -> Tuple[List[Script], int]:
        """获取剧本列表"""
        query = db.query(Script)
        
        if novel_id:
            query = query.filter(Script.novel_id == novel_id)
        if chapter_id:
            query = query.filter(Script.chapter_id == chapter_id)
        if status:
            query = query.filter(Script.status == status)
        
        total = query.count()
        scripts = query.order_by(desc(Script.created_at)).offset(skip).limit(limit).all()
        
        return scripts, total
    
    @staticmethod
    def create_script(db: Session, script_data: ScriptCreate) -> Script:
        """创建剧本"""
        script = Script(
            novel_id=script_data.novel_id,
            chapter_id=script_data.chapter_id,
            title=script_data.title,
            content=script_data.content,
            format=script_data.format,
            status="draft",
            ai_generated=False
        )
        
        db.add(script)
        db.commit()
        db.refresh(script)
        
        return script
    
    @staticmethod
    def update_script(
        db: Session,
        script_id: UUID,
        script_data: ScriptUpdate
    ) -> Script:
        """更新剧本"""
        script = ScriptService.get_script_by_id(db, script_id)
        if not script:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="剧本不存在"
            )
        
        update_data = script_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(script, field, value)
        
        db.commit()
        db.refresh(script)
        
        return script
    
    @staticmethod
    def delete_script(db: Session, script_id: UUID) -> bool:
        """删除剧本"""
        script = ScriptService.get_script_by_id(db, script_id)
        if not script:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="剧本不存在"
            )
        
        db.delete(script)
        db.commit()
        
        return True
    
    @staticmethod
    def generate_script_from_chapter(
        db: Session,
        chapter_id: UUID,
        style: str = "standard",
        scene_count: int = 5
    ) -> Script:
        """
        从章节生成剧本
        
        TODO: 集成AI服务生成剧本
        """
        from app.models.novel import Chapter
        
        chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
        if not chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="章节不存在"
            )
        
        # 创建剧本
        script = Script(
            novel_id=chapter.novel_id,
            chapter_id=chapter_id,
            title=f"{chapter.title} - 剧本",
            content={
                "source": "ai_generated",
                "style": style,
                "chapter_content": chapter.content[:1000] if chapter.content else ""
            },
            format="standard",
            status="generating",
            ai_generated=True
        )
        
        db.add(script)
        db.commit()
        db.refresh(script)
        
        # TODO: 提交Celery任务进行AI生成
        
        return script


class SceneService:
    """场景服务类"""
    
    @staticmethod
    def get_scene_by_id(db: Session, scene_id: UUID) -> Optional[Scene]:
        """根据ID获取场景"""
        return db.query(Scene).filter(Scene.id == scene_id).first()
    
    @staticmethod
    def get_scenes_by_script(
        db: Session,
        script_id: UUID,
        skip: int = 0,
        limit: int = 50
    ) -> Tuple[List[Scene], int]:
        """获取剧本的场景列表"""
        query = db.query(Scene).filter(Scene.script_id == script_id)
        total = query.count()
        scenes = query.order_by(Scene.scene_number).offset(skip).limit(limit).all()
        
        return scenes, total
    
    @staticmethod
    def create_scene(
        db: Session,
        scene_data: SceneCreate,
        script_id: UUID
    ) -> Scene:
        """创建场景"""
        # 检查剧本是否存在
        script = db.query(Script).filter(Script.id == script_id).first()
        if not script:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="剧本不存在"
            )
        
        scene = Scene(
            script_id=script_id,
            scene_number=scene_data.scene_number,
            title=scene_data.title,
            description=scene_data.description,
            location=scene_data.location,
            time_of_day=scene_data.time_of_day,
            characters=scene_data.characters,
            props=scene_data.props,
            action_description=scene_data.action_description,
            camera_direction=scene_data.camera_direction,
            dialogue=scene_data.dialogue
        )
        
        db.add(scene)
        db.commit()
        db.refresh(scene)
        
        return scene
    
    @staticmethod
    def update_scene(
        db: Session,
        scene_id: UUID,
        scene_data: SceneUpdate
    ) -> Scene:
        """更新场景"""
        scene = SceneService.get_scene_by_id(db, scene_id)
        if not scene:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="场景不存在"
            )
        
        update_data = scene_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(scene, field, value)
        
        db.commit()
        db.refresh(scene)
        
        return scene
    
    @staticmethod
    def delete_scene(db: Session, scene_id: UUID) -> bool:
        """删除场景"""
        scene = SceneService.get_scene_by_id(db, scene_id)
        if not scene:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="场景不存在"
            )
        
        db.delete(scene)
        db.commit()
        
        return True
    
    @staticmethod
    def batch_create_scenes(
        db: Session,
        script_id: UUID,
        scenes_data: List[SceneCreate]
    ) -> List[Scene]:
        """批量创建场景"""
        scenes = []
        for scene_data in scenes_data:
            scene = Scene(
                script_id=script_id,
                scene_number=scene_data.scene_number,
                title=scene_data.title,
                description=scene_data.description,
                location=scene_data.location,
                time_of_day=scene_data.time_of_day,
                characters=scene_data.characters,
                props=scene_data.props,
                action_description=scene_data.action_description,
                camera_direction=scene_data.camera_direction,
                dialogue=scene_data.dialogue
            )
            scenes.append(scene)
        
        db.add_all(scenes)
        db.commit()
        
        for scene in scenes:
            db.refresh(scene)
        
        return scenes
    
    @staticmethod
    def reorder_scenes(db: Session, script_id: UUID, scene_order: List[UUID]):
        """重新排序场景"""
        for index, scene_id in enumerate(scene_order, start=1):
            scene = db.query(Scene).filter(
                Scene.id == scene_id,
                Scene.script_id == script_id
            ).first()
            
            if scene:
                scene.scene_number = index
        
        db.commit()


# 服务实例
script_service = ScriptService()
scene_service = SceneService()
