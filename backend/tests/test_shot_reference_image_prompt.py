from app.api.v1.endpoints.shots import _build_shot_reference_image_prompt
from app.services.consistency_context import _entity_ref, _merge_prompt_scope_entities, _summarize_refs
from types import SimpleNamespace


def test_shot_reference_prompt_keeps_locked_outfit_and_forbids_rendered_text() -> None:
    prompt = _build_shot_reference_image_prompt(
        "沈砚说：所有人撤离。角色视觉设定：深蓝旧呢大衣。",
        "3D 动漫",
    )

    assert "必须完整穿着已锁定服装" in prompt
    assert "不得脱下、替换或简化" in prompt
    assert "对白仅用于表情与口型语义" in prompt
    assert "禁止任何可读文字" in prompt


def test_story_entity_visual_dna_is_kept_in_image_prompt_context() -> None:
    entity = SimpleNamespace(
        id="entity-1", entity_type="character", name="沈砚", description=None,
        aliases=[], confidence=100, source="deterministic",
        attributes={"visual_dna": {"costume": "深蓝旧呢大衣", "hair": "黑色短发"}},
    )

    ref = _entity_ref(entity)

    assert ref["visual_dna"]["costume"] == "深蓝旧呢大衣"
    assert "深蓝旧呢大衣" in _summarize_refs([ref])


def test_chapter_prompt_scope_inherits_approved_novel_character() -> None:
    chapter_scene = SimpleNamespace(id="scene", entity_type="scene")
    canonical_character = SimpleNamespace(id="character", entity_type="character")
    foreign_prop = SimpleNamespace(id="prop", entity_type="prop")

    merged = _merge_prompt_scope_entities([chapter_scene], [canonical_character, foreign_prop])

    assert [entity.id for entity in merged] == ["scene", "character"]
