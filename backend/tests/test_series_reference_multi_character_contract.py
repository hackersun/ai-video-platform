from types import SimpleNamespace

from app.services import series_run_reference_preparation
from app.features.series_reference_skill.public import character_visual_contract
from app.features.series_run_media_preflight.public import _asset_matches
from app.models import Asset, StoryEntity
from app.services.default_prompt_skills import STANDARD_PROMPT_SKILLS


def test_composite_reference_binds_every_required_character_once():
    assert hasattr(series_run_reference_preparation, "_character_role_bindings")
    character_role_bindings = series_run_reference_preparation._character_role_bindings
    characters = [
        SimpleNamespace(id="character-lin", name="林澈", canonical_name="林澈"),
        SimpleNamespace(id="character-lu", name="陆遥", canonical_name="陆遥"),
        SimpleNamespace(id="character-lin", name="林澈重复", canonical_name="林澈"),
    ]

    bindings = character_role_bindings(characters)

    assert bindings == [
        {"role": "character_canonical", "entity_id": "character-lin"},
        {"role": "character_canonical", "entity_id": "character-lu"},
    ]


def test_multi_character_composite_matches_each_bound_character() -> None:
    asset = Asset(id="asset-1", generation_params={
        "composite_reference_rule": "single_artifact_dual_role_v1",
        "role_bindings": [
            {"role": "character_canonical", "entity_id": "character-1"},
            {"role": "character_canonical", "entity_id": "character-2"},
            {"role": "global_style_board", "novel_id": "novel-1"},
        ],
    })

    assert _asset_matches(asset, StoryEntity(id="character-1")) is True
    assert _asset_matches(asset, StoryEntity(id="character-2")) is True
    assert _asset_matches(asset, StoryEntity(id="character-3")) is False


def test_composite_reference_has_a_dedicated_builtin_prompt_skill() -> None:
    skills = [item for item in STANDARD_PROMPT_SKILLS if item["task"] == "series_reference_board"]

    assert len(skills) == 1
    assert "复合" in skills[0]["content"]
    assert "characters" in skills[0]["variables"]


def test_reference_prompt_contract_contains_exact_locked_wardrobe() -> None:
    character = SimpleNamespace(
        id="character-shen",
        name="沈砚",
        canonical_name="沈砚",
        appearance="黑色短发，深蓝旧呢大衣，银色怀表。",
        attributes={
            "visual_dna": {
                "identity_anchor": "沈砚",
                "hair": "黑色短发",
                "costume": "深蓝旧呢大衣",
            }
        },
    )

    contract = character_visual_contract([character])

    assert "沈砚" in contract
    assert "外观定稿=黑色短发，深蓝旧呢大衣，银色怀表" in contract
    assert "服装=深蓝旧呢大衣" in contract
    assert "不得改成短衫" in contract


def test_reference_visual_contract_hash_changes_with_canonical_appearance() -> None:
    black_hair = SimpleNamespace(
        id="character-shen",
        appearance="黑色短发，深蓝旧呢大衣",
        attributes={"visual_dna": {"costume": "深蓝旧呢大衣"}},
    )
    silver_hair = SimpleNamespace(
        id="character-shen",
        appearance="银白色短发，深蓝旧呢大衣",
        attributes={"visual_dna": {"costume": "深蓝旧呢大衣"}},
    )

    assert series_run_reference_preparation.reference_visual_contract_hash(
        [black_hair]
    ) != series_run_reference_preparation.reference_visual_contract_hash([silver_hair])


def test_existing_reference_without_current_visual_contract_is_stale() -> None:
    character = SimpleNamespace(
        id="character-shen",
        attributes={"visual_dna": {"costume": "深蓝旧呢大衣"}},
    )
    asset = SimpleNamespace(generation_params={"evidence": {"status": "completed"}})

    assert series_run_reference_preparation._reference_visual_contract_matches(
        asset, [character]
    ) is False


def test_reference_visual_contract_hash_is_independent_of_query_order() -> None:
    first = SimpleNamespace(id="character-a", attributes={"visual_dna": {"costume": "蓝色长外套"}})
    second = SimpleNamespace(id="character-b", attributes={"visual_dna": {"costume": "灰色风衣"}})

    assert series_run_reference_preparation.reference_visual_contract_hash([first, second]) == (
        series_run_reference_preparation.reference_visual_contract_hash([second, first])
    )


def test_superseded_series_reference_rebinds_shot_lock_without_dropping_other_assets() -> None:
    shot = SimpleNamespace(extra_data={"production_context": {
        "asset_version_locks": [
            {"asset_id": "old-reference", "asset_version": 1, "locked": True},
            {"asset_id": "scene-asset", "asset_version": 3, "locked": True},
        ],
        "canonical_reference_id": "old-reference",
        "canonical_reference_version": 1,
    }})

    changed = series_run_reference_preparation.rebind_shot_reference_context(
        shot,
        superseded_asset_id="old-reference",
        replacement_asset_id="new-reference",
        replacement_asset_version=2,
        rebound_at="2026-07-24T00:00:00",
    )

    assert changed is True
    context = shot.extra_data["production_context"]
    assert context["asset_version_locks"] == [
        {"asset_id": "new-reference", "asset_version": 2, "locked": True},
        {"asset_id": "scene-asset", "asset_version": 3, "locked": True},
    ]
    assert context["canonical_reference_id"] == "new-reference"
    assert context["canonical_reference_version"] == 2
    assert context["reference_rebind"]["superseded_asset_id"] == "old-reference"


def test_first_series_reference_is_bound_to_existing_run_shot() -> None:
    shot = SimpleNamespace(extra_data={"production_context": {
        "asset_version_locks": [
            {"asset_id": "scene-asset", "asset_version": 3, "locked": True},
        ],
    }})

    changed = series_run_reference_preparation.rebind_shot_reference_context(
        shot,
        superseded_asset_id="",
        replacement_asset_id="series-reference",
        replacement_asset_version=1,
        rebound_at="2026-08-01T00:00:00",
    )

    assert changed is True
    context = shot.extra_data["production_context"]
    assert context["asset_version_locks"] == [
        {"asset_id": "scene-asset", "asset_version": 3, "locked": True},
        {"asset_id": "series-reference", "asset_version": 1, "locked": True},
    ]
    assert context["canonical_reference_id"] == "series-reference"
    assert context["canonical_reference_version"] == 1
