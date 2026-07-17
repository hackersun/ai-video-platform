"""Targeted, merge-only enrichment for one named StoryEntity."""

from __future__ import annotations

import re
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.models import StoryEntity
from app.services.entity_quality_service import score_entity_candidate
from app.services.entity_review_service import _entity_snapshot, _write_feedback
from app.services.prompt_template_router import select_prompt_skill_for_model
from app.services.story_entity_lifecycle import APPROVED, CANDIDATE, get_entity_review_status, set_entity_review_status


ALLOWED_FIELDS = {
    "description",
    "appearance",
    "visual_prompt",
    "aliases",
    "relations",
    "state_changes",
    "attributes",
    "evidence",
    "tags",
    "voice_profile",
    "visual_dna",
}


def _json_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _sentence_for_name(text: str, name: str) -> str:
    for sentence in re.split(r"[。！？!?\n]", text or ""):
        sentence = sentence.strip(" ，,；;")
        if name and name in sentence:
            return sentence[:500]
    return (text or "")[:500]


def _appearance_from_evidence(name: str, evidence: str, source_text: str = "") -> Optional[str]:
    patterns = [
        rf"{re.escape(name)}([^。！？；;，,]*(?:戴着|穿着|披着|握着|拿着|手持|身穿)[^。！？；;，,]*)",
        r"((?:戴着|穿着|披着|握着|拿着|手持|身穿)[^。！？；;，,]*)",
    ]
    for text in (evidence or "", source_text or ""):
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                value = next((group for group in match.groups() if group), "")
                value = value.strip(" ，,；;")
                if value:
                    return value[:200]
    return None


def _aliases_from_evidence(name: str, evidence: str) -> list[str]:
    aliases: list[str] = []
    for pattern in (rf"{re.escape(name)}又名([\u4e00-\u9fffA-Za-z0-9_-]{{1,12}})", rf"{re.escape(name)}别名([\u4e00-\u9fffA-Za-z0-9_-]{{1,12}})"):
        for match in re.finditer(pattern, evidence or ""):
            alias = match.group(1).strip()
            if alias and alias != name and alias not in aliases:
                aliases.append(alias)
    return aliases


def _relations_from_evidence(name: str, evidence: str) -> list[dict[str, Any]]:
    relations: list[dict[str, Any]] = []
    for pattern in (rf"{re.escape(name)}与([\u4e00-\u9fff]{{2,4}})", rf"与([\u4e00-\u9fff]{{2,4}}).{{0,8}}{re.escape(name)}"):
        for match in re.finditer(pattern, evidence or ""):
            target = match.group(1).strip()
            if target and target != name:
                item = {"target": target, "type": "related", "evidence": evidence[:200]}
                if item not in relations:
                    relations.append(item)
    return relations


def _proposed_patch(*, entity_type: str, name: str, text: str, fields: list[str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    evidence = _sentence_for_name(text, name)
    requested = [field for field in fields if field in ALLOWED_FIELDS]
    patch: dict[str, Any] = {}
    if "description" in requested:
        patch["description"] = f"{name}：{evidence}" if evidence else name
    if "appearance" in requested:
        appearance = _appearance_from_evidence(name, evidence, text)
        if appearance:
            patch["appearance"] = appearance
    if "visual_prompt" in requested:
        base = patch.get("appearance") or evidence or name
        patch["visual_prompt"] = f"{name}，{base}，动漫角色设定，保持一致性" if entity_type == "character" else f"{name}，{base}，动漫资产设定"
    if "aliases" in requested:
        aliases = _aliases_from_evidence(name, evidence)
        if aliases:
            patch["aliases"] = aliases
    if "relations" in requested:
        relations = _relations_from_evidence(name, evidence)
        if relations:
            patch["relations"] = relations
    if "state_changes" in requested and evidence:
        patch["state_changes"] = [{"description": evidence, "source": "targeted_enrichment"}]
    if "evidence" in requested and evidence:
        patch["evidence"] = evidence
    attributes: dict[str, Any] = {}
    if "visual_dna" in requested and (patch.get("appearance") or evidence):
        attributes["visual_dna"] = patch.get("appearance") or evidence
    if "voice_profile" in requested and entity_type == "character":
        attributes["voice_profile"] = {"style": "待人工确认", "evidence": evidence}
    if "attributes" in requested and evidence:
        attributes["source_summary"] = evidence
    if attributes:
        patch["attributes"] = attributes
    mentions = [{"mention_text": name, "evidence": evidence, "confidence": 80}] if evidence else []
    return patch, mentions


async def _find_target_entity(
    db: AsyncSession,
    *,
    user_id: str,
    entity_type: str,
    entity_name: str,
    novel_id: Optional[str],
    chapter_id: Optional[str],
    script_id: Optional[str],
    target_entity_id: Optional[str],
) -> Optional[StoryEntity]:
    if target_entity_id:
        entity = await db.get(StoryEntity, target_entity_id)
        if entity and entity.user_id == user_id:
            return entity
        return None
    query = select(StoryEntity).where(
        StoryEntity.user_id == user_id,
        StoryEntity.entity_type == entity_type,
        StoryEntity.name == entity_name,
    )
    query = query.where(StoryEntity.novel_id == novel_id if novel_id else StoryEntity.novel_id.is_(None))
    if chapter_id:
        query = query.where(StoryEntity.chapter_id == chapter_id)
    if script_id:
        query = query.where(StoryEntity.script_id == script_id)
    return (await db.execute(query.limit(1))).scalar_one_or_none()


def _merge_list(existing: list[Any], incoming: list[Any]) -> list[Any]:
    merged = list(existing or [])
    for item in incoming or []:
        if item not in merged:
            merged.append(item)
    return merged


def _apply_safe_patch(entity: StoryEntity, patch: dict[str, Any]) -> None:
    for field in ("description", "appearance", "visual_prompt", "evidence"):
        if field in patch and not getattr(entity, field, None):
            setattr(entity, field, patch[field])
    if "aliases" in patch:
        entity.aliases = _merge_list(entity.aliases or [], patch["aliases"])
    if "relations" in patch:
        entity.relations = _merge_list(entity.relations or [], patch["relations"])
    if "state_changes" in patch:
        entity.state_changes = _merge_list(entity.state_changes or [], patch["state_changes"])
    if "tags" in patch:
        entity.tags = _merge_list(entity.tags or [], patch["tags"])
    if "attributes" in patch:
        entity.attributes = {**_json_dict(entity.attributes), **_json_dict(patch["attributes"])}
    entity.updated_at = utc_now()


async def enrich_target_entity(
    db: AsyncSession,
    *,
    user_id: str,
    text: str,
    entity_type: str,
    entity_name: str,
    fields: Optional[list[str]] = None,
    mode: str = "preview",
    novel_id: Optional[str] = None,
    chapter_id: Optional[str] = None,
    script_id: Optional[str] = None,
    target_entity_id: Optional[str] = None,
    model_config_id: Optional[str] = None,
    provider: Optional[str] = None,
    model_id: Optional[str] = None,
    model_capabilities: Optional[list[str]] = None,
) -> dict[str, Any]:
    requested_fields = [field for field in (fields or ["description", "appearance", "visual_prompt", "aliases", "relations", "state_changes", "attributes", "evidence"]) if field in ALLOWED_FIELDS]
    if not requested_fields:
        raise ValueError("至少选择一个可补全字段")

    prompt_routing = await select_prompt_skill_for_model(
        db,
        user_id=user_id,
        task="entity_extraction",
        stage="analysis",
        provider_name=provider,
        model_id=model_id,
        model_capabilities=model_capabilities or [],
        output_contract="json_object",
        context={
            "entity_type": entity_type,
            "entity_name": entity_name,
            "fields": "、".join(requested_fields),
            "source_content": (text or "")[:30000],
            "output_format": "JSON 对象",
        },
        internal_prompt="只补全指定实体，不全量抽取，也不覆盖已定稿字段。",
    )

    entity = await _find_target_entity(
        db,
        user_id=user_id,
        entity_type=entity_type,
        entity_name=entity_name,
        novel_id=novel_id,
        chapter_id=chapter_id,
        script_id=script_id,
        target_entity_id=target_entity_id,
    )
    patch, mentions = _proposed_patch(entity_type=entity_type, name=entity_name, text=text, fields=requested_fields)
    quality = score_entity_candidate(
        {
            "entity_type": entity_type,
            "name": entity_name,
            "description": patch.get("description"),
            "appearance": patch.get("appearance"),
            "visual_prompt": patch.get("visual_prompt"),
            "aliases": patch.get("aliases") or [],
            "attributes": patch.get("attributes") or {},
            "relations": patch.get("relations") or [],
            "state_changes": patch.get("state_changes") or [],
            "evidence": patch.get("evidence"),
            "confidence": 80,
            "source": "targeted_enrichment",
        }
    ).model_dump()

    created = False
    if entity is None and mode != "preview":
        entity = StoryEntity(
            id=str(uuid4()),
            user_id=user_id,
            novel_id=novel_id,
            chapter_id=chapter_id,
            script_id=script_id,
            entity_type=entity_type,
            name=entity_name,
            source="targeted_enrichment",
        )
        set_entity_review_status(entity, CANDIDATE, changed_by=user_id, reason="targeted enrichment")
        db.add(entity)
        created = True

    merge_policy = "preview_only"
    warnings: list[str] = []
    if entity is not None and mode != "preview":
        before = _entity_snapshot(entity)
        extra = dict(_json_dict(entity.extra_data))
        extra["last_targeted_enrichment"] = {
            "fields": requested_fields,
            "quality": quality,
            "prompt_routing": {key: value for key, value in prompt_routing.items() if key != "prompt"},
            "model_config_id": model_config_id,
        }
        if get_entity_review_status(entity) == APPROVED and mode != "apply_to_approved_requires_confirmation":
            extra["pending_enrichment"] = {
                "proposed_patch": patch,
                "evidence_mentions": mentions,
                "created_at": utc_now().isoformat(),
            }
            entity.extra_data = extra
            entity.updated_at = utc_now()
            merge_policy = "pending_for_approved"
            warnings.append("已定稿实体不会自动覆盖，补全结果已作为待确认补丁保存")
        else:
            entity.extra_data = extra
            _apply_safe_patch(entity, patch)
            if get_entity_review_status(entity) != APPROVED:
                set_entity_review_status(entity, CANDIDATE, changed_by=user_id, reason="targeted enrichment")
            merge_policy = "safe_merge"
        await _write_feedback(
            db,
            user_id=user_id,
            entity=entity,
            action="targeted_enrichment",
            before_data=before,
            reason="目标实体补全",
            extra_data={"fields": requested_fields, "mode": mode, "quality": quality},
        )
        await db.commit()
        await db.refresh(entity)

    return {
        "target": {"entity_type": entity_type, "entity_name": entity_name, "fields": requested_fields},
        "matched_entity": _entity_snapshot(entity) if entity else None,
        "created_candidate": created,
        "proposed_patch": patch,
        "evidence_mentions": mentions,
        "quality": quality,
        "prompt_routing": {key: value for key, value in prompt_routing.items() if key != "prompt"},
        "merge_policy": merge_policy,
        "warnings": warnings,
    }
