"""DashScope video driver registration over the existing external submission path."""

from app.features.model_drivers.adapters._shared import unsupported_poll, unsupported_submit
from app.features.model_drivers.domain import DriverTestResult


class DashScopeVideoDriver:
    key = "dashscope_video_v1"
    capabilities = frozenset({"video_generation"})

    async def test_connection(self, context):
        if not context.api_key:
            return DriverTestResult("failed", "缺少 API Key", {})
        return DriverTestResult("connection_configured", "配置完整；真实任务提交时验证权限和额度", {})

    async def submit(self, _command, _context):
        return unsupported_submit()

    poll = staticmethod(unsupported_poll)
