"""Shot quality and budget estimation helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from app.core.model_registry import get_task_default
from app.services.ai_generation_feedback import build_ai_generation_feedback

# 最大时长阈值（秒）
MAX_SHOT_DURATION = 15
# 台词最大字数
MAX_DIALOGUE_CHARS = 300


class IssueSeverity(str, Enum):
    """问题严重程度"""
    ERROR = "error"      # 阻塞性问题
    WARNING = "warning"  # 警告
    INFO = "info"        # 提示


class IssueType(str, Enum):
    """问题类型"""
    MISSING_PROMPT = "missing_prompt"
    MISSING_IMAGE = "missing_image"
    DURATION_TOO_LONG = "duration_too_long"
    DIALOGUE_TOO_LONG = "dialogue_too_long"
    MISSING_CHARACTER_REFS = "missing_character_refs"
    MISSING_SCENE_REFS = "missing_scene_refs"
    MISSING_PROP_REFS = "missing_prop_refs"
    MISSING_EVENT_REFS = "missing_event_refs"
    MISSING_KEYFRAMES = "missing_keyframes"
    MISSING_DIALOGUE = "missing_dialogue"
    NO_REVIEW_APPROVED = "no_review_approved"


@dataclass
class QualityIssue:
    """单个质量问题"""
    type: str
    severity: str
    message: str
    field: Optional[str] = None
    current_value: Optional[Any] = None
    recommended_value: Optional[Any] = None

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "severity": self.severity,
            "message": self.message,
            "field": self.field,
            "current_value": self.current_value,
            "recommended_value": self.recommended_value,
        }


@dataclass
class QualityReport:
    """镜头质量报告"""
    shot_id: str
    score: int
    status: str  # blocked, warning, ready
    issues: List[QualityIssue] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    summary: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "shot_id": self.shot_id,
            "score": self.score,
            "status": self.status,
            "issues": [issue.to_dict() for issue in self.issues],
            "blockers": self.blockers,
            "warnings": self.warnings,
            "suggestions": self.suggestions,
            "summary": self.summary,
            "metadata": self.metadata,
        }


@dataclass
class StoryboardQualitySummary:
    """分镜质量汇总"""
    storyboard_id: str
    total_shots: int
    avg_score: float
    shots_by_status: Dict[str, int] = field(default_factory=dict)
    error_count: int = 0
    warning_count: int = 0
    ready_count: int = 0
    blocked_shots: List[dict] = field(default_factory=list)
    warning_shots: List[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "storyboard_id": self.storyboard_id,
            "total_shots": self.total_shots,
            "avg_score": round(self.avg_score, 1),
            "shots_by_status": self.shots_by_status,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "ready_count": self.ready_count,
            "blocked_shots": self.blocked_shots,
            "warning_shots": self.warning_shots,
        }


def _has_text(value: Optional[str]) -> bool:
    return bool(value and str(value).strip())


def _names_from_refs(refs: Any) -> List[str]:
    if not isinstance(refs, list):
        return []
    names: List[str] = []
    for item in refs:
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("character_name") or item.get("title") or "").strip()
        else:
            name = str(item or "").strip()
        if name and name not in names:
            names.append(name)
    return names


class ShotQualityService:
    """镜头质量检查服务"""

    def __init__(self, max_retry: int = 3):
        self.max_retry = max_retry

    def check_shot_quality(self, shot: Any) -> QualityReport:
        """
        检查镜头质量

        检测项：
        1. 空prompt检测 - 检测shot.prompt为空
        2. 缺参考图提示 - 检测shot.image_url为空
        3. 时长不匹配检测 - 检测shot.duration超过15秒
        4. 台词过长警告 - 检测dialogue超过300字
        5. 无角色资产警告 - 检测scene/prop无关联资产
        """
        issues: List[QualityIssue] = []
        blockers: List[str] = []
        warnings: List[str] = []
        suggestions: List[str] = []
        extra_data = getattr(shot, "extra_data", None) if isinstance(getattr(shot, "extra_data", None), dict) else {}

        # 1. 空prompt检测 - ERROR
        prompt = getattr(shot, "prompt", None) or ""
        visual_description = getattr(shot, "visual_description", None) or ""
        if not _has_text(prompt) and not _has_text(visual_description):
            blockers.append("缺少视频提示词和视觉描述，无法稳定生成镜头视频")
            issues.append(QualityIssue(
                type=IssueType.MISSING_PROMPT,
                severity=IssueSeverity.ERROR,
                message="镜头缺少生成提示词（prompt）和视觉描述",
                field="prompt",
                current_value=None,
                recommended_value="请填写清晰的镜头描述"
            ))

        # 2. 缺参考图提示 - WARNING
        image_url = getattr(shot, "image_url", None)
        if not image_url or not image_url.strip():
            warnings.append("当前镜头没有参考图，可能影响角色/场景一致性")
            issues.append(QualityIssue(
                type=IssueType.MISSING_IMAGE,
                severity=IssueSeverity.WARNING,
                message="镜头缺少参考图，可能影响画面一致性",
                field="image_url",
                current_value=None,
                recommended_value="建议为镜头生成或上传参考图"
            ))

        # 3. 时长不匹配检测 - WARNING
        duration = getattr(shot, "duration", None)
        if duration and duration > MAX_SHOT_DURATION:
            warnings.append(f"镜头时长{duration}秒超过推荐值{MAX_SHOT_DURATION}秒")
            issues.append(QualityIssue(
                type=IssueType.DURATION_TOO_LONG,
                severity=IssueSeverity.WARNING,
                message=f"镜头时长{duration}秒超过推荐值{MAX_SHOT_DURATION}秒，可能影响生成质量",
                field="duration",
                current_value=duration,
                recommended_value=MAX_SHOT_DURATION
            ))

        # 4. 台词过长警告 - WARNING
        dialogue = getattr(shot, "dialogue", None) or ""
        subtitle_text = (((getattr(shot, "extra_data", None) or {}).get("subtitle_text")) if isinstance(getattr(shot, "extra_data", None), dict) else None or dialogue
        if len(dialogue) > MAX_DIALOGUE_CHARS:
            warnings.append(f"对白过长（{len(dialogue)}字），可能影响配音节奏")
            issues.append(QualityIssue(
                type=IssueType.DIALOGUE_TOO_LONG,
                severity=IssueSeverity.WARNING,
                message=f"对白过长（{len(dialogue)}字），建议控制在{MAX_DIALOGUE_CHARS}字以内",
                field="dialogue",
                current_value=len(dialogue),
                recommended_value=MAX_DIALOGUE_CHARS
            ))

        # 5. 缺少台词提示
        if not _has_text(dialogue) and not _has_text(extra_data.get("subtitle_text")):
            warnings.append("当前镜头没有台词或字幕文本，生成后可能没有对白轨")
            issues.append(QualityIssue(
                type=IssueType.MISSING_DIALOGUE,
                severity=IssueSeverity.INFO,
                message="当前镜头没有台词或字幕文本",
                field="dialogue"
            ))

        # 6. 关键帧检查 - WARNING
        keyframes = getattr(shot, "keyframes", None) or []
        if not isinstance(keyframes, list) or len(keyframes) == 0:
            warnings.append("未设置关键帧，长镜头一致性可能较弱")
            suggestions.append("为镜头补充 start/end/keyframe 参考")
            issues.append(QualityIssue(
                type=IssueType.MISSING_KEYFRAMES,
                severity=IssueSeverity.WARNING,
                message="未设置关键帧，长镜头一致性可能较弱",
                field="keyframes",
                current_value=None,
                recommended_value="建议添加关键帧配置"
            ))

        # 7. 角色引用检查 - WARNING
        character_refs = getattr(shot, "character_refs", None) or []
        if not isinstance(character_refs, list) or len(character_refs) == 0:
            warnings.append("未显式绑定角色引用，可能退化为通用角色生成")
            issues.append(QualityIssue(
                type=IssueType.MISSING_CHARACTER_REFS,
                severity=IssueSeverity.WARNING,
                message="未显式绑定角色引用，可能退化为通用角色生成",
                field="character_refs",
                current_value=None,
                recommended_value="建议绑定角色引用"
            ))

        # 8. 场景/道具/事件引用检查
        entity_refs = extra_data.get("entity_refs") if isinstance(extra_data.get("entity_refs"), dict) else {}
        if not _names_from_refs(entity_refs.get("scenes")):
            warnings.append("缺少场景引用，场景一致性较弱")
            issues.append(QualityIssue(
                type=IssueType.MISSING_SCENE_REFS,
                severity=IssueSeverity.WARNING,
                message="缺少场景引用，场景一致性较弱",
                field="entity_refs.scenes"
            ))
        if not _names_from_refs(entity_refs.get("props")):
            warnings.append("缺少道具引用，道具状态可能不一致")
            issues.append(QualityIssue(
                type=IssueType.MISSING_PROP_REFS,
                severity=IssueSeverity.WARNING,
                message="缺少道具引用，道具状态可能不一致",
                field="entity_refs.props"
            ))
        if not _names_from_refs(entity_refs.get("events")):
            warnings.append("缺少事件引用，镜头与小说事件的衔接可能偏弱")
            issues.append(QualityIssue(
                type=IssueType.MISSING_EVENT_REFS,
                severity=IssueSeverity.WARNING,
                message="缺少事件引用，镜头与小说事件的衔接可能偏弱",
                field="entity_refs.events"
            ))

        # 9. 审核状态检查
        production_context = extra_data.get("production_context") if isinstance(extra_data.get("production_context"), dict) else {}
        review_state = production_context.get("review_state") or extra_data.get("review_state") or "pending_review"
        if review_state not in {"approved", "locked"}:
            suggestions.append("完成镜头审核后再进入批量生成或真实渲染")
            issues.append(QualityIssue(
                type=IssueType.NO_REVIEW_APPROVED,
                severity=IssueSeverity.INFO,
                message="镜头尚未完成审核",
                field="production_context.review_state",
                current_value=review_state,
                recommended_value="approved or locked"
            ))

        # 计算质量分数
        score = 100
        score -= 20 if blockers else 0
        score -= min(35, len(warnings) * 6)
        score = max(0, score)

        shot_id = str(getattr(shot, "id", "unknown"))
        status = "blocked" if blockers else ("warning" if warnings else "ready")

        return QualityReport(
            shot_id=shot_id,
            score=score,
            status=status,
            issues=issues,
            blockers=blockers,
            warnings=warnings,
            suggestions=suggestions,
            summary=build_ai_generation_feedback(
                stage="shot_quality_check",
                message="镜头质量检查完成",
                context={
                    "novel_id": extra_data.get("novel_id"),
                    "chapter_id": extra_data.get("chapter_id"),
                    "title": prompt or visual_description,
                    "characters": character_refs,
                    "scenes": entity_refs.get("scenes") or [],
                    "props": entity_refs.get("props") or [],
                    "events": entity_refs.get("events") or [],
                },
                warnings=warnings,
                extra={
                    "score": score,
                    "status": status,
                    "issue_count": len(issues),
                    "has_image": bool(image_url),
                    "duration": duration,
                },
            ),
            metadata={
                "has_prompt": bool(_has_text(prompt)),
                "has_visual_description": bool(_has_text(visual_description)),
                "has_image": bool(image_url),
                "has_keyframes": bool(keyframes),
                "has_character_refs": bool(character_refs),
                "has_dialogue": bool(_has_text(dialogue)),
                "duration": duration,
                "dialogue_length": len(dialogue),
            }
        )

    def check_shot_quality_simple(self, shot: Any) -> Dict[str, Any]:
        """检查镜头质量，返回字典格式（向后兼容）"""
        report = self.check_shot_quality(shot)
        return report.to_dict()

    async def auto_retry_video(
        self,
        db: Any,
        shot_id: str,
        user_id: str,
        max_attempts: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        自动重试失败的视频生成

        最多重试指定次数，默认使用 self.max_retry
        通过 VideoGenerateRequest 提交新任务

        Returns:
            Dict包含:
            - success: bool
            - job_id: str 或 None
            - task_id: str 或 None
            - attempts: int
            - message: str
        """
        from sqlalchemy import select, and_
        from app.models import Shot
        from app.api.v1.endpoints.video import VideoGenerateRequest, generate_video
        import uuid

        max_attempts = max_attempts or self.max_retry
        result = await db.execute(
            select(Shot).where(and_(Shot.id == shot_id, Shot.user_id == user_id))
        )
        shot = result.scalar_one_or_none()
        if not shot:
            return {
                "success": False,
                "job_id": None,
                "task_id": None,
                "attempts": 0,
                "message": "镜头不存在"
            }

        if shot.video_status == "succeeded":
            return {
                "success": True,
                "job_id": None,
                "task_id": None,
                "attempts": 0,
                "message": "视频已生成成功，无需重试"
            }

        extra_data = shot.extra_data if isinstance(shot.extra_data, dict) else {}
        retry_count = (extra_data.get("video_retry_count") or 0)
        if retry_count >= max_attempts:
            return {
                "success": False,
                "job_id": None,
                "task_id": None,
                "attempts": retry_count,
                "message": f"已达最大重试次数({max_attempts})，请手动检查问题"
            }

        prompt = shot.prompt or shot.visual_description or "shot video"
        request = VideoGenerateRequest(
            prompt=prompt,
            duration=shot.duration or 4,
            shot_id=shot_id,
            storyboard_id=shot.storyboard_id,
            image_url=shot.image_url,
            use_consistency_context=True,
        )

        try:
            response = await generate_video(request, db, user_id)

            shot.extra_data = {
                **extra_data,
                "video_retry_count": retry_count + 1,
                "last_retry_at": str(uuid.uuid4()),
                "retry_attempt": retry_count + 1,
            }
            shot.video_status = "pending"
            await db.commit()

            return {
                "success": True,
                "job_id": response.job_id,
                "task_id": response.task_id,
                "attempts": retry_count + 1,
                "message": "视频重试任务已提交"
            }
        except Exception as e:
            return {
                "success": False,
                "job_id": None,
                "task_id": None,
                "attempts": retry_count,
                "message": f"视频重试失败: {str(e)}"
            }


def build_storyboard_quality_summary(storyboard_id: str, shots: List[Any]) -> StoryboardQualitySummary:
    """
    构建分镜质量汇总

    遍历所有镜头，汇总质量检查结果
    """
    service = ShotQualityService()

    total_score = 0
    error_count = 0
    warning_count = 0
    ready_count = 0
    status_counts: Dict[str, int] = {}
    blocked_shots: List[dict] = []
    warning_shots: List[dict] = []

    for shot in shots:
        report = service.check_shot_quality(shot)
        total_score += report.score

        status = report.status
        status_counts[status] = status_counts.get(status, 0) + 1

        if status == "blocked":
            error_count += 1
            blocked_shots.append({
                "shot_id": report.shot_id,
                "shot_number": getattr(shot, "shot_number", 0),
                "score": report.score,
                "blockers": report.blockers,
                "issues": [i.to_dict() for i in report.issues if i.severity == IssueSeverity.ERROR]
            })
        elif status == "warning":
            warning_count += 1
            warning_shots.append({
                "shot_id": report.shot_id,
                "shot_number": getattr(shot, "shot_number", 0),
                "score": report.score,
                "warnings": report.warnings,
                "issues": [i.to_dict() for i in report.issues if i.severity == IssueSeverity.WARNING]
            })
        else:
            ready_count += 1

    total_shots = len(shots)
    avg_score = total_score / total_shots if total_shots > 0 else 0

    return StoryboardQualitySummary(
        storyboard_id=storyboard_id,
        total_shots=total_shots,
        avg_score=avg_score,
        shots_by_status=status_counts,
        error_count=error_count,
        warning_count=warning_count,
        ready_count=ready_count,
        blocked_shots=blocked_shots,
        warning_shots=warning_shots,
    )


def estimate_shot_generation_budget(shot: Any) -> Dict[str, Any]:
    duration = int(getattr(shot, "duration", 4) or 4)
    dialogue = getattr(shot, "dialogue", None) or ""
    prompt = getattr(shot, "prompt", None) or ""
    visual_description = getattr(shot, "visual_description", None) or ""
    subtitle_text = (((getattr(shot, "extra_data", None) or {}).get("subtitle_text")) if isinstance(getattr(shot, "extra_data", None), dict) else None) or dialogue
    shot_video_default = get_task_default("shot_video") or {}
    shot_audio_video_default = get_task_default("shot_audio_video") or {}

    video_capabilities = shot_video_default.get("default_model", {}).get("capabilities", [])
    av_capabilities = shot_audio_video_default.get("default_model", {}).get("capabilities", [])

    prompt_tokens = max(16, len(prompt) // 2 + len(visual_description) // 2 + len(dialogue) // 2)
    subtitle_tokens = max(0, len(subtitle_text) // 2)
    total_tokens = prompt_tokens + subtitle_tokens

    return {
        "estimated_duration_seconds": duration,
        "estimated_prompt_tokens": prompt_tokens,
        "estimated_subtitle_tokens": subtitle_tokens,
        "estimated_total_tokens": total_tokens,
        "estimated_video_task": {
            "task_type": "shot_video",
            "default_model_id": shot_video_default.get("default_model_id"),
            "capabilities": video_capabilities,
        },
        "estimated_direct_av_task": {
            "task_type": "shot_audio_video",
            "default_model_id": shot_audio_video_default.get("default_model_id"),
            "capabilities": av_capabilities,
        },
        "estimated_cost_notes": [
            "实际费用由所选模型和供应商决定",
            "当前估算仅用于提示镜头复杂度和模型选择",
        ],
    }


def build_shot_quality_report(shot: Any) -> Dict[str, Any]:
    """
    镜头质量报告（向后兼容函数）

    新代码建议使用 ShotQualityService.check_shot_quality()
    """
    extra_data = getattr(shot, "extra_data", None) if isinstance(getattr(shot, "extra_data", None), dict) else {}
    warnings: List[str] = []
    blockers: List[str] = []
    suggestions: List[str] = []

    if not _has_text(getattr(shot, "prompt", None)) and not _has_text(getattr(shot, "visual_description", None)):
        blockers.append("缺少视频提示词和视觉描述，无法稳定生成镜头视频")
    if not _has_text(getattr(shot, "dialogue", None)) and not _has_text(extra_data.get("subtitle_text")):
        warnings.append("当前镜头没有台词或字幕文本，生成后可能没有对白轨")

    keyframes = getattr(shot, "keyframes", None) or []
    if not isinstance(keyframes, list) or len(keyframes) == 0:
        warnings.append("未设置关键帧，长镜头一致性可能较弱")
        suggestions.append("为镜头补充 start/end/keyframe 参考")

    character_refs = getattr(shot, "character_refs", None) or []
    if not isinstance(character_refs, list) or len(character_refs) == 0:
        warnings.append("未显式绑定角色引用，可能退化为通用角色生成")

    entity_refs = extra_data.get("entity_refs") if isinstance(extra_data.get("entity_refs"), dict) else {}
    if not _names_from_refs(entity_refs.get("scenes")):
        warnings.append("缺少场景引用，场景一致性较弱")
    if not _names_from_refs(entity_refs.get("props")):
        warnings.append("缺少道具引用，道具状态可能不一致")
    if not _names_from_refs(entity_refs.get("events")):
        warnings.append("缺少事件引用，镜头与小说事件的衔接可能偏弱")

    production_context = extra_data.get("production_context") if isinstance(extra_data.get("production_context"), dict) else {}
    review_state = production_context.get("review_state") or extra_data.get("review_state") or "pending_review"
    if review_state not in {"approved", "locked"}:
        suggestions.append("完成镜头审核后再进入批量生成或真实渲染")

    score = 100
    score -= 20 if blockers else 0
    score -= min(35, len(warnings) * 6)
    score = max(0, score)

    # 新的增强检测项
    image_url = getattr(shot, "image_url", None)
    if not image_url or not image_url.strip():
        warnings.append("当前镜头没有参考图，可能影响角色/场景一致性")

    duration = getattr(shot, "duration", None)
    if duration and duration > MAX_SHOT_DURATION:
        warnings.append(f"镜头时长{duration}秒超过推荐值{MAX_SHOT_DURATION}秒")

    dialogue = getattr(shot, "dialogue", None) or ""
    if len(dialogue) > MAX_DIALOGUE_CHARS:
        warnings.append(f"对白过长（{len(dialogue)}字），可能影响配音节奏")

    return {
        "score": score,
        "status": "blocked" if blockers else ("warning" if warnings else "ready"),
        "blockers": blockers,
        "warnings": warnings,
        "suggestions": suggestions,
        "summary": build_ai_generation_feedback(
            stage="shot_quality_check",
            message="镜头质量检查完成",
            context={
                "novel_id": extra_data.get("novel_id"),
                "chapter_id": extra_data.get("chapter_id"),
                "title": getattr(shot, "prompt", None) or getattr(shot, "visual_description", None),
                "characters": getattr(shot, "character_refs", None) or [],
                "scenes": entity_refs.get("scenes") or [],
                "props": entity_refs.get("props") or [],
                "events": entity_refs.get("events") or [],
            },
            warnings=warnings,
            extra={
                "score": score,
                "status": "blocked" if blockers else ("warning" if warnings else "ready"),
                "has_image": bool(image_url),
                "duration": duration,
                "dialogue_length": len(dialogue),
            },
        ),
    }
