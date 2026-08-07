from app.features.model_config import ModelProfileContract  # noqa: F401 - primes model-driver imports
from app.features.model_drivers import VideoReference
from app.features.video_generation.application.driver_submission import build_video_command
from app.features.video_generation.schemas import VideoGenerateRequest


def test_video_command_preserves_reference_roles_and_legacy_url_groups() -> None:
    command = build_video_command(
        prompt="女孩从童年成长为掌门",
        content=[
            {"type": "image_url", "image_url": {"url": "https://cdn.test/first.png"}, "role": "first_frame"},
            {"type": "image_url", "image_url": {"url": "https://cdn.test/last.png"}, "role": "last_frame"},
            {"type": "video_url", "video_url": {"url": "https://cdn.test/motion.mp4"}, "role": "reference_video"},
            {"type": "audio_url", "audio_url": {"url": "https://cdn.test/voice.mp3"}, "role": "reference_audio"},
            {"type": "text", "text": "ignored duplicate prompt carrier"},
        ],
        params={"duration": 8, "resolution": "2K", "ratio": "adaptive"},
    )

    assert command.references == (
        VideoReference("image", "https://cdn.test/first.png", "first_frame"),
        VideoReference("image", "https://cdn.test/last.png", "last_frame"),
        VideoReference("video", "https://cdn.test/motion.mp4", "reference_video"),
        VideoReference("audio", "https://cdn.test/voice.mp3", "reference_audio"),
    )
    assert command.reference_images == (
        "https://cdn.test/first.png",
        "https://cdn.test/last.png",
    )
    assert command.reference_videos == ("https://cdn.test/motion.mp4",)
    assert command.reference_audios == ("https://cdn.test/voice.mp3",)


def test_video_request_accepts_h3_ratio_and_last_frame() -> None:
    request = VideoGenerateRequest(
        prompt="自然转场",
        ratio="adaptive",
        last_frame_image_url="https://cdn.test/last.png",
    )

    assert request.ratio == "adaptive"
    assert request.last_frame_image_url == "https://cdn.test/last.png"
