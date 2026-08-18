"""Official DeepSeek provider and current public text-model catalog."""

from datetime import datetime

DEEPSEEK_API_BASE_URL = "https://api.deepseek.com"

DEEPSEEK_PROVIDER = {
    "id": "deepseek",
    "name": "deepseek",
    "name_cn": "DeepSeek 官方",
    "name_en": "DeepSeek",
    "provider_type": "cloud",
    "base_url": DEEPSEEK_API_BASE_URL,
    "auth_type": "bearer",
    "is_active": True,
    "is_builtin": True,
    "description": "DeepSeek 官方 API，支持 V4 Flash 与 V4 Pro 文本模型",
    "website_url": "https://platform.deepseek.com/",
    "doc_url": "https://api-docs.deepseek.com/",
}


def _deepseek_model(
    *, suffix: str, display_name: str, recommended: bool,
    input_cost_per_1k: float, output_cost_per_1k: float, description: str,
) -> dict:
    return {
        "id": f"deepseek-{suffix}",
        "provider_id": "deepseek",
        "model_id": f"deepseek-{suffix}",
        "model_name": f"DeepSeek-{display_name}",
        "model_name_cn": f"DeepSeek {display_name}",
        "model_type": "chat",
        "capabilities": ["chat", "completion", "reasoning", "function_calling", "json_mode", "long_context"],
        "context_window": 1_000_000,
        "max_tokens": 384_000,
        "input_cost_per_1k": input_cost_per_1k,
        "output_cost_per_1k": output_cost_per_1k,
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": False,
        "supports_json_mode": True,
        "is_active": True,
        "is_recommended": recommended,
        "description": description,
        "version": "v4",
        "release_date": datetime(2026, 4, 24),
    }


DEEPSEEK_MODEL_SEEDS = [
    _deepseek_model(
        suffix="v4-flash", display_name="V4 Flash", recommended=True,
        input_cost_per_1k=0.00014, output_cost_per_1k=0.00028,
        description="DeepSeek 官方高性价比文本模型，适合章节续写、实体提取、剧本和批量分镜。",
    ),
    _deepseek_model(
        suffix="v4-pro", display_name="V4 Pro", recommended=False,
        input_cost_per_1k=0.000435, output_cost_per_1k=0.00087,
        description="DeepSeek 官方高阶推理模型，适合复杂剧情规划、长篇一致性检查和剧本重构。",
    ),
]
