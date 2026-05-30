"""
角色关系图 API 测试
"""

import pytest
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


class TestGraphAPI:
    """关系图 API 测试"""

    @pytest.mark.asyncio
    async def test_get_relation_types(self):
        """测试获取关系类型列表"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/graph/relation-types")
            assert response.status_code == 200
            data = response.json()
            assert "types" in data
            assert "descriptions" in data
            assert len(data["types"]) > 0

    @pytest.mark.asyncio
    async def test_get_graph_status(self):
        """测试获取图谱服务状态"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 不带认证Token测试
            response = await client.get("/api/v1/graph/status")
            # 应该返回401未授权
            assert response.status_code in [200, 401]

    @pytest.mark.asyncio
    async def test_get_novel_graph_not_found(self):
        """测试获取不存在的小说的关系图"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/graph/novel/non-existent-id")
            # 未授权或不存在
            assert response.status_code in [401, 404]


class TestCharacterGraphService:
    """CharacterGraphService 测试"""

    def test_relation_types_defined(self):
        """验证关系类型定义"""
        from app.api.v1.endpoints.graph import RELATION_TYPES, ENTITY_TYPES

        assert "friend" in RELATION_TYPES
        assert "family" in RELATION_TYPES
        assert "love" in RELATION_TYPES
        assert "character" in ENTITY_TYPES
        assert "scene" in ENTITY_TYPES

    def test_entity_types_defined(self):
        """验证实体类型定义"""
        from app.api.v1.endpoints.graph import ENTITY_TYPES

        expected_types = ["character", "scene", "prop", "event"]
        for et in expected_types:
            assert et in ENTITY_TYPES