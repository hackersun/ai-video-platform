"""Documented, network-free public facade for series-run media readiness."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Asset, Shot, StoryEntity, Workflow
from app.models.series_production_run import SeriesProductionRun
from app.services.episode_contract_service import stable_hash
from app.services.production_bible import build_production_bible_summary
from app.services.provider_asset_binding_service import inspect_provider_binding_readiness
from app.services.shot_quality_service import extract_dialogue_speaker
from app.services.story_entity_lifecycle import APPROVED, CANDIDATE, LEGACY_ACTIVE, get_entity_review_status


@dataclass
class _EntityState:
    all_entities: list[StoryEntity]
    visible: list[StoryEntity]
    statuses: dict[str, str]
    issues: list[dict[str, Any]]


@dataclass
class _AssetState:
    selected: list[Asset]
    bindings: dict[str, Any]
    issues: list[dict[str, Any]]


def _issue(code: str, message: str, **details: Any) -> dict[str, Any]:
    return {"code": code, "message": message, **details}


def _asset_roles(asset: Asset) -> set[str]:
    params = asset.generation_params if isinstance(asset.generation_params, dict) else {}
    return {str(value) for value in params.get("canonical_roles") or []}


def _role_bindings(asset: Asset, role: str) -> list[dict[str, Any]]:
    params = asset.generation_params if isinstance(asset.generation_params, dict) else {}
    return [item for item in params.get("role_bindings") or []
            if isinstance(item, dict) and item.get("role") == role]


def _asset_matches(asset: Asset, entity: StoryEntity) -> bool:
    params = asset.generation_params if isinstance(asset.generation_params, dict) else {}
    if params.get("composite_reference_rule") == "single_artifact_dual_role_v1":
        bindings = _role_bindings(asset, "character_canonical")
        return len(bindings) == 1 and str(bindings[0].get("entity_id") or "") == entity.id
    return asset.entity_id == entity.id


async def _story_issues(
    db: AsyncSession, run: SeriesProductionRun, summary: dict[str, Any],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    lock = (run.run_metadata or {}).get("story_locks") or {}
    v2_ready = False
    if lock:
        from app.features.series_run_story_locks.public import inspect_story_lock_freshness
        freshness = await inspect_story_lock_freshness(db, run, supersede=True)
        v2_ready = bool(freshness.get("ready")
                        and lock.get("closure_contract_version") == "required_entity_closure_v2")
        if not freshness.get("ready"):
            issues.append(_issue("story_lock_stale", "四章、实体、风格、Bible 或运行输入已变化"))
    if not summary.get("story_bible_id"):
        issues.append(_issue("story_bible_missing", "Story Bible 不存在"))
    elif not v2_ready and (summary.get("story_bible_status") not in {"approved", "locked"}
                           or not summary.get("story_bible_approval_record")):
        issues.append(_issue("story_bible_not_approved", "Story Bible 尚未显式批准或锁定"))
    machine = summary.get("state_machine") or {}
    if not v2_ready and not machine.get("available"):
        issues.append(_issue("state_machine_missing", "状态机不存在"))
    elif not v2_ready:
        blocking = [item for item in machine.get("issues") or []
                    if not isinstance(item, dict) or item.get("blocking", True)]
        if machine.get("status") not in {"approved", "locked"} or blocking:
            issues.append(_issue("state_machine_blocking", "状态机未批准或仍有阻塞问题", issues=blocking))
    return issues


async def _entity_state(db: AsyncSession, run: SeriesProductionRun) -> _EntityState:
    entities = list((await db.scalars(select(StoryEntity).where(
        StoryEntity.user_id == run.user_id, StoryEntity.novel_id == run.novel_id,
    ))).all())
    statuses = {item.id: get_entity_review_status(item) for item in entities}
    visible = [item for item in entities if statuses[item.id] == LEGACY_ACTIVE or (
        statuses[item.id] == APPROVED and bool((item.attributes or {}).get("approval_record"))
    )]
    lock = (run.run_metadata or {}).get("story_locks") or {}
    required_ids = set(lock.get("required_entity_ids") or [])
    if lock.get("closure_contract_version") == "required_entity_closure_v2":
        visible = [item for item in visible if item.id in required_ids]
    issues: list[dict[str, Any]] = []
    if not visible:
        issues.append(_issue("production_entities_missing", "没有可用于生产的实体"))
    unapproved = [item.id for item in entities if item.id in required_ids and (statuses[item.id] == CANDIDATE or (
        statuses[item.id] == APPROVED and item not in visible
    ))]
    if unapproved:
        issues.append(_issue("production_entities_unapproved", "存在未批准候选实体", entity_ids=unapproved))
    names: dict[tuple[str, str], list[str]] = {}
    for entity in [item for item in entities if statuses[item.id] not in {"rejected", "archived"}]:
        key = (entity.entity_type, str(entity.canonical_name or entity.name).strip())
        names.setdefault(key, []).append(entity.id)
    conflicts = [ids for ids in names.values() if len(ids) > 1 and any(value in unapproved for value in ids)]
    if conflicts:
        issues.append(_issue("production_entity_conflict", "同一规范实体仍有候选冲突", entity_groups=conflicts))
    return _EntityState(entities, visible, statuses, issues)


def _required_asset(entity: StoryEntity) -> tuple[bool, set[str]]:
    attrs = entity.attributes or {}
    required = entity.entity_type == "character" or (
        entity.entity_type == "scene" and bool(
            attrs.get("recurring") or attrs.get("continuity_critical") or attrs.get("requires_canonical_asset")
        )
    ) or (entity.entity_type == "prop" and bool(attrs.get("continuity_critical")))
    roles = {"front", "three_quarter", "full_body"} if entity.entity_type == "character" else {
        "scene_anchor" if entity.entity_type == "scene" else "critical_prop"
    }
    return required, roles


def _select_assets(assets: list[Asset], visible: list[StoryEntity], novel_id: str) -> tuple[list[Asset], list[str], list[str], list[dict[str, Any]]]:
    selected: list[Asset] = []
    missing: list[str] = []
    unlocked: list[str] = []
    conflicts: list[dict[str, Any]] = []
    for entity in visible:
        required, roles = _required_asset(entity)
        if not required:
            continue
        candidates = [item for item in assets if _asset_matches(item, entity) and item.is_final and roles.issubset(_asset_roles(item))]
        canonical = candidates[0] if len(candidates) == 1 else None
        if len(candidates) > 1:
            conflicts.append({"entity_id": entity.id, "asset_ids": [item.id for item in candidates]})
        if canonical is None:
            missing.append(entity.id)
        else:
            selected.append(canonical)
            if not canonical.is_locked:
                unlocked.append(canonical.id)
    styles = [item for item in assets if item.category == "style" and item.is_final
              and "global_style_board" in _asset_roles(item) and (
                  (item.generation_params or {}).get("composite_reference_rule") != "single_artifact_dual_role_v1"
                  or any(str(binding.get("novel_id") or "") == novel_id for binding in _role_bindings(item, "global_style_board"))
              )]
    style = styles[0] if len(styles) == 1 else None
    if len(styles) > 1:
        conflicts.append({"entity_id": "global_style_board", "asset_ids": [item.id for item in styles]})
    if style is None and not styles:
        missing.append("global_style_board")
    elif style is not None:
        selected.append(style)
        if not style.is_locked:
            unlocked.append(style.id)
    return selected, missing, unlocked, conflicts


async def _asset_state(db: AsyncSession, run: SeriesProductionRun, visible: list[StoryEntity]) -> _AssetState:
    assets = list((await db.scalars(select(Asset).where(
        Asset.is_active.is_(True), or_(Asset.user_id == run.user_id, Asset.is_public.is_(True)),
        Asset.novel_id == run.novel_id,
    ))).all())
    selected, missing, unlocked, conflicts = _select_assets(assets, visible, run.novel_id)
    issues: list[dict[str, Any]] = []
    if missing:
        issues.append(_issue("canonical_assets_missing", "缺少规范资产", items=missing))
    if unlocked:
        issues.append(_issue("canonical_assets_unlocked", "规范资产尚未锁定", asset_ids=unlocked))
    if conflicts:
        issues.append(_issue("canonical_asset_conflict", "规范资产候选存在冲突", items=conflicts))
    provider_id = str((run.model_bindings or {}).get("provider_id") or "").strip()
    model_id = str((run.model_bindings or {}).get("model_id") or "").strip()
    bindings: dict[str, Any] = {"ready": False, "missing": [], "not_ready": [], "bindings": []}
    if selected and provider_id and model_id:
        bindings = await inspect_provider_binding_readiness(
            db, assets=selected, provider_id=provider_id, model_id=model_id,
        )
    if not selected or not provider_id or not model_id or bindings["missing"]:
        issues.append(_issue("provider_binding_missing", "缺少精确版本的 provider binding", asset_ids=bindings["missing"]))
    if bindings["not_ready"]:
        issues.append(_issue("provider_binding_not_ready", "provider binding 未验证或媒体不可公开访问", asset_ids=bindings["not_ready"]))
    return _AssetState(selected, bindings, issues)


async def _run_shots(db: AsyncSession, run: SeriesProductionRun) -> list[Shot]:
    workflow_ids = [str((episode.get("canonical_ids") or {}).get("workflow_id"))
                    for episode in run.episodes or [] if (episode.get("canonical_ids") or {}).get("workflow_id")]
    workflows = list((await db.scalars(select(Workflow).where(
        Workflow.id.in_(workflow_ids), Workflow.user_id == run.user_id,
    ))).all()) if workflow_ids else []
    storyboard_ids = [item.storyboard_id for item in workflows if item.storyboard_id]
    return list((await db.scalars(select(Shot).where(
        Shot.user_id == run.user_id, Shot.storyboard_id.in_(storyboard_ids),
    ))).all()) if storyboard_ids else []


def _name_map(visible: list[StoryEntity]) -> dict[str, list[StoryEntity]]:
    result: dict[str, list[StoryEntity]] = {}
    for entity in visible:
        if entity.entity_type != "character":
            continue
        for name in {entity.name, entity.canonical_name, *(entity.aliases or [])}:
            if name:
                result.setdefault(str(name).strip(), []).append(entity)
    return result


def _dialogue_state(
    shots: list[Shot], visible: list[StoryEntity], *, native_audio: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    names = _name_map(visible)
    excluded = {"旁白", "画外音", "解说", "系统"}
    speaking_ids = {item.id for item in visible if item.entity_type == "character"
                    and bool((item.attributes or {}).get("speaking"))}
    unknown: list[dict[str, Any]] = []
    contracts: list[dict[str, Any]] = []
    for shot in shots:
        extra = shot.extra_data if isinstance(shot.extra_data, dict) else {}
        speaker = extract_dialogue_speaker(shot.dialogue, extra)
        has_dialogue = bool(str(shot.dialogue or extra.get("subtitle_text") or "").strip())
        matches = list({item.id: item for item in names.get(speaker, [])}.values()) if speaker else []
        reason = ("excluded_role" if speaker in excluded else "speaker_missing" if has_dialogue and not speaker
                  else "unknown_or_ambiguous" if speaker and len(matches) != 1 else None)
        if reason in {"speaker_missing", "unknown_or_ambiguous"}:
            unknown.append({"shot_id": shot.id, "speaker": speaker, "reason": reason})
        if speaker and speaker not in excluded and len(matches) == 1:
            speaking_ids.add(matches[0].id)
        payload = {"dialogue": shot.dialogue, "subtitle_text": extra.get("subtitle_text"),
                   "dialogue_speaker": extra.get("dialogue_speaker"), "speaker_name": extra.get("speaker_name")}
        contracts.append({"shot_id": shot.id, "shot_version": int(shot.version or 1),
                          "dialogue_contract_hash": stable_hash(payload), "parsed_speaker": speaker,
                          "resolved_entity_id": matches[0].id if len(matches) == 1 else None, "issue_reason": reason})
    speaking = [item for item in visible if item.id in speaking_ids]
    locks, missing = [], []
    for entity in speaking:
        binding = (entity.attributes or {}).get("voice_binding") or {}
        if not binding.get("voice_id") or binding.get("status") not in {"approved", "locked", "legacy"}:
            missing.append(entity.id)
        else:
            locks.append({"entity_id": entity.id, "voice_id": binding["voice_id"],
                          "voice_version": binding.get("version", 1)})
    issues = ([_issue("dialogue_speaker_unknown", "对白说话人未知或存在歧义", items=unknown)] if unknown else [])
    if not native_audio and (not visible or missing):
        issues.append(_issue("voice_binding_missing", "说话角色音色绑定未解析", entity_ids=missing))
    return issues, locks, contracts


def _snapshot(
    summary: dict[str, Any], entities: _EntityState, assets: _AssetState,
    voice_locks: list[dict[str, Any]], contracts: list[dict[str, Any]], issues: list[dict[str, Any]],
) -> dict[str, Any]:
    machine = summary.get("state_machine") or {}
    return {
        "story_bible": {"id": summary.get("story_bible_id"), "status": summary.get("story_bible_status"),
                        "approval_record": summary.get("story_bible_approval_record"), "version": summary.get("story_bible_version")},
        "production_graph": {"version": (summary.get("production_graph") or {}).get("through_version", 0),
                             "hash": (summary.get("production_graph") or {}).get("graph_hash")},
        "state_machine": {"status": machine.get("status"), "version": machine.get("version") or machine.get("generated_at"),
                          "issues_fingerprint": stable_hash({"issues": machine.get("issues") or []})},
        "entity_versions": sorted([{"entity_id": item.id, "version": int(item.version or 1),
                                    "status": entities.statuses[item.id], "is_approved": bool(item.is_approved),
                                    "approval_record": (item.attributes or {}).get("approval_record")}
                                   for item in entities.all_entities], key=lambda item: item["entity_id"]),
        "asset_locks": sorted([{"asset_id": item.id, "asset_version": int(item.version or 1),
                                "locked": bool(item.is_locked)} for item in assets.selected], key=lambda item: item["asset_id"]),
        "voice_locks": sorted(voice_locks, key=lambda item: item["entity_id"]),
        "provider_bindings": sorted(assets.bindings["bindings"], key=lambda item: item["asset_id"]),
        "shot_dialogue_contracts": sorted(contracts, key=lambda item: item["shot_id"]),
        "gate_issue_fingerprints": sorted([{"code": item["code"], "fingerprint": stable_hash(item)} for item in issues],
                                          key=lambda item: (item["code"], item["fingerprint"])),
        "gate_codes": sorted(item["code"] for item in issues),
    }


async def evaluate_media_preflight(
    db: AsyncSession, run: SeriesProductionRun, *, native_audio: bool = False,
) -> dict[str, Any]:
    """Fail closed before the first real media operation; performs no provider calls."""
    summary = await build_production_bible_summary(db, run.user_id, run.novel_id)
    entities = await _entity_state(db, run)
    assets = await _asset_state(db, run, entities.visible)
    dialogue_issues, voice_locks, contracts = _dialogue_state(
        await _run_shots(db, run), entities.visible, native_audio=native_audio,
    )
    issues = [*await _story_issues(db, run, summary), *entities.issues, *assets.issues, *dialogue_issues]
    snapshot = _snapshot(summary, entities, assets, voice_locks, contracts, issues)
    return {"ready": not issues, "codes": [item["code"] for item in issues], "issues": issues,
            "asset_locks": snapshot["asset_locks"], "voice_locks": snapshot["voice_locks"],
            "provider_bindings": snapshot["provider_bindings"], "story_bible_id": summary.get("story_bible_id"),
            "production_graph_version": (summary.get("production_graph") or {}).get("through_version", 0),
            "input_snapshot": snapshot, "snapshot_hash": stable_hash(snapshot)}


__all__ = ["evaluate_media_preflight"]
