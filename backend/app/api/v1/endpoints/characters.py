"""
角色相关端点
"""

from uuid import uuid4
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
from app.models.novel import Character


router = APIRouter()


class CharacterCreateRequest(BaseModel):
    name: str
    novel_id: str
    description: str = ""
    avatar: str = ""


@router.get("/")
async def list_characters(
    skip: int = 0,
    limit: int = 20,
    novel_id: str = None,
    db: AsyncSession = Depends(get_db),
):
    """获取角色列表"""
    query = select(Character)
    if novel_id:
        query = query.where(Character.novel_id == novel_id)

    result = await db.execute(query.offset(skip).limit(limit))
    characters = result.scalars().all()

    items = []
    for char in characters:
        items.append(
            {
                "id": char.id,
                "name": char.name,
                "description": char.description,
                "avatar": char.avatar,
                "novel_id": char.novel_id,
                "created_at": char.created_at.isoformat() if char.created_at else None,
            }
        )

    total_result = await db.execute(select(func.count(Character.id)))
    total = total_result.scalar()

    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.get("/{character_id}")
async def get_character(character_id: str, db: AsyncSession = Depends(get_db)):
    """获取角色详情"""
    result = await db.execute(select(Character).where(Character.id == character_id))
    char = result.scalar_one_or_none()

    if not char:
        raise HTTPException(status_code=404, detail="角色不存在")

    return {
        "id": char.id,
        "name": char.name,
        "description": char.description,
        "avatar": char.avatar,
        "novel_id": char.novel_id,
        "created_at": char.created_at.isoformat() if char.created_at else None,
    }


@router.post("/")
async def create_character(
    request: CharacterCreateRequest, db: AsyncSession = Depends(get_db)
):
    """创建角色"""
    char = Character(
        id=str(uuid4()),
        name=request.name,
        description=request.description,
        avatar=request.avatar or "",
        novel_id=request.novel_id,
    )
    db.add(char)
    await db.commit()
    await db.refresh(char)

    return {
        "id": char.id,
        "name": char.name,
        "description": char.description,
        "avatar": char.avatar,
    }


class CharacterUpdateRequest(BaseModel):
    name: str = ""
    description: str = ""
    avatar: str = ""


@router.put("/{character_id}")
async def update_character(
    character_id: str,
    request: CharacterUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """更新角色"""
    result = await db.execute(select(Character).where(Character.id == character_id))
    char = result.scalar_one_or_none()

    if not char:
        raise HTTPException(status_code=404, detail="角色不存在")

    if request.name:
        char.name = request.name
    if request.description:
        char.description = request.description
    if request.avatar:
        char.avatar = request.avatar

    await db.commit()
    await db.refresh(char)

    return {
        "id": char.id,
        "name": char.name,
        "description": char.description,
        "avatar": char.avatar,
    }


@router.delete("/{character_id}")
async def delete_character(character_id: str, db: AsyncSession = Depends(get_db)):
    """删除角色"""
    result = await db.execute(select(Character).where(Character.id == character_id))
    char = result.scalar_one_or_none()

    if not char:
        raise HTTPException(status_code=404, detail="角色不存在")

    await db.delete(char)
    await db.commit()

    return {"message": "删除成功"}


@router.post("/{character_id}/generate-avatar")
async def generate_avatar(character_id: str, db: AsyncSession = Depends(get_db)):
    """AI生成角色头像"""
    result = await db.execute(select(Character).where(Character.id == character_id))
    char = result.scalar_one_or_none()

    if not char:
        raise HTTPException(status_code=404, detail="角色不存在")

    seed = hash(char.name) % 10000
    avatar_url = f"https://picsum.photos/seed/{seed}/200/200"

    char.avatar = avatar_url
    await db.commit()
    await db.refresh(char)

    return {"id": char.id, "avatar": char.avatar, "message": "头像生成成功"}
