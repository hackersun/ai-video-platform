"""Workflow-level Studio guidance for the smart command console."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _stage(
    stage_id: str,
    label: str,
    status: str,
    description: str,
    action: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "id": stage_id,
        "label": label,
        "status": status,
        "description": description,
        "action": action,
    }


def _guided_action(
    code: str,
    label: str,
    *,
    reason: str,
    risk: str = "safe",
    href: Optional[str] = None,
    scope: Optional[List[str]] = None,
    expected_outputs: Optional[List[str]] = None,
    source_issue_code: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    confirmation_required = risk in {"confirm", "production"}
    return {
        "code": code,
        "label": label,
        "reason": reason,
        "risk": risk,
        "href": href,
        "scope": scope or [],
        "expected_outputs": expected_outputs or [],
        "source_issue_code": source_issue_code,
        "params": params or {},
        "confirmation": {
            "required": confirmation_required,
            "title": label,
            "description": reason,
            "impact": scope or [],
            "confirm_label": "确认执行" if confirmation_required else "执行",
        },
    }


def _issue_by_code(issues: List[Dict[str, Any]], code: str) -> Optional[Dict[str, Any]]:
    return next((issue for issue in issues if issue.get("code") == code), None)


def build_studio_guidance(
    *,
    workflow: Dict[str, Any],
    story_context: Dict[str, Any],
    story_bible: Dict[str, Any],
    production_bible_summary: Dict[str, Any],
    production: Dict[str, Any],
    timeline: Dict[str, Any],
    issues: List[Dict[str, Any]],
    actions: List[Dict[str, Any]],
    mode_policy: Dict[str, Any],
) -> Dict[str, Any]:
    workflow = workflow or {}
    story_context = story_context or {}
    story_bible = story_bible or {}
    production_bible_summary = production_bible_summary or {}
    production = production or {}
    timeline = timeline or {}
    issues = issues or []
    actions = actions or []
    mode_policy = mode_policy or {}

    novel = story_context.get("novel") or {}
    chapter = story_context.get("chapter") or {}
    shot_count = int(production.get("shot_count") or 0)
    asset_coverage = float(production.get("asset_lock_coverage") or 0)
    readiness_score = int(production_bible_summary.get("readiness_score") or 0)
    blockers = int(mode_policy.get("blocking_issue_count") or 0)
    has_bible = bool(story_bible.get("id") or production_bible_summary.get("story_bible_id"))
    has_timeline = bool(timeline.get("preview_url") or timeline.get("clip_count"))

    missing_story_bible = _issue_by_code(issues, "missing_story_bible")
    missing_shots = _issue_by_code(issues, "missing_shots")
    missing_locks = _issue_by_code(issues, "missing_asset_locks")

    if not workflow.get("novel_id") or not workflow.get("chapter_id"):
        next_action = _guided_action(
            "open_novel_context",
            "补齐小说和章节",
            reason="工作流缺少小说或章节上下文，无法保证连续制作一致性。",
            risk="navigation",
            href="/workflow",
            scope=["当前工作流"],
            expected_outputs=["绑定小说", "绑定章节"],
        )
        current_stage = "content"
    elif missing_story_bible:
        next_action = _guided_action(
            "open_story_bible",
            "生成 Story Bible",
            reason=missing_story_bible.get("message") or "缺少小说级设定本。",
            risk="navigation",
            href=f"/novels/{workflow.get('novel_id')}?tab=story-bible",
            scope=[str(novel.get("title") or workflow.get("novel_id"))],
            expected_outputs=["风格规则", "角色规则", "场景规则", "道具规则"],
            source_issue_code="missing_story_bible",
        )
        current_stage = "bible"
    elif missing_shots:
        next_action = _guided_action(
            "open_storyboard",
            "生成或编辑分镜镜头",
            reason=missing_shots.get("message") or "缺少镜头，无法生成草片。",
            risk="navigation",
            href="/storyboards",
            scope=[str(chapter.get("title") or workflow.get("chapter_id"))],
            expected_outputs=["分镜", "镜头列表"],
            source_issue_code="missing_shots",
        )
        current_stage = "episode"
    elif missing_locks:
        next_action = _guided_action(
            "apply_asset_locks",
            "应用资产锁",
            reason=missing_locks.get("message") or "镜头缺少资产锁。",
            risk="safe",
            scope=[f"{shot_count} 个镜头", "角色/场景/道具资产"],
            expected_outputs=["镜头资产锁", "生产上下文刷新"],
            source_issue_code="missing_asset_locks",
        )
        current_stage = "episode"
    elif not has_timeline:
        next_action = _guided_action(
            "open_producer",
            "生成本集草片",
            reason="设定与镜头已具备基础条件，下一步进入草片生产。",
            risk="navigation",
            href=f"/producer?workflow_id={workflow.get('id')}",
            scope=[str(chapter.get("title") or "当前章节")],
            expected_outputs=["镜头音视频任务", "可审阅草片"],
        )
        current_stage = "draft"
    elif blockers:
        next_action = _guided_action(
            "create_review",
            "运行出片检查",
            reason="仍存在阻断项，需要复审或修复后再出片。",
            risk="confirm",
            scope=[f"{blockers} 个阻断项"],
            expected_outputs=["复审记录", "修复建议"],
        )
        current_stage = "review"
    else:
        next_action = _guided_action(
            "quality_check",
            "运行质量检查",
            reason="当前工作流没有硬阻断，终稿前执行质量检查。",
            risk="safe",
            scope=["当前工作流", f"{shot_count} 个镜头"],
            expected_outputs=["质量报告", "出片建议"],
        )
        current_stage = "review"

    stages = [
        _stage(
            "content",
            "内容准备",
            "ready" if workflow.get("novel_id") and workflow.get("chapter_id") else "blocked",
            "小说、章节和整书计划上下文。",
        ),
        _stage(
            "bible",
            "设定锁定",
            "ready" if has_bible else "blocked",
            "Story Bible、风格、角色、场景、道具和声线。",
        ),
        _stage(
            "episode",
            "本集工程",
            "ready" if shot_count > 0 and asset_coverage >= 1 else "working" if shot_count > 0 else "blocked",
            "剧本、分镜、镜头、实体引用和资产锁。",
        ),
        _stage(
            "draft",
            "草片生产",
            "ready" if has_timeline else "working" if shot_count > 0 else "blocked",
            "视频、配音、字幕、合成和时间线。",
        ),
        _stage(
            "review",
            "复审出片",
            "blocked" if blockers else "ready",
            "连续性复审、质量检查和成片验证。",
        ),
    ]

    return {
        "readiness_score": readiness_score,
        "current_stage": current_stage,
        "next_action": next_action,
        "stages": stages,
        "blocker_count": blockers,
        "mode": mode_policy.get("mode") or "production",
        "breadcrumbs": {
            "novel_id": workflow.get("novel_id"),
            "chapter_id": workflow.get("chapter_id"),
            "workflow_id": workflow.get("id"),
        },
        "secondary_actions": actions[:6],
    }
