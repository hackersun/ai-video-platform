"""
阿里百炼 (Qianlian) API 服务
支持 qwen3.5-plus, kimi-k2.5, glm-5, MiniMax-M2.5 等模型
用于 Coding Plan 生成
"""

import json
import aiohttp
from typing import List, Dict, Optional, AsyncGenerator
from datetime import datetime


class QianlianService:
    """阿里百炼 API 服务类"""
    
    # Coding Plan 专用端点
    BASE_URL = "https://coding.dashscope.aliyuncs.com/v1"
    
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
            model: 模型ID，如 qwen3.5-plus, kimi-k2.5, glm-5, MiniMax-M2.5
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
        """流式聊天补全"""
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
    
    async def generate_coding_plan(
        self,
        requirement: str,
        model: str = "qwen3.5-plus",
        context: Optional[str] = None,
        language: Optional[str] = None
    ) -> Dict:
        """
        生成 Coding Plan（代码规划）
        
        使用百炼模型进行技术方案设计和代码规划
        
        Args:
            requirement: 需求描述
            model: 模型ID，默认 qwen3.5-plus
            context: 额外上下文信息
            language: 目标编程语言
        
        Returns:
            包含 Coding Plan 的响应
        """
        system_prompt = """你是一个专业的技术架构师和代码规划专家。
请根据用户的需求，生成详细的 Coding Plan，包括：

## 1. 技术方案概述
- 核心功能
- 技术选型理由

## 2. 系统架构设计
- 整体架构图描述
- 模块划分
- 数据流

## 3. 核心模块划分
- 各模块职责
- 模块间接口

## 4. 关键代码示例
- 核心算法
- 数据结构
- 关键函数

## 5. 实现步骤规划
- Phase 1: 基础框架
- Phase 2: 核心功能
- Phase 3: 优化完善

## 6. 注意事项和最佳实践
- 性能优化建议
- 安全注意事项
- 代码规范

请以结构化的 Markdown 格式输出，便于开发人员理解和执行。"""

        user_prompt = f"## 需求描述\n{requirement}\n\n"
        
        if language:
            user_prompt += f"## 目标编程语言\n{language}\n\n"
        
        if context:
            user_prompt += f"## 额外上下文\n{context}\n\n"
        
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
    
    async def generate_novel(
        self,
        prompt: str,
        model: str = "qwen3.5-plus",
        max_tokens: int = 8000,
        temperature: float = 0.8
    ) -> Dict:
        """
        生成小说
        
        使用百炼模型进行文本生成
        
        Args:
            prompt: 创作提示
            model: 模型ID
            max_tokens: 最大token数
            temperature: 温度参数
        
        Returns:
            包含生成内容的响应
        """
        messages = [
            {
                "role": "system",
                "content": """你是一个专业的小说作家，擅长创作各种类型的小说。
请根据用户的要求创作高质量的小说内容，注意：
- 情节曲折，人物鲜明
- 描写细腻，画面感强
- 对话自然，符合人物性格
- 适当设置悬念和冲突"""
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
    
    async def understand_dialogue(
        self,
        user_input: str,
        context: Optional[List[Dict]] = None,
        model: str = "qwen3.5-plus"
    ) -> Dict:
        """
        对话理解
        
        理解用户需求，提取关键信息
        
        Args:
            user_input: 用户输入
            context: 上下文消息
            model: 模型ID
        
        Returns:
            理解结果
        """
        messages = [
            {
                "role": "system",
                "content": """你是一个智能助手，擅长理解用户的需求并提取关键信息。
请分析用户的输入，识别：
1. 意图分类（创作、咨询、修改、其他）
2. 关键实体（人物、地点、事件等）
3. 情感倾向（积极、中性、消极）
4. 额外需求（风格偏好、长度要求等）

请以结构化的 JSON 格式输出。"""
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
    
    async def generate_storyboard(
        self,
        scene_description: str,
        model: str = "qwen3.5-plus",
        image_url: Optional[str] = None
    ) -> Dict:
        """
        生成视频分镜描述
        
        使用视觉模型结合图像理解生成分镜
        
        Args:
            scene_description: 场景描述
            model: 模型ID
            image_url: 参考图片URL（可选）
        
        Returns:
            分镜内容
        """
        messages = [
            {
                "role": "system",
                "content": """你是一个专业的视频分镜师，擅长将场景描述转化为详细的分镜脚本。
请提供：
1. 镜头基本信息（编号、时长、景别）
2. 画面描述（构图、色彩、光影）
3. 运镜方式（推、拉、摇、移、跟等）
4. 台词/配音建议
5. 配乐/音效建议

请以结构化的方式输出，便于拍摄和制作。"""
            }
        ]
        
        if image_url:
            messages.append({
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
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
    
    async def generate_novel_plan(
        self,
        theme: str,
        model: str = "qwen3.5-plus"
    ) -> Dict:
        """
        生成小说创作规划
        
        Args:
            theme: 小说主题
            model: 模型ID
        
        Returns:
            创作规划
        """
        system_prompt = """你是一个专业的小说创作规划师，擅长设计精彩的故事架构。

请为用户提供的小说主题生成详细的创作规划，包括：

## 1. 故事大纲
- 起始事件
- 核心冲突
- 高潮设计
- 结局安排

## 2. 主要角色设定
- 主角：背景、性格、成长弧线
- 配角：职责、特点
- 反派/障碍制造者

## 3. 关键情节节点
- 开端：引入主角和世界观
- 发展：冲突升级
- 高潮：最大冲突爆发
- 结局：解决与收尾

## 4. 章节规划
- 总章节数
- 每章核心内容

## 5. 写作风格建议
- 叙事视角
- 语言风格
- 描写技巧

请以结构化的 Markdown 格式输出。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"小说主题：{theme}\n\n请生成详细的创作规划："}
        ]
        
        return await self.chat_completion(
            model=model,
            messages=messages,
            temperature=0.8,
            max_tokens=3000
        )
    
    def calculate_request_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """计算请求成本"""
        model_config = QIANLIAN_MODELS.get(model, {})
        input_cost = (input_tokens / 1000) * model_config.get("input_cost_per_1k", 0)
        output_cost = (output_tokens / 1000) * model_config.get("output_cost_per_1k", 0)
        return input_cost + output_cost


# ============== 模型配置 ==============

QIANLIAN_MODELS = {
    "qwen3.5-plus": {
        "type": "vision",
        "name": "通义千问3.5-Plus",
        "context_window": 32768,
        "max_tokens": 4096,
        "input_cost_per_1k": 0.02,
        "output_cost_per_1k": 0.06,
        "capabilities": ["chat", "vision", "completion"]
    },
    "kimi-k2.5": {
        "type": "vision",
        "name": "月之暗面Kimi-K2.5",
        "context_window": 32768,
        "max_tokens": 4096,
        "input_cost_per_1k": 0.02,
        "output_cost_per_1k": 0.06,
        "capabilities": ["chat", "vision", "completion"]
    },
    "glm-5": {
        "type": "chat",
        "name": "智谱GLM-5",
        "context_window": 32768,
        "max_tokens": 4096,
        "input_cost_per_1k": 0.02,
        "output_cost_per_1k": 0.06,
        "capabilities": ["chat", "completion"]
    },
    "MiniMax-M2.5": {
        "type": "chat",
        "name": "MiniMax-M2.5",
        "context_window": 32768,
        "max_tokens": 4096,
        "input_cost_per_1k": 0.02,
        "output_cost_per_1k": 0.06,
        "capabilities": ["chat", "completion"]
    }
}


def get_qianlian_model(model_id: str) -> Optional[Dict]:
    """获取百炼模型配置"""
    return QIANLIAN_MODELS.get(model_id)


# 默认模型
DEFAULT_QIANLIAN_MODEL = "qwen3.5-plus"  # 百炼默认模型
DEFAULT_CODING_PLAN_MODEL = "qwen3.5-plus"  # Coding Plan默认使用百炼模型


# ============== 便捷函数 ==============

async def create_qianlian_service(api_key: str) -> QianlianService:
    """创建百炼服务实例"""
    return QianlianService(api_key)
