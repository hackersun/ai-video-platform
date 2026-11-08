from app.features.model_drivers.adapters._shared import connection_failure_message


class _Resp:
    def __init__(self, code):
        self.status_code = code


class _HttpError(Exception):
    def __init__(self, code):
        super().__init__(f"HTTP {code}")
        self.response = _Resp(code)


def test_auth_failure_is_actionable_without_leaking_detail():
    assert "API Key 无效" in connection_failure_message(_HttpError(401))
    assert "API Key 无效" in connection_failure_message(RuntimeError("Unauthorized: invalid api key sk-xxx"))
    assert "sk-xxx" not in connection_failure_message(RuntimeError("invalid api key sk-xxx"))


def test_rate_limit_and_network_hints():
    assert "频繁" in connection_failure_message(_HttpError(429))
    assert "无法连接" in connection_failure_message(TimeoutError())


def test_unknown_error_keeps_generic_message():
    assert connection_failure_message(ValueError("boom")) == "供应商连接测试失败"
