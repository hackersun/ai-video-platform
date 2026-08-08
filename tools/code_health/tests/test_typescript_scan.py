from pathlib import Path

import pytest

from tools.code_health.policy import load_policy
from tools.code_health.typescript_scan import scan_typescript_files


@pytest.fixture
def policy():
    return load_policy(Path("tools/code_health/policy.json"))


def _write_function(path: Path, *, name: str, body_lines: int, default_export: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    prefix = "export default " if default_export else "export "
    body = "\n".join(f"  const value{index} = {index};" for index in range(body_lines))
    path.write_text(
        f"{prefix}function {name}() {{\n{body}\n  return <div>{{value0}}</div>;\n}}\n",
        encoding="utf-8",
    )


def test_route_page_over_300_lines_is_reported(tmp_path: Path, policy) -> None:
    path = tmp_path / "frontend/src/app/oversized/page.tsx"
    _write_function(path, name="Page", body_lines=299, default_export=True)

    metrics = scan_typescript_files([path], tmp_path, policy)[0]

    assert any(item.code == "react_page_too_long" for item in metrics.violations)


def test_feature_component_over_200_lines_is_reported(tmp_path: Path, policy) -> None:
    path = tmp_path / "frontend/src/features/example/components/OversizedCard.tsx"
    _write_function(path, name="OversizedCard", body_lines=199)

    metrics = scan_typescript_files([path], tmp_path, policy)[0]

    assert any(item.code == "react_component_too_long" for item in metrics.violations)


def test_small_typescript_function_has_no_size_violation(tmp_path: Path, policy) -> None:
    path = tmp_path / "frontend/src/features/example/utils.ts"
    path.parent.mkdir(parents=True)
    path.write_text("export function value() { return 1; }\n", encoding="utf-8")

    metrics = scan_typescript_files([path], tmp_path, policy)[0]

    assert metrics.violations == ()
