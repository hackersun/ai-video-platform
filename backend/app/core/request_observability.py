"""Request correlation and dependency-free Prometheus counters."""

from __future__ import annotations

import hmac
import os
import re
from collections import defaultdict
from threading import Lock
from typing import Mapping
from uuid import uuid4

from app.core.runtime_environment import AppEnvironment, effective_environment


_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_QUEUE_STATUSES = ("pending", "running", "retry_wait", "dead_letter", "needs_attention")


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


def _number(value: object) -> float:
    try:
        return max(0.0, float(value or 0))
    except (TypeError, ValueError):
        return 0.0


def render_operational_metrics(snapshot: Mapping[str, object]) -> str:
    database = snapshot.get("database")
    queue = snapshot.get("task_queue")
    database_ready = int(isinstance(database, Mapping) and database.get("status") == "ok")
    queue_values = queue if isinstance(queue, Mapping) else {}
    lines = [
        "# HELP ai_video_database_ready Database readiness (1 ready, 0 unavailable).",
        "# TYPE ai_video_database_ready gauge",
        f"ai_video_database_ready {database_ready}",
        "# HELP ai_video_task_queue_depth Durable task count by bounded status.",
        "# TYPE ai_video_task_queue_depth gauge",
    ]
    for status in _QUEUE_STATUSES:
        lines.append(
            f'ai_video_task_queue_depth{{status="{status}"}} {int(_number(queue_values.get(status)))}'
        )
    lines.extend(
        [
            "# HELP ai_video_task_oldest_active_age_seconds Age of the oldest active durable task.",
            "# TYPE ai_video_task_oldest_active_age_seconds gauge",
            "ai_video_task_oldest_active_age_seconds "
            f"{_number(queue_values.get('oldest_active_age_seconds')):.3f}",
        ]
    )
    return "\n".join(lines) + "\n"


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
