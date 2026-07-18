"""Compatibility-only legacy MiniMax connection-test helper."""

import httpx


def _request_contract(model_id: str, message: str, api_key: str) -> tuple[str, str, str, dict]:
    from app.core.minimax_config import DEFAULT_TTS_VOICE, MINIMAX_MODELS, get_minimax_base_url

    model_config = next(
        (item for item in MINIMAX_MODELS if item["id"] == model_id or item.get("api_model_id") == model_id),
        {},
    )
    model_type = model_config.get("type", "text-generation")
    actual_model = model_config.get("api_model_id", model_id)
    base_url = get_minimax_base_url(api_key)
    if model_type == "image-generation":
        return model_type, actual_model, f"{base_url}/image_generation", {
            "model": actual_model, "prompt": message[:200], "aspect_ratio": "1:1",
            "n": 1, "response_format": "url",
        }
    if model_type == "tts":
        from app.services.minimax_tts_request import build_minimax_tts_request

        request = build_minimax_tts_request(
            model_id=actual_model, text=message[:50], voice_id=DEFAULT_TTS_VOICE, speed=1.0,
        )
        return model_type, actual_model, f"{base_url}{request.url_path}", request.payload
    path = "/text/chatcompletion_v2" if actual_model == "MiniMax-M3" else "/chat/completions"
    return model_type, actual_model, f"{base_url}{path}", {
        "model": actual_model, "messages": [{"role": "user", "content": message}], "max_tokens": 100,
    }


def _success_result(result: dict, model_type: str, actual_model: str, elapsed_ms: int) -> dict:
    from app.core.minimax_voice_contract import minimax_tts_verification_message

    if model_type == "text-generation":
        choices = result.get("choices", [])
        response_text = choices[0].get("message", {}).get("content", "响应成功") if choices else str(result)[:100]
    elif model_type == "image-generation":
        items = result.get("data", {}).get("items", [])
        response_text = (f"生成图像成功，URL: {items[0].get('url', '')[:80]}" if items
                         else f"图像生成响应: {str(result)[:100]}")
    elif model_type == "tts":
        response_text = f"TTS响应: {str(result)[:100]}"
    else:
        response_text = str(result)[:100]
    return {
        "success": True,
        "message": minimax_tts_verification_message(actual_model) if model_type == "tts" else "MiniMax API 连接成功！",
        "response": response_text, "response_time_ms": elapsed_ms,
        "tokens_used": result.get("usage", {}).get("total_tokens", 0) if model_type == "text-generation" else 0,
    }


async def test_minimax_api(api_key: str, model_id: str, message: str) -> dict:
    """Preserve the legacy direct-test contract for compatibility callers."""
    from app.services.minimax_errors import minimax_config_test_failure

    model_type, actual_model, url, data = _request_contract(model_id, message, api_key)
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=data, headers=headers)
            elapsed_ms = int(response.elapsed.total_seconds() * 1000)
            if response.status_code != 200:
                return {
                    "success": False, "message": f"API错误 [{response.status_code}]: {response.text[:150]}",
                    "response": None, "response_time_ms": elapsed_ms, "tokens_used": 0,
                }
            result = response.json()
            return minimax_config_test_failure(result, elapsed_ms) or _success_result(
                result, model_type, actual_model, elapsed_ms,
            )
    except httpx.TimeoutException:
        return {"success": False, "message": "连接超时，请检查网络或API地址", "response": None,
                "response_time_ms": 60000, "tokens_used": 0}
    except Exception as error:
        return {"success": False, "message": f"连接失败: {str(error)[:100]}", "response": None,
                "response_time_ms": 0, "tokens_used": 0}
