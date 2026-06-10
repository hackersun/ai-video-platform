"""测试镜头质量检查服务"""

from app.services.shot_quality_service import (
    ShotQualityService,
    QualityReport,
    QualityIssue,
    IssueType,
    IssueSeverity,
    build_storyboard_quality_summary,
    build_shot_quality_report,
    MAX_SHOT_DURATION,
    MAX_DIALOGUE_CHARS,
)


class MockShot:
    """模拟镜头对象"""
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", "test-shot-001")
        self.prompt = kwargs.get("prompt", "A beautiful sunset scene")
        self.visual_description = kwargs.get("visual_description", None)
        self.dialogue = kwargs.get("dialogue", None)
        self.duration = kwargs.get("duration", 4)
        self.image_url = kwargs.get("image_url", None)
        self.keyframes = kwargs.get("keyframes", None)
        self.character_refs = kwargs.get("character_refs", None)
        self.extra_data = kwargs.get("extra_data", {})


def test_empty_prompt_detection():
    """测试空prompt检测"""
    shot = MockShot(prompt="", visual_description="")
    service = ShotQualityService()
    report = service.check_shot_quality(shot)

    assert report.status == "blocked"
    assert len(report.blockers) > 0
    assert any(i.type == IssueType.MISSING_PROMPT for i in report.issues)
    print(f"[PASS] 空prompt检测: {report.blockers}")


def test_missing_image_warning():
    """测试缺参考图提示"""
    shot = MockShot(prompt="A scene", image_url=None)
    service = ShotQualityService()
    report = service.check_shot_quality(shot)

    assert report.status == "warning"
    assert len(report.warnings) > 0
    assert any(i.type == IssueType.MISSING_IMAGE for i in report.issues)
    print(f"[PASS] 缺参考图检测: {report.warnings}")


def test_duration_too_long_warning():
    """测试时长不匹配检测"""
    shot = MockShot(prompt="A scene", duration=20)
    service = ShotQualityService()
    report = service.check_shot_quality(shot)

    assert len(report.warnings) > 0
    assert any(i.type == IssueType.DURATION_TOO_LONG for i in report.issues)
    print(f"[PASS] 时长不匹配检测: {report.warnings}")


def test_dialogue_too_long_warning():
    """测试台词过长警告"""
    long_dialogue = "A" * 400  # 超过300字限制
    shot = MockShot(prompt="A scene", dialogue=long_dialogue)
    service = ShotQualityService()
    report = service.check_shot_quality(shot)

    assert len(report.warnings) > 0
    assert any(i.type == IssueType.DIALOGUE_TOO_LONG for i in report.issues)
    print(f"[PASS] 台词过长检测: {report.warnings}")


def test_placeholder_dialogue_speaker_warning():
    """测试占位说话人警告"""
    shot = MockShot(
        prompt="A scene",
        dialogue="角色A：我会查清楚。",
        character_refs=[{"name": "林澈"}],
        extra_data={"entity_refs": {"characters": [{"name": "林澈"}]}},
    )
    service = ShotQualityService()
    report = service.check_shot_quality(shot)

    assert any(i.type == IssueType.PLACEHOLDER_DIALOGUE_SPEAKER for i in report.issues)
    assert any("占位说话人" in warning for warning in report.warnings)


def test_unknown_dialogue_speaker_warning():
    """测试未知说话人警告"""
    shot = MockShot(
        prompt="A scene",
        dialogue="陌生人：我会查清楚。",
        character_refs=[{"name": "林澈"}],
        extra_data={"entity_refs": {"characters": [{"name": "林澈"}]}},
    )
    service = ShotQualityService()
    report = service.check_shot_quality(shot)

    assert any(i.type == IssueType.UNKNOWN_DIALOGUE_SPEAKER for i in report.issues)
    assert any("未绑定到当前镜头角色" in warning for warning in report.warnings)


def test_missing_character_refs_warning():
    """测试无角色引用警告"""
    shot = MockShot(prompt="A scene", character_refs=None)
    service = ShotQualityService()
    report = service.check_shot_quality(shot)

    assert len(report.warnings) > 0
    assert any(i.type == IssueType.MISSING_CHARACTER_REFS for i in report.issues)
    print(f"[PASS] 无角色引用检测: {report.warnings}")


def test_missing_keyframes_warning():
    """测试缺关键帧警告"""
    shot = MockShot(prompt="A scene", keyframes=None)
    service = ShotQualityService()
    report = service.check_shot_quality(shot)

    assert len(report.warnings) > 0
    assert any(i.type == IssueType.MISSING_KEYFRAMES for i in report.issues)
    print(f"[PASS] 缺关键帧检测: {report.warnings}")


def test_good_shot_ready_status():
    """测试良好镜头状态为ready"""
    shot = MockShot(
        prompt="A beautiful sunset over mountains",
        duration=5,
        image_url="https://example.com/image.jpg",
        keyframes=[{"time": 0, "prompt": "wide shot"}, {"time": 4, "prompt": "close up"}],
        character_refs=[{"character_id": "char-001", "name": "Hero"}],
        dialogue="Hello world",
        extra_data={
            "entity_refs": {
                "scenes": [{"name": "Mountain"}],
                "props": [{"name": "Compass"}],
                "events": [{"name": "Sunset reveal"}]
            }
        }
    )
    service = ShotQualityService()
    report = service.check_shot_quality(shot)

    assert report.status == "ready"
    assert report.score >= 80
    print(f"[PASS] 良好镜头: score={report.score}, status={report.status}")


def test_quality_score_calculation():
    """测试质量分数计算"""
    shot = MockShot(prompt="A scene")
    service = ShotQualityService()
    report = service.check_shot_quality(shot)

    # 空prompt应该扣20分
    assert report.score <= 80
    print(f"[PASS] 质量分数: score={report.score}, status={report.status}")


def test_storyboard_quality_summary():
    """测试分镜质量汇总"""
    shots = [
        MockShot(
            id="shot-1",
            prompt="Scene 1",
            duration=5,
            image_url="https://example.com/scene-1.jpg",
            keyframes=[{"time": 0, "prompt": "wide shot"}, {"time": 4, "prompt": "close up"}],
            character_refs=[{"character_id": "char-001", "name": "Hero"}],
            dialogue="We made it.",
            extra_data={
                "entity_refs": {
                    "scenes": [{"name": "Mountain"}],
                    "props": [{"name": "Compass"}],
                    "events": [{"name": "Arrival"}]
                },
                "production_context": {"review_state": "approved"},
            },
        ),
        MockShot(id="shot-2", prompt="", duration=20),  # blocked
        MockShot(id="shot-3", prompt="Scene 3", image_url=None),  # warning
    ]
    summary = build_storyboard_quality_summary("sb-001", shots)

    assert summary.total_shots == 3
    assert summary.error_count == 1
    assert summary.warning_count == 1
    assert summary.ready_count == 1
    print(f"[PASS] 分镜质量汇总: total={summary.total_shots}, avg_score={summary.avg_score}")


def test_legacy_build_shot_quality_report():
    """测试向后兼容的build_shot_quality_report函数"""
    shot = MockShot(prompt="A scene")
    report = build_shot_quality_report(shot)

    assert "score" in report
    assert "status" in report
    assert "blockers" in report
    assert "warnings" in report
    print(f"[PASS] 向后兼容函数: score={report['score']}")


def test_issue_severity_values():
    """测试IssueSeverity枚举值"""
    assert IssueSeverity.ERROR == "error"
    assert IssueSeverity.WARNING == "warning"
    assert IssueSeverity.INFO == "info"
    print("[PASS] IssueSeverity枚举值")


def test_issue_type_values():
    """测试IssueType枚举值"""
    assert IssueType.MISSING_PROMPT == "missing_prompt"
    assert IssueType.MISSING_IMAGE == "missing_image"
    assert IssueType.DURATION_TOO_LONG == "duration_too_long"
    assert IssueType.DIALOGUE_TOO_LONG == "dialogue_too_long"
    print("[PASS] IssueType枚举值")


def test_quality_issue_to_dict():
    """测试QualityIssue.to_dict()"""
    issue = QualityIssue(
        type=IssueType.MISSING_IMAGE,
        severity=IssueSeverity.WARNING,
        message="Missing reference image",
        field="image_url",
        current_value=None,
        recommended_value="Add image URL"
    )
    data = issue.to_dict()

    assert data["type"] == "missing_image"
    assert data["severity"] == "warning"
    assert data["message"] == "Missing reference image"
    print(f"[PASS] QualityIssue.to_dict(): {data}")


def test_quality_report_to_dict():
    """测试QualityReport.to_dict()"""
    shot = MockShot(id="test-001", prompt="Test")
    service = ShotQualityService()
    report = service.check_shot_quality(shot)
    data = report.to_dict()

    assert "shot_id" in data
    assert "score" in data
    assert "status" in data
    assert "issues" in data
    print(f"[PASS] QualityReport.to_dict(): shot_id={data['shot_id']}, issues={len(data['issues'])}")


def test_max_constants():
    """测试常量配置"""
    assert MAX_SHOT_DURATION == 15
    assert MAX_DIALOGUE_CHARS == 300
    print(f"[PASS] 常量: MAX_DURATION={MAX_SHOT_DURATION}, MAX_DIALOGUE={MAX_DIALOGUE_CHARS}")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("运行镜头质量检查服务测试")
    print("=" * 60)

    tests = [
        test_empty_prompt_detection,
        test_missing_image_warning,
        test_duration_too_long_warning,
        test_dialogue_too_long_warning,
        test_missing_character_refs_warning,
        test_missing_keyframes_warning,
        test_good_shot_ready_status,
        test_quality_score_calculation,
        test_storyboard_quality_summary,
        test_legacy_build_shot_quality_report,
        test_issue_severity_values,
        test_issue_type_values,
        test_quality_issue_to_dict,
        test_quality_report_to_dict,
        test_max_constants,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {e}")
            failed += 1

    print("=" * 60)
    print(f"测试结果: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
