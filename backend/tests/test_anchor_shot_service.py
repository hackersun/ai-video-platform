from types import SimpleNamespace

import pytest

from app.services.anchor_shot_service import anchor_coverage_blocker, recommend_anchor_shots, validate_anchor_selection


def _shot(shot_id: str, episode: int, *, dialogue="", extra=None):
    return SimpleNamespace(
        id=shot_id,
        shot_number=1,
        dialogue=dialogue,
        prompt="转折 道具 主角" if episode in {2, 4} else "主角 场景",
        visual_description="新场景 决战" if episode >= 3 else "首次登场",
        character_refs=[{"character_id": "hero"}],
        camera_angle="wide",
        video_url="https://artifact.invalid/video.mp4",
        video_status="succeeded",
        extra_data={"episode_number": episode, "event_refs": [f"event-{episode}"], "style_evidence": {"style": "anime"}, "delivery_evidence": {"artifact_id": shot_id}, **(extra or {})},
    )


def test_smoke_recommendation_uses_two_different_episodes():
    shots = [_shot(f"shot-{episode}", episode, dialogue="主角：出发") for episode in range(1, 5)]

    result = recommend_anchor_shots(shots, mode="smoke")

    assert len(result) == 2
    assert [item["episode_number"] for item in result] == [1, 4]


def test_full_recommendation_covers_all_episodes_and_dimensions():
    shots = [
        _shot(f"shot-{episode}-{index}", episode, dialogue="主角：守住约定" if index == 1 else "", extra={"continuity_prop": index == 2})
        for episode in range(1, 5)
        for index in range(1, 3)
    ]

    result = recommend_anchor_shots(shots, mode="full")

    assert len(result) == 6
    assert {item["episode_number"] for item in result} == {1, 2, 3, 4}
    assert set().union(*(set(item["dimensions"]) for item in result)) >= {
        "character_visual", "scene_prop_state", "narrative_truth", "voice_dialogue", "style_cinematography"
    }


def test_representative_recommendation_uses_first_middle_and_last_episode():
    shots = [_shot(f"shot-{episode}", episode, dialogue="主角：守住道心") for episode in range(1, 6)]

    result = recommend_anchor_shots(shots, mode="representative")

    assert len(result) == 3
    assert [item["episode_number"] for item in result] == [1, 3, 5]
    assert anchor_coverage_blocker(result, mode="representative") is None


def test_representative_selection_does_not_require_post_generation_quality_dimensions():
    shots = [_shot(f"shot-{episode}", episode) for episode in range(1, 6)]
    for shot in shots:
        shot.camera_angle = None
        shot.video_url = None
        shot.video_status = "pending"
        shot.dialogue = ""
        shot.prompt = "主角进入场景"
        shot.visual_description = "固定服装"
        shot.extra_data = {"episode_number": shot.extra_data["episode_number"]}

    result = recommend_anchor_shots(shots, mode="representative")

    assert anchor_coverage_blocker(result, mode="representative") is None


def test_selection_rejects_shot_outside_run():
    with pytest.raises(ValueError, match="outside series run"):
        validate_anchor_selection(["shot-1", "foreign"], {"shot-1", "shot-2"})


def test_full_mode_fails_closed_when_run_has_only_four_shots():
    recommendations = recommend_anchor_shots([_shot(f"shot-{episode}", episode) for episode in range(1, 5)], mode="full")

    blocker = anchor_coverage_blocker(recommendations, mode="full")

    assert blocker["code"] == "insufficient_anchor_coverage"
    assert blocker["available_count"] == 4


def test_six_shots_do_not_claim_dimensions_without_structured_evidence():
    shots = [_shot(f"shot-{index}", ((index - 1) % 4) + 1) for index in range(1, 7)]
    for shot in shots:
        shot.camera_angle = None
        shot.video_url = None
        shot.video_status = "pending"
        shot.dialogue = ""
        shot.prompt = "普通镜头"
        shot.visual_description = "普通画面"
        shot.extra_data = {"episode_number": shot.extra_data["episode_number"]}

    blocker = anchor_coverage_blocker(recommend_anchor_shots(shots, mode="full"), mode="full")

    assert blocker["code"] == "insufficient_anchor_coverage"
    assert {"style_cinematography", "voice_dialogue", "delivery_integrity", "narrative_truth"}.issubset(blocker["missing_dimensions"])
