from tools.security.check_tracked_files import sensitive_reason


def test_sensitive_paths_are_blocked() -> None:
    assert sensitive_reason("backend/.env") == "环境变量文件"
    assert sensitive_reason("infra/client.key") == "私钥或证书密钥"
    assert sensitive_reason("tmp/customer.sqlite3") == "数据库文件"


def test_source_and_examples_are_allowed() -> None:
    assert sensitive_reason("backend/.env.example") is None
    assert sensitive_reason("backend/app/core/security.py") is None
    assert sensitive_reason("docs/security/key-rotation.md") is None
