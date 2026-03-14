"""
剧本管理API
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter()

# 模拟剧本数据存储
_mock_scripts: List[dict] = []


@router.get("/")
async def get_scripts(
    novel_id: Optional[str] = Query(None, description="按小说ID筛选"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取剧本列表"""
    scripts = _mock_scripts
    
    if novel_id:
        scripts = [s for s in scripts if s.get("novel_id") == novel_id]
    
    return {
        "items": scripts,
        "total": len(scripts),
        "page": page,
        "page_size": limit,
        "pages": 1
    }


@router.get("/{script_id}")
async def get_script(
    script_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取单个剧本详情"""
    script = next((s for s in _mock_scripts if s["id"] == script_id), None)
    if not script:
        raise HTTPException(status_code=404, detail="剧本不存在")
    return script


@router.post("/")
async def create_script(
    data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建新剧本"""
    import uuid
    
    script = {
        "id": str(uuid.uuid4()),
        "title": data.get("title", ""),
        "novel_id": data.get("novel_id", ""),
        "content": data.get("content", ""),
        "status": "draft",
        "scenes": [],
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "user_id": str(current_user.id)
    }
    
    _mock_scripts.append(script)
    
    return {
        "id": script["id"],
        "title": script["title"],
        "novel_id": script["novel_id"],
        "content": script["content"],
        "status": script["status"],
        "created_at": script["created_at"],
        "updated_at": script["updated_at"]
    }


@router.patch("/{script_id}")
async def update_script(
    script_id: str,
    data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新剧本"""
    script = next((s for s in _mock_scripts if s["id"] == script_id), None)
    if not script:
        raise HTTPException(status_code=404, detail="剧本不存在")
    
    if "title" in data:
        script["title"] = data["title"]
    if "content" in data:
        script["content"] = data["content"]
    
    script["updated_at"] = datetime.utcnow().isoformat()
    
    return script


@router.delete("/{script_id}")
async def delete_script(
    script_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除剧本"""
    global _mock_scripts
    script = next((s for s in _mock_scripts if s["id"] == script_id), None)
    if not script:
        raise HTTPException(status_code=404, detail="剧本不存在")
    
    _mock_scripts = [s for s in _mock_scripts if s["id"] != script_id]
    
    return {"message": "剧本已删除"}


@router.post("/generate")
async def generate_script(
    data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """AI生成剧本"""
    import uuid
    
    script = {
        "id": str(uuid.uuid4()),
        "title": f"AI生成剧本 - {datetime.now().strftime('%Y%m%d%H%M%S')}",
        "novel_id": data.get("novel_id", ""),
        "content": "这是AI生成的剧本内容...",
        "status": "draft",
        "scenes": [],
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "user_id": str(current_user.id),
        "is_ai_generated": True
    }
    
    _mock_scripts.append(script)
    
    return script
