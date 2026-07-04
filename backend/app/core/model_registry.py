"""
Unified model registry for novel-to-anime production tasks.

This module is the runtime authority for provider/model/task defaults. Database
LLMConfig rows still store user credentials and per-user settings.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


DASHSCOPE_VIDEO_SYNTHESIS_PATH = "/api/v1/services/aigc/video-generation/video-synthesis"
HAPPYHORSE_DURATIONS = list(range(3, 16))
HAPPYHORSE_RATIOS = ["16:9", "9:16", "3:4", "4:3", "4:5", "5:4", "1:1", "9:21", "21:9"]
SEEDANCE20_REFERENCE_PROTOCOL = {
    "provider": "volcano",
    "input_mode": "reference_images_text",
    "input_media_field": "content",
    "input_media_type": "reference_image",
    "prompt_reference_syntax": "@图{index}",
    "reference_image_range": [0, 9],
    "reference_video_range": [0, 3],
    "reference_audio_range": [0, 3],
}


def _happyhorse_model(
    variant: str,
    display_suffix: str,
    capabilities: List[str],
    input_mode: str,
    input_media_type: Optional[str],
    reference_image_range: List[int],
    priority: int,
    aliases: Optional[List[str]] = None,
) -> Dict[str, Any]:
    reference_images = reference_image_range[1]
    protocol: Dict[str, Any] = {
        "provider": "dashscope",
        "endpoint_path": DASHSCOPE_VIDEO_SYNTHESIS_PATH,
        "method": "POST",
        "auth_header": "Authorization: Bearer <api_key>",
        "async_header": {"X-DashScope-Async": "enable"},
        "request_model_field": "model",
        "input_mode": input_mode,
        "reference_image_range": reference_image_range,
    }
    if input_media_type:
        protocol.update({
            "input_media_field": "input.media",
            "input_media_type": input_media_type,
        })
    if input_media_type == "reference_image":
        protocol["prompt_reference_syntax"] = "[Image {index}]"

    return {
        "id": f"alibaba.happyhorse.1_1_{variant}",
        "provider_id": "alibaba",
        "api_model_id": f"happyhorse-1.1-{variant}",
        "display_name": f"HappyHorse-1.1 {display_suffix}",
        "modality": "video",
        "capabilities": capabilities,
        "endpoint_key": "video_generation",
        "limits": {
            "durations": HAPPYHORSE_DURATIONS,
            "resolutions": ["720P", "1080P"],
            "ratios": HAPPYHORSE_RATIOS,
            "reference_images": reference_images,
            "reference_videos": 0,
            "reference_audios": 0,
            "supports_at_reference": input_media_type == "reference_image",
            "native_audio": False,
        },
        "protocol": protocol,
        "routing": {"lane": "premium", "priority": priority},
        "aliases": aliases or [],
        "status": {"active": True, "recommended": True, "verified": False},
    }


HAPPYHORSE_VIDEO_MODELS = [
    _happyhorse_model(
        "r2v",
        "R2V",
        ["text_to_video", "reference_to_video", "image_to_video", "shot_video", "character_consistency"],
        "reference_images_text",
        "reference_image",
        [1, 9],
        20,
        ["alibaba.happyhorse.1_1", "HappyHorse-1.1", "happyhorse_1_1", "happyhorse-1.1"],
    ),
    _happyhorse_model(
        "i2v",
        "I2V",
        ["text_to_video", "first_frame_image_to_video", "image_to_video", "shot_video"],
        "image_text",
        "first_frame_image",
        [1, 1],
        21,
        ["HappyHorse-1.1-I2V", "happyhorse_1_1_i2v"],
    ),
    _happyhorse_model(
        "t2v",
        "T2V",
        ["text_to_video", "shot_video"],
        "text",
        None,
        [0, 0],
        22,
        ["HappyHorse-1.1-T2V", "happyhorse_1_1_t2v"],
    ),
]


PROVIDERS: List[Dict[str, Any]] = [
    {
        "id": "volcano",
        "display_name": "火山引擎",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "auth_type": "bearer",
        "endpoints": {
            "chat": "/chat/completions",
            "image_generation": "/images/generations",
            "video_generation": "/contents/generations/tasks",
            "tts": "/audio/speech",
        },
    },
    {
        "id": "dashscope",
        "display_name": "阿里 DashScope",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "auth_type": "bearer",
        "endpoints": {"chat": "/chat/completions"},
    },
    {
        "id": "qianlian",
        "display_name": "阿里百炼",
        "base_url": "https://coding.dashscope.aliyuncs.com/apps/anthropic/v1",
        "auth_type": "bearer",
        "endpoints": {"chat": "/messages"},
    },
    {
        "id": "alibaba",
        "display_name": "阿里视频",
        "base_url": "https://dashscope.aliyuncs.com",
        "auth_type": "bearer",
        "endpoints": {"video_generation": DASHSCOPE_VIDEO_SYNTHESIS_PATH},
    },
    {
        "id": "kling",
        "display_name": "可灵",
        "base_url": "https://api.klingai.com",
        "auth_type": "bearer",
        "endpoints": {"video_generation": "/v1/videos/generations"},
    },
    {
        "id": "pixverse",
        "display_name": "PixVerse / 拍我",
        "base_url": "https://app-api.pixverse.ai/openapi/v2",
        "auth_type": "bearer",
        "endpoints": {"video_generation": "/video"},
    },
    {
        "id": "minimax",
        "display_name": "MiniMax",
        "base_url": "https://api.minimaxi.com/v1",
        "auth_type": "bearer",
        "endpoints": {"chat": "/text/chatcompletion_v2", "tts": "/t2a_v2"},
    },
    {
        "id": "openai",
        "display_name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "auth_type": "bearer",
        "endpoints": {
            "chat": "/chat/completions",
            "image_generation": "/images/generations",
            "video_generation": "/videos",
        },
    },
    {
        "id": "google",
        "display_name": "Google Vertex AI",
        "base_url": "https://aiplatform.googleapis.com",
        "auth_type": "oauth",
        "endpoints": {"video_generation": "/v1/projects/{project}/locations/{location}/publishers/google/models"},
    },
    {
        "id": "local",
        "display_name": "本地执行器",
        "base_url": "",
        "auth_type": "none",
        "endpoints": {"local_synthesis": "ffmpeg"},
    },
    {
        "id": "comfyui",
        "display_name": "ComfyUI",
        "base_url": "http://127.0.0.1:8188",
        "auth_type": "none",
        "endpoints": {"workflow_submit": "/prompt", "health": "/system_stats"},
    },
    {
        "id": "ffmpeg_cloud",
        "display_name": "FFmpeg 云渲染",
        "base_url": "",
        "auth_type": "bearer",
        "endpoints": {"render": "/render", "health": "/health"},
    },
    {
        "id": "lip_sync",
        "display_name": "口型/唇形适配器",
        "base_url": "",
        "auth_type": "bearer",
        "endpoints": {"lip_sync": "/lip-sync", "health": "/health"},
    },
]


MODELS: List[Dict[str, Any]] = [
    {
        "id": "volcano.doubao.seed_1_8",
        "provider_id": "volcano",
        "api_model_id": "doubao-seed-1-8-251228",
        "display_name": "豆包 Seed 1.8",
        "modality": "text",
        "capabilities": ["chat", "text_generation", "json_mode", "structured_output"],
        "endpoint_key": "chat",
        "limits": {"context_window": 4096, "max_output_tokens": 2048},
        "status": {"active": True, "recommended": True, "verified": False},
    },
    {
        "id": "dashscope.qwen_plus",
        "provider_id": "dashscope",
        "api_model_id": "qwen-plus",
        "display_name": "通义千问 Plus",
        "modality": "text",
        "capabilities": ["chat", "text_generation", "json_mode", "structured_output"],
        "endpoint_key": "chat",
        "limits": {"context_window": 32768, "max_output_tokens": 8192},
        "status": {"active": True, "recommended": True, "verified": False},
    },
    {
        "id": "qianlian.qwen_3_5_plus",
        "provider_id": "qianlian",
        "api_model_id": "qwen3.5-plus",
        "display_name": "百炼 千问 3.5 Plus",
        "modality": "text",
        "capabilities": ["chat", "text_generation", "vision", "structured_output"],
        "endpoint_key": "chat",
        "limits": {"context_window": 32768, "max_output_tokens": 4096},
        "status": {"active": True, "recommended": True, "verified": False},
    },
    {
        "id": "dashscope.qwen_long",
        "provider_id": "dashscope",
        "api_model_id": "qwen-long",
        "display_name": "通义千问 Long",
        "modality": "text",
        "capabilities": ["chat", "text_generation", "long_context"],
        "endpoint_key": "chat",
        "limits": {"context_window": 1_000_000, "max_output_tokens": 8192},
        "status": {"active": True, "recommended": True, "verified": False},
    },
    {
        "id": "volcano.seedream.4_5",
        "provider_id": "volcano",
        "api_model_id": "ep-20260320112226-rgndq",
        "display_name": "豆包 Seedream 4.5",
        "modality": "image",
        "capabilities": ["text_to_image", "image_to_image", "character_reference", "scene_reference"],
        "endpoint_key": "image_generation",
        "limits": {"ratios": ["16:9", "9:16", "1:1"], "sizes": ["720p", "1080p"]},
        "status": {"active": True, "recommended": True, "verified": False},
    },
    {
        "id": "volcano.seedance.1_0_pro_fast",
        "provider_id": "volcano",
        "api_model_id": "Doubao-Seedance-1.0-pro-fast",
        "display_name": "豆包 Seedance 1.0 Pro Fast",
        "modality": "video",
        "capabilities": ["text_to_video", "image_to_video", "shot_video"],
        "endpoint_key": "video_generation",
        "limits": {
            "durations": [4, 5, 8, 10],
            "resolutions": ["480p", "720p", "1080p"],
            "reference_images": 1,
            "reference_videos": 0,
            "reference_audios": 0,
            "supports_at_reference": False,
            "native_audio": False,
        },
        "status": {"active": True, "recommended": True, "verified": False},
    },
    {
        "id": "volcano.seedance.2_0",
        "provider_id": "volcano",
        "api_model_id": "doubao-seedance-2-0-260128",
        "display_name": "豆包 Seedance 2.0",
        "modality": "video",
        "capabilities": ["text_to_video", "image_to_video", "shot_video"],
        "endpoint_key": "video_generation",
        "limits": {
            "durations": [4, 5, 8, 10, 15],
            "resolutions": ["480p", "720p"],
            "reference_images": 9,
            "reference_videos": 3,
            "reference_audios": 3,
            "supports_at_reference": True,
            "native_audio": True,
        },
        "protocol": SEEDANCE20_REFERENCE_PROTOCOL,
        "routing": {"lane": "recommended", "priority": 10},
        "aliases": ["doubao-seedance-2.0", "Doubao-Seedance-2.0"],
        "status": {"active": True, "recommended": True, "verified": False},
    },
    {
        "id": "volcano.seedance.2_0_fast",
        "provider_id": "volcano",
        "api_model_id": "doubao-seedance-2-0-fast-260128",
        "display_name": "豆包 Seedance 2.0 Fast",
        "modality": "video",
        "capabilities": ["text_to_video", "image_to_video", "shot_video"],
        "endpoint_key": "video_generation",
        "limits": {
            "durations": [4, 5, 8, 10, 15],
            "resolutions": ["480p", "720p"],
            "reference_images": 9,
            "reference_videos": 3,
            "reference_audios": 3,
            "supports_at_reference": True,
            "native_audio": True,
        },
        "protocol": SEEDANCE20_REFERENCE_PROTOCOL,
        "routing": {"lane": "fast_preview", "priority": 90},
        "aliases": ["doubao-seedance-2.0-fast", "Doubao-Seedance-2.0-fast"],
        "status": {"active": True, "recommended": True, "verified": False},
    },
    *HAPPYHORSE_VIDEO_MODELS,
    {
        "id": "kling.3_0_omni",
        "provider_id": "kling",
        "api_model_id": "kling-v3-omni",
        "display_name": "可灵 3.0 Omni",
        "modality": "video",
        "capabilities": [
            "text_to_video",
            "image_to_video",
            "shot_video",
            "multi_shot_story",
            "character_consistency",
            "native_audio",
        ],
        "endpoint_key": "video_generation",
        "limits": {
            "durations": [3, 5, 8, 10, 15],
            "resolutions": ["720p", "1080p"],
            "reference_images": 8,
            "reference_videos": 2,
            "reference_audios": 2,
            "supports_at_reference": True,
            "native_audio": True,
        },
        "routing": {"lane": "premium", "priority": 30},
        "aliases": ["Kling-3.0-Omni", "kling-3.0-omni"],
        "status": {"active": True, "recommended": True, "verified": False},
    },
    {
        "id": "pixverse.c1",
        "provider_id": "pixverse",
        "api_model_id": "pixverse-c1",
        "display_name": "PixVerse C1",
        "modality": "video",
        "capabilities": [
            "text_to_video",
            "image_to_video",
            "shot_video",
            "anime_action",
            "vfx",
            "storyboard_to_video",
        ],
        "endpoint_key": "video_generation",
        "limits": {
            "durations": [5, 8, 10],
            "resolutions": ["720p", "1080p"],
            "reference_images": 9,
            "reference_videos": 1,
            "reference_audios": 1,
            "supports_at_reference": True,
            "native_audio": False,
        },
        "routing": {"lane": "specialist", "priority": 40},
        "aliases": ["PixVerse-C1", "pixverse_c1"],
        "status": {"active": True, "recommended": True, "verified": False},
    },
    {
        "id": "volcano.seedance.1_5_pro",
        "provider_id": "volcano",
        "api_model_id": "doubao-seedance-1-5-pro-251215",
        "display_name": "豆包 Seedance 1.5 Pro",
        "modality": "video",
        "capabilities": ["text_to_video", "image_to_video", "shot_video"],
        "endpoint_key": "video_generation",
        "limits": {
            "durations": [4, 8, 10],
            "resolutions": ["480p", "720p", "1080p"],
            "reference_images": 1,
            "reference_videos": 0,
            "reference_audios": 0,
            "supports_at_reference": False,
            "native_audio": False,
        },
        "routing": {"lane": "compatible", "priority": 70},
        "aliases": ["doubao-seedance-1.5-pro", "Doubao-Seedance-1.5-pro"],
        "status": {"active": True, "recommended": False, "verified": False},
    },
    {
        "id": "kling.v2_6",
        "provider_id": "kling",
        "api_model_id": "kling-v2-6",
        "display_name": "可灵 V2.6",
        "modality": "video",
        "capabilities": ["text_to_video", "image_to_video", "shot_video", "native_audio"],
        "endpoint_key": "video_generation",
        "limits": {
            "durations": [5, 10],
            "resolutions": ["720p", "1080p"],
            "reference_images": 2,
            "reference_videos": 0,
            "reference_audios": 1,
            "supports_at_reference": False,
            "native_audio": True,
        },
        "routing": {"lane": "compatible", "priority": 80},
        "aliases": ["Kling-V2-6", "kling-v2.6"],
        "status": {"active": True, "recommended": False, "verified": False},
    },
    {
        "id": "kling.o1",
        "provider_id": "kling",
        "api_model_id": "kling-o1",
        "display_name": "可灵 O1",
        "modality": "video",
        "capabilities": [
            "text_to_video",
            "image_to_video",
            "shot_video",
            "multimodal_reference",
            "video_editing",
        ],
        "endpoint_key": "video_generation",
        "limits": {
            "durations": [5, 10],
            "resolutions": ["720p", "1080p"],
            "reference_images": 6,
            "reference_videos": 1,
            "reference_audios": 0,
            "supports_at_reference": True,
            "native_audio": False,
        },
        "routing": {"lane": "compatible", "priority": 85},
        "aliases": ["Kling-O1", "kling_o1"],
        "status": {"active": True, "recommended": False, "verified": False},
    },
    {
        "id": "openai.sora_2",
        "provider_id": "openai",
        "api_model_id": "sora-2",
        "display_name": "OpenAI Sora 2",
        "modality": "audio_video",
        "capabilities": [
            "text_to_audio_video",
            "image_to_audio_video",
            "dialogue_audio",
            "sound_effect_generation",
            "subtitle_timing",
            "shot_audio_video",
        ],
        "endpoint_key": "video_generation",
        "limits": {"durations": [4, 8, 10, 12], "resolutions": ["720p", "1080p"]},
        "status": {"active": True, "recommended": False, "verified": False},
    },
    {
        "id": "google.veo_3",
        "provider_id": "google",
        "api_model_id": "veo-3.0-generate",
        "display_name": "Google Veo 3",
        "modality": "audio_video",
        "capabilities": [
            "text_to_audio_video",
            "image_to_audio_video",
            "dialogue_audio",
            "sound_effect_generation",
            "subtitle_timing",
            "shot_audio_video",
        ],
        "endpoint_key": "video_generation",
        "limits": {"durations": [8], "resolutions": ["720p", "1080p"]},
        "status": {"active": True, "recommended": False, "verified": False},
    },
    {
        "id": "minimax.speech_02_hd",
        "provider_id": "minimax",
        "api_model_id": "speech-02-hd",
        "display_name": "MiniMax Speech 02 HD",
        "modality": "audio",
        "capabilities": ["text_to_speech", "dialogue_tts", "voice_consistency"],
        "endpoint_key": "tts",
        "limits": {"speed": {"min": 0.5, "max": 2.0}},
        "status": {"active": True, "recommended": True, "verified": False},
    },
    {
        "id": "minimax.m3",
        "provider_id": "minimax",
        "api_model_id": "MiniMax-M3",
        "display_name": "MiniMax M3",
        "modality": "text",
        "capabilities": ["chat", "text_generation", "json_mode", "structured_output", "vision", "multimodal", "long_context"],
        "endpoint_key": "chat",
        "limits": {"context_window": 1_000_000, "max_output_tokens": 8192},
        "status": {"active": True, "recommended": True, "verified": False},
    },
    {
        "id": "local.subtitle_exporter",
        "provider_id": "local",
        "api_model_id": "subtitle-exporter",
        "display_name": "本地字幕导出器",
        "modality": "subtitle",
        "capabilities": ["subtitle_generation", "subtitle_timing", "srt_export", "vtt_export", "ass_export"],
        "endpoint_key": "local_synthesis",
        "limits": {},
        "status": {"active": True, "recommended": True, "verified": False},
    },
    {
        "id": "local.ffmpeg",
        "provider_id": "local",
        "api_model_id": "ffmpeg",
        "display_name": "本地 FFmpeg 合成",
        "modality": "video",
        "capabilities": ["audio_video_mux", "timeline_export", "subtitle_burn_in"],
        "endpoint_key": "local_synthesis",
        "limits": {},
        "status": {"active": True, "recommended": True, "verified": False},
    },
    {
        "id": "comfyui.workflow_adapter",
        "provider_id": "comfyui",
        "api_model_id": "workflow-json",
        "display_name": "ComfyUI Workflow Adapter",
        "modality": "workflow",
        "capabilities": [
            "workflow_json",
            "controlnet",
            "ip_adapter",
            "animatediff",
            "multi_reference",
            "shot_video",
            "reference_image_count",
        ],
        "endpoint_key": "workflow_submit",
        "limits": {"reference_image_count": {"min": 0, "max": 8}},
        "status": {"active": True, "recommended": False, "verified": False},
    },
    {
        "id": "ffmpeg.cloud_renderer",
        "provider_id": "ffmpeg_cloud",
        "api_model_id": "ffmpeg-cloud-renderer",
        "display_name": "FFmpeg Cloud Renderer",
        "modality": "render",
        "capabilities": ["timeline_render", "subtitle_burn_in", "audio_video_mux", "render_package"],
        "endpoint_key": "render",
        "limits": {},
        "status": {"active": True, "recommended": False, "verified": False},
    },
    {
        "id": "generic.lip_sync",
        "provider_id": "lip_sync",
        "api_model_id": "generic-lip-sync",
        "display_name": "Generic Lip Sync Adapter",
        "modality": "video",
        "capabilities": ["lip_sync", "audio_driven_video", "avatar_animation", "mouth_cue_export"],
        "endpoint_key": "lip_sync",
        "limits": {},
        "status": {"active": True, "recommended": False, "verified": False},
    },
]


TASK_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "chapter_writing": {
        "display_name": "章节写作",
        "required_capabilities": ["text_generation", "long_context"],
        "default_model_id": "dashscope.qwen_long",
        "fallback_model_ids": ["dashscope.qwen_plus", "qianlian.qwen_3_5_plus", "volcano.doubao.seed_1_8"],
    },
    "novel_generation": {
        "display_name": "小说生成",
        "required_capabilities": ["text_generation", "long_context"],
        "default_model_id": "dashscope.qwen_long",
        "fallback_model_ids": ["dashscope.qwen_plus", "qianlian.qwen_3_5_plus", "volcano.doubao.seed_1_8"],
    },
    "script_generation": {
        "display_name": "剧本改编",
        "required_capabilities": ["text_generation", "structured_output"],
        "default_model_id": "dashscope.qwen_plus",
        "fallback_model_ids": ["qianlian.qwen_3_5_plus", "volcano.doubao.seed_1_8"],
    },
    "storyboard_generation": {
        "display_name": "分镜生成",
        "required_capabilities": ["json_mode", "structured_output"],
        "default_model_id": "dashscope.qwen_plus",
        "fallback_model_ids": ["qianlian.qwen_3_5_plus", "volcano.doubao.seed_1_8"],
    },
    "character_image": {
        "display_name": "角色定稿图",
        "required_capabilities": ["text_to_image", "character_reference"],
        "default_model_id": "volcano.seedream.4_5",
        "fallback_model_ids": [],
    },
    "scene_reference_image": {
        "display_name": "场景参考图",
        "required_capabilities": ["text_to_image", "scene_reference"],
        "default_model_id": "volcano.seedream.4_5",
        "fallback_model_ids": [],
    },
    "shot_video": {
        "display_name": "镜头视频",
        "required_capabilities": ["image_to_video", "text_to_video"],
        "default_model_id": "volcano.seedance.2_0",
        "fallback_model_ids": [
            "alibaba.happyhorse.1_1_r2v",
            "alibaba.happyhorse.1_1_i2v",
            "alibaba.happyhorse.1_1_t2v",
            "kling.3_0_omni",
            "pixverse.c1",
            "volcano.seedance.1_5_pro",
            "kling.v2_6",
            "kling.o1",
        ],
    },
    "shot_audio_video": {
        "display_name": "镜头音视频直生",
        "required_capabilities": ["text_to_audio_video", "shot_audio_video"],
        "default_model_id": "openai.sora_2",
        "fallback_model_ids": ["google.veo_3", "volcano.seedance.2_0_fast", "volcano.seedance.2_0", "volcano.seedance.1_0_pro_fast"],
    },
    "tts_dialogue": {
        "display_name": "角色配音",
        "required_capabilities": ["text_to_speech", "dialogue_tts", "voice_consistency"],
        "default_model_id": "minimax.speech_02_hd",
        "fallback_model_ids": [],
    },
    "final_synthesis": {
        "display_name": "成片合成",
        "required_capabilities": ["audio_video_mux", "timeline_export"],
        "default_model_id": "local.ffmpeg",
        "fallback_model_ids": [],
    },
    "subtitle_generation": {
        "display_name": "字幕轨生成",
        "required_capabilities": ["subtitle_generation", "subtitle_timing"],
        "default_model_id": "local.subtitle_exporter",
        "fallback_model_ids": [],
    },
    "comfyui_workflow": {
        "display_name": "ComfyUI 工作流生成",
        "required_capabilities": ["workflow_json"],
        "default_model_id": "comfyui.workflow_adapter",
        "fallback_model_ids": ["volcano.seedance.2_0_fast", "volcano.seedance.2_0", "volcano.seedance.1_0_pro_fast"],
    },
    "lip_sync_video": {
        "display_name": "口型/唇形视频",
        "required_capabilities": ["lip_sync", "audio_driven_video"],
        "default_model_id": "generic.lip_sync",
        "fallback_model_ids": [],
    },
    "cloud_render": {
        "display_name": "云渲染执行",
        "required_capabilities": ["timeline_render", "render_package"],
        "default_model_id": "ffmpeg.cloud_renderer",
        "fallback_model_ids": ["local.ffmpeg"],
    },
}


def get_provider(provider_id: str) -> Optional[Dict[str, Any]]:
    return next((provider for provider in PROVIDERS if provider["id"] == provider_id), None)


def get_model(model_id: str) -> Optional[Dict[str, Any]]:
    return next((model for model in MODELS if model["id"] == model_id), None)


def find_model(model_id_or_api_id: str) -> Optional[Dict[str, Any]]:
    model_key = (model_id_or_api_id or "").strip()
    if not model_key:
        return None
    return next(
        (
            model
            for model in MODELS
            if model.get("id") == model_key
            or model.get("api_model_id") == model_key
            or model_key in (model.get("aliases") or [])
        ),
        None,
    )


def get_model_generation_limits(model_id_or_api_id: str) -> Dict[str, Any]:
    model = find_model(model_id_or_api_id)
    limits = model.get("limits") if model and isinstance(model.get("limits"), dict) else {}
    return dict(limits)


def get_model_reference_limits(model_id_or_api_id: str) -> Dict[str, Any]:
    """Return multimodal reference limits for a registered model.

    Unknown models intentionally fall back to the legacy single-image behavior.
    """
    default_limits = {
        "images": 1,
        "videos": 0,
        "audios": 0,
        "at_reference": False,
        "native_audio": False,
    }
    model = find_model(model_id_or_api_id)
    if not model:
        return dict(default_limits)

    limits = model.get("limits") if isinstance(model.get("limits"), dict) else {}
    return {
        "images": int(limits.get("reference_images", default_limits["images"]) or 0),
        "videos": int(limits.get("reference_videos", default_limits["videos"]) or 0),
        "audios": int(limits.get("reference_audios", default_limits["audios"]) or 0),
        "at_reference": bool(limits.get("supports_at_reference", default_limits["at_reference"])),
        "native_audio": bool(limits.get("native_audio", default_limits["native_audio"])),
    }


def get_task_default(task: str) -> Optional[Dict[str, Any]]:
    default = TASK_DEFAULTS.get(task)
    if not default:
        return None
    return {"task": task, **default, "default_model": get_model(default["default_model_id"])}


def get_video_model_catalog(task: str = "shot_video") -> Dict[str, Any]:
    task_default = get_task_default(task)
    if not task_default:
        return {"task": task, "default_model_id": None, "models": []}

    ordered_ids: List[str] = []
    for model_id in [task_default["default_model_id"], *task_default.get("fallback_model_ids", [])]:
        if model_id and model_id not in ordered_ids:
            ordered_ids.append(model_id)

    models = []
    for model_id in ordered_ids:
        model = get_model(model_id)
        if not model:
            continue
        status_info = model.get("status") if isinstance(model.get("status"), dict) else {}
        if status_info.get("active") is False or model.get("modality") != "video":
            continue
        models.append(model)

    return {
        "task": task,
        "display_name": task_default.get("display_name"),
        "required_capabilities": task_default.get("required_capabilities", []),
        "default_model_id": task_default["default_model_id"],
        "models": models,
    }


def get_registry() -> Dict[str, Any]:
    return {
        "providers": PROVIDERS,
        "models": MODELS,
        "task_defaults": [get_task_default(task) for task in TASK_DEFAULTS],
    }
