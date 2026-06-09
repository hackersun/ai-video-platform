"""创作工作台测试/生产模式策略。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


BLOCKING_SEVERITIES = {"blocking", "error"}
CONFIRMABLE_SEVERITY = "confirmable"
MIN_BYPASS_REASON_LENGTH = 8


@dataclass(frozen=True)
class StudioModePolicy:
    """工作台运行模式和测试跳过策略。"""

    mode: str = "production"
    allow_test_bypass: bool = False
    bypass_reason: Optional[str] = None

    @property
    def normalized_mode(self) -> str:
        return "test" if self.mode == "test" else "production"


def _reason_is_valid(reason: Optional[str]) -> bool:
    return len((reason or "").strip()) >= MIN_BYPASS_REASON_LENGTH


def issue_is_blocking(issue: Dict[str, Any]) -> bool:
    return issue.get("severity") in BLOCKING_SEVERITIES


def apply_mode_policy(issues: List[Dict[str, Any]], policy: StudioModePolicy) -> Dict[str, Any]:
    """按测试/生产模式处理问题严重程度。

    生产模式下，阻断项保持阻断。
    测试模式下，只有用户显式允许且填写足够长原因时，阻断项才会降级为 confirmable。
    """

    mode = policy.normalized_mode
    normalized: List[Dict[str, Any]] = []
    bypassed: List[Dict[str, Any]] = []
    bypass_reason = (policy.bypass_reason or "").strip()
    can_bypass = mode == "test" and policy.allow_test_bypass and _reason_is_valid(bypass_reason)

    for issue in issues:
        item = dict(issue)
        if mode == "test" and policy.allow_test_bypass and issue_is_blocking(item):
            if can_bypass:
                item["original_severity"] = item.get("severity")
                item["severity"] = CONFIRMABLE_SEVERITY
                item["bypassed"] = True
                item["bypass_reason"] = bypass_reason
                bypassed.append(item)
            else:
                item["bypass_error"] = "测试模式跳过需要填写至少 8 个字符的原因"
        normalized.append(item)

    blocking = [item for item in normalized if issue_is_blocking(item)]
    warning_count = len([item for item in normalized if item.get("severity") == "warning"])
    confirmable_count = len([item for item in normalized if item.get("severity") == CONFIRMABLE_SEVERITY])
    return {
        "mode": mode,
        "ready": len(blocking) == 0,
        "issues": normalized,
        "blocking_issue_count": len(blocking),
        "warning_issue_count": warning_count,
        "confirmable_issue_count": confirmable_count,
        "bypassed_issue_count": len(bypassed),
        "bypass_audit": (
            {
                "reason": bypass_reason,
                "count": len(bypassed),
                "issue_codes": [item.get("code") for item in bypassed],
            }
            if bypassed
            else None
        ),
    }


def policy_from_request(
    *,
    mode: str = "production",
    allow_test_bypass: bool = False,
    bypass_reason: Optional[str] = None,
) -> StudioModePolicy:
    return StudioModePolicy(
        mode="test" if mode == "test" else "production",
        allow_test_bypass=allow_test_bypass,
        bypass_reason=bypass_reason,
    )
