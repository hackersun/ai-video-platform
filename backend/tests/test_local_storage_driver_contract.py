from pathlib import Path

import pytest

from app.features import model_drivers
from app.features.model_config import ModelProfileContract


def _context(driver_key, capability, limits, connection_params=None):
    profile = ModelProfileContract(
        profile_version_id=f"profile:{driver_key}", provider_id=driver_key,
        api_model_id=driver_key, driver_key=driver_key, capabilities=frozenset({capability}),
        input_contract={}, output_contract={}, parameter_schema={}, default_params={}, limits=limits,
        pricing={}, prompt_profile_key=None, contract_version="v1",
    )
    return model_drivers.DriverContext(
        profile, driver_key, "connection-1", {"api_key": "ak", "api_secret": "sk"},
        base_url="https://cdn.example.com", connection_params=connection_params or {},
    )


@pytest.mark.asyncio
async def test_local_ffmpeg_driver_executes_production_renderer(monkeypatch, tmp_path):
    command_type = getattr(model_drivers, "MediaRenderCommand", None)
    assert command_type is not None
    captured = {}

    async def fake_render(manifest, *, output_dir, burn_subtitles):
        captured.update(manifest=manifest, output_dir=output_dir, burn_subtitles=burn_subtitles)
        return {"output_url": "/static/generated/final.mp4", "duration": 4.0}

    monkeypatch.setattr("app.services.ffmpeg_local_renderer.render_workflow_package", fake_render)
    command = command_type(
        manifest={"segments": [{"video_url": "/static/generated/shot.mp4"}]},
        output_dir=str(tmp_path), burn_subtitles=True,
    )

    submission = await model_drivers.execute_generation(
        model_drivers.build_builtin_driver_registry(), command,
        _context("local_ffmpeg_v1", "media_render", {"max_segments": 1}),
    )

    assert captured == {
        "manifest": command.manifest, "output_dir": Path(tmp_path), "burn_subtitles": True,
    }
    assert submission.status == "completed"
    assert submission.output["output_url"] == "/static/generated/final.mp4"


@pytest.mark.asyncio
async def test_qiniu_driver_executes_production_upload_boundary(monkeypatch):
    command_type = getattr(model_drivers, "ObjectStorageCommand", None)
    assert command_type is not None
    captured = {}

    async def fake_upload(local_url, **kwargs):
        captured.update(local_url=local_url, **kwargs)
        return {
            "provider_url": "https://cdn.example.com/static/generated/ref.png",
            "object_key": "static/generated/ref.png", "omitted_reason": None,
        }

    monkeypatch.setattr("app.services.media_delivery.upload_local_static_to_qiniu", fake_upload)
    params = {
        "bucket": "media", "upload_url": "https://upload.qiniup.com",
        "local_static_prefix": "/static/", "public_static_prefix": "/static/",
    }
    context = _context(
        "qiniu_kodo_v1", "object_storage", {"max_source_url_chars": 1024}, params,
    )
    command = command_type(source_url="/static/generated/ref.png")

    submission = await model_drivers.execute_generation(
        model_drivers.build_builtin_driver_registry(), command, context,
    )

    assert captured["local_url"] == command.source_url
    assert captured["access_key"] == "ak"
    assert captured["secret_key"] == "sk"
    assert captured["params"] == params
    assert submission.status == "completed"
    assert submission.output["provider_url"] == "https://cdn.example.com/static/generated/ref.png"
