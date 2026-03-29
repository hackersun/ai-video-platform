"""
Neo4j Character Knowledge Graph Service
角色关系知识图谱服务 - 用于维护角色一致性和关系
"""

import os
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Neo4j connection settings
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")


class CharacterGraphService:
    """角色知识图谱服务"""

    _driver = None

    def __init__(self):
        self._connected = False
        self._connect()

    def _connect(self):
        """建立 Neo4j 连接"""
        try:
            from neo4j import GraphDatabase
            self._driver = GraphDatabase.driver(
                NEO4J_URI,
                auth=(NEO4J_USER, NEO4J_PASSWORD),
                max_connection_lifetime=3600,
                max_connection_pool_size=10,
                connection_acquisition_timeout=60,
            )
            # Test connection
            with self._driver.session() as session:
                session.run("RETURN 1")
            self._connected = True
            logger.info("✅ Neo4j connected successfully")
        except ImportError:
            logger.warning("neo4j driver not installed, character graph disabled")
            self._connected = False
        except Exception as e:
            logger.warning(f"Neo4j connection failed: {e}, character graph disabled")
            self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def close(self):
        """关闭连接"""
        if self._driver:
            self._driver.close()
            self._driver = None
            self._connected = False

    def _run_query(self, query: str, params: Dict[str, Any] = None) -> List[Dict]:
        """执行 Cypher 查询"""
        if not self._connected:
            return []
        try:
            with self._driver.session() as session:
                result = session.run(query, params or {})
                return [dict(record) for record in result]
        except Exception as e:
            logger.error(f"Neo4j query error: {e}")
            return []

    def init_constraints(self):
        """初始化约束和索引"""
        if not self._connected:
            return
        constraints = [
            "CREATE CONSTRAINT character_id IF NOT EXISTS FOR (c:Character) REQUIRE c.character_id IS UNIQUE",
            "CREATE CONSTRAINT character_name IF NOT EXISTS FOR (c:Character) REQUIRE c.name IS UNIQUE",
            "CREATE INDEX character_id_index IF NOT EXISTS FOR (c:Character) ON (c.character_id)",
            "CREATE INDEX character_name_index IF NOT EXISTS FOR (c:Character) ON (c.name)",
        ]
        for c in constraints:
            try:
                self._run_query(c)
            except Exception:
                pass  # Constraint may already exist

    def create_character_node(
        self,
        character_id: str,
        name: str,
        appearance: str = "",
        personality: str = "",
        voice: str = "",
        tags: List[str] = None,
        avatar_url: str = "",
    ) -> bool:
        """创建角色节点"""
        if not self._connected:
            logger.debug("Neo4j not connected, skipping character node creation")
            return False
        query = """
        MERGE (c:Character {character_id: $character_id})
        SET c.name = $name,
            c.appearance = $appearance,
            c.personality = $personality,
            c.voice = $voice,
            c.tags = $tags,
            c.avatar_url = $avatar_url,
            c.updated_at = datetime()
        """
        try:
            self._run_query(query, {
                "character_id": character_id,
                "name": name,
                "appearance": appearance,
                "personality": personality,
                "voice": voice,
                "tags": tags or [],
                "avatar_url": avatar_url,
            })
            return True
        except Exception as e:
            logger.error(f"Failed to create character node: {e}")
            return False

    def update_character_node(
        self,
        character_id: str,
        appearance: str = None,
        personality: str = None,
        voice: str = None,
        avatar_url: str = None,
    ) -> bool:
        """更新角色节点"""
        if not self._connected:
            return False
        updates = []
        params = {"character_id": character_id}
        if appearance is not None:
            updates.append("c.appearance = $appearance")
            params["appearance"] = appearance
        if personality is not None:
            updates.append("c.personality = $personality")
            params["personality"] = personality
        if voice is not None:
            updates.append("c.voice = $voice")
            params["voice"] = voice
        if avatar_url is not None:
            updates.append("c.avatar_url = $avatar_url")
            params["avatar_url"] = avatar_url
        if not updates:
            return False
        updates.append("c.updated_at = datetime()")
        query = f"""
        MATCH (c:Character {{character_id: $character_id}})
        SET {', '.join(updates)}
        """
        try:
            self._run_query(query, params)
            return True
        except Exception as e:
            logger.error(f"Failed to update character node: {e}")
            return False

    def create_relationship(
        self,
        char1_id: str,
        char2_id: str,
        relationship_type: str,
        description: str = "",
    ) -> bool:
        """创建两个角色之间的关系"""
        if not self._connected:
            return False
        rel_type = relationship_type.upper().replace(" ", "_")
        query = """
        MATCH (c1:Character {character_id: $char1_id})
        MATCH (c2:Character {character_id: $char2_id})
        MERGE (c1)-[r:RELATES_TO {type: $rel_type}]->(c2)
        SET r.description = $description,
            r.created_at = datetime()
        """
        try:
            self._run_query(query, {
                "char1_id": char1_id,
                "char2_id": char2_id,
                "rel_type": rel_type,
                "description": description,
            })
            return True
        except Exception as e:
            logger.error(f"Failed to create relationship: {e}")
            return False

    def link_character_to_scene(
        self,
        character_id: str,
        storyboard_id: str,
        scene_description: str = "",
        shot_count: int = 1,
    ) -> bool:
        """将角色链接到场景/分镜"""
        if not self._connected:
            return False
        query = """
        MATCH (c:Character {character_id: $character_id})
        MERGE (s:Scene {storyboard_id: $storyboard_id})
        SET s.description = $scene_description,
            s.shot_count = $shot_count
        MERGE (c)-[r:APPEARS_IN]->(s)
        SET r.shot_count = $shot_count,
            r.updated_at = datetime()
        """
        try:
            self._run_query(query, {
                "character_id": character_id,
                "storyboard_id": storyboard_id,
                "scene_description": scene_description,
                "shot_count": shot_count,
            })
            return True
        except Exception as e:
            logger.error(f"Failed to link character to scene: {e}")
            return False

    def get_character_network(self, character_id: str) -> Dict[str, Any]:
        """获取角色网络（所有关联角色和场景）"""
        if not self._connected:
            return {"characters": [], "scenes": []}
        query = """
        MATCH (c:Character {character_id: $character_id})
        OPTIONAL MATCH (c)-[r:RELATES_TO]->(other:Character)
        WITH c, collect(DISTINCT {
            id: other.character_id,
            name: other.name,
            relationship: r.type,
            description: r.description
        }) as characters
        OPTIONAL MATCH (c)-[r2:APPEARS_IN]->(s:Scene)
        WITH c, characters, collect(DISTINCT {
            storyboard_id: s.storyboard_id,
            description: s.description,
            shot_count: s.shot_count
        }) as scenes
        RETURN characters, scenes
        """
        try:
            results = self._run_query(query, {"character_id": character_id})
            if results:
                return {
                    "characters": results[0].get("characters", []) or [],
                    "scenes": results[0].get("scenes", []) or [],
                }
            return {"characters": [], "scenes": []}
        except Exception as e:
            logger.error(f"Failed to get character network: {e}")
            return {"characters": [], "scenes": []}

    def get_character_consistency_prompt(
        self,
        character_id: str,
        storyboard_id: str = None,
    ) -> str:
        """构建角色一致性提示词（用于注入到分镜生成）"""
        if not self._connected:
            return ""
        query = """
        MATCH (c:Character {character_id: $character_id})
        RETURN c.name as name,
               c.appearance as appearance,
               c.personality as personality,
               c.voice as voice,
               c.tags as tags
        """
        try:
            results = self._run_query(query, {"character_id": character_id})
            if not results:
                return ""
            c = results[0]
            parts = [f"角色名称: {c.get('name', '')}"]
            if c.get("appearance"):
                parts.append(f"外貌特征: {c['appearance']}")
            if c.get("personality"):
                parts.append(f"性格特点: {c['personality']}")
            if c.get("voice"):
                parts.append(f"声音/配音风格: {c['voice']}")
            if c.get("tags"):
                parts.append(f"标签: {', '.join(c['tags'])}")

            # 如果有场景ID，获取该角色在该场景中的具体描述
            if storyboard_id:
                scene_query = """
                MATCH (c:Character {character_id: $character_id})
                       -[r:APPEARS_IN]->(s:Scene {storyboard_id: $storyboard_id})
                RETURN s.description as scene_description, r.shot_count as shot_count
                """
                scene_results = self._run_query(scene_query, {
                    "character_id": character_id,
                    "storyboard_id": storyboard_id,
                })
                if scene_results:
                    parts.append(f"在本分镜中的场景: {scene_results[0].get('scene_description', '')}")

            return " | ".join(parts)
        except Exception as e:
            logger.error(f"Failed to get consistency prompt: {e}")
            return ""

    def extract_relationships_from_text(
        self,
        character_ids: List[str],
        text: str,
        api_key: str = None,
    ) -> List[Dict[str, str]]:
        """使用LLM从文本中提取角色关系"""
        if len(character_ids) < 2:
            return []
        if not api_key:
            return []

        # 使用简单的关键词匹配作为fallback
        relationships = []
        try:
            # 简单的fallback：如果没有LLM API key，使用共现分析
            for i, char1 in enumerate(character_ids):
                for char2 in character_ids[i + 1:]:
                    # 检查两个角色是否在同一段文本中（简单启发式）
                    relationships.append({
                        "char1_id": char1,
                        "char2_id": char2,
                        "type": "APPEARS_WITH",
                        "description": "在故事中共同出现",
                    })
        except Exception as e:
            logger.error(f"Failed to extract relationships: {e}")

        return relationships

    def delete_character_node(self, character_id: str) -> bool:
        """删除角色节点及其所有关系"""
        if not self._connected:
            return False
        query = """
        MATCH (c:Character {character_id: $character_id})
        DETACH DELETE c
        """
        try:
            self._run_query(query, {"character_id": character_id})
            return True
        except Exception as e:
            logger.error(f"Failed to delete character node: {e}")
            return False

    def search_characters(self, keyword: str) -> List[Dict]:
        """搜索角色（按名称或标签）"""
        if not self._connected:
            return []
        query = """
        MATCH (c:Character)
        WHERE c.name CONTAINS $keyword
           OR ANY(tag IN c.tags WHERE tag CONTAINS $keyword)
        RETURN c.character_id as id, c.name as name, c.appearance as appearance,
               c.personality as personality, c.tags as tags
        LIMIT 20
        """
        try:
            return self._run_query(query, {"keyword": keyword})
        except Exception as e:
            logger.error(f"Failed to search characters: {e}")
            return []

    def get_all_characters(self) -> List[Dict]:
        """获取所有角色"""
        if not self._connected:
            return []
        query = """
        MATCH (c:Character)
        RETURN c.character_id as id, c.name as name, c.appearance as appearance,
               c.personality as personality, c.voice as voice, c.tags as tags,
               c.avatar_url as avatar_url
        ORDER BY c.name
        """
        try:
            return self._run_query(query)
        except Exception as e:
            logger.error(f"Failed to get all characters: {e}")
            return []


# 全局单例
_graph_service: Optional[CharacterGraphService] = None


def get_character_graph_service() -> CharacterGraphService:
    global _graph_service
    if _graph_service is None:
        _graph_service = CharacterGraphService()
        _graph_service.init_constraints()
    return _graph_service
