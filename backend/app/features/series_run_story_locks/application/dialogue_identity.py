"""Explicit-dialogue candidate normalization owned by Story Lock."""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass
from typing import Any
from app.core.time_utils import utc_now
from app.models import StoryEntity
from app.services.story_entity_lifecycle import APPROVED, ARCHIVED, CANDIDATE, REJECTED, get_entity_review_status, set_entity_review_status
from ..domain.scoped_reference import canonical_identity_sha256, sign_merge_edge
from ..public_errors import StoryLockPreparationBlocked
def _fingerprint(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def _normalized_character_name(entity: StoryEntity) -> str:
    return str(entity.canonical_name or entity.name or "").strip().casefold()


_ROLE_TAGS = {
    "protagonist": "protagonist", "lead": "protagonist", "主角": "protagonist", "主人公": "protagonist",
    "antagonist": "antagonist", "villain": "antagonist", "反派": "antagonist",
    "supporting": "supporting", "support": "supporting", "配角": "supporting",
}
_SPECIES_TAGS = {
    "human": "human", "人类": "human", "凡人": "human",
    "spirit": "spirit", "灵体": "spirit", "精灵": "spirit",
    "demon": "demon", "恶魔": "demon", "妖魔": "demon",
}
_STATE_TAGS = {
    "alive": "alive", "存活": "alive", "生还": "alive",
    "dead": "dead", "deceased": "dead", "死亡": "dead", "已死": "dead",
    "injured": "injured", "wounded": "injured", "受伤": "injured",
}
_SYSTEM_DESCRIPTION_BOILERPLATE_V1 = {"规则识别人物", "规则识别人物动作", "规则识别人物描述"}
_SYSTEM_EXTRACTION_METADATA_ATTRS_V1 = {
    "extraction_notes", "description_semantics_version", "source_kind",
    "mention_count", "mention_stats", "extraction_confidence",
    "evidence_contract",
    "deterministic_dialogue_evidence",
    "extraction_metadata_history", "extraction_metadata_aggregates",
}
_OPERATIONAL_CHARACTER_ATTRS = {
    "approval_record", "speaking", "dialogue_evidence", "dialogue_evidence_hash", "voice_binding",
    "source_chapter_id", "source_chapter_index", "source_chapter_number", "introduced_at",
    "merged_into_entity_id", "identity_fact_provenance", "description_provenance",
}
_VISUAL_DNA_PLACEHOLDERS = {
    "默认服装", "依据原文固定服装与标志配饰",
}


def _taxonomy_value(value: Any, taxonomy: dict[str, str]) -> str:
    normalized = " ".join(str(value or "").strip().casefold().replace("_", "-").split())
    return taxonomy.get(normalized, normalized)


def _visual_dna_facts(values: list[Any]) -> tuple[list[set[str]], list[dict[str, Any]]]:
    dictionaries = [value for value in values if isinstance(value, dict)]
    conflict_values: list[set[str]] = []
    fields: list[dict[str, Any]] = []
    for key in sorted({name for value in dictionaries for name in value}):
        raw_values = [value[key] for value in dictionaries
                      if value.get(key) not in (None, "", [], {})
                      and value.get(key) not in _VISUAL_DNA_PLACEHOLDERS]
        fingerprints = {_fingerprint(value) for value in raw_values}
        conflict_values.append(fingerprints)
        if len(fingerprints) > 1:
            fields.append({"category": "identity_attribute", "field": f"visual_dna.{key}",
                           "values": raw_values})
    return conflict_values, fields


def _merged_visual_dna(active: list[StoryEntity]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for item in active:
        value = (item.attributes or {}).get("visual_dna")
        if not isinstance(value, dict):
            continue
        for key, raw in value.items():
            if raw in (None, "", [], {}) or raw in _VISUAL_DNA_PLACEHOLDERS:
                continue
            merged.setdefault(key, raw)
    return merged


@dataclass(frozen=True)
class _TagFacts:
    roles: set[str]
    species: set[str]
    unknown: set[str]
    state_changes: list[dict[str, Any]]


@dataclass(frozen=True)
class _MergeMetadata:
    history: list[dict[str, Any]]
    aggregates: dict[str, dict[str, Any]]
    evidence: list[dict[str, Any]]
    merge_hash: str


@dataclass(frozen=True)
class _CanonicalProjection:
    active: list[StoryEntity]
    merged: list[StoryEntity]
    identity_keys: list[str]
    chapter_order: dict[str, int]
    earliest_chapter_id: str | None
    tags: _TagFacts


def _active_candidates(matches: list[StoryEntity]) -> tuple[list[StoryEntity], bool]:
    active = [item for item in matches if not (
        get_entity_review_status(item) == ARCHIVED
        and ((item.extra_data or {}).get("normalized_merge") or {}).get("status") == "merged_superseded"
    )]
    allowed_sources = {"system", "deterministic"}
    allowed_approval_reasons = {
        "entity_extraction_v2:auto_approve",
        "rule_based_explicit_dialogue_v1",
        "rule_based_explicit_dialogue_native_audio_v1",
    }
    unsafe_lifecycle = any(
        item.source not in allowed_sources or get_entity_review_status(item) == REJECTED
        or (get_entity_review_status(item) == APPROVED
            and str(((item.attributes or {}).get("approval_record") or {}).get("reason") or "")
            not in allowed_approval_reasons)
        for item in active
    )
    for item in active:
        description = " ".join(str(item.description or "").split())
        if item.source in allowed_sources and description in _SYSTEM_DESCRIPTION_BOILERPLATE_V1:
            attrs = dict(item.attributes or {})
            attrs["extraction_notes"] = list(dict.fromkeys([*(attrs.get("extraction_notes") or []), description]))
            attrs["description_semantics_version"] = "system_boilerplate_v1"
            item.attributes = attrs
            item.extra_data = {**(item.extra_data or {}), "description_migration": {
                "kind": "system_boilerplate_v1", "value": description, "migrated_at": utc_now().isoformat(),
            }}
            item.evidence = item.evidence or description
            item.description = None
    return active, unsafe_lifecycle


def _identity_conflicts(
    active: list[StoryEntity],
) -> tuple[list[str], list[set[str]], list[dict[str, Any]]]:
    ephemeral = _OPERATIONAL_CHARACTER_ATTRS | _SYSTEM_EXTRACTION_METADATA_ATTRS_V1
    keys = sorted({key for item in active for key in (item.attributes or {}) if key not in ephemeral})
    conflict_values: list[set[str]] = []
    fields: list[dict[str, Any]] = []
    canonical_identities = {_normalized_character_name(item) for item in active}
    conflict_values.append(canonical_identities)
    if len(canonical_identities) > 1:
        fields.append({"category": "identity_column", "field": "canonical_identity",
                       "values": sorted(canonical_identities)})
    descriptions = {" ".join(str(item.description or "").split()).casefold()
                    for item in active if str(item.description or "").strip()}
    conflict_values.append(descriptions)
    if len(descriptions) > 1:
        fields.append({"category": "identity_column", "field": "description", "values": sorted(descriptions)})
    for key in keys:
        values = [(item.attributes or {}).get(key) for item in active
                  if (item.attributes or {}).get(key) not in (None, "", [], {})]
        if key == "visual_dna":
            visual_values, visual_fields = _visual_dna_facts(values)
            conflict_values.extend(visual_values)
            fields.extend(visual_fields)
            continue
        if key == "role":
            fingerprints = {_taxonomy_value(value, _ROLE_TAGS) for value in values}
        elif key == "species":
            fingerprints = {_taxonomy_value(value, _SPECIES_TAGS) for value in values}
        else:
            fingerprints = {_fingerprint(value) for value in values}
        conflict_values.append(fingerprints)
        if len(fingerprints) > 1:
            fields.append({"category": "identity_attribute", "field": key, "values": values})
    voices = {_fingerprint((item.attributes or {}).get("voice_binding")) for item in active
              if (item.attributes or {}).get("voice_binding")}
    conflict_values.append(voices)
    if len(voices) > 1:
        fields.append({"category": "voice_binding", "field": "voice_binding", "values": [
            (item.attributes or {}).get("voice_binding") for item in active
            if (item.attributes or {}).get("voice_binding")
        ]})
    for key in ("appearance", "visual_prompt"):
        values = {" ".join(str(getattr(item, key) or "").split()).casefold()
                  for item in active if str(getattr(item, key) or "").strip()}
        conflict_values.append(values)
        if len(values) > 1:
            fields.append({"category": "identity_column", "field": key, "values": sorted(values)})
    return keys, conflict_values, fields


def _timeline_conflicts(active: list[StoryEntity]) -> tuple[dict[tuple[str, str], set[str]], dict[str, set[str]]]:
    relations: dict[tuple[str, str], set[str]] = {}
    states: dict[str, set[str]] = {}
    for item in active:
        fallback = str(item.chapter_id or item.first_seen_chapter_id or "")
        for relation in item.relations or []:
            if isinstance(relation, dict):
                chapter_id = str(relation.get("chapter_id") or fallback)
                target = str(relation.get("entity_id") or relation.get("target") or relation.get("name") or "")
                relations.setdefault((chapter_id, target), set()).add(
                    str(relation.get("type") or relation.get("relation") or "")
                )
        for change in item.state_changes or []:
            if isinstance(change, dict):
                chapter_id = str(change.get("chapter_id") or fallback)
                states.setdefault(chapter_id, set()).add(_fingerprint({
                    key: value for key, value in change.items() if key not in {"source_entity_id", "provenance"}
                }))
    return relations, states


def _tag_facts(active: list[StoryEntity]) -> _TagFacts:
    roles: set[str] = set()
    species: set[str] = set()
    states: dict[str, set[str]] = {}
    unknown: set[str] = set()
    changes: list[dict[str, Any]] = []
    for item in active:
        chapter_id = str(item.chapter_id or item.first_seen_chapter_id or "")
        for raw_tag in item.tags or []:
            tag = " ".join(str(raw_tag or "").strip().casefold().replace("_", "-").split())
            if tag in _ROLE_TAGS:
                roles.add(_ROLE_TAGS[tag])
            elif tag in _SPECIES_TAGS:
                species.add(_SPECIES_TAGS[tag])
            elif tag in _STATE_TAGS:
                state = _STATE_TAGS[tag]
                states.setdefault(chapter_id, set()).add(state)
                changes.append({"state": state, "chapter_id": chapter_id, "source_entity_id": item.id,
                                "provenance": {"kind": "normalized_state_tag", "raw_tag": raw_tag}})
            elif tag:
                unknown.add(tag)
    if len(roles) > 1 or len(species) > 1 or len(unknown) > 1 or any(len(values) > 1 for values in states.values()):
        values = [*roles, *species, *unknown, *(value for group in states.values() for value in group)]
        raise StoryLockPreparationBlocked("explicit_dialogue_character_conflict", conflict_fields=[{
            "category": "identity_tag", "field": "tags", "values": values,
        }])
    return _TagFacts(roles, species, unknown, changes)


def _raise_candidate_conflicts(
    active: list[StoryEntity], unsafe_lifecycle: bool, conflict_values: list[set[str]],
    conflict_fields: list[dict[str, Any]], relations: dict[tuple[str, str], set[str]], states: dict[str, set[str]],
) -> None:
    if unsafe_lifecycle or any(len(values) > 1 for values in conflict_values):
        if unsafe_lifecycle:
            lifecycle = [{"source": item.source, "review_status": get_entity_review_status(item)} for item in active]
            conflict_fields.append({"category": "entity_lifecycle", "field": "source_review_status",
                                    "values": lifecycle})
        raise StoryLockPreparationBlocked("explicit_dialogue_character_conflict", conflict_fields=conflict_fields)
    if any(len(values) > 1 for values in relations.values()) or any(len(values) > 1 for values in states.values()):
        fields = []
        if any(len(values) > 1 for values in relations.values()):
            fields.append({"category": "identity_relation", "field": "relations",
                           "values": sorted({value for values in relations.values() for value in values})})
        if any(len(values) > 1 for values in states.values()):
            fields.append({"category": "identity_state", "field": "state_changes",
                           "values": sorted({value for values in states.values() for value in values})})
        raise StoryLockPreparationBlocked("explicit_dialogue_character_conflict", conflict_fields=fields)


def _merge_metadata(
    active: list[StoryEntity], chapter_order: dict[str, int], speaker: str, evidence: list[dict[str, Any]],
) -> _MergeMetadata:
    keys = sorted(_SYSTEM_EXTRACTION_METADATA_ATTRS_V1 - {
        "extraction_metadata_history", "extraction_metadata_aggregates",
    })
    history: list[dict[str, Any]] = []
    for item in sorted(active, key=lambda value: (
        chapter_order.get(str(value.chapter_id or value.first_seen_chapter_id or ""), 10**9), value.id,
    )):
        metadata = {key: (item.attributes or {}).get(key) for key in keys
                    if (item.attributes or {}).get(key) not in (None, "", [], {})}
        if item.confidence is not None:
            metadata["confidence"] = item.confidence
        history_item = {
            "source_entity_id": item.id, "chapter_id": item.chapter_id or item.first_seen_chapter_id,
            "evidence": item.evidence, "evidence_hash": _fingerprint(item.evidence), "metadata": metadata,
        }
        history_item["metadata_hash"] = _fingerprint(history_item)
        history.append(history_item)
    aggregates: dict[str, dict[str, Any]] = {}
    for key in [*keys, "confidence"]:
        entries = [item for item in history if key in item["metadata"]]
        if not entries:
            continue
        values = [item["metadata"][key] for item in entries]
        aggregate: dict[str, Any] = {
            "count": len(entries), "source_entity_ids": sorted(item["source_entity_id"] for item in entries),
            "value_hashes": sorted({_fingerprint(value) for value in values}),
        }
        if all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
            aggregate.update(min=min(values), max=max(values))
        aggregates[key] = aggregate
    hashes = {item["source_entity_id"]: item["metadata_hash"] for item in history}
    merge_evidence = [{
        "entity_id": item.id, "chapter_id": item.chapter_id, "first_seen_chapter_id": item.first_seen_chapter_id,
        "evidence": item.evidence, "source": item.source, "metadata_hash": hashes[item.id],
    } for item in active]
    merge_hash = _fingerprint({"speaker": speaker, "entities": merge_evidence, "dialogue": evidence})
    return _MergeMetadata(history, aggregates, merge_evidence, merge_hash)


def _apply_identity_projection(
    canonical: StoryEntity, projection: _CanonicalProjection, metadata: _MergeMetadata,
    speaker: str, evidence_hash: str,
) -> dict[str, list[str]]:
    active = projection.active
    canonical.name = speaker
    canonical.canonical_name = speaker
    canonical.source = "system"
    canonical.chapter_id = projection.earliest_chapter_id
    canonical.first_seen_chapter_id = projection.earliest_chapter_id
    canonical.aliases = list(dict.fromkeys([*(canonical.aliases or []), *(
        alias for item in active for alias in [item.name, item.canonical_name, *(item.aliases or [])] if alias
    )]))
    canonical.extra_data = {**(canonical.extra_data or {}),
        "explicit_dialogue_rule": {"rule": "rule_based_explicit_dialogue_v1", "evidence_hash": evidence_hash},
        "entity_normalization": {"status": "canonical", "merged_entity_ids": [item.id for item in projection.merged],
                                 "chapter_mentions": metadata.evidence, "merge_hash": metadata.merge_hash}}
    attrs = dict(canonical.attributes or {})
    attrs["extraction_metadata_history"] = metadata.history
    attrs["extraction_metadata_aggregates"] = metadata.aggregates
    attrs["extraction_notes"] = list(dict.fromkeys(
        note for item in metadata.history for note in (item["metadata"].get("extraction_notes") or [])
    ))
    mentions = [item["metadata"].get("mention_count") for item in metadata.history
                if isinstance(item["metadata"].get("mention_count"), (int, float))]
    if mentions:
        attrs["mention_count"] = sum(mentions)
    confidence = [item["metadata"].get("extraction_confidence") for item in metadata.history
                  if isinstance(item["metadata"].get("extraction_confidence"), (int, float))]
    if confidence:
        attrs["extraction_confidence"] = max(confidence)
    canonical.confidence = max((item.confidence for item in active if item.confidence is not None),
                               default=canonical.confidence)
    provenance: dict[str, list[str]] = {}
    for key in projection.identity_keys:
        sources = [item for item in active if (item.attributes or {}).get(key) not in (None, "", [], {})]
        if sources:
            raw = (sources[0].attributes or {})[key]
            attrs[key] = (_merged_visual_dna(active) if key == "visual_dna" else
                          _taxonomy_value(raw, _ROLE_TAGS) if key == "role" else
                          _taxonomy_value(raw, _SPECIES_TAGS) if key == "species" else raw)
            provenance[key] = list(dict.fromkeys(
                str(item.chapter_id or item.first_seen_chapter_id or "") for item in sources
            ))
    attrs["identity_fact_provenance"] = provenance
    attrs["source_chapter_id"] = projection.earliest_chapter_id
    attrs["source_chapter_index"] = projection.chapter_order.get(str(projection.earliest_chapter_id), 1)
    attrs["introduced_at"] = {"chapter_id": projection.earliest_chapter_id,
                              "chapter_number": attrs["source_chapter_index"]}
    canonical.attributes = attrs
    return provenance


def _apply_tag_identity(
    canonical: StoryEntity, projection: _CanonicalProjection, provenance: dict[str, list[str]],
) -> None:
    active, tags = projection.active, projection.tags
    attrs = dict(canonical.attributes or {})
    if tags.roles:
        attrs["role"] = next(iter(tags.roles))
        provenance["role"] = list(dict.fromkeys(str(item.chapter_id or item.first_seen_chapter_id or "")
            for item in active if any(_ROLE_TAGS.get(" ".join(str(tag).strip().casefold().split())) in tags.roles
                                      for tag in (item.tags or []))))
    if tags.species:
        attrs["species"] = next(iter(tags.species))
        provenance["species"] = list(dict.fromkeys(str(item.chapter_id or item.first_seen_chapter_id or "")
            for item in active if any(_SPECIES_TAGS.get(" ".join(str(tag).strip().casefold().split())) in tags.species
                                      for tag in (item.tags or []))))
    canonical.attributes = attrs
    descriptions = [item for item in active if str(item.description or "").strip()]
    if descriptions:
        canonical.description = descriptions[0].description
        canonical.extra_data = {**(canonical.extra_data or {}), "description_provenance": [
            str(item.chapter_id or item.first_seen_chapter_id or "") for item in descriptions
        ]}


def _merged_dicts(projection: _CanonicalProjection, field: str) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in sorted(projection.active, key=lambda value: (
        projection.chapter_order.get(str(value.chapter_id or value.first_seen_chapter_id or ""), 10**9), value.id,
    )):
        for raw in getattr(item, field) or []:
            if not isinstance(raw, dict):
                continue
            value = {**raw, "chapter_id": raw.get("chapter_id") or item.chapter_id or item.first_seen_chapter_id,
                     "source_entity_id": item.id}
            key = _fingerprint({name: content for name, content in value.items() if name != "source_entity_id"})
            if key not in seen:
                seen.add(key)
                values.append(value)
    return values


def _finalize_projection(
    canonical: StoryEntity, projection: _CanonicalProjection, provenance: dict[str, list[str]],
    merge_hash: str, user_id: str,
) -> None:
    canonical.relations = _merged_dicts(projection, "relations")
    canonical.state_changes = sorted(
        [*_merged_dicts(projection, "state_changes"), *projection.tags.state_changes],
        key=lambda item: (projection.chapter_order.get(str(item.get("chapter_id") or ""), 10**9), _fingerprint(item)),
    )
    ordered = sorted(projection.active, key=lambda item: (
        projection.chapter_order.get(str(item.chapter_id or item.first_seen_chapter_id or ""), 10**9), item.id,
    ))
    canonical.tags = sorted({
        *({f"role:{next(iter(projection.tags.roles))}"} if projection.tags.roles else set()),
        *({f"species:{next(iter(projection.tags.species))}"} if projection.tags.species else set()),
        *projection.tags.unknown,
    })
    canonical.attributes = {**(canonical.attributes or {}), "tag_fact_provenance": {
        tag: (provenance.get("role", []) if tag.startswith("role:") else
              provenance.get("species", []) if tag.startswith("species:") else
              list(dict.fromkeys(str(item.chapter_id or item.first_seen_chapter_id or "") for item in ordered
                    if tag in {" ".join(str(raw).strip().casefold().replace("_", "-").split())
                               for raw in (item.tags or [])})))
        for tag in canonical.tags
    }}
    set_entity_review_status(canonical, CANDIDATE, changed_by=user_id, reason="safe_system_duplicate_normalization")
    for item in projection.merged:
        item.first_seen_chapter_id = item.first_seen_chapter_id or item.chapter_id
        edge = sign_merge_edge({
            "source_entity_id": item.id, "canonical_entity_id": canonical.id,
            "user_id": item.user_id, "novel_id": item.novel_id,
            "entity_type": item.entity_type,
            "canonical_identity_sha256": canonical_identity_sha256(
                entity_type=canonical.entity_type,
                canonical_name=str(canonical.canonical_name or canonical.name or "")),
        })
        existing_edges = list((item.extra_data or {}).get("merge_edges") or [])
        source_edges = [value for value in existing_edges if value.get("source_entity_id") == item.id]
        if source_edges and source_edges != [edge]:
            raise StoryLockPreparationBlocked("existing normalized merge audit conflicts")
        item.extra_data = {**(item.extra_data or {}), "merge_edges": [
            *[value for value in existing_edges if value.get("source_entity_id") != item.id], edge,
        ], "normalized_merge": {
            "status": "merged_superseded", "canonical_entity_id": canonical.id,
            "merge_hash": merge_hash, "merged_at": utc_now().isoformat(),
        }}
        item.attributes = {**(item.attributes or {}), "merged_into_entity_id": canonical.id}
        set_entity_review_status(item, ARCHIVED, changed_by=user_id,
                                 reason="merged_into_explicit_dialogue_canonical")


def _normalize_safe_dialogue_duplicates(
    matches: list[StoryEntity], *, speaker: str, evidence: list[dict[str, Any]], evidence_hash: str, user_id: str,
    chapter_order: dict[str, int],
) -> StoryEntity:
    active, unsafe_lifecycle = _active_candidates(matches)
    identity_keys, conflict_values, conflict_fields = _identity_conflicts(active)
    relation_semantics, state_semantics = _timeline_conflicts(active)
    tag_facts = _tag_facts(active)
    _raise_candidate_conflicts(
        active, unsafe_lifecycle, conflict_values, conflict_fields, relation_semantics, state_semantics,
    )
    canonical = sorted(active, key=lambda item: (
        0 if get_entity_review_status(item) == APPROVED else 1,
        item.created_at or utc_now(), item.id,
    ))[0]
    merged = [item for item in active if item.id != canonical.id]
    earliest = min(active, key=lambda item: (
        chapter_order.get(str(item.first_seen_chapter_id or item.chapter_id or ""), 10**9), item.id,
    ))
    earliest_chapter_id = earliest.first_seen_chapter_id or earliest.chapter_id
    metadata = _merge_metadata(active, chapter_order, speaker, evidence)
    projection = _CanonicalProjection(active, merged, identity_keys, chapter_order, earliest_chapter_id, tag_facts)
    provenance = _apply_identity_projection(canonical, projection, metadata, speaker, evidence_hash)
    _apply_tag_identity(canonical, projection, provenance)
    _finalize_projection(canonical, projection, provenance, metadata.merge_hash, user_id)
    return canonical
