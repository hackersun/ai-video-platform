from app.services.consistency_ledger_service import build_consistency_ledger


def test_build_consistency_ledger_flags_unbound_character() -> None:
    ledger = build_consistency_ledger(
        shots=[{"id": "shot-1", "character_refs": [], "scene_refs": ["scene-1"], "video_status": "succeeded"}],
        episode_contract={"entity_locks": [{"entity_id": "char-1", "entity_type": "character", "name": "孙剑"}]},
        jobs=[],
    )

    assert ledger["overall_score"] < 80
    assert ledger["findings"][0]["code"] == "shot_character_unbound"
    assert ledger["findings"][0]["repair_action"]["code"] == "bind_character_reference"


def test_build_consistency_ledger_accepts_bound_character_refs() -> None:
    ledger = build_consistency_ledger(
        shots=[{"id": "shot-1", "character_refs": [{"character_id": "char-1"}], "scene_refs": []}],
        episode_contract={"entity_locks": [{"entity_id": "char-1", "entity_type": "character", "name": "孙剑"}]},
        jobs=[],
    )

    assert ledger["overall_score"] == 100
    assert ledger["findings"] == []


def test_build_consistency_ledger_accepts_entity_ref_characters() -> None:
    ledger = build_consistency_ledger(
        shots=[{"id": "shot-1", "character_refs": [], "entity_refs": {"character": ["char-1"]}}],
        episode_contract={"entity_locks": [{"entity_id": "char-1", "entity_type": "character", "name": "孙剑"}]},
        jobs=[],
    )

    assert ledger["overall_score"] == 100
    assert ledger["findings"] == []
