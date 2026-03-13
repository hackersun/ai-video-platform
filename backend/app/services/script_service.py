"""
Script service layer (async)
"""

from typing import Optional, List, Tuple
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, delete
from sqlalchemy.orm import selectinload

from app.models.novel import Script, Scene
from app.schemas.script import ScriptCreate, ScriptUpdate, SceneCreate, SceneUpdate


class ScriptService:
    """Script service class"""

    @staticmethod
    async def get_script_by_id(db: AsyncSession, script_id: UUID) -> Optional[Script]:
        """Get script by ID"""
        result = await db.execute(select(Script).where(Script.id == script_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_scripts(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 20,
        novel_id: Optional[UUID] = None,
        chapter_id: Optional[UUID] = None,
        status_filter: Optional[str] = None,
    ) -> Tuple[List[Script], int]:
        """Get script list"""
        query = select(Script)
        count_query = select(func.count()).select_from(Script)

        if novel_id:
            query = query.where(Script.novel_id == novel_id)
            count_query = count_query.where(Script.novel_id == novel_id)
        if chapter_id:
            query = query.where(Script.chapter_id == chapter_id)
            count_query = count_query.where(Script.chapter_id == chapter_id)
        if status_filter:
            query = query.where(Script.status == status_filter)
            count_query = count_query.where(Script.status == status_filter)

        result = await db.execute(
            query.order_by(desc(Script.created_at)).offset(skip).limit(limit)
        )
        scripts = result.scalars().all()

        total_result = await db.execute(count_query)
        total = total_result.scalar()

        return list(scripts), total

    @staticmethod
    async def create_script(db: AsyncSession, script_data: ScriptCreate) -> Script:
        """Create script"""
        script = Script(
            novel_id=script_data.novel_id,
            chapter_id=script_data.chapter_id,
            title=script_data.title,
            content=script_data.content,
            format=script_data.format,
            status="draft",
            ai_generated=False,
        )

        db.add(script)
        await db.commit()
        await db.refresh(script)

        return script

    @staticmethod
    async def update_script(
        db: AsyncSession, script_id: UUID, script_data: ScriptUpdate
    ) -> Script:
        """Update script"""
        script = await ScriptService.get_script_by_id(db, script_id)
        if not script:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Script not found")

        update_data = script_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(script, field, value)

        await db.commit()
        await db.refresh(script)

        return script

    @staticmethod
    async def delete_script(db: AsyncSession, script_id: UUID) -> bool:
        """Delete script"""
        script = await ScriptService.get_script_by_id(db, script_id)
        if not script:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Script not found")

        await db.delete(script)
        await db.commit()

        return True


class SceneService:
    """Scene service class"""

    @staticmethod
    async def get_scene_by_id(db: AsyncSession, scene_id: UUID) -> Optional[Scene]:
        """Get scene by ID"""
        result = await db.execute(select(Scene).where(Scene.id == scene_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_scenes_by_script(
        db: AsyncSession, script_id: UUID, skip: int = 0, limit: int = 50
    ) -> Tuple[List[Scene], int]:
        """Get scenes for a script"""
        query = select(Scene).where(Scene.script_id == script_id)
        count_query = (
            select(func.count()).select_from(Scene).where(Scene.script_id == script_id)
        )

        result = await db.execute(
            query.order_by(Scene.scene_number).offset(skip).limit(limit)
        )
        scenes = result.scalars().all()

        total_result = await db.execute(count_query)
        total = total_result.scalar()

        return list(scenes), total

    @staticmethod
    async def create_scene(
        db: AsyncSession, script_id: UUID, scene_data: SceneCreate
    ) -> Scene:
        """Create scene"""
        result = await db.execute(select(Script).where(Script.id == script_id))
        script = result.scalar_one_or_none()
        if not script:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Script not found")

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
            dialogue=scene_data.dialogue,
        )

        db.add(scene)
        await db.commit()
        await db.refresh(scene)

        return scene

    @staticmethod
    async def update_scene(
        db: AsyncSession, scene_id: UUID, scene_data: SceneUpdate
    ) -> Scene:
        """Update scene"""
        scene = await SceneService.get_scene_by_id(db, scene_id)
        if not scene:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Scene not found")

        update_data = scene_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(scene, field, value)

        await db.commit()
        await db.refresh(scene)

        return scene

    @staticmethod
    async def delete_scene(db: AsyncSession, scene_id: UUID) -> bool:
        """Delete scene"""
        scene = await SceneService.get_scene_by_id(db, scene_id)
        if not scene:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Scene not found")

        await db.delete(scene)
        await db.commit()

        return True


script_service = ScriptService()
scene_service = SceneService()
