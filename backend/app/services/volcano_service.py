"""
Volcano Engine (火山引擎) API 服务
支持豆包系列模型：Seedream-4.5、Seedream-5.0-lite、Seed-2.0-pro
"""

import json
import aiohttp
from typing import List, Dict, Optional, AsyncGenerator
from datetime import datetime


class VolcanoService:
    """Volcano Engine API 服务类"""
    
    BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
    
    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
    
    # ============== 图像生成模型 ==============
    
    async def generate_image(
        self,
        prompt: str,
        model: str = "Doubao-Seedream-4.5",
        size: str = "1024x1024",
        style: str = "auto",
        **kwargs
    ) -> Dict:
        """
        图像生成
        
        Args:
            prompt: 图片描述
            model: 模型ID，如 Doubao-Seedream-4.5, Doubao-Seedream-5.0-lite
            size: 图片尺寸，如 1024x1024, 768x1344, 1344x768
            style: 风格，如 auto, realistic, anime, cartoon
        
        Returns:
            API响应，包含图片URL
        """
        url = f"{self.BASE_URL}/images/generations"
        
        payload = {
            "model": model,
            "prompt": prompt,
            "image_size": size,
            "style": style,
            "number": kwargs.get("number", 1)
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=self.headers,
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"图像生成API调用失败: {error_text}")
                
                return await response.json()
    
    async def edit_image(
        self,
        prompt: str,
        image: str,
        model: str = "Doubao-Seedream-4.5",
        mask: Optional[str] = None,
        size: str = "1024x1024",
        **kwargs
    ) -> Dict:
        """
        图像编辑
        
        Args:
            prompt: 编辑指令
            image: 原图URL或base64
            model: 模型ID
            mask: 蒙版URL或base64（可选）
            size: 输出尺寸
        
        Returns:
            API响应
        """
        url = f"{self.BASE_URL}/images/edits"
        
        payload = {
            "model": model,
            "prompt": prompt,
            "image": image,
            "image_size": size
        }
        
        if mask:
            payload["mask"] = mask
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=self.headers,
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"图像编辑API调用失败: {error_text}")
                
                return await response.json()
    
    async def inpaint_image(
        self,
        prompt: str,
        image: str,
        mask: str,
        model: str = "Doubao-Seedream-4.5",
        **kwargs
    ) -> Dict:
        """
        图像局部重绘
        
        Args:
            prompt: 重绘指令
            image: 原图URL或base64
            mask: 蒙版URL或base64，标识需要重绘的区域
            model: 模型ID
        
        Returns:
            API响应
        """
        url = f"{self.BASE_URL}/images/edits"
        
        payload = {
            "model": model,
            "prompt": prompt,
            "image": image,
            "mask": mask,
            "image_size": kwargs.get("size", "1024x1024")
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=self.headers,
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"图像局部重绘API调用失败: {error_text}")
                
                return await response.json()
    
    async def outpaint_image(
        self,
        prompt: str,
        image: str,
        direction: str = "right",
        model: str = "Doubao-Seedream-4.5",
        **kwargs
    ) -> Dict:
        """
        图像局部扩展
        
        Args:
            prompt: 扩展内容描述
            image: 原图URL或base64
            direction: 扩展方向，left/right/top/bottom
            model: 模型ID
        
        Returns:
            API响应
        """
        url = f"{self.BASE_URL}/images/edits"
        
        payload = {
            "model": model,
            "prompt": prompt,
            "image": image,
            "direction": direction
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=self.headers,
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"图像扩展API调用失败: {error_text}")
                
                return await response.json()
    
    # ============== 视频生成模型 ==============
    
    async def generate_video(
        self,
        prompt: str,
        model: str = "Doubao-Seed-2.0-pro",
        duration: int = 5,
        resolution: str = "720p",
        **kwargs
    ) -> Dict:
        """
        文本生成视频
        
        Args:
            prompt: 视频描述
            model: 模型ID，如 Doubao-Seed-2.0-pro
            duration: 视频时长（秒），默认5秒
            resolution: 分辨率，如 480p, 720p, 1080p
        
        Returns:
            API响应，包含视频ID，后续可查询进度
        """
        url = f"{self.BASE_URL}/video/generations"
        
        payload = {
            "model": model,
            "prompt": prompt,
            "duration": duration,
            "resolution": resolution,
            **kwargs
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=self.headers,
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"视频生成API调用失败: {error_text}")
                
                return await response.json()
    
    async def generate_video_from_image(
        self,
        prompt: str,
        image: str,
        model: str = "Doubao-Seed-2.0-pro",
        duration: int = 5,
        resolution: str = "720p",
        **kwargs
    ) -> Dict:
        """
        图片生成视频
        
        Args:
            prompt: 视频描述
            image: 图片URL或base64
            model: 模型ID
            duration: 视频时长（秒）
            resolution: 分辨率
        
        Returns:
            API响应
        """
        url = f"{self.BASE_URL}/video/generations"
        
        payload = {
            "model": model,
            "prompt": prompt,
            "image": image,
            "duration": duration,
            "resolution": resolution,
            **kwargs
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=self.headers,
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"图生视频API调用失败: {error_text}")
                
                return await response.json()
    
    async def query_video_status(
        self,
        task_id: str,
        model: str = "Doubao-Seed-2.0-pro"
    ) -> Dict:
        """
        查询视频生成状态
        
        Args:
            task_id: 任务ID
            model: 模型ID
        
        Returns:
            任务状态信息
        """
        url = f"{self.BASE_URL}/video/generations/{task_id}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=self.headers
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"查询视频状态API调用失败: {error_text}")
                
                return await response.json()
    
    async def video_completion(
        self,
        prompt: str,
        model: str = "Doubao-Seed-2.0-pro",
        duration: int = 5,
        **kwargs
    ) -> Dict:
        """
        视频生成完整流程
        
        提交任务后轮询直到完成
        
        Args:
            prompt: 视频描述
            model: 模型ID
            duration: 时长
            poll_interval: 轮询间隔（秒）
            max_polls: 最大轮询次数
        
        Returns:
            完成的视频信息
        """
        poll_interval = kwargs.pop("poll_interval", 5)
        max_polls = kwargs.pop("max_polls", 60)
        
        # 提交任务
        result = await self.generate_video(
            prompt=prompt,
            model=model,
            duration=duration,
            **kwargs
        )
        
        task_id = result.get("id") or result.get("task_id")
        if not task_id:
            return result
        
        # 轮询等待完成
        for _ in range(max_polls):
            status_result = await self.query_video_status(task_id, model)
            
            status = status_result.get("status") or status_result.get("task_status")
            
            if status == "completed" or status == "succeed":
                return status_result
            
            if status == "failed" or status == "error":
                raise Exception(f"视频生成失败: {status_result.get('error', '未知错误')}")
            
            # 等待后继续轮询
            await asyncio.sleep(poll_interval)
        
        raise Exception("视频生成超时")
    
    # ============== 聊天补全（豆包文本模型） ==============
    
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
        聊天补全
        
        支持豆包系列模型：doubao-seed-1.8, doubao-pro-4k, doubao-lite-4k, doubao-pro-32k
        
        Args:
            model: 模型ID
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            stream: 是否流式输出
        
        Returns:
            API响应
        """
        url = f"{self.BASE_URL}/chat/completions"
        
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
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"API调用失败: {error_text}")
                
                return await response.json()
    
    async def chat_completion_stream(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        流式聊天补全
        """
        url = f"{self.BASE_URL}/chat/completions"
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True
        }
        
        if max_tokens:
            payload["max_tokens"] = max_tokens
        
        payload.update(kwargs)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=self.headers,
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"API调用失败: {error_text}")
                
                async for line in response.content:
                    line = line.decode('utf-8').strip()
                    if line.startswith('data:'):
                        data = line[5:].strip()
                        if data != '[DONE]':
                            yield data


# ============== 模型配置 ==============

VOLCANO_MODELS = {
    # 图像生成模型
    "Doubao-Seedream-4.5": {
        "type": "image-generation",
        "name": "豆包Seedream-4.5",
        "context_window": 4096,
        "max_tokens": 4096,
        "input_cost_per_1k": 0.05,
        "output_cost_per_1k": 0.05,
        "capabilities": ["text-to-image", "image-edit", "inpainting", "outpainting"],
        "sizes": ["768x1344", "1024x1024", "1344x768", "960x1280", "1280x960"],
        "styles": ["auto", "realistic", "anime", "cartoon"]
    },
    "Doubao-Seedream-5.0-lite": {
        "type": "image-generation",
        "name": "豆包Seedream-5.0-lite",
        "context_window": 4096,
        "max_tokens": 4096,
        "input_cost_per_1k": 0.02,
        "output_cost_per_1k": 0.02,
        "capabilities": ["text-to-image", "image-edit", "inpainting"],
        "sizes": ["768x1344", "1024x1024", "1344x768"],
        "styles": ["auto", "realistic", "anime", "cartoon"]
    },
    
    # 视频生成模型
    "Doubao-Seed-2.0-pro": {
        "type": "video-generation",
        "name": "豆包Seed-2.0-pro",
        "context_window": 4096,
        "max_tokens": 4096,
        "input_cost_per_1k": 0.5,
        "output_cost_per_1k": 0.5,
        "capabilities": ["text-to-video", "image-to-video", "video-edit"],
        "durations": [5, 10],
        "resolutions": ["480p", "720p", "1080p"]
    },
    
    # 文本生成模型
    "doubao-seed-1.8": {
        "type": "chat",
        "name": "豆包Seed-1.8",
        "context_window": 4096,
        "max_tokens": 2048,
        "input_cost_per_1k": 0.005,
        "output_cost_per_1k": 0.009,
        "capabilities": ["chat", "completion", "function_calling", "json_mode"]
    },
    "doubao-pro-4k": {
        "type": "chat",
        "name": "豆包Pro-4K",
        "context_window": 4096,
        "max_tokens": 4096,
        "input_cost_per_1k": 0.008,
        "output_cost_per_1k": 0.02,
        "capabilities": ["chat", "completion"]
    },
    "doubao-lite-4k": {
        "type": "chat",
        "name": "豆包Lite-4K",
        "context_window": 4096,
        "max_tokens": 4096,
        "input_cost_per_1k": 0.003,
        "output_cost_per_1k": 0.006,
        "capabilities": ["chat", "completion"]
    },
    "doubao-pro-32k": {
        "type": "chat",
        "name": "豆包Pro-32K",
        "context_window": 32768,
        "max_tokens": 8192,
        "input_cost_per_1k": 0.02,
        "output_cost_per_1k": 0.06,
        "capabilities": ["chat", "completion", "function_calling", "json_mode"]
    }
}


def get_volcano_model(model_id: str) -> Optional[Dict]:
    """获取火山引擎模型配置"""
    return VOLCANO_MODELS.get(model_id)


def calculate_volcano_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    """计算火山引擎模型成本"""
    model = VOLCANO_MODELS.get(model_id)
    if not model:
        return 0.0
    
    input_cost = (input_tokens / 1000) * model.get("input_cost_per_1k", 0)
    output_cost = (output_tokens / 1000) * model.get("output_cost_per_1k", 0)
    
    return input_cost + output_cost


# 默认模型配置
DEFAULT_IMAGE_MODEL = "Doubao-Seedream-4.5"
DEFAULT_VIDEO_MODEL = "Doubao-Seed-2.0-pro"
DEFAULT_TEXT_MODEL = "doubao-seed-1.8"


# ============== 便捷函数 ==============

async def create_volcano_service(api_key: str, api_secret: Optional[str] = None) -> VolcanoService:
    """创建Volcano服务实例"""
    return VolcanoService(api_key, api_secret)
