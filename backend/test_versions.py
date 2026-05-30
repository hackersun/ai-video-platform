"""
版本管理功能测试
"""
import pytest
import asyncio
from uuid import uuid4
from datetime import datetime

# 设置测试环境
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import Base, sync_engine, AsyncSessionLocal, get_db
from app.models.version import Version, VersionRule
from app.services.version_service import (
    create_version,
    list_versions,
    get_version,
    get_version_count,
    get_next_version_number,
    cleanup_old_versions,
    compare_snapshots,
    resource_to_snapshot,
    RESOURCE_TYPES,
    DEFAULT_VERSION_RULES,
)
from app.models.novel import Novel
from app.models.chapter import Chapter


class TestVersionModel:
    """测试 Version 模型"""

    def test_version_to_dict(self):
        """测试 Version 转换为字典"""
        version = Version(
            id=str(uuid4()),
            user_id=str(uuid4()),
            resource_type="novel",
            resource_id=str(uuid4()),
            version_number=1,
            version_label="测试版本",
            change_summary="测试变更摘要",
            created_at=datetime.now(),
            created_by=str(uuid4()),
        )

        result = version.to_dict()

        assert result["id"] == version.id
        assert result["resource_type"] == "novel"
        assert result["version_number"] == 1
        assert result["version_label"] == "测试版本"
        assert result["change_summary"] == "测试变更摘要"

    def test_version_rule_to_dict(self):
        """测试 VersionRule 转换为字典"""
        rule = VersionRule(
            resource_type="novel",
            max_versions=20,
            auto_snapshot=True,
            auto_cleanup=False,
        )

        result = rule.to_dict()

        assert result["resource_type"] == "novel"
        assert result["max_versions"] == 20
        assert result["auto_snapshot"] is True
        assert result["auto_cleanup"] is False


class TestVersionService:
    """测试版本服务"""

    @pytest.fixture
    async def async_db(self):
        """获取异步数据库会话"""
        async with AsyncSessionLocal() as session:
            yield session

    @pytest.fixture
    def sync_db(self):
        """获取同步数据库会话"""
        from app.core.database import SyncSessionLocal
        return SyncSessionLocal()

    def test_resource_types(self):
        """测试支持的资源类型"""
        expected_types = ["novel", "chapter", "script", "storyboard", "shot"]
        assert RESOURCE_TYPES == expected_types

    def test_default_version_rules(self):
        """测试默认版本规则"""
        for resource_type in RESOURCE_TYPES:
            assert resource_type in DEFAULT_VERSION_RULES
            rule = DEFAULT_VERSION_RULES[resource_type]
            assert "max_versions" in rule
            assert "auto_snapshot" in rule
            assert "auto_cleanup" in rule
            assert rule["max_versions"] == 10
            assert rule["auto_snapshot"] is True
            assert rule["auto_cleanup"] is True

    def test_compare_snapshots(self):
        """测试快照比较"""
        old_snapshot = {
            "title": "旧标题",
            "content": "旧内容",
            "status": "draft",
        }
        new_snapshot = {
            "title": "新标题",
            "content": "新内容",
            "status": "completed",
            "tags": ["tag1", "tag2"],
        }

        diff = compare_snapshots(old_snapshot, new_snapshot)

        # 检查新增
        assert "tags" in diff["added"]
        assert diff["added"]["tags"] == ["tag1", "tag2"]

        # 检查未变更
        assert "title" in diff["changed"]
        assert diff["changed"]["title"]["old"] == "旧标题"
        assert diff["changed"]["title"]["new"] == "新标题"

        assert "content" in diff["changed"]
        assert diff["changed"]["content"]["old"] == "旧内容"
        assert diff["changed"]["content"]["new"] == "新内容"

        assert "status" in diff["changed"]
        assert diff["changed"]["status"]["old"] == "draft"
        assert diff["changed"]["status"]["new"] == "completed"

    def test_compare_snapshots_no_changes(self):
        """测试快照比较 - 无变化"""
        snapshot = {
            "title": "标题",
            "content": "内容",
        }

        diff = compare_snapshots(snapshot, snapshot)

        assert len(diff["added"]) == 0
        assert len(diff["removed"]) == 0
        assert len(diff["changed"]) == 0

    def test_compare_snapshots_add_and_remove(self):
        """测试快照比较 - 新增和删除字段"""
        old_snapshot = {"field1": "value1", "field2": "value2"}
        new_snapshot = {"field2": "value2", "field3": "value3"}

        diff = compare_snapshots(old_snapshot, new_snapshot)

        assert "field1" in diff["removed"]
        assert "field3" in diff["added"]
        assert "field2" not in diff["changed"]

    def test_resource_to_snapshot(self):
        """测试资源转快照"""
        # 创建模拟资源对象
        class MockResource:
            id = "test-id"
            user_id = "test-user"
            title = "测试标题"
            content = "测试内容"
            status = "draft"

        resource = MockResource()

        # 使用 mock 的 __table__ 属性
        class MockColumn:
            name: str

        class MockTable:
            columns: list[MockColumn] = [
                type('MockColumn', (), {'name': name})()
                for name in ['id', 'user_id', 'title', 'content', 'status']
            ]

        resource.__table__ = MockTable()

        snapshot = resource_to_snapshot(resource)

        assert snapshot["id"] == "test-id"
        assert snapshot["user_id"] == "test-user"
        assert snapshot["title"] == "测试标题"
        assert snapshot["content"] == "测试内容"
        assert snapshot["status"] == "draft"


class TestVersionAPI:
    """测试版本 API 端点"""

    def test_api_endpoints_configured(self):
        """测试 API 端点配置正确"""
        from app.api.v1.endpoints import versions
        from app.api.v1.router import api_router

        # 验证 versions 路由存在
        routers = [r.path for r in api_router.routes]
        assert "/versions" in routers


if __name__ == "__main__":
    pytest.main([__file__, "-v"])