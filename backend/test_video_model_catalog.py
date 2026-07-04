from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.model_registry import find_model, get_model, get_model_reference_limits, get_task_default
from main import app


def auth_headers(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


def test_video_registry_plans_supported_model_lanes() -> None:
    shot_default = get_task_default("shot_video")

    assert shot_default is not None
    assert shot_default["default_model_id"] == "volcano.seedance.2_0"
    assert shot_default["fallback_model_ids"] == [
        "alibaba.happyhorse.1_1_r2v",
        "alibaba.happyhorse.1_1_i2v",
        "alibaba.happyhorse.1_1_t2v",
        "kling.3_0_omni",
        "pixverse.c1",
        "volcano.seedance.1_5_pro",
        "kling.v2_6",
        "kling.o1",
    ]

    expected_models = {
        "volcano.seedance.2_0": "recommended",
        "alibaba.happyhorse.1_1_r2v": "premium",
        "alibaba.happyhorse.1_1_i2v": "premium",
        "alibaba.happyhorse.1_1_t2v": "premium",
        "kling.3_0_omni": "premium",
        "pixverse.c1": "specialist",
        "volcano.seedance.1_5_pro": "compatible",
        "kling.v2_6": "compatible",
        "kling.o1": "compatible",
    }
    for model_id, lane in expected_models.items():
        model = get_model(model_id)
        assert model is not None
        assert model["modality"] == "video"
        assert model["routing"]["lane"] == lane
        assert "shot_video" in model["capabilities"]

    seedance_limits = get_model_reference_limits("volcano.seedance.2_0")
    assert seedance_limits["images"] == 9
    assert seedance_limits["videos"] == 3
    assert seedance_limits["audios"] == 3
    assert seedance_limits["at_reference"] is True
    seedance = get_model("volcano.seedance.2_0")
    assert seedance["protocol"]["input_mode"] == "reference_images_text"
    assert seedance["protocol"]["reference_image_range"] == [0, 9]
    assert seedance["protocol"]["reference_video_range"] == [0, 3]
    assert seedance["protocol"]["reference_audio_range"] == [0, 3]

    legacy_limits = get_model_reference_limits("kling.v2_6")
    assert legacy_limits["images"] == 2
    assert legacy_limits["native_audio"] is True


def test_happyhorse_variants_expose_matching_dashscope_protocols() -> None:
    expected = {
        "alibaba.happyhorse.1_1_t2v": {
            "api_model_id": "happyhorse-1.1-t2v",
            "capability": "text_to_video",
            "input_mode": "text",
            "media_type": None,
            "reference_images": 0,
            "reference_image_range": [0, 0],
        },
        "alibaba.happyhorse.1_1_i2v": {
            "api_model_id": "happyhorse-1.1-i2v",
            "capability": "first_frame_image_to_video",
            "input_mode": "image_text",
            "media_type": "first_frame_image",
            "reference_images": 1,
            "reference_image_range": [1, 1],
        },
        "alibaba.happyhorse.1_1_r2v": {
            "api_model_id": "happyhorse-1.1-r2v",
            "capability": "reference_to_video",
            "input_mode": "reference_images_text",
            "media_type": "reference_image",
            "reference_images": 9,
            "reference_image_range": [1, 9],
        },
    }

    for model_id, info in expected.items():
        model = get_model(model_id)

        assert model is not None
        assert model["api_model_id"] == info["api_model_id"]
        assert "shot_video" in model["capabilities"]
        assert info["capability"] in model["capabilities"]
        assert "native_audio" not in model["capabilities"]
        assert model["limits"]["durations"] == list(range(3, 16))
        assert model["limits"]["resolutions"] == ["720P", "1080P"]
        assert model["limits"]["ratios"] == ["16:9", "9:16", "3:4", "4:3", "4:5", "5:4", "1:1", "9:21", "21:9"]

        protocol = model["protocol"]
        assert protocol["provider"] == "dashscope"
        assert protocol["endpoint_path"] == "/api/v1/services/aigc/video-generation/video-synthesis"
        assert protocol["async_header"] == {"X-DashScope-Async": "enable"}
        assert protocol["input_mode"] == info["input_mode"]
        assert protocol.get("input_media_type") == info["media_type"]
        assert protocol["reference_image_range"] == info["reference_image_range"]

        limits = get_model_reference_limits(info["api_model_id"])
        assert limits["images"] == info["reference_images"]
        assert limits["videos"] == 0
        assert limits["audios"] == 0
        assert limits["native_audio"] is False

    assert find_model("alibaba.happyhorse.1_1")["api_model_id"] == "happyhorse-1.1-r2v"
    assert find_model("happyhorse-1.1")["api_model_id"] == "happyhorse-1.1-r2v"


def test_video_models_endpoint_exposes_catalog_for_selector(monkeypatch) -> None:
    monkeypatch.setenv("DEV_MODE", "true")
    client = TestClient(app)

    response = client.get("/api/v1/video/models", headers=auth_headers("video-catalog-user"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["default_model_id"] == "volcano.seedance.2_0"
    ids = [model["id"] for model in payload["models"]]
    assert ids[:4] == [
        "volcano.seedance.2_0",
        "alibaba.happyhorse.1_1_r2v",
        "alibaba.happyhorse.1_1_i2v",
        "alibaba.happyhorse.1_1_t2v",
    ]
    assert "kling.3_0_omni" in ids
    assert "pixverse.c1" in ids
    assert "volcano.seedance.1_5_pro" in ids
    assert "kling.v2_6" in ids
    assert "kling.o1" in ids

    seedance = payload["models"][0]
    assert seedance["display_name"] == "豆包 Seedance 2.0"
    assert seedance["provider_id"] == "volcano"
    assert seedance["lane"] == "recommended"
    assert seedance["limits"]["durations"] == [4, 5, 8, 10, 15]
    assert seedance["is_configured"] is False

    happyhorse_models = [model for model in payload["models"] if model["id"].startswith("alibaba.happyhorse.1_1_")]
    assert [model["api_model_id"] for model in happyhorse_models] == [
        "happyhorse-1.1-r2v",
        "happyhorse-1.1-i2v",
        "happyhorse-1.1-t2v",
    ]
    assert [model["protocol"]["input_mode"] for model in happyhorse_models] == [
        "reference_images_text",
        "image_text",
        "text",
    ]
    assert all(
        model["protocol"]["async_header"] == {"X-DashScope-Async": "enable"}
        for model in happyhorse_models
    )
