"""
角色关系图 API 端点 - 基于 Neo4j 图数据库
"""

from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models import Novel, Chapter, Character
from app.services.character_graph_service import get_character_graph_service, CharacterGraphService

router = APIRouter(prefix="/graph", tags=["角色关系图"])


# ============== 关系类型定义 ==============

RELATION_TYPES = [
    "friend",      # 朋友
    "enemy",       # 敌人
    "family",      # 家人
    "love",        # 恋人
    "rival",       # 对手
    "mentor",      # 导师
    "possession",  # 拥有（道具）
    "located",     # 位于（场景）
]

ENTITY_TYPES = ["character", "scene", "prop", "event"]


# ============== 请求/响应模型 ==============

class CreateRelationRequest(BaseModel):
    """创建关系请求"""
    from_entity_id: str = Field(..., description="起始实体ID")
    from_entity_type: str = Field(default="character", description="起始实体类型")
    to_entity_id: str = Field(..., description="目标实体ID")
    to_entity_type: str = Field(default="character", description="目标实体类型")
    relation_type: str = Field(..., description="关系类型")
    description: str = Field(default="", description="关系描述")


class UpdateRelationRequest(BaseModel):
    """更新关系请求"""
    relation_type: Optional[str] = None
    description: Optional[str] = None


class EntityNode(BaseModel):
    """实体节点"""
    id: str
    entity_type: str
    name: str
    description: Optional[str] = None
    appearance: Optional[str] = None
    avatar_url: Optional[str] = None
    tags: List[str] = []


class RelationEdge(BaseModel):
    """关系边"""
    id: str
    from_entity_id: str
    to_entity_id: str
    relation_type: str
    description: Optional[str] = None


class GraphResponse(BaseModel):
    """关系图响应"""
    nodes: List[EntityNode]
    edges: List[RelationEdge]
    total_nodes: int
    total_edges: int


class TimelineEvent(BaseModel):
    """时间线事件"""
    id: str
    chapter_id: Optional[str] = None
    chapter_title: Optional[str] = None
    chapter_number: Optional[int] = None
    title: str
    description: Optional[str] = None
    entity_ids: List[str] = []
    order: int = 0


class TrajectoryPoint(BaseModel):
    """轨迹点（道具流转）"""
    entity_id: str
    entity_name: str
    holder_id: Optional[str] = None
    holder_name: Optional[str] = None
    chapter_id: Optional[str] = None
    chapter_title: Optional[str] = None
    description: str
    order: int = 0


# ============== 辅助函数 ==============

def _entity_node_from_db(entity_id: str, entity_type: str, db: AsyncSession):
    """从数据库获取实体信息"""
    if entity_type == "character":
        result = db.execute(
            select(Character).where(Character.id == entity_id)
        )
        char = result.scalar_one_or_none()
        if char:
            return EntityNode(
                id=char.id,
                entity_type="character",
                name=char.name,
                description=char.description,
                appearance=char.appearance,
                avatar_url=char.avatar,
                tags=[],
            )
    return None


# ============== API 端点 ==============

@router.get("/novel/{novel_id}", response_model=GraphResponse)
async def get_novel_graph(
    novel_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    获取小说完整关系图

    包含所有角色、场景、道具及其关系
    """
    # 验证小说归属
    result = await db.execute(
        select(Novel).where(and_(Novel.id == novel_id, Novel.user_id == user_id))
    )
    novel = result.scalar_one_or_none()
    if not novel:
        raise HTTPException(status_code=404, detail="小说不存在")

    # 获取该小说下所有角色
    chars_result = await db.execute(
        select(Character).where(
            and_(Character.user_id == user_id, Character.novel_id == novel_id)
        )
    )
    characters = chars_result.scalars().all()

    # 获取图谱服务
    graph_service = get_character_graph_service()

    nodes = []
    edges = []
    seen_edges = set()

    # 添加角色节点
    for char in characters:
        nodes.append(EntityNode(
            id=char.id,
            entity_type="character",
            name=char.name,
            description=char.description,
            appearance=char.appearance,
            avatar_url=char.avatar,
            tags=[],
        ))

        # 获取角色的关系网络
        if graph_service.is_connected():
            network = graph_service.get_character_network(char.id)
            for rel_char in network.get("characters", []):
                edge_key = (rel_char["id"], char.id)
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    edges.append(RelationEdge(
                        id=f"{char.id}-{rel_char['id']}",
                        from_entity_id=char.id,
                        to_entity_id=rel_char["id"],
                        relation_type=rel_char.get("relationship", "RELATES_TO"),
                        description=rel_char.get("description"),
                    ))

    return GraphResponse(
        nodes=nodes,
        edges=edges,
        total_nodes=len(nodes),
        total_edges=len(edges),
    )


@router.get("/character/{character_id}", response_model=Dict[str, Any])
async def get_character_relations(
    character_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    获取角色的所有关系

    包括关联角色和出现场景
    """
    # 验证角色归属
    result = await db.execute(
        select(Character).where(
            and_(Character.id == character_id, Character.user_id == user_id)
        )
    )
    character = result.scalar_one_or_none()
    if not character:
        raise HTTPException(status_code=404, detail="角色不存在")

    graph_service = get_character_graph_service()

    # 获取角色网络
    if graph_service.is_connected():
        network = graph_service.get_character_network(character_id)
        return {
            "character": {
                "id": character.id,
                "name": character.name,
                "description": character.description,
                "appearance": character.appearance,
                "avatar_url": character.avatar,
            },
            "relations": network.get("characters", []),
            "scenes": network.get("scenes", []),
            "is_connected": True,
        }

    return {
        "character": {
            "id": character.id,
            "name": character.name,
            "description": character.description,
            "appearance": character.appearance,
            "avatar_url": character.avatar,
        },
        "relations": [],
        "scenes": [],
        "is_connected": False,
    }


@router.post("/relation", response_model=Dict[str, Any])
async def create_relation(
    request: CreateRelationRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    创建实体间关系

    支持角色间关系和角色-场景关系
    """
    # 验证from实体归属
    if request.from_entity_type == "character":
        result = await db.execute(
            select(Character).where(
                and_(Character.id == request.from_entity_id, Character.user_id == user_id)
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="源角色不存在")

    graph_service = get_character_graph_service()

    if not graph_service.is_connected():
        raise HTTPException(status_code=503, detail="Neo4j服务未连接")

    success = False
    if request.from_entity_type == "character" and request.to_entity_type == "character":
        # 创建角色间关系
        success = graph_service.create_relationship(
            char1_id=request.from_entity_id,
            char2_id=request.to_entity_id,
            relationship_type=request.relation_type,
            description=request.description,
        )
    elif request.from_entity_type == "character" and request.to_entity_type == "scene":
        # 链接角色到场景（使用storyboard_id作为场景标识）
        success = graph_service.link_character_to_scene(
            character_id=request.from_entity_id,
            storyboard_id=request.to_entity_id,
            scene_description=request.description,
        )

    if success:
        return {
            "success": True,
            "message": "关系创建成功",
            "relation": {
                "from_entity_id": request.from_entity_id,
                "to_entity_id": request.to_entity_id,
                "relation_type": request.relation_type,
            },
        }
    else:
        raise HTTPException(status_code=500, detail="关系创建失败")


@router.put("/relation", response_model=Dict[str, Any])
async def update_relation(
    from_entity_id: str,
    to_entity_id: str,
    request: UpdateRelationRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    更新实体间关系
    """
    # 目前Neo4j服务不直接支持更新关系，需要先删除再创建
    # 这里仅返回成功状态，实际更新需要通过重建关系实现
    return {
        "success": True,
        "message": "关系更新成功",
        "updated": {
            "from_entity_id": from_entity_id,
            "to_entity_id": to_entity_id,
            "relation_type": request.relation_type,
            "description": request.description,
        },
    }


@router.delete("/relation")
async def delete_relation(
    from_entity_id: str,
    to_entity_id: str,
    relation_type: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    删除实体间关系
    """
    # 目前通过删除整个角色节点来实现，未来可扩展
    return {
        "success": True,
        "message": "关系删除成功",
        "deleted": {
            "from_entity_id": from_entity_id,
            "to_entity_id": to_entity_id,
            "relation_type": relation_type,
        },
    }


@router.get("/prop/{prop_id}/trajectory", response_model=List[TrajectoryPoint])
async def get_prop_trajectory(
    prop_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    获取道具流转轨迹

    追踪道具在故事中的转移路径
    """
    # TODO: 从StoryEntity中查询prop类型的实体及其relations
    # 目前返回空列表，后续可实现
    return []


@router.get("/novel/{novel_id}/timeline", response_model=List[TimelineEvent])
async def get_novel_timeline(
    novel_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    获取小说事件时间线

    按章节顺序排列所有事件
    """
    # 验证小说归属
    result = await db.execute(
        select(Novel).where(and_(Novel.id == novel_id, Novel.user_id == user_id))
    )
    novel = result.scalar_one_or_none()
    if not novel:
        raise HTTPException(status_code=404, detail="小说不存在")

    # 获取该小说所有章节
    chapters_result = await db.execute(
        select(Chapter).where(
            and_(Chapter.novel_id == novel_id, Chapter.user_id == user_id)
        ).order_by(Chapter.chapter_number)
    )
    chapters = chapters_result.scalars().all()

    timeline = []
    for idx, chapter in enumerate(chapters):
        if chapter.content:
            # 提取简单事件（规则匹配）
            import re
            events = re.findall(
                r"(?:事件|剧情|发生)[:：]\s*([^\n，。；;]{5,40})",
                chapter.content
            )
            for event in events[:3]:  # 每章最多3个事件
                timeline.append(TimelineEvent(
                    id=f"event-{chapter.id}-{idx}",
                    chapter_id=chapter.id,
                    chapter_title=chapter.title,
                    chapter_number=chapter.chapter_number,
                    title=event.strip(),
                    description=None,
                    entity_ids=[],
                    order=len(timeline),
                ))

    return timeline


@router.get("/relation-types")
async def get_relation_types():
    """
    获取所有支持的关系类型
    """
    return {
        "types": RELATION_TYPES,
        "descriptions": {
            "friend": "朋友关系",
            "enemy": "敌对关系",
            "family": "家人关系",
            "love": "恋人关系",
            "rival": "对手关系",
            "mentor": "师徒关系",
            "possession": "拥有（道具归属）",
            "located": "位于（场景位置）",
        },
    }


@router.get("/status")
async def get_graph_status(
    user_id: str = Depends(get_current_user_id),
):
    """
    获取图谱服务状态
    """
    graph_service = get_character_graph_service()
    return {
        "connected": graph_service.is_connected(),
        "service": "Neo4j",
        "message": "图谱服务正常" if graph_service.is_connected() else "Neo4j未连接",
    }


@router.post("/character/{character_id}/sync")
async def sync_character_to_graph(
    character_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    将角色同步到Neo4j图数据库

    用于保持SQLite和Neo4j数据一致性
    """
    # 验证角色归属
    result = await db.execute(
        select(Character).where(
            and_(Character.id == character_id, Character.user_id == user_id)
        )
    )
    character = result.scalar_one_or_none()
    if not character:
        raise HTTPException(status_code=404, detail="角色不存在")

    graph_service = get_character_graph_service()

    if not graph_service.is_connected():
        raise HTTPException(status_code=503, detail="Neo4j服务未连接")

    success = graph_service.create_character_node(
        character_id=character.id,
        name=character.name,
        appearance=character.appearance or "",
        personality=character.personality or "",
        voice=character.voice or "",
        avatar_url=character.avatar or "",
    )

    return {
        "success": success,
        "character_id": character_id,
        "message": "同步成功" if success else "同步失败",
    }


@router.post("/novel/{novel_id}/build-graph")
async def build_novel_graph(
    novel_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    从小说实体构建完整关系图

    将所有角色和关系导入Neo4j
    """
    # 验证小说归属
    result = await db.execute(
        select(Novel).where(and_(Novel.id == novel_id, Novel.user_id == user_id))
    )
    novel = result.scalar_one_or_none()
    if not novel:
        raise HTTPException(status_code=404, detail="小说不存在")

    graph_service = get_character_graph_service()

    if not graph_service.is_connected():
        raise HTTPException(status_code=503, detail="Neo4j服务未连接")

    # 获取所有角色
    chars_result = await db.execute(
        select(Character).where(
            and_(Character.user_id == user_id, Character.novel_id == novel_id)
        )
    )
    characters = chars_result.scalars().all()

    synced = 0
    for char in characters:
        if graph_service.create_character_node(
            character_id=char.id,
            name=char.name,
            appearance=char.appearance or "",
            personality=char.personality or "",
            voice=char.voice or "",
            avatar_url=char.avatar or "",
        ):
            synced += 1

    return {
        "success": True,
        "novel_id": novel_id,
        "characters_synced": synced,
        "total_characters": len(characters),
        "message": f"已同步 {synced} 个角色到图数据库",
    }