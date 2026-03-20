"""
AI平台模型配置
定义各能力类型的默认模型
"""

from enum import Enum


class ModelCapability(str, Enum):
    """模型能力类型"""
    TEXT_GENERATION = "text-generation"      # 文本生成
    IMAGE_GENERATION = "image-generation"    # 图像生成
    VIDEO_GENERATION = "video-generation"    # 视频生成
    TTS = "tts"                             # 语音合成
    AUDIO_GENERATION = "audio-generation"   # 音频生成


# 服务商
class ModelProvider(str, Enum):
    VOLCANO = "volcano"     # 火山引擎
    QWEN = "qwen"           # 阿里千问
    BAIDU = "baidu"        # 百度文心


# 各能力默认模型配置
# 注意：
# - 千问 (qwen-long等) 通过 DashScope API: https://dashscope.aliyuncs.com
# - 百炼 (qwen3.5-plus等) 通过百炼 API: https://coding.dashscope.aliyuncs.com
# - 火山引擎 (豆包等) 通过 ARK API: https://ark.cn-beijing.volces.com
DEFAULT_MODEL_CONFIG = {
    ModelCapability.TEXT_GENERATION: {
        "provider": ModelProvider.QWEN,
        "model_id": "qwen-long",
        "model_name_cn": "千问Long",
        "platform": "dashscope",  # 千问/DashScope平台
        "description": "长文本生成，默认用于小说、剧本创作，支持百万token上下文"
    },
    ModelCapability.IMAGE_GENERATION: {
        "provider": ModelProvider.VOLCANO,
        "model_id": "Doubao-Seedream-4.5",
        "model_name_cn": "豆包Seedream-4.5",
        "platform": "volcano",  # 火山引擎平台
        "description": "高质量图像生成"
    },
    ModelCapability.VIDEO_GENERATION: {
        "provider": ModelProvider.VOLCANO,
        "model_id": "Doubao-Seed-2.0-pro",
        "model_name_cn": "豆包Seed-2.0-pro",
        "platform": "volcano",  # 火山引擎平台
        "description": "视频生成，支持4/8/10秒"
    },
    ModelCapability.TTS: {
        "provider": ModelProvider.VOLCANO,
        "model_id": "Doubao-Seedream-5.0-lite",
        "model_name_cn": "豆包Seedream-5.0-lite",
        "platform": "volcano",  # 火山引擎平台
        "description": "语音合成"
    }
}


def get_default_model(capability: ModelCapability) -> dict:
    """获取指定能力的默认模型"""
    return DEFAULT_MODEL_CONFIG.get(capability, {})


def get_text_generation_model() -> dict:
    """获取文本生成默认模型"""
    return get_default_model(ModelCapability.TEXT_GENERATION)


def get_image_generation_model() -> dict:
    """获取图像生成默认模型"""
    return get_default_model(ModelCapability.IMAGE_GENERATION)


def get_video_generation_model() -> dict:
    """获取视频生成默认模型"""
    config = get_default_model(ModelCapability.VIDEO_GENERATION)
    # 默认4秒
    return {**config, "default_duration": 4}


def get_tts_model() -> dict:
    """获取TTS默认模型"""
    return get_default_model(ModelCapability.TTS)


def get_video_duration_options() -> list:
    """获取视频时长选项"""
    return [
        {"value": 4, "label": "4秒", "description": "短视频片段"},
        {"value": 8, "label": "8秒", "description": "中等长度"},
        {"value": 10, "label": "10秒", "description": "较长视频"}
    ]


def get_image_size_options() -> list:
    """获取图像尺寸选项"""
    return [
        {"value": "512x512", "label": "512x512", "description": "正方形小图"},
        {"value": "768x768", "label": "768x768", "description": "正方形中图"},
        {"value": "1024x1024", "label": "1024x1024", "description": "正方形大图"},
        {"value": "1024x1536", "label": "1024x1536", "description": "竖版海报"},
        {"value": "1536x1024", "label": "1536x1024", "description": "横版封面"}
    ]
