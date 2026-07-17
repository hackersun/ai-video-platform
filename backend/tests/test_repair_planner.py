import pytest

from app.services.repair_planner import plan_minimal_repair


@pytest.mark.parametrize(
    ("issue", "expected_actions"),
    [
        ("wrong_voice", ("regenerate_tts", "rerun_lipsync", "rerender_audio")),
        ("wrong_speaker", ("regenerate_tts", "rerun_lipsync", "rerender_audio")),
        ("wrong_prop_state", ("regenerate_shot_video", "rerun_visual_review")),
        ("wrong_prop_owner", ("regenerate_shot_video", "rerun_visual_review")),
        ("subtitle_timing", ("retime_subtitles", "rerender_subtitles")),
        ("missing_subtitle", ("generate_subtitles", "rerender_subtitles")),
        ("corrupt_mp4", ("rerender_video", "validate_mp4")),
    ],
)
def test_plan_minimal_repair_maps_known_blocker_to_smallest_action_chain(
    issue: str,
    expected_actions: tuple[str, ...],
) -> None:
    plan = plan_minimal_repair(
        issue=issue,
        affected_artifact_ids=("artifact-b",),
        candidate_artifact_ids=("artifact-a", "artifact-b", "artifact-c"),
    )

    assert plan.issue_code == issue
    assert plan.actions == expected_actions
    assert plan.affected_artifact_ids == ("artifact-b",)
    assert plan.unchanged_artifact_ids == ("artifact-a", "artifact-c")


def test_unknown_blocker_uses_scoped_manual_review_without_regenerating_everything() -> None:
    plan = plan_minimal_repair(
        issue="provider_specific_temporal_defect",
        affected_artifact_ids=("artifact-b",),
        candidate_artifact_ids=("artifact-a", "artifact-b", "artifact-c"),
    )

    assert plan.actions == ("review_affected_artifact",)
    assert plan.affected_artifact_ids == ("artifact-b",)
    assert plan.unchanged_artifact_ids == ("artifact-a", "artifact-c")


def test_plan_rejects_affected_ids_outside_the_candidate_scope() -> None:
    with pytest.raises(ValueError, match="affected artifact IDs must belong"):
        plan_minimal_repair(
            issue="wrong_voice",
            affected_artifact_ids=("artifact-outside",),
            candidate_artifact_ids=("artifact-a", "artifact-b"),
        )


def test_plan_deduplicates_ids_without_changing_caller_order() -> None:
    plan = plan_minimal_repair(
        issue="subtitle_timing",
        affected_artifact_ids=("artifact-b", "artifact-b"),
        candidate_artifact_ids=("artifact-c", "artifact-b", "artifact-c", "artifact-a"),
    )

    assert plan.affected_artifact_ids == ("artifact-b",)
    assert plan.unchanged_artifact_ids == ("artifact-c", "artifact-a")
