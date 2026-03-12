"""
剧本路由模块
"""

from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.schemas.script import (
    ScriptCreate,
    ScriptUpdate,
    ScriptResponse,
    ScriptDetail,
    ScriptListResponse,
    SceneCreate,
    SceneUpdate,
    SceneResponse,
    SceneListResponse,
    ScriptGenerateRequest,
    SceneGenerateRequest,
    VideoGenerateRequest,
    GenerationResult
)
from app.services.script_service import script_service, scene_service
from app.services.novel_service import novel_service

router = APIRouter(prefix="/scripts", tags=["剧本"])


# ==================== 剧本CRUD ====================

@router.get("", response_model=ScriptListResponse)
async def list_scripts(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    novel_id: Optional[UUID] = Query(None),
    chapter_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None, pattern="^(draft|published|generating)$"),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取剧本列表"""
    # 如果指定了novel_id，检查权限
    if novel_id:
        novel = novel_service.get_novel_by_id(db, novel_id)
        if not novel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="小说不存在"
            )
        # 只能查看自己的剧本或已发布的
        if str(novel.author_id) != user_id:
            # 只显示已发布的
            status = "published"
    
    scripts, total = script_service.get_scripts(
        db,
        skip=skip,
        limit=limit,
        novel_id=novel_id,
        chapter_id=chapter_id,
        status=status
    )
    
    return ScriptListResponse(
        items=scripts,
        total=total,
        page=skip // limit + 1,
        page_size=limit,
        pages=(total + limit - 1) // limit
    )


@router.post("", response_model=ScriptResponse, status_code=status.HTTP_201_CREATED)
async def create_script(
    script_data: ScriptCreate,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """创建剧本"""
    # 检查权限
    if script_data.novel_id:
        novel = novel_service.get_novel_by_id(db, script_data.novel_id)
        if not novel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="小说不存在"
            )
        if str(novel.author_id) != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权为此小说创建剧本"
            )
    
    script = script_service.create_script(db, script_data)
    return script


@router.get("/{script_id}", response_model=ScriptDetail)
async def get_script(
    script_id: UUID,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取剧本详情"""
    script = script_service.get_script_by_id(db, script_id)
    if not script:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="剧本不存在"
        )
    
    # 检查权限
    if script.novel and str(script.novel.author_id) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权查看此剧本"
        )
    
    # 获取场景
    scenes, _ = scene_service.get_scenes_by_script(db, script_id)
    
    return ScriptDetail(
        id=script.id,
        novel_id=script.novel_id,
        chapter_id=script.chapter_id,
        title=script.title,
        format=script.format,
        status=script.status,
        ai_generated=script.ai_generated,
        created_at=script.created_at,
        updated_at=script.updated_at,
        content=script.content,
        scenes=scenes
    )


@router.put("/{script_id}", response_model=ScriptResponse)
async def update_script(
    script_id: UUID,
    script_data: ScriptUpdate,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """更新剧本"""
    script = script_service.get_script_by_id(db, script_id)
    if not script:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="剧本不存在"
        )
    
    # 检查权限
    if script.novel and str(script.novel.author_id) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权修改此剧本"
        )
    
    script = script_service.update_script(db, script_id, script_data)
    return script


@router.delete("/{script_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_script(
    script_id: UUID,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """删除剧本"""
    script = script_service.get_script_by_id(db, script_id)
    if not script:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="剧本不存在"
        )
    
    # 检查权限
    if script.novel and str(script.novel.author_id) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除此剧本"
        )
    
    script_service.delete_script(db, script_id)
    return None


# ==================== 场景CRUD ====================

@router.get("/{script_id}/scenes", response_model=SceneListResponse)
async def list_scenes(
    script_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """获取剧本场景列表"""
    # 检查剧本是否存在
    script = script_service.get_script_by_id(db, script_id)
    if not script:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="剧本不存在"
        )
    
    scenes, total = scene_service.get_scenes_by_script(db, script_id, skip, limit)
    
    return SceneListResponse(
        items=scenes,
        total=total,
        page=skip // limit + 1,
        page_size=limit,
        pages=(total + limit - 1) // limit
    )


@router.post("/{script_id}/scenes", response_model=SceneResponse, status_code=status.HTTP_201_CREATED)
async def create_scene(
    script_id: UUID,
    scene_data: SceneCreate,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """创建场景"""
    # 检查权限
    script = script_service.get_script_by_id(db, script_id)
    if not script:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="剧本不存在"
        )
    
    if script.novel and str(script.novel.author_id) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权为此剧本添加场景"
        )
    
    scene = scene_service.create_scene(db, scene_data, script_id)
    return scene


@router.get("/{script_id}/scenes/{scene_id}", response_model=SceneResponse)
async def get_scene(
    script_id: UUID,
    scene_id: UUID,
    db: Session = Depends(get_db)
):
    """获取场景详情"""
    scene = scene_service.get_scene_by_id(db, scene_id)
    if not scene or str(scene.script_id) != str(script_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="场景不存在"
        )
    
    return scene


@router.put("/{script_id}/scenes/{scene_id}", response_model=SceneResponse)
async def update_scene(
    script_id: UUID,
    scene_id: UUID,
    scene_data: SceneUpdate,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """更新场景"""
    # 检查权限
    script = script_service.get_script_by_id(db, script_id)
    if not script:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="剧本不存在"
        )
    
    if script.novel and str(script.novel.author_id) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权修改此场景"
        )
    
    scene = scene_service.update_scene(db, scene_id, scene_data)
    return scene


@router.delete("/{script_id}/scenes/{scene_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scene(
    script_id: UUID,
    scene_id: UUID,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """删除场景"""
    # 检查权限
    script = script_service.get_script_by_id(db, script_id)
    if not script:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="剧本不存在"
        )
    
    if script.novel and str(script.novel.author_id) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除此场景"
        )
    
    scene_service.delete_scene(db, scene_id)
    return None


@router.post("/{script_id}/scenes/reorder")
async def reorder_scenes(
    script_id: UUID,
    scene_order: List[UUID],
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """重新排序场景"""
    # 检查权限
    script = script_service.get_script_by_id(db, script_id)
    if not script:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="剧本不存在"
        )
    
    if script.novel and str(script.novel.author_id) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权修改此剧本"
        )
    
    scene_service.reorder_scenes(db, script_id, scene_order)
    
    return {"message": "场景顺序已更新"}


# ==================== AI生成相关 ====================

@router.post("/generate", response_model=GenerationResult)
async def generate_script(
    generate_data: ScriptGenerateRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    从章节生成剧本
    
    提交生成任务，返回任务ID
    """
    # 检查权限
    novel = novel_service.get_novel_by_id(db, generate_data.novel_id)
    if not novel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="小说不存在"
        )
    
    if str(novel.author_id) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权为此小说生成剧本"
        )
    
    # TODO: 提交Celery任务进行AI生成
    # script = script_service.generate_script_from_chapter(
    #     db,
    #     chapter_id=generate_data.chapter_id,
    #     style=generate_data.style,
    #     scene_count=generate_data.scene_count
    # )
    
    from datetime import datetime
    return GenerationResult(
        task_id="script-gen-demo",
        status="pending",
        progress=0,
        created_at=datetime.utcnow()
    )


@router.post("/scenes/{scene_id}/generate-video", response_model=GenerationResult)
async def generate_scene_video(
    scene_id: UUID,
    video_request: VideoGenerateRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """生成场景视频"""
    scene = scene_service.get_scene_by_id(db, scene_id)
    if not scene:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="场景不存在"
        )
    
    # 检查权限
    if scene.script.novel and str(scene.script.novel.author_id) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权为此场景生成视频"
        )
    
    # TODO: 提交视频生成任务
    
    from datetime import datetime
    return GenerationResult(
        task_id=f"video-gen-{scene_id}",
        status="pending",
        progress=0,
        created_at=datetime.utcnow()
    )


@router.get("/generate/{task_id}", response_model=GenerationResult)
async def get_generation_status(
    task_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """查询生成任务状态"""
    # TODO: 查询任务状态
    
    from datetime import datetime
    return GenerationResult(
        task_id=task_id,
        status="processing",
        progress=50,
        created_at=datetime.utcnow()
    )
