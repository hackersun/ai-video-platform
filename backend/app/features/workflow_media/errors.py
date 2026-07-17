"""Transport-neutral errors exposed by workflow media application use cases."""

from typing import Any


class WorkflowMediaError(Exception):
    """Preserve the existing HTTP-compatible status and detail at the API edge."""

    def __init__(self, status_code: int, detail: Any) -> None:
        super().__init__(str(detail))
        self.status_code = status_code
        self.detail = detail
