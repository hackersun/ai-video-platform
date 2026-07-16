"""豆包语音 V3 HTTP TTS 适配器。"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from time import perf_counter
from typing import Any, Callable
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import aiohttp


DEFAULT_RESOURCE_ID = "seed-tts-2.0"
DEFAULT_VOICE = "zh_female_vv_uranus_bigtts"
SUCCESS_CODES = {0, 20000000}
LEGACY_VOICE_ALIASES = {
    "female_nvsheng": DEFAULT_VOICE,
    "female_tianmei": DEFAULT_VOICE,
    "male_jiaqi": "zh_male_dayi_uranus_bigtts",
    "male_zhichang": "zh_male_dayi_uranus_bigtts",
    "male_dashu": "zh_male_dayi_uranus_bigtts",
}


@dataclass(frozen=True)
class VolcanoSpeechEndpoint:
    url: str
    app_id: str
    resource_id: str


def is_volcano_speech_tts_endpoint(base_url: str | None) -> bool:
    if not base_url:
        return False
    parsed = urlsplit(base_url)
    return (
        parsed.hostname == "openspeech.bytedance.com"
        and parsed.path.startswith("/api/v3/tts/")
    )


def configure_volcano_speech_endpoint(
    base_url: str | None,
    extra_params: dict[str, Any] | None,
) -> str | None:
    if not is_volcano_speech_tts_endpoint(base_url):
        return base_url
    params = extra_params or {}
    app_id = str(params.get("app_id") or params.get("appid") or "").strip()
    if not app_id:
        return base_url
    parsed = urlsplit(base_url or "")
    query = parse_qs(parsed.query)
    query["app_id"] = [app_id]
    query["resource_id"] = [str(params.get("resource_id") or DEFAULT_RESOURCE_ID)]
    flat_query = {key: values[-1] for key, values in query.items()}
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(flat_query), ""))


def parse_volcano_speech_endpoint(base_url: str) -> VolcanoSpeechEndpoint:
    if not is_volcano_speech_tts_endpoint(base_url):
        raise ValueError("不是受支持的豆包语音 V3 TTS 地址")
    parsed = urlsplit(base_url)
    query = parse_qs(parsed.query)
    app_id = (query.get("app_id") or query.get("appid") or [""])[0].strip()
    resource_id = (query.get("resource_id") or [DEFAULT_RESOURCE_ID])[0].strip()
    if not app_id:
        raise ValueError("豆包语音 TTS 配置缺少 app_id")
    endpoint_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    return VolcanoSpeechEndpoint(
        url=endpoint_url,
        app_id=app_id,
        resource_id=resource_id or DEFAULT_RESOURCE_ID,
    )


def normalize_volcano_speech_voice(voice: str | None) -> str:
    normalized = (voice or "").strip()
    return LEGACY_VOICE_ALIASES.get(normalized, normalized or DEFAULT_VOICE)


def parse_volcano_speech_events(payload: str) -> tuple[list[dict[str, Any]], bytes]:
    decoder = json.JSONDecoder()
    events: list[dict[str, Any]] = []
    audio_chunks: list[bytes] = []
    position = 0
    while position < len(payload):
        while position < len(payload) and payload[position].isspace():
            position += 1
        if position >= len(payload):
            break
        try:
            event, position = decoder.raw_decode(payload, position)
        except json.JSONDecodeError as exc:
            raise ValueError("豆包语音返回了无法解析的事件流") from exc
        if not isinstance(event, dict):
            raise ValueError("豆包语音返回了非对象事件")
        code = event.get("code")
        if code not in SUCCESS_CODES:
            message = str(event.get("message") or "unknown provider error")
            raise ValueError(f"豆包语音合成失败 [{code}]: {message}")
        if event.get("data"):
            try:
                audio_chunks.append(base64.b64decode(event["data"], validate=True))
            except (ValueError, TypeError) as exc:
                raise ValueError("豆包语音返回了无效的音频分片") from exc
        events.append(event)
    if not events or events[-1].get("code") != 20000000:
        raise ValueError("豆包语音事件流未正常结束")
    audio = b"".join(audio_chunks)
    if not audio:
        raise ValueError("豆包语音合成成功但未返回音频")
    return events, audio


def _save_audio(audio: bytes, output_dir: str) -> tuple[str, str]:
    static_root = Path(__file__).resolve().parents[2] / "static"
    relative_dir = Path(output_dir.strip("/"))
    if ".." in relative_dir.parts:
        raise ValueError("无效的 TTS 输出目录")
    audio_dir = static_root / relative_dir
    audio_dir.mkdir(parents=True, exist_ok=True)
    task_id = str(uuid4())
    audio_path = audio_dir / f"{task_id}.mp3"
    audio_path.write_bytes(audio)
    return task_id, f"/static/{relative_dir.as_posix()}/{audio_path.name}"


async def synthesize_volcano_speech_v3(
    *,
    access_token: str,
    base_url: str,
    text: str,
    voice: str,
    speed: float,
    output_dir: str,
) -> dict[str, Any]:
    endpoint = parse_volcano_speech_endpoint(base_url)
    resolved_voice = normalize_volcano_speech_voice(voice)
    request_id = str(uuid4())
    headers = {
        "X-Api-App-Id": endpoint.app_id,
        "X-Api-Access-Key": access_token,
        "X-Api-Resource-Id": endpoint.resource_id,
        "X-Api-Request-Id": request_id,
        "Content-Type": "application/json",
    }
    payload = {
        "user": {"uid": "ai-video-platform"},
        "req_params": {
            "text": text,
            "speaker": resolved_voice,
            "speed_ratio": speed,
            "audio_params": {"format": "mp3", "sample_rate": 24000},
        },
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            endpoint.url,
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=60),
        ) as response:
            response_text = await response.text()
            if response.status != 200:
                raise ValueError(f"豆包语音 HTTP 请求失败 [{response.status}]")
    _, audio = parse_volcano_speech_events(response_text)
    task_id, audio_url = _save_audio(audio, output_dir)
    duration = round(max(len(text) / (4.5 * max(speed, 0.1)), 0.1), 2)
    return {
        "task_id": task_id,
        "audio_url": audio_url,
        "status": "succeeded",
        "duration": duration,
        "model": endpoint.resource_id,
        "voice": resolved_voice,
        "speed": speed,
        "request_id": request_id,
        "message": "豆包语音 TTS 转换成功",
    }


async def test_volcano_speech_connection(
    access_token: str,
    base_url: str,
    message: str,
) -> dict[str, Any]:
    started_at = perf_counter()
    try:
        result = await synthesize_volcano_speech_v3(
            access_token=access_token,
            base_url=base_url,
            text=(message or "豆包语音连接测试。")[:120],
            voice=DEFAULT_VOICE,
            speed=1.0,
            output_dir="audio/previews",
        )
        elapsed_ms = int((perf_counter() - started_at) * 1000)
        return {
            "success": True,
            "message": "豆包语音 V3 连接成功",
            "response": result.get("audio_url"),
            "response_time_ms": elapsed_ms,
            "tokens_used": 0,
        }
    except Exception as exc:
        return {
            "success": False,
            "message": str(exc),
            "response": None,
            "response_time_ms": int((perf_counter() - started_at) * 1000),
            "tokens_used": 0,
        }


def route_volcano_speech_tts(
    legacy_method: Callable[..., Any],
) -> Callable[..., Any]:
    """仅为 openspeech 配置改走豆包语音 V3，保留原 Ark 行为。"""

    @wraps(legacy_method)
    async def routed(
        service: Any,
        text: str,
        model: str = "doubao-tts",
        voice: str = "female_nvsheng",
        speed: float = 1.0,
        output_dir: str = "audio",
        **kwargs: Any,
    ) -> dict[str, Any]:
        if not is_volcano_speech_tts_endpoint(service.base_url):
            return await legacy_method(
                service,
                text=text,
                model=model,
                voice=voice,
                speed=speed,
                output_dir=output_dir,
                **kwargs,
            )
        return await synthesize_volcano_speech_v3(
            access_token=service.api_key,
            base_url=service.base_url,
            text=text,
            voice=voice,
            speed=speed,
            output_dir=output_dir,
        )

    return routed
