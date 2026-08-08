from pathlib import Path

import pytest

from tools.code_health.policy import PolicyError, load_policy


def test_repository_policy_loads() -> None:
    policy = load_policy(Path("tools/code_health/policy.json"))

    assert policy.version == 1
    assert policy.roots == ("backend/app", "frontend/src")
    assert policy.limits.new_file_lines == 500
    assert policy.limits.function_lines == 80
    assert policy.limits.route_lines == 60
    assert policy.limits.react_page_lines == 300
    assert policy.limits.react_component_lines == 200


def test_exception_requires_reason_owner_and_removal_condition(tmp_path: Path) -> None:
    path = tmp_path / "policy.json"
    path.write_text(
        '{"version":1,"roots":["src"],"exclude":[],"limits":{'
        '"new_file_lines":500,"function_lines":80,"route_lines":60,'
        '"react_page_lines":300,"react_component_lines":200,"endpoint_routes":10},'
        '"boundaries":[],"exceptions":[{"path":"legacy.py","max_file_lines":900}]}',
        encoding="utf-8",
    )

    with pytest.raises(PolicyError, match="reason.*owner.*remove_when"):
        load_policy(path)


def test_limits_must_be_positive_integers(tmp_path: Path) -> None:
    path = tmp_path / "policy.json"
    path.write_text(
        '{"version":1,"roots":["src"],"exclude":[],"limits":{'
        '"new_file_lines":0,"function_lines":80,"route_lines":60,'
        '"react_page_lines":300,"react_component_lines":200,"endpoint_routes":10},'
        '"boundaries":[],"exceptions":[]}',
        encoding="utf-8",
    )

    with pytest.raises(PolicyError, match="positive integer"):
        load_policy(path)
