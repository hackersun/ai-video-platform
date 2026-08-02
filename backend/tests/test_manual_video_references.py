import pytest

from app.features.video_generation.application.manual_references import (
    build_manual_reference_package,
    merge_reference_packages,
)
from app.features.video_generation.errors import VideoGenerationError


def test_manual_reference_package_accepts_public_multimodal_urls() -> None:
    package = build_manual_reference_package(
        image_urls=["https://cdn.example.com/character.png"],
        video_urls=["https://cdn.example.com/motion.mp4"],
        audio_urls=["https://cdn.example.com/voice.wav"],
        limits={"images": 2, "videos": 1, "audios": 1},
    )

    assert [item["url"] for item in package["images"]] == ["https://cdn.example.com/character.png"]
    assert [item["url"] for item in package["videos"]] == ["https://cdn.example.com/motion.mp4"]
    assert [item["url"] for item in package["audios"]] == ["https://cdn.example.com/voice.wav"]


@pytest.mark.parametrize(
    "urls",
    [["http://127.0.0.1/private.png"], ["data:image/png;base64,abc"]],
)
def test_manual_reference_package_rejects_non_public_urls(urls: list[str]) -> None:
    with pytest.raises(VideoGenerationError, match="公网"):
        build_manual_reference_package(
            image_urls=urls, video_urls=[], audio_urls=[],
            limits={"images": 2, "videos": 1, "audios": 1},
        )


def test_manual_reference_package_rejects_count_over_model_limit() -> None:
    with pytest.raises(VideoGenerationError, match="最多 1 个视频参考"):
        build_manual_reference_package(
            image_urls=[],
            video_urls=["https://cdn.example.com/a.mp4", "https://cdn.example.com/b.mp4"],
            audio_urls=[],
            limits={"images": 2, "videos": 1, "audios": 1},
        )


def test_manual_references_fill_after_canonical_assets_without_duplicates() -> None:
    merged = merge_reference_packages(
        {"images": [{"url": "https://cdn.example.com/locked.png", "canonical_asset_id": "asset-1"}]},
        {
            "images": [
                {"url": "https://cdn.example.com/locked.png"},
                {"url": "https://cdn.example.com/manual.png"},
            ],
            "videos": [{"url": "https://cdn.example.com/motion.mp4"}],
        },
    )

    assert [item["url"] for item in merged["images"]] == [
        "https://cdn.example.com/locked.png", "https://cdn.example.com/manual.png",
    ]
    assert merged["videos"][0]["url"] == "https://cdn.example.com/motion.mp4"


def test_merge_reference_packages_rejects_total_over_model_limit() -> None:
    with pytest.raises(VideoGenerationError, match="自动资产参考已占用"):
        merge_reference_packages(
            {"images": [{"url": "https://cdn.example.com/locked.png"}]},
            {"images": [{"url": "https://cdn.example.com/manual.png"}]},
            limits={"images": 1},
        )
