from app.core.model_registry import TASK_DEFAULTS, find_model, get_model_reference_limits
from app.features.model_drivers.configuration_testing import select_llm_connection_driver_key
from app.services.minimax_h3_video_contract import (
    MINIMAX_H3_DRIVER_KEY,
    h3_parameter_schema,
    h3_reference_limits,
    validate_h3_generation,
)


def test_h3_contract_accepts_official_boundary_values() -> None:
    assert h3_reference_limits() == {
        "images": 9,
        "videos": 3,
        "audios": 3,
        "total": 12,
    }
    assert validate_h3_generation(
        prompt="镜头缓慢推进",
        duration=4,
        resolution="768P",
        ratio="16:9",
        references=[],
    ) == []
    assert validate_h3_generation(
        prompt="角色跟随参考动作",
        duration=15,
        resolution="2K",
        ratio="adaptive",
        references=[
            {"media_type": "image", "role": "reference_image"}
            for _ in range(9)
        ] + [
            {"media_type": "video", "role": "reference_video"}
            for _ in range(3)
        ],
    ) == []


def test_h3_contract_rejects_invalid_provider_parameters_before_submission() -> None:
    errors = validate_h3_generation(
        prompt="字" * 7001,
        duration=16,
        resolution="1080P",
        ratio="adaptive",
        references=[
            {"media_type": "image", "role": "reference_image"}
            for _ in range(10)
        ] + [
            {"media_type": "video", "role": "reference_video"}
            for _ in range(3)
        ],
    )

    assert {item["code"] for item in errors} == {
        "prompt_too_long",
        "duration_out_of_range",
        "resolution_not_supported",
        "reference_images_exceeded",
        "reference_total_exceeded",
    }


def test_h3_parameter_schema_matches_driver_kernel_shape() -> None:
    schema = h3_parameter_schema()

    assert schema["required"] == ["duration", "resolution", "ratio"]
    assert schema["properties"]["duration"] == {
        "type": "integer",
        "minimum": 4,
        "maximum": 15,
    }
    assert schema["properties"]["resolution"]["enum"] == ["768P", "2K"]
    assert "adaptive" in schema["properties"]["ratio"]["enum"]


def test_canonical_catalog_exposes_h3_without_replacing_shot_video_default() -> None:
    model = find_model("minimax.h3")

    assert model is not None
    assert model["api_model_id"] == "MiniMax-H3"
    assert model["driver_key"] == MINIMAX_H3_DRIVER_KEY
    assert model["status"]["verified"] is False
    assert get_model_reference_limits("MiniMax-H3") == {
        "images": 9,
        "videos": 3,
        "audios": 3,
        "at_reference": False,
        "native_audio": False,
    }
    assert TASK_DEFAULTS["shot_video"]["default_model_id"] != "minimax.h3"
    assert select_llm_connection_driver_key("minimax", "video") == MINIMAX_H3_DRIVER_KEY
