from types import SimpleNamespace

from app.features.video_generation.application.consistency_package import (
    _PackageState,
    _format_visual_locks,
    _resolve_character_refs,
)


def test_scoped_story_entity_ref_is_kept_as_canonical_character_lock() -> None:
    canonical = SimpleNamespace(
        id="canonical-shenyan", name="沈砚", canonical_name="沈砚",
        description="雾港调查员",
        appearance="黑色短发，深蓝旧呢大衣，银色怀表。",
        attributes={"visual_dna": {"costume": "深蓝旧呢大衣"}},
    )
    request = SimpleNamespace(character_ids=[])
    shot = SimpleNamespace(prompt="沈砚抵达灯塔", visual_description="", dialogue="沈砚：撤离。")
    scoped_ref = {
        "entity_type": "character", "entity_id": canonical.id,
        "canonical_entity_id": canonical.id, "source_entity_id": "chapter-four-mention",
    }
    state = _PackageState(
        context=SimpleNamespace(request=request), shot=shot,
        shot_context={"character_refs": [scoped_ref], "subtitle_text": "沈砚：撤离。"},
        novel_id="novel-1", chapter_id="chapter-4", characters=[], character_by_id={},
        story_character_by_id={canonical.id: canonical, "chapter-four-mention": canonical},
    )

    _resolve_character_refs(state)

    assert state.filtered_refs == []
    assert state.character_refs[0]["entity_id"] == canonical.id
    assert state.character_refs[0]["name"] == "沈砚"
    assert state.character_refs[0]["appearance"] == canonical.appearance
    assert state.character_refs[0]["visual_dna"]["costume"] == "深蓝旧呢大衣"
    assert "外貌:黑色短发，深蓝旧呢大衣，银色怀表" in _format_visual_locks(
        state.character_refs
    )
