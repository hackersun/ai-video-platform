from app.features.model_config.prompt_usage_contract import (
    PROMPT_USAGE_GROUPS,
    PROMPT_USAGE_STATUS_LABELS,
    prompt_usage_stage,
    prompt_usage_stages,
)


def test_prompt_usage_registry_covers_the_ordered_production_chain():
    assert [stage.id for stage in prompt_usage_stages()] == [
        "chapter_writing",
        "character_extraction",
        "scene_prop_extraction",
        "script_generation",
        "storyboard_generation",
        "character_image",
        "scene_reference_image",
        "prop_image",
        "shot_video",
        "tts_dialogue",
        "subtitle",
        "synthesis",
    ]
    assert [group.name for group in PROMPT_USAGE_GROUPS] == [
        "故事开发",
        "内容制作",
        "视觉生产",
        "声音与交付",
    ]


def test_prompt_usage_registry_exposes_the_runtime_contracts():
    assert prompt_usage_stage("character_extraction").output_contract == "json_array"
    assert prompt_usage_stage("scene_prop_extraction").prompt_task == "entity_extraction"
    assert prompt_usage_stage("character_image").model_task == "shot_image"
    assert prompt_usage_stage("shot_video").capability == "video_generation"
    assert prompt_usage_stage("tts_dialogue").model_task == "shot_speech"


def test_non_prompt_stages_are_explicitly_not_applicable():
    assert prompt_usage_stage("subtitle").uses_prompt is False
    assert prompt_usage_stage("subtitle").model_task is None
    assert prompt_usage_stage("synthesis").uses_prompt is False
    assert prompt_usage_stage("synthesis").prompt_task is None


def test_prompt_usage_statuses_have_operator_facing_chinese_labels():
    assert PROMPT_USAGE_STATUS_LABELS == {
        "effective": "当前生效",
        "overridden": "模型专用覆盖",
        "internal_fallback": "内置兜底",
        "invalid_binding": "模型配置异常",
        "not_applicable": "无需提示词",
    }
