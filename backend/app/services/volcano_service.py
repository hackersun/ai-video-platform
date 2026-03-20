"""
火山引擎（Volcano Engine）API 服务
支持豆包大模型、图像生成、视频生成、TTS语音合成
"""

import base64
import hashlib
import hmac
import time
from typing import List, Dict, Optional, AsyncGenerator
from datetime import datetime
import aiohttp

from app.core.volcano_config import VOLCANO_MODELS, get_volcano_model


class VolcanoService:
    """火山引擎 API 服务类"""

    # 文本生成 API (ARK)
    ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"

    # 图像/视频生成 API (视觉智能)
    VISUAL_BASE_URL = "https://visual.volcengine.com"

    def __init__(self, access_key: str, secret_key: str):
        self.access_key = access_key
        self.secret_key = secret_key
        self.headers = {
            "Content-Type": "application/json"
        }

    def _generate_auth_header(self, method: str, path: str, body: str = "") -> dict:
        """生成火山引擎签名认证"""
        # 这里简化处理，实际应使用完整的签名算法
        headers = {
            "Content-Type": "application/json",
            "X-Date": datetime.utcnow().strftime("%Y%m%dT%H%M%SZ"),
            "X-Access-Key": self.access_key
        }
        return headers

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

        headers = self._generate_auth_header("POST", "/chat/completions")
        headers["Authorization"] = f"Bearer {self.secret_key}"

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"API调用失败: {error_text}")

                return await response.json()

    async def generate_image(
        self,
        prompt: str,
        model: str = "Doubao-Seedream-4.5",
        size: str = "1024x1024",
        num: int = 1,
        **kwargs
    ) -> Dict:
        """
        图像生成

        Args:
            prompt: 图片描述
            model: 模型ID，如 Doubao-Seedream-4.5, Doubao-Seedream-5.0-lite
            size: 图片尺寸，如 512x512, 768x768, 1024x1024, 1024x1536, 1536x1024
            num: 生成数量
        """
        # 注意：图像生成API可能使用不同的端点，这里使用通用视觉API
        url = f"{self.VISUAL_BASE_URL}/api/v1/image/generate"

        payload = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "n": num
        }

        payload.update(kwargs)

        headers = self._generate_auth_header("POST", "/api/v1/image/generate")
        headers["Authorization"] = f"Bearer {self.secret_key}"

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=headers,
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
        duration: int = 4,
        resolution: str = "720p",
        image_url: Optional[str] = None,
        **kwargs
    ) -> Dict:
        """
        视频生成

        Args:
            prompt: 视频描述
            model: 模型ID，如 Doubao-Seed-2.0-pro
            duration: 视频时长(秒)，支持 4, 8, 10 秒
            resolution: 分辨率，如 720p, 1080p
            image_url: 可选，参考图片URL用于图生视频
        """
        url = f"{self.VISUAL_BASE_URL}/api/v1/video/generate"

        payload = {
            "model": model,
            "prompt": prompt,
            "duration": duration,
            "resolution": resolution
        }

        if image_url:
            payload["image_url"] = image_url

        payload.update(kwargs)

        headers = self._generate_auth_header("POST", "/api/v1/video/generate")
        headers["Authorization"] = f"Bearer {self.secret_key}"

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=headers,
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
        url = f"{self.VISUAL_BASE_URL}/api/v1/tts/synthesize"

        payload = {
            "model": model,
            "input": text,
            "voice": voice,
            "speed": speed
        }

        payload.update(kwargs)

        headers = self._generate_auth_header("POST", "/api/v1/tts/synthesize")
        headers["Authorization"] = f"Bearer {self.secret_key}"

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=headers,
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

        Args:
            video_url: 视频文件URL
            audio_url: 音频文件URL
            model: 合成模型
        """
        url = f"{self.VISUAL_BASE_URL}/api/v1/video/voice/synthesis"

        payload = {
            "model": model,
            "video_url": video_url,
            "audio_url": audio_url
        }

        payload.update(kwargs)

        headers = self._generate_auth_header("POST", "/api/v1/video/voice/synthesis")
        headers["Authorization"] = f"Bearer {self.secret_key}"

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=headers,
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
def create_volcano_service(access_key: str, secret_key: str) -> VolcanoService:
    """创建火山引擎服务实例"""
    return VolcanoService(access_key, secret_key)
