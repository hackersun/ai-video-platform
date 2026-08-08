"""Compatibility facade for durable whole-book execution."""

from app.features.task_execution.series_run_handler import (
    enqueue_series_run_execution,
    handle_series_run_execution,
    queue_series_run_execution,
)

__all__ = [
    "enqueue_series_run_execution",
    "handle_series_run_execution",
    "queue_series_run_execution",
]
