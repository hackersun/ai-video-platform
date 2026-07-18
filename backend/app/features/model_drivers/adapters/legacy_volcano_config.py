"""Compatibility-only legacy Volcano connection-test helpers."""

import httpx

from app.core.volcano_agent_plan_config import VOLCANO_AGENT_PLAN_BASE_URL
from app.features.video_generation.constants import PROVIDER_VIDEO_WATERMARK_ARG


_IMAGE_MODEL_IDS = {
    "Doubao-Seedream-4.5", "Doubao-Seedream-5.0-lite",
    "volcano-seedream-4.5", "volcano-seedream-5.0-lite",
}
_VIDEO_MODEL_IDS = {
    "Doubao-Seedance-1.5-pro", "Doubao-Seedance-1.0-pro-fast",
    "Doubao-Seedance-2.0", "Doubao-Seedance-2.0-fast",
    "doubao-seedance-1-5-pro-251215", "doubao-seedance-2-0-260128",
    "doubao-seedance-2-0-fast-260128", "volcano-seedance-1-5-pro",
    "volcano-seedance-1-0-pro-fast", "volcano-seedance-2-0", "volcano-seedance-2-0-fast",
}


def _volcano_request(model_id: str, message: str) -> tuple[str, str, str, dict]:
    from app.core.volcano_config import VOLCANO_MODELS, get_endpoint_id

    config = next((item for item in VOLCANO_MODELS if item["id"] == model_id), {})
    model_type = config.get("type", "text-generation")
    if model_type == "text-generation":
        model_type = ("image-generation" if model_id in _IMAGE_MODEL_IDS else
                      "video-generation" if model_id in _VIDEO_MODEL_IDS else model_type)
    actual_model = get_endpoint_id(model_id)
    base_url = "https://ark.cn-beijing.volces.com/api/v3"
    if model_type == "video-generation":
        return model_type, actual_model, f"{base_url}/contents/generations/tasks", {
            "model": actual_model,
            "content": [{"type": "text", "text": (
                f"{message} --duration 4 --resolution 720p --camerafixed true "
                f"--watermark {PROVIDER_VIDEO_WATERMARK_ARG}"
            )}],
        }
    if model_type == "image-generation":
        return model_type, actual_model, f"{base_url}/images/generations", {
            "model": actual_model, "prompt": message[:200], "size": "2048x2048",
            "n": 1, "response_format": "url",
        }
    return model_type, actual_model, f"{base_url}/chat/completions", {
        "model": actual_model, "messages": [{"role": "user", "content": message}], "max_tokens": 100,
    }


def _volcano_success(result: dict, model_type: str, elapsed_ms: int) -> dict:
    if model_type == "video-generation":
        task_id = result.get("id", "unknown")
        return {"success": True, "message": f"火山引擎视频模型 API 连接成功！任务ID: {task_id}",
                "response": f"任务已提交: {task_id}", "response_time_ms": elapsed_ms, "tokens_used": 0}
    if model_type == "image-generation":
        return {"success": True, "message": "火山引擎图像模型 API 连接成功！",
                "response": result.get("data", [{}])[0].get("url", "响应成功"),
                "response_time_ms": elapsed_ms, "tokens_used": 0}
    return {"success": True, "message": "火山引擎 API 连接成功！",
            "response": result.get("choices", [{}])[0].get("message", {}).get("content", "响应成功"),
            "response_time_ms": elapsed_ms, "tokens_used": result.get("usage", {}).get("total_tokens", 0)}


def _response_error(response) -> str:
    try:
        payload = response.json()
        return payload.get("error", {}).get("message", payload.get("message", response.text[:200]))
    except Exception:
        return response.text[:200]


async def test_volcano_api(api_key: str, model_id: str, message: str) -> dict:
    """Preserve the legacy direct-test contract for compatibility callers."""
    model_type, _actual_model, url, data = _volcano_request(model_id, message)
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=data, headers=headers)
            elapsed_ms = int(response.elapsed.total_seconds() * 1000)
            if response.status_code == 200:
                return _volcano_success(response.json(), model_type, elapsed_ms)
            return {"success": False,
                    "message": f"[HTTP {response.status_code}] API错误: {_response_error(response)}\n模型ID: {model_id} | 端点: {url}",
                    "response": None, "response_time_ms": elapsed_ms, "tokens_used": 0}
    except httpx.TimeoutException:
        return {"success": False, "message": f"连接超时(30s)，请检查网络或API地址是否正确\n请求地址: {url}",
                "response": None, "response_time_ms": 30000, "tokens_used": 0}
    except httpx.ConnectError as error:
        return {"success": False, "message": f"连接失败，无法访问API地址: {error}\n请求地址: {url}",
                "response": None, "response_time_ms": 0, "tokens_used": 0}
    except Exception as error:
        return {"success": False, "message": f"测试异常: {str(error)[:300]}", "response": None,
                "response_time_ms": 0, "tokens_used": 0}


def _is_video_model_id(model_id: str) -> bool:
    return any(key in model_id for key in ("seedance", "video"))


def _is_image_model_id(model_id: str) -> bool:
    return any(key in model_id for key in ("seedream", "image"))


def _agent_plan_request(model_id: str, message: str) -> tuple[str, str, dict | None, dict | None]:
    base_url = VOLCANO_AGENT_PLAN_BASE_URL
    if _is_video_model_id(model_id) or _is_image_model_id(model_id):
        return "GET", f"{base_url}/contents/generations/tasks", {"page_num": 1, "page_size": 1}, None
    return "POST", f"{base_url}/chat/completions", None, {
        "model": model_id, "messages": [{"role": "user", "content": message}], "max_tokens": 100,
    }


def _agent_plan_success(result: dict, model_id: str, elapsed_ms: int) -> dict:
    if _is_video_model_id(model_id):
        response_text, tokens_used = "Agent Plan 视频任务查询端点验证通过，未提交生成任务。", 0
    elif _is_image_model_id(model_id):
        response_text, tokens_used = "Agent Plan 专属 Key 与 /api/plan/v3 验证通过，未提交图像生成任务。", 0
    else:
        response_text = result.get("choices", [{}])[0].get("message", {}).get("content", "响应成功")
        tokens_used = result.get("usage", {}).get("total_tokens", 0)
    return {"success": True, "message": "火山方舟 Agent Plan API 连接成功！",
            "response": response_text, "response_time_ms": elapsed_ms, "tokens_used": tokens_used}


async def test_volcano_agent_plan_api(api_key: str, model_id: str, message: str) -> dict:
    """Preserve the read-only Agent Plan compatibility test."""
    method, url, params, data = _agent_plan_request(model_id, message)
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = (await client.get(url, params=params, headers=headers) if method == "GET"
                        else await client.post(url, json=data, headers=headers))
            elapsed_ms = int(response.elapsed.total_seconds() * 1000)
            if response.status_code == 200:
                return _agent_plan_success(response.json(), model_id, elapsed_ms)
            return {"success": False,
                    "message": f"[HTTP {response.status_code}] Agent Plan API错误: {_response_error(response)}\n端点: {url}",
                    "response": None, "response_time_ms": elapsed_ms, "tokens_used": 0}
    except httpx.TimeoutException:
        return {"success": False, "message": f"Agent Plan 连接超时(60s)，请检查网络或 API 地址\n请求地址: {url}",
                "response": None, "response_time_ms": 60000, "tokens_used": 0}
    except httpx.ConnectError as error:
        return {"success": False, "message": f"Agent Plan 连接失败，无法访问 API 地址: {error}\n请求地址: {url}",
                "response": None, "response_time_ms": 0, "tokens_used": 0}
    except Exception as error:
        return {"success": False, "message": f"Agent Plan 测试异常: {str(error)[:300]}", "response": None,
                "response_time_ms": 0, "tokens_used": 0}
