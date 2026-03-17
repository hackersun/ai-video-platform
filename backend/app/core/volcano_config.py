"""
火山引擎（Volcano Engine）模型配置
支持豆包大模型系列
"""

# 火山引擎配置
VOLCANO_CONFIG = {
    "provider": "volcano",
    "provider_name": "Volcano Engine",
    "provider_name_cn": "火山引擎",
    "base_url": "https://ark.cn-beijing.volces.com/api/v3",
    "auth_type": "bearer",
    "auth_header": "Authorization",
    "doc_url": "https://www.volcengine.com/docs/82379",
    "icon_url": "/icons/volcano.svg",
}

# 火山引擎豆包模型列表
VOLCANO_MODELS = [
    {
        "id": "doubao-seed-1-8-251228",
        "name": "doubao-seed-1-8-251228",
        "name_cn": "豆包Seed-1.8",
        "type": "text-generation",
        "capabilities": ["chat", "completion", "function_calling", "json_mode"],
        "context_window": 4096,
        "max_tokens": 2048,
        "input_cost_per_1k": 0.5,  # 0.5元/千tokens
        "output_cost_per_1k": 1.0,  # 1.0元/千tokens
        "description": "豆包最新轻量级模型，性价比高，响应速度快",
        "use_case": "对话理解、快速响应、轻量级任务",
        "version": "1.8",
        "release_date": "2024-12-28",
        "is_recommended": True,
        "is_verified": True,  # 已验证可用
        "verified_key": "be8feb9d-6b08-406e-8447-b22b87cd907a"  # 验证通过的Key
    },
    {
        "id": "doubao-pro-4k",
        "name": "doubao-pro-4k",
        "name_cn": "豆包Pro-4K",
        "type": "text-generation",
        "capabilities": ["chat", "completion", "function_calling"],
        "context_window": 4096,
        "max_tokens": 4096,
        "input_cost_per_1k": 0.8,
        "output_cost_per_1k": 2.0,
        "description": "豆包Pro轻量版，性价比高，适合大多数场景",
        "use_case": "通用对话、文本生成",
        "version": "1.0",
        "is_recommended": False
    },
    {
        "id": "doubao-lite-4k",
        "name": "doubao-lite-4k",
        "name_cn": "豆包Lite-4K",
        "type": "text-generation",
        "capabilities": ["chat", "completion"],
        "context_window": 4096,
        "max_tokens": 4096,
        "input_cost_per_1k": 0.3,
        "output_cost_per_1k": 0.6,
        "description": "豆包Lite极速版，响应最快，成本最低",
        "use_case": "快速响应、低成本场景",
        "version": "1.0",
        "is_recommended": False
    },
    {
        "id": "doubao-pro-32k",
        "name": "doubao-pro-32k",
        "name_cn": "豆包Pro-32K",
        "type": "text-generation",
        "capabilities": ["chat", "completion", "function_calling", "json_mode"],
        "context_window": 32768,
        "max_tokens": 8192,
        "input_cost_per_1k": 2.0,
        "output_cost_per_1k": 6.0,
        "description": "豆包Pro长上下文版，支持32K上下文",
        "use_case": "长文档处理、复杂对话",
        "version": "1.0",
        "is_recommended": False
    },
    {
        "id": "doubao-pro-128k",
        "name": "doubao-pro-128k",
        "name_cn": "豆包Pro-128K",
        "type": "text-generation",
        "capabilities": ["chat", "completion", "function_calling"],
        "context_window": 128000,
        "max_tokens": 8192,
        "input_cost_per_1k": 5.0,
        "output_cost_per_1k": 9.0,
        "description": "豆包Pro超长上下文版，支持128K上下文",
        "use_case": "超长文档、代码分析",
        "version": "1.0",
        "is_recommended": False
    },
    {
        "id": "volcano-vision",
        "name": "volcano-vision",
        "name_cn": "火山文生图",
        "type": "image-generation",
        "capabilities": ["text-to-image", "image-to-image", "inpainting"],
        "supported_sizes": ["512x512", "768x768", "1024x1024", "1024x1536", "1536x1024"],
        "cost_per_image": 10,  # 10分/张
        "description": "火山引擎高质量文生图模型",
        "use_case": "图像生成、图像编辑",
        "is_recommended": False
    },
    {
        "id": "volcano-video",
        "name": "volcano-video",
        "name_cn": "火山视频生成",
        "type": "video-generation",
        "capabilities": ["image-to-video", "text-to-video"],
        "supported_durations": [4, 8, 10],
        "cost_per_second": 50,  # 50分/秒
        "description": "火山引擎高质量视频生成模型",
        "use_case": "视频生成、动画制作",
        "is_recommended": False
    }
]

# 用途推荐
VOLCANO_USE_CASES = {
    "对话理解": ["doubao-seed-1-8-251228", "doubao-pro-4k"],
    "小说生成": ["doubao-pro-32k", "doubao-pro-128k"],
    "快速响应": ["doubao-seed-1-8-251228", "doubao-lite-4k"],
    "长文档处理": ["doubao-pro-128k", "doubao-pro-32k"],
    "图像生成": ["volcano-vision"],
    "视频生成": ["volcano-video"],
    "低成本场景": ["doubao-lite-4k", "doubao-seed-1-8-251228"]
}


def get_volcano_model(model_id: str) -> dict:
    """获取火山引擎模型配置"""
    for model in VOLCANO_MODELS:
        if model["id"] == model_id:
            return model
    return {}


def get_recommended_volcano_models(use_case: str) -> list:
    """获取推荐模型"""
    model_ids = VOLCANO_USE_CASES.get(use_case, [])
    return [get_volcano_model(mid) for mid in model_ids]


def calculate_volcano_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    """计算成本（元）"""
    model = get_volcano_model(model_id)
    if not model:
        return 0.0
    
    input_cost = (input_tokens / 1000) * model["input_cost_per_1k"]
    output_cost = (output_tokens / 1000) * model["output_cost_per_1k"]
    
    return round(input_cost + output_cost, 4)


def get_verified_models() -> list:
    """获取已验证的模型列表"""
    return [m for m in VOLCANO_MODELS if m.get("is_verified", False)]
