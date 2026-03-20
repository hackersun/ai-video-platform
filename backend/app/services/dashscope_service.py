"""
DashScope (阿里千问) API 服务
支持 qwen-turbo/plus/max/long/vl-plus 等模型
"""

import json
import aiohttp
from typing import List, Dict, Optional, AsyncGenerator
from datetime import datetime

from app.core.qwen_config import QWEN_MODELS, get_qwen_model, calculate_cost


class DashScopeService:
    """DashScope API 服务类"""
    
    BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    
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
        聊天补全
        
        Args:
            model: 模型ID，如 qwen-turbo, qwen-plus
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            stream: 是否流式输出
            **kwargs: 其他参数
        
        Returns:
            API响应
        """
        url = f"{self.BASE_URL}/chat/completions"
        
        # 验证模型
        model_config = get_qwen_model(model)
        if not model_config:
            raise ValueError(f"不支持的模型: {model}")
        
        # 构建请求体
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream
        }
        
        if max_tokens:
            payload["max_tokens"] = max_tokens
        
        # 添加其他参数
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
        
        Yields:
            SSE格式的数据块
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
    
    async def generate_novel(
        self,
        prompt: str,
        model: str = "qwen-long",
        max_tokens: int = 8000,
        temperature: float = 0.8
    ) -> Dict:
        """
        生成小说
        
        使用 qwen-long 模型，支持长文本生成（百万token上下文）
        """
        messages = [
            {
                "role": "system",
                "content": "你是一个专业的小说作家，擅长创作各种类型的小说。请根据用户的要求创作高质量的小说内容。"
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        return await self.chat_completion(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
    
    async def generate_storyboard(
        self,
        scene_description: str,
        model: str = "qwen-vl-plus",
        image_url: Optional[str] = None
    ) -> Dict:
        """
        生成视频分镜描述
        
        使用 qwen-vl-plus 视觉模型，结合图像理解生成分镜
        """
        messages = [
            {
                "role": "system",
                "content": "你是一个专业的视频分镜师，擅长将场景描述转化为详细的分镜脚本。请提供镜头角度、运镜方式、画面构图等专业建议。"
            }
        ]
        
        # 如果有图片URL，添加视觉输入
        if image_url:
            messages.append({
                "role": "user",
                "content": [
                    {"type": "image", "image": image_url},
                    {"type": "text", "text": f"根据这张参考图和以下场景描述，生成详细的分镜脚本：\n\n{scene_description}"}
                ]
            })
        else:
            messages.append({
                "role": "user",
                "content": f"请为以下场景生成分镜脚本：\n\n{scene_description}"
            })
        
        return await self.chat_completion(
            model=model,
            messages=messages,
            temperature=0.7,
            max_tokens=2000
        )
    
    async def understand_dialogue(
        self,
        user_input: str,
        context: Optional[List[Dict]] = None,
        model: str = "qwen-plus"
    ) -> Dict:
        """
        对话理解
        
        理解用户需求，提取关键信息
        """
        messages = [
            {
                "role": "system",
                "content": "你是一个智能助手，擅长理解用户的需求并提取关键信息。请分析用户的输入，识别意图、提取实体、判断情感。"
            }
        ]
        
        if context:
            messages.extend(context)
        
        messages.append({
            "role": "user",
            "content": user_input
        })
        
        return await self.chat_completion(
            model=model,
            messages=messages,
            temperature=0.7,
            max_tokens=1000
        )
    
    async def generate_coding_plan(
        self,
        requirement: str,
        model: str = "qwen-coder-plus",
        context: Optional[str] = None,
        language: Optional[str] = None
    ) -> Dict:
        """
        生成 Coding Plan（代码规划）
        
        使用 qwen-coder-plus 模型进行技术方案设计和代码规划
        
        Args:
            requirement: 需求描述
            model: 模型ID，默认 qwen-coder-plus
            context: 额外上下文信息
            language: 目标编程语言
        """
        system_prompt = """你是一个专业的技术架构师和代码规划专家。
请根据用户的需求，生成详细的 Coding Plan，包括：
1. 技术方案概述
2. 系统架构设计
3. 核心模块划分
4. 关键代码示例
5. 实现步骤规划
6. 注意事项和最佳实践

请以结构化的方式输出，便于开发人员理解和执行。"""

        user_prompt = f"需求描述：\n{requirement}\n\n"
        
        if language:
            user_prompt += f"目标语言：{language}\n\n"
        
        if context:
            user_prompt += f"额外上下文：\n{context}\n\n"
        
        user_prompt += "请生成详细的 Coding Plan："
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        return await self.chat_completion(
            model=model,
            messages=messages,
            temperature=0.7,
            max_tokens=4000
        )
    
    async def generate_novel_with_plan(
        self,
        prompt: str,
        model: str = "qwen-coder-plus",
        max_tokens: int = 8000
    ) -> Dict:
        """
        使用 Coding Plan 方式生成小说
        
        先规划情节架构，再生成具体内容
        """
        # 第一步：生成情节规划
        plan_prompt = f"""作为小说创作规划师，请为以下主题生成详细的小说创作规划：

主题：{prompt}

请提供：
1. 故事大纲（起承转合）
2. 主要角色设定
3. 关键情节节点
4. 章节规划
5. 写作风格和技巧建议

请以结构化的方式输出规划："""
        
        plan_messages = [
            {"role": "system", "content": "你是专业的小说创作规划师，擅长设计精彩的故事架构。"},
            {"role": "user", "content": plan_prompt}
        ]
        
        plan_response = await self.chat_completion(
            model=model,
            messages=plan_messages,
            temperature=0.8,
            max_tokens=2000
        )
        
        plan_content = plan_response["choices"][0]["message"]["content"]
        
        # 第二步：基于规划生成小说内容
        content_prompt = f"""基于以下规划，创作小说正文：

创作规划：
{plan_content}

原始主题：{prompt}

请创作第一章内容（约3000字）："""
        
        content_messages = [
            {"role": "system", "content": "你是专业的小说作家，擅长将规划转化为精彩的故事内容。"},
            {"role": "user", "content": content_prompt}
        ]
        
        content_response = await self.chat_completion(
            model="qwen-long",  # 使用长文本模型生成内容
            messages=content_messages,
            temperature=0.8,
            max_tokens=max_tokens
        )
        
        # 合并结果
        content = content_response["choices"][0]["message"]["content"]
        usage = content_response.get("usage", {})
        
        return {
            "plan": plan_content,
            "content": content,
            "usage": usage
        }
    
    async def generate_technical_storyboard(
        self,
        scene_description: str,
        technical_requirements: Optional[str] = None,
        model: str = "qwen-coder-plus"
    ) -> Dict:
        """
        生成技术分镜方案
        
        结合代码规划能力，生成技术实现导向的分镜
        """
        system_prompt = """你是专业的技术分镜师和视觉开发专家。
请为视频场景生成分镜方案，包含技术实现细节：

1. 镜头基本信息（编号、时长、景别）
2. 画面描述（构图、色彩、光影）
3. 技术实现方案（特效、动画、合成）
4. 代码/节点参考（如需要程序化生成）
5. 资源需求清单
6. 实现难度评估

请以结构化的方式输出，便于技术团队执行。"""

        user_prompt = f"场景描述：\n{scene_description}\n\n"
        
        if technical_requirements:
            user_prompt += f"技术要求：\n{technical_requirements}\n\n"
        
        user_prompt += "请生成技术分镜方案："
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        return await self.chat_completion(
            model=model,
            messages=messages,
            temperature=0.7,
            max_tokens=3000
        )
    
    def calculate_request_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """计算请求成本"""
        return calculate_cost(model, input_tokens, output_tokens)


# 便捷函数
async def create_dashscope_service(api_key: str) -> DashScopeService:
    """创建DashScope服务实例"""
    return DashScopeService(api_key)
