"""
初始化数据 - 服务商和模型配置
"""
from app.core.database import SessionLocal
from app.models.provider import Provider
from app.models.ai_model import AIModel
import logging

logger = logging.getLogger(__name__)


def seed_providers_and_models():
    """初始化服务商和模型数据"""
    db = SessionLocal()
    
    try:
        # 检查是否已有数据
        existing_providers = db.query(Provider).count()
        if existing_providers > 0:
            logger.info("数据已存在，跳过初始化")
            return
        
        # ============ 创建服务商 ============
        
        # 火山引擎
        volcengine = Provider(
            code="volcengine",
            name="火山引擎",
            description="字节跳动旗下的云服务平台，提供方舟大模型",
            base_url="https://ark.cn-beijing.volces.com/api/v3",
            is_active=True
        )
        db.add(volcengine)
        db.flush()
        
        # Doubao (火山引擎子品牌)
        doubao = Provider(
            code="doubao",
            name="Doubao",
            description="豆包AI模型服务",
            base_url="https://ark.cn-beijing.volces.com/api/v3",
            is_active=True
        )
        db.add(doubao)
        db.flush()
        
        # OpenAI
        openai = Provider(
            code="openai",
            name="OpenAI",
            description="OpenAI官方API服务",
            base_url="https://api.openai.com/v1",
            is_active=True
        )
        db.add(openai)
        db.flush()
        
        # Anthropic
        anthropic = Provider(
            code="anthropic",
            name="Anthropic",
            description="Claude模型服务",
            base_url="https://api.anthropic.com/v1",
            is_active=True
        )
        db.add(anthropic)
        db.flush()
        
        # ============ 创建模型配置 ============
        
        # 火山引擎模型
        models_data = [
            # Doubao系列
            {"provider": doubao, "code": "doubao-seed-2.0-pro", "name": "Doubao Seed 2.0 Pro", "type": "llm", "max_tokens": 32000, "context_window": 128000},
            {"provider": doubao, "code": "doubao-seed-2.0lite", "name": "Doubao Seed 2.0 Lite", "type": "llm", "max_tokens": 16000, "context_window": 64000},
            {"provider": doubao, "code": "doubao-seed-2.5-pro", "name": "Doubao Seed 2.5 Pro", "type": "llm", "max_tokens": 64000, "context_window": 200000},
            
            # 火山引擎CVC视觉模型
            {"provider": volcengine, "code": "cvc-pixel", "name": "CVC-Pixel图像生成", "type": "image", "max_tokens": 4096},
            
            # OpenAI模型
            {"provider": openai, "code": "gpt-4o", "name": "GPT-4o", "type": "llm", "max_tokens": 16384, "context_window": 128000},
            {"provider": openai, "code": "gpt-4o-mini", "name": "GPT-4o Mini", "type": "llm", "max_tokens": 16384, "context_window": 128000},
            {"provider": openai, "code": "gpt-4-turbo", "name": "GPT-4 Turbo", "type": "llm", "max_tokens": 4096, "context_window": 128000},
            {"provider": openai, "code": "dall-e-3", "name": "DALL-E 3", "type": "image", "max_tokens": 4000},
            
            # Anthropic模型
            {"provider": anthropic, "code": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet", "type": "llm", "max_tokens": 8192, "context_window": 200000},
            {"provider": anthropic, "code": "claude-3-opus-20240229", "name": "Claude 3 Opus", "type": "llm", "max_tokens": 4096, "context_window": 200000},
        ]
        
        for md in models_data:
            model = AIModel(
                provider_id=md["provider"].id,
                model_code=md["code"],
                model_name=md["name"],
                model_type=md["type"],
                max_tokens=md.get("max_tokens", 4096),
                context_window=md.get("context_window", 8192),
                temperature=0.7,
                top_p=0.9,
                is_default=md["code"] == "gpt-4o",  # GPT-4o设为默认
                is_active=True
            )
            db.add(model)
        
        db.commit()
        logger.info("✅ 初始化数据创建成功")
        logger.info(f"   - 服务商: {4} 个")
        logger.info(f"   - 模型: {len(models_data)} 个")
        
    except Exception as e:
        logger.error(f"初始化数据失败: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    seed_providers_and_models()