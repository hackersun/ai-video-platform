"""Small normalization helpers shared by built-in provider drivers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.features.model_drivers.domain import DriverResultError, DriverSubmission, DriverTestResult


_ACCEPTED_SUBMISSION_STATUSES = frozenset({
    "accepted", "completed", "in_progress", "pending", "processing", "queued", "running", "submitted",
})
_COMPLETED_PROVIDER_STATUSES = frozenset({"completed", "success", "succeeded"})
_PENDING_PROVIDER_STATUSES = frozenset({"accepted", "in_progress", "pending", "processing", "queued", "running", "submitted"})
_ARTIFACT_KEYS = frozenset({"audio_url", "image_url", "image_urls", "output_url", "provider_url", "text", "url", "video_url"})


def _legacy_response_summary(output: Any) -> Any:
    if not isinstance(output, dict):
        return None
    if output.get("text") is not None:
        return output["text"]
    image_urls = output.get("image_urls")
    if isinstance(image_urls, list) and image_urls:
        return f"生成图像成功，URL: {str(image_urls[0])[:80]}"
    for key in ("audio_url", "image_url", "output_url", "provider_url", "url", "video_url"):
        if output.get(key):
            return output[key]
    return None


_AUTH_HINTS = ("401", "403", "unauthorized", "forbidden", "authentication", "invalid api key", "api key", "apikey", "access denied")
_SPEECH_AUTH_HINTS = ("grant", "not granted", "resource", "permission", "45000", "鉴权")
_PROVIDER_PAYLOAD_HINTS = ("无法解析", "未正常结束", "未返回音频", "无效的音频分片", "非对象事件")
_NETWORK_HINTS = ("timeout", "timed out", "connecterror", "connection refused", "name or service not known", "nodename nor servname")


def _error_status_code(error: BaseException) -> int | None:
    for candidate in (getattr(error, "status_code", None), getattr(getattr(error, "response", None), "status_code", None)):
        if isinstance(candidate, int):
            return candidate
    return None


def connection_failure_message(error: BaseException) -> str:
    """Map a provider exception to an actionable, secret-free Chinese hint."""
    status = _error_status_code(error)
    text = f"{type(error).__name__} {error}".lower()
    if "app_id" in text or "appid" in text:
        return "供应商连接测试失败：语音服务缺少 App ID，请在模型设置的语音卡片填写 App ID 后重新保存"
    if "不是受支持" in text:
        return "供应商连接测试失败：语音接口地址不受支持，请清空自定义 API 地址或改用官方地址"
    if any(hint in text for hint in _SPEECH_AUTH_HINTS):
        return "供应商连接测试失败：语音 Access Token 无效或未开通该音色资源，请检查后重新保存"
    if any(hint in text for hint in _PROVIDER_PAYLOAD_HINTS):
        return "供应商连接测试失败：供应商返回异常数据，请稍后重试"
    if status in (401, 403) or any(hint in text for hint in _AUTH_HINTS):
        return "供应商连接测试失败：API Key 无效或无权限，请检查后重新保存"
    if status == 429:
        return "供应商连接测试失败：请求过于频繁或额度不足，请稍后重试"
    if isinstance(error, TimeoutError) or any(hint in text for hint in _NETWORK_HINTS):
        return "供应商连接测试失败：无法连接供应商，请检查网络或自定义 API 地址"
    return "供应商连接测试失败"


async def connection_test(
    operation: Callable[[], Awaitable[DriverSubmission]],
    success_message: str,
) -> DriverTestResult:
    try:
        submission = await operation()
    except Exception as error:
        return DriverTestResult(
            "failed", connection_failure_message(error), {"provider_error_type": type(error).__name__},
        )
    evidence = {"submission_status": submission.status}
    if submission.status not in _ACCEPTED_SUBMISSION_STATUSES or not (
        submission.provider_task_id or submission.output
    ):
        return DriverTestResult("failed", "供应商未返回可验证的任务或产物", evidence)
    response = _legacy_response_summary(submission.output)
    if response is not None:
        evidence["response"] = response
    if isinstance(submission.output, dict) and submission.output.get("usage_count") is not None:
        evidence["usage_count"] = submission.output["usage_count"]
    return DriverTestResult(
        "connection_verified",
        success_message,
        {**evidence, "provider_task_id_present": bool(submission.provider_task_id)},
    )


def completed_output(result: dict[str, Any]) -> DriverSubmission:
    if not isinstance(result, dict):
        raise DriverResultError("provider result must be an object")
    task_id = result.get("task_id") or result.get("id")
    artifact_present = any(result.get(key) for key in _ARTIFACT_KEYS)
    raw_status = str(result.get("status") or "").strip().lower()
    if raw_status in _COMPLETED_PROVIDER_STATUSES and (task_id or artifact_present):
        normalized = "completed"
    elif raw_status in _PENDING_PROVIDER_STATUSES and task_id:
        normalized = raw_status
    elif not raw_status and artifact_present:
        normalized = "completed"
    elif not raw_status and task_id:
        normalized = "accepted"
    else:
        raise DriverResultError("provider result has no accepted status or recovery evidence")
    return DriverSubmission(normalized, str(task_id) if task_id else None, result)


async def unsupported_poll(_provider_task_id: str, _context: Any) -> DriverSubmission:
    raise DriverResultError("driver does not expose a separate polling operation")


def unsupported_submit() -> DriverSubmission:
    raise DriverResultError("driver capability is invoked through its existing production application service")
