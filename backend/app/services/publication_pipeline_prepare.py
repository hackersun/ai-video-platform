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
from app.services.live_canary_bindings import (
    BindingValidationError, required_tested_at_for_run, validate_required_model_bindings,
)
from app.services.publication_pipeline_media import PipelineMediaBlocked
from app.services.simple_model_setup import CAPABILITY_LABELS, ensure_fresh, resolve_effective_configs

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


MODELS_HINT = "请到「模型设置」填写 API Key 并测试连接"


async def auto_bind_models(db: AsyncSession, run: SeriesProductionRun) -> None:
    """Bind the user's effective defaults (novel override > global default), re-testing stale ones."""
    resolved = await resolve_effective_configs(db, run.user_id, run.novel_id)
    missing = [CAPABILITY_LABELS[c] for c in REQUIRED_CAPABILITIES if not resolved.get(c)]
    if missing:
        raise PipelineMediaBlocked("models_not_configured", f"尚未配置{'、'.join(missing)}模型，{MODELS_HINT}")
    required_at = required_tested_at_for_run(run)
    wanted = {c: resolved[c] for c in REQUIRED_CAPABILITIES}
    failures = await ensure_fresh(db, wanted, not_before=required_at)
    if failures:
        raise PipelineMediaBlocked("models_not_configured", "；".join(failures.values()) + f"。{MODELS_HINT}")
    try:
        await validate_required_model_bindings(
            db, run, {c: wanted[c][0].id for c in REQUIRED_CAPABILITIES},
            required_tested_at=required_at, persist=True,
        )
    except BindingValidationError as exc:
        raise PipelineMediaBlocked("models_not_configured", f"模型绑定校验失败：{exc}。{MODELS_HINT}") from exc
    _record(run, "auto_bind", "passed")


def _preferred_voice(options: List[str], *, fake: bool, saved: str | None) -> str | None:
    if fake and "deterministic-protagonist-voice" in options:
        return "deterministic-protagonist-voice"
    if saved and saved in options:
        return saved
    return options[0] if options else None


async def _saved_default_voice(db: AsyncSession, config_id: str | None) -> str | None:
    if not config_id or db is None:
        return None
    from app.models.llm_config import LLMConfig

    config = await db.get(LLMConfig, config_id)
    extra = (config.extra_params if config is not None and isinstance(config.extra_params, dict) else {})
    return str(extra.get("default_voice_id") or "") or None


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
    from app.services.live_canary_budget import InvalidAccountingInput, trusted_live_canary_policy
    from app.services.series_run_live_preflight import build_live_preflight_plan, persist_voice_selection
    from app.services.series_run_reference_preparation import (
        ReferencePreparationBlocked, default_reference_adapter, prepare_series_reference,
    )

    if run.status not in {"shots_ready", "anchor_ready"}:
        return run
    fake = deterministic_provider_fake_enabled()

    # 1. model bindings: deterministic fixture in fake mode; otherwise the user's
    #    model settings are bound automatically (stale tests are re-run server-side)
    if fake:
        if not (run.run_metadata or {}).get("deterministic_acceptance") or not _bindings_complete(run):
            await setup_acceptance_fixture(db, user_id=run.user_id, novel_id=run.novel_id)
            await db.refresh(run)
        _record(run, "setup", "passed")
    elif not _bindings_complete(run):
        await auto_bind_models(db, run)
        await db.refresh(run)

    # 2. live-call switch: fake mode may auto-enable; live mode requires explicit opt-in
    if fake:
        if (run.budget_policy or {}).get("profile") != "isolated_live_canary":
            try:
                run.budget_policy = trusted_live_canary_policy({"profile": "isolated_live_canary"})
            except InvalidAccountingInput as exc:
                raise PipelineMediaBlocked(
                    "live_canary_unavailable", f"服务端未配置真实调用预算上限，请联系管理员（{exc}）",
                ) from exc
    else:
        from app.services.billing_guard import get_or_create_settings
        settings = await get_or_create_settings(db, run.user_id)
        if not settings.live_calls_opt_in:
            raise PipelineMediaBlocked(
                "live_calls_not_opted_in",
                "尚未开启真实模型调用。请到「模型设置」开启并确认费用上限后再试。",
            )
        if (run.budget_policy or {}).get("profile") != "isolated_live_canary":
            try:
                run.budget_policy = trusted_live_canary_policy({"profile": "isolated_live_canary"})
            except InvalidAccountingInput as exc:
                raise PipelineMediaBlocked(
                    "live_canary_unavailable", f"服务端未配置真实调用预算上限，请联系管理员（{exc}）",
                ) from exc
    await db.commit()
    await db.refresh(run)

    # 3. voice selection
    plan = await build_live_preflight_plan(db, run)
    voice = plan.get("voice_options") or {}
    if voice and not voice.get("selection"):
        options = [o.get("voice_id") for o in voice.get("options") or [] if o.get("voice_id")]
        saved = None if fake else await _saved_default_voice(db, voice.get("config_id"))
        voice_id = _preferred_voice(options, fake=fake, saved=saved)
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
    blocker = anchor_coverage_blocker(full, mode="full", episodes=shots)
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

    # 7. preflight (real mode: one automatic re-bind when bindings went stale)
    preflight = await evaluate_media_preflight(db, run)
    if not preflight.get("ready") and not fake and "model_bindings_not_fresh" in (preflight.get("codes") or []):
        await auto_bind_models(db, run)
        await db.refresh(run)
        preflight = await evaluate_media_preflight(db, run)
    if not preflight.get("ready"):
        codes = [str(c) for c in preflight.get("codes") or []]
        first = codes[0] if codes else "series_run_media_preflight_failed"
        raise PipelineMediaBlocked(PREFLIGHT_CODE_MAP.get(first, first), "媒体前置检查未通过：" + ",".join(codes))
    _record(run, "preflight", "passed")
    await db.commit()
    await db.refresh(run)
    return run


__all__ = ["auto_bind_models", "prepare_run_for_media", "PREFLIGHT_CODE_MAP"]
