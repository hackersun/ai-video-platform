"""
素材库 API 端点
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File, Form
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime

router = APIRouter(prefix="/api/v1/assets", tags=["assets"])


class AssetUploadResponse(BaseModel):
    """素材上传响应"""
    id: str
    name: str
    status: str
    message: str


class AssetResponse(BaseModel):
    """素材响应"""
    id: str
    name: str
    description: Optional[str] = None
    asset_type: str
    file_format: str
    file_size: int
    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    thumbnail_url: Optional[str] = None
    preview_url: Optional[str] = None
    ai_tags: List[str] = []
    custom_tags: List[str] = []
    download_count: int = 0
    view_count: int = 0
    created_at: datetime


@router.get("/categories")
async def get_asset_categories():
    """获取素材分类"""
    return {
        "video": [
            {"id": "intro", "name": "片头片尾", "icon": "play-circle"},
            {"id": "transition", "name": "转场特效", "icon": "shuffle"},
            {"id": "background", "name": "背景视频", "icon": "video"},
        ],
        "image": [
            {"id": "background", "name": "背景图", "icon": "image"},
            {"id": "illustration", "name": "插图", "icon": "image"},
            {"id": "icon", "name": "图标", "icon": "smile"},
        ],
        "audio": [
            {"id": "bgm", "name": "背景音乐", "icon": "music"},
            {"id": "sfx", "name": "音效", "icon": "volume-2"},
        ],
    }


@router.get("")
async def list_assets(
    asset_type: Optional[str] = Query(None),
    category_id: Optional[str] = Query(None),
    folder_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """获取素材列表"""
    return {"items": [], "total": 0, "skip": skip, "limit": limit}


@router.get("/folders")
async def list_folders(parent_id: Optional[str] = Query(None)):
    """获取素材文件夹"""
    return {"items": [], "total": 0}


@router.post("/folders")
async def create_folder(
    name: str = Form(...),
    parent_id: Optional[str] = Form(None),
):
    """创建文件夹"""
    return {"id": "new-folder-id", "name": name, "message": "创建成功"}


@router.post("/upload")
async def upload_asset(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    asset_type: str = Form(...),
    folder_id: Optional[str] = Form(None),
):
    """上传素材"""
    return {"id": "new-asset-id", "name": name or file.filename, "status": "processing"}


@router.get("/{asset_id}")
async def get_asset(asset_id: str):
    """获取素材详情"""
    return {"id": asset_id, "name": "素材名称", "asset_type": "video", "status": "ready"}


@router.delete("/{asset_id}")
async def delete_asset(asset_id: str):
    """删除素材"""
    return {"message": "删除成功"}


@router.post("/{asset_id}/favorite")
async def favorite_asset(asset_id: str):
    """收藏素材"""
    return {"message": "收藏成功"}


@router.get("/user/favorites")
async def get_user_favorites(skip: int = 0, limit: int = 20):
    """获取用户收藏的素材"""
    return {"items": [], "total": 0, "skip": skip, "limit": limit}