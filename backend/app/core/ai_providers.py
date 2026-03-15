"""
AI模型提供商预设配置
包含火山引擎、OpenAI、Anthropic等主流服务商
"""

# 火山引擎方舟大模型配置
VOLCANO_CONFIG = {
    "provider": "volcano",
    "provider_name": "Volcano Engine",
    "provider_name_cn": "火山引擎",
    "supported_types": ["text", "image", "video"],
    "base_url_template": "https://ark.cn-beijing.volces.com/api/v3",
    "auth_type": "bearer",
    "default_headers": {
        "Content-Type": "application/json"
    },
    "available_models": [
        # 文本生成模型
        {
            "id": "doubao-seed-2.0-pro",
            "name": "Doubao-Seed-2.0-pro",
            "name_cn": "豆包Seed-2.0-pro",
            "type": "text-generation",
            "version": "2.0",
            "capabilities": ["chat", "completion", "function-calling", "json-mode"],
            "context_window": 128000,
            "max_tokens": 8192,
            "input_cost": 5,  # 5元/百万tokens
            "output_cost": 9,  # 9元/百万tokens
            "description": "豆包最新旗舰模型，综合能力最强"
        },
        {
            "id": "doubao-pro-4k",
            "name": "Doubao-pro-4k",
            "name_cn": "豆包Pro-4K",
            "type": "text-generation",
            "context_window": 4096,
            "max_tokens": 4096,
            "input_cost": 0.8,
            "output_cost": 2,
            "description": "豆包Pro轻量版，性价比高"
        },
        {
            "id": "doubao-lite-4k",
            "name": "Doubao-lite-4k",
            "name_cn": "豆包Lite-4K",
            "type": "text-generation",
            "context_window": 4096,
            "max_tokens": 4096,
            "input_cost": 0.3,
            "output_cost": 0.6,
            "description": "豆包Lite极速版，响应快成本低"
        },
        # 图片生成模型
        {
            "id": "volcano-vision",
            "name": "Volcano Vision",
            "name_cn": "火山文生图",
            "type": "image-generation",
            "capabilities": ["text-to-image", "image-to-image", "inpainting"],
            "supported_sizes": ["512x512", "768x768", "1024x1024", "1024x1536", "1536x1024"],
            "cost_per_image": 10,  # 10分/张
            "description": "火山引擎高质量文生图模型"
        },
        # 视频生成模型
        {
            "id": "volcano-video",
            "name": "Volcano Video",
            "name_cn": "火山视频生成",
            "type": "video-generation",
            "capabilities": ["image-to-video", "text-to-video"],
            "supported_durations": [4, 8, 10],
            "cost_per_second": 50,  # 50分/秒
            "description": "火山引擎高质量视频生成模型"
        }
    ],
    "documentation_url": "https://www.volcengine.com/docs/82379"
}

# OpenAI配置
OPENAI_CONFIG = {
    "provider": "openai",
    "provider_name": "OpenAI",
    "provider_name_cn": "OpenAI",
    "supported_types": ["text", "image"],
    "base_url_template": "https://api.openai.com/v1",
    "auth_type": "bearer",
    "default_headers": {
        "Content-Type": "application/json"
    },
    "available_models": [
        {
            "id": "gpt-4o",
            "name": "GPT-4o",
            "type": "text-generation",
            "capabilities": ["chat", "completion", "function-calling", "vision"],
            "context_window": 128000,
            "max_tokens": 4096,
            "description": "OpenAI最新多模态旗舰模型"
        },
        {
            "id": "gpt-4o-mini",
            "name": "GPT-4o-mini",
            "type": "text-generation",
            "capabilities": ["chat", "completion", "function-calling", "vision"],
            "context_window": 128000,
            "max_tokens": 4096,
            "description": "GPT-4o轻量版，成本更低"
        },
        {
            "id": "dall-e-3",
            "name": "DALL-E 3",
            "type": "image-generation",
            "capabilities": ["text-to-image"],
            "supported_sizes": ["1024x1024", "1024x1792", "1792x1024"],
            "description": "OpenAI高质量文生图模型"
        }
    ],
    "documentation_url": "https://platform.openai.com/docs"
}

# Anthropic配置
ANTHROPIC_CONFIG = {
    "provider": "anthropic",
    "provider_name": "Anthropic",
    "provider_name_cn": "Anthropic",
    "supported_types": ["text"],
    "base_url_template": "https://api.anthropic.com/v1",
    "auth_type": "bearer",
    "default_headers": {
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01"
    },
    "available_models": [
        {
            "id": "claude-3-5-sonnet-20241022",
            "name": "Claude 3.5 Sonnet",
            "type": "text-generation",
            "capabilities": ["chat", "completion", "function-calling", "vision"],
            "context_window": 200000,
            "max_tokens": 8192,
            "description": "Anthropic最新智能模型"
        }
    ],
    "documentation_url": "https://docs.anthropic.com"
}

# 所有预设配置
PROVIDER_PRESETS = {
    "volcano": VOLCANO_CONFIG,
    "openai": OPENAI_CONFIG,
    "anthropic": ANTHROPIC_CONFIG
}

# 默认模型推荐
DEFAULT_MODELS = {
    "text-generation": "doubao-seed-2.0-pro",
    "image-generation": "volcano-vision",
    "video-generation": "volcano-video"
}


def get_provider_config(provider: str) -> dict:
    """获取提供商配置"""
    return PROVIDER_PRESETS.get(provider, {})


def get_model_config(provider: str, model_id: str) -> dict:
    """获取模型配置"""
    config = get_provider_config(provider)
    for model in config.get("available_models", []):
        if model["id"] == model_id:
            return model
    return {}


def list_all_models(model_type: str = None) -> list:
    """列出所有可用模型"""
    models = []
    for provider, config in PROVIDER_PRESETS.items():
        for model in config.get("available_models", []):
            if model_type is None or model["type"] == model_type:
                models.append({
                    "provider": provider,
                    **model
                })
    return models
