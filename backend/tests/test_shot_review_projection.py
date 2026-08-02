from types import SimpleNamespace

from app.services.shot_review_projection import shot_reference_review_fields


def test_shot_review_projection_exposes_episode_scene_sequence() -> None:
    shot = SimpleNamespace(
        image_url=None,
        image_status=None,
        image_asset_id=None,
        character_refs=[],
        extra_data={
            "episode_shot_number": 7,
            "scene_index": 3,
            "scene_count": 5,
            "scene_title": "归墟塔",
            "entity_refs": {},
        },
    )

    result = shot_reference_review_fields(shot)

    assert result["episode_shot_number"] == 7
    assert result["scene_index"] == 3
    assert result["scene_count"] == 5
    assert result["scene_title"] == "归墟塔"
