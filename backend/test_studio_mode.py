from __future__ import annotations

from app.services.studio_mode import StudioModePolicy, apply_mode_policy


def test_production_mode_keeps_blocking_issues_blocking() -> None:
    result = apply_mode_policy(
        [
            {"code": "missing_asset_locks", "severity": "blocking", "message": "缺少资产锁"},
            {"code": "quality_warning", "severity": "warning", "message": "质量有风险"},
        ],
        StudioModePolicy(mode="production", allow_test_bypass=True, bypass_reason="测试临时跳过"),
    )

    assert result["mode"] == "production"
    assert result["ready"] is False
    assert result["blocking_issue_count"] == 1
    assert result["warning_issue_count"] == 1
    assert result["bypass_audit"] is None
    assert result["issues"][0]["severity"] == "blocking"


def test_test_mode_can_downgrade_blocking_issue_with_reason() -> None:
    result = apply_mode_policy(
        [{"code": "model_unverified", "severity": "blocking", "message": "模型未验证"}],
        StudioModePolicy(mode="test", allow_test_bypass=True, bypass_reason="本地联调先验证流程"),
    )

    assert result["mode"] == "test"
    assert result["ready"] is True
    assert result["blocking_issue_count"] == 0
    assert result["confirmable_issue_count"] == 1
    assert result["bypassed_issue_count"] == 1
    assert result["bypass_audit"]["reason"] == "本地联调先验证流程"
    assert result["bypass_audit"]["issue_codes"] == ["model_unverified"]
    assert result["issues"][0]["original_severity"] == "blocking"
    assert result["issues"][0]["severity"] == "confirmable"


def test_test_mode_requires_explicit_bypass_reason() -> None:
    result = apply_mode_policy(
        [{"code": "reference_image_not_public", "severity": "error", "message": "参考图不是公网地址"}],
        StudioModePolicy(mode="test", allow_test_bypass=True, bypass_reason="太短"),
    )

    assert result["ready"] is False
    assert result["blocking_issue_count"] == 1
    assert result["bypassed_issue_count"] == 0
    assert result["issues"][0]["severity"] == "error"
    assert result["issues"][0]["bypass_error"] == "测试模式跳过需要填写至少 8 个字符的原因"


def test_warning_is_never_bypassed() -> None:
    result = apply_mode_policy(
        [{"code": "soft_warning", "severity": "warning", "message": "建议补充信息"}],
        StudioModePolicy(mode="test", allow_test_bypass=True, bypass_reason="本地联调先验证流程"),
    )

    assert result["ready"] is True
    assert result["warning_issue_count"] == 1
    assert result["confirmable_issue_count"] == 0
    assert result["bypass_audit"] is None
    assert result["issues"][0]["severity"] == "warning"
