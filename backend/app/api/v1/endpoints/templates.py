"""
模板市场 API 端点
"""

from app.core.time_utils import utc_now
from typing import List, Optional
from datetime import datetime
from uuid import uuid4
import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, or_
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.template import Template, TEMPLATE_CATEGORIES, PRESET_TEMPLATES

router = APIRouter(tags=["模板市场"])


# ============== Pydantic 模型 ==============

class TemplateCreate(BaseModel):
    """创建模板"""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    content: dict = Field(..., description="模板内容结构数据")
    is_public: bool = Field(default=False, description="是否公开")


class TemplateUpdate(BaseModel):
    """更新模板"""
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    content: Optional[dict] = None
    is_public: Optional[bool] = None
    is_featured: Optional[bool] = None
    rating: Optional[float] = None


class TemplateResponse(BaseModel):
    """模板响应"""
    id: str
    user_id: str
    name: str
    description: Optional[str]
    category: Optional[str]
    tags: List[str]
    content: dict
    usage_count: int
    rating: float
    is_public: bool
    is_featured: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm(cls, template: Template) -> "TemplateResponse":
        tags = []
        if template.tags:
            try:
                tags = json.loads(template.tags) if isinstance(template.tags, str) else template.tags
            except:
                tags = []
        return cls(
            id=template.id,
            user_id=template.user_id,
            name=template.name,
            description=template.description,
            category=template.category,
            tags=tags,
            content=template.content or {},
            usage_count=template.usage_count or 0,
            rating=template.rating or 0,
            is_public=template.is_public or False,
            is_featured=template.is_featured or False,
            created_at=template.created_at,
            updated_at=template.updated_at,
        )


class TemplateCategoryResponse(BaseModel):
    """模板分类响应"""
    id: str
    name: str
    icon: str
    description: Optional[str]


# ============== API端点 ==============

@router.get("/categories", response_model=List[TemplateCategoryResponse])
async def list_categories():
    """获取所有模板分类"""
    return [
        TemplateCategoryResponse(**cat) for cat in TEMPLATE_CATEGORIES
    ]


@router.get("/presets", response_model=List[TemplateResponse])
async def list_preset_templates(
    category: Optional[str] = Query(None, description="按分类过滤"),
):
    """获取预置模板列表"""
    templates = []
    for idx, preset in enumerate(PRESET_TEMPLATES):
        if category and preset.get("category") != category:
            continue
        templates.append(TemplateResponse(
            id=f"preset_{idx}",
            user_id="system",
            name=preset["name"],
            description=preset.get("description"),
            category=preset.get("category"),
            tags=preset.get("tags", []),
            content=preset.get("content", {}),
            usage_count=0,
            rating=0,
            is_public=True,
            is_featured=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ))
    return templates


@router.get("", response_model=List[TemplateResponse])
async def list_templates(
    category: Optional[str] = Query(None, description="按分类过滤"),
    is_public: Optional[bool] = Query(None, description="按公开状态过滤"),
    search: Optional[str] = Query(None, description="搜索名称或描述"),
    include_presets: bool = Query(True, description="是否包含预置模板"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取用户的模板列表（包含可选的预置模板）"""
    # 查询用户模板
    query = select(Template).where(Template.user_id == user_id)
    if category:
        query = query.where(Template.category == category)
    if is_public is not None:
        query = query.where(Template.is_public == is_public)
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            or_(
                Template.name.ilike(search_pattern),
                Template.description.ilike(search_pattern)
            )
        )
    query = query.order_by(desc(Template.usage_count), desc(Template.updated_at))
    result = await db.execute(query)
    user_templates = result.scalars().all()

    responses = [TemplateResponse.from_orm(t) for t in user_templates]

    # 合并预置模板
    if include_presets:
        for idx, preset in enumerate(PRESET_TEMPLATES):
            if category and preset.get("category") != category:
                continue
            if is_public is False:  # 用户只查询私有模板时不包含预置
                continue
            if search:
                search_lower = search.lower()
                name_match = search_lower in preset["name"].lower()
                desc_match = preset.get("description", "").lower()
                desc_match = search_lower in desc_match
                if not (name_match or desc_match):
                    continue
            responses.append(TemplateResponse(
                id=f"preset_{idx}",
                user_id="system",
                name=preset["name"],
                description=preset.get("description"),
                category=preset.get("category"),
                tags=preset.get("tags", []),
                content=preset.get("content", {}),
                usage_count=0,
                rating=0,
                is_public=True,
                is_featured=False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            ))

    return responses


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取模板详情"""
    # 检查是否是预置模板
    if template_id.startswith("preset_"):
        try:
            idx = int(template_id.replace("preset_", ""))
            if 0 <= idx < len(PRESET_TEMPLATES):
                preset = PRESET_TEMPLATES[idx]
                return TemplateResponse(
                    id=template_id,
                    user_id="system",
                    name=preset["name"],
                    description=preset.get("description"),
                    category=preset.get("category"),
                    tags=preset.get("tags", []),
                    content=preset.get("content", {}),
                    usage_count=0,
                    rating=0,
                    is_public=True,
                    is_featured=False,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
        except ValueError:
            pass
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模板不存在"
        )

    result = await db.execute(
        select(Template).where(
            and_(Template.id == template_id, Template.user_id == user_id)
        )
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模板不存在"
        )

    return TemplateResponse.from_orm(template)


@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    template_data: TemplateCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """创建新模板"""
    new_template = Template(
        id=str(uuid4()),
        user_id=user_id,
        name=template_data.name,
        description=template_data.description,
        category=template_data.category,
        tags=json.dumps(template_data.tags) if template_data.tags else "[]",
        content=template_data.content,
        is_public=template_data.is_public,
    )

    db.add(new_template)
    await db.commit()
    await db.refresh(new_template)

    return TemplateResponse.from_orm(new_template)


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: str,
    template_data: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """更新模板"""
    if template_id.startswith("preset_"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="预置模板不可编辑"
        )

    result = await db.execute(
        select(Template).where(
            and_(Template.id == template_id, Template.user_id == user_id)
        )
    )
    db_template = result.scalar_one_or_none()

    if not db_template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模板不存在"
        )

    update_data = template_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == 'tags' and value is not None:
            setattr(db_template, field, json.dumps(value))
        else:
            setattr(db_template, field, value)

    db_template.updated_at = utc_now()

    await db.commit()
    await db.refresh(db_template)

    return TemplateResponse.from_orm(db_template)


@router.delete("/{template_id}")
async def delete_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """删除模板"""
    if template_id.startswith("preset_"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="预置模板不可删除"
        )

    result = await db.execute(
        select(Template).where(
            and_(Template.id == template_id, Template.user_id == user_id)
        )
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模板不存在"
        )

    await db.delete(template)
    await db.commit()

    return {"message": "模板已删除"}


@router.post("/{template_id}/use", response_model=TemplateResponse)
async def use_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """使用模板（增加使用计数）"""
    # 检查是否是预置模板
    if template_id.startswith("preset_"):
        try:
            idx = int(template_id.replace("preset_", ""))
            if 0 <= idx < len(PRESET_TEMPLATES):
                preset = PRESET_TEMPLATES[idx]
                return TemplateResponse(
                    id=template_id,
                    user_id="system",
                    name=preset["name"],
                    description=preset.get("description"),
                    category=preset.get("category"),
                    tags=preset.get("tags", []),
                    content=preset.get("content", {}),
                    usage_count=0,  # 预置模板不计数
                    rating=0,
                    is_public=True,
                    is_featured=False,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
        except ValueError:
            pass
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模板不存在"
        )

    result = await db.execute(
        select(Template).where(
            and_(Template.id == template_id, Template.user_id == user_id)
        )
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模板不存在"
        )

    template.usage_count = (template.usage_count or 0) + 1
    template.updated_at = utc_now()

    await db.commit()
    await db.refresh(template)

    return TemplateResponse.from_orm(template)


@router.post("/{template_id}/clone", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def clone_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """复制模板到用户自己的模板库"""
    # 检查是否是预置模板
    if template_id.startswith("preset_"):
        try:
            idx = int(template_id.replace("preset_", ""))
            if 0 <= idx < len(PRESET_TEMPLATES):
                preset = PRESET_TEMPLATES[idx]
                new_template = Template(
                    id=str(uuid4()),
                    user_id=user_id,
                    name=f"{preset['name']} (副本)",
                    description=preset.get("description"),
                    category=preset.get("category"),
                    tags=json.dumps(preset.get("tags", [])),
                    content=preset.get("content", {}),
                    is_public=False,
                )
                db.add(new_template)
                await db.commit()
                await db.refresh(new_template)
                return TemplateResponse.from_orm(new_template)
        except ValueError:
            pass
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模板不存在"
        )

    # 复制用户自己的模板
    result = await db.execute(
        select(Template).where(
            and_(Template.id == template_id, Template.user_id == user_id)
        )
    )
    original = result.scalar_one_or_none()

    if not original:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模板不存在"
        )

    tags = []
    if original.tags:
        try:
            tags = json.loads(original.tags) if isinstance(original.tags, str) else original.tags
        except:
            tags = []

    new_template = Template(
        id=str(uuid4()),
        user_id=user_id,
        name=f"{original.name} (副本)",
        description=original.description,
        category=original.category,
        tags=json.dumps(tags),
        content=original.content or {},
        is_public=False,
    )

    db.add(new_template)
    await db.commit()
    await db.refresh(new_template)

    return TemplateResponse.from_orm(new_template)