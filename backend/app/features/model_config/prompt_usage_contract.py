"""Stable production-stage contract for the Prompt Usage Map."""

from __future__ import annotations

from dataclasses import dataclass

from app.features.model_config.domain import ModelCapability


PROMPT_USAGE_STATUS_LABELS = {
    "effective": "当前生效",
    "overridden": "模型专用覆盖",
    "internal_fallback": "内置兜底",
    "invalid_binding": "模型配置异常",
    "not_applicable": "无需提示词",
}


@dataclass(frozen=True)
class PromptUsageStage:
    id: str
    name: str
    group_id: str
    prompt_task: str | None
    model_task: str | None
    capability: ModelCapability | None
    prompt_stage: str | None = None
    output_contract: str | None = None
    uses_prompt: bool = True


@dataclass(frozen=True)
class PromptUsageGroup:
    id: str
    name: str
    stage_ids: tuple[str, ...]


PROMPT_USAGE_GROUPS = (
    PromptUsageGroup(
        "story_development",
        "故事开发",
        ("chapter_writing", "character_extraction", "scene_prop_extraction"),
    ),
    PromptUsageGroup(
        "content_production",
        "内容制作",
        ("script_generation", "storyboard_generation"),
    ),
    PromptUsageGroup(
        "visual_production",
        "视觉生产",
        ("character_image", "scene_reference_image", "prop_image", "shot_video"),
    ),
    PromptUsageGroup(
        "audio_delivery",
        "声音与交付",
        ("tts_dialogue", "subtitle", "synthesis"),
    ),
)


_STAGES = (
    PromptUsageStage(
        "chapter_writing", "章节续写", "story_development",
        "chapter_writing", "script_generation", "text_generation",
    ),
    PromptUsageStage(
        "character_extraction", "角色提取", "story_development",
        "entity_extraction", "entity_extraction", "text_generation",
        prompt_stage="character", output_contract="json_array",
    ),
    PromptUsageStage(
        "scene_prop_extraction", "场景/道具提取", "story_development",
        "entity_extraction", "entity_extraction", "text_generation",
        prompt_stage="scene_prop", output_contract="json_array",
    ),
    PromptUsageStage(
        "script_generation", "剧本生成", "content_production",
        "script_generation", "script_generation", "text_generation",
    ),
    PromptUsageStage(
        "storyboard_generation", "分镜生成", "content_production",
        "storyboard_generation", "script_generation", "text_generation",
    ),
    PromptUsageStage(
        "character_image", "角色定稿图", "visual_production",
        "character_image", "shot_image", "image_generation",
    ),
    PromptUsageStage(
        "scene_reference_image", "场景参考图", "visual_production",
        "scene_reference_image", "shot_image", "image_generation",
    ),
    PromptUsageStage(
        "prop_image", "道具参考图", "visual_production",
        "prop_image", "shot_image", "image_generation",
    ),
    PromptUsageStage(
        "shot_video", "镜头视频", "visual_production",
        "shot_video", "shot_video", "video_generation",
    ),
    PromptUsageStage(
        "tts_dialogue", "对白配音", "audio_delivery",
        "tts_dialogue", "shot_speech", "speech_generation",
    ),
    PromptUsageStage(
        "subtitle", "字幕", "audio_delivery", None, None, None,
        uses_prompt=False,
    ),
    PromptUsageStage(
        "synthesis", "成片合成", "audio_delivery", None, None, None,
        uses_prompt=False,
    ),
)

_STAGES_BY_ID = {stage.id: stage for stage in _STAGES}


def prompt_usage_stages() -> tuple[PromptUsageStage, ...]:
    return _STAGES


def prompt_usage_stage(stage_id: str) -> PromptUsageStage:
    return _STAGES_BY_ID[stage_id]
