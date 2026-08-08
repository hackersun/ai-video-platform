from pathlib import Path

import pytest

from tools.code_health.policy import load_policy
from tools.code_health.python_scan import scan_python_file


@pytest.fixture
def repo_root() -> Path:
    return Path.cwd()


@pytest.fixture
def policy(repo_root: Path):
    return load_policy(repo_root / "tools/code_health/policy.json")


def test_route_over_60_lines_is_reported(repo_root: Path, policy) -> None:
    metrics = scan_python_file(
        repo_root / "tools/code_health/tests/fixtures/python/oversized_route.py",
        repo_root,
        policy,
    )

    assert [(item.code, item.allowed) for item in metrics.violations] == [
        ("route_too_long", 60),
    ]


def test_service_importing_endpoint_is_reported(repo_root: Path, policy, tmp_path: Path) -> None:
    path = tmp_path / "backend/app/services/service_imports_endpoint.py"
    path.parent.mkdir(parents=True)
    path.write_text(
        (repo_root / "tools/code_health/tests/fixtures/python/service_imports_endpoint.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    metrics = scan_python_file(
        path,
        tmp_path,
        policy,
    )

    assert metrics.imports == ("app.api.v1.endpoints",)
    assert [item.code for item in metrics.violations] == ["service_imports_endpoint"]


def test_syntax_error_is_reported_without_importing_application(repo_root: Path, policy, tmp_path: Path) -> None:
    path = tmp_path / "broken.py"
    path.write_text("def broken(:\n", encoding="utf-8")

    metrics = scan_python_file(path, tmp_path, policy)

    assert [item.code for item in metrics.violations] == ["python_syntax_error"]
