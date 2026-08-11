from pathlib import Path
import re


WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"
REQUIRED_ACTION_MAJORS = {
    "actions/checkout": {"v7"},
    "actions/setup-python": {"v7"},
    "actions/setup-node": {"v7"},
    "actions/upload-artifact": {"v7"},
    "codecov/codecov-action": {"v7"},
    "docker/setup-buildx-action": {"v4"},
}


def test_ci_uses_node24_action_majors() -> None:
    references = re.findall(
        r"uses:\s*([\w.-]+/[\w.-]+)@(v\d+)",
        WORKFLOW.read_text(encoding="utf-8"),
    )
    observed = {
        action: {major for name, major in references if name == action}
        for action in REQUIRED_ACTION_MAJORS
    }

    assert observed == REQUIRED_ACTION_MAJORS
