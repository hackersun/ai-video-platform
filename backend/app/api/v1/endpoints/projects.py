"""
项目(Project)管理 API 端点
"""
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.project import Project, ProjectMember
from app.models.asset import AssetCategory, DEFAULT_CATEGORIES

router = APIRouter(tags=["项目管理"])


# ========== 请求/响应模型 ==========

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    global_style: Optional[str] = Field(None, description="全局风格: anime, realistic, manga")
    global_seed: Optional[str] = Field(None, description="全局一致性种子词")
    global_negative_prompt: Optional[str] = Field(None, description="全局负面提示词")
    character_consistency_mode: Optional[str] = Field("seed", description="一致性模式: seed/reference/ipadapter")
    aspect_ratio: Optional[str] = Field("16:9", description="画幅: 16:9, 9:16, 1:1")
    default_fps: Optional[int] = Field(24, ge=1, le=120)
    default_resolution: Optional[str] = Field("1080p", description="分辨率: 720p, 1080p, 4k")
    tags: Optional[List[str]] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    cover_url: Optional[str] = None
    global_style: Optional[str] = None
    global_seed: Optional[str] = None
    global_negative_prompt: Optional[str] = None
    character_consistency_mode: Optional[str] = None
    default_character_refs: Optional[list] = None
    aspect_ratio: Optional[str] = None
    default_fps: Optional[int] = None
    default_resolution: Optional[str] = None
    default_duration: Optional[int] = None
    status: Optional[str] = None
    tags: Optional[list] = None


class ProjectResponse(BaseModel):
    id: str
    user_id: str
    name: str
    description: Optional[str] = None
    cover_url: Optional[str] = None
    global_style: Optional[str] = None
    global_seed: Optional[str] = None
    global_negative_prompt: Optional[str] = None
    character_consistency_mode: Optional[str] = None
    default_character_refs: Optional[list] = None
    aspect_ratio: Optional[str] = None
    default_fps: Optional[int] = None
    default_resolution: Optional[str] = None
    default_duration: Optional[int] = None
    status: str
    is_public: bool
    novel_count: int = 0
    storyboard_count: int = 0
    timeline_count: int = 0
    shot_count: int = 0
    video_count: int = 0
    tags: Optional[list] = None
    created_at: str
    updated_at: str


class ProjectMemberResponse(BaseModel):
    id: str
    project_id: str
    user_id: str
    role: str
    is_active: bool
    joined_at: Optional[str] = None


# ========== 辅助函数 ==========

def build_project_response(project: Project) -> ProjectResponse:
    return ProjectResponse(
        id=str(project.id),
        user_id=str(project.user_id),
        name=project.name,
        description=project.description,
        cover_url=project.cover_url,
        global_style=project.global_style,
        global_seed=project.global_seed,
        global_negative_prompt=project.global_negative_prompt,
        character_consistency_mode=project.character_consistency_mode,
        default_character_refs=project.default_character_refs,
        aspect_ratio=project.aspect_ratio,
        default_fps=project.default_fps,
        default_resolution=project.default_resolution,
        default_duration=project.default_duration,
        status=project.status or "active",
        is_public=project.is_public or False,
        novel_count=project.novel_count or 0,
        storyboard_count=project.storyboard_count or 0,
        timeline_count=project.timeline_count or 0,
        shot_count=project.shot_count or 0,
        video_count=project.video_count or 0,
        tags=project.tags,
        created_at=str(project.created_at),
        updated_at=str(project.updated_at),
    )


async def ensure_default_categories(db: AsyncSession):
    """确保预置资产分类存在"""
    for cat_data in DEFAULT_CATEGORIES:
        result = await db.execute(
            select(AssetCategory).where(AssetCategory.name == cat_data["name"])
        )
        existing = result.scalar_one_or_none()
        if not existing:
            category = AssetCategory(
                id=str(uuid4()),
                name=cat_data["name"],
                name_cn=cat_data["name_cn"],
                icon=cat_data["icon"],
                sort_order=cat_data["sort_order"],
                is_system=True,
            )
            db.add(category)
    await db.commit()


# ========== API 端点 ==========

@router.get("", response_model=List[ProjectResponse])
async def list_projects(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取用户的所有项目"""
    query = select(Project).where(Project.user_id == user_id)
    if status:
        query = query.where(Project.status == status)
    query = query.order_by(desc(Project.updated_at)).offset(offset).limit(limit)

    result = await db.execute(query)
    projects = result.scalars().all()
    return [build_project_response(p) for p in projects]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取单个项目详情"""
    result = await db.execute(
        select(Project).where(
            and_(Project.id == project_id,
                 Project.user_id == user_id)))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return build_project_response(project)


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    request: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """创建新项目"""
    await ensure_default_categories(db)

    project = Project(
        id=str(uuid4()),
        user_id=user_id,
        name=request.name,
        description=request.description,
        global_style=request.global_style,
        global_seed=request.global_seed,
        global_negative_prompt=request.global_negative_prompt,
        character_consistency_mode=request.character_consistency_mode or "seed",
        aspect_ratio=request.aspect_ratio or "16:9",
        default_fps=request.default_fps or 24,
        default_resolution=request.default_resolution or "1080p",
        default_duration=5,
        status="active",
        tags=request.tags or [],
    )
    db.add(project)

    # 创建者自动成为 owner
    member = ProjectMember(
        id=str(uuid4()),
        project_id=project.id,
        user_id=user_id,
        role="owner",
        joined_at=datetime.utcnow(),
    )
    db.add(member)

    await db.commit()
    await db.refresh(project)
    return build_project_response(project)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    request: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """更新项目"""
    result = await db.execute(
        select(Project).where(
            and_(Project.id == project_id,
                 Project.user_id == user_id)))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(project, key, value)
    project.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(project)
    return build_project_response(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """删除项目（软删除，改为 archived）"""
    result = await db.execute(
        select(Project).where(
            and_(Project.id == project_id,
                 Project.user_id == user_id)))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    project.status = "archived"
    project.updated_at = datetime.utcnow()
    await db.commit()


@router.get("/{project_id}/members", response_model=List[ProjectMemberResponse])
async def list_project_members(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取项目成员"""
    result = await db.execute(
        select(Project).where(
            and_(Project.id == project_id,
                 Project.user_id == user_id)))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    member_result = await db.execute(
        select(ProjectMember).where(
            and_(ProjectMember.project_id == project_id,
                 ProjectMember.is_active == True))
    )
    members = member_result.scalars().all()
    return [
        ProjectMemberResponse(
            id=str(m.id),
            project_id=str(m.project_id),
            user_id=str(m.user_id),
            role=m.role,
            is_active=m.is_active,
            joined_at=str(m.joined_at) if m.joined_at else None,
        )
        for m in members
    ]


@router.get("/stats/summary")
async def get_project_stats(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取项目统计"""
    result = await db.execute(
        select(Project).where(
            and_(Project.user_id == user_id,
                 Project.status != "archived"))
    )
    projects = result.scalars().all()
    return {
        "total": len(projects),
        "active": sum(1 for p in projects if p.status == "active"),
        "completed": sum(1 for p in projects if p.status == "completed"),
        "paused": sum(1 for p in projects if p.status == "paused"),
    }
