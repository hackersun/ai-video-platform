from app.features.workflow_media.adapters.video_submission import _provider_parameter_rejection_detail


def test_seedance_invalid_image_role_is_redacted_as_confirmed_parameter_rejection() -> None:
    error = RuntimeError(
        "Error code: 400 InvalidParameter: invalid role specified for image content; request id secret"
    )

    detail = _provider_parameter_rejection_detail(error)

    assert detail == {
        "code": "seedance_image_role_rejected",
        "message": "视频模型拒绝了参考图角色参数；本次请求未受理、不会自动重试，请刷新模型适配配置后重试。",
    }
    assert "secret" not in repr(detail)
