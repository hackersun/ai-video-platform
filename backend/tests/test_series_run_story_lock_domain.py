from __future__ import annotations

import pytest
from itertools import permutations

from app.features.series_run_story_locks.domain import (
    EntityFact, build_closure, validate_reference_scope, validate_required_facts,
)


def _fact(
    *, chapter_id: str = "chapter-1", entity_type: str = "prop",
    content_hash: str = "a" * 64, expected_content_hash: str = "a" * 64,
    relations: tuple[dict, ...] = (), state_changes: tuple[dict, ...] = (),
    tags: tuple[str, ...] = (), identity: dict | None = None,
) -> EntityFact:
    return EntityFact(
        id="entity-1", entity_type=entity_type, user_id="user-1", novel_id="novel-1",
        chapter_id=chapter_id, lifecycle_status="candidate", evidence_status="verified",
        evidence_chapter_id=chapter_id, source_span=(0, 1), content_hash=content_hash,
        expected_content_hash=expected_content_hash, parser_version="trusted-v1",
        chapter_content_length=100,
        conflicting_values=(), first_seen_chapter_id=chapter_id,
        identity=identity or {}, relations=relations, state_changes=state_changes, tags=tags,
        provenance_chapter_ids=(),
        canonical_identity_key=f"{entity_type}:entity-1", identity_keys=(f"{entity_type}:entity-1",),
    )


def test_reference_scope_accepts_same_or_earlier_chapter_fact() -> None:
    ranks = {"chapter-1": 0, "chapter-2": 1}

    validate_reference_scope([("prop", "entity-1", "chapter-2")], [_fact()], ranks)


def test_reference_scope_rejects_future_chapter_projection() -> None:
    ranks = {"chapter-1": 0, "chapter-2": 1}

    with pytest.raises(ValueError, match="future-chapter"):
        validate_reference_scope(
            [("prop", "entity-1", "chapter-1")],
            [_fact(chapter_id="chapter-2")],
            ranks,
        )


def test_reference_scope_rejects_wrong_entity_type() -> None:
    with pytest.raises(ValueError, match="wrong type"):
        validate_reference_scope(
            [("scene", "entity-1", "chapter-1")],
            [_fact(entity_type="prop")],
            {"chapter-1": 0},
        )


def test_closure_rejects_unknown_required_entity_instead_of_dropping_it() -> None:
    with pytest.raises(ValueError, match="does not resolve"):
        build_closure({"prop": ["missing"]}, [])


@pytest.mark.parametrize("content_hash", ["z" * 64, "A" * 64, "b" * 64])
def test_required_evidence_rejects_invalid_or_nonmatching_chapter_hash(content_hash: str) -> None:
    fact = _fact(content_hash=content_hash)
    closure = build_closure({"prop": [fact.id]}, [fact])

    with pytest.raises(Exception, match="required_entity_evidence_invalid"):
        validate_required_facts(closure, [fact])


def test_reference_scope_uses_unique_chapter_order_within_same_episode() -> None:
    ranks = {"chapter-1": 0, "chapter-2": 1}
    with pytest.raises(ValueError, match="future-chapter"):
        validate_reference_scope(
            [("prop", "entity-1", "chapter-1")],
            [_fact(chapter_id="chapter-2")],
            ranks,
        )


@pytest.mark.parametrize(
    "fact",
    [
        _fact(identity={"role": ["protagonist", "antagonist"]}),
        _fact(relations=({"chapter_id": "chapter-1", "entity_id": "x", "type": "ally"},
                         {"chapter_id": "chapter-1", "entity_id": "x", "type": "enemy"})),
        _fact(state_changes=({"chapter_id": "chapter-1", "state": "alive"},
                             {"chapter_id": "chapter-1", "state": "dead"})),
        _fact(tags=("protagonist", "antagonist")),
    ],
)
def test_required_fact_rejects_identity_relation_state_and_tag_conflicts(fact: EntityFact) -> None:
    closure = build_closure({"prop": [fact.id]}, [fact])
    with pytest.raises(Exception, match="required_entity_compatibility_conflict"):
        validate_required_facts(closure, [fact])


def test_required_group_rejects_conflicting_same_identity_facts() -> None:
    first = _fact(identity={"role": "protagonist"})
    second = EntityFact(**{
        **first.__dict__, "id": "entity-2", "identity": {"role": "antagonist"},
    })
    closure = build_closure({"prop": [first.id, second.id]}, [first, second])

    with pytest.raises(Exception, match="required_entity_compatibility_conflict"):
        validate_required_facts(closure, [first, second])


def test_required_group_rejects_distinct_unknown_tags() -> None:
    first = _fact(tags=("red-cloak",))
    second = EntityFact(**{**first.__dict__, "id": "entity-2", "tags": ("blue-cloak",)})
    closure = build_closure({"prop": [first.id, second.id]}, [first, second])

    with pytest.raises(Exception, match="required_entity_compatibility_conflict"):
        validate_required_facts(closure, [first, second])


def test_different_identity_groups_do_not_conflict() -> None:
    first = _fact(identity={"role": "protagonist"})
    second = EntityFact(**{
        **first.__dict__, "id": "entity-2", "canonical_identity_key": "prop:entity-2",
        "identity_keys": ("prop:entity-2",), "identity": {"role": "antagonist"},
    })
    closure = build_closure({"prop": [first.id, second.id]}, [first, second])

    validate_required_facts(closure, [first, second])


def test_alias_identity_key_cannot_point_to_multiple_canonical_identities() -> None:
    first = _fact()
    second = EntityFact(**{
        **first.__dict__, "id": "entity-2", "canonical_identity_key": "prop:entity-2",
        "identity_keys": ("prop:entity-2", "prop:alias:shared"),
    })
    first = EntityFact(**{**first.__dict__, "identity_keys": (first.canonical_identity_key, "prop:alias:shared")})
    closure = build_closure({"prop": [first.id, second.id]}, [first, second])

    with pytest.raises(Exception, match="required_entity_identity_ambiguous"):
        validate_required_facts(closure, [first, second])


def test_speaker_reference_groups_distinct_rows_for_compatibility() -> None:
    first = _fact(identity={"role": "protagonist"})
    first = EntityFact(**{**first.__dict__, "identity_keys": (first.canonical_identity_key, "prop:speaker:shared")})
    second = EntityFact(**{
        **first.__dict__, "id": "entity-2", "canonical_identity_key": "prop:entity-2",
        "identity_keys": ("prop:entity-2", "prop:speaker:shared"), "identity": {"role": "antagonist"},
    })
    closure = build_closure({"prop": [first.id, second.id]}, [first, second])

    with pytest.raises(Exception, match="required_entity_compatibility_conflict"):
        validate_required_facts(closure, [first, second])


def test_same_unknown_tag_and_known_synonyms_deduplicate() -> None:
    first = _fact(tags=("red-cloak", "lead", "alive"))
    second = EntityFact(**{
        **first.__dict__, "id": "entity-2", "tags": ("red-cloak", "protagonist", "存活"),
    })
    closure = build_closure({"prop": [first.id, second.id]}, [first, second])

    validate_required_facts(closure, [first, second])


def test_bridged_identity_component_blocks_conflict_in_every_input_order() -> None:
    x = _fact(identity={"role": "protagonist"})
    y = EntityFact(**{
        **x.__dict__, "id": "entity-y", "canonical_identity_key": "prop:canonical:y",
        "identity_keys": ("prop:canonical:y", "prop:speaker:shared"),
        "identity": {"role": "antagonist"},
    })
    bridge = EntityFact(**{
        **x.__dict__, "id": "entity-bridge",
        "identity_keys": (x.canonical_identity_key, "prop:speaker:shared"),
    })
    for ordered in permutations([x, y, bridge]):
        closure = build_closure({"prop": [fact.id for fact in ordered]}, list(ordered))
        with pytest.raises(Exception, match="required_entity_compatibility_conflict"):
            validate_required_facts(closure, list(ordered))


def test_compatible_bridged_identity_component_is_order_independent() -> None:
    x = _fact(identity={"role": "lead"})
    y = EntityFact(**{
        **x.__dict__, "id": "entity-y", "canonical_identity_key": "prop:canonical:y",
        "identity_keys": ("prop:canonical:y", "prop:speaker:shared"),
        "identity": {"role": "protagonist"},
    })
    bridge = EntityFact(**{
        **x.__dict__, "id": "entity-bridge",
        "identity_keys": (x.canonical_identity_key, "prop:speaker:shared"),
    })
    for ordered in permutations([x, y, bridge]):
        closure = build_closure({"prop": [fact.id for fact in ordered]}, list(ordered))
        validate_required_facts(closure, list(ordered))


def test_single_fact_distinct_unknown_tags_fail_closed() -> None:
    fact = _fact(tags=("red-cloak", "blue-cloak"))
    closure = build_closure({"prop": [fact.id]}, [fact])
    with pytest.raises(Exception, match="required_entity_compatibility_conflict"):
        validate_required_facts(closure, [fact])


def test_single_fact_known_synonyms_deduplicate() -> None:
    fact = _fact(tags=("lead", "protagonist", "alive", "存活", "human", "人类"))
    closure = build_closure({"prop": [fact.id]}, [fact])
    validate_required_facts(closure, [fact])
