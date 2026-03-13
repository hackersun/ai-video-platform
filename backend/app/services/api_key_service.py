"""
用户API密钥配置服务
"""

from typing import List, Optional, Dict
from datetime import datetime
from uuid import UUID
import os
import json


# 模拟数据库（实际项目中应使用真实数据库）
_user_api_keys: Dict[str, List[Dict]] = {}


class APIKeyService:
    """API密钥管理服务"""

    # 支持的API提供商配置
    PROVIDERS = {
        "openai": {
            "id": "openai",
            "name": "OpenAI",
            "logo": "🤖",
            "description": "GPT系列模型",
            "required_params": ["api_key"],
            "base_url": "https://api.openai.com/v1",
            "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
            "type": "text_generation",
        },
        "anthropic": {
            "id": "anthropic",
            "name": "Anthropic",
            "logo": "🧠",
            "description": "Claude系列模型",
            "required_params": ["api_key"],
            "base_url": "https://api.anthropic.com",
            "models": ["claude-3-5-sonnet", "claude-3-opus", "claude-3-haiku"],
            "type": "text_generation",
        },
        "volcengine": {
            "id": "volcengine",
            "name": "火山引擎",
            "logo": "🌋",
            "description": "字节跳动AI服务",
            "required_params": ["api_key", "secret_key"],
            "base_url": "https://ark.cn-beijing.volces.com/api/v3",
            "models": ["doubao-pro-4k", "doubao-pro-32k", "qwen-vl-max", "cve-v1", "kling-v1"],
            "type": "multi",
        },
        "midjourney": {
            "id": "midjourney",
            "name": "Midjourney",
            "logo": "🎨",
            "description": "AI图像生成",
            "required_params": ["api_key", "server_id", "channel_id"],
            "base_url": "https://api.midjourney.ai",
            "models": ["midjourney", "niji-journey"],
            "type": "image_generation",
        },
        "runway": {
            "id": "runway",
            "name": "Runway",
            "logo": "🎬",
            "description": "AI视频生成",
            "required_params": ["api_key"],
            "base_url": "https://api.runwayml.com/v1",
            "models": ["gen3-alpha", "gen2"],
            "type": "video_generation",
        },
        "pika": {
            "id": "pika",
            "name": "Pika",
            "logo": "🎥",
            "description": "AI视频生成",
            "required_params": ["api_key"],
            "base_url": "https://api.pika.art",
            "models": ["pika-1.0", "pika-labs"],
            "type": "video_generation",
        },
        "suno": {
            "id": "suno",
            "name": "Suno",
            "logo": "🎵",
            "description": "AI音乐生成",
            "required_params": ["api_key"],
            "base_url": "https://api.suno.ai",
            "models": ["chirp-v3", "chirp-v3-5"],
            "type": "music_generation",
        },
        "elevenlabs": {
            "id": "elevenlabs",
            "name": "ElevenLabs",
            "logo": "🔊",
            "description": "AI语音合成",
            "required_params": ["api_key"],
            "base_url": "https://api.elevenlabs.io/v1",
            "models": ["eleven_multilingual_v2", "eleven_monolingual_v1"],
            "type": "voice_synthesis",
        },
        "doubao": {
            "id": "doubao",
            "name": "豆包",
            "logo": "🫛",
            "description": "字节跳动免费模型",
            "required_params": ["api_key"],
            "base_url": "https://ark.cn-beijing.volces.com/api/v3",
            "models": ["doubao-pro-4k", "doubao-lite-4k"],
            "type": "text_generation",
        },
        "kimi": {
            "id": "kimi",
            "name": "Kimi",
            "logo": "🌙",
            "description": "月之暗面AI助手",
            "required_params": ["api_key"],
            "base_url": "https://api.moonshot.cn/v1",
            "models": ["kimi-chat", "kimi-chat-128k"],
            "type": "text_generation",
        },
    }

    def get_providers(self) -> List[Dict]:
        """获取所有支持的提供商"""
        providers = []
        for pid, config in self.PROVIDERS.items():
            providers.append({
                "id": pid,
                "name": config["name"],
                "logo": config["logo"],
                "description": config["description"],
                "type": config["type"],
                "models": config["models"],
                "required_params": config["required_params"],
            })
        return providers

    def get_provider(self, provider_id: str) -> Optional[Dict]:
        """获取特定提供商配置"""
        return self.PROVIDERS.get(provider_id)

    def save_api_key(
        self,
        user_id: str,
        provider_id: str,
        credentials: Dict[str, str],
        name: str = None
    ) -> Dict:
        """
        保存用户API密钥
        
        Args:
            user_id: 用户ID
            provider_id: 提供商ID
            credentials: 凭据字典，如 {"api_key": "xxx", "secret_key": "yyy"}
            name: 密钥名称（可选）
            
        Returns:
            保存的API密钥配置
        """
        if provider_id not in self.PROVIDERS:
            raise ValueError(f"不支持的提供商: {provider_id}")
        
        provider_config = self.PROVIDERS[provider_id]
        
        # 验证必需参数
        for param in provider_config["required_params"]:
            if param not in credentials:
                raise ValueError(f"缺少必需参数: {param}")
        
        # 生成密钥ID
        key_id = f"key_{provider_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # 脱敏显示API key
        masked_credentials = {}
        for k, v in credentials.items():
            if k == "api_key" and v:
                masked_credentials[k] = v[:8] + "****" + v[-4:] if len(v) > 12 else "****"
            else:
                masked_credentials[k] = v
        
        api_key_config = {
            "id": key_id,
            "user_id": user_id,
            "provider_id": provider_id,
            "provider_name": provider_config["name"],
            "credentials": credentials,  # 实际应加密存储
            "masked_credentials": masked_credentials,
            "name": name or f"{provider_config['name']} API",
            "is_active": True,
            "is_default": False,
            "models": provider_config["models"],
            "created_at": datetime.utcnow().isoformat(),
            "last_used": None,
            "usage_count": 0,
        }
        
        # 保存到存储
        if user_id not in _user_api_keys:
            _user_api_keys[user_id] = []
        
        _user_api_keys[user_id].append(api_key_config)
        
        return api_key_config

    def get_user_api_keys(self, user_id: str) -> List[Dict]:
        """获取用户的所有API密钥"""
        keys = _user_api_keys.get(user_id, [])
        # 返回时隐藏真实凭据
        result = []
        for key in keys:
            result.append({
                "id": key["id"],
                "provider_id": key["provider_id"],
                "provider_name": key["provider_name"],
                "masked_credentials": key["masked_credentials"],
                "name": key["name"],
                "is_active": key["is_active"],
                "is_default": key["is_default"],
                "models": key["models"],
                "created_at": key["created_at"],
                "last_used": key["last_used"],
                "usage_count": key["usage_count"],
            })
        return result

    def delete_api_key(self, user_id: str, key_id: str) -> bool:
        """删除API密钥"""
        keys = _user_api_keys.get(user_id, [])
        for i, key in enumerate(keys):
            if key["id"] == key_id:
                keys.pop(i)
                return True
        return False

    def set_default_key(self, user_id: str, key_id: str) -> bool:
        """设置默认API密钥"""
        keys = _user_api_keys.get(user_id, [])
        for key in keys:
            key["is_default"] = (key["id"] == key_id)
        return True

    def toggle_key_active(self, user_id: str, key_id: str, active: bool) -> bool:
        """启用/禁用API密钥"""
        keys = _user_api_keys.get(user_id, [])
        for key in keys:
            if key["id"] == key_id:
                key["is_active"] = active
                return True
        return False

    def get_available_models(self, user_id: str) -> Dict:
        """获取用户可用的模型列表"""
        user_keys = self.get_user_api_keys(user_id)
        
        available = {
            "text_generation": [],
            "image_generation": [],
            "video_generation": [],
            "voice_synthesis": [],
            "music_generation": [],
        }
        
        for key in user_keys:
            if key["is_active"]:
                provider = self.get_provider(key["provider_id"])
                if provider:
                    model_type = provider["type"]
                    if model_type == "multi":
                        # 多类型提供商
                        for m in key["models"]:
                            if m in ["cve-v1", "kling-v1"]:
                                available["image_generation"].append({
                                    "id": m,
                                    "name": m,
                                    "provider_id": key["provider_id"],
                                    "provider_name": key["provider_name"],
                                    "api_key_id": key["id"],
                                })
                            elif m in ["doubao", "qwen"]:
                                available["text_generation"].append({
                                    "id": m,
                                    "name": m,
                                    "provider_id": key["provider_id"],
                                    "provider_name": key["provider_name"],
                                    "api_key_id": key["id"],
                                })
                    else:
                        for m in key["models"]:
                            if model_type in available:
                                available[model_type].append({
                                    "id": m,
                                    "name": m,
                                    "provider_id": key["provider_id"],
                                    "provider_name": key["provider_name"],
                                    "api_key_id": key["id"],
                                })
        
        return available


# 服务实例
api_key_service = APIKeyService()