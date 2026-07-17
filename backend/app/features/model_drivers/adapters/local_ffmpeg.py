"""Local FFmpeg availability driver."""

import shutil

from app.features.model_drivers.adapters._shared import unsupported_poll, unsupported_submit
from app.features.model_drivers.domain import DriverTestResult


def check_local_ffmpeg(binary: str, which=shutil.which) -> tuple[str, str]:
    if which(binary):
        return "success", f"本地 FFmpeg 可用：{binary}"
    return "failed", f"未找到本地 FFmpeg 可执行文件：{binary}"


class LocalFFmpegDriver:
    key = "local_ffmpeg_v1"
    capabilities = frozenset({"media_render"})

    async def test_connection(self, context):
        binary = str(context.connection_params.get("binary_path") or "ffmpeg")
        status, message = check_local_ffmpeg(binary, shutil.which)
        normalized = "connection_verified" if status == "success" else "failed"
        return DriverTestResult(normalized, message, {"binary": binary})

    async def submit(self, _command, _context):
        return unsupported_submit()

    poll = staticmethod(unsupported_poll)
