from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image


def _write_image(path: Path, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (24, 24), color).save(path)


def test_local_visual_similarity_scores_identical_images_high(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from app.services import visual_similarity_adapter as adapter

    static_root = tmp_path / "static"
    monkeypatch.setattr(adapter, "STATIC_ROOT", static_root)
    _write_image(static_root / "refs" / "front.png", (120, 40, 80))
    _write_image(static_root / "frames" / "one.png", (120, 40, 80))

    result = adapter.score_local_visual_similarity(
        reference_url="/static/refs/front.png",
        frame_urls=["/static/frames/one.png"],
    )

    assert result is not None
    assert result["score"] == 100
    assert result["method"] == "local_rgb_mean_absolute_difference"
    assert result["model"] == "local-image-rgb"
    assert result["frame_count"] == 1
    assert result["frame_scores"] == [100]


def test_local_visual_similarity_averages_frame_scores(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from app.services import visual_similarity_adapter as adapter

    static_root = tmp_path / "static"
    monkeypatch.setattr(adapter, "STATIC_ROOT", static_root)
    _write_image(static_root / "refs" / "front.png", (255, 255, 255))
    _write_image(static_root / "frames" / "matching.png", (255, 255, 255))
    _write_image(static_root / "frames" / "drift.png", (0, 0, 0))

    result = adapter.score_local_visual_similarity(
        reference_url="/static/refs/front.png",
        frame_urls=["/static/frames/matching.png", "/static/frames/drift.png"],
    )

    assert result is not None
    assert result["score"] == 50
    assert result["frame_scores"] == [100, 0]


def test_local_visual_similarity_skips_remote_or_missing_inputs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from app.services import visual_similarity_adapter as adapter

    monkeypatch.setattr(adapter, "STATIC_ROOT", tmp_path / "static")

    assert adapter.score_local_visual_similarity(
        reference_url="https://cdn.example.com/front.png",
        frame_urls=["/static/frames/one.jpg"],
    ) is None
    assert adapter.score_local_visual_similarity(
        reference_url="/static/refs/missing.png",
        frame_urls=["/static/frames/missing.jpg"],
    ) is None
