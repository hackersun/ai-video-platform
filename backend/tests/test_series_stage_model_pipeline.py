from __future__ import annotations

from types import SimpleNamespace

import pytest


def _validate_items(value):
    if not isinstance(value, list) or not value or not isinstance(value[0], dict):
        raise ValueError("items_required")
    return value


@pytest.mark.asyncio
async def test_stage_pipeline_uses_valid_model_json_and_records_sanitized_evidence(monkeypatch):
    from app.features.series_skill_execution import model_pipeline

    context = SimpleNamespace(binding=SimpleNamespace(
        binding_id="binding-1", connection_id="connection-1",
        profile=SimpleNamespace(provider_id="volcano", api_model_id="doubao-seed"),
    ), driver_context=object())

    async def resolve(*args, **kwargs):
        return context

    async def execute(*args, **kwargs):
        return SimpleNamespace(status="completed", output={"text": '```json\n[{"name":"林澈"}]\n```'})

    monkeypatch.setattr(model_pipeline, "resolve_generation_context", resolve)
    monkeypatch.setattr(model_pipeline, "execute_generation", execute)
    result = await model_pipeline.execute_skill_model_or_fallback(
        object(), user_id="user-1", rendered_prompt="extract entities",
        output_contract="json_array", validator=_validate_items,
        fallback=lambda: [{"name": "fallback"}],
    )

    assert result.value == [{"name": "林澈"}]
    assert result.evidence["execution_mode"] == "provider_model"
    assert result.evidence["validation_status"] == "passed"
    assert result.evidence["provider_id"] == "volcano"
    assert result.evidence["api_model_id"] == "doubao-seed"
    assert len(result.evidence["input_sha256"]) == 64
    assert len(result.evidence["output_sha256"]) == 64
    assert "extract entities" not in str(result.evidence)
    assert "林澈" not in str(result.evidence)


@pytest.mark.asyncio
@pytest.mark.parametrize("response, reason", [
    ("not-json", "model_output_invalid"),
    ("[]", "model_output_rejected"),
])
async def test_stage_pipeline_falls_back_when_model_output_is_invalid(monkeypatch, response, reason):
    from app.features.series_skill_execution import model_pipeline

    context = SimpleNamespace(binding=SimpleNamespace(
        binding_id="binding-1", connection_id="connection-1",
        profile=SimpleNamespace(provider_id="volcano", api_model_id="doubao-seed"),
    ), driver_context=object())
    monkeypatch.setattr(model_pipeline, "resolve_generation_context", lambda *a, **k: _async(context))
    monkeypatch.setattr(model_pipeline, "execute_generation", lambda *a, **k: _async(
        SimpleNamespace(status="completed", output={"text": response})
    ))

    result = await model_pipeline.execute_skill_model_or_fallback(
        object(), user_id="user-1", rendered_prompt="prompt",
        output_contract="json_array", validator=_validate_items,
        fallback=lambda: [{"name": "fallback"}],
    )

    assert result.value == [{"name": "fallback"}]
    assert result.evidence["execution_mode"] == "deterministic_fallback"
    assert result.evidence["fallback_reason"] == reason


@pytest.mark.asyncio
async def test_stage_pipeline_falls_back_when_binding_or_provider_is_unavailable(monkeypatch):
    from app.features.series_skill_execution import model_pipeline

    async def fail(*args, **kwargs):
        raise RuntimeError("secret provider detail")

    monkeypatch.setattr(model_pipeline, "resolve_generation_context", fail)
    result = await model_pipeline.execute_skill_model_or_fallback(
        object(), user_id="user-1", rendered_prompt="prompt",
        output_contract="json_array", validator=_validate_items,
        fallback=lambda: [{"name": "fallback"}],
    )

    assert result.value == [{"name": "fallback"}]
    assert result.evidence["fallback_reason"] == "model_unavailable"
    assert "secret provider detail" not in str(result.evidence)


async def _async(value):
    return value
