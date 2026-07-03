from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.services.cost_calculator import CostCalculator
from main import app


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DEV_MODE", "true")
    return TestClient(app)


def test_seedance_20_video_billing_estimate_uses_token_formula() -> None:
    calculator = CostCalculator()

    estimate = calculator.estimate_video_billing_units(
        model_id="doubao-seedance-2-0-fast-260128",
        count=2,
        duration=4,
        resolution="720p",
        frame_rate=24,
    )

    assert estimate == {
        "formula": "seedance_2_token_formula",
        "model_id": "doubao-seedance-2-0-fast-260128",
        "count": 2,
        "duration_seconds": 4,
        "input_duration_seconds": 0,
        "output_duration_seconds": 4,
        "resolution": "720p",
        "width": 1280,
        "height": 720,
        "frame_rate": 24,
        "tokens_per_video": 86400,
        "estimated_tokens": 172800,
    }


def test_seedance_20_video_cost_uses_optional_price_per_million_tokens() -> None:
    calculator = CostCalculator()

    cost = calculator.estimate_video_cost(
        model_id="doubao-seedance-2-0-260128",
        duration=4,
        resolution="720p",
        frame_rate=24,
        price_per_million_tokens=46,
    )

    assert cost == 3.9744


def test_legacy_video_cost_is_unchanged_without_seedance_token_price() -> None:
    calculator = CostCalculator()

    assert calculator.estimate_video_cost(duration=4, resolution="720p") == 0.6
    assert calculator.estimate_video_cost(
        model_id="doubao-seedance-2-0-260128",
        duration=4,
        resolution="720p",
    ) == 0.6


def test_video_cost_estimate_route_returns_seedance_billing_units(client: TestClient) -> None:
    response = client.get(
        "/api/v1/costs/estimate/video",
        params={
            "count": 2,
            "duration": 4,
            "resolution": "720p",
            "model_id": "doubao-seedance-2-0-fast-260128",
            "frame_rate": 24,
            "price_per_million_tokens": 46,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["estimated_cost"] == 7.9488
    assert payload["parameters"]["billing_units"]["formula"] == "seedance_2_token_formula"
    assert payload["parameters"]["billing_units"]["estimated_tokens"] == 172800
