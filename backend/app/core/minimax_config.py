"""
MiniMax 模型配置
支持文本生成、图像生成、TTS语音合成

API调用规范:
- 文本模型: POST /v1/chat/completions      → model_id 传模型名（如 MiniMax-M2.7）
- 图像模型: POST /v1/image_generation     → model_id 传 image-01
- TTS模型:   POST /v1/t2a_v2              → model_id 传 speech-2.6-hd
"""

# ============== 全局配置 ==============

MINIMAX_CONFIG = {
    "provider": "minimax",
    "provider_name": "MiniMax",
    "provider_name_cn": "MiniMax",
    "provider_name_en": "MiniMax",
    "provider_type": "cloud",
    "base_url": "https://api.minimaxi.com/v1",  # 默认中国，可被前缀路由覆盖
    "auth_type": "bearer",
    "auth_header": "Authorization",
    "doc_url": "https://platform.minimaxi.com/document",
    "icon_url": "/icons/minimax.svg",
    "description": "MiniMax 海螺AI，支持文本生成、图像生成、TTS语音合成",
    "website_url": "https://www.minimaxi.com/",
}

# ============== API Key 前缀路由 ==============

# MiniMax API 端点
MINIMAX_ENDPOINTS = {
    "cn": "https://api.minimaxi.com/v1",   # 中国大陆
    "global": "https://api.minimax.io/v1", # 海外
}
DEFAULT_MINIMAX_ENDPOINT = "https://api.minimaxi.com/v1"  # 默认中国


def get_minimax_base_url(api_key: str = "") -> str:
    """
    根据 API Key 前缀自动判断区域。
    实测：sk-cp- 前缀的 key 在 api.minimaxi.com 可用，api.minimax.io 可能返回 2049。
    因此 sk-cp- 也默认走中国端点。
    """
    if api_key.startswith("sk-cp-"):
        # sk-cp- 前缀实测在 api.minimaxi.com 可用，默认中国
        return MINIMAX_ENDPOINTS["cn"]
    # sk-api-* 或其他默认走中国
    return MINIMAX_ENDPOINTS["cn"]


# ============== 模型列表 ==============

MINIMAX_MODELS = [

    # ========== 文本生成模型 ==========
    {
        "id": "MiniMax-M2.7",
        "name": "MiniMax-M2.7",
        "name_cn": "MiniMax-M2.7",
        "type": "text-generation",
        "endpoint": "/v1/chat/completions",
        "api_model_id": "MiniMax-M2.7",
        "capabilities": ["chat", "completion", "function_calling", "json_mode", "reasoning"],
        "context_window": 1000000,
        "max_tokens": 8192,
        "input_cost_per_1k": 0,
        "output_cost_per_1k": 0,
        "description": "MiniMax 最新旗舰模型，超长上下文，支持函数调用和推理",
        "use_cases": ["对话", "小说生成", "复杂推理", "函数调用"],
        "version": "M2.7",
        "is_verified": False,
    },
    {
        "id": "MiniMax-M2",
        "name": "MiniMax-M2",
        "name_cn": "MiniMax-M2",
        "type": "text-generation",
        "endpoint": "/v1/chat/completions",
        "api_model_id": "MiniMax-M2",
        "capabilities": ["chat", "completion", "function_calling", "json_mode"],
        "context_window": 1000000,
        "max_tokens": 8192,
        "input_cost_per_1k": 0,
        "output_cost_per_1k": 0,
        "description": "MiniMax M2 模型，超长上下文，支持函数调用",
        "use_cases": ["对话", "长文本处理", "函数调用"],
        "version": "M2",
        "is_verified": False,
    },

    # ========== 图像生成模型 ==========
    {
        "id": "MiniMax-image-01",
        "name": "MiniMax-image-01",
        "name_cn": "MiniMax图像生成",
        "type": "image-generation",
        "endpoint": "/v1/image_generation",
        "api_model_id": "image-01",
        "capabilities": ["text-to-image", "image-to-image"],
        "supported_ratios": ["1:1", "16:9", "4:3", "3:2", "2:3", "3:4", "9:16", "21:9"],
        "recommended_sizes": ["1024x1024", "1280x720", "720x1280"],
        "cost_per_image": 0,
        "description": "MiniMax 高质量图像生成，支持文生图/图生图，生成快速",
        "use_cases": ["角色形象", "场景图", "道具图", "分镜参考图"],
        "version": "image-01",
        "is_verified": False,
    },

    # ========== TTS 语音合成模型 ==========
    {
        "id": "MiniMax-speech-2.6-hd",
        "name": "MiniMax-speech-2.6-hd",
        "name_cn": "MiniMax语音合成-HD",
        "type": "tts",
        "endpoint": "/v1/t2a_v2",
        "api_model_id": "speech-2.6-hd",
        "capabilities": ["text-to-speech"],
        "cost_per_1k_chars": 0,
        "description": "MiniMax 高质量语音合成，支持中文/英文/多语种，多种音色可选",
        "use_cases": ["配音", "有声书", "旁白", "角色对话"],
        "version": "speech-2.6-hd",
        "is_verified": False,
        "note": "部分 Token Plan 可能不支持，请确认账户已开通 TTS 权限"
    },
    {
        "id": "MiniMax-speech-2.6-turbo",
        "name": "MiniMax-speech-2.6-turbo",
        "name_cn": "MiniMax语音合成-Turbo",
        "type": "tts",
        "endpoint": "/v1/t2a_v2",
        "api_model_id": "speech-2.6-turbo",
        "capabilities": ["text-to-speech"],
        "cost_per_1k_chars": 0,
        "description": "MiniMax 快速语音合成，性价比更高",
        "use_cases": ["配音", "旁白", "快速生成"],
        "version": "speech-2.6-turbo",
        "is_verified": False,
        "note": "部分 Token Plan 可能不支持，请确认账户已开通 TTS 权限"
    },
]

# ============== TTS 音色列表（精选）==============

TTS_VOICES = [
    # 中文
    {"voice_id": "female-shaonv",    "name": "少女",     "gender": "female", "lang": "中文"},
    {"voice_id": "female-yujie",    "name": "御姐",     "gender": "female", "lang": "中文"},
    {"voice_id": "female-chengshu", "name": "知性",     "gender": "female", "lang": "中文"},
    {"voice_id": "male-qn-qingse",   "name": "清涩少年", "gender": "male",   "lang": "中文"},
    {"voice_id": "male-qn-jingying", "name": "精英男性", "gender": "male",   "lang": "中文"},
    {"voice_id": "male-qn-badao",    "name": "霸道",     "gender": "male",   "lang": "中文"},
    {"voice_id": "audiobook_male_1", "name": "有声书男", "gender": "male",   "lang": "中/英"},
    {"voice_id": "audiobook_female_1","name": "有声书女", "gender": "female", "lang": "中/英"},
    # 英文
    {"voice_id": "English_expressive_narrator", "name": "英文叙述", "gender": "female", "lang": "英文"},
    {"voice_id": "female-tianmei",   "name": "甜美女声", "gender": "female", "lang": "英文"},
    # 多语
    {"voice_id": "Japanese_female_qingli", "name": "日语女声", "gender": "female", "lang": "日语"},
    {"voice_id": "Korean_female_qingli",   "name": "韩语女声", "gender": "female", "lang": "韩语"},
]

# ============== 默认模型 ==============

DEFAULT_TEXT_MODEL  = "MiniMax-M2.7"
DEFAULT_IMAGE_MODEL = "MiniMax-image-01"
DEFAULT_TTS_MODEL   = "MiniMax-speech-2.6-hd"
DEFAULT_TTS_VOICE   = "female-shaonv"


# ============== 辅助函数 ==============

def get_minimax_model(model_id: str) -> dict:
    """根据模型ID获取模型配置（支持内部ID和API model_id两种匹配）"""
    for m in MINIMAX_MODELS:
        if m["id"] == model_id:
            return m
        if m.get("api_model_id") == model_id:
            return m
    return {}


def get_models_by_type(model_type: str) -> list:
    """获取指定类型的所有模型"""
    return [m for m in MINIMAX_MODELS if m.get("type") == model_type]


def get_text_models() -> list:
    return get_models_by_type("text-generation")


def get_image_models() -> list:
    return get_models_by_type("image-generation")


def get_tts_models() -> list:
    return get_models_by_type("tts")


def get_verified_models() -> list:
    return [m for m in MINIMAX_MODELS if m.get("is_verified", False)]


def get_verified_by_type(model_type: str) -> list:
    return [m for m in MINIMAX_MODELS
            if m.get("type") == model_type and m.get("is_verified", False)]
