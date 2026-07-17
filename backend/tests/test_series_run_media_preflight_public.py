"""Architecture contract for the documented media-preflight owner."""

from pathlib import Path

from app.features.series_run_media_preflight.public import evaluate_media_preflight as public_preflight
from app.services.series_run_orchestrator import evaluate_media_preflight as legacy_preflight


def test_legacy_orchestrator_reexports_the_public_owner() -> None:
    assert legacy_preflight is public_preflight


def test_live_preflight_does_not_import_the_private_orchestrator_gate() -> None:
    source = (Path(__file__).parents[1] / "app/services/series_run_live_preflight.py").read_text()
    assert "from app.services.series_run_orchestrator import evaluate_media_preflight" not in source
    assert "from app.features.series_run_media_preflight.public import evaluate_media_preflight" in source


def test_series_run_endpoint_does_not_import_workflow_endpoint() -> None:
    source = (Path(__file__).parents[1] / "app/api/v1/endpoints/series_runs.py").read_text()
    assert "from app.api.v1.endpoints.workflow import" not in source
