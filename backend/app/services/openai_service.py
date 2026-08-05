"""
OpenAI API 服务
支持 GPT-4o, GPT-4o-mini, DALL-E, Sora 等模型

API文档: https://platform.openai.com/docs
"""

import os
import uuid
from typing import List, Dict, Optional, AsyncGenerator
from datetime import datetime
import aiohttp

from app.core.openai_config import OPENAI_CONFIG, OPENAI_MODELS, get_openai_model


class OpenAIService:
    """OpenAI API 服务类"""

    # API 基础地址
    BASE_URL = "https://api.openai.com/v1"

    def __init__(self, api_key: str, base_url: Optional[str] = None):
        self.api_key = api_key
        self.base_url = (base_url or self.BASE_URL).rstrip("/")
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
        request_timeout: float = 300,
        **kwargs
    ) -> Dict:
        """
        聊天补全 (文本生成)

        Args:
            model: 模型ID，如 gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            stream: 是否流式输出
        """
        url = f"{self.base_url}/chat/completions"

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
                timeout=aiohttp.ClientTimeout(total=request_timeout)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"OpenAI API调用失败: {error_text}")

                return await response.json()

    async def analyze_image(
        self,
        prompt: str,
        image_url: Optional[str] = None,
        image_base64: Optional[str] = None,
        model: str = "gpt-4o",
        detail: str = "high",
        **kwargs
    ) -> Dict:
        """
        图像理解 (Vision)

        Args:
            prompt: 分析提示词
            image_url: 图像URL（可选）
            image_base64: 图像Base64编码（可选）
            model: 模型ID，默认 gpt-4o
            detail: 图像细节级别 low, high, auto
        """
        url = f"{self.base_url}/chat/completions"

        content = []
        image_source = None

        if image_base64:
            image_source = {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_base64}",
                    "detail": detail
                }
            }
        elif image_url:
            image_source = {
                "type": "image_url",
                "image_url": {
                    "url": image_url,
                    "detail": detail
                }
            }

        if image_source:
            content.append(image_source)

        content.append({
            "type": "text",
            "text": prompt
        })

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": content
                }
            ],
            "max_tokens": 4096
        }
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
                    raise Exception(f"OpenAI Vision API调用失败: {error_text}")

                return await response.json()

    async def generate_image(
        self,
        prompt: str,
        model: str = "dall-e-3",
        size: str = "1024x1024",
        quality: str = "standard",
        n: int = 1,
        save_local: bool = True,
        **kwargs
    ) -> Dict:
        """
        图像生成 (DALL-E)

        Args:
            prompt: 图片描述
            model: 模型ID，dall-e-3 或 dall-e-2
            size: 图片尺寸: 1024x1024, 1024x1792, 1792x1024
            quality: 图片质量: standard, hd
            n: 生成数量 (DALL-E 3 仅支持1)
            save_local: 是否下载并保存到本地 static 目录

        Returns:
            包含 image_urls 的字典（可能包含本地路径）
        """
        url = f"{self.base_url}/images/generations"

        payload = {
            "model": model,
            "prompt": prompt,
            "n": n,
            "size": size,
            "quality": quality,
            "response_format": "url"
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
                    raise Exception(f"DALL-E API调用失败: {error_text}")

                result = await response.json()

        # 下载并保存到本地
        local_urls = []
        if save_local and "data" in result:
            for item in result["data"]:
                if isinstance(item, dict) and "url" in item:
                    image_url = item["url"]
                    try:
                        local_path = await self._download_and_save_image(image_url)
                        local_urls.append(local_path)
                    except Exception as e:
                        # 下载失败时使用原始URL
                        local_urls.append(image_url)

        return {
            "created": result.get("created"),
            "model": result.get("model", model),
            "images": result.get("data", []),
            "local_urls": local_urls if save_local else [],
            "task_id": str(uuid.uuid4())
        }

    async def _download_and_save_image(self, image_url: str) -> str:
        """下载图片并保存到本地 static/images 目录"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    image_url,
                    timeout=aiohttp.ClientTimeout(total=60),
                    headers={"Accept": "image/*"}
                ) as response:
                    if response.status != 200:
                        raise Exception(f"下载图片失败: HTTP {response.status}")

                    image_data = await response.read()

            # 确定文件扩展名
            content_type = response.headers.get("Content-Type", "")
            if "png" in content_type:
                ext = "png"
            elif "gif" in content_type:
                ext = "gif"
            elif "webp" in content_type:
                ext = "webp"
            else:
                ext = "png"

            # 保存到 static/images 目录
            static_base = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                "static"
            )
            images_dir = os.path.join(static_base, "images")
            os.makedirs(images_dir, exist_ok=True)

            filename = f"openai_{uuid.uuid4()}.{ext}"
            image_path = os.path.join(images_dir, filename)

            with open(image_path, "wb") as f:
                f.write(image_data)

            return f"/static/images/{filename}"

        except aiohttp.ClientError as e:
            raise Exception(f"下载图片网络错误: {str(e)}")
        except IOError as e:
            raise Exception(f"保存图片文件错误: {str(e)}")

    async def generate_video(
        self,
        prompt: str,
        model: str = "sora",
        duration: int = 10,
        aspect_ratio: str = "16:9",
        **kwargs
    ) -> Dict:
        """
        视频生成 (OpenAI Sora)

        注意: Sora 目前处于有限测试阶段，可能不可用。
        此方法作为占位符实现。

        Args:
            prompt: 视频描述
            model: 模型ID，默认 sora
            duration: 视频时长(秒)
            aspect_ratio: 宽高比: 16:9, 9:16, 1:1

        Returns:
            包含任务信息的字典
        """
        # Sora API 尚未正式公开，这里提供接口定义
        # 实际使用需要等待 OpenAI Sora 正式发布
        raise NotImplementedError(
            "OpenAI Sora 视频生成API尚未正式发布。"
            "当前可通过火山引擎进行视频生成。"
        )

    async def extract_characters(
        self,
        text: str,
        model: str = "gpt-4o",
        character_count: int = 5,
        **kwargs
    ) -> Dict:
        """
        从文本中提取角色信息

        Args:
            text: 待分析文本
            model: 模型ID，默认 gpt-4o
            character_count: 提取角色数量

        Returns:
            包含角色信息的响应
        """
        system_prompt = """你是一个专业的角色分析专家。你需要从给定的文本中识别和提取所有主要角色。

请为每个识别出的角色提取以下信息：
- name: 角色名称
- description: 角色简介/背景描述
- appearance: 外貌特征描述
- personality: 性格特点描述
- voice: 声音/语言特征描述
- tags: 角色标签列表（如：主角、反派、配角等）

请严格按照JSON格式输出一个角色数组，不要包含其他内容。
格式：
[
    {
        "name": "角色名",
        "description": "角色描述",
        "appearance": "外貌特征",
        "personality": "性格特点",
        "voice": "声音特征",
        "tags": ["主角", "英雄"]
    }
]"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请从以下文本中提取角色信息（最多{character_count}个主要角色）：\n\n{text}"}
        ]

        return await self.chat_completion(
            model=model,
            messages=messages,
            temperature=0.3,
            max_tokens=4000,
            **kwargs
        )

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """计算成本"""
        model_config = get_openai_model(model)
        if not model_config:
            return 0.0

        input_cost = (input_tokens / 1000) * model_config.get("input_cost_per_1k", 0)
        output_cost = (output_tokens / 1000) * model_config.get("output_cost_per_1k", 0)

        return round(input_cost + output_cost, 4)


# ============== 便捷函数 ==============

def create_openai_service(api_key: str) -> OpenAIService:
    """创建 OpenAI 服务实例"""
    return OpenAIService(api_key)


# 默认模型配置
DEFAULT_TEXT_MODEL = "gpt-4o-mini"
DEFAULT_VISION_MODEL = "gpt-4o"
DEFAULT_IMAGE_MODEL = "dall-e-3"
