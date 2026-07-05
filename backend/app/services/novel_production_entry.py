"""Novel-level production entry guidance for the Studio command console."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chapter, Novel, Workflow
from app.services.series_production import get_series_plan


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


async def _chapter_count(db: AsyncSession, user_id: str, novel_id: str) -> int:
    result = await db.execute(select(Chapter.id).where(Chapter.user_id == user_id, Chapter.novel_id == novel_id))
    return len(result.scalars().all())


async def _latest_workflow(db: AsyncSession, user_id: str, novel_id: str) -> Optional[Workflow]:
    result = await db.execute(
        select(Workflow)
        .where(Workflow.user_id == user_id, Workflow.novel_id == novel_id)
        .order_by(desc(Workflow.updated_at), desc(Workflow.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _workflow_count(db: AsyncSession, user_id: str, novel_id: str) -> int:
    result = await db.execute(select(Workflow.id).where(Workflow.user_id == user_id, Workflow.novel_id == novel_id))
    return len(result.scalars().all())


async def build_novel_production_entry(db: AsyncSession, user_id: str, novel_id: str) -> Dict[str, Any]:
    novel = await db.get(Novel, novel_id)
    if novel is None or novel.user_id != user_id:
        return {
            "novel_id": novel_id,
            "stage": "not_found",
            "label": "小说不存在",
            "description": "无法读取该小说的制作入口。",
            "primary_action": _action("open_novels", "返回小说管理", "/novels", "回到小说管理列表。"),
            "metrics": {},
        }

    chapter_count = await _chapter_count(db, user_id, novel_id)
    plan = await get_series_plan(db, user_id, novel_id)
    episodes = plan.get("episodes") if isinstance(plan, dict) else []
    latest_workflow = await _latest_workflow(db, user_id, novel_id)
    workflow_count = await _workflow_count(db, user_id, novel_id)

    metrics = {
        "chapter_count": chapter_count,
        "episode_count": len(episodes or []),
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

    if not episodes:
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


async def build_novel_production_entries(
    db: AsyncSession,
    user_id: str,
    novel_ids: Iterable[str],
) -> Dict[str, Any]:
    entries: Dict[str, Dict[str, Any]] = {}
    for novel_id in [value for value in novel_ids if value]:
        entries[novel_id] = await build_novel_production_entry(db, user_id, novel_id)
    return {"entries": entries, "count": len(entries)}
