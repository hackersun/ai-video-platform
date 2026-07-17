"""Typed, secret-safe MiniMax provider outcomes."""

from __future__ import annotations


class MiniMaxProviderRejected(Exception):
    """The provider explicitly rejected a request before returning a task or artifact."""

    def __init__(
        self, operation: str, status_code: object, message: object, *,
        provider_task_id: object = None, artifact_returned: bool = False,
    ) -> None:
        self.operation = str(operation)
        self.status_code = str(status_code)
        self.provider_message = str(message)[:200]
        self.provider_task_id = str(provider_task_id).strip() if provider_task_id else None
        self.artifact_returned = bool(artifact_returned)
        super().__init__(
            f"MiniMax {self.operation}失败 [{self.status_code}]: {self.provider_message}"
        )


def minimax_provider_rejection(payload, operation: str) -> MiniMaxProviderRejected | None:
    if not isinstance(payload, dict):
        return None
    base_resp = payload.get("base_resp") or payload.get("baseResponse")
    if not isinstance(base_resp, dict):
        return None
    status_code = base_resp.get("status_code")
    if status_code in (None, 0, "0"):
        return None
    message = base_resp.get("status_msg") or base_resp.get("message") or "provider rejected request"
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    task_id = payload.get("task_id") or data.get("task_id")
    artifact_returned = any(bool(data.get(key)) for key in (
        "items", "image_urls", "image_base64", "images", "url", "audio", "audio_file",
    ))
    return MiniMaxProviderRejected(
        operation, status_code, message,
        provider_task_id=task_id, artifact_returned=artifact_returned,
    )


def minimax_config_test_failure(payload, response_time_ms: int) -> dict | None:
    rejection = minimax_provider_rejection(payload, "configuration test")
    if not rejection:
        return None
    return {
        "success": False,
        "message": f"MiniMax API 业务拒绝 [{rejection.status_code}]",
        "response": None,
        "response_time_ms": response_time_ms,
        "tokens_used": 0,
    }


__all__ = [
    "MiniMaxProviderRejected", "minimax_config_test_failure", "minimax_provider_rejection",
]
