from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.model_registry import get_registry
import app.services.seedance_contract as seedance_contract


get_seedance_contract = seedance_contract.get_seedance_contract


def test_seedance_20_contract_defaults_to_experimental_until_official_evidence_exists() -> None:
    contract = get_seedance_contract("doubao-seedance-2-0-260128", provider="volcano")

    assert contract.model_family == "seedance_2"
    assert contract.provider == "volcano"
    assert contract.status == "experimental"
    assert contract.roles.image == "reference_image"
    assert contract.roles.video == "reference_video"
    assert contract.roles.audio == "reference_audio"
    assert contract.at_reference_syntax == "@image{index}"
    assert contract.pricing_status == "unconfirmed"
    assert contract.agent_plan_multireference is False
    assert contract.official_sources == [
        "https://www.volcengine.com/docs/82379/1520757",
    ]


def test_seedance_fast_uses_same_experimental_contract() -> None:
    contract = get_seedance_contract("doubao-seedance-2-0-fast-260128", provider="volcano")

    assert contract.model_family == "seedance_2"
    assert contract.status == "experimental"
    assert contract.max_images == 9
    assert contract.max_videos == 3
    assert contract.max_audios == 3


def test_agent_plan_contract_stays_single_reference_before_official_confirmation() -> None:
    contract = get_seedance_contract("doubao-seedance-2.0-fast", provider="volcano_agent_plan")

    assert contract.provider == "volcano_agent_plan"
    assert contract.status == "experimental"
    assert contract.agent_plan_multireference is False
    assert contract.max_images == 1
    assert contract.max_videos == 0
    assert contract.max_audios == 0


def test_unknown_model_uses_legacy_single_image_contract() -> None:
    contract = get_seedance_contract("unknown-model", provider="volcano")

    assert contract.model_family == "legacy"
    assert contract.status == "legacy_single_reference"
    assert contract.max_images == 1
    assert contract.max_videos == 0
    assert contract.max_audios == 0
    assert contract.roles.image == "image_url"


def test_incomplete_evidence_never_confirms_seedance_contract() -> None:
    contract_is_confirmed = getattr(seedance_contract, "contract_is_confirmed", None)
    resolve_seedance_contract = getattr(seedance_contract, "resolve_seedance_contract", None)
    required_evidence = getattr(seedance_contract, "REQUIRED_CONFIRMATION_EVIDENCE", None)
    assert callable(contract_is_confirmed)
    assert callable(resolve_seedance_contract)

    evidence = {
        "official_schema_url": "https://www.volcengine.com/docs/82379/1520757",
        "official_schema_accessed_at": "2026-07-11",
        "payload_contract_test": "tests/test_reference_package.py::test_provider_content_adapter_submits_multimodal_references",
        "pricing_url": "https://www.volcengine.com/activity/seedance2",
    }

    assert contract_is_confirmed(evidence) is False
    assert required_evidence == (
        "official_schema_url",
        "official_schema_accessed_at",
        "payload_contract_test",
        "live_canary_job_id",
        "pricing_url",
        "failure_retry_evidence",
    )

    contract = resolve_seedance_contract(
        "doubao-seedance-2-0-260128",
        provider="volcano",
        evidence=evidence,
    )

    assert contract.contract_status == "experimental"
    assert contract.contract_version == "seedance-2.0-ark-2026-07-11"
    assert contract.verified_at is None
    assert contract.reference_limits == {
        "images": 9,
        "videos": 3,
        "audios": 3,
        "at_reference": True,
        "native_audio": True,
    }
    assert contract.verification_gaps == ["live_canary_job_id", "failure_retry_evidence"]


def test_complete_evidence_confirms_seedance_contract() -> None:
    contract_is_confirmed = getattr(seedance_contract, "contract_is_confirmed", None)
    resolve_seedance_contract = getattr(seedance_contract, "resolve_seedance_contract", None)
    assert callable(contract_is_confirmed)
    assert callable(resolve_seedance_contract)

    evidence = {
        "official_schema_url": "https://www.volcengine.com/docs/82379/1520757",
        "official_schema_accessed_at": "2026-07-11",
        "payload_contract_test": "tests/test_reference_package.py::test_provider_content_adapter_submits_multimodal_references",
        "live_canary_job_id": "canary-job-recorded-outside-this-test",
        "pricing_url": "https://www.volcengine.com/activity/seedance2",
        "failure_retry_evidence": "recorded-retry-fixture",
    }

    assert contract_is_confirmed(evidence) is True

    contract = resolve_seedance_contract(
        "doubao-seedance-2-0-260128",
        provider="volcano",
        evidence=evidence,
    )

    assert contract.contract_status == "confirmed"
    assert contract.verified_at == "2026-07-11"
    assert contract.verification_gaps == []


def test_registry_exposes_additive_seedance_contract_metadata() -> None:
    registry = get_registry()
    model = next(item for item in registry["models"] if item["id"] == "volcano.seedance.2_0")

    assert model["contract_status"] == "experimental"
    assert model["contract_version"] == "seedance-2.0-ark-2026-07-11"
    assert model["verified_at"] is None
    assert model["reference_limits"] == {
        "images": 9,
        "videos": 3,
        "audios": 3,
        "at_reference": True,
        "native_audio": True,
    }
    assert model["verification_gaps"] == ["live_canary_job_id", "failure_retry_evidence"]


def test_registry_does_not_invent_seedance_limits_for_other_models() -> None:
    registry = get_registry()
    model = next(item for item in registry["models"] if item["id"] == "volcano.doubao.seed_1_8")

    assert model["contract_status"] == "unavailable"
    assert model["reference_limits"] == {}
    assert model["verification_gaps"] == ["model_contract_not_registered"]


def test_llm_model_api_schema_exposes_contract_fields_additively() -> None:
    from app.api.v1.endpoints.llm_config import LLMModelResponse

    fields = LLMModelResponse.model_fields

    assert fields.keys() >= {
        "contract_status",
        "contract_version",
        "verified_at",
        "reference_limits",
        "verification_gaps",
    }


@pytest.mark.asyncio
async def test_llm_models_response_keeps_visibility_and_adds_contract_metadata(monkeypatch) -> None:
    from app.api.v1.endpoints import llm_config

    async def _skip_seed(_db) -> None:
        return None

    class _ScalarResult:
        def __init__(self, items):
            self._items = items

        def scalars(self):
            return self

        def all(self):
            return self._items

    class _FakeSession:
        def __init__(self, result_sets):
            self._result_sets = iter(result_sets)

        async def execute(self, _query):
            return _ScalarResult(next(self._result_sets))

    visible_model = SimpleNamespace(
        id="seedance-public",
        provider_id="volcano",
        model_id="doubao-seedance-2-0-260128",
        model_name="Doubao Seedance 2.0",
        model_name_cn="豆包 Seedance 2.0",
        model_type="video-generation",
        capabilities=["text-to-video", "image-to-video"],
        context_window=0,
        max_tokens=0,
        input_cost_per_1k=0,
        output_cost_per_1k=0,
        is_active=True,
        is_recommended=True,
        description="公开视频模型",
        base_url=None,
    )
    hidden_model = SimpleNamespace(
        **{
            **vars(visible_model),
            "id": "test-video-hidden",
            "model_id": "test-video-hidden",
            "model_name": "Test Video Hidden",
            "model_name_cn": "测试视频模型",
        }
    )
    provider = SimpleNamespace(
        id="volcano",
        name="volcano",
        name_en="Volcano Engine",
        name_cn="火山引擎",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        description="",
    )
    db = _FakeSession([[provider], [visible_model, hidden_model], []])
    monkeypatch.setattr(llm_config, "ensure_default_models", _skip_seed)

    responses = await llm_config.list_models(provider=None, db=db, user_id="user-contract-test")

    assert [item["id"] for item in responses] == ["seedance-public"]
    response = llm_config.LLMModelResponse.model_validate(responses[0]).model_dump()
    assert response["model_name"] == "Doubao Seedance 2.0"
    assert response["contract_status"] == "experimental"
    assert response["contract_version"] == "seedance-2.0-ark-2026-07-11"
    assert response["verified_at"] is None
    assert response["reference_limits"] == {
        "images": 9,
        "videos": 3,
        "audios": 3,
        "at_reference": True,
        "native_audio": True,
    }
    assert response["verification_gaps"] == ["live_canary_job_id", "failure_retry_evidence"]
