"""Run the durable production task worker."""

from __future__ import annotations

import asyncio
import os
import socket
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import AsyncSessionLocal
from app.core.runtime_environment import validate_runtime_environment
from app.features.task_execution.series_run_handler import (
    TASK_TYPE as SERIES_RUN_TASK_TYPE,
    handle_series_run_execution,
)
from app.features.task_execution.shot_image_handler import (
    TASK_TYPE as SHOT_IMAGE_TASK_TYPE,
    handle_shot_image_poll,
)
from app.features.task_execution.worker import run_worker


async def run() -> None:
    validate_runtime_environment()
    worker_id = os.getenv("TASK_WORKER_ID") or f"{socket.gethostname()}-{os.getpid()}"
    await run_worker(
        AsyncSessionLocal,
        worker_id=worker_id,
        handlers={
            SERIES_RUN_TASK_TYPE: handle_series_run_execution,
            SHOT_IMAGE_TASK_TYPE: handle_shot_image_poll,
        },
    )


if __name__ == "__main__":
    asyncio.run(run())
