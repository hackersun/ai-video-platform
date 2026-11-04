"""P2: ensure series plan + Series Run through shots_ready for publication pipelines."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.series_anchor_generation.errors import SeriesAnchorError
from app.features.series_anchor_generation.run_creation import create_run as create_series_run_record
from app.models.chapter import Chapter
from app.models.novel import Novel
from app.models.series_production_run import SeriesProductionRun
from app.services.series_production import build_series_plan, get_series_plan
from app.services.series_run_orchestrator import SeriesRunOrchestrator

logger = logging.getLogger(__name__)

ExecuteFrontFn = Callable[[AsyncSession, SeriesProductionRun], Awaitable[SeriesProductionRun]]

DEFAULT_REQUESTED_STAGES = ["scripts", "storyboards", "shots"]


class PipelineFrontBlocked(Exception):
    def __init__(self, code: str, detail: str = ""):
        self.code = code
        self.detail = detail or code
        super().__init__(self.detail)


def publication_run_idempotency_key(client_key: str) -> str:
    return f"pubpipe:{client_key}"


def _episodes_from_plan(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    episodes: List[Dict[str, Any]] = []
    for raw in plan.get("episodes") or []:
        if not isinstance(raw, dict):
            continue
        chapter_ids = [str(cid) for cid in (raw.get("chapter_ids") or []) if cid]
        if not chapter_ids:
            continue
        episode_number = int(raw.get("episode_number") or (len(episodes) + 1))
        item: Dict[str, Any] = {
            "episode_number": episode_number,
            "chapter_ids": chapter_ids,
        }
        if raw.get("title"):
            item["title"] = raw["title"]
        episodes.append(item)
    episodes.sort(key=lambda item: int(item["episode_number"]))
    return episodes


def _chapter_input_hash(chapters: Sequence[Chapter]) -> str:
    """Same lineage format as the Series Run panel / acceptance path: ``id:updated_at`` joined by ``|``."""
    return "|".join(
        f"{chapter.id}:{chapter.updated_at.isoformat() if chapter.updated_at else ''}" for chapter in chapters
    )


async def _attach_episode_input_hashes(
    db: AsyncSession, *, user_id: str, novel_id: str, episodes: List[Dict[str, Any]]
) -> None:
    """Series Run episode stages require ``input_hash``; derive it from the owned chapters."""
    wanted = {cid for episode in episodes for cid in episode["chapter_ids"]}
    rows = (
        await db.scalars(
            select(Chapter).where(
                Chapter.id.in_(wanted), Chapter.user_id == user_id, Chapter.novel_id == novel_id
            )
        )
    ).all()
    by_id = {str(row.id): row for row in rows}
    for episode in episodes:
        missing = [cid for cid in episode["chapter_ids"] if cid not in by_id]
        if missing:
            raise PipelineFrontBlocked(
                "series_plan_chapters_invalid", f"series_plan 引用了不存在的章节: {missing}"
            )
        episode["input_hash"] = _chapter_input_hash([by_id[cid] for cid in episode["chapter_ids"]])


async def ensure_series_plan_for_pipeline(
    db: AsyncSession,
    *,
    user_id: str,
    novel_id: str,
    ensure: bool,
    series_plan_version: Optional[str] = None,
) -> Dict[str, Any]:
    novel = await db.scalar(select(Novel).where(Novel.id == novel_id, Novel.user_id == user_id))
    if novel is None:
        raise PipelineFrontBlocked("novel_not_found", "小说不存在")

    chapter_count = await db.scalar(
        select(Chapter.id).where(Chapter.novel_id == novel_id, Chapter.user_id == user_id).limit(1)
    )
    if chapter_count is None:
        raise PipelineFrontBlocked("chapters_missing", "请先为小说创建或导入章节")

    plan = await get_series_plan(db, user_id, novel_id)
    if (not plan or not plan.get("episodes")) and ensure:
        try:
            plan = await build_series_plan(db, user_id, novel_id=novel_id, persist=True)
        except Exception as exc:  # HTTPException or validation
            detail = getattr(exc, "detail", None) or str(exc)
            raise PipelineFrontBlocked("series_plan_build_failed", str(detail)) from exc

    if not plan or not plan.get("episodes"):
        raise PipelineFrontBlocked(
            "series_plan_missing",
            "缺少整书 series_plan；请先生成计划或设置 ensure_series_plan=true",
        )

    episodes = _episodes_from_plan(plan)
    if not episodes:
        raise PipelineFrontBlocked("series_plan_episodes_missing", "series_plan 没有可用集/章节映射")
    await _attach_episode_input_hashes(db, user_id=user_id, novel_id=novel_id, episodes=episodes)
    if not episodes:
        raise PipelineFrontBlocked("series_plan_episodes_missing", "series_plan 没有可用集/章节映射")

    version = series_plan_version or str(plan.get("version") or plan.get("series_plan_version") or "1")
    return {
        "series_plan_version": version,
        "episodes": episodes,
        "plan": plan,
    }


async def ensure_series_run_for_pipeline(
    db: AsyncSession,
    *,
    user_id: str,
    novel_id: str,
    series_plan_version: str,
    idempotency_key: str,
    episodes: Sequence[Dict[str, Any]],
    model_bindings: Optional[Dict[str, Any]] = None,
    budget_policy: Optional[Dict[str, Any]] = None,
    requested_stages: Optional[Sequence[str]] = None,
) -> SeriesProductionRun:
    run_key = publication_run_idempotency_key(idempotency_key)
    try:
        run, _created = await create_series_run_record(
            db,
            user_id=user_id,
            novel_id=novel_id,
            plan_version=series_plan_version,
            idempotency_key=run_key,
            requested_stages=list(requested_stages or DEFAULT_REQUESTED_STAGES),
            model_bindings=dict(model_bindings or {}),
            requested_budget_policy=dict(budget_policy or {}),
            episodes=list(episodes),
        )
    except SeriesAnchorError as exc:
        raise PipelineFrontBlocked("series_run_create_failed", str(exc.detail)) from exc
    return run


async def run_front_to_shots(
    db: AsyncSession,
    run: SeriesProductionRun,
    *,
    execute_fn: Optional[ExecuteFrontFn] = None,
) -> SeriesProductionRun:
    if run.status == "shots_ready":
        return run
    if run.status in {"completed", "evaluating", "media_running", "anchor_ready"}:
        # Already past shots — treat as shots-ready for front stage purposes.
        return run

    executor = execute_fn
    if executor is None:
        orch = SeriesRunOrchestrator()

        async def _default(db_session: AsyncSession, current: SeriesProductionRun) -> SeriesProductionRun:
            return await orch.execute(db_session, current)

        executor = _default

    updated = await executor(db, run)
    await db.refresh(updated)
    if updated.status not in {"shots_ready", "anchor_ready", "media_running", "evaluating", "completed"}:
        raise PipelineFrontBlocked(
            "front_to_shots_incomplete",
            f"Series Run 未能到达 shots_ready（当前 status={updated.status}）",
        )
    return updated


__all__ = [
    "PipelineFrontBlocked",
    "DEFAULT_REQUESTED_STAGES",
    "ensure_series_plan_for_pipeline",
    "ensure_series_run_for_pipeline",
    "publication_run_idempotency_key",
    "run_front_to_shots",
]
