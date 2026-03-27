"""
OpenAI 模型配置
支持 GPT-4o, GPT-4o-mini, DALL-E, Sora 等模型
"""

# OpenAI 配置
OPENAI_CONFIG = {
    "provider": "openai",
    "provider_name": "OpenAI",
    "provider_name_cn": "OpenAI",
    "base_url": "https://api.openai.com/v1",
    "auth_type": "bearer",
    "auth_header": "Authorization",
    "doc_url": "https://platform.openai.com/docs",
    "icon_url": "/icons/openai.svg",
}

# OpenAI 模型列表
OPENAI_MODELS = [
    {
        "id": "gpt-4o",
        "name": "gpt-4o",
        "name_cn": "GPT-4o",
        "type": "chat",
        "capabilities": ["chat", "vision", "function_calling", "json_mode"],
        "context_window": 128000,
        "max_tokens": 16384,
        "input_cost_per_1k": 2.5,   # $2.5 / 1M tokens input
        "output_cost_per_1k": 10.0,  # $10 / 1M tokens output
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": True,
        "supports_json_mode": True,
        "description": "OpenAI 最强旗舰模型，支持文本和图像理解",
        "use_case": "复杂推理、高质量文本生成、图像分析",
        "version": "2024-05-13",
        "release_date": "2024-05-13",
        "is_recommended": True,
    },
    {
        "id": "gpt-4o-mini",
        "name": "gpt-4o-mini",
        "name_cn": "GPT-4o-mini",
        "type": "chat",
        "capabilities": ["chat", "vision", "function_calling", "json_mode"],
        "context_window": 128000,
        "max_tokens": 16384,
        "input_cost_per_1k": 0.15,   # $0.15 / 1M tokens input
        "output_cost_per_1k": 0.60,  # $0.60 / 1M tokens output
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": True,
        "supports_json_mode": True,
        "description": "轻量级旗舰模型，性价比高，支持文本和图像理解",
        "use_case": "快速响应、图像分析、轻量级任务",
        "version": "2024-07-18",
        "release_date": "2024-07-18",
        "is_recommended": True,
    },
    {
        "id": "gpt-4-turbo",
        "name": "gpt-4-turbo",
        "name_cn": "GPT-4 Turbo",
        "type": "chat",
        "capabilities": ["chat", "vision", "function_calling", "json_mode"],
        "context_window": 128000,
        "max_tokens": 4096,
        "input_cost_per_1k": 10.0,
        "output_cost_per_1k": 30.0,
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": True,
        "supports_json_mode": True,
        "description": "GPT-4 高性能版，上下文窗口大",
        "use_case": "复杂对话、图像理解",
        "version": "2024-04-09",
        "release_date": "2024-04-09",
        "is_recommended": False,
    },
    {
        "id": "gpt-3.5-turbo",
        "name": "gpt-3.5-turbo",
        "name_cn": "GPT-3.5 Turbo",
        "type": "chat",
        "capabilities": ["chat", "function_calling", "json_mode"],
        "context_window": 16385,
        "max_tokens": 4096,
        "input_cost_per_1k": 0.5,
        "output_cost_per_1k": 1.5,
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": False,
        "supports_json_mode": True,
        "description": "轻量快速模型，适合简单任务",
        "use_case": "快速响应、简单对话",
        "version": "0125",
        "release_date": "2024-01-25",
        "is_recommended": False,
    },
    # DALL-E 图像生成模型
    {
        "id": "dall-e-3",
        "name": "dall-e-3",
        "name_cn": "DALL-E 3",
        "type": "image-generation",
        "capabilities": ["text-to-image"],
        "supported_sizes": ["1024x1024", "1024x1792", "1792x1024"],
        "input_cost_per_1k": 0,
        "output_cost_per_1k": 0,
        "cost_per_image": 0.04,  # $0.04 / image (1024x1024 standard)
        "supports_streaming": False,
        "supports_function_calling": False,
        "supports_vision": False,
        "supports_json_mode": False,
        "description": "OpenAI 最新高质量图像生成模型，支持精细控制和多种尺寸",
        "use_case": "高质量图像生成、插画创作",
        "version": "3",
        "release_date": "2023-11-06",
        "is_recommended": True,
    },
    {
        "id": "dall-e-2",
        "name": "dall-e-2",
        "name_cn": "DALL-E 2",
        "type": "image-generation",
        "capabilities": ["text-to-image", "image-edit", "variation"],
        "supported_sizes": ["256x256", "512x512", "1024x1024"],
        "input_cost_per_1k": 0,
        "output_cost_per_1k": 0,
        "cost_per_image": 0.02,  # $0.02 / image
        "supports_streaming": False,
        "supports_function_calling": False,
        "supports_vision": False,
        "supports_json_mode": False,
        "description": "OpenAI 图像生成模型，支持图像编辑和变体生成",
        "use_case": "图像生成、图像编辑",
        "version": "2",
        "release_date": "2022-11-03",
        "is_recommended": False,
    },
    # Sora 视频生成模型 (预留)
    {
        "id": "sora",
        "name": "sora",
        "name_cn": "OpenAI Sora",
        "type": "video-generation",
        "capabilities": ["text-to-video", "image-to-video"],
        "supported_durations": [5, 10, 20],
        "input_cost_per_1k": 0,
        "output_cost_per_1k": 0,
        "cost_per_second": 0.0,  # 待定
        "supports_streaming": False,
        "supports_function_calling": False,
        "supports_vision": False,
        "supports_json_mode": False,
        "description": "OpenAI 视频生成模型（即将发布）",
        "use_case": "视频生成、动画制作",
        "version": "1.0",
        "release_date": "2024-02-15",
        "is_recommended": False,
        "coming_soon": True,
    }
]


def get_openai_model(model_id: str) -> dict:
    """获取 OpenAI 模型配置"""
    for model in OPENAI_MODELS:
        if model["id"] == model_id:
            return model
    return {}


def get_recommended_openai_models(use_case: str) -> list:
    """获取推荐模型"""
    use_case_map = {
        "对话理解": ["gpt-4o-mini", "gpt-4o"],
        "图像分析": ["gpt-4o", "gpt-4o-mini"],
        "图像生成": ["dall-e-3", "dall-e-2"],
        "视频生成": ["sora"],
        "快速响应": ["gpt-4o-mini", "gpt-3.5-turbo"],
        "复杂推理": ["gpt-4o"],
        "低成本场景": ["gpt-4o-mini", "gpt-3.5-turbo"],
    }
    model_ids = use_case_map.get(use_case, [])
    return [get_openai_model(mid) for mid in model_ids if get_openai_model(mid)]


def calculate_openai_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    """计算成本（美元）"""
    model = get_openai_model(model_id)
    if not model:
        return 0.0

    input_cost = (input_tokens / 1000) * model.get("input_cost_per_1k", 0)
    output_cost = (output_tokens / 1000) * model.get("output_cost_per_1k", 0)

    return round(input_cost + output_cost, 6)


# 用途推荐
OPENAI_USE_CASES = {
    "对话理解": ["gpt-4o-mini", "gpt-4o"],
    "图像分析": ["gpt-4o", "gpt-4o-mini"],
    "图像生成": ["dall-e-3", "dall-e-2"],
    "视频生成": ["sora"],
    "快速响应": ["gpt-4o-mini", "gpt-3.5-turbo"],
    "复杂推理": ["gpt-4o"],
    "低成本场景": ["gpt-4o-mini", "gpt-3.5-turbo"]
}
