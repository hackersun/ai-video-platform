"""One-click media preparation for publication pipelines.

Folds the manual Series Run prep sequence (setup → live canary → voice →
full anchor selection → story locks → reference → preflight) into the
pipeline so ``POST /novels/{id}/publication-pipelines`` needs no other calls.
Every step is idempotent; anything that genuinely needs a human fails closed
with a ``PipelineMediaBlocked`` carrying a stable ``blocker_code``.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.publication_pipeline import NovelPublicationPipeline
from app.models.series_production_run import SeriesProductionRun
from app.services.publication_pipeline_media import PipelineMediaBlocked

logger = logging.getLogger(__name__)

REQUIRED_CAPABILITIES = ("text", "image", "tts", "video")

# preflight issue code -> pipeline blocker_code (human-actionable)
PREFLIGHT_CODE_MAP = {
    "model_bindings_not_fresh": "models_not_configured",
    "model_bindings_missing": "models_not_configured",
    "voice_selection_required": "voice_selection_required",
    "voice_selection_stale": "voice_selection_required",
}


def _record(run: SeriesProductionRun, step: str, result: str) -> None:
    meta = dict(run.run_metadata or {})
    prep = dict(meta.get("pipeline_prep") or {})
    prep[step] = result
    meta["pipeline_prep"] = prep
    run.run_metadata = meta


def _bindings_complete(run: SeriesProductionRun) -> bool:
    caps = ((run.model_bindings or {}).get("capabilities") or {})
    return all(isinstance(caps.get(c), dict) and caps[c].get("config_id") for c in REQUIRED_CAPABILITIES)


async def prepare_run_for_media(
    db: AsyncSession, run: SeriesProductionRun, pipeline: NovelPublicationPipeline,
) -> SeriesProductionRun:
    from app.api.v1.endpoints.series_runs import _run_shots
    from app.features.series_run_acceptance import setup_acceptance_fixture
    from app.features.series_run_media_preflight.public import evaluate_media_preflight
    from app.features.series_run_story_locks.public import (
        StoryLockPreparationBlocked, prepare_story_locks, safe_story_lock_error_detail,
    )
    from app.services.anchor_shot_service import anchor_coverage_blocker, recommend_anchor_shots
    from app.services.deterministic_provider_fake import deterministic_provider_fake_enabled
    from app.services.live_canary_budget import BindingValidationError, InvalidAccountingInput, trusted_live_canary_policy
    from app.services.series_run_live_preflight import build_live_preflight_plan, persist_voice_selection
    from app.services.series_run_reference_preparation import (
        ReferencePreparationBlocked, default_reference_adapter, prepare_series_reference,
    )

    if run.status not in {"shots_ready", "anchor_ready"}:
        return run
    fake = deterministic_provider_fake_enabled()

    # 1. model bindings (deterministic fixture in fake mode; must pre-exist otherwise)
    if fake:
        if not (run.run_metadata or {}).get("deterministic_acceptance") or not _bindings_complete(run):
            await setup_acceptance_fixture(db, user_id=run.user_id, novel_id=run.novel_id)
            await db.refresh(run)
        _record(run, "setup", "passed")
    elif not _bindings_complete(run):
        raise PipelineMediaBlocked("models_not_configured", "尚未配置并测试文本/图片/配音/视频模型，请先到模型中心完成配置")

    # 2. budget profile
    if fake and ((run.budget_policy or {}).get("profile") != "isolated_live_canary"):
        try:
            run.budget_policy = trusted_live_canary_policy({"profile": "isolated_live_canary"})
        except InvalidAccountingInput as exc:
            raise PipelineMediaBlocked("live_canary_unavailable", str(exc)) from exc
    await db.commit()
    await db.refresh(run)

    # 3. voice selection
    plan = await build_live_preflight_plan(db, run)
    voice = plan.get("voice_options") or {}
    if voice and not voice.get("selection"):
        options = [o.get("voice_id") for o in voice.get("options") or [] if o.get("voice_id")]
        preferred = "deterministic-protagonist-voice" if fake else None
        voice_id = preferred if preferred in options else (options[0] if fake and options else None)
        if not voice_id:
            raise PipelineMediaBlocked("voice_selection_required", "需要为主角选择配音声线")
        try:
            await persist_voice_selection(db, run, config_id=voice["config_id"], model_id=voice["model_id"],
                                          voice_id=voice_id, version=1)
        except BindingValidationError as exc:
            await db.rollback()
            raise PipelineMediaBlocked("voice_selection_required", str(exc)) from exc
        await db.refresh(run)
        if fake:  # setup re-applies the voice binding onto the protagonist
            await setup_acceptance_fixture(db, user_id=run.user_id, novel_id=run.novel_id)
            await db.refresh(run)
    _record(run, "voice", "passed")

    # 4. full anchor selection covering every shot
    shots, _ = await _run_shots(db, run)
    full = recommend_anchor_shots(shots, mode="full")
    blocker = anchor_coverage_blocker(full, mode="full")
    if blocker:
        code = blocker.get("code") if isinstance(blocker, dict) else str(blocker)
        raise PipelineMediaBlocked("full_shot_selection_required", f"无法覆盖全部镜头：{code}")
    selected: List[str] = [item["shot_id"] for item in full]
    meta = dict(run.run_metadata or {})
    if meta.get("selected_anchor_mode") != "full" or list(meta.get("selected_anchor_shot_ids") or []) != selected:
        meta["selected_anchor_shot_ids"] = selected
        meta["selected_anchor_mode"] = "full"
        meta["anchor_selection_revision"] = int(meta.get("anchor_selection_revision") or 0) + 1
        run.run_metadata = meta
    _record(run, "anchors", "passed")
    await db.commit()
    await db.refresh(run)

    # 5. story locks  6. reference
    try:
        await prepare_story_locks(db, run)
    except StoryLockPreparationBlocked as exc:
        detail: Dict[str, Any] = safe_story_lock_error_detail(exc) or {}
        raise PipelineMediaBlocked(str(detail.get("code") or "story_lock_blocked"),
                                   str(detail.get("message") or exc)
                                   + (f"（{exc.__cause__}）" if exc.__cause__ else "")) from exc
    await db.refresh(run)
    try:
        await prepare_series_reference(db, run, adapter=default_reference_adapter())
    except ReferencePreparationBlocked as exc:
        raise PipelineMediaBlocked("reference_preparation_blocked", str(exc)) from exc
    await db.refresh(run)

    # 7. preflight
    preflight = await evaluate_media_preflight(db, run)
    if not preflight.get("ready"):
        codes = [str(c) for c in preflight.get("codes") or []]
        first = codes[0] if codes else "series_run_media_preflight_failed"
        raise PipelineMediaBlocked(PREFLIGHT_CODE_MAP.get(first, first), "媒体前置检查未通过：" + ",".join(codes))
    _record(run, "preflight", "passed")
    await db.commit()
    await db.refresh(run)
    return run


__all__ = ["prepare_run_for_media", "PREFLIGHT_CODE_MAP"]
