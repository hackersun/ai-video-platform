"""Novel-level production entry guidance for the Studio command console."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chapter, Novel, Workflow
from app.services.series_production import get_series_plan


BATCH_LIMIT = 100


def _query_params(params: Dict[str, Optional[str]]) -> str:
    pairs = [(key, value) for key, value in params.items() if value]
    return "&".join(f"{key}={value}" for key, value in pairs)


def _action(code: str, label: str, href: str, description: str, risk: str = "navigation") -> Dict[str, Any]:
    return {
        "code": code,
        "label": label,
        "href": href,
        "description": description,
        "risk": risk,
    }


def _not_found_entry(novel_id: str) -> Dict[str, Any]:
    return {
        "novel_id": novel_id,
        "stage": "not_found",
        "label": "小说不存在",
        "description": "无法读取该小说的制作入口。",
        "primary_action": _action("open_novels", "返回小说管理", "/novels", "回到小说管理列表。"),
        "metrics": {},
    }


def _normalize_novel_ids(novel_ids: Iterable[str]) -> List[str]:
    ids: List[str] = []
    seen = set()
    for novel_id in novel_ids:
        value = str(novel_id or "").strip()
        if not value or value in seen:
            continue
        ids.append(value)
        seen.add(value)
        if len(ids) >= BATCH_LIMIT:
            break
    return ids


def _entry_from_state(
    novel_id: str,
    chapter_count: int,
    episode_count: int,
    latest_workflow: Optional[Workflow],
    workflow_count: int,
) -> Dict[str, Any]:
    metrics = {
        "chapter_count": chapter_count,
        "episode_count": episode_count,
        "workflow_count": workflow_count,
    }

    if chapter_count <= 0:
        return {
            "novel_id": novel_id,
            "stage": "content_prepare",
            "label": "待补章节",
            "description": "先导入或拆分章节，再生成整书多集计划。",
            "primary_action": _action("open_chapters", "补齐章节", f"/novels/{novel_id}?tab=chapters", "进入小说章节管理。"),
            "metrics": metrics,
        }

    if latest_workflow is not None:
        params = _query_params({
            "workflow_id": latest_workflow.id,
            "novel_id": novel_id,
            "chapter_id": latest_workflow.chapter_id,
        })
        return {
            "novel_id": novel_id,
            "stage": "studio_fix" if latest_workflow.status != "completed" else "studio_ready",
            "label": "进入工作室",
            "description": "本集工程已创建，进入 Studio 按推荐步骤处理。",
            "primary_action": _action("open_studio", "继续制作", f"/studio?{params}", "带小说、章节和工作流上下文进入工作室。"),
            "metrics": metrics,
            "workflow_id": latest_workflow.id,
            "chapter_id": latest_workflow.chapter_id,
        }

    if episode_count <= 0:
        return {
            "novel_id": novel_id,
            "stage": "series_plan",
            "label": "待生成整书计划",
            "description": "已有章节，下一步生成多集制作计划。",
            "primary_action": _action("open_series_plan", "生成整书计划", f"/novels/{novel_id}?tab=series-plan", "进入整书生产计划。"),
            "metrics": metrics,
        }

    return {
        "novel_id": novel_id,
        "stage": "workflow_create",
        "label": "待创建本集工程",
        "description": "整书计划已就绪，下一步创建或继续第一个本集工程。",
        "primary_action": _action("open_series_plan", "创建本集工程", f"/novels/{novel_id}?tab=series-plan", "在多集计划中创建本集工程。"),
        "metrics": metrics,
    }


async def _chapter_count(db: AsyncSession, user_id: str, novel_id: str) -> int:
    result = await db.execute(
        select(func.count(Chapter.id)).where(Chapter.user_id == user_id, Chapter.novel_id == novel_id)
    )
    return int(result.scalar_one() or 0)


async def _latest_workflow(db: AsyncSession, user_id: str, novel_id: str) -> Optional[Workflow]:
    result = await db.execute(
        select(Workflow)
        .where(Workflow.user_id == user_id, Workflow.novel_id == novel_id)
        .order_by(desc(Workflow.updated_at), desc(Workflow.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _workflow_count(db: AsyncSession, user_id: str, novel_id: str) -> int:
    result = await db.execute(
        select(func.count(Workflow.id)).where(Workflow.user_id == user_id, Workflow.novel_id == novel_id)
    )
    return int(result.scalar_one() or 0)


async def _chapter_counts(db: AsyncSession, user_id: str, novel_ids: List[str]) -> Dict[str, int]:
    result = await db.execute(
        select(Chapter.novel_id, func.count(Chapter.id))
        .where(Chapter.user_id == user_id, Chapter.novel_id.in_(novel_ids))
        .group_by(Chapter.novel_id)
    )
    return {novel_id: int(count or 0) for novel_id, count in result.all()}


async def _workflow_counts(db: AsyncSession, user_id: str, novel_ids: List[str]) -> Dict[str, int]:
    result = await db.execute(
        select(Workflow.novel_id, func.count(Workflow.id))
        .where(Workflow.user_id == user_id, Workflow.novel_id.in_(novel_ids))
        .group_by(Workflow.novel_id)
    )
    return {novel_id: int(count or 0) for novel_id, count in result.all()}


async def _latest_workflows(db: AsyncSession, user_id: str, novel_ids: List[str]) -> Dict[str, Workflow]:
    result = await db.execute(
        select(Workflow)
        .where(Workflow.user_id == user_id, Workflow.novel_id.in_(novel_ids))
        .order_by(desc(Workflow.updated_at), desc(Workflow.created_at))
    )
    workflows: Dict[str, Workflow] = {}
    for workflow in result.scalars().all():
        if workflow.novel_id and workflow.novel_id not in workflows:
            workflows[workflow.novel_id] = workflow
    return workflows


async def build_novel_production_entry(db: AsyncSession, user_id: str, novel_id: str) -> Dict[str, Any]:
    result = await db.execute(select(Novel).where(Novel.id == novel_id, Novel.user_id == user_id))
    novel = result.scalar_one_or_none()
    if novel is None:
        return _not_found_entry(novel_id)

    chapter_count = await _chapter_count(db, user_id, novel_id)
    plan = await get_series_plan(db, user_id, novel_id)
    episodes = plan.get("episodes") if isinstance(plan, dict) else []
    latest_workflow = await _latest_workflow(db, user_id, novel_id)
    workflow_count = await _workflow_count(db, user_id, novel_id)

    return _entry_from_state(novel_id, chapter_count, len(episodes or []), latest_workflow, workflow_count)


async def build_novel_production_entries(
    db: AsyncSession,
    user_id: str,
    novel_ids: Iterable[str],
) -> Dict[str, Any]:
    ids = _normalize_novel_ids(novel_ids)
    if not ids:
        return {"entries": {}, "count": 0}

    novels_result = await db.execute(select(Novel.id).where(Novel.user_id == user_id, Novel.id.in_(ids)))
    existing_ids = set(novels_result.scalars().all())
    chapter_counts = await _chapter_counts(db, user_id, ids)
    workflow_counts = await _workflow_counts(db, user_id, ids)
    latest_workflows = await _latest_workflows(db, user_id, ids)

    entries: Dict[str, Dict[str, Any]] = {}
    for novel_id in ids:
        if novel_id not in existing_ids:
            entries[novel_id] = _not_found_entry(novel_id)
            continue

        chapter_count = chapter_counts.get(novel_id, 0)
        latest_workflow = latest_workflows.get(novel_id)
        episode_count = 0
        if chapter_count > 0 and latest_workflow is None:
            plan = await get_series_plan(db, user_id, novel_id)
            episodes = plan.get("episodes") if isinstance(plan, dict) else []
            episode_count = len(episodes or [])

        entries[novel_id] = _entry_from_state(
            novel_id,
            chapter_count,
            episode_count,
            latest_workflow,
            workflow_counts.get(novel_id, 0),
        )
    return {"entries": entries, "count": len(entries)}
