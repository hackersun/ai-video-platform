"""
阿里千问（Qwen）模型配置
支持DashScope API
"""

# 阿里千问 DashScope 配置
DASHSCOPE_CONFIG = {
    "provider": "qwen",
    "provider_name": "Alibaba Qwen",
    "provider_name_cn": "阿里千问",
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "auth_type": "bearer",
    "auth_header": "Authorization",
    "doc_url": "https://help.aliyun.com/document_detail/611411.html",
    "icon_url": "/icons/qwen.svg",
}

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

# 阿里百炼配置
QIANLIAN_CONFIG = {
    "provider": "qianlian",
    "provider_name": "Alibaba Qianlian",
    "provider_name_cn": "阿里百炼",
    "base_url": "https://coding.dashscope.aliyuncs.com/v1",
    "auth_type": "bearer",
    "auth_header": "Authorization",
    "doc_url": "https://help.aliyun.com/document_detail/3096588.html",
    "icon_url": "/icons/qianlian.svg",
}

# 默认模型配置
DEFAULT_MODELS = {
    # 文本生成
    "default_text": "doubao-seed-1.8",  # 火山引擎 - 豆包Seed-1.8
    
    # 图像生成
    "default_image": "Doubao-Seedream-4.5",  # 火山引擎 - Seedream-4.5
    
    # 视频生成
    "default_video": "Doubao-Seed-2.0-pro",  # 火山引擎 - Seed-2.0-pro
    
    # Coding Plan / 对话理解
    "default_coding_plan": "qwen3.5-plus",  # 百炼 - 通义千问3.5-Plus
    "default_dialogue": "qwen3.5-plus",  # 百炼 - 通义千问3.5-Plus
    
    # 小说生成
    "default_novel": "qwen-long",  # 千问 - 长文本模型
    
    # 分镜生成
    "default_storyboard": "qwen-vl-plus",  # 千问VL - 视觉模型
    
    # 角色扮演
    "default_roleplay": "qwen-plus",  # 千问Plus
}

# 各功能对应的服务商和模型
SERVICE_MODEL_MAP = {
    "novel_generation": {
        "provider": "qwen",
        "model": "qwen-long",
        "description": "长文本小说生成"
    },
    "coding_plan": {
        "provider": "qianlian",
        "model": "qwen3.5-plus",
        "description": "Coding Plan 生成"
    },
    "dialogue_understanding": {
        "provider": "qianlian",
        "model": "qwen3.5-plus",
        "description": "对话理解"
    },
    "storyboard_generation": {
        "provider": "qwen",
        "model": "qwen-vl-plus",
        "description": "视频分镜生成"
    },
    "image_generation": {
        "provider": "volcano",
        "model": "Doubao-Seedream-4.5",
        "description": "图像生成"
    },
    "video_generation": {
        "provider": "volcano",
        "model": "Doubao-Seed-2.0-pro",
        "description": "视频生成"
    },
    "roleplay": {
        "provider": "qwen",
        "model": "qwen-plus",
        "description": "角色扮演"
    }
}

# 千问模型列表
QWEN_MODELS = [
    {
        "id": "qwen-turbo",
        "name": "qwen-turbo",
        "name_cn": "千问Turbo",
        "type": "text-generation",
        "capabilities": ["chat", "completion"],
        "context_window": 8192,
        "max_tokens": 2048,
        "input_cost_per_1k": 0.5,  # 0.5元/千tokens
        "output_cost_per_1k": 1.0,
        "description": "轻量级模型，响应速度快，成本低",
        "use_case": "对话理解、快速响应"
    },
    {
        "id": "qwen-plus",
        "name": "qwen-plus",
        "name_cn": "千问Plus",
        "type": "text-generation",
        "capabilities": ["chat", "completion", "function_calling"],
        "context_window": 32768,
        "max_tokens": 8192,
        "input_cost_per_1k": 2.0,
        "output_cost_per_1k": 6.0,
        "description": "均衡型模型，综合能力优秀",
        "use_case": "对话理解、小说生成"
    },
    {
        "id": "qwen-max",
        "name": "qwen-max",
        "name_cn": "千问Max",
        "type": "text-generation",
        "capabilities": ["chat", "completion", "function_calling", "json_mode"],
        "context_window": 32768,
        "max_tokens": 8192,
        "input_cost_per_1k": 20.0,
        "output_cost_per_1k": 60.0,
        "description": "旗舰级模型，最强性能",
        "use_case": "复杂推理、高质量生成"
    },
    {
        "id": "qwen-long",
        "name": "qwen-long",
        "name_cn": "千问Long",
        "type": "text-generation",
        "capabilities": ["chat", "completion"],
        "context_window": 1000000,  # 100万token
        "max_tokens": 8192,
        "input_cost_per_1k": 0.5,
        "output_cost_per_1k": 2.0,
        "description": "超长上下文模型，支持百万token",
        "use_case": "长文本小说生成、文档分析"
    },
    {
        "id": "qwen-coder-plus",
        "name": "qwen-coder-plus",
        "name_cn": "千问Coder Plus",
        "type": "text-generation",
        "capabilities": ["chat", "completion", "code_generation", "planning"],
        "context_window": 32768,
        "max_tokens": 8192,
        "input_cost_per_1k": 2.0,
        "output_cost_per_1k": 6.0,
        "description": "代码生成旗舰模型，支持复杂规划和架构设计",
        "use_case": "代码生成、Coding Plan、技术方案设计"
    },
    {
        "id": "qwen-coder-turbo",
        "name": "qwen-coder-turbo",
        "name_cn": "千问Coder Turbo",
        "type": "text-generation",
        "capabilities": ["chat", "completion", "code_generation"],
        "context_window": 8192,
        "max_tokens": 4096,
        "input_cost_per_1k": 0.5,
        "output_cost_per_1k": 1.0,
        "description": "代码生成轻量模型，响应速度快",
        "use_case": "快速代码生成、简单规划"
    },
    {
        "id": "qwen-vl-plus",
        "name": "qwen-vl-plus",
        "name_cn": "千问VL Plus",
        "type": "vision-language",
        "capabilities": ["chat", "vision", "image_understanding"],
        "context_window": 32768,
        "max_tokens": 2048,
        "input_cost_per_1k": 2.0,
        "output_cost_per_1k": 6.0,
        "description": "视觉语言模型，支持图像理解",
        "use_case": "视频分镜生成、图像描述"
    },
    {
        "id": "qwen-vl-max",
        "name": "qwen-vl-max",
        "name_cn": "千问VL Max",
        "type": "vision-language",
        "capabilities": ["chat", "vision", "image_understanding"],
        "context_window": 32768,
        "max_tokens": 2048,
        "input_cost_per_1k": 20.0,
        "output_cost_per_1k": 60.0,
        "description": "视觉语言旗舰模型",
        "use_case": "高精度图像理解、视频分析"
    }
]

# 用途推荐
QWEN_USE_CASES = {
    "对话理解": ["qwen-plus", "qwen-turbo"],
    "小说生成": ["qwen-long", "qwen-plus"],
    "视频分镜": ["qwen-vl-plus", "qwen-vl-max"],
    "代码生成": ["qwen-coder-plus"],
    "快速响应": ["qwen-turbo"]
}


def get_qwen_model(model_id: str) -> dict:
    """获取千问模型配置"""
    for model in QWEN_MODELS:
        if model["id"] == model_id:
            return model
    return {}


def get_recommended_models(use_case: str) -> list:
    """获取推荐模型"""
    model_ids = QWEN_USE_CASES.get(use_case, [])
    return [get_qwen_model(mid) for mid in model_ids]


def calculate_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    """计算成本（元）"""
    model = get_qwen_model(model_id)
    if not model:
        return 0.0
    
    input_cost = (input_tokens / 1000) * model["input_cost_per_1k"]
    output_cost = (output_tokens / 1000) * model["output_cost_per_1k"]
    
    return round(input_cost + output_cost, 4)
