"""
AI 服务模块
提供图片生成相关的 AI 服务
"""

import os
import json
import aiohttp
from typing import Optional
from app.core.config import settings


class AIService:
    """AI 服务类"""

    @staticmethod
    async def generate_cover_image(prompt: str) -> Optional[str]:
        """
        根据提示词生成封面图片

        Args:
            prompt: 图片描述提示词

        Returns:
            图片URL，失败返回None
        """
        # 如果配置了 OpenAI API Key，使用 DALL-E 生成
        if settings.OPENAI_API_KEY:
            return await AIService._generate_with_dalle(prompt)

        # 否则使用 Unsplash 作为备选（基于关键词搜索相关图片）
        return await AIService._generate_with_unsplash(prompt)

    @staticmethod
    async def _generate_with_dalle(prompt: str) -> Optional[str]:
        """使用 DALL-E 生成图片"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                }

                payload = {
                    "prompt": f"{prompt}, illustration, anime style, high quality, detailed",
                    "n": 1,
                    "size": "1024x1024",
                }

                async with session.post(
                    "https://api.openai.com/v1/images/generations",
                    json=payload,
                    headers=headers,
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data["data"][0]["url"]

        except Exception as e:
            print(f"DALL-E generation failed: {e}")

        return None

    @staticmethod
    async def _generate_with_unsplash(prompt: str) -> Optional[str]:
        """
        使用 Unsplash API 搜索相关图片
        作为备选方案
        """
        try:
            # 从提示词中提取关键词
            keywords = AIService._extract_keywords(prompt)

            # 使用 Picsum Photos 作为备选（无需API key）
            # 基于关键词生成一个稳定的 seed
            seed = hash(keywords) % 10000
            return f"https://picsum.photos/seed/{seed}/400/560"

        except Exception as e:
            print(f"Image search failed: {e}")

        return None

    @staticmethod
    def _extract_keywords(prompt: str) -> str:
        """从提示词中提取关键词"""
        # 移除常见描述词，保留核心内容
        stop_words = [
            "illustration",
            "anime",
            "style",
            "high",
            "quality",
            "detailed",
            "画面",
            "插画",
            "动漫",
            "风格",
        ]
        words = [w for w in prompt.split() if w.lower() not in stop_words]
        return " ".join(words[:5]) if words else prompt


ai_service = AIService()
