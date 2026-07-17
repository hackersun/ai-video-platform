from types import SimpleNamespace

import pytest

from app.features.video_generation.application import model_config


@pytest.mark.asyncio
async def test_video_job_refresh_uses_the_job_bound_config_instead_of_provider_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str | None]] = []

    async def resolve(_db, _user_id, requested_model, config_id=None):
        calls.append((requested_model, config_id))
        return {
            "api_key": "bound-video-key",
            "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        }

    async def provider_default(*_args, **_kwargs):
        raise AssertionError("provider default must not be used for a bound video job")

    monkeypatch.setattr(model_config, "resolve_video_model_config", resolve)
    monkeypatch.setattr(model_config, "get_user_api_key", provider_default, raising=False)
    job = SimpleNamespace(
        model_id="doubao-seedance-1-5-pro-251215",
        extra_data={
            "provider_id": "volcano",
            "model_config_id": "video-config-1",
        },
    )

    result = await model_config.resolve_video_job_client_config(
        object(), "user-1", job,
    )

    assert result == (
        "bound-video-key",
        "https://ark.cn-beijing.volces.com/api/v3",
    )
    assert calls == [
        ("doubao-seedance-1-5-pro-251215", "video-config-1"),
    ]
