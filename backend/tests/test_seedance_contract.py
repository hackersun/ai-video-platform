from __future__ import annotations

from app.services.seedance_contract import get_seedance_contract


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
