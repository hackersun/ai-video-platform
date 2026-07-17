from dataclasses import FrozenInstanceError

import pytest

from app.features.model_config import (
    BindingScope,
    CertificationLevel,
    ModelProfileContract,
    ProfileStatus,
    ResolvedModelBinding,
    normalize_capabilities,
)


@pytest.mark.parametrize(
    ("model_type", "capabilities", "expected"),
    [
        ("video-generation", ["text-to-video", "image_to_video"], {"video_generation"}),
        ("tts", ["text-to-speech"], {"speech_generation"}),
        ("vision", ["image_understanding"], {"vision_analysis"}),
        ("image", ["text_to_image"], {"image_generation"}),
    ],
)
def test_normalize_capabilities_uses_canonical_ids(model_type, capabilities, expected):
    assert normalize_capabilities(model_type, capabilities) == expected


def test_normalize_capabilities_accepts_canonical_ids_and_ignores_unknown_values():
    assert normalize_capabilities(
        "text_generation",
        ["subtitle-generation", "not-a-capability", "object_storage"],
    ) == {"text_generation", "subtitle_generation", "object_storage"}


def test_profile_and_binding_contracts_are_immutable():
    profile = ModelProfileContract(
        profile_version_id="profile-v1",
        provider_id="provider-1",
        api_model_id="model-1",
        driver_key="driver-1",
        capabilities=frozenset({"video_generation"}),
        input_contract={"prompt": "string"},
        output_contract={"video_url": "string"},
        parameter_schema={"duration": {"type": "integer"}},
        default_params={"duration": 5},
        limits={"duration": 10},
        pricing={"unit": "second"},
        prompt_profile_key="video.default",
        contract_version="v1",
    )
    binding = ResolvedModelBinding(
        task="shot.video",
        capability="video_generation",
        profile=profile,
        connection_id="connection-1",
        binding_version=1,
        source_scope=BindingScope.PROJECT,
    )

    assert binding.profile is profile
    assert binding.source_scope is BindingScope.PROJECT
    with pytest.raises(FrozenInstanceError):
        profile.provider_id = "other"
    with pytest.raises(FrozenInstanceError):
        binding.connection_id = "other"


def test_profile_lifecycle_enums_have_stable_wire_values():
    assert [status.value for status in ProfileStatus] == ["draft", "published", "disabled"]
    assert [level.value for level in CertificationLevel] == ["none", "connection", "contract", "live"]
    assert [scope.value for scope in BindingScope] == ["request", "series", "project", "user", "system"]
