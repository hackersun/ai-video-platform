"""Continuity review task aggregation and resolution."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.models import Novel, Shot, Storyboard, Workflow


def _json_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _shot_summary(shot: Shot) -> Optional[str]:
    text = shot.visual_description or shot.prompt or shot.dialogue
    if not text:
        return None
    return text if len(text) <= 96 else f"{text[:96]}..."


def _task_status(extra_data: Dict[str, Any], production_context: Dict[str, Any], continuity_change: Dict[str, Any]) -> str:
    review_state = production_context.get("review_state") or extra_data.get("review_state")
    if continuity_change.get("resolved_at"):
        return "resolved"
    if extra_data.get("needs_review") is True or review_state in {"pending_review", "changes_requested"} or continuity_change:
        return "open"
    return "closed"


def _task_urls(shot: Shot, storyboard: Optional[Storyboard], workflow: Optional[Workflow]) -> Dict[str, Optional[str]]:
    shot_url = f"/shots?shot_id={shot.id}"
    storyboard_url = f"/storyboards?storyboard_id={storyboard.id}" if storyboard else None
    if workflow:
        shot_review_url = f"/studio/shot-review?workflow_id={workflow.id}&shot_id={shot.id}"
    else:
        shot_review_url = "/studio/shot-review"
    return {
        "shot_url": shot_url,
        "storyboard_url": storyboard_url,
        "shot_review_url": shot_review_url,
    }


def _sort_tasks(tasks: List[Dict[str, Any]], sort: str) -> List[Dict[str, Any]]:
    reverse = sort.endswith("_desc")
    if sort.startswith("episode_"):
        return sorted(tasks, key=lambda item: item.get("episode_index") or 0, reverse=reverse)
    if sort.startswith("entity_"):
        return sorted(tasks, key=lambda item: item.get("entity_name") or "", reverse=reverse)
    return sorted(tasks, key=lambda item: item.get("review_at") or item.get("marked_at") or "", reverse=reverse)


async def list_continuity_review_tasks(
    db: AsyncSession,
    user_id: str,
    *,
    novel_id: Optional[str] = None,
    entity_id: Optional[str] = None,
    episode_index: Optional[int] = None,
    review_state: Optional[str] = None,
    task_status: str = "open",
    sort: str = "updated_desc",
    workflow_id: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    query = (
        select(Shot, Storyboard, Novel, Workflow)
        .outerjoin(Storyboard, Shot.storyboard_id == Storyboard.id)
        .outerjoin(Novel, Storyboard.novel_id == Novel.id)
        .outerjoin(Workflow, and_(Workflow.storyboard_id == Shot.storyboard_id, Workflow.user_id == user_id))
        .where(Shot.user_id == user_id, Shot.extra_data.is_not(None))
        .order_by(desc(Shot.updated_at), desc(Workflow.updated_at))
    )
    if novel_id:
        query = query.where(Storyboard.novel_id == novel_id)
    if workflow_id:
        query = query.where(Workflow.id == workflow_id)

    result = await db.execute(query)
    tasks: List[Dict[str, Any]] = []
    seen_shot_ids = set()
    for shot, storyboard, novel, workflow in result.all():
        if shot.id in seen_shot_ids:
            continue
        extra_data = _json_dict(shot.extra_data)
        production_context = _json_dict(extra_data.get("production_context"))
        continuity_change = _json_dict(production_context.get("continuity_change"))
        current_review_state = production_context.get("review_state") or extra_data.get("review_state")
        current_status = _task_status(extra_data, production_context, continuity_change)
        is_review_task = current_status in {"open", "resolved"}
        if not is_review_task:
            continue
        if task_status != "all" and current_status != task_status:
            continue
        if entity_id and str(continuity_change.get("entity_id") or "") != entity_id:
            continue
        if episode_index is not None and int(continuity_change.get("episode_index") or 0) != episode_index:
            continue
        if review_state and current_review_state != review_state:
            continue

        urls = _task_urls(shot, storyboard, workflow)
        seen_shot_ids.add(shot.id)
        tasks.append({
            "shot_id": shot.id,
            "shot_number": shot.shot_number or 1,
            "storyboard_id": getattr(storyboard, "id", None),
            "storyboard_title": getattr(storyboard, "title", None),
            "novel_id": getattr(storyboard, "novel_id", None),
            "novel_title": getattr(novel, "title", None),
            "workflow_id": getattr(workflow, "id", None),
            "workflow_title": getattr(workflow, "title", None),
            "shot_summary": _shot_summary(shot),
            "entity_id": continuity_change.get("entity_id"),
            "entity_name": continuity_change.get("entity_name"),
            "entity_type": continuity_change.get("entity_type"),
            "episode_index": continuity_change.get("episode_index"),
            "review_reason": extra_data.get("review_reason") or production_context.get("review_notes"),
            "review_at": extra_data.get("review_at") or continuity_change.get("marked_at"),
            "review_state": current_review_state,
            "review_notes": production_context.get("review_notes"),
            "change_note": continuity_change.get("change_note"),
            "marked_at": continuity_change.get("marked_at"),
            "status": current_status,
            **urls,
        })

    sorted_tasks = _sort_tasks(tasks, sort)
    filters = {
        "novel_id": novel_id,
        "entity_id": entity_id,
        "episode_index": episode_index,
        "review_state": review_state,
        "status": task_status,
    }
    response: Dict[str, Any] = {"tasks": sorted_tasks[:limit], "total": len(sorted_tasks), "filters": filters, "sort": sort}
    if workflow_id:
        response["workflow_id"] = workflow_id
    return response


async def resolve_continuity_review_task(
    db: AsyncSession,
    user_id: str,
    shot_id: str,
    *,
    resolution_note: Optional[str] = None,
    commit: bool = True,
) -> Dict[str, Any]:
    result = await db.execute(select(Shot).where(Shot.id == shot_id, Shot.user_id == user_id))
    shot = result.scalar_one_or_none()
    if shot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="镜头不存在")

    now = utc_now().isoformat()
    extra_data = dict(_json_dict(shot.extra_data))
    production_context = dict(_json_dict(extra_data.get("production_context")))
    continuity_change = dict(_json_dict(production_context.get("continuity_change")))
    note = resolution_note or "连续性复审已完成"

    if continuity_change:
        continuity_change["resolved_at"] = now
        continuity_change["resolution_note"] = note
        production_context["continuity_change"] = continuity_change

    extra_data["needs_review"] = False
    extra_data["review_resolved_at"] = now
    extra_data["review_resolution_note"] = note
    production_context["review_state"] = "approved"
    production_context["review_notes"] = note
    production_context["updated_at"] = now
    extra_data["production_context"] = production_context
    shot.extra_data = extra_data
    shot.updated_at = utc_now()

    if commit:
        await db.commit()
        await db.refresh(shot)

    return {
        "status": "resolved",
        "shot_id": shot.id,
        "review_state": "approved",
        "resolved_at": now,
        "resolution_note": note,
    }


async def resolve_continuity_review_tasks_batch(
    db: AsyncSession,
    user_id: str,
    shot_ids: List[str],
    *,
    resolution_note: Optional[str] = None,
) -> Dict[str, Any]:
    resolved: List[Dict[str, Any]] = []
    unique_shot_ids = list(dict.fromkeys(shot_ids))
    for shot_id in unique_shot_ids:
        resolved.append(await resolve_continuity_review_task(
            db,
            user_id,
            shot_id,
            resolution_note=resolution_note,
            commit=False,
        ))

    await db.commit()
    return {
        "status": "resolved",
        "resolved_count": len(resolved),
        "shot_ids": [item["shot_id"] for item in resolved],
        "tasks": resolved,
    }
