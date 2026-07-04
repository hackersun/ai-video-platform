"""
资产库 API 端点
支持项目资产库 + 全局资产库双层复用
"""
from app.core.time_utils import utc_now
from datetime import datetime
from typing import Dict, List, Literal, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, desc, or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dev_generation import is_dev_mode
from app.core.security import get_current_user_id
from app.models.asset import Asset, AssetCategory
from app.models.asset import DEFAULT_CATEGORIES
from app.models.project import Project
from app.models import Chapter, Novel, Script, StoryEntity
from app.models.character import Character
from app.services.default_anime_library import ensure_default_anime_assets
from app.services.asset_generation_service import AssetGenerationService, get_asset_view_presets, get_image_style_templates
from app.services.asset_visual_review import review_asset_against_contract, retry_prompt_advice
from app.services.media_persistence import persist_uploaded_media_bytes

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
    entity_type: Optional[str] = None
    tags: Optional[List[str]] = None
    style_tags: Optional[List[str]] = None
    prompt_template: Optional[str] = None
    variables: Optional[List[dict]] = None
    shot_template: Optional[dict] = None
    source_prompt: Optional[str] = None
    generation_params: Optional[dict] = None
    character_id: Optional[str] = None
    expressions: Optional[List[dict]] = None
    poses: Optional[List[dict]] = None
    is_public: bool = False


class AssetUpdate(BaseModel):
    category: Optional[str] = None
    asset_type: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
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
    source_prompt: Optional[str] = None
    generation_params: Optional[dict] = None
    character_id: Optional[str] = None
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
    source_url: Optional[str] = None
    source_prompt: Optional[str] = None
    generation_params: Optional[dict] = None
    created_at: str
    updated_at: str


class AssetUploadResponse(BaseModel):
    url: str
    filename: str
    content_type: str
    size: int
    media_type: str
    kind: str


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


class EntityViewGenerateRequest(BaseModel):
    entity_id: str
    novel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    script_id: Optional[str] = None
    view_keys: Optional[List[str]] = Field(None, description="可选视图 key，不传则生成该实体类型全部必备视图")
    style: str = Field("anime", description="anime/xianxia/wuxia/fantasy/urban/cartoon/realistic")
    model_config_id: Optional[str] = None
    consistency_mode: Literal["off", "draft", "standard", "strict"] = Field("off", description="一致性模式: off/draft/standard/strict")
    force_contract_refresh: bool = False
    anchor_view_key: Optional[str] = None


class AssetRegenerateRequest(BaseModel):
    style: Optional[str] = Field(None, description="可选风格；不传则沿用原资产生成风格")
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


class AssetViewPresetResponse(BaseModel):
    presets: List[dict]


class AssetStyleTemplatesResponse(BaseModel):
    default_style: str = "anime"
    templates: List[dict]


class EntityViewAssetsResponse(BaseModel):
    entity_type: str
    entity_id: str
    assets: Dict[str, AssetResponse]
    total: int
    failures: List[AssetResponse] = []


class EntityAssetsResponse(BaseModel):
    entity_type: str
    entity_id: str
    assets: List[AssetResponse]
    locked_assets: List[AssetResponse]
    total: int


class AssetVisualConsistencyRequest(BaseModel):
    score: float = Field(..., ge=0, le=100)
    model: Optional[str] = None
    reference_asset_ids: Optional[List[str]] = None
    issues: Optional[List[str]] = None
    notes: Optional[str] = None


class AssetBulkActionRequest(BaseModel):
    asset_ids: List[str] = Field(..., min_length=1, description="要批量维护的资产ID")
    action: str = Field(..., description="archive/lock/unlock/set_scope/set_tags")
    scope: Optional[str] = Field(None, description="global/project/novel/chapter/script/entity")
    project_id: Optional[str] = None
    novel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    script_id: Optional[str] = None
    entity_id: Optional[str] = None
    tags: Optional[List[str]] = None
    allow_test_override: bool = Field(False, description="测试模式允许跳过生产限制")


class AssetReextractRequest(BaseModel):
    entity_ids: Optional[List[str]] = Field(None, description="可选：只重建指定实体的资产包")
    novel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    script_id: Optional[str] = None
    entity_types: List[str] = Field(default_factory=lambda: ["character", "scene", "prop"])
    mode: str = Field("append", description="append/overwrite/delete_then_extract")
    style: str = Field("anime", description="生成风格")
    view_keys: Optional[List[str]] = Field(None, description="可选：只重建指定视图 key")
    model_config_id: Optional[str] = None
    allow_test_override: bool = Field(False, description="测试模式允许跳过锁定/引用限制")
    limit: int = Field(30, ge=1, le=100)


class BulkSkippedItem(BaseModel):
    id: str
    reason: str
    repair_action: Optional[str] = None


class AssetBulkActionResponse(BaseModel):
    updated_count: int = 0
    deleted_count: int = 0
    created_count: int = 0
    skipped: List[BulkSkippedItem] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    assets: List[AssetResponse] = Field(default_factory=list)


async def ensure_default_categories(db: AsyncSession) -> None:
    """Ensure production-oriented asset categories exist for the current DB."""
    changed = False
    for cat_data in DEFAULT_CATEGORIES:
        result = await db.execute(select(AssetCategory).where(AssetCategory.name == cat_data["name"]))
        existing_categories = result.scalars().all()
        if existing_categories:
            updates = {
                "name_cn": cat_data["name_cn"],
                "icon": cat_data["icon"],
                "sort_order": cat_data["sort_order"],
                "is_system": True,
            }
            for existing in existing_categories:
                for key, value in updates.items():
                    if getattr(existing, key) != value:
                        setattr(existing, key, value)
                        changed = True
            continue
        db.add(
            AssetCategory(
                id=str(uuid4()),
                name=cat_data["name"],
                name_cn=cat_data["name_cn"],
                icon=cat_data["icon"],
                sort_order=cat_data["sort_order"],
                is_system=True,
            )
        )
        changed = True
    if changed:
        await db.commit()


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
        source_url=getattr(asset, 'source_url', None),
        source_prompt=getattr(asset, 'source_prompt', None),
        generation_params=getattr(asset, 'generation_params', None),
        created_at=str(asset.created_at),
        updated_at=str(asset.updated_at),
    )


def story_entity_visual_description(entity: StoryEntity) -> str:
    attributes = entity.attributes if isinstance(entity.attributes, dict) else {}
    description_parts = [
        getattr(entity, "appearance", None),
        getattr(entity, "visual_prompt", None),
        entity.description,
        attributes.get("appearance"),
        attributes.get("visual_prompt"),
        attributes.get("mood"),
    ]
    return "；".join(str(item).strip() for item in description_parts if item) or entity.evidence or ""


def _story_entity_name_candidates(entity: StoryEntity) -> List[str]:
    candidates = [
        getattr(entity, "name", None),
        getattr(entity, "canonical_name", None),
    ]
    aliases = entity.aliases if isinstance(entity.aliases, list) else []
    candidates.extend(aliases)
    seen = set()
    result = []
    for item in candidates:
        text = str(item or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


async def resolve_character_for_story_entity(
    db: AsyncSession,
    user_id: str,
    entity: Optional[StoryEntity],
) -> Optional[Character]:
    """Resolve a story character entity to the editable Character record used by video consistency."""
    if not entity or entity.entity_type != "character":
        return None
    names = _story_entity_name_candidates(entity)
    if not names:
        return None
    filters = [Character.user_id == user_id, Character.name.in_(names)]
    if entity.novel_id:
        filters.append(or_(Character.novel_id == entity.novel_id, Character.novel_id.is_(None)))
    result = await db.execute(
        select(Character)
        .where(and_(*filters))
        .order_by(desc(Character.updated_at))
    )
    characters = list(result.scalars().all())
    if not characters:
        return None

    def rank(character: Character) -> tuple[int, int, int]:
        exact_name = 0 if character.name == entity.name else 1
        same_novel = 0 if entity.novel_id and character.novel_id == entity.novel_id else 1
        global_fallback = 0 if character.novel_id is None else 1
        return (exact_name, same_novel, global_fallback)

    return sorted(characters, key=rank)[0]


def _asset_upload_media_type(asset_type: str, kind: str) -> str:
    if kind == "thumbnail":
        return "image"
    if asset_type in {"image", "video", "audio"}:
        return asset_type
    return "artifact"


def _asset_upload_limit(media_type: str) -> int:
    return {
        "image": 20 * 1024 * 1024,
        "video": 300 * 1024 * 1024,
        "audio": 80 * 1024 * 1024,
        "artifact": 20 * 1024 * 1024,
    }.get(media_type, 20 * 1024 * 1024)


def ensure_bulk_asset_scope_payload(scope: Optional[str], payload: AssetScopeUpdate | AssetBulkActionRequest) -> None:
    if scope == "project" and not payload.project_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="项目作用域必须提供 project_id")
    if scope == "novel" and not payload.novel_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="小说作用域必须提供 novel_id")
    if scope == "chapter" and not payload.chapter_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="章节作用域必须提供 chapter_id")
    if scope == "script" and not payload.script_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="剧本作用域必须提供 script_id")
    if scope == "entity" and not payload.entity_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="实体作用域必须提供 entity_id")


def asset_view_key(asset: Asset) -> Optional[str]:
    params = asset.generation_params if isinstance(asset.generation_params, dict) else {}
    value = params.get("view_key") or params.get("asset_subtype") or params.get("view_angle")
    return str(value) if value else None


def entity_view_keys(entity_type: str, requested: Optional[List[str]] = None) -> List[str]:
    presets = {preset["entity_type"]: preset for preset in get_asset_view_presets()}
    preset = presets.get(entity_type)
    if not preset:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"不支持的实体资产类型：{entity_type}")
    allowed = [view["key"] for view in preset.get("views", [])]
    if not requested:
        return allowed
    unknown = [key for key in requested if key not in allowed]
    if unknown:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"不支持的资产视图：{', '.join(unknown)}")
    return requested


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
        resolved_novel_id = resolved["novel_id"]
        resolved_chapter_id = resolved["chapter_id"]
        resolved_script_id = resolved["script_id"]
        if resolved_novel_id and entity.novel_id and entity.novel_id != resolved_novel_id:
            raise HTTPException(status_code=400, detail="实体不属于指定小说")
        if resolved_chapter_id and entity.chapter_id and entity.chapter_id != resolved_chapter_id:
            raise HTTPException(status_code=400, detail="实体不属于指定章节")
        if resolved_script_id and getattr(entity, "script_id", None) and entity.script_id != resolved_script_id:
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
    await ensure_default_categories(db)
    await ensure_default_anime_assets(db, user_id)
    result = await db.execute(select(AssetCategory).order_by(AssetCategory.sort_order))
    categories_by_name = {}
    for category in result.scalars().all():
        categories_by_name.setdefault(category.name, category)
    categories = list(categories_by_name.values())

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
    await ensure_default_categories(db)
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


@router.post("/upload", response_model=AssetUploadResponse)
async def upload_asset_file(
    asset_type: str = Query("image", description="资源类型：image/video/audio/text/lora/ipadapter"),
    kind: str = Query("resource", description="resource/thumbnail"),
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
):
    """上传资产资源或缩略图，并返回稳定的 /static 路径。"""
    if kind not in {"resource", "thumbnail"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="上传类型仅支持 resource 或 thumbnail")

    media_type = _asset_upload_media_type(asset_type, kind)
    data = await file.read()
    try:
        url = persist_uploaded_media_bytes(
            data,
            media_type=media_type,
            content_type=file.content_type or "",
            subdir=f"assets/{media_type}s",
            prefix=f"{kind}-{user_id[:8]}",
            max_bytes=_asset_upload_limit(media_type),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    finally:
        await file.close()

    return AssetUploadResponse(
        url=url,
        filename=file.filename or "",
        content_type=file.content_type or "",
        size=len(data),
        media_type=media_type,
        kind=kind,
    )


@router.get("/view-presets", response_model=AssetViewPresetResponse)
async def list_asset_view_presets(
    user_id: str = Depends(get_current_user_id),
):
    """获取创作者可理解的多视图资产预设。"""
    return AssetViewPresetResponse(presets=get_asset_view_presets())


@router.get("/style-templates", response_model=AssetStyleTemplatesResponse)
async def list_asset_style_templates(
    user_id: str = Depends(get_current_user_id),
):
    """获取统一图片生成风格模板，用于封面、头像、参考图和镜头图。"""
    return AssetStyleTemplatesResponse(templates=get_image_style_templates())


@router.post("/generate-entity-views", response_model=EntityViewAssetsResponse)
async def generate_entity_view_assets(
    request: EntityViewGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """按小说实体生成角色三视图、场景四视图或道具多视图。"""
    scope = await validate_asset_scope(
        db,
        user_id,
        novel_id=request.novel_id,
        chapter_id=request.chapter_id,
        script_id=request.script_id,
        entity_id=request.entity_id,
    )
    if request.consistency_mode in {"standard", "strict"} and not scope["novel_id"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="标准/严格一致性模式需要绑定小说",
        )

    entity_result = await db.execute(
        select(StoryEntity).where(and_(StoryEntity.id == request.entity_id, StoryEntity.user_id == user_id))
    )
    entity = entity_result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="实体不存在")
    if entity.entity_type not in {"character", "scene", "prop"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="仅支持角色、场景、道具生成多视图资产")
    entity_view_keys(entity.entity_type, request.view_keys)
    if request.anchor_view_key:
        entity_view_keys(entity.entity_type, [request.anchor_view_key])

    description = story_entity_visual_description(entity)
    character = await resolve_character_for_story_entity(db, user_id, entity)

    service = AssetGenerationService(db, user_id)
    if request.model_config_id:
        await service.configure_image_model(request.model_config_id)
    try:
        generated = await service.generate_entity_view_assets(
            entity_id=entity.id,
            entity_type=entity.entity_type,
            entity_name=entity.name,
            entity_description=description,
            style=request.style,
            novel_id=scope["novel_id"],
            chapter_id=scope["chapter_id"],
            script_id=scope["script_id"],
            character_id=character.id if character else None,
            view_keys=request.view_keys,
            consistency_mode=request.consistency_mode,
            force_contract_refresh=request.force_contract_refresh,
            anchor_view_key=request.anchor_view_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"多视图资产生成失败: {str(exc)}") from exc

    return EntityViewAssetsResponse(
        entity_type=entity.entity_type,
        entity_id=entity.id,
        assets={key: build_asset_response(asset) for key, asset in generated.items()},
        total=len(generated),
        failures=[build_asset_response(asset) for asset in service.last_generation_failures],
    )


@router.post("/bulk-action", response_model=AssetBulkActionResponse)
async def bulk_action_assets(
    request: AssetBulkActionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """批量维护资产，生产模式默认保护锁定、定稿和已引用资产。"""
    if request.action not in {"archive", "lock", "unlock", "set_scope", "set_tags"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="不支持的资产批量动作")

    updated_assets: list[Asset] = []
    skipped: list[BulkSkippedItem] = []
    warnings: list[str] = []
    allow_test_override = request.allow_test_override and is_dev_mode()
    if request.allow_test_override and not allow_test_override:
        warnings.append("生产模式不允许使用测试跳过开关，请先解除锁定、替换引用或切换到测试环境")

    for asset_id in request.asset_ids:
        result = await db.execute(
            select(Asset).where(and_(Asset.id == asset_id, Asset.user_id == user_id))
        )
        asset = result.scalar_one_or_none()
        if not asset:
            skipped.append(BulkSkippedItem(id=asset_id, reason="资产不存在", repair_action="刷新资产库后重新选择"))
            continue

        if request.action == "archive":
            blocked_reasons = []
            if asset.is_locked or asset.is_final:
                blocked_reasons.append("资产已锁定或定稿")
            if (asset.usage_count or 0) > 0:
                blocked_reasons.append(f"资产已被引用 {asset.usage_count} 次")
            if blocked_reasons and not allow_test_override:
                skipped.append(
                    BulkSkippedItem(
                        id=asset.id,
                        reason="；".join(blocked_reasons),
                        repair_action="先解锁资产或替换引用后再归档",
                    )
                )
                continue
            if blocked_reasons and allow_test_override:
                warnings.append(f"测试模式已跳过「{asset.name}」的生产限制：{'；'.join(blocked_reasons)}")
            asset.is_active = False
            asset.updated_at = utc_now()
            updated_assets.append(asset)
            continue

        if request.action == "lock":
            asset.is_locked = True
            asset.is_final = True
            asset.locked_at = utc_now()
            asset.locked_by = user_id
            asset.updated_at = utc_now()
            updated_assets.append(asset)
            continue

        if request.action == "unlock":
            asset.is_locked = False
            asset.is_final = False
            asset.updated_at = utc_now()
            updated_assets.append(asset)
            continue

        if request.action == "set_tags":
            asset.tags = request.tags or []
            asset.updated_at = utc_now()
            updated_assets.append(asset)
            continue

        if request.action == "set_scope":
            scope = request.scope
            if scope not in {"global", "project", "novel", "chapter", "script", "entity"}:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="不支持的资产作用域")
            if scope == "global":
                resolved = {"project_id": None, "novel_id": None, "chapter_id": None, "script_id": None, "entity_id": None}
            else:
                ensure_bulk_asset_scope_payload(scope, request)
                resolved = await validate_asset_scope(
                    db,
                    user_id,
                    project_id=request.project_id if scope == "project" else None,
                    novel_id=request.novel_id,
                    chapter_id=request.chapter_id if scope in {"chapter", "script", "entity"} else None,
                    script_id=request.script_id if scope in {"script", "entity"} else None,
                    entity_id=request.entity_id if scope == "entity" else None,
                )
            asset.project_id = resolved["project_id"]
            asset.novel_id = resolved["novel_id"]
            asset.chapter_id = resolved["chapter_id"]
            asset.script_id = resolved["script_id"]
            asset.entity_id = resolved["entity_id"]
            asset.updated_at = utc_now()
            updated_assets.append(asset)

    if updated_assets:
        await db.commit()
        for asset in updated_assets:
            await db.refresh(asset)

    return AssetBulkActionResponse(
        updated_count=len(updated_assets),
        deleted_count=len([asset for asset in updated_assets if request.action == "archive"]),
        skipped=skipped,
        warnings=warnings,
        assets=[build_asset_response(asset) for asset in updated_assets],
    )


@router.post("/reextract", response_model=AssetBulkActionResponse)
async def reextract_assets(
    request: AssetReextractRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """按小说、剧本或选中实体重建角色/场景/道具资产包。"""
    if request.mode not in {"append", "overwrite", "delete_then_extract"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="重建模式只支持 append、overwrite、delete_then_extract")
    supported_types = {"character", "scene", "prop"}
    entity_types = [item for item in request.entity_types if item in supported_types]
    if not entity_types:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="资产重建只支持角色、场景和道具实体")
    if not request.entity_ids and not any([request.novel_id, request.chapter_id, request.script_id]):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="请提供 entity_ids、novel_id、chapter_id 或 script_id")

    if any([request.novel_id, request.chapter_id, request.script_id]):
        await validate_asset_scope(
            db,
            user_id,
            novel_id=request.novel_id,
            chapter_id=request.chapter_id,
            script_id=request.script_id,
        )

    conditions = [StoryEntity.user_id == user_id, StoryEntity.entity_type.in_(entity_types)]
    if request.entity_ids:
        conditions.append(StoryEntity.id.in_(request.entity_ids))
    else:
        if request.script_id:
            conditions.append(StoryEntity.script_id == request.script_id)
        elif request.chapter_id:
            conditions.append(StoryEntity.chapter_id == request.chapter_id)
        elif request.novel_id:
            conditions.append(StoryEntity.novel_id == request.novel_id)

    entity_result = await db.execute(
        select(StoryEntity)
        .where(and_(*conditions))
        .order_by(StoryEntity.entity_type, StoryEntity.name)
        .limit(request.limit)
    )
    entities = list(entity_result.scalars().all())
    if not entities:
        return AssetBulkActionResponse(
            skipped=[
                BulkSkippedItem(
                    id=request.script_id or request.chapter_id or request.novel_id or ",".join(request.entity_ids or []),
                    reason="当前范围没有可重建资产的角色、场景或道具实体",
                    repair_action="先在实体库按小说/剧本重新抽取实体",
                )
            ]
        )

    allow_test_override = request.allow_test_override and is_dev_mode()
    warnings: list[str] = []
    if request.allow_test_override and not allow_test_override:
        warnings.append("生产模式不允许使用测试跳过开关，请先解除资产锁、替换引用或切换测试环境")

    service = AssetGenerationService(db, user_id)
    if request.model_config_id:
        await service.configure_image_model(request.model_config_id)

    generated_assets: list[Asset] = []
    skipped: list[BulkSkippedItem] = []
    archived_count = 0
    processed_count = 0

    for entity in entities:
        try:
            requested_view_keys = entity_view_keys(entity.entity_type, request.view_keys)
        except HTTPException:
            raise
        entity_asset_result = await db.execute(
            select(Asset).where(
                and_(
                    Asset.user_id == user_id,
                    Asset.entity_id == entity.id,
                    Asset.entity_type == entity.entity_type,
                    Asset.is_active == True,
                )
            )
        )
        active_assets = list(entity_asset_result.scalars().all())
        assets_by_key: dict[str, list[Asset]] = {}
        for asset in active_assets:
            key = asset_view_key(asset)
            if key:
                assets_by_key.setdefault(key, []).append(asset)

        view_keys_to_generate: list[str] = []
        for key in requested_view_keys:
            existing_for_key = assets_by_key.get(key, [])
            blocked_assets = [
                asset for asset in existing_for_key
                if asset.is_locked or asset.is_final or (asset.usage_count or 0) > 0
            ]
            if request.mode == "append" and existing_for_key:
                continue
            if blocked_assets and not allow_test_override:
                for asset in blocked_assets:
                    skipped.append(
                        BulkSkippedItem(
                            id=asset.id,
                            reason="资产已锁定、定稿或正在被引用",
                            repair_action="先解锁资产或替换引用后再重建该视图",
                        )
                    )
                continue
            if blocked_assets and allow_test_override:
                warnings.append(f"测试模式已重建「{entity.name}」的 {key} 视图，并跳过锁定/引用限制")
            if request.mode in {"overwrite", "delete_then_extract"}:
                for asset in existing_for_key:
                    if asset.is_locked or asset.is_final or (asset.usage_count or 0) > 0:
                        if not allow_test_override:
                            continue
                    asset.is_active = False
                    asset.updated_at = utc_now()
                    archived_count += 1
            view_keys_to_generate.append(key)

        if not view_keys_to_generate:
            continue

        character = await resolve_character_for_story_entity(db, user_id, entity)
        try:
            generated = await service.generate_entity_view_assets(
                entity_id=entity.id,
                entity_type=entity.entity_type,
                entity_name=entity.name,
                entity_description=story_entity_visual_description(entity),
                style=request.style,
                novel_id=entity.novel_id,
                chapter_id=entity.chapter_id,
                script_id=getattr(entity, "script_id", None),
                character_id=character.id if character else None,
                view_keys=view_keys_to_generate,
            )
        except ValueError as exc:
            skipped.append(
                BulkSkippedItem(
                    id=entity.id,
                    reason=str(exc),
                    repair_action="先拆分复合实体或调整实体类型后再生成资产",
                )
            )
            continue
        generated_assets.extend(generated.values())
        processed_count += 1

    if archived_count:
        await db.commit()
    for asset in generated_assets:
        await db.refresh(asset)

    return AssetBulkActionResponse(
        updated_count=processed_count,
        deleted_count=archived_count,
        created_count=len(generated_assets),
        skipped=skipped,
        warnings=warnings,
        assets=[build_asset_response(asset) for asset in generated_assets],
    )


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
    resolved_character_id = request.character_id
    resolved_entity_type = request.entity_type
    if not resolved_character_id and scope["entity_id"] and request.category == "character":
        entity_result = await db.execute(
            select(StoryEntity).where(and_(StoryEntity.id == scope["entity_id"], StoryEntity.user_id == user_id))
        )
        entity = entity_result.scalar_one_or_none()
        if entity:
            resolved_entity_type = resolved_entity_type or entity.entity_type
            character = await resolve_character_for_story_entity(db, user_id, entity)
            if character:
                resolved_character_id = character.id

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
        entity_type=resolved_entity_type,
        tags=request.tags or [],
        style_tags=request.style_tags or [],
        prompt_template=request.prompt_template,
        variables=request.variables,
        shot_template=request.shot_template,
        source_prompt=request.source_prompt,
        generation_params=request.generation_params,
        character_id=resolved_character_id,
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
    next_category = update_data.get("category", asset.category)
    next_entity_id = update_data.get("entity_id", asset.entity_id)
    next_character_id = update_data.get("character_id", asset.character_id)
    if next_category == "character" and next_entity_id and not next_character_id:
        entity_result = await db.execute(
            select(StoryEntity).where(and_(StoryEntity.id == next_entity_id, StoryEntity.user_id == user_id))
        )
        entity = entity_result.scalar_one_or_none()
        if entity:
            update_data["entity_type"] = update_data.get("entity_type") or getattr(asset, "entity_type", None) or entity.entity_type
            character = await resolve_character_for_story_entity(db, user_id, entity)
            if character:
                update_data["character_id"] = character.id
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
            ensure_bulk_asset_scope_payload(scope, request)
        if scope == "novel" and not resolved["novel_id"]:
            ensure_bulk_asset_scope_payload(scope, request)
        if scope == "chapter" and not resolved["chapter_id"]:
            ensure_bulk_asset_scope_payload(scope, request)
        if scope == "script" and not resolved["script_id"]:
            ensure_bulk_asset_scope_payload(scope, request)
        if scope == "entity" and not resolved["entity_id"]:
            ensure_bulk_asset_scope_payload(scope, request)

    asset.project_id = resolved["project_id"]
    asset.novel_id = resolved["novel_id"]
    asset.chapter_id = resolved["chapter_id"]
    asset.script_id = resolved["script_id"]
    asset.entity_id = resolved["entity_id"]
    asset.updated_at = utc_now()
    await db.commit()
    await db.refresh(asset)
    return build_asset_response(asset)


@router.post("/{asset_id}/retry-generation", response_model=EntityViewAssetsResponse)
async def retry_asset_generation(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """重试一条失败的实体多视图生成记录。"""
    result = await db.execute(
        select(Asset).where(and_(Asset.id == asset_id, Asset.user_id == user_id))
    )
    failure_asset = result.scalar_one_or_none()
    if not failure_asset:
        raise HTTPException(status_code=404, detail="资产不存在")

    params = failure_asset.generation_params if isinstance(failure_asset.generation_params, dict) else {}
    if params.get("source") != "entity_multiview" or params.get("status") != "failed":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="只有多视图生成失败记录可以重试")

    entity_id = failure_asset.entity_id or params.get("entity_id")
    entity_type = getattr(failure_asset, "entity_type", None) or params.get("entity_type")
    view_key = params.get("view_key")
    if not entity_id or not entity_type or not view_key:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="失败记录缺少实体或视图信息")

    entity_result = await db.execute(
        select(StoryEntity).where(and_(StoryEntity.id == entity_id, StoryEntity.user_id == user_id))
    )
    entity = entity_result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="实体不存在")

    character = await resolve_character_for_story_entity(db, user_id, entity)
    service = AssetGenerationService(db, user_id)
    generated = await service.generate_entity_view_assets(
        entity_id=entity.id,
        entity_type=str(entity_type),
        entity_name=entity.name,
        entity_description=story_entity_visual_description(entity),
        style=params.get("style") or "anime",
        novel_id=failure_asset.novel_id or entity.novel_id,
        chapter_id=failure_asset.chapter_id or entity.chapter_id,
        script_id=failure_asset.script_id or getattr(entity, "script_id", None),
        character_id=failure_asset.character_id or (character.id if character else None),
        view_keys=[str(view_key)],
    )

    if generated:
        next_params = dict(params)
        next_params["status"] = "retried"
        next_params["retried_at"] = utc_now().isoformat()
        next_params["retried_asset_ids"] = [asset.id for asset in generated.values()]
        failure_asset.generation_params = next_params
        failure_asset.is_active = False
        failure_asset.updated_at = utc_now()
        await db.commit()

    return EntityViewAssetsResponse(
        entity_type=str(entity_type),
        entity_id=str(entity_id),
        assets={key: build_asset_response(asset) for key, asset in generated.items()},
        total=len(generated),
        failures=[build_asset_response(asset) for asset in service.last_generation_failures],
    )


@router.post("/{asset_id}/regenerate", response_model=AssetResponse)
async def regenerate_asset(
    asset_id: str,
    request: AssetRegenerateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """按原资产绑定的小说对象、视图和视觉约束重新生成一个新版本。"""
    result = await db.execute(
        select(Asset).where(and_(Asset.id == asset_id, Asset.user_id == user_id))
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")

    params = asset.generation_params if isinstance(asset.generation_params, dict) else {}
    entity_id = asset.entity_id or params.get("entity_id")
    entity_type = getattr(asset, "entity_type", None) or params.get("entity_type") or asset.category
    view_key = params.get("view_key") or params.get("asset_subtype") or params.get("view_angle")
    if not entity_id or entity_type not in {"character", "scene", "prop"} or not view_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="当前资产缺少小说对象或视图信息，暂不支持按一致性约束重新生成",
        )

    entity_result = await db.execute(
        select(StoryEntity).where(and_(StoryEntity.id == entity_id, StoryEntity.user_id == user_id))
    )
    entity = entity_result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="实体不存在")

    character = await resolve_character_for_story_entity(db, user_id, entity)
    service = AssetGenerationService(db, user_id)
    if request.model_config_id:
        await service.configure_image_model(request.model_config_id)
    style = request.style or params.get("style") or "anime"
    retry_advice = params.get("retry_prompt_advice")
    retry_prompt_advice_value = retry_advice.strip() if isinstance(retry_advice, str) else None
    generated = await service.generate_entity_view_assets(
        entity_id=entity.id,
        entity_type=str(entity_type),
        entity_name=entity.name,
        entity_description=story_entity_visual_description(entity),
        style=style,
        project_id=asset.project_id,
        novel_id=asset.novel_id or entity.novel_id,
        chapter_id=asset.chapter_id or entity.chapter_id,
        script_id=asset.script_id or getattr(entity, "script_id", None),
        character_id=asset.character_id or (character.id if character else None),
        view_keys=[str(view_key)],
        retry_feedback_advice=retry_prompt_advice_value,
    )
    regenerated = generated.get(str(view_key))
    if not regenerated:
        raise HTTPException(status_code=500, detail="重新生成未返回有效资产，请检查图像模型配置")

    next_params = regenerated.generation_params if isinstance(regenerated.generation_params, dict) else {}
    next_params["regenerated_from_asset_id"] = asset.id
    next_params["regenerated_at"] = utc_now().isoformat()
    next_params["style"] = style
    regenerated.generation_params = next_params
    regenerated.version = (asset.version or 1) + 1
    asset.replaced_by_id = regenerated.id
    asset.updated_at = utc_now()
    await db.commit()
    await db.refresh(regenerated)
    return build_asset_response(regenerated)


@router.post("/{asset_id}/visual-consistency", response_model=AssetResponse)
async def record_asset_visual_consistency(
    asset_id: str,
    request: AssetVisualConsistencyRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """记录人工或外部视觉检测模型的一致性评分。"""
    result = await db.execute(
        select(Asset).where(and_(Asset.id == asset_id, Asset.user_id == user_id))
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")

    params = dict(asset.generation_params) if isinstance(asset.generation_params, dict) else {}
    record = {
        "score": request.score,
        "model": request.model or "manual-review",
        "reference_asset_ids": request.reference_asset_ids or [],
        "issues": request.issues or [],
        "notes": request.notes or "",
        "checked_at": utc_now().isoformat(),
    }
    history = list(params.get("visual_consistency_history") or [])
    history.insert(0, record)
    params["visual_consistency"] = record
    params["visual_consistency_history"] = history[:20]
    asset.generation_params = params
    asset.updated_at = utc_now()

    await db.commit()
    await db.refresh(asset)
    return build_asset_response(asset)


@router.post("/{asset_id}/review-contract", response_model=AssetResponse)
async def review_asset_contract(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Recompute deterministic prompt coverage against the persisted visual contract."""
    result = await db.execute(
        select(Asset).where(and_(Asset.id == asset_id, Asset.user_id == user_id))
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")

    params = dict(asset.generation_params) if isinstance(asset.generation_params, dict) else {}
    visual_contract = params.get("visual_contract")
    if not isinstance(visual_contract, dict) or not visual_contract:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="当前资产缺少 visual_contract")

    view_key = str(params.get("view_key") or params.get("view_angle") or params.get("asset_subtype") or "")
    provider_metadata = {
        "provider_name": params.get("provider_name"),
        "model_id": params.get("model_id"),
        "model_strategy": params.get("model_strategy"),
    }
    review = review_asset_against_contract(
        visual_contract,
        view_key,
        asset.source_prompt or "",
        provider_result_metadata=provider_metadata,
    )
    params["visual_consistency"] = review
    if review.get("status") != "passed" or review.get("issues"):
        params["retry_prompt_advice"] = retry_prompt_advice(review.get("issues") or [], visual_contract)
    else:
        params.pop("retry_prompt_advice", None)

    asset.generation_params = params
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
    await service.configure_image_model(request.model_config_id)

    # 生成角色资产
    try:
        assets_result = await service.generate_character_assets(
            character_id=character.id,
            character_name=character.name,
            character_description=character.description or character.appearance or "",
            style=request.style,
            project_id=character.project_id,
            novel_id=character.novel_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"角色资产生成失败: {str(exc)}")

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
    service = AssetGenerationService(db, user_id)
    await service.configure_image_model(request.model_config_id)

    try:
        assets_result = await service.generate_scene_assets(
            scene_id=request.scene_id,
            scene_name=request.scene_name,
            scene_description=request.scene_description,
            style=request.style,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"场景资产生成失败: {str(exc)}")

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
    service = AssetGenerationService(db, user_id)
    await service.configure_image_model(request.model_config_id)

    try:
        assets_result = await service.generate_prop_assets(
            prop_id=request.prop_id,
            prop_name=request.prop_name,
            prop_description=request.prop_description,
            style=request.style,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"道具资产生成失败: {str(exc)}")

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
