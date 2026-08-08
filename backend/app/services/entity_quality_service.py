"""Deterministic quality scoring for extracted story entity candidates."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.services.entity_extraction_schema import CanonicalEntityCandidate


AUTO_APPROVE = "auto_approve"
NEEDS_REVIEW = "needs_review"
REJECT_NOISE = "reject_noise"

AutoDecision = Literal["auto_approve", "needs_review", "reject_noise"]


class EntityQualityResult(BaseModel):
    score: int = Field(ge=0, le=100)
    auto_decision: AutoDecision
    flags: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    components: dict[str, int] = Field(default_factory=dict)


def _clamp(value: int, minimum: int = 0, maximum: int = 100) -> int:
    return max(minimum, min(maximum, value))


def _evidence_score(candidate: CanonicalEntityCandidate) -> tuple[int, list[str]]:
    evidence = candidate.evidence or candidate.description or ""
    if not evidence:
        return 0, ["missing_evidence"]
    if candidate.name and candidate.name in evidence:
        return 30, []
    if len(evidence.strip()) >= 8:
        return 20, ["evidence_without_exact_name"]
    return 10, ["weak_evidence"]


def _name_shape_score(candidate: CanonicalEntityCandidate) -> tuple[int, list[str]]:
    name = candidate.name.strip()
    flags: list[str] = []
    if not name:
        return 0, ["empty_name"]
    if len(name) > 24:
        flags.append("name_too_long")
    if re.search(r"[。！？!?\n]", name):
        flags.append("name_contains_sentence_punctuation")
    if candidate.entity_type in {"character", "scene", "prop"} and len(name) <= 12 and not flags:
        return 25, []
    if candidate.entity_type == "event" and 4 <= len(name) <= 40 and not flags:
        return 25, []
    return 12, flags


def _noise_flags(candidate: CanonicalEntityCandidate) -> list[str]:
    from app.services import entity_extraction_service as extraction_rules

    name = candidate.name.strip()
    flags: list[str] = []
    if candidate.entity_type == "character":
        if extraction_rules._is_group_or_non_character_name(name):
            flags.append("noise:character_group_or_non_character")
        if extraction_rules._is_event_like_name(name):
            flags.append("noise:character_event_phrase")
        if name.endswith("家"):
            flags.append("noise:character_family_or_faction")
        if name.endswith((*extraction_rules.PROP_SUFFIXES, "果")):
            flags.append("noise:character_prop_name")
        predicate_tails = {"深": ("以",), "正": ("在", "要", "是"), "可": ("是", "以", "能")}
        continuations = predicate_tails.get(name[-1:], ())
        if len(name) >= 3 and any(f"{name}{continuation}" in (candidate.evidence or "") for continuation in continuations):
            flags.append("noise:character_predicate_fragment")
    elif candidate.entity_type == "scene" and extraction_rules._is_production_copy_scene_name(name):
        flags.append("noise:production_copy_scene")
    elif candidate.entity_type == "prop" and extraction_rules._is_production_copy_prop_name(name):
        predicate_phrase = bool(re.match(r"^[\u4e00-\u9fff]{2,4}(?:在|从|向|把|将)", name))
        explicit_label = str(candidate.description or "").startswith("文本标注道具") or candidate.source == "deterministic_label"
        if predicate_phrase and explicit_label:
            pass
        elif predicate_phrase:
            flags.append("noise:prop_predicate_phrase")
        else:
            flags.append("noise:production_copy_prop")
    elif candidate.entity_type == "event":
        if re.match(r"^(?:这日|当日|次日|翌日|当天|中午|清晨|傍晚|夜幕|片刻)", name):
            flags.append("noise:event_time_fragment")
        if re.search(r"(?:气血翻涌|不寒而栗|眼中闪过|面色一变|心中一惊|眉头一皱)", name):
            flags.append("noise:event_state_fragment")
    return flags


def _type_boundary_score(candidate: CanonicalEntityCandidate) -> tuple[int, list[str]]:
    flags = _noise_flags(candidate)
    if flags:
        return 0, flags
    return 20, []


def _production_usefulness_score(candidate: CanonicalEntityCandidate) -> tuple[int, list[str]]:
    text = f"{candidate.name} {candidate.description or ''} {candidate.evidence or ''}"
    attrs = candidate.attributes if isinstance(candidate.attributes, dict) else {}
    if candidate.entity_type == "character":
        if attrs.get("visual_dna") or any(marker in text for marker in ("说", "问", "站", "握", "穿", "戴")):
            return 20, []
    elif candidate.entity_type == "scene":
        if attrs.get("scene_dna") or any(marker in text for marker in ("雨", "夜", "灯", "门", "室", "局", "巷", "城", "站")):
            return 20, []
    elif candidate.entity_type == "prop":
        if attrs.get("prop_dna") or any(marker in text for marker in ("握", "拿", "响", "铜", "灯", "铃", "信", "钥匙")):
            return 20, []
    elif candidate.entity_type == "event":
        if any(marker in text for marker in ("发现", "遭遇", "决定", "战斗", "逃离", "抵达", "响", "打开", "求救")):
            return 20, []
    return 8, ["low_production_usefulness"]


def score_entity_candidate(candidate: CanonicalEntityCandidate | dict[str, Any]) -> EntityQualityResult:
    canonical = candidate if isinstance(candidate, CanonicalEntityCandidate) else CanonicalEntityCandidate.model_validate(candidate)
    evidence_score, evidence_flags = _evidence_score(canonical)
    name_score, name_flags = _name_shape_score(canonical)
    type_score, type_flags = _type_boundary_score(canonical)
    usefulness_score, usefulness_flags = _production_usefulness_score(canonical)
    confidence_score = _clamp(round((canonical.confidence or 0) * 0.05), 0, 5)

    explicit_deterministic_label = (
        canonical.source == "deterministic_label"
        or str(canonical.description or "").startswith("文本标注")
    )
    source_flags = (
        ["deterministic_requires_review"]
        if canonical.source.startswith("deterministic") and not explicit_deterministic_label
        else []
    )
    flags = [*evidence_flags, *name_flags, *type_flags, *usefulness_flags, *source_flags]
    components = {
        "evidence": evidence_score,
        "name_shape": name_score,
        "type_boundary": type_score,
        "production_usefulness": usefulness_score,
        "confidence": confidence_score,
    }
    score = _clamp(sum(components.values()))

    if any(flag.startswith("noise:") for flag in flags):
        score = min(score, 35)
        decision: AutoDecision = REJECT_NOISE
    elif score >= 86 and not evidence_flags and not name_flags and not usefulness_flags and not source_flags:
        decision = AUTO_APPROVE
    elif score >= 55:
        decision = NEEDS_REVIEW
    else:
        decision = REJECT_NOISE

    reasons = [flag.replace("_", " ") for flag in flags]
    return EntityQualityResult(
        score=score,
        auto_decision=decision,
        flags=flags,
        reasons=reasons,
        components=components,
    )
