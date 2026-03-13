"""
模板 API 端点
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime

# 暂时注释掉依赖，等实现后再取消注释
# from app.services.template_service import TemplateService
# from app.core.security import get_current_user

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])


class TemplateCreate(BaseModel):
    """创建模板请求"""
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    content_type: Optional[str] = None
    style_type: Optional[str] = None
    industry: Optional[str] = None
    duration: Optional[str] = None
    platform: Optional[str] = None
    template_data: Optional[dict] = None
    preview_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    price: Optional[float] = 0.0
    tags: Optional[List[str]] = []


class TemplateUpdate(BaseModel):
    """更新模板请求"""
    title: Optional[str] = None
    description: Optional[str] = None
    content_type: Optional[str] = None
    style_type: Optional[str] = None
    industry: Optional[str] = None
    duration: Optional[str] = None
    platform: Optional[str] = None
    template_data: Optional[dict] = None
    preview_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    price: Optional[float] = None
    tags: Optional[List[str]] = None


class TemplateFilter(BaseModel):
    """模板过滤参数"""
    content_type: Optional[str] = None
    style_type: Optional[str] = None
    industry: Optional[str] = None
    duration: Optional[str] = None
    platform: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    is_free: Optional[bool] = False
    search: Optional[str] = None
    sort_by: str = "newest"


class TemplateResponse(BaseModel):
    """模板响应"""
    id: str
    title: str
    description: Optional[str] = None
    content_type: Optional[str] = None
    style_type: Optional[str] = None
    industry: Optional[str] = None
    duration: Optional[str] = None
    platform: Optional[str] = None
    template_data: Optional[dict] = None
    preview_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    price: float
    download_count: int = 0
    rating: float = 5.0
    rating_count: int = 0
    author_id: str
    created_at: datetime
    updated_at: datetime


@router.get("/categories")
async def get_template_categories():
    """获取模板分类"""
    return {
        "content_types": [
            {"id": "short_video", "name": "短视频", "icon": "video"},
            {"id": "promo", "name": "宣传片", "icon": "megaphone"},
            {"id": "product", "name": "产品介绍", "icon": "package"},
            {"id": "education", "name": "教育培训", "icon": "book"},
            {"id": "social", "name": "社交媒体", "icon": "share"},
            {"id": "ad", "name": "广告", "icon": "target"},
            {"id": "vlog", "name": "Vlog", "icon": "camera"},
            {"id": "animation", "name": "动画", "icon": "film"},
        ],
        "style_types": [
            {"id": "business", "name": "商务专业"},
            {"id": "lively", "name": "活泼可爱"},
            {"id": "tech", "name": "科技感"},
            {"id": "retro", "name": "复古风"},
            {"id": "minimal", "name": "极简主义"},
            {"id": "cinematic", "name": "电影感"},
            {"id": "cartoon", "name": "卡通"},
            {"id": "realistic", "name": "写实"},
        ],
        "industries": [
            {"id": "ecommerce", "name": "电商"},
            {"id": "education", "name": "教育"},
            {"id": "finance", "name": "金融"},
            {"id": "medical", "name": "医疗"},
            {"id": "food", "name": "餐饮"},
            {"id": "travel", "name": "旅游"},
            {"id": "tech", "name": "科技"},
            {"id": "entertainment", "name": "娱乐"},
        ],
        "durations": [
            {"id": "15s", "name": "15秒"},
            {"id": "30s", "name": "30秒"},
            {"id": "60s", "name": "60秒"},
            {"id": "3min", "name": "3分钟"},
            {"id": "5min", "name": "5分钟"},
        ],
        "platforms": [
            {"id": "douyin", "name": "抖音"},
            {"id": "kuaishou", "name": "快手"},
            {"id": "xiaohongshu", "name": "小红书"},
            {"id": "bilibili", "name": "B站"},
            {"id": "youtube", "name": "YouTube"},
        ],
    }


@router.get("")
async def list_templates(
    content_type: Optional[str] = Query(None),
    style_type: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    duration: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    is_free: Optional[bool] = Query(False),
    search: Optional[str] = Query(None),
    sort_by: str = Query("newest"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """获取模板列表（公开）"""
    # TODO: 实现真实的数据库查询
    return {
        "items": [],
        "total": 0,
        "skip": skip,
        "limit": limit,
    }


@router.get("/market")
async def get_template_market(
    content_type: Optional[str] = Query(None),
    style_type: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("newest"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """获取模板市场"""
    # TODO: 实现真实的模板市场查询
    return {
        "items": [],
        "total": 0,
        "skip": skip,
        "limit": limit,
        "categories": [
            {"id": "hot", "name": "热门推荐", "count": 0},
            {"id": "new", "name": "新品上架", "count": 0},
            {"id": "free", "name": "免费模板", "count": 0},
        ],
    }


@router.get("/featured")
async def get_featured_templates(
    limit: int = Query(10, ge=1, le=50),
):
    """获取推荐模板"""
    # TODO: 实现
    return {"items": [], "total": 0}


@router.get("/{template_id}")
async def get_template(template_id: str):
    """获取模板详情"""
    # TODO: 实现
    return {
        "id": template_id,
        "title": "示例模板",
        "description": "模板描述",
        "price": 0.0,
    }


@router.post("")
async def create_template(request: TemplateCreate):
    """创建模板"""
    # TODO: 实现
    return {"id": "new-template-id", "message": "模板创建成功"}


@router.put("/{template_id}")
async def update_template(template_id: str, request: TemplateUpdate):
    """更新模板"""
    # TODO: 实现
    return {"id": template_id, "message": "模板更新成功"}


@router.delete("/{template_id}")
async def delete_template(template_id: str):
    """删除模板"""
    # TODO: 实现
    return {"message": "模板删除成功"}


@router.post("/{template_id}/publish")
async def publish_template(template_id: str):
    """发布模板到市场"""
    # TODO: 实现
    return {"id": template_id, "status": "pending", "message": "已提交审核"}


@router.post("/{template_id}/favorite")
async def add_to_favorites(template_id: str):
    """收藏模板"""
    # TODO: 实现
    return {"message": "收藏成功"}


@router.delete("/{template_id}/favorite")
async def remove_from_favorites(template_id: str):
    """取消收藏"""
    # TODO: 实现
    return {"message": "取消收藏成功"}


@router.get("/user/favorites")
async def get_user_favorites(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """获取用户收藏的模板"""
    # TODO: 实现
    return {"items": [], "total": 0, "skip": skip, "limit": limit}


@router.get("/user/my-templates")
async def get_user_templates(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """获取用户创建的模板"""
    # TODO: 实现
    return {"items": [], "total": 0, "skip": skip, "limit": limit}


@router.post("/{template_id}/use")
async def use_template(template_id: str):
    """使用模板（记录使用次数）"""
    # TODO: 实现
    return {"message": "使用成功", "download_count": 1}