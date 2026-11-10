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
    "voice_binding_missing": "voice_binding_missing",
}

# blocker_code -> Chinese, actionable repair hint for the one-click UI
BLOCKER_REPAIR_HINTS = {
    "models_not_configured": "请到「模型设置」填写 API Key，点「保存并检测」通过后再试。",
    "voice_selection_required": "请到「模型设置」确认语音模型可用，然后重新点「一键生成」。",
    "voice_binding_missing": "说话角色还没配音色。请重新点「一键生成」（系统会自动绑定默认音色），或到角色页手动选音色。",
    "live_calls_not_opted_in": "请到「模型设置」开启真实模型调用并确认费用上限后再试。",
    "queue_dead_letter": "任务重试次数已用尽。请到小说详情页点「重试」，或检查后台 Worker / Redis 后重新提交。",
    "series_run_media_preflight_failed": "媒体前置检查未通过。请根据页面提示补齐模型、音色或素材后重试。",
}


def actionable_blocker_detail(code: str, detail: str = "") -> str:
    """Prefer a Chinese repair hint; keep original detail as secondary context."""
    hint = BLOCKER_REPAIR_HINTS.get(str(code) or "")
    text = (detail or "").strip()
    if hint and text and text not in hint:
        return f"{hint}（{text}）"
    return hint or text or str(code)


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


async def ensure_speaking_voice_bindings(
    db: AsyncSession, run: SeriesProductionRun, *, force_entity_ids: list[str] | None = None,
) -> int:
    """Bind a usable default TTS voice onto every speaking character missing one.

    One-click ``persist_voice_selection`` only stores the run-level protagonist
    selection. Media preflight requires **each** speaking entity to carry
    ``voice_binding``; without this step, real-model multi-character novels hit
    ``voice_binding_missing`` and stall. Fake mode is usually covered by the
    acceptance fixture, but we still fill gaps so both paths stay consistent.

    Returns the number of entities newly bound.
    """
    from sqlalchemy import select
    from sqlalchemy.orm.attributes import flag_modified

    from app.models.story_entity import StoryEntity
    from app.services.story_entity_lifecycle import get_entity_review_status

    selection = dict((run.run_metadata or {}).get("voice_selection") or {})
    voice_id = str(selection.get("voice_id") or "").strip()
    if not voice_id:
        return 0

    # Prefer distinct voices when the allowlist exposes more than one option.
    option_ids: list[str] = []
    raw_options = ((run.run_metadata or {}).get("voice_options_cache") or {}).get("options") or []
    for item in raw_options:
        if isinstance(item, dict) and item.get("voice_id"):
            option_ids.append(str(item["voice_id"]))
    if voice_id not in option_ids:
        option_ids.insert(0, voice_id)
    if not option_ids:
        option_ids = [voice_id]

    rows = list(
        (
            await db.scalars(
                select(StoryEntity).where(
                    StoryEntity.user_id == run.user_id,
                    StoryEntity.novel_id == run.novel_id,
                    StoryEntity.entity_type == "character",
                )
            )
        ).all()
    )
    forced = {str(item) for item in (force_entity_ids or []) if item}
    bound = 0
    voice_index = 0
    for entity in rows:
        status = get_entity_review_status(entity)
        if status in {"rejected", "archived"}:
            continue
        attrs = dict(entity.attributes or {})
        # Dialogue-derived speakers may appear only via preflight entity_ids.
        if not attrs.get("speaking") and entity.id not in forced:
            continue
        binding = dict(attrs.get("voice_binding") or {})
        if binding.get("voice_id") and binding.get("status") in {"approved", "locked", "legacy"}:
            continue
        chosen = option_ids[voice_index % len(option_ids)]
        voice_index += 1
        attrs["voice_binding"] = {
            "voice_id": chosen,
            "version": int(selection.get("version") or 1),
            "status": "locked",
            "provider_id": selection.get("provider_id"),
            "config_id": selection.get("config_id"),
            "db_model_id": selection.get("db_model_id") or selection.get("model_id"),
            "api_model_id": selection.get("api_model_id"),
            "tested_at": selection.get("tested_at"),
            "source": "one_click_default_voice",
        }
        attrs["speaking"] = True
        entity.attributes = attrs
        flag_modified(entity, "attributes")
        bound += 1
    if bound:
        _record(run, "speaking_voice_bindings", f"bound:{bound}")
        await db.commit()
    return bound


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
    # Cache allowlisted options for multi-character default binding (no network).
    if voice and isinstance(voice.get("options"), list):
        meta = dict(run.run_metadata or {})
        meta["voice_options_cache"] = {
            "config_id": voice.get("config_id"),
            "options": list(voice.get("options") or []),
        }
        run.run_metadata = meta
        await db.commit()
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

    # 7. speaking-character voices (real multi-character: close voice_binding_missing)
    await ensure_speaking_voice_bindings(db, run)
    await db.refresh(run)

    # 8. preflight (real mode: one automatic re-bind when bindings went stale)
    preflight = await evaluate_media_preflight(db, run)
    if not preflight.get("ready") and not fake and "model_bindings_not_fresh" in (preflight.get("codes") or []):
        await auto_bind_models(db, run)
        await db.refresh(run)
        preflight = await evaluate_media_preflight(db, run)
    if not preflight.get("ready") and "voice_binding_missing" in (preflight.get("codes") or []):
        # One more pass after preflight named the missing speakers (dialogue-derived).
        missing_ids: list[str] = []
        for issue in preflight.get("issues") or []:
            if isinstance(issue, dict) and issue.get("code") == "voice_binding_missing":
                missing_ids.extend(str(i) for i in (issue.get("entity_ids") or []) if i)
        await ensure_speaking_voice_bindings(db, run, force_entity_ids=missing_ids)
        await db.refresh(run)
        preflight = await evaluate_media_preflight(db, run)
    if not preflight.get("ready"):
        codes = [str(c) for c in preflight.get("codes") or []]
        first = codes[0] if codes else "series_run_media_preflight_failed"
        mapped = PREFLIGHT_CODE_MAP.get(first, first)
        raise PipelineMediaBlocked(
            mapped,
            actionable_blocker_detail(mapped, "媒体前置检查未通过：" + ",".join(codes)),
        )
    _record(run, "preflight", "passed")
    await db.commit()
    await db.refresh(run)
    return run


__all__ = ["BLOCKER_REPAIR_HINTS", "PREFLIGHT_CODE_MAP", "actionable_blocker_detail", "auto_bind_models", "ensure_speaking_voice_bindings", "prepare_run_for_media"]
