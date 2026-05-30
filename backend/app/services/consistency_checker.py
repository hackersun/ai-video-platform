"""
一致性检查器 - 检查镜头角色外观、锁定资产、TTS音色一致性
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Shot, StoryBible, StoryEntity, Asset, TTSJob
from app.services.voice_service import get_character_voice_from_story_bible


@dataclass
class ConsistencyIssue:
    """一致性问题的数据类"""
    type: str
    severity: str  # error, warning, info
    entity: Optional[str] = None
    expected: Optional[str] = None
    actual: Optional[str] = None
    message: Optional[str] = None


@dataclass
class ConsistencyReport:
    """一致性检查报告"""
    shot_id: str
    issues: List[ConsistencyIssue] = field(default_factory=list)

    @property
    def is_consistent(self) -> bool:
        return not self.has_blocking_issues

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")

    @property
    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "info")

    @property
    def has_blocking_issues(self) -> bool:
        return self.error_count > 0


class ConsistencyChecker:
    """一致性检查器"""

    def __init__(self):
        pass

    async def check_shot_consistency(
        self,
        db: AsyncSession,
        shot: Shot,
        story_bible: Optional[StoryBible] = None
    ) -> ConsistencyReport:
        """
        检查镜头一致性

        Args:
            db: 数据库会话
            shot: 要检查的镜头
            story_bible: 关联的Story Bible（可选）

        Returns:
            ConsistencyReport: 一致性检查报告
        """
        issues: List[ConsistencyIssue] = []

        # 1. 检查entity_refs是否填充
        issues.extend(await self._check_entity_refs(shot))

        # 2. 检查角色外观是否与Story Bible一致
        if story_bible:
            issues.extend(await self._check_character_appearance(db, shot, story_bible))

        # 3. 检查是否使用锁定资产
        issues.extend(await self._check_locked_assets(db, shot))

        # 4. 检查TTS音色一致性
        if story_bible:
            issues.extend(await self._check_tts_voice_consistency(db, shot, story_bible))

        return ConsistencyReport(
            shot_id=shot.id,
            issues=issues
        )

    async def _check_entity_refs(self, shot: Shot) -> List[ConsistencyIssue]:
        """检查entity_refs是否填充"""
        issues: List[ConsistencyIssue] = []

        entity_refs = shot.extra_data.get("entity_refs", {}) if shot.extra_data else {}

        # 检查是否为空
        if not entity_refs or not any(entity_refs.values()):
            issues.append(ConsistencyIssue(
                type="missing_entity_refs",
                severity="warning",
                message="镜头缺少实体引用，可能影响一致性"
            ))
            return issues

        # 检查角色引用
        character_refs = shot.character_refs or []
        if not character_refs:
            issues.append(ConsistencyIssue(
                type="missing_character_refs",
                severity="warning",
                message="镜头缺少角色引用"
            ))

        return issues

    async def _check_character_appearance(
        self,
        db: AsyncSession,
        shot: Shot,
        story_bible: StoryBible
    ) -> List[ConsistencyIssue]:
        """检查角色外观是否与Story Bible一致"""
        issues: List[ConsistencyIssue] = []

        entity_refs = shot.extra_data.get("entity_refs", {}) if shot.extra_data else {}
        character_refs = entity_refs.get("characters", [])

        if not character_refs:
            return issues

        character_rules = {r.get("name"): r for r in (story_bible.character_rules or [])}

        for char_ref in character_refs:
            # 支持两种格式：直接是entity_id或者{"character_id": "...", "name": "..."}
            char_id = char_ref if isinstance(char_ref, str) else char_ref.get("character_id")

            if not char_id:
                continue

            entity = await self._get_entity(db, char_id)
            if entity and entity.name in character_rules:
                rule = character_rules[entity.name]
                expected_appearance = rule.get("appearance")
                actual_appearance = entity.appearance

                # 检查外观描述是否完整
                if expected_appearance and not actual_appearance:
                    issues.append(ConsistencyIssue(
                        type="character_appearance_missing",
                        severity="warning",
                        entity=entity.name,
                        message=f"角色 {entity.name} 缺少外观描述"
                    ))

                # 检查外观是否匹配Story Bible
                if expected_appearance and actual_appearance:
                    expected_words = set(expected_appearance.lower().split())
                    actual_words = set(actual_appearance.lower().split())
                    common_words = expected_words & actual_words

                    # 如果完全无重叠，给出警告
                    if len(common_words) == 0 and len(expected_words) > 3:
                        issues.append(ConsistencyIssue(
                            type="character_appearance_mismatch",
                            severity="warning",
                            entity=entity.name,
                            expected=expected_appearance[:100] + "..." if len(expected_appearance) > 100 else expected_appearance,
                            actual=actual_appearance[:100] + "..." if len(actual_appearance) > 100 else actual_appearance,
                            message=f"角色 {entity.name} 的外观描述与Story Bible不一致"
                        ))

        return issues

    async def _check_locked_assets(
        self,
        db: AsyncSession,
        shot: Shot
    ) -> List[ConsistencyIssue]:
        """检查是否使用锁定资产"""
        issues: List[ConsistencyIssue] = []

        # 检查是否有参考图但未锁定
        if shot.image_url and not shot.image_asset_id:
            # 检查extra_data中的locked_assets
            locked_assets = shot.extra_data.get("locked_assets", {}) if shot.extra_data else {}
            if not locked_assets:
                issues.append(ConsistencyIssue(
                    type="unlocked_asset_reference",
                    severity="warning",
                    message="镜头使用了参考图但未锁定资产版本"
                ))

        # 如果有image_asset_id，检查该资产是否已锁定
        if shot.image_asset_id:
            asset = await self._get_asset(db, shot.image_asset_id)
            if asset and not asset.is_locked:
                issues.append(ConsistencyIssue(
                    type="asset_not_locked",
                    severity="info",
                    entity=asset.name,
                    message=f"资产 {asset.name} 尚未锁定"
                ))

        return issues

    async def _check_tts_voice_consistency(
        self,
        db: AsyncSession,
        shot: Shot,
        story_bible: StoryBible
    ) -> List[ConsistencyIssue]:
        """检查TTS音色一致性"""
        issues: List[ConsistencyIssue] = []

        # 从extra_data获取TTS作业ID
        extra_data = shot.extra_data or {}
        tts_job_id = extra_data.get("tts_job_id")

        if not tts_job_id:
            return issues

        tts_job = await self._get_tts_job(db, tts_job_id)
        if not tts_job:
            return issues

        # 获取角色名称
        character_name = None
        if tts_job.character_id:
            character = await self._get_entity(db, tts_job.character_id)
            if character:
                character_name = character.name

        # 如果没有找到角色名，无法检查
        if not character_name:
            return issues

        # 从Story Bible获取期望的音色
        bible_voice = await get_character_voice_from_story_bible(
            db, character_name, story_bible.id
        )

        if not bible_voice:
            # Story Bible中没有定义该角色的音色配置，不算错误
            return issues

        bible_voice_name = bible_voice.get("voice", "")
        if not bible_voice_name:
            return issues

        # 比较实际使用的音色
        actual_voice = tts_job.voice or "default"
        if bible_voice_name != actual_voice:
            issues.append(ConsistencyIssue(
                type="tts_voice_drift",
                severity="error",
                entity=character_name,
                expected=bible_voice_name,
                actual=actual_voice,
                message=f"角色 {character_name} 的TTS音色与Story Bible不一致"
            ))

        return issues

    async def _get_entity(self, db: AsyncSession, entity_id: str) -> Optional[StoryEntity]:
        """获取StoryEntity"""
        result = await db.execute(
            select(StoryEntity).where(StoryEntity.id == entity_id)
        )
        return result.scalar_one_or_none()

    async def _get_tts_job(self, db: AsyncSession, tts_job_id: str) -> Optional[TTSJob]:
        """获取TTSJob"""
        result = await db.execute(
            select(TTSJob).where(TTSJob.id == tts_job_id)
        )
        return result.scalar_one_or_none()

    async def _get_asset(self, db: AsyncSession, asset_id: str) -> Optional[Asset]:
        """获取Asset"""
        result = await db.execute(
            select(Asset).where(Asset.id == asset_id)
        )
        return result.scalar_one_or_none()

    async def check_batch_consistency(
        self,
        db: AsyncSession,
        shots: List[Shot],
        story_bible: Optional[StoryBible] = None
    ) -> Dict[str, ConsistencyReport]:
        """
        批量检查多个镜头的一致性

        Args:
            db: 数据库会话
            shots: 要检查的镜头列表
            story_bible: 关联的Story Bible（可选）

        Returns:
            Dict[str, ConsistencyReport]: shot_id到检查报告的映射
        """
        results = {}
        for shot in shots:
            results[shot.id] = await self.check_shot_consistency(db, shot, story_bible)
        return results

    async def get_consistency_summary(
        self,
        db: AsyncSession,
        shots: List[Shot],
        story_bible: Optional[StoryBible] = None
    ) -> Dict[str, Any]:
        """
        获取一致性检查汇总信息

        Args:
            db: 数据库会话
            shots: 要检查的镜头列表
            story_bible: 关联的Story Bible（可选）

        Returns:
            Dict: 包含统计信息的汇总字典
        """
        reports = await self.check_batch_consistency(db, shots, story_bible)

        total_shots = len(reports)
        consistent_shots = sum(1 for r in reports.values() if r.is_consistent)
        total_errors = sum(r.error_count for r in reports.values())
        total_warnings = sum(r.warning_count for r in reports.values())
        total_infos = sum(r.info_count for r in reports.values())

        # 按问题类型统计
        issues_by_type: Dict[str, int] = {}
        for report in reports.values():
            for issue in report.issues:
                issues_by_type[issue.type] = issues_by_type.get(issue.type, 0) + 1

        return {
            "total_shots": total_shots,
            "consistent_shots": consistent_shots,
            "inconsistent_shots": total_shots - consistent_shots,
            "consistency_rate": consistent_shots / total_shots if total_shots > 0 else 1.0,
            "total_errors": total_errors,
            "total_warnings": total_warnings,
            "total_infos": total_infos,
            "issues_by_type": issues_by_type,
            "reports": {shot_id: {
                "is_consistent": r.is_consistent,
                "error_count": r.error_count,
                "warning_count": r.warning_count,
                "issues": [
                    {
                        "type": i.type,
                        "severity": i.severity,
                        "entity": i.entity,
                        "message": i.message
                    } for i in r.issues
                ]
            } for shot_id, r in reports.items()}
        }