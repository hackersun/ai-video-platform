"""
阿里百炼 (Qianlian) API 服务
支持 qwen3.5-plus, kimi-k2.5, glm-5, MiniMax-M2.5 等模型
用于 Coding Plan 生成

注意：百炼使用 Anthropic 兼容 API 格式
API地址: https://coding.dashscope.aliyuncs.com/apps/anthropic
"""

import json
import aiohttp
from typing import List, Dict, Optional, Any, AsyncGenerator

from fastapi import HTTPException
from app.services.ai_service_base import (
    AIServiceBase,
    MODEL_CONTEXT_WINDOWS,
    DEFAULT_MAX_TOKENS,
    truncate_context,
    estimate_tokens,
)


# 百炼支持的模型配置
QIANLIAN_MODELS = {
    "qwen3.5-plus": {
        "name": "通义千问3.5-Plus",
        "context_window": 32000,
        "max_output": 4096,
        "vision": True,
    },
    "kimi-k2.5": {
        "name": "Moonshot-Kimi-K2.5",
        "context_window": 128000,
        "max_output": 4096,
        "vision": True,
    },
    "glm-5": {
        "name": "THUDM-GLM-5",
        "context_window": 128000,
        "max_output": 4096,
        "vision": False,
    },
    "minimax-m2.5": {
        "name": "MiniMax-M2.5",
        "context_window": 128000,
        "max_output": 4096,
        "vision": False,
    },
    "qwen-long": {
        "name": "通义千问-Long",
        "context_window": 1000000,
        "max_output": 8192,
        "vision": False,
    },
}


class QianlianService(AIServiceBase):
    """阿里百炼 API 服务类 (Anthropic 兼容格式)，继承自AIServiceBase"""

    DEFAULT_BASE_URL = "https://coding.dashscope.aliyuncs.com/apps/anthropic/v1"
    DEFAULT_MODEL = "qwen3.5-plus"
    DEFAULT_MAX_TOKENS = 4000

    def __init__(self, api_key: str, base_url: Optional[str] = None):
        super().__init__(api_key, base_url)
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "anthropic-version": "2023-06-01"
        }

    def get_context_window(self, model: str) -> int:
        """获取模型的上下文窗口大小"""
        model_cfg = QIANLIAN_MODELS.get(model, {})
        if model_cfg:
            return model_cfg.get("context_window", 32000)
        return MODEL_CONTEXT_WINDOWS.get(model, MODEL_CONTEXT_WINDOWS.get("default"))

    async def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        聊天补全 (Anthropic 兼容格式)

        百炼 Anthropic 兼容接口不支持独立的 system 角色，
        需要将 system 提示合并到第一条 user 消息中。
        """
        url = f"{self.base_url}/messages"

        # 提取 system prompt
        processed_messages = []
        system_prompt = ""

        for msg in messages:
            if msg.get("role") == "system":
                system_prompt += msg.get("content", "") + "\n\n"
            else:
                processed_messages.append(msg)

        # 如果有系统提示，合并到第一个用户消息
        if system_prompt and processed_messages:
            first_msg = processed_messages[0]
            if first_msg.get("role") == "user":
                first_msg["content"] = system_prompt.strip() + "\n\n" + first_msg.get("content", "")
            else:
                processed_messages.insert(0, {
                    "role": "user",
                    "content": system_prompt.strip()
                })

        # Anthropic 格式 payload
        payload: Dict[str, Any] = {
            "model": model,
            "messages": processed_messages,
            "temperature": temperature,
        }

        output_limit = max_tokens or self.DEFAULT_MAX_TOKENS
        # 确保不超出模型最大输出
        model_cfg = QIANLIAN_MODELS.get(model, {})
        if model_cfg:
            output_limit = min(output_limit, model_cfg.get("max_output", 4096))
        payload["max_tokens"] = output_limit

        payload.update(kwargs)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                error_text = ""
                if response.status != 200:
                    error_text = await response.text()
                    try:
                        err_json = await response.json()
                        err_msg = err_json.get("error", {}).get("message", err_json.get("message", ""))
                        err_type = err_json.get("error", {}).get("type", "unknown")
                        # 包含原始错误信息供解析
                        full_error = Exception(
                            f"[HTTP {response.status}] {err_type}: {err_msg}\n"
                            f"模型: {model}\n"
                            f"原始响应: {error_text[:500]}"
                        )
                        # 使用基类的错误解析
                        error_detail = self._parse_error(full_error, error_text)
                        raise HTTPException(status_code=error_detail[1], detail=error_detail[0])
                    except HTTPException:
                        raise
                    except Exception:
                        raise Exception(
                            f"[HTTP {response.status}] API调用失败\n"
                            f"响应内容: {error_text[:500]}"
                        )

                result = await response.json()

                # 提取文本内容（只取 type=text，忽略思考过程）
                content_list = result.get("content", [])
                text_content = ""
                for item in content_list:
                    if item.get("type") == "text":
                        text_content += item.get("text", "")

                if not text_content:
                    raise Exception(
                        f"API返回内容为空，请检查模型是否支持当前请求\n"
                        f"模型: {model}\n"
                        f"响应: {json.dumps(result, ensure_ascii=False)[:300]}"
                    )

                # 转换为 OpenAI 兼容格式返回
                return {
                    "choices": [{
                        "message": {
                            "role": "assistant",
                            "content": text_content
                        },
                        "finish_reason": result.get("stop_reason", "stop")
                    }],
                    "usage": result.get("usage", {}),
                    "model": model
                }

    def _parse_error(self, error: Exception, raw_response: str = "") -> tuple[str, int]:
        """
        解析API错误，返回(中文错误信息, HTTP状态码)
        """
        error_str = str(error)
        error_lower = error_str.lower()

        # 上下文窗口超限
        if "context window exceeds" in error_lower or "context_length" in error_lower:
            return ("输入内容过长，已超出模型上下文窗口限制。请精简输入内容后重试。", 400)
        if "maximum context" in error_lower:
            return ("输入内容超出模型支持的最大长度。请精简内容后重试。", 400)

        # 认证/密钥错误
        if "401" in error_str or "unauthorized" in error_lower or "invalid api key" in error_lower:
            return ("API密钥无效或已过期。请检查LLM配置中的API Key。", 401)

        # 权限/配额
        if "403" in error_str or "forbidden" in error_lower or "quota" in error_lower:
            return ("API权限不足或配额用尽。请检查阿里百炼平台的账户余额和套餐余量。", 403)

        # 限流
        if "429" in error_str or "rate limit" in error_lower or "too many requests" in error_lower:
            return ("请求过于频繁，请稍后重试。", 429)

        # 服务端错误
        if any(x in error_str for x in ["500", "502", "503"]) or "internal" in error_lower:
            return ("AI服务暂时不可用，请稍后重试。", 503)

        # 超时
        if "timeout" in error_lower or "timed out" in error_lower:
            return ("AI服务响应超时，请检查网络后重试。", 504)

        # 尝试从原始响应中提取
        if raw_response:
            try:
                resp = json.loads(raw_response)
                if isinstance(resp, dict):
                    err_msg = resp.get("error", {}).get("message", "")
                    if err_msg:
                        if "context window" in err_msg.lower():
                            return ("输入内容过长，已超出模型上下文窗口限制。", 400)
                        return (f"AI服务返回错误：{err_msg[:150]}", 400)
            except:
                pass

        # 通用
        if error_str and len(error_str) < 300:
            return (f"AI生成失败：{error_str}", 400)
        return ("AI生成失败，请稍后重试。", 400)

    async def safe_chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        max_context_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        安全的聊天补全：自动处理上下文截断和中文错误信息
        """
        # 提取 system prompt
        system_prompt = ""
        for msg in messages:
            if msg.get("role") == "system":
                system_prompt = msg.get("content", "")
                break

        # 智能截断
        context_window = self.get_context_window(model)
        output_tokens = max_tokens or self.DEFAULT_MAX_TOKENS
        max_input = context_window - output_tokens - 200  # 留200余量

        if max_input < 500:
            max_input = 500

        truncated = truncate_context(
            messages,
            max_tokens=max_input,
            preserve_system=True,
            system_prompt=system_prompt
        )

        try:
            return await self.chat_completion(
                model=model,
                messages=truncated,
                temperature=temperature,
                max_tokens=output_tokens,
                **kwargs
            )
        except Exception as e:
            error_detail, status_code = self._parse_error(e)
            raise HTTPException(status_code=status_code, detail=error_detail)

    async def chat_completion_stream(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """流式聊天补全 (Anthropic 兼容格式)"""
        url = f"{self.base_url}/messages"

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True
        }

        if max_tokens is None:
            max_tokens = 4096
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
                    try:
                        err_json = await response.json()
                        err_msg = err_json.get("error", {}).get("message", error_text)
                        raise Exception(f"[HTTP {response.status}] {err_msg}")
                    except Exception:
                        raise Exception(f"[HTTP {response.status}] API调用失败: {error_text[:300]}")

                async for line in response.content:
                    line = line.decode('utf-8').strip()
                    if line.startswith('data:'):
                        data = line[5:].strip()
                        if data != '[DONE]':
                            yield data


def get_qianlian_model(model_id: str) -> Optional[Dict]:
    """获取百炼模型配置"""
    return QIANLIAN_MODELS.get(model_id)


DEFAULT_QIANLIAN_MODEL = "qwen3.5-plus"
DEFAULT_CODING_PLAN_MODEL = "qwen3.5-plus"


async def create_qianlian_service(api_key: str, base_url: Optional[str] = None) -> QianlianService:
    """创建百炼服务实例"""
    return QianlianService(api_key, base_url)
