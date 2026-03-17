"""
角色管理 API 端点
"""

from typing import List, Optional
from datetime import datetime
from uuid import uuid4
import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.character import Character

router = APIRouter(tags=["角色管理"])


# ============== 数据模型 ==============

class CharacterCreate(BaseModel):
    """创建角色请求"""
    name: str = Field(..., min_length=1, max_length=100, description="角色名称")
    description: Optional[str] = Field(None, description="角色描述")
    appearance: Optional[str] = Field(None, description="外貌特征")
    personality: Optional[str] = Field(None, description="性格特点")
    voice: Optional[str] = Field(None, description="声音特征")
    avatar: Optional[str] = Field(None, description="头像URL")
    tags: List[str] = Field(default_factory=list, description="标签")


class CharacterUpdate(BaseModel):
    """更新角色请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    appearance: Optional[str] = None
    personality: Optional[str] = None
    voice: Optional[str] = None
    avatar: Optional[str] = None
    tags: Optional[List[str]] = None


class CharacterResponse(BaseModel):
    """角色响应"""
    id: str
    user_id: str
    name: str
    description: Optional[str]
    appearance: Optional[str]
    personality: Optional[str]
    voice: Optional[str]
    avatar: Optional[str]
    tags: List[str]
    created_at: datetime
    updated_at: datetime
    
    @classmethod
    def from_orm(cls, character: Character) -> "CharacterResponse":
        tags = []
        if character.tags:
            try:
                tags = json.loads(character.tags) if isinstance(character.tags, str) else character.tags
            except:
                tags = []
        return cls(
            id=character.id,
            user_id=character.user_id,
            name=character.name,
            description=character.description,
            appearance=character.appearance,
            personality=character.personality,
            voice=character.voice,
            avatar=character.avatar,
            tags=tags,
            created_at=character.created_at,
            updated_at=character.updated_at
        )


# ============== 模拟数据库（开发阶段使用）==============

# 内存存储，生产环境应使用真实数据库
CHARACTERS_DB = {}


# ============== API端点 ==============

@router.get("", response_model=List[CharacterResponse])
async def list_characters(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取用户的所有角色"""
    result = await db.execute(
        select(Character).where(Character.user_id == user_id).order_by(desc(Character.created_at))
    )
    characters = result.scalars().all()
    return [CharacterResponse.from_orm(char) for char in characters]


@router.get("/count")
async def get_character_count(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取角色数量（用于Dashboard统计）"""
    result = await db.execute(
        select(Character).where(Character.user_id == user_id)
    )
    characters = result.scalars().all()
    
    return {"count": len(characters)}


@router.get("/{character_id}", response_model=CharacterResponse)
async def get_character(
    character_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取单个角色详情"""
    result = await db.execute(
        select(Character).where(
            and_(Character.id == character_id, Character.user_id == user_id)
        )
    )
    character = result.scalar_one_or_none()
    
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="角色不存在"
        )
    
    return CharacterResponse.from_orm(character)


@router.post("", response_model=CharacterResponse, status_code=status.HTTP_201_CREATED)
async def create_character(
    character: CharacterCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """创建新角色"""
    new_character = Character(
        id=str(uuid4()),
        user_id=user_id,
        name=character.name,
        description=character.description,
        appearance=character.appearance,
        personality=character.personality,
        voice=character.voice,
        avatar=character.avatar,
        tags=json.dumps(character.tags) if character.tags else "[]",
    )
    
    db.add(new_character)
    await db.commit()
    await db.refresh(new_character)
    
    return CharacterResponse.from_orm(new_character)


@router.put("/{character_id}", response_model=CharacterResponse)
async def update_character(
    character_id: str,
    character: CharacterUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """更新角色信息"""
    result = await db.execute(
        select(Character).where(
            and_(Character.id == character_id, Character.user_id == user_id)
        )
    )
    db_character = result.scalar_one_or_none()
    
    if not db_character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="角色不存在"
        )
    
    # 更新非空字段
    update_data = character.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == 'tags' and value is not None:
            setattr(db_character, field, json.dumps(value))
        else:
            setattr(db_character, field, value)
    
    db_character.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(db_character)
    
    return CharacterResponse.from_orm(db_character)


@router.delete("/{character_id}")
async def delete_character(
    character_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """删除角色"""
    result = await db.execute(
        select(Character).where(
            and_(Character.id == character_id, Character.user_id == user_id)
        )
    )
    character = result.scalar_one_or_none()
    
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="角色不存在"
        )
    
    await db.delete(character)
    await db.commit()
    
    return {"message": "角色已删除"}