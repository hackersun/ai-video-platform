"""Stable cross-feature facade for video-generation kernels."""

from app.features.video_generation.application.consistency_package import (
    VideoConsistencyPackageContext,
    VideoConsistencyPackageError,
    build_video_consistency_package,
    collect_character_multiview_refs,
    derive_stable_seed,
    extract_shot_generation_context,
    json_dict,
    lookup_character_by_name,
)
from app.features.video_generation.application.job_sync import VideoJobSyncCommand, sync_video_job_and_shot
from app.features.video_generation.application.lineage import resolve_video_lineage
from app.features.video_generation.application.model_config import (
    get_video_model_name,
    resolve_video_job_client_config,
    resolve_video_model_config,
)
from app.features.video_generation.adapters.ark import (
    build_ark_video_create_kwargs,
    create_ark_client,
    submit_ark_video_task,
)
from app.features.video_generation.adapters.media_delivery import resolve_provider_image_delivery
from app.features.video_generation.constants import (
    MAX_PROVIDER_SEED,
    PROVIDER_VIDEO_WATERMARK_ARG,
    PROVIDER_VIDEO_WATERMARK_ENABLED,
    SEEDANCE_NATIVE_AUDIO_MODEL_IDS,
    VIDEO_MODEL_ID,
)
from app.features.video_generation.domain.provider_contract import (
    append_provider_image_note,
    provider_image_url_error_message,
    video_model_metadata,
    video_prompt_parameters,
)
from app.features.video_generation.domain.context_metadata import (
    build_video_context_metadata,
    build_video_extra_data,
    resolve_video_seed,
)
from app.features.video_generation.errors import VideoGenerationError
from app.features.video_generation.schemas import VideoGenerateRequest

__all__ = [
    "VideoConsistencyPackageContext",
    "VideoConsistencyPackageError",
    "build_video_consistency_package",
    "collect_character_multiview_refs",
    "derive_stable_seed",
    "extract_shot_generation_context",
    "json_dict",
    "lookup_character_by_name",
    "get_video_model_name",
    "MAX_PROVIDER_SEED",
    "PROVIDER_VIDEO_WATERMARK_ARG",
    "PROVIDER_VIDEO_WATERMARK_ENABLED",
    "SEEDANCE_NATIVE_AUDIO_MODEL_IDS",
    "VIDEO_MODEL_ID",
    "VideoGenerateRequest",
    "VideoGenerationError",
    "VideoJobSyncCommand",
    "append_provider_image_note",
    "build_video_context_metadata",
    "build_video_extra_data",
    "build_ark_video_create_kwargs",
    "create_ark_client",
    "provider_image_url_error_message",
    "resolve_provider_image_delivery",
    "resolve_video_lineage",
    "resolve_video_job_client_config",
    "resolve_video_model_config",
    "resolve_video_seed",
    "sync_video_job_and_shot",
    "submit_ark_video_task",
    "video_model_metadata",
    "video_prompt_parameters",
]
