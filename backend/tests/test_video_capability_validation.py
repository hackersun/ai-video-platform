import pytest

from app.features.video_generation.application.capability_validation import (
    reference_limits_from_contract,
    validate_video_generation_parameters,
)
from app.features.video_generation.errors import VideoGenerationError
from app.features.video_generation.schemas import VideoGenerateRequest


def test_video_parameters_allow_configured_seedance_25_duration() -> None:
    request = VideoGenerateRequest(prompt="连续漫剧镜头", duration=30, resolution="1080p")
    validate_video_generation_parameters(
        duration=request.duration,
        resolution=request.resolution,
        limits={"duration_min": 4, "duration_max": 30, "resolutions": ["720p", "1080p"]},
    )


@pytest.mark.parametrize(
    ("duration", "resolution", "message"),
    [(31, "1080p", "4–30 秒"), (8, "4k", "720p、1080p")],
)
def test_video_parameters_reject_values_outside_model_contract(
    duration: int, resolution: str, message: str,
) -> None:
    with pytest.raises(VideoGenerationError, match=message):
        validate_video_generation_parameters(
            duration=duration,
            resolution=resolution,
            limits={"duration_min": 4, "duration_max": 30, "resolutions": ["720p", "1080p"]},
        )


def test_reference_limits_use_persisted_model_contract_over_registry_fallback() -> None:
    assert reference_limits_from_contract(
        {
            "reference_images": 20, "reference_videos": 10,
            "reference_audios": 5, "native_audio": True,
        },
        {"images": 1, "videos": 0, "audios": 0, "native_audio": False},
    ) == {"images": 20, "videos": 10, "audios": 5, "native_audio": True}
