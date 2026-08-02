"""Network-free preparation and planning for a four-chapter live canary."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.time_utils import utc_now
from app.models import Asset, Chapter, LLMConfig, LLMModel, MediaGenerationJob, ProviderAssetBinding, Shot, StoryBible, Workflow
from app.models.series_production_run import SeriesProductionRun
from app.services.live_canary_budget import (
    BindingValidationError,
    required_tested_at_for_run,
    validate_model_bindings,
)
from app.services.live_canary_bindings import validate_persisted_model_bindings
from app.services.live_canary_repair_budget import effective_budget_maximum
from app.features.series_run_media_preflight.public import evaluate_media_preflight
from app.services.shot_quality_service import extract_dialogue_speaker
from app.services.shot_image_delivery import is_live_ready_shot_image
from app.services.anchor_shot_service import ANCHOR_MODE_CONTRACTS
from app.services.dialogue_lineage_service import extract_explicit_dialogue
from app.services.media_job_selection import latest_non_superseded_by_shot
from app.services.shot_input_fingerprint import shot_input_fingerprint
from app.features.series_run_story_locks.public import (
    StoryLockPreparationBlocked,
    inspect_story_lock_freshness,
    invalidate_story_lock_lineage,
    prepare_story_locks,
    provider_voice_allowlist as _provider_voice_allowlist,
    selection_hash as _selection_hash,
    valid_voice_selection as _valid_voice_selection,
)


async def _validated_voice_context(db: AsyncSession, run: SeriesProductionRun) -> tuple[dict[str, str], LLMConfig, LLMModel, tuple[str, ...]]:
    bindings = {
        capability: str((((run.model_bindings or {}).get("capabilities") or {}).get(capability) or {}).get("config_id") or "")
        for capability in ("text", "image", "tts", "video")
    }
    snapshots = await validate_model_bindings(
        db, run, bindings, required_tested_at=required_tested_at_for_run(run),
        freshness_seconds=900, persist=False,
    )
    snapshot = snapshots["tts"]
    config = await db.get(LLMConfig, snapshot["config_id"])
    model = await db.get(LLMModel, snapshot["db_model_id"])
    allowlist = _provider_voice_allowlist(snapshot["provider_id"])
    if config is None or model is None or not allowlist:
        raise BindingValidationError("fresh TTS binding has no safe voice options")
    return snapshot, config, model, allowlist


async def _supersede_voice_lineage(db: AsyncSession, run: SeriesProductionRun, *, reason: str) -> None:
    await invalidate_story_lock_lineage(db, run, reason=reason)


async def voice_options_for_run(db: AsyncSession, run: SeriesProductionRun) -> dict[str, Any]:
    snapshot, _config, _model, allowlist = await _validated_voice_context(db, run)
    selection = _valid_voice_selection(run, snapshot, allowlist)
    return {
        "config_id": snapshot["config_id"], "model_id": snapshot["db_model_id"],
        "provider_id": snapshot["provider_id"], "tested_at": snapshot["tested_at"],
        "options": [{"voice_id": voice_id, "label": voice_id} for voice_id in allowlist],
        "selection": selection,
    }


async def persist_voice_selection(
    db: AsyncSession, run: SeriesProductionRun, *, config_id: str, model_id: str, voice_id: str, version: int,
) -> dict[str, Any]:
    snapshot, _config, _model, allowlist = await _validated_voice_context(db, run)
    if config_id != snapshot["config_id"] or model_id != snapshot["db_model_id"]:
        raise BindingValidationError("voice selection does not match the current TTS binding snapshot")
    if voice_id not in allowlist or version < 1:
        raise BindingValidationError("voice selection is not allowed by the bound provider")
    selection = {**snapshot, "voice_id": voice_id, "version": version}
    selection["selection_hash"] = _selection_hash(selection)
    metadata = dict(run.run_metadata or {})
    previous = metadata.get("voice_selection")
    if previous and previous.get("selection_hash") != selection["selection_hash"]:
        await _supersede_voice_lineage(db, run, reason="voice_selection_changed")
        metadata = dict(run.run_metadata or {})
        metadata.setdefault("superseded_voice_selections", []).append({**previous, "superseded_at": utc_now().isoformat()})
    metadata["voice_selection"] = selection
    run.run_metadata = metadata
    flag_modified(run, "run_metadata")
    await db.commit()
    return selection


def _fingerprint(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _money(value: Any) -> Decimal | None:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not amount.is_finite() or amount < 0:
        return None
    return amount.quantize(Decimal("0.01"))


def _money_text(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), ".2f")


async def _selected_anchor_shots(db: AsyncSession, run: SeriesProductionRun) -> list[tuple[int, Shot]]:
    selected = [str(item) for item in ((run.run_metadata or {}).get("selected_anchor_shot_ids") or [])]
    mode = str((run.run_metadata or {}).get("selected_anchor_mode") or "smoke")
    required_count = ANCHOR_MODE_CONTRACTS.get(mode, ANCHOR_MODE_CONTRACTS["smoke"])["target_count"]
    if len(selected) != required_count or len(set(selected)) != required_count:
        return []
    episode_by_shot: dict[str, int] = {}
    allowed: set[str] = set()
    for episode in run.episodes or []:
        for shot_id in (episode.get("canonical_ids") or {}).get("shot_ids") or []:
            allowed.add(str(shot_id))
            episode_by_shot[str(shot_id)] = int(episode.get("episode_number") or 0)
    if any(item not in allowed for item in selected):
        return []
    rows = list((await db.scalars(select(Shot).where(Shot.id.in_(selected), Shot.user_id == run.user_id))).all())
    by_id = {item.id: item for item in rows}
    if set(by_id) != set(selected):
        return []
    return [(episode_by_shot[item], by_id[item]) for item in selected]


async def _story_preflight(
    db: AsyncSession, run: SeriesProductionRun, *, native_audio: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    blockers: list[dict[str, Any]] = []
    freshness = await inspect_story_lock_freshness(db, run, supersede=False)
    if freshness.get("code") == "story_lock_stale":
        blockers.append({"code": "story_lock_stale", "message": "章节、实体、风格、Bible 或运行输入已变化"})
        return {
            "ready": False,
            "issues": [dict(blockers[0])],
            "codes": ["story_lock_stale"],
        }, blockers
    try:
        hard_preflight = await evaluate_media_preflight(db, run, native_audio=native_audio)
        blockers.extend(hard_preflight.get("issues") or [])
    except Exception:
        hard_preflight = {"ready": False, "issues": []}
        blockers.append({"code": "hard_preflight_unavailable", "message": "媒体预检暂不可用"})
    return hard_preflight, blockers


async def _anchor_preflight(
    db: AsyncSession, run: SeriesProductionRun, *, native_audio: bool = False,
) -> tuple[list[dict[str, Any]], int, bool, list[dict[str, Any]]]:
    blockers: list[dict[str, Any]] = []
    dialogue_contracts: list[dict[str, Any]] = []
    dialogue_count = 0
    voice_selection_required = False

    anchors = await _selected_anchor_shots(db, run)
    selected_mode = str((run.run_metadata or {}).get("selected_anchor_mode") or "smoke")
    contract = ANCHOR_MODE_CONTRACTS.get(selected_mode, ANCHOR_MODE_CONTRACTS["smoke"])
    required_anchor_count = contract["target_count"]
    required_episode_count = contract["required_episodes"]
    if len(anchors) != required_anchor_count or len({item[0] for item in anchors}) < required_episode_count:
        blockers.append({
            "code": "anchor_coverage_insufficient",
            "message": f"需要 {required_anchor_count} 个关键镜头覆盖 {required_episode_count} 章",
        })
    for episode_number, shot in anchors:
        extra = shot.extra_data or {}
        dialogue = str(shot.dialogue or extra.get("subtitle_text") or "").strip()
        speaker = extract_dialogue_speaker(dialogue, extra) if dialogue else None
        if dialogue:
            dialogue_count += 1
            voice_selection_required = voice_selection_required or (
                not native_audio and isinstance(extra.get("dialogue_source"), dict)
            )
            if not speaker:
                blockers.append({"code": "dialogue_speaker_unknown", "message": "对白说话人未知", "shot_id": shot.id})
        dialogue_contracts.append({
            "shot_id": shot.id, "episode_number": episode_number, "dialogue": dialogue,
            "speaker": speaker, "requires_tts": bool(dialogue) and not native_audio,
            "audio_route": "video_native_audio" if native_audio and dialogue else "tts" if dialogue else "none",
            "first_frame_ready": is_live_ready_shot_image(shot.image_url),
            "contract_hash": _fingerprint({"shot_id": shot.id, "dialogue": dialogue, "speaker": speaker}),
        })
        if not is_live_ready_shot_image(shot.image_url):
            blockers.append({
                "code": "shot_first_frame_missing",
                "message": "关键镜头缺少已生成首帧，请先补齐首帧后再生成视频",
                "shot_id": shot.id,
            })
    return dialogue_contracts, dialogue_count, voice_selection_required, blockers


async def _pending_video_count(db: AsyncSession, run: SeriesProductionRun, anchors: list[tuple[int, Shot]]) -> int:
    shot_ids = [shot.id for _, shot in anchors]
    if not shot_ids:
        return 0
    jobs = list((await db.scalars(select(MediaGenerationJob).where(
        MediaGenerationJob.user_id == run.user_id,
        MediaGenerationJob.shot_id.in_(shot_ids),
        MediaGenerationJob.is_active.is_(True),
        MediaGenerationJob.status.in_(("succeeded", "completed")),
    ))).all())
    latest = latest_non_superseded_by_shot(jobs)
    return sum(
        not (job := latest.get(shot.id))
        or str((job.extra_data or {}).get("shot_input_fingerprint") or "") != shot_input_fingerprint(shot)
        for _, shot in anchors
    )


def _budget_preflight(
    run: SeriesProductionRun, *, anchor_count: int, dialogue_count: int,
    missing_first_frame_count: int = 0,
    native_audio: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, str], list[dict[str, Any]]]:
    blockers: list[dict[str, Any]] = []
    policy = run.budget_policy or {}
    estimates = policy.get("estimates_rmb") or {}
    cost_breakdown: list[dict[str, Any]] = []
    projected = Decimal("0")
    if any(
        key in estimates and _money(estimates.get(key)) is None
        for key in ("image", "video", "tts", "text")
    ):
        blockers.append({"code": "budget_accounting_invalid", "message": "预算估算包含损坏金额"})
    reference = (run.run_metadata or {}).get("reference_preparation") or {}
    reference_required = not bool(reference.get("asset_id") and reference.get("asset_version"))
    requirements = (
        ("image", (1 if reference_required else 0) + missing_first_frame_count),
        ("video", anchor_count),
        ("tts", 0 if native_audio else dialogue_count),
    )
    for capability, quantity in requirements:
        if quantity == 0:
            continue
        unit = _money(estimates.get(capability))
        if unit is None or unit <= 0:
            blockers.append({"code": f"{capability}_estimate_missing", "message": f"缺少可信 {capability} 成本估算"})
            continue
        subtotal = unit * quantity
        projected += subtotal
        cost_breakdown.append({
            "capability": capability, "quantity": quantity,
            "unit_estimate_rmb": _money_text(unit), "subtotal_rmb": _money_text(subtotal),
            "source": "server_trusted_policy",
        })
    summary = run.cost_summary or {}
    spent = _money(summary.get("spent_rmb", "0"))
    reserved = _money(summary.get("reserved_rmb", "0"))
    accounting_invalid = spent is None or reserved is None
    if accounting_invalid:
        blockers.append({"code": "budget_accounting_invalid", "message": "预算账本金额损坏或不是有限非负数"})
        spent = Decimal("0")
        reserved = Decimal("0")
    configured_maximum = _money(policy.get("max_rmb"))
    if "max_rmb" in policy and configured_maximum is None:
        blockers.append({"code": "budget_accounting_invalid", "message": "预算上限金额损坏"})
    wave_one_maximum = Decimal("10.00")
    if policy.get("profile") != "isolated_live_canary" or policy.get("live_canary") is not True or configured_maximum is None:
        blockers.append({"code": "trusted_budget_policy_missing", "message": "缺少服务端可信预算策略"})
        maximum = Decimal("0")
    else:
        maximum = (
            effective_budget_maximum(run)
            if configured_maximum == wave_one_maximum
            else min(configured_maximum, wave_one_maximum)
        )
        if configured_maximum != wave_one_maximum:
            blockers.append({"code": "wave_one_budget_policy_invalid", "message": "Wave 1 服务端预算上限必须恰好为 RMB10"})
    remaining = max(Decimal("0"), maximum - spent - reserved)
    projected_total = spent + reserved + projected
    if projected_total > maximum:
        blockers.append({"code": "projected_budget_exceeded", "message": "预计成本超过最大预算"})
    budget = {
        "maximum_rmb": _money_text(maximum), "spent_rmb": _money_text(spent),
        "reserved_rmb": _money_text(reserved), "remaining_rmb": _money_text(remaining),
        "projected_increment_rmb": _money_text(projected), "projected_total_rmb": _money_text(projected_total),
    }
    return cost_breakdown, budget, blockers


async def _binding_preflight(
    db: AsyncSession, run: SeriesProductionRun, *, required_capabilities: set[str],
    voice_selection_required: bool,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    blockers: list[dict[str, Any]] = []
    capabilities = (run.model_bindings or {}).get("capabilities") or {}
    config_ids = {
        name: str((capabilities.get(name) or {}).get("config_id") or "")
        for name in required_capabilities
    }
    voice_options = None
    try:
        await validate_persisted_model_bindings(
            db, run, required_capabilities=required_capabilities,
        )
        if "tts" in required_capabilities:
            snapshot, _voice_config, _voice_model, allowlist = await _validated_voice_context(db, run)
            selection = _valid_voice_selection(run, snapshot, allowlist)
            if (run.run_metadata or {}).get("voice_selection") and selection is None:
                blockers.append({"code": "voice_selection_stale", "message": "声线选择所依赖的配置测试快照已变化，需要重新选择"})
            voice_options = {
                "config_id": snapshot["config_id"], "model_id": snapshot["db_model_id"],
                "provider_id": snapshot["provider_id"], "tested_at": snapshot["tested_at"],
                "options": [{"voice_id": voice_id, "label": voice_id} for voice_id in allowlist],
                "selection": selection,
            }
            if voice_selection_required and selection is None:
                blockers.append({"code": "voice_selection_required", "message": "需要从当前 TTS 配置的安全声线列表中显式锁定声线"})
    except BindingValidationError:
        if "tts" in required_capabilities and (run.run_metadata or {}).get("voice_selection"):
            blockers.append({"code": "voice_selection_stale", "message": "声线选择所依赖的配置测试快照已失效，需要重新测试并选择"})
        blockers.append({"code": "model_bindings_not_fresh", "message": "模型配置缺少新鲜且有效的服务端测试"})
    return voice_options, blockers


def _dedupe_blockers(blockers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None]] = set()
    for blocker in blockers:
        code = str(blocker.get("code") or "unknown_preflight_blocker")
        key = (code, str(blocker.get("shot_id")) if blocker.get("shot_id") else None)
        if key not in seen:
            seen.add(key)
            deduped.append({**blocker, "code": code})
    return deduped


async def build_live_preflight_plan(
    db: AsyncSession, run: SeriesProductionRun, *, native_audio: bool = False,
) -> dict[str, Any]:
    """Build a fail-closed, read-only live-canary plan."""
    hard_preflight, story_blockers = await _story_preflight(db, run, native_audio=native_audio)
    contracts, dialogue_count, voice_required, anchor_blockers = await _anchor_preflight(
        db, run, native_audio=native_audio,
    )
    anchors = await _selected_anchor_shots(db, run)
    cost_breakdown, budget, budget_blockers = _budget_preflight(
        run,
        anchor_count=await _pending_video_count(db, run, anchors),
        dialogue_count=dialogue_count,
        missing_first_frame_count=sum(not item["first_frame_ready"] for item in contracts),
        native_audio=native_audio,
    )
    reference = (run.run_metadata or {}).get("reference_preparation") or {}
    chapter_ids = list(dict.fromkeys(
        str(chapter_id)
        for episode in (run.episodes or [])
        for chapter_id in (episode.get("chapter_ids") or [])
    ))
    source_chapters = list((await db.scalars(select(Chapter).where(
        Chapter.id.in_(chapter_ids),
        Chapter.user_id == run.user_id,
        Chapter.novel_id == run.novel_id,
    ))).all()) if chapter_ids else []
    has_source_dialogue = any(
        extract_explicit_dialogue(str(chapter.content or "")) for chapter in source_chapters
    )
    required_capabilities = {"video"}
    if (
        not (reference.get("asset_id") and reference.get("asset_version"))
        or any(not item["first_frame_ready"] for item in contracts)
    ):
        required_capabilities.add("image")
    if (dialogue_count or has_source_dialogue) and not native_audio:
        required_capabilities.add("tts")
    voice_options, binding_blockers = await _binding_preflight(
        db, run, required_capabilities=required_capabilities,
        voice_selection_required=voice_required,
    )
    deduped = _dedupe_blockers(
        story_blockers + anchor_blockers + budget_blockers + binding_blockers
    )
    return {
        "run_id": run.id,
        "ready": not deduped,
        "blockers": deduped,
        "blocker_codes": list(dict.fromkeys(item["code"] for item in deduped)),
        "hard_preflight": hard_preflight,
        "anchor_dialogue_contracts": contracts,
        "required_capabilities": sorted(required_capabilities),
        "voice_options": voice_options,
        "cost_breakdown": cost_breakdown,
        "budget": budget,
    }


__all__ = [
    "StoryLockPreparationBlocked", "build_live_preflight_plan", "inspect_story_lock_freshness",
    "prepare_story_locks",
]
