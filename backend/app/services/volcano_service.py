"""
火山引擎（Volcano Engine）API 服务
支持豆包大模型系列 - 文本生成、图像生成、视频生成、TTS语音合成

API调用规范:
- 文本模型: POST /chat/completions       → model_id 传  模型ID（如 doubao-seed-1-8-251228）
- 图像模型: POST /images/generations    → model_id 传 ENDPOINT_ID（如 ep-20260320112226-rgndq）
- 视频模型: POST /contents/generations/tasks → model_id 传 ENDPOINT_ID（如 ep-20260322134751-fbglz）
"""

from typing import List, Dict, Optional, Any
import ipaddress
from urllib.parse import urlparse
import aiohttp

from app.features.video_generation.constants import PROVIDER_VIDEO_WATERMARK_ARG
from app.services.volcano_speech_tts import route_volcano_speech_tts

from app.core.volcano_config import (
    VOLCANO_CONFIG,
    ENDPOINT_IDS,
    get_volcano_model,
    get_models_by_type,
    get_verified_by_type,
    DEFAULT_TEXT_MODEL,
    DEFAULT_IMAGE_MODEL,
    DEFAULT_VIDEO_MODEL,
)


def _is_cloud_accessible_http_url(url: str) -> bool:
    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return False
    hostname = parsed.hostname
    if not hostname:
        return False
    host = hostname.lower()
    if host in {"localhost", "local"} or host.endswith(".local"):
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return True
    return ip.is_global


class VolcanoService:
    """火山引擎 API 服务类"""

    def __init__(self, api_key: str, base_url: Optional[str] = None):
        self.api_key = api_key
        # base_url: 支持用户自定义（如通过 LLMConfig.extra_params.base_url 传入）
        self.base_url = base_url or VOLCANO_CONFIG["base_url"]
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
        聊天补全（文本生成）
        端点: POST /chat/completions
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
                url, headers=self.headers, json=payload,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise Exception(f"文本生成失败 [{resp.status}]: {text}")
                return await resp.json()

    # ============== 图像生成 ==============

    async def generate_image(
        self,
        prompt: str,
        model: str = DEFAULT_IMAGE_MODEL,
        size: Optional[str] = None,
        num: int = 1,
        style: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        图像生成（同步模式 - 等待完成返回URL）
        端点: POST /images/generations
        模型: Doubao-Seedream-4.5, Doubao-Seedream-5.0-lite, doubao-seedream-5-0-260128
        """
        endpoint_id = ENDPOINT_IDS.get(model, model)

        # 构建 prompt
        full_prompt = prompt
        if style:
            full_prompt = f"{style}, {prompt}"

        # 尺寸映射：支持语义尺寸
        size_map = {
            "1k":    "1024x1024",   # 1048576 < 3686400 ❌ 不够
            "1.5k":  "1024x1536",   # 1572864 < 3686400 ❌ 不够
            "2k":    "2048x2048",     # 4194304 ✅
            "3k":    "2048x3072",    # 6291456 ✅
            "4k":    "3072x3072",    # 9437184 ✅
            "2k_h":  "1024x1792",   # 1835008 < 3686400 ❌ 不够
            "2k_w":  "1792x1024",   # 1835008 < 3686400 ❌ 不够
            "9:16":  "960x3840",     # 3686400 ✅
            "16:9":  "1920x1080",   # 2073600 < 3686400 ❌ 不够
        }
        seedream_50 = endpoint_id == "doubao-seedream-5-0-260128"
        if seedream_50:
            semantic_size = str(size or "2K").upper()
            resolved_size = semantic_size if semantic_size in {"1K", "2K", "4K"} else "2K"
        else:
            resolved_size = size_map.get(size, size) if size else "2048x2048"

        # 如果显式指定了像素数不够，自动扩大
        if not seedream_50:
            if resolved_size:
                try:
                    parts = resolved_size.split("x")
                    w, h = int(parts[0]), int(parts[1])
                    if w * h < 3686400:
                        # 等比放大到满足最小像素
                        scale = (3686400 / (w * h)) ** 0.5
                        new_w = int(w * scale)
                        new_h = int(h * scale)
                        # 调整为16的倍数
                        new_w = (new_w // 16) * 16
                        new_h = (new_h // 16) * 16
                        resolved_size = f"{new_w}x{new_h}"
                except (ValueError, IndexError):
                    resolved_size = "2048x2048"
            else:
                resolved_size = "2048x2048"

        payload = {
            "model": endpoint_id,
            "prompt": full_prompt,
            "size": resolved_size,
            "response_format": "url",
            "stream": False,
        }
        if seedream_50 and num > 1:
            payload.update({
                "sequential_image_generation": "auto",
                "sequential_image_generation_options": {"max_images": num},
            })
        elif not seedream_50:
            payload["n"] = num
        payload.update(kwargs)

        url = f"{self.base_url}/images/generations"
        request_timeout = 600 if endpoint_id == "doubao-seedream-5-0-260128" else 180
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, headers=self.headers, json=payload,
                timeout=aiohttp.ClientTimeout(total=request_timeout)
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise Exception(f"图像生成失败 [{resp.status}]: {text}")
                result = await resp.json()
                # 如果返回了直接的图片URL（同步模式），直接返回
                if result.get("data") and len(result["data"]) > 0:
                    first = result["data"][0]
                    if isinstance(first, dict) and first.get("url"):
                        return result
                # 否则需要查询任务状态（异步模式）
                task_id = result.get("id")
                if task_id:
                    image_url = await self._poll_image_task(task_id, endpoint_id, timeout=60)
                    return {"data": [{"url": image_url}], "id": task_id}
                return result

    async def _poll_image_task(self, task_id: str, model: str, timeout: int = 60) -> str:
        """轮询图片生成任务直到完成，返回图片URL"""
        import asyncio
        import time
        deadline = time.time() + timeout
        status_url = f"{self.base_url}/images/generations/tasks/{task_id}"
        async with aiohttp.ClientSession() as session:
            while time.time() < deadline:
                async with session.get(status_url, headers=self.headers,
                        timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        await asyncio.sleep(2)
                        continue
                    result = await resp.json()
                    status = result.get("status", "")
                    if status == "succeeded":
                        data = result.get("data", [])
                        if data and isinstance(data[0], dict) and data[0].get("url"):
                            return data[0]["url"]
                        raise Exception("图片生成成功但未找到图片URL")
                    elif status == "failed":
                        raise Exception(f"图片生成失败: {result.get('message', 'unknown')}")
                    # pending 或 processing，继续轮询
                    await asyncio.sleep(3)
            raise Exception(f"图片生成超时（{timeout}s）")

    # ============== 视频生成 ==============

    async def generate_video(
        self,
        prompt: str,
        model: str = DEFAULT_VIDEO_MODEL,
        image_url: Optional[str] = None,
        duration: int = 4,
        resolution: str = "720p",
        camerafixed: str = "false",
        watermark: str = PROVIDER_VIDEO_WATERMARK_ARG,
        seed: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        视频生成（图生视频/文生视频）
        端点: POST /contents/generations/tasks
        模型: Doubao-Seedance-1.0-pro-fast, Doubao-Seedance-1.5-pro
        """
        endpoint_id = ENDPOINT_IDS.get(model, model)

        # 构建 content
        content = []
        provider_image_url = image_url if image_url and _is_cloud_accessible_http_url(image_url) else None
        if provider_image_url:
            content.append({
                "type": "image_url",
                "image_url": {"url": provider_image_url}
            })

        provider_note = ""
        if image_url and not provider_image_url:
            provider_note = " 参考图不是公网可访问URL，云端调用不传image_url，请依据文字中的角色、场景和风格描述保持一致。"
        prompt_text = f"{prompt}{provider_note} --duration {duration} --resolution {resolution} --camerafixed {camerafixed} --watermark {watermark}"
        content.append({
            "type": "text",
            "text": prompt_text
        })

        payload = {
            "model": endpoint_id,
            "content": content,
        }
        if seed is not None:
            payload["seed"] = seed
        payload.update(kwargs)

        url = f"{self.base_url}/contents/generations/tasks"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, headers=self.headers, json=payload,
                timeout=aiohttp.ClientTimeout(total=300)
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise Exception(f"视频生成失败 [{resp.status}]: {text}")
                return await resp.json()

    async def get_video_status(self, task_id: str, model: str = DEFAULT_VIDEO_MODEL) -> Dict[str, Any]:
        """查询视频生成任务状态"""
        endpoint_id = ENDPOINT_IDS.get(model, model)
        url = f"{self.base_url}/contents/generations/tasks/{task_id}"
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, headers=self.headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise Exception(f"查询视频状态失败 [{resp.status}]: {text}")
                return await resp.json()

    async def video_voice_synthesis(
        self,
        video_url: str,
        audio_url: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Video/audio synthesis hook.
        """
        model = kwargs.pop("model", "volcano-synthesis")
        payload = {
            "model": model,
            "video_url": video_url,
            "audio_url": audio_url,
        }
        payload.update(kwargs)

        url = f"{self.base_url}/video/synthesis"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=300),
            ) as resp:
                if resp.status != 200:
                    text_body = await resp.text()
                    raise Exception(f"音视频合成失败 [{resp.status}]: {text_body}")
                return await resp.json()

    # ============== TTS语音合成 ==============

    @route_volcano_speech_tts
    async def text_to_speech(
        self,
        text: str,
        model: str = "doubao-tts",
        voice: str = "female_nvsheng",
        speed: float = 1.0,
        output_dir: str = "audio",
        **kwargs
    ) -> Dict[str, Any]:
        """
        文本转语音 (TTS)
        端点: POST /audio/speech
        """
        import os
        import uuid
        speech_url = f"{self.base_url}/audio/speech"
        speech_headers = {"Authorization": f"Bearer {self.api_key}"}

        payload = {
            "model": model,
            "input": text,
            "voice": voice,
            "speed": speed,
            "response_format": "mp3",
        }
        payload.update(kwargs)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    speech_url, headers=speech_headers, json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    if resp.status == 422:
                        return await self._tts_via_responses(text, model, voice, speed, output_dir, **kwargs)
                    if resp.status != 200:
                        text_body = await resp.text()
                        raise Exception(f"TTS失败 [{resp.status}]: {text_body}")
                    if hasattr(resp, "read"):
                        audio_data = await resp.read()
                    else:
                        result = await resp.json()
                        return {
                            "task_id": result.get("task_id") or str(uuid.uuid4()),
                            "audio_url": result.get("audio_url"),
                            "status": result.get("status", "succeeded"),
                            "duration": result.get("duration"),
                            "model": result.get("model", model),
                            "voice": voice,
                            "speed": speed,
                            "message": result.get("message", "TTS 转换成功"),
                        }
        except aiohttp.ClientError as e:
            if "422" in str(e):
                return await self._tts_via_responses(text, model, voice, speed, output_dir, **kwargs)
            raise Exception(f"TTS网络请求失败: {e}")

        task_id = str(uuid.uuid4())
        static_base = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "static"
        )
        audio_dir = os.path.join(static_base, output_dir)
        os.makedirs(audio_dir, exist_ok=True)
        filename = f"{task_id}.mp3"
        audio_path = os.path.join(audio_dir, filename)
        with open(audio_path, "wb") as f:
            f.write(audio_data)
        audio_url = f"/static/{output_dir}/{filename}"
        estimated_duration = round(len(text) / (150 * speed), 1)

        return {
            "task_id": task_id,
            "audio_url": audio_url,
            "status": "succeeded",
            "duration": estimated_duration,
            "model": model,
            "voice": voice,
            "speed": speed,
            "message": "TTS 转换成功"
        }

    async def _tts_via_responses(
        self, text: str, model: str, voice: str,
        speed: float, output_dir: str, **kwargs
    ) -> Dict[str, Any]:
        """TTS 回退：通过 Responses API 调用"""
        import os
        import uuid
        url = f"{self.base_url}/responses"
        payload = {
            "model": model,
            "input": [{"role": "user", "content": [
                {"type": "input_text", "text": text}
            ]}],
            "voice": voice,
            "speed": speed,
        }
        payload.update(kwargs)
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, headers=self.headers, json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as resp:
                if resp.status != 200:
                    text_body = await resp.text()
                    raise Exception(f"TTS Responses API失败 [{resp.status}]: {text_body}")
                result = await resp.json()

        audio_url = None
        task_id = result.get("id", str(uuid.uuid4()))
        output = result.get("output", {})
        if isinstance(output, dict):
            audio_url = output.get("audio_url") or output.get("url")
        elif isinstance(output, list):
            for item in output:
                if isinstance(item, dict) and item.get("type") == "audio":
                    audio_url = item.get("audio_url") or item.get("url")
                    break

        if not audio_url:
            raise Exception(f"TTS Responses API返回格式异常: {result}")

        if audio_url.startswith("http"):
            async with aiohttp.ClientSession() as session:
                async with session.get(audio_url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                    if resp.status != 200:
                        raise Exception(f"下载TTS音频失败: {resp.status}")
                    audio_data = await resp.read()
        else:
            raise Exception(f"TTS返回URL格式不支持: {audio_url}")

        static_base = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "static"
        )
        audio_dir = os.path.join(static_base, output_dir)
        os.makedirs(audio_dir, exist_ok=True)
        filename = f"{task_id}.mp3"
        audio_path = os.path.join(audio_dir, filename)
        with open(audio_path, "wb") as f:
            f.write(audio_data)
        final_url = f"/static/{output_dir}/{filename}"
        est_dur = round(len(text) / (150 * speed), 1)
        return {
            "task_id": task_id, "audio_url": final_url,
            "status": "succeeded", "duration": est_dur,
            "model": model, "voice": voice, "speed": speed,
            "message": "TTS 转换成功 (via Responses API)"
        }

    # ============== 成本计算 ==============

    def calculate_cost(self, model: str, input_tokens: int = 0, output_tokens: int = 0) -> float:
        """计算文本模型成本"""
        m = get_volcano_model(model)
        if not m:
            return 0.0
        ic = m.get("input_cost_per_1k", 0)
        oc = m.get("output_cost_per_1k", 0)
        return round((input_tokens / 1000) * ic + (output_tokens / 1000) * oc, 4)


# ============== 便捷函数 ==============

def create_volcano_service(api_key: str) -> VolcanoService:
    return VolcanoService(api_key)
