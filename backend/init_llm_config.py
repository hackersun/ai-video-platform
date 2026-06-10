"""
LLM服务商和模型配置初始化脚本

运行此脚本初始化LLM服务商和模型配置到数据库
"""
import sys
import uuid
sys.path.insert(0, '.')

from app.core.database import sync_engine
from sqlalchemy.orm import Session
from app.core.volcano_agent_plan_config import VOLCANO_AGENT_PLAN_MODELS, VOLCANO_AGENT_PLAN_PROVIDER
from app.models.llm_config import LLMProvider, LLMModel


def init_llm_providers_and_models():
    """初始化LLM服务商和模型"""
    
    # 服务商配置
    providers = [
        {
            "id": "volcano",
            "name": "volcano",
            "name_cn": "火山引擎",
            "name_en": "Volcano Engine",
            "provider_type": "cloud",
            "base_url": "https://ark.cn-beijing.volces.com/api/v3",
            "auth_type": "bearer",
            "is_active": True,
            "is_builtin": True,
            "description": "字节跳动火山引擎，提供豆包大模型系列",
            "website_url": "https://www.volcengine.com/",
            "doc_url": "https://www.volcengine.com/docs/82379"
        },
        VOLCANO_AGENT_PLAN_PROVIDER,
        {
            "id": "qianlian",
            "name": "qianlian",
            "name_cn": "阿里百炼",
            "name_en": "Alibaba Qianlian",
            "provider_type": "cloud",
            "base_url": "https://coding.dashscope.aliyuncs.com/apps/anthropic/v1",
            "auth_type": "bearer",
            "is_active": True,
            "is_builtin": True,
            "description": "阿里云百炼平台，支持qwen3.5-plus、kimi等模型",
            "website_url": "https://bailian.console.aliyun.com/",
            "doc_url": "https://help.aliyun.com/zh/model-studio/"
        },
        {
            "id": "dashscope",
            "name": "dashscope",
            "name_cn": "千问(DashScope)",
            "name_en": "Alibaba DashScope",
            "provider_type": "cloud",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "auth_type": "bearer",
            "is_active": True,
            "is_builtin": True,
            "description": "阿里云千问平台，支持qwen-long、qwen-plus等模型",
            "website_url": "https://dashscope.console.aliyun.com/",
            "doc_url": "https://help.aliyun.com/zh/dashscope/"
        },
        {
            "id": "openai",
            "name": "openai",
            "name_cn": "OpenAI",
            "name_en": "OpenAI",
            "provider_type": "cloud",
            "base_url": "https://api.openai.com/v1",
            "auth_type": "bearer",
            "is_active": True,
            "is_builtin": True,
            "description": "OpenAI 提供 GPT-4o、DALL-E、Sora 等模型",
            "website_url": "https://platform.openai.com/",
            "doc_url": "https://platform.openai.com/docs"
        },
        {
            "id": "minimax",
            "name": "minimax",
            "name_cn": "MiniMax",
            "name_en": "MiniMax",
            "provider_type": "cloud",
            "base_url": "https://api.minimaxi.com/v1",
            "auth_type": "bearer",
            "is_active": True,
            "is_builtin": True,
            "description": "MiniMax 海螺AI，支持文本生成、图像生成、TTS语音合成",
            "website_url": "https://www.minimaxi.com/",
            "doc_url": "https://platform.minimaxi.com/document"
        }
    ]
    
    # 模型配置
    models = [
        *VOLCANO_AGENT_PLAN_MODELS,
        # 火山引擎 - 文本模型
        {
            "id": "volcano-doubao-seed-1-8",
            "provider_id": "volcano",
            "model_id": "doubao-seed-1-8-251228",
            "model_name": "doubao-seed-1-8-251228",
            "model_name_cn": "豆包Seed-1.8",
            "model_type": "chat",
            "capabilities": ["chat", "completion", "function_calling"],
            "context_window": 4096,
            "max_tokens": 2048,
            "input_cost_per_1k": 0.5,
            "output_cost_per_1k": 1.0,
            "supports_streaming": True,
            "supports_function_calling": True,
            "is_recommended": False,
            "is_active": True,
            "description": "豆包最新轻量级模型，性价比高"
        },
        # 火山引擎 - 视频模型
        {
            "id": "volcano-seedance-1-0-pro-fast",
            "provider_id": "volcano",
            "model_id": "ep-20260322134751-fbglz",
            "model_name": "Doubao-Seedance-1.0-pro-fast",
            "model_name_cn": "豆包Seedance-1.0-pro-fast",
            "model_type": "video",
            "capabilities": ["text-to-video", "image-to-video"],
            "context_window": 0,
            "max_tokens": 0,
            "input_cost_per_1k": 0,
            "output_cost_per_1k": 0,
            "supports_streaming": False,
            "supports_function_calling": False,
            "is_recommended": False,
            "is_active": True,
            "description": "豆包Seedance 1.0 Pro快速版，图生视频/文生视频，速度快"
        },
        {
            "id": "volcano-seedance-2-0",
            "provider_id": "volcano",
            "model_id": "doubao-seedance-2-0-260128",
            "model_name": "Doubao-Seedance-2.0",
            "model_name_cn": "豆包Seedance-2.0",
            "model_type": "video",
            "capabilities": ["text-to-video", "image-to-video"],
            "context_window": 0,
            "max_tokens": 0,
            "input_cost_per_1k": 0,
            "output_cost_per_1k": 0,
            "supports_streaming": False,
            "supports_function_calling": False,
            "is_recommended": True,
            "is_active": True,
            "description": "豆包Seedance 2.0，高质量文生视频/图生视频模型"
        },
        {
            "id": "volcano-seedance-2-0-fast",
            "provider_id": "volcano",
            "model_id": "doubao-seedance-2-0-fast-260128",
            "model_name": "Doubao-Seedance-2.0-fast",
            "model_name_cn": "豆包Seedance-2.0-fast",
            "model_type": "video",
            "capabilities": ["text-to-video", "image-to-video"],
            "context_window": 0,
            "max_tokens": 0,
            "input_cost_per_1k": 0,
            "output_cost_per_1k": 0,
            "supports_streaming": False,
            "supports_function_calling": False,
            "is_recommended": True,
            "is_active": True,
            "description": "豆包Seedance 2.0 Fast，适合批量镜头草稿和快速预览"
        },
        {
            "id": "volcano-video",
            "provider_id": "volcano",
            "model_id": "volcano-video",
            "model_name": "volcano-video",
            "model_name_cn": "火山视频生成",
            "model_type": "video",
            "capabilities": ["text-to-video", "image-to-video"],
            "context_window": 0,
            "max_tokens": 0,
            "input_cost_per_1k": 0,
            "output_cost_per_1k": 0,
            "supports_streaming": False,
            "supports_function_calling": False,
            "is_recommended": False,
            "is_active": True,
            "description": "火山引擎高质量视频生成模型"
        },
        # 火山引擎 - 图像模型
        {
            "id": "volcano-seedream-4-5",
            "provider_id": "volcano",
            "model_id": "Doubao-Seedream-4.5",
            "model_name": "Doubao-Seedream-4.5",
            "model_name_cn": "豆包Seedream-4.5",
            "model_type": "image",
            "capabilities": ["text-to-image", "image-to-image"],
            "context_window": 0,
            "max_tokens": 0,
            "input_cost_per_1k": 0,
            "output_cost_per_1k": 0,
            "supports_streaming": False,
            "supports_function_calling": False,
            "is_recommended": True,
            "is_active": True,
            "description": "豆包高质量图像生成模型"
        },
        
        # 百炼 - 文本模型
        {
            "id": "qianlian-qwen-3-5-plus",
            "provider_id": "qianlian",
            "model_id": "qwen3.5-plus",
            "model_name": "qwen3.5-plus",
            "model_name_cn": "千问3.5-Plus",
            "model_type": "chat",
            "capabilities": ["chat", "completion", "vision"],
            "context_window": 32768,
            "max_tokens": 4096,
            "input_cost_per_1k": 0.02,
            "output_cost_per_1k": 0.06,
            "supports_streaming": True,
            "supports_function_calling": False,
            "supports_vision": True,
            "is_recommended": True,
            "is_active": True,
            "description": "支持图片理解，千问3.5-Plus模型"
        },
        {
            "id": "qianlian-kimi-k2-5",
            "provider_id": "qianlian",
            "model_id": "kimi-k2.5",
            "model_name": "Moonshot-Kimi-K2.5",
            "model_name_cn": "Kimi-K2.5",
            "model_type": "chat",
            "capabilities": ["chat", "completion", "vision"],
            "context_window": 32768,
            "max_tokens": 4096,
            "input_cost_per_1k": 0.02,
            "output_cost_per_1k": 0.06,
            "supports_streaming": True,
            "supports_function_calling": False,
            "supports_vision": True,
            "is_recommended": False,
            "is_active": True,
            "description": "月之暗面Kimi模型，支持图片理解"
        },
        {
            "id": "qianlian-glm-5",
            "provider_id": "qianlian",
            "model_id": "glm-5",
            "model_name": "THUDM-GLM-5",
            "model_name_cn": "智谱GLM-5",
            "model_type": "chat",
            "capabilities": ["chat", "completion"],
            "context_window": 32768,
            "max_tokens": 4096,
            "input_cost_per_1k": 0.02,
            "output_cost_per_1k": 0.06,
            "supports_streaming": True,
            "supports_function_calling": False,
            "is_recommended": False,
            "is_active": True,
            "description": "智谱大语言模型GLM-5"
        },
        {
            "id": "qianlian-minimax-m2-5",
            "provider_id": "qianlian",
            "model_id": "MiniMax-M2.5",
            "model_name": "MiniMax-M2.5",
            "model_name_cn": "MiniMax-M2.5",
            "model_type": "chat",
            "capabilities": ["chat", "completion"],
            "context_window": 32768,
            "max_tokens": 4096,
            "input_cost_per_1k": 0.02,
            "output_cost_per_1k": 0.06,
            "supports_streaming": True,
            "supports_function_calling": False,
            "is_recommended": False,
            "is_active": True,
            "description": "MiniMax大语言模型M2.5"
        },

        # OpenAI - 文本模型
        {
            "id": "openai-gpt-4o",
            "provider_id": "openai",
            "model_id": "gpt-4o",
            "model_name": "gpt-4o",
            "model_name_cn": "GPT-4o",
            "model_type": "chat",
            "capabilities": ["chat", "vision", "function_calling", "json_mode"],
            "context_window": 128000,
            "max_tokens": 16384,
            "input_cost_per_1k": 2.5,
            "output_cost_per_1k": 10.0,
            "supports_streaming": True,
            "supports_function_calling": True,
            "supports_vision": True,
            "is_recommended": True,
            "is_active": True,
            "description": "OpenAI 最强旗舰模型，支持文本和图像理解"
        },
        {
            "id": "openai-gpt-4o-mini",
            "provider_id": "openai",
            "model_id": "gpt-4o-mini",
            "model_name": "gpt-4o-mini",
            "model_name_cn": "GPT-4o-mini",
            "model_type": "chat",
            "capabilities": ["chat", "vision", "function_calling", "json_mode"],
            "context_window": 128000,
            "max_tokens": 16384,
            "input_cost_per_1k": 0.15,
            "output_cost_per_1k": 0.6,
            "supports_streaming": True,
            "supports_function_calling": True,
            "supports_vision": True,
            "is_recommended": True,
            "is_active": True,
            "description": "轻量级旗舰模型，性价比高，支持文本和图像理解"
        },
        {
            "id": "openai-gpt-4-turbo",
            "provider_id": "openai",
            "model_id": "gpt-4-turbo",
            "model_name": "gpt-4-turbo",
            "model_name_cn": "GPT-4 Turbo",
            "model_type": "chat",
            "capabilities": ["chat", "vision", "function_calling", "json_mode"],
            "context_window": 128000,
            "max_tokens": 4096,
            "input_cost_per_1k": 10.0,
            "output_cost_per_1k": 30.0,
            "supports_streaming": True,
            "supports_function_calling": True,
            "supports_vision": True,
            "is_recommended": False,
            "is_active": True,
            "description": "GPT-4 高性能版，上下文窗口大"
        },
        {
            "id": "openai-gpt-3-5-turbo",
            "provider_id": "openai",
            "model_id": "gpt-3.5-turbo",
            "model_name": "gpt-3.5-turbo",
            "model_name_cn": "GPT-3.5 Turbo",
            "model_type": "chat",
            "capabilities": ["chat", "function_calling", "json_mode"],
            "context_window": 16385,
            "max_tokens": 4096,
            "input_cost_per_1k": 0.5,
            "output_cost_per_1k": 1.5,
            "supports_streaming": True,
            "supports_function_calling": True,
            "supports_vision": False,
            "is_recommended": False,
            "is_active": True,
            "description": "轻量快速模型，适合简单任务"
        },

        # OpenAI - 图像生成模型
        {
            "id": "openai-dall-e-3",
            "provider_id": "openai",
            "model_id": "dall-e-3",
            "model_name": "dall-e-3",
            "model_name_cn": "DALL-E 3",
            "model_type": "image",
            "capabilities": ["text-to-image"],
            "context_window": 0,
            "max_tokens": 0,
            "input_cost_per_1k": 0,
            "output_cost_per_1k": 0,
            "supports_streaming": False,
            "supports_function_calling": False,
            "supports_vision": False,
            "is_recommended": True,
            "is_active": True,
            "description": "OpenAI 高质量图像生成模型"
        },
        {
            "id": "openai-dall-e-2",
            "provider_id": "openai",
            "model_id": "dall-e-2",
            "model_name": "dall-e-2",
            "model_name_cn": "DALL-E 2",
            "model_type": "image",
            "capabilities": ["text-to-image", "image-edit", "variation"],
            "context_window": 0,
            "max_tokens": 0,
            "input_cost_per_1k": 0,
            "output_cost_per_1k": 0,
            "supports_streaming": False,
            "supports_function_calling": False,
            "supports_vision": False,
            "is_recommended": False,
            "is_active": True,
            "description": "OpenAI 图像生成模型"
        },

        # OpenAI - 视频生成模型 (Sora, 预留)
        {
            "id": "openai-sora",
            "provider_id": "openai",
            "model_id": "sora",
            "model_name": "sora",
            "model_name_cn": "OpenAI Sora",
            "model_type": "video",
            "capabilities": ["text-to-video", "image-to-video"],
            "context_window": 0,
            "max_tokens": 0,
            "input_cost_per_1k": 0,
            "output_cost_per_1k": 0,
            "supports_streaming": False,
            "supports_function_calling": False,
            "supports_vision": False,
            "is_recommended": False,
            "is_active": True,
            "description": "OpenAI 视频生成模型（即将发布）"
        },

        # 千问 - 文本模型
        {
            "id": "dashscope-qwen-long",
            "provider_id": "dashscope",
            "model_id": "qwen-long",
            "model_name": "qwen-long",
            "model_name_cn": "千问Long",
            "model_type": "chat",
            "capabilities": ["chat", "completion"],
            "context_window": 1000000,  # 100万token
            "max_tokens": 8192,
            "input_cost_per_1k": 0.5,
            "output_cost_per_1k": 2.0,
            "supports_streaming": True,
            "supports_function_calling": False,
            "is_recommended": True,
            "is_active": True,
            "description": "超长上下文模型，支持百万token，适合长篇小说生成"
        },
        {
            "id": "dashscope-qwen-plus",
            "provider_id": "dashscope",
            "model_id": "qwen-plus",
            "model_name": "qwen-plus",
            "model_name_cn": "千问Plus",
            "model_type": "chat",
            "capabilities": ["chat", "completion", "function_calling"],
            "context_window": 32768,
            "max_tokens": 8192,
            "input_cost_per_1k": 2.0,
            "output_cost_per_1k": 6.0,
            "supports_streaming": True,
            "supports_function_calling": True,
            "is_recommended": False,
            "is_active": True,
            "description": "均衡型模型，综合能力优秀"
        },
        {
            "id": "dashscope-qwen-coder-plus",
            "provider_id": "dashscope",
            "model_id": "qwen-coder-plus",
            "model_name": "qwen-coder-plus",
            "model_name_cn": "千问Coder Plus",
            "model_type": "chat",
            "capabilities": ["chat", "completion", "code_generation"],
            "context_window": 32768,
            "max_tokens": 8192,
            "input_cost_per_1k": 2.0,
            "output_cost_per_1k": 6.0,
            "supports_streaming": True,
            "supports_function_calling": False,
            "is_recommended": False,
            "is_active": True,
            "description": "代码生成旗舰模型，支持复杂规划"
        },
        {
            "id": "dashscope-qwen-vl-plus",
            "provider_id": "dashscope",
            "model_id": "qwen-vl-plus",
            "model_name": "qwen-vl-plus",
            "model_name_cn": "千问VL Plus",
            "model_type": "vision",
            "capabilities": ["chat", "vision", "image_understanding"],
            "context_window": 32768,
            "max_tokens": 2048,
            "input_cost_per_1k": 2.0,
            "output_cost_per_1k": 6.0,
            "supports_streaming": True,
            "supports_function_calling": False,
            "supports_vision": True,
            "is_recommended": True,
            "is_active": True,
            "description": "视觉语言模型，支持视频分镜生成"
        },
        {
            "id": "dashscope-qwen-turbo",
            "provider_id": "dashscope",
            "model_id": "qwen-turbo",
            "model_name": "qwen-turbo",
            "model_name_cn": "千问Turbo",
            "model_type": "chat",
            "capabilities": ["chat", "completion"],
            "context_window": 8192,
            "max_tokens": 2048,
            "input_cost_per_1k": 0.5,
            "output_cost_per_1k": 1.0,
            "supports_streaming": True,
            "supports_function_calling": False,
            "is_recommended": False,
            "is_active": True,
            "description": "轻量级模型，响应速度快"
        },

        # MiniMax - 文本生成模型
        {
            "id": "minimax-m3",
            "provider_id": "minimax",
            "model_id": "MiniMax-M3",
            "model_name": "MiniMax-M3",
            "model_name_cn": "MiniMax-M3",
            "model_type": "chat",
            "capabilities": ["chat", "completion", "function_calling", "json_mode", "reasoning", "vision", "multimodal", "long_context"],
            "context_window": 1000000,
            "max_tokens": 8192,
            "input_cost_per_1k": 0,
            "output_cost_per_1k": 0,
            "supports_streaming": True,
            "supports_function_calling": True,
            "supports_vision": True,
            "supports_json_mode": True,
            "is_recommended": True,
            "is_active": True,
            "description": "MiniMax M3 最新文本/多模态模型，1M 上下文，适合小说、剧本、角色提取、分镜规划和多模态理解",
            "version": "M3",
            "base_url": "https://api.minimaxi.com/v1"
        },
        {
            "id": "minimax-m2-7",
            "provider_id": "minimax",
            "model_id": "MiniMax-M2.7",
            "model_name": "MiniMax-M2.7",
            "model_name_cn": "MiniMax-M2.7",
            "model_type": "chat",
            "capabilities": ["chat", "completion", "function_calling", "json_mode", "reasoning"],
            "context_window": 1000000,
            "max_tokens": 8192,
            "input_cost_per_1k": 0,
            "output_cost_per_1k": 0,
            "supports_streaming": True,
            "supports_function_calling": True,
            "is_recommended": False,
            "is_active": True,
            "description": "MiniMax 最新旗舰模型，超长上下文，支持函数调用和推理"
        },
        # MiniMax - 图像生成模型
        {
            "id": "minimax-image-01",
            "provider_id": "minimax",
            "model_id": "image-01",
            "model_name": "MiniMax-image-01",
            "model_name_cn": "MiniMax图像生成",
            "model_type": "image",
            "capabilities": ["text-to-image"],
            "context_window": 0,
            "max_tokens": 0,
            "input_cost_per_1k": 0,
            "output_cost_per_1k": 0,
            "supports_streaming": False,
            "supports_function_calling": False,
            "is_recommended": True,
            "is_active": True,
            "description": "MiniMax 高质量图像生成，支持文生图/图生图，生成快速"
        },
        # MiniMax - TTS语音合成模型
        {
            "id": "minimax-speech-2-6-hd",
            "provider_id": "minimax",
            "model_id": "speech-2.6-hd",
            "model_name": "MiniMax-speech-2.6-hd",
            "model_name_cn": "MiniMax语音合成-HD",
            "model_type": "tts",
            "capabilities": ["text-to-speech"],
            "context_window": 0,
            "max_tokens": 0,
            "input_cost_per_1k": 0,
            "output_cost_per_1k": 0,
            "supports_streaming": False,
            "supports_function_calling": False,
            "is_recommended": True,
            "is_active": True,
            "description": "MiniMax 高质量语音合成，支持中文/英文/多语种，多种音色可选"
        },
    ]
    
    with Session(sync_engine) as session:
        # 插入服务商
        for p in providers:
            existing = session.query(LLMProvider).filter_by(name=p["name"]).first()
            if not existing:
                provider = LLMProvider(**p)
                session.add(provider)
                print(f"  ✓ 添加服务商: {p['name_cn']} ({p['name']})")
            else:
                print(f"  - 服务商已存在: {p['name_cn']} ({p['name']})")
        
        session.commit()
        
        # 插入模型
        for m in models:
            existing = session.query(LLMModel).filter_by(model_id=m["model_id"]).first()
            if not existing:
                model = LLMModel(**m)
                session.add(model)
                print(f"  ✓ 添加模型: {m['model_name_cn']} ({m['model_id']})")
            else:
                print(f"  - 模型已存在: {m['model_name_cn']} ({m['model_id']})")
        
        session.commit()
    
    print("\n✅ LLM服务商和模型初始化完成！")
    print(f"   - 服务商: {len(providers)} 个")
    print(f"   - 模型: {len(models)} 个")


if __name__ == "__main__":
    print("=" * 50)
    print("LLM服务商和模型初始化")
    print("=" * 50)
    init_llm_providers_and_models()
