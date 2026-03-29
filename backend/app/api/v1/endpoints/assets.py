"""
资产库 API 端点
支持项目资产库 + 全局资产库双层复用
"""
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, desc, or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.asset import Asset, AssetCategory
from app.models.project import Project

router = APIRouter(tags=["资产库"])


# ========== 请求/响应模型 ==========

class AssetCreate(BaseModel):
    category: str = Field(..., description="资产类别")
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    asset_type: str = Field("image", description="类型: image/video/audio/text")
    url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    project_id: Optional[str] = Field(None, description="所属项目，NULL表示全局资产")
    tags: Optional[List[str]] = None
    style_tags: Optional[List[str]] = None
    prompt_template: Optional[str] = None
    variables: Optional[List[dict]] = None
    character_id: Optional[str] = None
    expressions: Optional[List[dict]] = None
    poses: Optional[List[dict]] = None


class AssetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    tags: Optional[List[str]] = None
    style_tags: Optional[List[str]] = None
    prompt_template: Optional[str] = None
    variables: Optional[List[dict]] = None
    expressions: Optional[List[dict]] = None
    poses: Optional[List[dict]] = None
    is_public: Optional[bool] = None


class AssetResponse(BaseModel):
    id: str
    user_id: str
    category: str
    name: str
    description: Optional[str] = None
    asset_type: Optional[str] = None
    url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    project_id: Optional[str] = None
    tags: Optional[List[str]] = None
    style_tags: Optional[List[str]] = None
    prompt_template: Optional[str] = None
    variables: Optional[List[dict]] = None
    character_id: Optional[str] = None
    expressions: Optional[List[dict]] = None
    poses: Optional[List[dict]] = None
    likes: int = 0
    usage_count: int = 0
    is_public: bool = False
    is_active: bool = True
    created_at: str
    updated_at: str


class AssetCategoryResponse(BaseModel):
    id: str
    name: str
    name_cn: Optional[str] = None
    icon: Optional[str] = None
    sort_order: int = 0
    asset_count: int = 0


def build_asset_response(asset: Asset) -> AssetResponse:
    return AssetResponse(
        id=str(asset.id),
        user_id=str(asset.user_id),
        category=asset.category,
        name=asset.name,
        description=asset.description,
        asset_type=asset.asset_type,
        url=asset.url,
        thumbnail_url=asset.thumbnail_url,
        project_id=str(asset.project_id) if asset.project_id else None,
        tags=asset.tags,
        style_tags=asset.style_tags,
        prompt_template=asset.prompt_template,
        variables=asset.variables,
        character_id=str(asset.character_id) if asset.character_id else None,
        expressions=asset.expressions,
        poses=asset.poses,
        likes=asset.likes or 0,
        usage_count=asset.usage_count or 0,
        is_public=asset.is_public or False,
        is_active=asset.is_active if asset.is_active is not None else True,
        created_at=str(asset.created_at),
        updated_at=str(asset.updated_at),
    )


# ========== API 端点 ==========

@router.get("/categories", response_model=List[AssetCategoryResponse])
async def list_categories(
    db: AsyncSession = Depends(get_db),
):
    """获取所有资产分类"""
    result = await db.execute(select(AssetCategory).order_by(AssetCategory.sort_order))
    categories = result.scalars().all()

    responses = []
    for cat in categories:
        # 统计该分类的资产数量
        count_result = await db.execute(
            select(func.count(Asset.id)).where(
                and_(Asset.category == cat.name, Asset.is_active == True)
            )
        )
        count = count_result.scalar() or 0

        responses.append(AssetCategoryResponse(
            id=str(cat.id),
            name=cat.name,
            name_cn=cat.name_cn,
            icon=cat.icon,
            sort_order=cat.sort_order or 0,
            asset_count=count,
        ))
    return responses


@router.get("", response_model=List[AssetResponse])
async def list_assets(
    category: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None, description="项目ID，NULL查全局资产"),
    tags: Optional[str] = Query(None, description="标签，逗号分隔"),
    search: Optional[str] = Query(None, description="搜索名称/描述"),
    include_public: bool = Query(True, description="是否包含公开资产"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取资产列表"""
    conditions = [Asset.is_active == True]

    if category:
        conditions.append(Asset.category == category)

    if project_id:
        conditions.append(Asset.project_id == project_id)
    else:
        # 不指定 project_id 时，只查全局和用户自己的
        conditions.append(
            or_(Asset.project_id.is_(None), Asset.user_id == user_id)
        )

    if include_public:
        conditions.append(or_(Asset.is_public == True, Asset.user_id == user_id))
    else:
        conditions.append(Asset.user_id == user_id)

    if search:
        conditions.append(
            or_(Asset.name.ilike(f"%{search}%"), Asset.description.ilike(f"%{search}%"))
        )

    result = await db.execute(
        select(Asset)
        .where(*conditions)
        .order_by(desc(Asset.usage_count), desc(Asset.created_at))
        .offset(offset)
        .limit(limit)
    )
    assets = result.scalars().all()
    return [build_asset_response(a) for a in assets]


@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取单个资产"""
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")

    # 检查访问权限
    if not asset.is_public and asset.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权访问此资产")

    return build_asset_response(asset)


@router.post("", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
async def create_asset(
    request: AssetCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """创建资产"""
    # 如果指定了 project_id，验证项目归属
    if request.project_id:
        proj_result = await db.execute(
            select(Project).where(
                and_(Project.id == request.project_id, Project.user_id == user_id)
            )
        )
        if not proj_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="项目不存在")

    asset = Asset(
        id=str(uuid4()),
        user_id=user_id,
        category=request.category,
        name=request.name,
        description=request.description,
        asset_type=request.asset_type or "image",
        url=request.url,
        thumbnail_url=request.thumbnail_url,
        project_id=request.project_id,
        tags=request.tags or [],
        style_tags=request.style_tags or [],
        prompt_template=request.prompt_template,
        variables=request.variables,
        character_id=request.character_id,
        expressions=request.expressions,
        poses=request.poses,
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return build_asset_response(asset)


@router.put("/{asset_id}", response_model=AssetResponse)
async def update_asset(
    asset_id: str,
    request: AssetUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """更新资产"""
    result = await db.execute(
        select(Asset).where(and_(Asset.id == asset_id, Asset.user_id == user_id))
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")

    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(asset, key, value)
    asset.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(asset)
    return build_asset_response(asset)


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """删除资产（软删除）"""
    result = await db.execute(
        select(Asset).where(and_(Asset.id == asset_id, Asset.user_id == user_id))
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")

    asset.is_active = False
    asset.updated_at = datetime.utcnow()
    await db.commit()


@router.post("/{asset_id}/like")
async def like_asset(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """点赞资产"""
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")

    asset.likes = (asset.likes or 0) + 1
    await db.commit()
    return {"likes": asset.likes}


@router.post("/{asset_id}/use")
async def use_asset(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """记录资产使用（使用后 usage_count++）"""
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")

    asset.usage_count = (asset.usage_count or 0) + 1
    await db.commit()
    return {"usage_count": asset.usage_count}
