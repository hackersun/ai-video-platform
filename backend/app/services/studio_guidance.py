"""Workflow-level Studio guidance for the smart command console."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import urlencode


def _href(path: str, params: Dict[str, Any]) -> str:
    query = urlencode({key: value for key, value in params.items() if value})
    return f"{path}?{query}" if query else path


def _context_params(workflow: Dict[str, Any], source_issue_code: Optional[str] = None) -> Dict[str, Any]:
    return {
        "workflow_id": workflow.get("id"),
        "novel_id": workflow.get("novel_id"),
        "chapter_id": workflow.get("chapter_id"),
        "source_issue": source_issue_code,
    }


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
    execution: Optional[str] = None,
    method: Optional[str] = None,
    endpoint: Optional[str] = None,
) -> Dict[str, Any]:
    confirmation_required = risk in {"confirm", "production"}
    payload = {
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
    if execution:
        payload["execution"] = execution
    if method:
        payload["method"] = method
    if endpoint:
        payload["endpoint"] = endpoint
    return payload


def _issue_by_code(issues: List[Dict[str, Any]], code: str) -> Optional[Dict[str, Any]]:
    return next((issue for issue in issues if issue.get("code") == code), None)


def _build_legacy_studio_guidance(
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
    confirmable = int(mode_policy.get("confirmable_issue_count") or 0)
    bypassed = int(mode_policy.get("bypassed_issue_count") or 0)
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
            href=_href(
                f"/novels/{workflow.get('novel_id')}",
                {"tab": "story-bible", **_context_params(workflow, "missing_story_bible")},
            ),
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
            href=_href("/storyboards", _context_params(workflow, "missing_shots")),
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
            href=_href("/producer", _context_params(workflow)),
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
            execution="review",
            method="POST",
            endpoint=f"/studio/workflows/{workflow.get('id')}/review",
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

    review_status = "blocked" if blockers else "working" if confirmable or bypassed else "ready"
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
            review_status,
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


PRODUCTION_STAGE_ORDER = [
    "facts", "assets", "episode_contract", "draft", "review", "final", "render", "publish"
]

QUALITY_DIMENSIONS = {
    "narrative_truth", "character_visual", "scene_prop_state",
    "motion_camera", "voice_lipsync", "delivery_integrity",
}


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
    episode_contract: Optional[Dict[str, Any]] = None,
    production_graph: Optional[Dict[str, Any]] = None,
    assets: Optional[Dict[str, Any]] = None,
    jobs: Optional[Dict[str, Any]] = None,
    consistency_ledger: Optional[Dict[str, Any]] = None,
    orchestration: Optional[Dict[str, Any]] = None,
    quality_evaluation: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    workflow = workflow or {}
    story_context = story_context or {}
    production_bible_summary = production_bible_summary or {}
    production = production or {}
    assets = assets or {}
    jobs = jobs or {}
    consistency_ledger = consistency_ledger or {}
    orchestration = orchestration or {}
    quality_evaluation = quality_evaluation or {}
    issues = issues or []
    actions = actions or []
    mode_policy = mode_policy or {}
    job_summary = jobs.get("summary") or {}
    blocking_issues = [item for item in issues if item.get("severity") in {"blocking", "error"}]
    warnings = [item for item in issues if item.get("severity") in {"warning", "confirmable"}]

    successful_drafts = [
        {"job_id": item.get("id"), "artifact_id": item.get("video_url")}
        for item in jobs.get("video_jobs") or []
        if item.get("status") in {"succeeded", "completed"} and item.get("video_url")
    ] + [
        {
            "job_id": item.get("id"),
            "artifact_id": item.get("output_manifest_url") or item.get("output_video_url") or item.get("output_audio_url"),
        }
        for item in jobs.get("media_jobs") or []
        if item.get("status") in {"succeeded", "completed"}
        and (item.get("output_manifest_url") or item.get("output_video_url") or item.get("output_audio_url"))
    ]
    successful_renders = [
        item for item in jobs.get("synthesis_jobs") or []
        if item.get("status") in {"succeeded", "completed"}
        and item.get("output_url")
        and item.get("is_publishable") is True
    ]
    evaluated_dimensions = {str(item) for item in quality_evaluation.get("dimensions") or []}
    quality_complete = (
        evaluated_dimensions == QUALITY_DIMENSIONS
        and len(quality_evaluation.get("evaluation_ids") or []) == len(QUALITY_DIMENSIONS)
        and quality_evaluation.get("blocking") is False
        and bool(quality_evaluation.get("artifact_id"))
    )
    successful_draft_ids = {str(item["job_id"]) for item in successful_drafts if item.get("job_id")}
    quality_deliverable = quality_complete and str(quality_evaluation.get("artifact_id")) in successful_draft_ids
    asset_ids = [
        str(item.get("id")) for item in assets.get("items") or []
        if item.get("id") and item.get("is_locked") and item.get("is_final")
    ]
    completed: Dict[str, bool] = {}
    completed["facts"] = bool(workflow.get("novel_id") and workflow.get("chapter_id") and (production_graph or {}).get("hash"))
    completed["assets"] = bool(
        completed["facts"]
        and asset_ids
        and float(production.get("asset_lock_coverage") or 0) >= 1
        and (production_bible_summary.get("asset_readiness") or {}).get("ready")
    )
    completed["episode_contract"] = bool(completed["assets"] and episode_contract and episode_contract.get("contract_id"))
    completed["draft"] = bool(completed["episode_contract"] and successful_drafts)
    completed["review"] = bool(completed["draft"] and quality_deliverable and not blocking_issues)
    completed["final"] = bool(
        completed["review"]
        and float(quality_evaluation.get("score") or 0) >= 90
        and int(consistency_ledger.get("overall_score") or 0) >= 90
    )
    completed["render"] = bool(completed["final"] and successful_renders)
    completed["publish"] = bool(
        completed["render"]
        and ((workflow.get("metadata") or {}).get("publication_id") or workflow.get("status") == "published")
    )
    first_incomplete = next((stage for stage in PRODUCTION_STAGE_ORDER if not completed[stage]), "publish")
    failed = orchestration.get("status") == "failed" and orchestration.get("task_id")
    current_stage = str(orchestration.get("failed_stage") or first_incomplete) if failed else first_incomplete

    action_specs = {
        "facts": ("open_novel_context", "补齐生产事实", "/workflow"),
        "assets": ("apply_asset_locks", "锁定标准资产", None),
        "episode_contract": ("lock_episode_contract", "锁定剧集合约", None),
        "draft": ("open_producer", "生成本集草片", _href("/producer", _context_params(workflow))),
        "review": ("quality_check", "运行六维质量检查", None),
        "final": ("repair_quality_blockers", "修复终稿阻断项", "/studio/shot-review"),
        "render": ("render_episode", "渲染本集终稿", "/synthesis"),
        "publish": ("publish_episode", "发布本集", "/synthesis"),
    }
    code, label, href = action_specs.get(current_stage, action_specs["publish"])
    recommended_action = _guided_action(
        code,
        label,
        reason=f"当前唯一推进阶段：{current_stage}",
        risk="navigation" if href else "safe",
        href=href,
        scope=[str((story_context.get("chapter") or {}).get("title") or "当前集")],
        expected_outputs=[current_stage],
    )
    orchestration_resume: Dict[str, Any] = {}
    if failed:
        orchestration_resume = {
            "task_id": orchestration["task_id"],
            "status": "failed",
            "failed_stage": current_stage,
            "completed_stages": orchestration.get("completed_stages") or [],
            "error_message": orchestration.get("error_message"),
            "safe_retry": True,
        }
        recommended_action = _guided_action(
            "retry_orchestration",
            "安全重试失败阶段",
            reason=str(orchestration.get("error_message") or "上次编排失败，可从持久化阶段继续。"),
            risk="safe",
            params={"task_id": orchestration["task_id"], "stage": current_stage},
            expected_outputs=[current_stage],
        )

    labels = {
        "facts": "事实锁定", "assets": "资产锁定", "episode_contract": "剧集合约", "draft": "草片",
        "review": "复审", "final": "终稿", "render": "渲染", "publish": "发布",
    }
    stages = [
        _stage(
            stage,
            labels[stage],
            "ready" if completed[stage] else "working" if stage == current_stage else "blocked",
            "已提供完成证据" if completed[stage] else "等待前序阶段或当前动作",
        )
        for stage in PRODUCTION_STAGE_ORDER
    ]
    evidence_by_stage = {
        "facts": {"hash": (production_graph or {}).get("hash")},
        "assets": {"evidence_ids": asset_ids},
        "episode_contract": {
            "evidence_id": (episode_contract or {}).get("contract_id"),
            "hash": (episode_contract or {}).get("production_bible_hash"),
        },
        "draft": successful_drafts[0] if successful_drafts else {},
        "review": {
            "artifact_id": quality_evaluation.get("artifact_id"),
            "evaluation_ids": quality_evaluation.get("evaluation_ids") or [],
            "score": quality_evaluation.get("score"),
        },
        "final": {
            "artifact_id": quality_evaluation.get("artifact_id"),
            "score": quality_evaluation.get("score"),
        },
        "render": {
            "job_id": successful_renders[0].get("id") if successful_renders else None,
            "artifact_id": successful_renders[0].get("output_url") if successful_renders else None,
        },
        "publish": {"evidence_id": (workflow.get("metadata") or {}).get("publication_id")},
    }
    completed_evidence = [
        {"stage": stage, **evidence_by_stage[stage]}
        for stage in PRODUCTION_STAGE_ORDER if completed[stage]
    ]
    return {
        "readiness_score": int(production_bible_summary.get("readiness_score") or 0),
        "current_stage": current_stage,
        "stages": stages,
        "blockers": blocking_issues,
        "confirmable_warnings": warnings,
        "completed_evidence": completed_evidence,
        "recommended_action": recommended_action,
        "next_action": recommended_action,
        "blocker_count": len(blocking_issues),
        "mode": mode_policy.get("mode") or "production",
        "breadcrumbs": _context_params(workflow),
        "secondary_actions": [item for item in actions if item.get("code") != recommended_action.get("code")][:6],
        "orchestration_resume": orchestration_resume,
    }
