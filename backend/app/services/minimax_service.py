"""
MiniMax API 服务
支持文本生成、图像生成、TTS语音合成

API调用规范:
- M3文本/多模态: POST /v1/text/chatcompletion_v2 → model_id = MiniMax-M3
- 旧文本模型: POST /v1/chat/completions  → model_id = MiniMax-M2.7
- 图像模型: POST /v1/image_generation → model_id = image-01
- TTS模型:   POST /v1/t2a_v2          → model_id = speech-2.6-hd
"""

from typing import List, Dict, Optional, Any
import aiohttp
import os
import uuid
import base64

from app.core.minimax_config import (
    MINIMAX_CONFIG,
    get_minimax_base_url,
    get_minimax_model,
    get_models_by_type,
    get_verified_by_type,
    DEFAULT_TEXT_MODEL,
    DEFAULT_IMAGE_MODEL,
    DEFAULT_TTS_MODEL,
    DEFAULT_TTS_VOICE,
    TTS_VOICES,
)


def _normalize_tts_model_id(model: str) -> str:
    """Convert local MiniMax catalog IDs to the API model ID used by /t2a_v2."""
    model_config = get_minimax_model(model)
    if model_config.get("type") == "tts" and model_config.get("api_model_id"):
        return model_config["api_model_id"]
    return model


def _normalize_image_model_id(model: str) -> str:
    """Convert local MiniMax catalog IDs to the API model ID used by /image_generation."""
    model_config = get_minimax_model(model)
    if model_config.get("type") == "image-generation" and model_config.get("api_model_id"):
        return model_config["api_model_id"]
    return model


def _raise_for_minimax_base_resp(result: Any, operation: str) -> None:
    if not isinstance(result, dict):
        return
    base_resp = result.get("base_resp") or result.get("baseResponse")
    if not isinstance(base_resp, dict):
        return
    status_code = base_resp.get("status_code")
    if status_code in (None, 0, "0"):
        return
    message = base_resp.get("status_msg") or base_resp.get("message") or "未知错误"
    raise Exception(f"MiniMax {operation}失败 [{status_code}]: {message}")


def _chat_endpoint_for_model(model: str) -> str:
    model_config = get_minimax_model(model)
    endpoint = model_config.get("endpoint")
    if endpoint and model_config.get("api_model_id") == "MiniMax-M3":
        return endpoint.replace("/v1/", "/")
    if model == "MiniMax-M3":
        return "/text/chatcompletion_v2"
    return "/chat/completions"


def _join_minimax_url(base_url: str, value: str, *, allow_plain: bool = True) -> Optional[str]:
    clean_value = value.strip()
    if not clean_value:
        return None
    if clean_value.startswith(("http://", "https://")):
        return clean_value
    if clean_value.startswith("/"):
        return base_url.rstrip("/") + clean_value
    return clean_value if allow_plain else None


def _extract_audio_url(value: Any, base_url: str, *, allow_plain: bool = True) -> Optional[str]:
    if isinstance(value, str):
        return _join_minimax_url(base_url, value, allow_plain=allow_plain)
    if isinstance(value, dict):
        for key in ("audio_url", "url", "file_url", "audio_file"):
            audio_url = _extract_audio_url(value.get(key), base_url, allow_plain=allow_plain)
            if audio_url:
                return audio_url
    return None


class MiniMaxService:
    """MiniMax API 服务类"""

    def __init__(self, api_key: str, base_url: Optional[str] = None):
        self.api_key = api_key
        self.base_url = base_url or get_minimax_base_url(api_key)
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

    # ============== 文本生成 ==============

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
        文本生成（对话补全）
        端点: M3 使用 /v1/text/chatcompletion_v2；旧文本模型使用 /v1/chat/completions
        模型: MiniMax-M3, MiniMax-M2.7, MiniMax-M2
        """
        url = f"{self.base_url}{_chat_endpoint_for_model(model)}"
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
                url, headers=self.headers, json=payload,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise Exception(f"MiniMax 文本生成失败 [{resp.status}]: {text}")
                return await resp.json()

    # ============== 图像生成 ==============

    async def generate_image(
        self,
        prompt: str,
        model: str = "image-01",
        aspect_ratio: str = "1:1",
        n: int = 1,
        response_format: str = "url",
        **kwargs
    ) -> Dict[str, Any]:
        """
        图像生成（文生图）
        端点: POST /v1/image_generation
        模型: image-01
        支持比例: 1:1, 16:9, 4:3, 3:2, 2:3, 3:4, 9:16, 21:9
        """
        api_model = _normalize_image_model_id(model)
        url = f"{self.base_url}/image_generation"
        payload = {
            "model": api_model,
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "n": min(n, 9),
            "response_format": response_format,
        }
        payload.update(kwargs)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, headers=self.headers, json=payload,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise Exception(f"MiniMax 图像生成失败 [{resp.status}]: {text}")
                result = await resp.json()
        _raise_for_minimax_base_resp(result, "图像生成")
        return result

    # ============== TTS语音合成 ==============

    async def text_to_speech(
        self,
        text: str,
        model: str = DEFAULT_TTS_MODEL,
        voice_id: str = DEFAULT_TTS_VOICE,
        speed: float = 1.0,
        vol: float = 1.0,
        pitch: float = 0,
        output_format: str = "url",
        output_dir: str = "audio",
        language_boost: str = "auto",
        **kwargs
    ) -> Dict[str, Any]:
        """
        文本转语音 (TTS)
        端点: POST /v1/t2a_v2
        模型: speech-2.6-hd, speech-2.6-turbo
        返回: 音频 URL 或 base64
        """
        api_model = _normalize_tts_model_id(model)
        speech_url = f"{self.base_url}/t2a_v2"
        payload = {
            "model": api_model,
            "text": text,
            "stream": False,
            "output_format": output_format,
            "voice_setting": {
                "voice_id": voice_id,
                "speed": speed,
                "vol": vol,
                "pitch": pitch,
            },
            "language_boost": language_boost,
        }
        payload.update(kwargs)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                speech_url, headers=self.headers, json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise Exception(f"MiniMax TTS失败 [{resp.status}]: {text}")
                result = await resp.json()

        _raise_for_minimax_base_resp(result, "TTS")

        # 解析响应
        # 同步返回: { "audio_content": "base64..." } 或
        # MiniMax v2: { "data": { "audio": "hex..." } } 或 { "data": { "audio_file": "url" } }
        audio_url = None
        audio_content = None
        task_id = str(uuid.uuid4())

        if "audio_content" in result:
            # 标准格式: base64 编码的音频
            audio_content = result["audio_content"]
            task_id = result.get("task_id", task_id)
        elif "data" in result and isinstance(result["data"], dict):
            data = result["data"]
            audio_url = (
                _extract_audio_url(data.get("audio_url"), self.base_url)
                or _extract_audio_url(data.get("url"), self.base_url)
                or _extract_audio_url(data.get("file_url"), self.base_url)
                or _extract_audio_url(data.get("audio_file"), self.base_url)
            )
            audio_value = data.get("audio")
            if not audio_url:
                audio_url = _extract_audio_url(audio_value, self.base_url, allow_plain=False)
            if not audio_url:
                if isinstance(audio_value, dict):
                    audio_content = audio_value.get("audio") or audio_value.get("audio_content") or audio_value.get("content")
                else:
                    audio_content = audio_value
                audio_content = audio_content or data.get("audio_content")
            else:
                audio_content = None
            task_id = result.get("task_id") or data.get("task_id") or task_id
        elif isinstance(result, dict):
            audio_content = result.get("audio_content") or result.get("audio")
            audio_url = (
                _extract_audio_url(result.get("audio_url"), self.base_url)
                or _extract_audio_url(result.get("url"), self.base_url)
                or _extract_audio_url(result.get("file_url"), self.base_url)
                or _extract_audio_url(result.get("audio_file"), self.base_url)
            )
            if audio_url:
                audio_content = None

        if audio_content:
            # 如果是 hex 编码，转换为 mp3 文件保存
            if output_format == "hex" or (isinstance(audio_content, str) and len(audio_content) > 1000):
                try:
                    audio_bytes = bytes.fromhex(audio_content)
                except ValueError:
                    # 如果不是 hex，当作 base64 处理
                    try:
                        audio_bytes = base64.b64decode(audio_content)
                    except Exception:
                        audio_bytes = None

                if audio_bytes:
                    static_base = os.path.join(
                        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "static"
                    )
                    audio_dir = os.path.join(static_base, output_dir)
                    os.makedirs(audio_dir, exist_ok=True)
                    filename = f"{task_id}.mp3"
                    audio_path = os.path.join(audio_dir, filename)
                    with open(audio_path, "wb") as f:
                        f.write(audio_bytes)
                    audio_url = f"/static/{output_dir}/{filename}"
                    estimated_duration = round(len(text) / (150 * speed), 1)
                    return {
                        "task_id": task_id,
                        "audio_url": audio_url,
                        "status": "succeeded",
                        "duration": estimated_duration,
                        "model": api_model,
                        "voice": voice_id,
                        "speed": speed,
                        "message": "TTS 转换成功"
                    }

            # 如果是 URL 格式
            if isinstance(audio_content, str) and audio_content.startswith("http"):
                audio_url = audio_content

        # 如果没有成功处理，返回原始响应
        if audio_url:
            estimated_duration = round(len(text) / (150 * speed), 1)
            return {
                "task_id": task_id,
                "audio_url": audio_url,
                "status": "succeeded",
                "duration": estimated_duration,
                "model": api_model,
                "voice": voice_id,
                "speed": speed,
                "message": "TTS 转换成功"
            }

        # 备用：直接返回原始响应
        result["status"] = "succeeded"
        result["voice"] = voice_id
        return result

    # ============== 成本计算 ==============

    def calculate_cost(self, model: str, input_tokens: int = 0, output_tokens: int = 0) -> float:
        """计算文本模型成本"""
        m = get_minimax_model(model)
        if not m:
            return 0.0
        ic = m.get("input_cost_per_1k", 0)
        oc = m.get("output_cost_per_1k", 0)
        return round((input_tokens / 1000) * ic + (output_tokens / 1000) * oc, 4)


# ============== 便捷函数 ==============

def create_minimax_service(api_key: str, base_url: Optional[str] = None) -> MiniMaxService:
    return MiniMaxService(api_key, base_url)
