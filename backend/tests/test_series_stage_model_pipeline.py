from __future__ import annotations

from types import SimpleNamespace
import asyncio

import pytest


def test_entity_candidate_contract_normalizes_fractional_confidence():
    from app.features.series_skill_execution.stage_contracts import validate_entity_candidates

    result = validate_entity_candidates(
        [{
            "entity_type": "character",
            "name": "沈砚",
            "evidence": "沈砚立于山门前",
            "confidence": 0.95,
        }],
        source_text="沈砚立于山门前",
        requested_types={"character"},
    )

    assert result[0]["confidence"] == 95


def test_entity_candidate_contract_rejects_incomplete_events():
    from app.features.series_skill_execution.stage_contracts import validate_entity_candidates

    result = validate_entity_candidates(
        [
            {
                "entity_type": "event",
                "name": "山门遇袭",
                "evidence": "山门遇袭",
                "confidence": 0.9,
            },
            {
                "entity_type": "character",
                "name": "沈砚",
                "evidence": "沈砚",
                "confidence": 90,
            },
        ],
        source_text="山门遇袭，沈砚拔剑迎敌",
        requested_types={"character", "event"},
    )

    assert [item["name"] for item in result] == ["沈砚"]


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


@pytest.mark.asyncio
async def test_stage_pipeline_times_out_to_deterministic_fallback(monkeypatch):
    from app.features.series_skill_execution import model_pipeline

    context = SimpleNamespace(binding=SimpleNamespace(
        binding_id="binding-1", connection_id="connection-1",
        profile=SimpleNamespace(provider_id="volcano", api_model_id="ark-code-latest"),
    ), driver_context=object())

    async def never_returns(*args, **kwargs):
        await asyncio.Event().wait()

    monkeypatch.setattr(model_pipeline, "resolve_generation_context", lambda *a, **k: _async(context))
    monkeypatch.setattr(model_pipeline, "execute_generation", never_returns)
    monkeypatch.setattr(model_pipeline, "MODEL_EXECUTION_TIMEOUT_SECONDS", 0.01)

    result = await model_pipeline.execute_skill_model_or_fallback(
        object(), user_id="user-1", rendered_prompt="prompt",
        output_contract="json_array", validator=_validate_items,
        fallback=lambda: [{"name": "fallback"}],
    )

    assert result.value == [{"name": "fallback"}]
    assert result.evidence["fallback_reason"] == "model_execution_timeout"


async def _async(value):
    return value


@pytest.mark.asyncio
async def test_entity_stage_only_enriches_matching_model_entities(monkeypatch):
    from app.features.series_skill_execution import entity_stage
    from app.features.series_skill_execution.model_pipeline import SeriesStageModelResult

    async def execute(*args, **kwargs):
        return SeriesStageModelResult(
            value=[{
                "entity_type": "character", "name": "顾清霜",
                "attributes": {"visual_dna": {"hair": "银发"}},
            }],
            evidence={"execution_mode": "provider_model", "validation_status": "passed"},
        )

    monkeypatch.setattr(entity_stage, "execute_skill_model_or_fallback", execute)
    items, evidence = await entity_stage.resolve_entity_candidates(
        object(), user_id="user-1", rendered_prompt="prompt", source_text="source",
        requested_types={"character", "scene"}, supplied=None, model_config_id=None,
        fallback=lambda: [
            {
                "entity_type": "character", "name": "顾清霜",
                "attributes": {"visual_dna": {"gender": "女性", "hair": "黑发高马尾"}},
            },
            {"entity_type": "scene", "name": "星墟古城", "attributes": {}},
        ],
    )

    character = next(item for item in items if item["name"] == "顾清霜")
    assert character["attributes"]["visual_dna"] == {"gender": "女性", "hair": "黑发高马尾"}
    assert not any(item["name"] == "星墟古城" for item in items)
    assert evidence["deterministic_enrichment"] == {
        "merged_entities": 1, "added_entities": 0,
    }
