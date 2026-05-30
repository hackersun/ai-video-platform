"""
ConsistencyChecker 单元测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import asdict

from app.services.consistency_checker import (
    ConsistencyChecker,
    ConsistencyIssue,
    ConsistencyReport
)


class TestConsistencyIssue:
    """测试 ConsistencyIssue 数据类"""

    def test_create_issue(self):
        issue = ConsistencyIssue(
            type="missing_entity_refs",
            severity="warning",
            entity="character_1",
            message="测试问题"
        )
        assert issue.type == "missing_entity_refs"
        assert issue.severity == "warning"
        assert issue.entity == "character_1"
        assert issue.message == "测试问题"

    def test_issue_defaults(self):
        issue = ConsistencyIssue(
            type="test",
            severity="info"
        )
        assert issue.entity is None
        assert issue.expected is None
        assert issue.actual is None
        assert issue.message is None


class TestConsistencyReport:
    """测试 ConsistencyReport 数据类"""

    def test_create_report(self):
        issues = [
            ConsistencyIssue(type="test1", severity="error"),
            ConsistencyIssue(type="test2", severity="warning"),
        ]
        report = ConsistencyReport(shot_id="shot_1", issues=issues)

        assert report.shot_id == "shot_1"
        assert len(report.issues) == 2

    def test_error_count(self):
        issues = [
            ConsistencyIssue(type="test1", severity="error"),
            ConsistencyIssue(type="test2", severity="warning"),
            ConsistencyIssue(type="test3", severity="error"),
            ConsistencyIssue(type="test4", severity="info"),
        ]
        report = ConsistencyReport(shot_id="shot_1", issues=issues)

        assert report.error_count == 2

    def test_warning_count(self):
        issues = [
            ConsistencyIssue(type="test1", severity="error"),
            ConsistencyIssue(type="test2", severity="warning"),
            ConsistencyIssue(type="test3", severity="warning"),
        ]
        report = ConsistencyReport(shot_id="shot_1", issues=issues)

        assert report.warning_count == 2

    def test_info_count(self):
        issues = [
            ConsistencyIssue(type="test1", severity="info"),
            ConsistencyIssue(type="test2", severity="info"),
            ConsistencyIssue(type="test3", severity="warning"),
        ]
        report = ConsistencyReport(shot_id="shot_1", issues=issues)

        assert report.info_count == 2

    def test_has_blocking_issues(self):
        # 有错误
        issues_with_error = [
            ConsistencyIssue(type="test1", severity="error"),
        ]
        report_with_error = ConsistencyReport(shot_id="shot_1", issues=issues_with_error)
        assert report_with_error.has_blocking_issues is True

        # 只有警告
        issues_only_warning = [
            ConsistencyIssue(type="test1", severity="warning"),
        ]
        report_only_warning = ConsistencyReport(shot_id="shot_2", issues=issues_only_warning)
        assert report_only_warning.has_blocking_issues is False

    def test_is_consistent(self):
        # 有阻塞问题
        issues_with_error = [
            ConsistencyIssue(type="test1", severity="error"),
        ]
        report_with_error = ConsistencyReport(shot_id="shot_1", issues=issues_with_error)
        assert report_with_error.is_consistent is False

        # 只有警告 - 应该一致
        issues_only_warning = [
            ConsistencyIssue(type="test1", severity="warning"),
        ]
        report_only_warning = ConsistencyReport(shot_id="shot_2", issues=issues_only_warning)
        assert report_only_warning.is_consistent is True

        # 无问题
        report_clean = ConsistencyReport(shot_id="shot_3", issues=[])
        assert report_clean.is_consistent is True

    def test_empty_report(self):
        report = ConsistencyReport(shot_id="shot_empty")

        assert report.error_count == 0
        assert report.warning_count == 0
        assert report.info_count == 0
        assert report.has_blocking_issues is False
        assert report.is_consistent is True


class TestConsistencyCheckerEntityRefs:
    """测试 ConsistencyChecker 的 entity_refs 检查"""

    @pytest.fixture
    def checker(self):
        return ConsistencyChecker()

    @pytest.mark.asyncio
    async def test_check_entity_refs_missing(self, checker):
        """测试缺少 entity_refs 的情况"""
        shot = MagicMock()
        shot.extra_data = {}

        issues = await checker._check_entity_refs(shot)

        assert len(issues) >= 1
        assert any(i.type == "missing_entity_refs" for i in issues)
        warning = next(i for i in issues if i.type == "missing_entity_refs")
        assert warning.severity == "warning"

    @pytest.mark.asyncio
    async def test_check_entity_refs_empty(self, checker):
        """测试 entity_refs 为空对象的情况"""
        shot = MagicMock()
        shot.extra_data = {"entity_refs": {}}

        issues = await checker._check_entity_refs(shot)

        assert len(issues) >= 1
        assert any(i.type == "missing_entity_refs" for i in issues)

    @pytest.mark.asyncio
    async def test_check_entity_refs_valid(self, checker):
        """测试有效的 entity_refs"""
        shot = MagicMock()
        shot.extra_data = {"entity_refs": {"characters": ["char_1", "char_2"]}}
        shot.character_refs = [{"character_id": "char_1"}]

        issues = await checker._check_entity_refs(shot)

        assert not any(i.type == "missing_entity_refs" for i in issues)

    @pytest.mark.asyncio
    async def test_check_entity_refs_no_character_refs(self, checker):
        """测试缺少角色引用的警告"""
        shot = MagicMock()
        shot.extra_data = {"entity_refs": {"scenes": ["scene_1"]}}
        shot.character_refs = []

        issues = await checker._check_entity_refs(shot)

        assert any(i.type == "missing_character_refs" for i in issues)


class TestConsistencyCheckerCharacterAppearance:
    """测试 ConsistencyChecker 的角色外观检查"""

    @pytest.fixture
    def checker(self):
        return ConsistencyChecker()

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_story_bible(self):
        bible = MagicMock()
        bible.character_rules = [
            {"name": "Alice", "appearance": "long golden hair, blue eyes"},
            {"name": "Bob", "appearance": "tall, muscular build, short black hair"}
        ]
        return bible

    @pytest.mark.asyncio
    async def test_check_character_appearance_missing(self, checker, mock_db, mock_story_bible):
        """测试角色缺少外观描述"""
        shot = MagicMock()
        shot.extra_data = {"entity_refs": {"characters": ["char_1"]}}

        # 模拟实体查询
        mock_entity = MagicMock()
        mock_entity.name = "Alice"
        mock_entity.appearance = None  # 缺少外观

        # _get_entity 返回 awaitable，需要正确处理
        async def mock_get_entity(*args, **kwargs):
            return mock_entity

        checker._get_entity = mock_get_entity

        issues = await checker._check_character_appearance(mock_db, shot, mock_story_bible)

        assert any(i.type == "character_appearance_missing" for i in issues)

    @pytest.mark.asyncio
    async def test_check_character_appearance_mismatch(self, mock_db, mock_story_bible):
        """测试角色外观与Story Bible不匹配 - 使用完全不重叠的词汇"""
        checker = ConsistencyChecker()

        shot = MagicMock()
        shot.extra_data = {"entity_refs": {"characters": ["char_1"]}}

        mock_entity = MagicMock()
        mock_entity.name = "Alice"
        # 使用完全不同的关键词，确保没有共同词
        mock_entity.appearance = "tall man with beard"

        mock_get_entity = AsyncMock(return_value=mock_entity)

        with patch.object(checker, '_get_entity', mock_get_entity):
            issues = await checker._check_character_appearance(mock_db, shot, mock_story_bible)

            # 验证mock被调用
            mock_get_entity.assert_called_once()

            # Story Bible: "long golden hair, blue eyes" -> 5 words
            # Entity: "tall man with beard" -> 4 words
            # 无共同词且expected_words > 3，应触发警告
            assert any(i.type == "character_appearance_mismatch" for i in issues)

    @pytest.mark.asyncio
    async def test_check_character_appearance_no_rules(self, mock_db):
        """测试Story Bible没有角色规则 - 使用空角色列表"""
        checker = ConsistencyChecker()

        shot = MagicMock()
        # 使用空角色列表，这样会直接返回（不进入循环）
        shot.extra_data = {"entity_refs": {"characters": []}}
        shot.character_refs = []

        story_bible = MagicMock()
        story_bible.character_rules = []

        issues = await checker._check_character_appearance(mock_db, shot, story_bible)

        # 空角色列表不会触发_get_entity调用
        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_check_character_appearance_empty_chars(self, mock_db):
        """测试角色列表为空的情况"""
        checker = ConsistencyChecker()

        shot = MagicMock()
        shot.extra_data = {"entity_refs": {"characters": []}}
        shot.character_refs = []

        story_bible = MagicMock()
        story_bible.character_rules = [{"name": "Alice", "appearance": "blonde hair"}]

        issues = await checker._check_character_appearance(mock_db, shot, story_bible)

        # 角色列表为空，不应该有检查
        assert len(issues) == 0


class TestConsistencyCheckerLockedAssets:
    """测试 ConsistencyChecker 的锁定资产检查"""

    @pytest.fixture
    def checker(self):
        return ConsistencyChecker()

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_check_unlocked_asset_reference(self, checker, mock_db):
        """测试使用参考图但未锁定"""
        shot = MagicMock()
        shot.image_url = "https://example.com/image.png"
        shot.image_asset_id = None
        shot.extra_data = {}

        issues = await checker._check_locked_assets(mock_db, shot)

        assert any(i.type == "unlocked_asset_reference" for i in issues)

    @pytest.mark.asyncio
    async def test_check_asset_not_locked(self, checker, mock_db):
        """测试资产未锁定"""
        shot = MagicMock()
        shot.image_url = "https://example.com/image.png"
        shot.image_asset_id = "asset_123"
        shot.extra_data = {}

        mock_asset = MagicMock()
        mock_asset.name = "Test Asset"
        mock_asset.is_locked = False

        mock_db.execute = AsyncMock(return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=mock_asset)
        ))

        issues = await checker._check_locked_assets(mock_db, shot)

        assert any(i.type == "asset_not_locked" for i in issues)

    @pytest.mark.asyncio
    async def test_check_asset_locked(self, checker, mock_db):
        """测试资产已锁定"""
        shot = MagicMock()
        shot.image_url = "https://example.com/image.png"
        shot.image_asset_id = "asset_123"
        shot.extra_data = {}

        mock_asset = MagicMock()
        mock_asset.name = "Test Asset"
        mock_asset.is_locked = True

        mock_db.execute = AsyncMock(return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=mock_asset)
        ))

        issues = await checker._check_locked_assets(mock_db, shot)

        assert not any(i.type == "asset_not_locked" for i in issues)

    @pytest.mark.asyncio
    async def test_check_no_image_url(self, checker, mock_db):
        """测试没有参考图的情况"""
        shot = MagicMock()
        shot.image_url = None
        shot.image_asset_id = None
        shot.extra_data = {}

        issues = await checker._check_locked_assets(mock_db, shot)

        assert not any(i.type == "unlocked_asset_reference" for i in issues)


class TestConsistencyCheckerTTSVoice:
    """测试 ConsistencyChecker 的TTS音色一致性检查"""

    @pytest.fixture
    def checker(self):
        return ConsistencyChecker()

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_story_bible(self):
        bible = MagicMock()
        bible.id = "bible_1"
        bible.character_rules = [
            {"name": "Alice", "voice": "Crystal_Clear"}
        ]
        return bible

    @pytest.mark.asyncio
    async def test_check_tts_voice_drift(self, checker, mock_db, mock_story_bible):
        """测试TTS音色偏离"""
        shot = MagicMock()
        shot.extra_data = {"tts_job_id": "tts_1"}

        mock_tts_job = MagicMock()
        mock_tts_job.voice = "Deep_Voice"  # 与Story Bible不一致
        mock_tts_job.character_id = "char_1"
        mock_tts_job.character_name = None

        mock_entity = MagicMock()
        mock_entity.name = "Alice"

        # 跟踪调用次数以返回不同结果
        call_count = [0]
        async def mock_execute(*args, **kwargs):
            result = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                # 第一次调用 - TTSJob查询
                result.scalar_one_or_none = MagicMock(return_value=mock_tts_job)
            else:
                # 第二次调用 - StoryEntity查询
                result.scalar_one_or_none = MagicMock(return_value=mock_entity)
            return result

        mock_db.execute = AsyncMock(side_effect=mock_execute)

        # Mock voice_service
        with patch('app.services.consistency_checker.get_character_voice_from_story_bible') as mock_voice:
            mock_voice.return_value = {"voice": "Crystal_Clear"}

            issues = await checker._check_tts_voice_consistency(mock_db, shot, mock_story_bible)

            assert any(i.type == "tts_voice_drift" for i in issues)
            drift_issue = next(i for i in issues if i.type == "tts_voice_drift")
            assert drift_issue.severity == "error"
            assert drift_issue.expected == "Crystal_Clear"
            assert drift_issue.actual == "Deep_Voice"

    @pytest.mark.asyncio
    async def test_check_tts_voice_match(self, checker, mock_db, mock_story_bible):
        """测试TTS音色匹配"""
        shot = MagicMock()
        shot.extra_data = {"tts_job_id": "tts_1"}

        mock_tts_job = MagicMock()
        mock_tts_job.voice = "Crystal_Clear"  # 与Story Bible一致
        mock_tts_job.character_id = "char_1"
        mock_tts_job.character_name = None

        mock_entity = MagicMock()
        mock_entity.name = "Alice"

        call_count = [0]
        async def mock_execute(*args, **kwargs):
            result = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                result.scalar_one_or_none = MagicMock(return_value=mock_tts_job)
            else:
                result.scalar_one_or_none = MagicMock(return_value=mock_entity)
            return result

        mock_db.execute = AsyncMock(side_effect=mock_execute)

        with patch('app.services.consistency_checker.get_character_voice_from_story_bible') as mock_voice:
            mock_voice.return_value = {"voice": "Crystal_Clear"}

            issues = await checker._check_tts_voice_consistency(mock_db, shot, mock_story_bible)

            assert not any(i.type == "tts_voice_drift" for i in issues)


class TestConsistencyCheckerFullCheck:
    """测试 ConsistencyChecker 的完整检查"""

    @pytest.fixture
    def checker(self):
        return ConsistencyChecker()

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_check_shot_consistency_full(self, checker, mock_db):
        """测试完整的一致性检查"""
        shot = MagicMock()
        shot.id = "shot_test_1"
        shot.extra_data = {}
        shot.character_refs = []
        shot.image_url = "https://example.com/image.png"
        shot.image_asset_id = None

        story_bible = MagicMock()
        story_bible.character_rules = []
        story_bible.id = "bible_1"

        report = await checker.check_shot_consistency(mock_db, shot, story_bible)

        assert report.shot_id == "shot_test_1"
        assert len(report.issues) > 0  # 应该有警告
        assert report.warning_count > 0

    @pytest.mark.asyncio
    async def test_check_batch_consistency(self, checker, mock_db):
        """测试批量一致性检查"""
        shots = [
            MagicMock(id="shot_1"),
            MagicMock(id="shot_2"),
            MagicMock(id="shot_3"),
        ]
        for shot in shots:
            shot.extra_data = {}
            shot.character_refs = []
            shot.image_url = None
            shot.image_asset_id = None

        results = await checker.check_batch_consistency(mock_db, shots)

        assert len(results) == 3
        assert "shot_1" in results
        assert "shot_2" in results
        assert "shot_3" in results

    @pytest.mark.asyncio
    async def test_get_consistency_summary(self, checker, mock_db):
        """测试一致性汇总信息"""
        shots = [
            MagicMock(id="shot_1"),
            MagicMock(id="shot_2"),
        ]
        for shot in shots:
            shot.extra_data = {}
            shot.character_refs = []
            shot.image_url = None
            shot.image_asset_id = None

        summary = await checker.get_consistency_summary(mock_db, shots)

        assert "total_shots" in summary
        assert "consistent_shots" in summary
        assert "consistency_rate" in summary
        assert summary["total_shots"] == 2
        assert summary["total_shots"] == summary["consistent_shots"] + summary["inconsistent_shots"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])