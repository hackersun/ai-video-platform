"""P3: media/quality automation helpers for publication pipelines."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.publication_pipeline import NovelPublicationPipeline
from app.models.series_production_run import SeriesProductionRun
from app.services.series_run_orchestrator import SeriesRunOrchestrator

EnterMediaFn = Callable[[AsyncSession, SeriesProductionRun], Awaitable[SeriesProductionRun]]
ListShotsFn = Callable[[AsyncSession, SeriesProductionRun], Awaitable[Tuple[list, Dict[str, str]]]]
GenerateFn = Callable[..., Awaitable[Dict[str, Any]]]


class PipelineMediaBlocked(Exception):
    def __init__(self, code: str, detail: str = ""):
        self.code = code
        self.detail = detail or code
        super().__init__(self.detail)


def commercial_required(pipeline: NovelPublicationPipeline, *, env_flag: bool = False) -> bool:
    gates = pipeline.gates if isinstance(pipeline.gates, dict) else {}
    if gates.get("require_commercial_gates") is True:
        return True
    return bool(env_flag)


def resolve_shot_scope(
    media_policy: Optional[Dict[str, Any]],
    gates: Optional[Dict[str, Any]],
    *,
    env_commercial: bool = False,
) -> str:
    policy = media_policy if isinstance(media_policy, dict) else {}
    gate_cfg = gates if isinstance(gates, dict) else {}
    scope = str(policy.get("shot_scope") or "all_episode_shots").strip() or "all_episode_shots"
    allow_anchor = policy.get("allow_anchor_smoke_only") is True
    commercial = gate_cfg.get("require_commercial_gates") is True or env_commercial
    if scope == "anchor_shots_only":
        if commercial or not allow_anchor:
            raise PipelineMediaBlocked(
                "anchor_shots_only_forbidden",
                "商用门禁或未显式允许时禁止 anchor_shots_only 静默降级",
            )
    return scope


def _all_shot_ids(run: SeriesProductionRun) -> List[str]:
    ids: List[str] = []
    for episode in run.episodes or []:
        canonical = episode.get("canonical_ids") or {}
        for shot_id in canonical.get("shot_ids") or []:
            ids.append(str(shot_id))
    return ids


def _quality_blocker_from_generate_result(result: Dict[str, Any]) -> Optional[str]:
    error_code = result.get("error_code")
    if error_code == "trusted_multimodal_evaluation_required":
        return "trusted_multimodal_evaluation_required"
    if error_code:
        return str(error_code)
    quality_results = result.get("quality_results") or []
    if result.get("status") == "completed" and quality_results:
        if any(isinstance(item, dict) and item.get("ready") is not True for item in quality_results):
            return "quality_gate_incomplete"
    return None


async def run_media_quality_for_pipeline(
    db: AsyncSession,
    run: SeriesProductionRun,
    pipeline: NovelPublicationPipeline,
    *,
    enter_media_fn: Optional[EnterMediaFn] = None,
    list_shots_fn: Optional[ListShotsFn] = None,
    generate_fn: Optional[GenerateFn] = None,
    env_commercial: bool = False,
) -> SeriesProductionRun:
    """Drive shots_ready → media → quality → completed (or raise PipelineMediaBlocked)."""
    if run.status == "completed":
        media_tail = ((run.gate_summary or {}).get("media_tail") or {})
        if media_tail.get("result") == "passed":
            return run

    scope = resolve_shot_scope(pipeline.media_policy, pipeline.gates, env_commercial=env_commercial)

    if enter_media_fn is None:
        orch = SeriesRunOrchestrator()

        async def _enter(db_session: AsyncSession, current: SeriesProductionRun) -> SeriesProductionRun:
            return await orch.enter_media_running(db_session, current)

        enter_media_fn = _enter

    if run.status in {"shots_ready", "anchor_ready"}:
        run = await enter_media_fn(db, run)
        await db.refresh(run)

    if generate_fn is None:
        raise PipelineMediaBlocked(
            "media_generate_fn_missing",
            "缺少媒体生成钩子；Worker 必须注入 generate_selected 路径",
        )

    shots: list = []
    workflow_for_shot: Dict[str, str] = {}
    if list_shots_fn is not None:
        shots, workflow_for_shot = await list_shots_fn(db, run)

    if scope == "all_episode_shots":
        requested = _all_shot_ids(run) or [str(getattr(s, "id", s)) for s in shots]
        mode = "full"
    else:
        # Non-commercial anchor smoke only (already validated by resolve_shot_scope).
        meta = run.run_metadata or {}
        requested = list(meta.get("selected_anchor_shot_ids") or [])
        mode = str(meta.get("selected_anchor_mode") or "smoke")
        if not requested:
            raise PipelineMediaBlocked("anchor_selection_missing", "缺少已锁定的 anchor 镜头选择")

    if not requested:
        raise PipelineMediaBlocked("shots_missing", "Series Run 尚无镜头可生成")

    result = await generate_fn(
        db,
        run=run,
        user_id=pipeline.user_id,
        shots=shots,
        workflow_for_shot=workflow_for_shot,
        requested=requested,
        mode=mode,
    )
    blocker = _quality_blocker_from_generate_result(result if isinstance(result, dict) else {})
    await db.refresh(run)
    if blocker:
        raise PipelineMediaBlocked(blocker, blocker)
    if run.status != "completed":
        media_tail = ((run.gate_summary or {}).get("media_tail") or {})
        if media_tail.get("result") != "passed":
            raise PipelineMediaBlocked(
                media_tail.get("blocker_code") or "quality_gate_incomplete",
                "媒体尾部未通过质量门禁",
            )
        # generate path may have closed tail without refresh showing completed yet
        if run.status not in {"completed", "evaluating"}:
            raise PipelineMediaBlocked(
                "media_quality_incomplete",
                f"Run 未完成媒体质量阶段（status={run.status}）",
            )
    media_tail = ((run.gate_summary or {}).get("media_tail") or {})
    if media_tail.get("result") == "blocked":
        raise PipelineMediaBlocked(
            media_tail.get("blocker_code") or "quality_gate_incomplete",
            "媒体尾部 blocked",
        )
    return run


__all__ = [
    "PipelineMediaBlocked",
    "commercial_required",
    "resolve_shot_scope",
    "run_media_quality_for_pipeline",
]
