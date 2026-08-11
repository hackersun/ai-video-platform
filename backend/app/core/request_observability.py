"""Request correlation and dependency-free Prometheus counters."""

from __future__ import annotations

import hmac
import os
import re
from collections import defaultdict
from threading import Lock
from uuid import uuid4

from app.core.runtime_environment import AppEnvironment, effective_environment


_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def normalize_request_id(value: str | None) -> str:
    candidate = str(value or "").strip()
    if candidate and _REQUEST_ID_PATTERN.fullmatch(candidate):
        return candidate
    return str(uuid4())


def metrics_access_allowed(authorization: str | None) -> bool:
    if effective_environment() in {AppEnvironment.LOCAL, AppEnvironment.TEST}:
        return True
    configured = os.getenv("OPERATIONS_TOKEN", "").strip()
    prefix = "Bearer "
    if not configured or not authorization or not authorization.startswith(prefix):
        return False
    return hmac.compare_digest(authorization[len(prefix):].strip(), configured)


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


class RequestMetrics:
    """Process-local counters suitable for one exporter per worker."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._count: dict[tuple[str, str, str], int] = defaultdict(int)
        self._duration: dict[tuple[str, str], float] = defaultdict(float)

    def observe(self, method: str, path: str, status_code: int, duration: float) -> None:
        status_group = f"{max(0, int(status_code)) // 100}xx"
        method_label = str(method or "UNKNOWN").upper()
        path_label = str(path or "unmatched")
        with self._lock:
            self._count[(method_label, path_label, status_group)] += 1
            self._duration[(method_label, path_label)] += max(0.0, float(duration))

    def render(self) -> str:
        lines = [
            "# HELP ai_video_http_requests_total HTTP requests by route and status group.",
            "# TYPE ai_video_http_requests_total counter",
        ]
        with self._lock:
            counts = sorted(self._count.items())
            durations = sorted(self._duration.items())
        for (method, path, status), count in counts:
            labels = (
                f'method="{_escape_label(method)}",path="{_escape_label(path)}",'
                f'status="{_escape_label(status)}"'
            )
            lines.append(f"ai_video_http_requests_total{{{labels}}} {count}")
        lines.extend(
            [
                "# HELP ai_video_http_request_duration_seconds_sum Total request duration by route.",
                "# TYPE ai_video_http_request_duration_seconds_sum counter",
            ]
        )
        for (method, path), duration in durations:
            labels = f'method="{_escape_label(method)}",path="{_escape_label(path)}"'
            lines.append(
                f"ai_video_http_request_duration_seconds_sum{{{labels}}} {duration:.6f}"
            )
        return "\n".join(lines) + "\n"


REQUEST_METRICS = RequestMetrics()
