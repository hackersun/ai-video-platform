from __future__ import annotations

from pathlib import Path

from app.services.generated_artifact_policy import classify_generated_artifact


def test_runtime_generated_media_is_ignored() -> None:
    assert classify_generated_artifact(Path("backend/static/dev/audio-1.mp3")).bucket == "runtime_generated"
    assert classify_generated_artifact(Path("backend/static/generated/images/shot.png")).bucket == "runtime_generated"
    assert classify_generated_artifact(Path("backend/static/generated/videos/shot.mp4")).bucket == "runtime_generated"
    assert classify_generated_artifact(Path("backend/static/exports/final.json")).bucket == "runtime_generated"


def test_manual_acceptance_outputs_are_ignored() -> None:
    result = classify_generated_artifact(Path("output/playwright/manual-acceptance-20260706/result.json"))

    assert result.bucket == "acceptance_output"
    assert result.should_ignore is True


def test_seed_starter_assets_require_review_not_blanket_ignore() -> None:
    result = classify_generated_artifact(Path("backend/static/starter/style-cyber-anime.svg"))

    assert result.bucket == "seed_asset_review_required"
    assert result.should_ignore is False


def test_normalizes_parent_segments_before_classifying_seed_assets() -> None:
    result = classify_generated_artifact(Path("backend/static/generated/../starter/style.svg"))

    assert result.bucket == "seed_asset_review_required"
    assert result.should_ignore is False


def test_source_files_are_not_generated_artifacts() -> None:
    result = classify_generated_artifact(Path("backend/app/api/v1/endpoints/workflow.py"))

    assert result.bucket == "source"
    assert result.should_ignore is False
