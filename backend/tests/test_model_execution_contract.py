from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.features.model_execution_contract import resolve_model_execution_contract
from app.services.live_canary_bindings import _binding_snapshot


def test_known_versions_get_stable_contracts() -> None:
    cases = [
        ("minimax", "MiniMax-M3", "text", "minimax.text.m3.v1"),
        ("minimax", "MiniMax-M2.7", "text", "minimax.text.m27.v1"),
        ("minimax", "image-01", "image", "minimax.image.image01.v1"),
        ("minimax", "speech-2.6-hd", "tts", "minimax.tts.v2.v1"),
        ("volcano", "seed-tts-2.0", "tts", "volcano.seed_tts.v3.v1"),
        ("volcano", "doubao-seedance-1-5-pro-251215", "video", "volcano.seedance15.v1"),
        ("alibaba", "happyhorse-1.1-i2v", "video", "alibaba.happyhorse11.i2v.v1"),
        ("alibaba", "happyhorse-1.1-r2v", "video", "alibaba.happyhorse11.r2v.v1"),
        ("alibaba", "happyhorse-1.1-t2v", "video", "alibaba.happyhorse11.t2v.v1"),
    ]

    for provider, model, capability, version in cases:
        contract = resolve_model_execution_contract(provider, model, capability)
        assert contract.contract_version == version
        assert contract.verification_status == "verified"
        assert contract.prompt_profile


def test_model_aliases_resolve_to_the_same_contract() -> None:
    internal = resolve_model_execution_contract("minimax", "minimax-speech-2-6-hd", "tts")
    provider = resolve_model_execution_contract("minimax", "speech-2.6-hd", "tts")

    assert internal == provider


def test_unknown_model_is_fail_closed() -> None:
    contract = resolve_model_execution_contract("new-provider", "future-model", "video")

    assert contract.verification_status == "unverified"
    assert contract.retry_policy == "never"
    assert contract.reference_limits == {"images": 0, "videos": 0, "audios": 0}
    assert contract.supported_inputs == ()


@pytest.mark.asyncio
async def test_binding_snapshot_includes_execution_contract_evidence() -> None:
    tested_at = datetime.now()
    config = SimpleNamespace(
        id="config-1", user_id="user-1", is_active=True, test_status="success",
        tested_at=tested_at, extra_params={},
    )
    model = SimpleNamespace(
        id="db-model-1", model_id="speech-2.6-hd", model_type="tts",
        capabilities=["text-to-speech"], is_active=True,
    )
    provider = SimpleNamespace(id="minimax", is_active=True)

    class _Result:
        def one_or_none(self):
            return config, model, provider

    class _DB:
        async def execute(self, _query):
            return _Result()

    snapshot = await _binding_snapshot(
        _DB(), SimpleNamespace(user_id="user-1", budget_policy={}), capability="tts",
        config_id="config-1", minimum_tested_at=tested_at - timedelta(seconds=1),
    )

    assert snapshot["contract_version"] == "minimax.tts.v2.v1"
    assert snapshot["prompt_profile"] == "minimax.tts.v2"
    assert snapshot["verification_status"] == "verified"
