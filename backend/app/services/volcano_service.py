"""
火山引擎（Volcano Engine）API 服务
支持豆包大模型、图像生成、视频生成、TTS语音合成

API文档: https://www.volcengine.com/docs/82379
"""

from typing import List, Dict, Optional, AsyncGenerator
from datetime import datetime
import aiohttp

from app.core.volcano_config import VOLCANO_MODELS, get_volcano_model


class VolcanoService:
    """火山引擎 API 服务类"""

    # ARK API 基础地址 (文本、图像、视频生成共用)
    ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"

    # 模型Endpoint IDs (从控制台获取)
    ENDPOINT_IDS = {
        "Doubao-Seedream-4.5": "ep-20260320112226-rgndq",
        "Doubao-Seedream-5.0-lite": "ep-20260320113731-jzjkn",
        "Doubao-Seed-2.0-pro": "ep-20260320111926-sn9tg"
    }

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

    async def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs
    ) -> Dict:
        """
        聊天补全 (文本生成)

        Args:
            model: 模型ID，如 doubao-seed-1-8-251228
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            stream: 是否流式输出
        """
        url = f"{self.ARK_BASE_URL}/chat/completions"

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        payload.update(kwargs)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"文本生成API调用失败: {error_text}")

                return await response.json()

    async def generate_image(
        self,
        prompt: str,
        model: str = "Doubao-Seedream-4.5",
        size: str = "2K",
        num: int = 1,
        watermark: bool = True,
        **kwargs
    ) -> Dict:
        """
        图像生成

        Args:
            prompt: 图片描述
            model: 模型ID，如 Doubao-Seedream-4.5, Doubao-Seedream-5.0-lite
            size: 图片尺寸，支持 2K, 4K 等
            num: 生成数量
            watermark: 是否添加水印
        """
        url = f"{self.ARK_BASE_URL}/images/generations"

        # 获取Endpoint ID
        endpoint_id = self.ENDPOINT_IDS.get(model, model)

        payload = {
            "model": endpoint_id,
            "prompt": prompt,
            "size": size,
            "n": num,
            "response_format": "url",
            "stream": False,
            "watermark": watermark
        }

        payload.update(kwargs)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=180)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"图像生成API调用失败: {error_text}")

                return await response.json()

    async def generate_video(
        self,
        prompt: str,
        model: str = "Doubao-Seed-2.0-pro",
        image_url: Optional[str] = None,
        duration: int = 4,
        **kwargs
    ) -> Dict:
        """
        视频生成 (通过Responses API)

        Args:
            prompt: 视频描述
            model: 模型ID，如 Doubao-Seed-2.0-pro
            image_url: 可选，参考图片URL用于图生视频
            duration: 视频时长(秒)，支持 4, 8, 10 秒
        """
        url = f"{self.ARK_BASE_URL}/responses"

        # 构建消息内容
        content = []
        if image_url:
            content.append({
                "type": "input_image",
                "image_url": image_url
            })
        content.append({
            "type": "input_text",
            "text": prompt
        })

        payload = {
            "model": model,  # 使用模型名称而非Endpoint ID
            "input": [
                {
                    "role": "user",
                    "content": content
                }
            ]
        }

        payload.update(kwargs)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=300)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"视频生成API调用失败: {error_text}")

                return await response.json()

    async def text_to_speech(
        self,
        text: str,
        model: str = "Doubao-Seedream-5.0-lite",
        voice: str = "default",
        speed: float = 1.0,
        **kwargs
    ) -> Dict:
        """
        文本转语音 (TTS)

        Args:
            text: 要转换的文本
            model: TTS模型
            voice: 音色选择
            speed: 语速，1.0为正常速度
        """
        # 注意: TTS可能使用不同的API端点，这里暂用Responses API
        url = f"{self.ARK_BASE_URL}/responses"

        payload = {
            "model": model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": f"请将以下文本转换为语音: {text}"
                        }
                    ]
                }
            ]
        }

        payload.update(kwargs)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"TTS API调用失败: {error_text}")

                return await response.json()

    async def video_voice_synthesis(
        self,
        video_url: str,
        audio_url: str,
        model: str = "default",
        **kwargs
    ) -> Dict:
        """
        视频语音合成（将音频与视频合并）

        注意: 火山引擎的视频语音合成可能需要使用特定API
        """
        url = f"{self.ARK_BASE_URL}/responses"

        payload = {
            "model": " Doubao-Seed-2.0-pro",
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": f"将音频 {audio_url} 合成到视频 {video_url}"
                        }
                    ]
                }
            ]
        }

        payload.update(kwargs)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=300)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"视频语音合成API调用失败: {error_text}")

                return await response.json()

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """计算成本"""
        model_config = get_volcano_model(model)
        if not model_config:
            return 0.0

        input_cost = (input_tokens / 1000) * model_config.get("input_cost_per_1k", 0)
        output_cost = (output_tokens / 1000) * model_config.get("output_cost_per_1k", 0)

        return round(input_cost + output_cost, 4)


# 便捷函数
def create_volcano_service(api_key: str) -> VolcanoService:
    """创建火山引擎服务实例"""
    return VolcanoService(api_key)
