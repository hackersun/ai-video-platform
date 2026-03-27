"""
火山引擎（Volcano Engine）模型配置
支持豆包大模型系列 - 文/图/视频生成

API调用规范:
- 文本模型: POST /chat/completions       → model_id 传模型ID
- 图像模型: POST /images/generations    → model_id 传 ENDPOINT_ID
- 视频模型: POST /contents/generations/tasks → model_id 传 ENDPOINT_ID
"""

# ============== 全局配置 ==============

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

# ============== Endpoint ID 映射 ==============
# 图像/视频模型的调用需要用 ENDPOINT_ID，而非模型名称

ENDPOINT_IDS = {
    # 图像生成模型
    "Doubao-Seedream-4.5":       "ep-20260320112226-rgndq",
    "Doubao-Seedream-5.0-lite":  "ep-20260320113731-jzjkn",
    # 文本模型（部分需要）
    "Doubao-Seed-2.0-pro":       "ep-20260320111926-sn9tg",
    # 视频生成模型
    "Doubao-Seedance-1.5-pro":   "doubao-seedance-1-5-pro-251215",
    "Doubao-Seedance-1.0-pro-fast": "ep-20260322134751-fbglz",
}


def get_endpoint_id(model_id: str) -> str:
    """获取模型的 Endpoint ID，用于图像/视频模型调用"""
    return ENDPOINT_IDS.get(model_id, model_id)


# ============== 模型列表 ==============

VOLCANO_MODELS = [

    # ========== 文本生成模型 (对话/LLM) ==========
    {
        "id": "doubao-seed-1-8-251228",
        "name": "doubao-seed-1-8-251228",
        "name_cn": "豆包Seed-1.8",
        "type": "text-generation",
        "endpoint": "/chat/completions",
        "api_model_id": "doubao-seed-1-8-251228",  # 直接用ID调用
        "capabilities": ["chat", "completion", "function_calling", "json_mode", "reasoning"],
        "context_window": 4096,
        "max_tokens": 2048,
        "input_cost_per_1k": 0.5,
        "output_cost_per_1k": 1.0,
        "description": "豆包轻量级模型，性价比高，支持函数调用和推理",
        "use_cases": ["对话", "快速响应", "轻量任务"],
        "version": "1.8",
        "is_verified": True,
        "verified_key": "be8feb9d-6b08-406e-8447-b22b87cd907a",
    },

    # ========== 图像生成模型 ==========
    {
        "id": "Doubao-Seedream-4.5",
        "name": "Doubao-Seedream-4.5",
        "name_cn": "豆包Seedream-4.5",
        "type": "image-generation",
        "endpoint": "/images/generations",
        "api_model_id": "ep-20260320112226-rgndq",  # ENDPOINT_ID
        "capabilities": ["text-to-image", "image-to-image"],
        "min_pixels": 3686400,  # >= 2048x2048
        "supported_ratios": ["1:1", "16:9", "9:16", "4:3", "3:4"],
        "recommended_sizes": ["2048x2048", "1024x1792", "960x3840"],
        "cost_per_image": 0,
        "description": "豆包高质量图像生成模型，支持文生图/图生图，像素要求>=3686400",
        "use_cases": ["角色形象", "场景图", "道具图", "参考图"],
        "version": "4.5",
        "is_verified": True,
        "verified_key": "be8feb9d-6b08-406e-8447-b22b87cd907a",
    },
    {
        "id": "Doubao-Seedream-5.0-lite",
        "name": "Doubao-Seedream-5.0-lite",
        "name_cn": "豆包Seedream-5.0-lite",
        "type": "image-generation",
        "endpoint": "/images/generations",
        "api_model_id": "ep-20260320113731-jzjkn",  # ENDPOINT_ID
        "capabilities": ["text-to-image", "image-to-image"],
        "min_pixels": 3686400,
        "supported_ratios": ["1:1", "16:9", "9:16", "4:3", "3:4", "21:9"],
        "recommended_sizes": ["2048x2048", "3072x3072", "960x3840", "1344x2688"],
        "cost_per_image": 0,
        "description": "豆包图像生成轻量版，支持更多比例，性价比更高",
        "use_cases": ["角色形象", "场景图", "快速生成"],
        "version": "5.0-lite",
        "is_verified": True,
        "verified_key": "be8feb9d-6b08-406e-8447-b22b87cd907a",
    },

    # ========== 视频生成模型 ==========
    {
        "id": "Doubao-Seedance-1.0-pro-fast",
        "name": "Doubao-Seedance-1.0-pro-fast",
        "name_cn": "豆包Seedance-1.0-pro-fast",
        "type": "video-generation",
        "endpoint": "/contents/generations/tasks",
        "api_model_id": "ep-20260322134751-fbglz",  # ENDPOINT_ID
        "capabilities": ["text-to-video", "image-to-video"],
        "supported_durations": [4, 5, 8, 10],
        "supported_resolutions": ["480p", "720p", "1080p"],
        "cost_per_second": 0,
        "description": "豆包Seedance 1.0 Pro快速版，支持文生视频/图生视频，生成速度快",
        "use_cases": ["视频生成", "动画制作", "镜头视频"],
        "version": "1.0-pro-fast",
        "is_verified": True,
        "verified_key": "be8feb9d-6b08-406e-8447-b22b87cd907a",
    },
    {
        "id": "Doubao-Seedance-1.5-pro",
        "name": "Doubao-Seedance-1.5-pro",
        "name_cn": "豆包Seedance-1.5-pro",
        "type": "video-generation",
        "endpoint": "/contents/generations/tasks",
        "api_model_id": "doubao-seedance-1-5-pro-251215",
        "capabilities": ["text-to-video", "image-to-video"],
        "supported_durations": [4, 8, 10],
        "supported_resolutions": ["480p", "720p", "1080p"],
        "cost_per_second": 0,
        "description": "豆包Seedance 1.5 Pro版，高质量视频生成，支持图生视频/文生视频（注：需账户有对应额度）",
        "use_cases": ["视频生成", "动画制作", "高质量视频"],
        "version": "1.5-pro",
        "is_verified": False,
        "note": "需在火山引擎控制台开启模型权限",
    },
]


# ============== 用途推荐 ==============

VOLCANO_USE_CASES = {
    "对话理解":    ["doubao-seed-1-8-251228"],
    "小说生成":    ["doubao-seed-1-8-251228"],
    "图像生成":    ["Doubao-Seedream-4.5", "Doubao-Seedream-5.0-lite"],
    "角色形象":    ["Doubao-Seedream-4.5", "Doubao-Seedream-5.0-lite"],
    "场景参考图":  ["Doubao-Seedream-4.5", "Doubao-Seedream-5.0-lite"],
    "视频生成":    ["Doubao-Seedance-1.0-pro-fast", "Doubao-Seedance-1.5-pro"],
    "镜头视频":    ["Doubao-Seedance-1.0-pro-fast", "Doubao-Seedance-1.5-pro"],
}


# ============== 默认模型 ==============

DEFAULT_TEXT_MODEL   = "doubao-seed-1-8-251228"
DEFAULT_IMAGE_MODEL  = "Doubao-Seedream-4.5"
DEFAULT_VIDEO_MODEL  = "Doubao-Seedance-1.0-pro-fast"  # 优先用已验证的快速版


# ============== 辅助函数 ==============

def get_volcano_model(model_id: str) -> dict:
    """根据模型ID获取模型配置"""
    for m in VOLCANO_MODELS:
        if m["id"] == model_id:
            return m
    return {}


def get_models_by_type(model_type: str) -> list:
    """获取指定类型的所有模型"""
    return [m for m in VOLCANO_MODELS if m.get("type") == model_type]


def get_verified_models() -> list:
    """获取已验证可用的模型"""
    return [m for m in VOLCANO_MODELS if m.get("is_verified", False)]


def get_verified_by_type(model_type: str) -> list:
    """获取指定类型中已验证的模型"""
    return [m for m in VOLCANO_MODELS
            if m.get("type") == model_type and m.get("is_verified", False)]


def get_recommended_volcano_models(use_case: str) -> list:
    """获取指定用途推荐的模型"""
    model_ids = VOLCANO_USE_CASES.get(use_case, [])
    return [get_volcano_model(mid) for mid in model_ids if get_volcano_model(mid)]


def calculate_volcano_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    """计算文本模型成本"""
    model = get_volcano_model(model_id)
    if not model:
        return 0.0
    ic = model.get("input_cost_per_1k", 0)
    oc = model.get("output_cost_per_1k", 0)
    return round((input_tokens / 1000) * ic + (output_tokens / 1000) * oc, 4)
