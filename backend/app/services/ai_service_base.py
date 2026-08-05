"""
AI 服务基类
提供统一的上下文管理、token估算、错误处理能力
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from fastapi import HTTPException
import re


# 各模型上下文窗口配置（token为单位）
MODEL_CONTEXT_WINDOWS = {
    # 阿里百炼模型
    "qwen3.5-plus": 32000,
    "qwen-long": 1000000,
    "kimi-k2.5": 128000,
    "glm-5": 128000,
    "minimax-m2.5": 128000,
    "qwen-plus": 128000,
    "qwen-turbo": 64000,
    # 默认值（约4K）
    "default": 4000,
    # DashScope 模型
    "qwen2-7b-instruct": 8000,
    "qwen2-72b-instruct": 8000,
}

# 默认输出token限制
DEFAULT_MAX_TOKENS = 4000

# Token估算：中文约 0.75 token/字，英文约 1.25 token/词
CHINESE_CHARS_PER_TOKEN = 1.5
ENGLISH_WORDS_PER_TOKEN = 1.0


def estimate_tokens(text: str) -> int:
    """
    估算文本的token数量
    简化算法：中文字符 * 0.75 + 英文单词 * 1.25
    """
    if not text:
        return 0
    # 中文字符数
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    # 英文单词数（粗略估算）
    english_words = len(re.findall(r'[a-zA-Z]+', text))
    # 其他字符
    other = len(text) - chinese_chars - english_words

    return int(chinese_chars / CHINESE_CHARS_PER_TOKEN +
               english_words / ENGLISH_WORDS_PER_TOKEN +
               other / 2)


def truncate_context(
    messages: List[Dict[str, str]],
    max_tokens: int = 4000,
    preserve_system: bool = True,
    system_prompt: str = ""
) -> List[Dict[str, str]]:
    """
    智能截断消息上下文，保持总token数不超过 max_tokens

    策略：
    1. 如果 system_prompt 存在，先截断 system_prompt
    2. 从最后往前删消息（保留最新对话）
    3. 如果单条消息过长，截断消息内容

    Args:
        messages: 消息列表 [{role: str, content: str}, ...]
        max_tokens: 最大token数
        preserve_system: 是否保留system消息（会截断但不会删除）
        system_prompt: system prompt 内容（单独传入时可以更精确控制）

    Returns:
        截断后的消息列表
    """
    result: List[Dict[str, str]] = []
    system_message: Optional[Dict[str, str]] = None
    current_tokens = 0
    system_tokens = 0

    # 先处理 system prompt
    if preserve_system and system_prompt:
        system_tokens = estimate_tokens(system_prompt)
        if system_tokens > max_tokens * 0.4:
            # system prompt 超过40%，截断它
            system_prompt = _truncate_text(system_prompt, int(max_tokens * 0.35))
            system_tokens = estimate_tokens(system_prompt)
        current_tokens += system_tokens
        system_message = {"role": "system", "content": system_prompt}

    # 反向遍历消息（从最新到最旧）
    for msg in reversed(messages):
        role = msg.get("role", "")
        if role == "system":
            continue  # system消息已经在上面处理

        content = msg.get("content", "")
        msg_tokens = estimate_tokens(content)

        if current_tokens + msg_tokens > max_tokens:
            # 需要截断这条消息或跳过它
            available = max_tokens - current_tokens
            if available < 50:
                break  # 剩余空间太小，跳过更早的消息
            truncated = _truncate_text(content, available)
            if truncated:
                result.insert(0, {"role": role, "content": truncated})
                current_tokens += estimate_tokens(truncated)
            break
        else:
            result.insert(0, {"role": role, "content": content})
            current_tokens += msg_tokens

    if system_message:
        result.insert(0, system_message)

    return result


def _truncate_text(text: str, max_tokens: int) -> str:
    """
    根据token数截断文本
    """
    if not text:
        return ""

    max_chars = int(max_tokens * CHINESE_CHARS_PER_TOKEN)

    # 如果文本本来就短，直接返回
    if len(text) <= max_chars:
        return text

    # 从末尾截断，保留前 max_chars 个字符
    # 但尽量在句号、换行处截断
    truncated = text[:max_chars]
    # 找到最后一个句号、换行或逗号
    for sep in ['\n\n', '\n', '。', '！', '？', '；', ',']:
        last_sep = truncated.rfind(sep)
        if last_sep > max_chars * 0.7:  # 至少保留70%
            truncated = truncated[:last_sep + len(sep)]
            break

    return truncated


def parse_api_error(error: Exception, raw_response: str = "") -> str:
    """
    解析API错误，返回中文友好的错误信息
    """
    error_str = str(error)
    error_lower = error_str.lower()

    if isinstance(error, TimeoutError):
        return "AI服务响应超时，请稍后重试。"

    # 上下文窗口超限
    if "context window exceeds" in error_lower or "context_length" in error_lower:
        return "输入内容过长，已超出模型上下文窗口限制。请减少章节数量或缩短文本长度。"

    if "maximum context" in error_lower:
        return "输入内容超出模型支持的最大长度。请精简内容后重试。"

    # 认证/密钥错误
    if "401" in error_str or "unauthorized" in error_lower or "invalid api key" in error_lower:
        return "API密钥无效或已过期。请检查LLM配置中的API Key。"

    if "authorized_error" in error_lower or "login fail" in error_lower:
        return "API密钥无效或已过期。请检查LLM配置中的API Key。"

    if "invalid message role" in error_lower:
        return "模型不支持当前消息角色格式，请检查文本模型服务适配。"

    # 权限/配额错误
    if "403" in error_str or "forbidden" in error_lower:
        return "API权限不足或配额用尽。请检查阿里百炼平台的账户余额。"

    # 限流
    if "429" in error_str or "rate limit" in error_lower or "too many requests" in error_lower:
        return "请求过于频繁，请稍后重试。"

    # 服务端错误
    if "500" in error_str or "502" in error_str or "503" in error_str or "internal" in error_lower:
        return "AI服务暂时不可用，请稍后重试。"

    # 超时
    if "timeout" in error_lower or "timed out" in error_lower:
        return "AI服务响应超时，请稍后重试。"

    # 尝试从原始响应中提取错误信息
    if raw_response:
        try:
            import json
            resp = json.loads(raw_response)
            if isinstance(resp, dict):
                # 尝试提取 error.message
                error_msg = resp.get("error", {}).get("message", "")
                if error_msg:
                    # 清理并简化错误信息
                    if "context window exceeds" in error_msg.lower():
                        return "输入内容过长，已超出模型上下文窗口限制。"
                    return f"AI服务返回错误：{error_msg[:100]}"
                # 尝试其他格式
                detail = resp.get("detail", "")
                if detail:
                    return str(detail)[:100]
        except:
            pass

    # 通用错误
    if error_str and len(error_str) < 200:
        return f"AI生成失败：{error_str}"
    return "AI生成失败，请稍后重试。"


class AIServiceBase(ABC):
    """
    AI服务基类
    所有具体的AI服务（QianlianService, DashScopeService等）都应继承此类
    """

    # 子类可覆盖这些属性
    DEFAULT_MODEL: str = "qwen3.5-plus"
    DEFAULT_MAX_TOKENS: int = 4000

    def __init__(self, api_key: str, base_url: Optional[str] = None):
        self.api_key = api_key
        self.base_url = base_url

    @abstractmethod
    async def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        聊天补全接口（子类必须实现）
        """
        pass

    def get_context_window(self, model: str) -> int:
        """获取模型的上下文窗口大小"""
        return MODEL_CONTEXT_WINDOWS.get(model, MODEL_CONTEXT_WINDOWS["default"])

    def prepare_messages(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str = "",
        max_context_tokens: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """
        准备消息列表：自动截断到上下文窗口大小

        Args:
            messages: 原始消息列表
            system_prompt: system prompt（可选）
            max_context_tokens: 最大上下文token（可选，默认用模型默认值）

        Returns:
            截断后的消息列表
        """
        # 从 messages 中提取 system prompt（如果存在）
        extracted_system = system_prompt
        if not extracted_system:
            for msg in messages:
                if msg.get("role") == "system":
                    extracted_system = msg.get("content", "")
                    break

        # 计算可用上下文窗口
        model = self.DEFAULT_MODEL
        max_tokens = max_context_tokens or self.DEFAULT_MAX_TOKENS
        max_input = self.get_context_window(model) - max_tokens - 100  # 留100 token余量

        if max_input < 1000:
            max_input = 1000

        # 智能截断
        return truncate_context(messages, max_tokens=max_input, preserve_system=True, system_prompt=extracted_system)

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
        安全的聊天补全：自动处理上下文截断和错误解析

        Raises:
            HTTPException: 中文友好的错误信息
        """
        # 自动截断上下文
        prepared = self.prepare_messages(messages, max_context_tokens=max_context_tokens)

        try:
            return await self.chat_completion(
                model=model,
                messages=prepared,
                temperature=temperature,
                max_tokens=max_tokens or self.DEFAULT_MAX_TOKENS,
                **kwargs
            )
        except Exception as e:
            error_msg = parse_api_error(e)
            raise HTTPException(status_code=400, detail=error_msg)
