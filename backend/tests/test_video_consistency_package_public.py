from __future__ import annotations


def test_video_consistency_package_has_dependency_safe_public_owner() -> None:
    from app.features.video_generation.public import (
        VideoConsistencyPackageContext,
        build_video_consistency_package,
        collect_character_multiview_refs,
        derive_stable_seed,
        extract_shot_generation_context,
    )

    assert VideoConsistencyPackageContext.__module__.startswith(
        "app.features.video_generation"
    )
    assert build_video_consistency_package.__module__.startswith(
        "app.features.video_generation"
    )
    assert collect_character_multiview_refs.__module__.startswith(
        "app.features.video_generation"
    )
    assert derive_stable_seed(["novel", "chapter"]) == derive_stable_seed(
        ["novel", "chapter"]
    )
    assert extract_shot_generation_context(None) == {
        "character_refs": [],
        "scene_refs": [],
        "prop_refs": [],
        "event_refs": [],
        "environment_context": None,
        "subtitle_text": None,
    }
