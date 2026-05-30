"""
资产库 API 端点
支持项目资产库 + 全局资产库双层复用
"""
from app.core.time_utils import utc_now
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
from app.models import Chapter, Novel, Script, StoryEntity
from app.models.character import Character
from app.services.default_anime_library import ensure_default_anime_assets
from app.services.asset_generation_service import AssetGenerationService
from app.services.volcano_service import VolcanoService
from app.core.volcano_config import DEFAULT_IMAGE_MODEL

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
    novel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    script_id: Optional[str] = None
    entity_id: Optional[str] = None
    tags: Optional[List[str]] = None
    style_tags: Optional[List[str]] = None
    prompt_template: Optional[str] = None
    variables: Optional[List[dict]] = None
    shot_template: Optional[dict] = None
    character_id: Optional[str] = None
    expressions: Optional[List[dict]] = None
    poses: Optional[List[dict]] = None
    is_public: bool = False


class AssetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    project_id: Optional[str] = None
    novel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    script_id: Optional[str] = None
    entity_id: Optional[str] = None
    tags: Optional[List[str]] = None
    style_tags: Optional[List[str]] = None
    prompt_template: Optional[str] = None
    variables: Optional[List[dict]] = None
    shot_template: Optional[dict] = None
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
    novel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    script_id: Optional[str] = None
    entity_id: Optional[str] = None
    entity_type: Optional[str] = None
    tags: Optional[List[str]] = None
    style_tags: Optional[List[str]] = None
    prompt_template: Optional[str] = None
    variables: Optional[List[dict]] = None
    shot_template: Optional[dict] = None
    character_id: Optional[str] = None
    expressions: Optional[List[dict]] = None
    poses: Optional[List[dict]] = None
    likes: int = 0
    usage_count: int = 0
    is_public: bool = False
    is_active: bool = True
    version: int = 1
    is_locked: bool = False
    is_final: bool = False
    locked_at: Optional[str] = None
    locked_by: Optional[str] = None
    created_at: str
    updated_at: str


class AssetScopeUpdate(BaseModel):
    scope: str = Field(..., description="global/novel/chapter/script/entity/project")
    project_id: Optional[str] = None
    novel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    script_id: Optional[str] = None
    entity_id: Optional[str] = None


class AssetCategoryResponse(BaseModel):
    id: str
    name: str
    name_cn: Optional[str] = None
    icon: Optional[str] = None
    sort_order: int = 0
    asset_count: int = 0


# ========== 资产生成请求/响应模型 ==========

class CharacterAssetGenerateRequest(BaseModel):
    character_id: str
    style: str = Field("anime", description="生成风格: anime/realistic/cartoon")
    model_config_id: Optional[str] = None


class SceneAssetGenerateRequest(BaseModel):
    scene_id: str
    scene_name: str
    scene_description: str
    style: str = Field("anime", description="生成风格: anime/realistic/cartoon")
    model_config_id: Optional[str] = None


class PropAssetGenerateRequest(BaseModel):
    prop_id: str
    prop_name: str
    prop_description: str
    style: str = Field("anime", description="生成风格: anime/realistic/cartoon")
    model_config_id: Optional[str] = None


class AssetGenerateResponse(BaseModel):
    asset_id: str
    name: str
    url: str
    is_locked: bool = False
    is_final: bool = False


class CharacterAssetsResponse(BaseModel):
    character_id: str
    assets: Dict[str, AssetGenerateResponse]
    total: int


class SceneAssetsResponse(BaseModel):
    scene_id: str
    assets: Dict[str, AssetGenerateResponse]
    total: int


class PropAssetsResponse(BaseModel):
    prop_id: str
    assets: Dict[str, AssetGenerateResponse]
    total: int


class EntityAssetsResponse(BaseModel):
    entity_type: str
    entity_id: str
    assets: List[AssetResponse]
    locked_assets: List[AssetResponse]
    total: int


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
        novel_id=str(asset.novel_id) if asset.novel_id else None,
        chapter_id=str(asset.chapter_id) if asset.chapter_id else None,
        script_id=str(asset.script_id) if asset.script_id else None,
        entity_id=str(asset.entity_id) if asset.entity_id else None,
        entity_type=getattr(asset, 'entity_type', None),
        tags=asset.tags,
        style_tags=asset.style_tags,
        prompt_template=asset.prompt_template,
        variables=asset.variables,
        shot_template=asset.shot_template,
        character_id=str(asset.character_id) if asset.character_id else None,
        expressions=asset.expressions,
        poses=asset.poses,
        likes=asset.likes or 0,
        usage_count=asset.usage_count or 0,
        is_public=asset.is_public or False,
        is_active=asset.is_active if asset.is_active is not None else True,
        version=getattr(asset, 'version', 1) or 1,
        is_locked=getattr(asset, 'is_locked', False) or False,
        is_final=getattr(asset, 'is_final', False) or False,
        locked_at=str(asset.locked_at) if getattr(asset, 'locked_at', None) else None,
        locked_by=getattr(asset, 'locked_by', None),
        created_at=str(asset.created_at),
        updated_at=str(asset.updated_at),
    )


async def validate_asset_scope(
    db: AsyncSession,
    user_id: str,
    *,
    project_id: Optional[str] = None,
    novel_id: Optional[str] = None,
    chapter_id: Optional[str] = None,
    script_id: Optional[str] = None,
    entity_id: Optional[str] = None,
) -> dict:
    """Validate scope IDs and infer parent lineage."""
    resolved = {
        "project_id": project_id,
        "novel_id": novel_id,
        "chapter_id": chapter_id,
        "script_id": script_id,
        "entity_id": entity_id,
    }
    if project_id:
        proj_result = await db.execute(
            select(Project).where(and_(Project.id == project_id, Project.user_id == user_id))
        )
        if not proj_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="项目不存在")
    if novel_id:
        novel_result = await db.execute(select(Novel).where(and_(Novel.id == novel_id, Novel.user_id == user_id)))
        if not novel_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="小说不存在")
    if chapter_id:
        chapter_result = await db.execute(select(Chapter).where(and_(Chapter.id == chapter_id, Chapter.user_id == user_id)))
        chapter = chapter_result.scalar_one_or_none()
        if not chapter:
            raise HTTPException(status_code=404, detail="章节不存在")
        if novel_id and chapter.novel_id != novel_id:
            raise HTTPException(status_code=400, detail="章节不属于指定小说")
        resolved["novel_id"] = chapter.novel_id
    if script_id:
        script_result = await db.execute(select(Script).where(and_(Script.id == script_id, Script.user_id == user_id)))
        script = script_result.scalar_one_or_none()
        if not script:
            raise HTTPException(status_code=404, detail="剧本不存在")
        script_extra = script.extra_data if isinstance(script.extra_data, dict) else {}
        if novel_id and script.novel_id and script.novel_id != novel_id:
            raise HTTPException(status_code=400, detail="剧本不属于指定小说")
        if chapter_id and script.chapter_id and script.chapter_id != chapter_id:
            raise HTTPException(status_code=400, detail="剧本不属于指定章节")
        resolved["novel_id"] = resolved["novel_id"] or script.novel_id
        resolved["chapter_id"] = resolved["chapter_id"] or script.chapter_id or script_extra.get("chapter_id")
    if entity_id:
        entity_result = await db.execute(
            select(StoryEntity).where(and_(StoryEntity.id == entity_id, StoryEntity.user_id == user_id))
        )
        entity = entity_result.scalar_one_or_none()
        if not entity:
            raise HTTPException(status_code=404, detail="实体不存在")
        if novel_id and entity.novel_id and entity.novel_id != novel_id:
            raise HTTPException(status_code=400, detail="实体不属于指定小说")
        if chapter_id and entity.chapter_id and entity.chapter_id != chapter_id:
            raise HTTPException(status_code=400, detail="实体不属于指定章节")
        if script_id and getattr(entity, "script_id", None) and entity.script_id != script_id:
            raise HTTPException(status_code=400, detail="实体不属于指定剧本")
        resolved["novel_id"] = resolved["novel_id"] or entity.novel_id
        resolved["chapter_id"] = resolved["chapter_id"] or entity.chapter_id
        resolved["script_id"] = resolved["script_id"] or getattr(entity, "script_id", None)
    return resolved


# ========== API 端点 ==========

@router.get("/categories", response_model=List[AssetCategoryResponse])
async def list_categories(
    include_public: bool = Query(True, description="是否包含公开资产"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取所有资产分类"""
    await ensure_default_anime_assets(db, user_id)
    result = await db.execute(select(AssetCategory).order_by(AssetCategory.sort_order))
    categories = result.scalars().all()

    responses = []
    for cat in categories:
        visibility_condition = or_(Asset.is_public == True, Asset.user_id == user_id) if include_public else Asset.user_id == user_id
        count_result = await db.execute(
            select(func.count(Asset.id)).where(
                and_(Asset.category == cat.name, Asset.is_active == True, visibility_condition)
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
    novel_id: Optional[str] = Query(None, description="小说ID"),
    chapter_id: Optional[str] = Query(None, description="章节ID"),
    script_id: Optional[str] = Query(None, description="剧本ID"),
    entity_id: Optional[str] = Query(None, description="实体ID"),
    scope: Optional[str] = Query(None, description="global/novel/chapter/script/entity/project"),
    tags: Optional[str] = Query(None, description="标签，逗号分隔"),
    search: Optional[str] = Query(None, description="搜索名称/描述"),
    include_public: bool = Query(True, description="是否包含公开资产"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取资产列表"""
    await ensure_default_anime_assets(db, user_id)

    conditions = [Asset.is_active == True]
    include_global_with_lineage = scope in (None, "", "all")

    if category:
        conditions.append(Asset.category == category)

    if project_id:
        if include_global_with_lineage:
            conditions.append(or_(Asset.project_id == project_id, Asset.project_id.is_(None)))
        else:
            conditions.append(Asset.project_id == project_id)
    else:
        conditions.append(
            or_(Asset.project_id.is_(None), Asset.user_id == user_id)
        )
    if novel_id:
        if include_global_with_lineage:
            conditions.append(or_(Asset.novel_id == novel_id, Asset.novel_id.is_(None)))
        else:
            conditions.append(Asset.novel_id == novel_id)
    if chapter_id:
        if include_global_with_lineage:
            conditions.append(or_(Asset.chapter_id == chapter_id, Asset.chapter_id.is_(None)))
        else:
            conditions.append(Asset.chapter_id == chapter_id)
    if script_id:
        if include_global_with_lineage:
            conditions.append(or_(Asset.script_id == script_id, Asset.script_id.is_(None)))
        else:
            conditions.append(Asset.script_id == script_id)
    if entity_id:
        if include_global_with_lineage:
            conditions.append(or_(Asset.entity_id == entity_id, Asset.entity_id.is_(None)))
        else:
            conditions.append(Asset.entity_id == entity_id)
    if scope == "global":
        conditions.extend([
            Asset.project_id.is_(None),
            Asset.novel_id.is_(None),
            Asset.chapter_id.is_(None),
            Asset.script_id.is_(None),
            Asset.entity_id.is_(None),
        ])
    elif scope == "novel":
        conditions.append(Asset.novel_id.is_not(None))
    elif scope == "chapter":
        conditions.append(Asset.chapter_id.is_not(None))
    elif scope == "script":
        conditions.append(Asset.script_id.is_not(None))
    elif scope == "entity":
        conditions.append(Asset.entity_id.is_not(None))
    elif scope == "project":
        conditions.append(Asset.project_id.is_not(None))

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
    scope = await validate_asset_scope(
        db,
        user_id,
        project_id=request.project_id,
        novel_id=request.novel_id,
        chapter_id=request.chapter_id,
        script_id=request.script_id,
        entity_id=request.entity_id,
    )

    asset = Asset(
        id=str(uuid4()),
        user_id=user_id,
        category=request.category,
        name=request.name,
        description=request.description,
        asset_type=request.asset_type or "image",
        url=request.url,
        thumbnail_url=request.thumbnail_url,
        project_id=scope["project_id"],
        novel_id=scope["novel_id"],
        chapter_id=scope["chapter_id"],
        script_id=scope["script_id"],
        entity_id=scope["entity_id"],
        tags=request.tags or [],
        style_tags=request.style_tags or [],
        prompt_template=request.prompt_template,
        variables=request.variables,
        shot_template=request.shot_template,
        character_id=request.character_id,
        expressions=request.expressions,
        poses=request.poses,
        is_public=request.is_public,
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
    if any(key in update_data for key in ("project_id", "novel_id", "chapter_id", "script_id", "entity_id")):
        scope = await validate_asset_scope(
            db,
            user_id,
            project_id=update_data.get("project_id", asset.project_id),
            novel_id=update_data.get("novel_id", asset.novel_id),
            chapter_id=update_data.get("chapter_id", asset.chapter_id),
            script_id=update_data.get("script_id", asset.script_id),
            entity_id=update_data.get("entity_id", asset.entity_id),
        )
        update_data.update(scope)
    for key, value in update_data.items():
        setattr(asset, key, value)
    asset.updated_at = utc_now()

    await db.commit()
    await db.refresh(asset)
    return build_asset_response(asset)


@router.post("/{asset_id}/scope", response_model=AssetResponse)
async def update_asset_scope(
    asset_id: str,
    request: AssetScopeUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """动态调整资产作用域：全局、项目、小说、章节、剧本或实体。"""
    result = await db.execute(
        select(Asset).where(and_(Asset.id == asset_id, Asset.user_id == user_id))
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")

    scope = request.scope
    if scope not in {"global", "project", "novel", "chapter", "script", "entity"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="不支持的资产作用域")
    if scope == "global":
        resolved = {"project_id": None, "novel_id": None, "chapter_id": None, "script_id": None, "entity_id": None}
    else:
        resolved = await validate_asset_scope(
            db,
            user_id,
            project_id=request.project_id if scope == "project" else None,
            novel_id=request.novel_id,
            chapter_id=request.chapter_id if scope in {"chapter", "script", "entity"} else None,
            script_id=request.script_id if scope in {"script", "entity"} else None,
            entity_id=request.entity_id if scope == "entity" else None,
        )
        if scope == "project" and not resolved["project_id"]:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="项目作用域必须提供 project_id")
        if scope == "novel" and not resolved["novel_id"]:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="小说作用域必须提供 novel_id")
        if scope == "chapter" and not resolved["chapter_id"]:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="章节作用域必须提供 chapter_id")
        if scope == "script" and not resolved["script_id"]:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="剧本作用域必须提供 script_id")
        if scope == "entity" and not resolved["entity_id"]:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="实体作用域必须提供 entity_id")

    asset.project_id = resolved["project_id"]
    asset.novel_id = resolved["novel_id"]
    asset.chapter_id = resolved["chapter_id"]
    asset.script_id = resolved["script_id"]
    asset.entity_id = resolved["entity_id"]
    asset.updated_at = utc_now()
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
    asset.updated_at = utc_now()
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


# ========== 资产生成 API ==========

def _get_volcano_service() -> Optional[VolcanoService]:
    """获取火山引擎服务实例"""
    import os
    api_key = os.environ.get("VOLCENGINE_API_KEY")
    if not api_key:
        return None
    return VolcanoService(api_key)


@router.post("/generate-character", response_model=CharacterAssetsResponse)
async def generate_character_assets(
    request: CharacterAssetGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """生成角色资产：头像、全身、表情、姿态"""
    # 获取角色信息
    result = await db.execute(select(Character).where(Character.id == request.character_id))
    character = result.scalar_one_or_none()
    if not character:
        raise HTTPException(status_code=404, detail="角色不存在")

    # 创建资产生成服务
    service = AssetGenerationService(db, user_id)

    # 设置火山引擎服务
    volcano_service = _get_volcano_service()
    if not volcano_service:
        raise HTTPException(status_code=503, detail="图像生成服务未配置 (VOLCENGINE_API_KEY)")

    # 检查VOLCENGINE_API_KEY是否有效
    test_result = await volcano_service.generate_image(
        prompt="test",
        size="1k",
    )
    if not test_result or not test_result.get("data"):
        raise HTTPException(status_code=503, detail="图像生成服务不可用")

    service.set_volcano_service(volcano_service)

    # 生成角色资产
    assets_result = await service.generate_character_assets(
        character_id=character.id,
        character_name=character.name,
        character_description=character.description or character.appearance or "",
        style=request.style,
        project_id=character.project_id,
        novel_id=character.novel_id,
    )

    # 构建响应
    assets_dict = {}
    for key, asset in assets_result.items():
        assets_dict[key] = AssetGenerateResponse(
            asset_id=asset.id,
            name=asset.name,
            url=asset.url,
            is_locked=asset.is_locked,
            is_final=asset.is_final,
        )

    return CharacterAssetsResponse(
        character_id=request.character_id,
        assets=assets_dict,
        total=len(assets_dict),
    )


@router.post("/generate-scene", response_model=SceneAssetsResponse)
async def generate_scene_assets(
    request: SceneAssetGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """生成场景资产：主场景、细节图"""
    volcano_service = _get_volcano_service()
    if not volcano_service:
        raise HTTPException(status_code=503, detail="图像生成服务未配置 (VOLCENGINE_API_KEY)")

    service = AssetGenerationService(db, user_id)
    service.set_volcano_service(volcano_service)

    assets_result = await service.generate_scene_assets(
        scene_id=request.scene_id,
        scene_name=request.scene_name,
        scene_description=request.scene_description,
        style=request.style,
    )

    assets_dict = {}
    for key, asset in assets_result.items():
        assets_dict[key] = AssetGenerateResponse(
            asset_id=asset.id,
            name=asset.name,
            url=asset.url,
            is_locked=asset.is_locked,
            is_final=asset.is_final,
        )

    return SceneAssetsResponse(
        scene_id=request.scene_id,
        assets=assets_dict,
        total=len(assets_dict),
    )


@router.post("/generate-prop", response_model=PropAssetsResponse)
async def generate_prop_assets(
    request: PropAssetGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """生成道具资产"""
    volcano_service = _get_volcano_service()
    if not volcano_service:
        raise HTTPException(status_code=503, detail="图像生成服务未配置 (VOLCENGINE_API_KEY)")

    service = AssetGenerationService(db, user_id)
    service.set_volcano_service(volcano_service)

    assets_result = await service.generate_prop_assets(
        prop_id=request.prop_id,
        prop_name=request.prop_name,
        prop_description=request.prop_description,
        style=request.style,
    )

    assets_dict = {}
    for key, asset in assets_result.items():
        assets_dict[key] = AssetGenerateResponse(
            asset_id=asset.id,
            name=asset.name,
            url=asset.url,
            is_locked=asset.is_locked,
            is_final=asset.is_final,
        )

    return PropAssetsResponse(
        prop_id=request.prop_id,
        assets=assets_dict,
        total=len(assets_dict),
    )


# ========== 版本锁定 API ==========

@router.post("/{asset_id}/lock", response_model=AssetResponse)
async def lock_asset(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """锁定资产版本"""
    result = await db.execute(
        select(Asset).where(and_(Asset.id == asset_id, Asset.user_id == user_id))
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")

    service = AssetGenerationService(db, user_id)
    locked_asset = await service.lock_asset_version(asset_id)
    return build_asset_response(locked_asset)


@router.post("/{asset_id}/unlock", response_model=AssetResponse)
async def unlock_asset(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """解锁资产版本"""
    result = await db.execute(
        select(Asset).where(and_(Asset.id == asset_id, Asset.user_id == user_id))
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")

    service = AssetGenerationService(db, user_id)
    unlocked_asset = await service.unlock_asset(asset_id)
    return build_asset_response(unlocked_asset)


@router.get("/entity/{entity_id}", response_model=EntityAssetsResponse)
async def get_entity_assets(
    entity_id: str,
    entity_type: Optional[str] = Query(None, description="实体类型: character/scene/prop"),
    include_locked_only: bool = Query(False, description="只返回锁定的资产"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取实体的所有资产"""
    conditions = [Asset.entity_id == entity_id, Asset.is_active == True]

    if entity_type:
        conditions.append(Asset.entity_type == entity_type)

    if include_locked_only:
        conditions.append(Asset.is_locked == True)

    result = await db.execute(
        select(Asset).where(*conditions).order_by(Asset.version.desc())
    )
    assets = result.scalars().all()

    # 获取锁定的资产
    locked_result = await db.execute(
        select(Asset).where(
            and_(
                Asset.entity_id == entity_id,
                Asset.is_locked == True,
                Asset.is_active == True,
            )
        )
    )
    locked_assets = locked_result.scalars().all()

    return EntityAssetsResponse(
        entity_type=entity_type or "unknown",
        entity_id=entity_id,
        assets=[build_asset_response(a) for a in assets],
        locked_assets=[build_asset_response(a) for a in locked_assets],
        total=len(assets),
    )


@router.get("/entity/{entity_id}/versions", response_model=List[AssetResponse])
async def get_entity_asset_versions(
    entity_id: str,
    entity_type: str = Query(..., description="实体类型: character/scene/prop"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取实体的所有资产版本"""
    service = AssetGenerationService(db, user_id)
    assets = await service.get_entity_asset_versions(entity_type, entity_id)
    return [build_asset_response(a) for a in assets]


@router.post("/batch-lock")
async def batch_lock_assets(
    asset_ids: List[str],
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """批量锁定资产"""
    service = AssetGenerationService(db, user_id)
    locked_assets = []

    for asset_id in asset_ids:
        try:
            asset = await service.lock_asset_version(asset_id)
            locked_assets.append(build_asset_response(asset))
        except ValueError:
            continue

    return {"locked_count": len(locked_assets), "assets": locked_assets}
