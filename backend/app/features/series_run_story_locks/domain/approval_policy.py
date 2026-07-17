"""Pure required-entity closure and approval rules."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Mapping, Sequence

from .errors import RequiredEntityBlocked, StoryLockSourceStale


ENTITY_TYPES = ("character", "scene", "prop", "event")
REFERENCE_KEYS = {"characters": "character", "scenes": "scene", "props": "prop", "events": "event"}


@dataclass(frozen=True)
class EntityFact:
    id: str
    entity_type: str
    user_id: str
    novel_id: str | None
    chapter_id: str | None
    lifecycle_status: str
    evidence_status: str
    evidence_chapter_id: str | None
    source_span: tuple[int, int] | None
    content_hash: str
    expected_content_hash: str
    chapter_content_length: int
    parser_version: str
    conflicting_values: tuple[object, ...]
    first_seen_chapter_id: str | None
    identity: Mapping[str, object]
    relations: tuple[Mapping[str, object], ...]
    state_changes: tuple[Mapping[str, object], ...]
    tags: tuple[str, ...]
    provenance_chapter_ids: tuple[str, ...]
    canonical_identity_key: str
    identity_keys: tuple[str, ...]


@dataclass(frozen=True)
class RequiredEntityClosure:
    candidate_counts: Mapping[str, int]
    required_counts: Mapping[str, int]
    required_entity_ids: tuple[str, ...]
    unrelated_candidate_count: int
    closure_hash: str
    dependency_edges: tuple[tuple[str, str], ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "candidate_counts": dict(self.candidate_counts),
            "required_counts": dict(self.required_counts),
            "required_entity_ids": list(self.required_entity_ids),
            "unrelated_candidate_count": self.unrelated_candidate_count,
            "closure_hash": self.closure_hash,
            "dependency_edges": [
                {"entity_type": entity_type, "entity_id": entity_id}
                for entity_type, entity_id in self.dependency_edges
            ],
        }


def build_closure(reference_ids: Mapping[str, Sequence[str]], facts: Sequence[EntityFact]) -> RequiredEntityClosure:
    facts_by_id = {fact.id: fact for fact in facts}
    candidate_counts = {kind: sum(fact.entity_type == kind for fact in facts) for kind in ENTITY_TYPES}
    required_pairs = sorted(
        (kind, entity_id)
        for kind in ENTITY_TYPES
        for entity_id in set(reference_ids.get(kind, ()))
    )
    for kind, entity_id in required_pairs:
        fact = facts_by_id.get(entity_id)
        if fact is None:
            raise StoryLockSourceStale("selected_entity_missing_or_unowned", "required entity reference does not resolve in the owned run")
        if fact.entity_type != kind:
            raise StoryLockSourceStale("selected_typed_ref_wrong_type", "required entity reference has the wrong type")
    required_ids = tuple(entity_id for _kind, entity_id in required_pairs)
    required_counts = {
        kind: sum(pair_kind == kind for pair_kind, _entity_id in required_pairs)
        for kind in ENTITY_TYPES
    }
    payload = [{"entity_id": entity_id, "entity_type": kind} for kind, entity_id in required_pairs]
    closure_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return RequiredEntityClosure(
        candidate_counts=candidate_counts,
        required_counts=required_counts,
        required_entity_ids=required_ids,
        unrelated_candidate_count=len(facts) - len(required_ids),
        closure_hash=closure_hash,
        dependency_edges=tuple(required_pairs),
    )


def validate_required_facts(closure: RequiredEntityClosure, facts: Sequence[EntityFact]) -> None:
    facts_by_id = {fact.id: fact for fact in facts}
    for entity_id in closure.required_entity_ids:
        fact = facts_by_id[entity_id]
        if fact.evidence_status == "ambiguous" or fact.conflicting_values:
            raise _blocked(fact, closure, "required_entity_evidence_ambiguous", fact.conflicting_values)
        if not _evidence_is_verified(fact):
            raise _blocked(fact, closure, "required_entity_evidence_invalid", (fact.id,))
        if fact.lifecycle_status not in {"candidate", "approved"}:
            raise _blocked(fact, closure, "required_entity_state_invalid", (fact.lifecycle_status,))
        conflicts = compatibility_conflicts(fact)
        if conflicts:
            raise _blocked(fact, closure, "required_entity_compatibility_conflict", conflicts)
    required = [facts_by_id[entity_id] for entity_id in closure.required_entity_ids]
    _validate_identity_aliases(required, closure)
    for group in _identity_groups(required):
        conflicts = group_compatibility_conflicts(group)
        if conflicts:
            raise _blocked(group[0], closure, "required_entity_compatibility_conflict", conflicts)


def validate_reference_scope(
    references: Sequence[tuple[str, str, str]],
    facts: Sequence[EntityFact],
    chapter_ranks: Mapping[str, int],
) -> None:
    facts_by_id = {fact.id: fact for fact in facts}
    for entity_type, entity_id, as_of_chapter_id in references:
        fact = facts_by_id.get(entity_id)
        if fact is None or fact.entity_type != entity_type:
            raise StoryLockSourceStale("selected_typed_ref_missing_or_wrong_type", "selected shot entity reference is missing or has the wrong type")
        fact_rank = chapter_ranks.get(str(fact.chapter_id or ""))
        first_seen_rank = chapter_ranks.get(str(fact.first_seen_chapter_id or ""))
        evidence_rank = chapter_ranks.get(str(fact.evidence_chapter_id or ""))
        as_of_rank = chapter_ranks.get(as_of_chapter_id)
        ranks = (fact_rank, first_seen_rank, evidence_rank, as_of_rank)
        if any(rank is None for rank in ranks) or max(fact_rank, first_seen_rank, evidence_rank) > as_of_rank:
            raise StoryLockSourceStale("selected_ref_future_projection", "selected shot entity reference projects a future-chapter fact")
        projected = [
            *fact.provenance_chapter_ids,
            *(str(item.get("chapter_id") or "") for item in fact.relations),
            *(str(item.get("chapter_id") or "") for item in fact.state_changes),
        ]
        if any(chapter_ranks.get(chapter_id, 10**9) > as_of_rank for chapter_id in projected):
            raise StoryLockSourceStale("selected_ref_future_provenance", "selected shot entity reference projects future provenance")


def _evidence_is_verified(fact: EntityFact) -> bool:
    return bool(
        fact.evidence_status == "verified"
        and fact.chapter_id
        and fact.evidence_chapter_id == fact.chapter_id
        and fact.source_span
        and fact.source_span[0] >= 0
        and fact.source_span[1] > fact.source_span[0]
        and fact.source_span[1] <= fact.chapter_content_length
        and len(fact.content_hash) == 64
        and all(character in "0123456789abcdef" for character in fact.content_hash)
        and fact.content_hash == fact.expected_content_hash
        and fact.parser_version
    )


ROLE_TAGS = {"protagonist": "protagonist", "lead": "protagonist", "主角": "protagonist",
             "antagonist": "antagonist", "villain": "antagonist", "反派": "antagonist",
             "supporting": "supporting", "support": "supporting", "配角": "supporting"}
SPECIES_TAGS = {"human": "human", "人类": "human", "spirit": "spirit", "灵体": "spirit",
                "demon": "demon", "恶魔": "demon"}
STATE_TAGS = {"alive": "alive", "存活": "alive", "dead": "dead", "死亡": "dead",
              "injured": "injured", "受伤": "injured"}


def compatibility_conflicts(fact: EntityFact) -> tuple[object, ...]:
    conflicts: list[object] = []
    for field, raw in fact.identity.items():
        values = raw if isinstance(raw, (list, tuple, set)) else [raw]
        normalized = {_identity_value(value, ROLE_TAGS if field == "role" else SPECIES_TAGS if field == "species" else {}) for value in values}
        if len(normalized) > 1:
            conflicts.append({"identity": field, "values": sorted(normalized)})
    conflicts.extend(_semantic_conflicts(fact.relations, ("chapter_id", "entity_id"), ("type", "relation")))
    conflicts.extend(_semantic_conflicts(
        fact.state_changes, ("chapter_id",), ("state", "status"), STATE_TAGS,
    ))
    conflicts.extend(_tag_conflicts(fact.tags, fact.chapter_id))
    return tuple(conflicts)


def group_compatibility_conflicts(facts: Sequence[EntityFact]) -> tuple[object, ...]:
    conflicts: list[object] = []
    fields = sorted({field for fact in facts for field in fact.identity})
    for field in fields:
        taxonomy = ROLE_TAGS if field == "role" else SPECIES_TAGS if field == "species" else {}
        values = {_identity_value(fact.identity[field], taxonomy) for fact in facts if field in fact.identity}
        if len(values) > 1:
            conflicts.append({"identity": field, "values": sorted(values)})
    conflicts.extend(_group_semantic_conflicts(facts, "relations", ("chapter_id", "entity_id"), ("type", "relation")))
    conflicts.extend(_group_semantic_conflicts(facts, "state_changes", ("chapter_id",), ("state", "status"), STATE_TAGS))
    conflicts.extend(_group_tag_conflicts(facts))
    return tuple(conflicts)


def _validate_identity_aliases(facts: Sequence[EntityFact], closure: RequiredEntityClosure) -> None:
    aliases: dict[str, set[str]] = {}
    for fact in facts:
        for key in fact.identity_keys:
            if ":alias:" in key:
                aliases.setdefault(key, set()).add(fact.canonical_identity_key)
    ambiguous = {key: values for key, values in aliases.items() if len(values) > 1}
    if ambiguous:
        fact = facts[0]
        raise _blocked(fact, closure, "required_entity_identity_ambiguous", tuple(sorted(ambiguous)))


def _identity_groups(facts: Sequence[EntityFact]) -> list[list[EntityFact]]:
    ordered = sorted(facts, key=lambda fact: (fact.canonical_identity_key, fact.id))
    parent = list(range(len(ordered)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    token_owner: dict[str, int] = {}
    for index, fact in enumerate(ordered):
        for token in sorted(set(fact.identity_keys)):
            if token in token_owner:
                union(index, token_owner[token])
            else:
                token_owner[token] = index
    components: dict[int, list[EntityFact]] = {}
    for index, fact in enumerate(ordered):
        components.setdefault(find(index), []).append(fact)
    groups = [sorted(group, key=lambda fact: (fact.canonical_identity_key, fact.id)) for group in components.values()]
    return sorted(groups, key=lambda group: (group[0].canonical_identity_key, group[0].id))


def _group_semantic_conflicts(
    facts: Sequence[EntityFact],
    field: str,
    key_fields: tuple[str, ...],
    value_fields: tuple[str, ...],
    taxonomy: Mapping[str, str] | None = None,
) -> list[object]:
    items = [item for fact in facts for item in getattr(fact, field)]
    return _semantic_conflicts(items, key_fields, value_fields, taxonomy)


def _group_tag_conflicts(facts: Sequence[EntityFact]) -> list[object]:
    known = _tag_conflicts(tuple(tag for fact in facts for tag in fact.tags), facts[0].chapter_id)
    unknown = {
        _taxonomy(tag, {}) for fact in facts for tag in fact.tags
        if _taxonomy(tag, {}) not in ROLE_TAGS and _taxonomy(tag, {}) not in SPECIES_TAGS
        and _taxonomy(tag, {}) not in STATE_TAGS and ":" not in _taxonomy(tag, {})
    }
    if len(unknown) > 1:
        known.append({"tag": "unknown", "values": sorted(unknown)})
    return known


def _semantic_conflicts(
    items: Sequence[Mapping[str, object]],
    key_fields: tuple[str, ...],
    value_fields: tuple[str, ...],
    taxonomy: Mapping[str, str] | None = None,
) -> list[object]:
    grouped: dict[tuple[str, ...], set[str]] = {}
    for item in items:
        key = tuple(str(item.get(field) or "") for field in key_fields)
        raw_value = next((item.get(field) for field in value_fields if item.get(field)), "")
        value = _taxonomy(raw_value, taxonomy or {})
        if not all(key) or not value:
            return [{"malformed_provenance": dict(item)}]
        grouped.setdefault(key, set()).add(value)
    return [{"key": key, "values": sorted(values)} for key, values in grouped.items() if len(values) > 1]


def _tag_conflicts(tags: Sequence[str], chapter_id: str | None) -> list[object]:
    groups: dict[str, set[str]] = {"role": set(), "species": set(), "state": set()}
    unknown: dict[str, set[str]] = {}
    plain_unknown: set[str] = set()
    for raw in tags:
        tag = _taxonomy(raw, {})
        if tag in ROLE_TAGS:
            groups["role"].add(ROLE_TAGS[tag])
        elif tag in SPECIES_TAGS:
            groups["species"].add(SPECIES_TAGS[tag])
        elif tag in STATE_TAGS:
            groups["state"].add(STATE_TAGS[tag])
        elif ":" in tag:
            key, value = tag.split(":", 1)
            unknown.setdefault(key, set()).add(value)
        else:
            plain_unknown.add(tag)
    conflicts = [{"tag": key, "chapter_id": chapter_id, "values": sorted(values)} for key, values in groups.items() if len(values) > 1]
    conflicts.extend({"tag": key, "values": sorted(values)} for key, values in unknown.items() if len(values) > 1)
    if len(plain_unknown) > 1:
        conflicts.append({"tag": "unknown", "values": sorted(plain_unknown)})
    return conflicts


def _taxonomy(value: object, taxonomy: Mapping[str, str]) -> str:
    normalized = " ".join(str(value or "").strip().casefold().replace("_", "-").split())
    return taxonomy.get(normalized, normalized)


def _identity_value(value: object, taxonomy: Mapping[str, str]) -> str:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _taxonomy(value, taxonomy)


def _blocked(
    fact: EntityFact,
    closure: RequiredEntityClosure,
    code: str,
    values: Sequence[object],
) -> RequiredEntityBlocked:
    category = f"{fact.entity_type}_state" if fact.entity_type != "character" else "identity_state"
    return RequiredEntityBlocked(
        code=code,
        blocker_category=category,
        field="state",
        values=tuple(values),
        required_counts=dict(closure.required_counts),
    )
