from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.api.v1.endpoints.workflow import WorkflowQualityEvaluateRequest
from app.api.v1.endpoints.workflow import _quality_gate_summary
from app.models import QualityEvaluation
from app.services.quality_evaluation_service import evaluate_artifact


@pytest.mark.parametrize(
    "field",
    [
        "expected_state",
        "observed_state",
        "evidence",
        "semantic_scores",
        "dimension_thresholds",
        "threshold_version",
        "evaluator_version",
        "artifact_id",
        "provider_id",
        "model_id",
    ],
)
def test_public_quality_request_rejects_authoritative_fields(field: str) -> None:
    with pytest.raises(ValidationError):
        WorkflowQualityEvaluateRequest(shot_id="shot-1", **{field: {}})


def test_unknown_blocking_row_fails_closed() -> None:
    row = QualityEvaluation(
        id="unknown-blocker",
        artifact_id="artifact-1",
        artifact_type="video_job",
        workflow_id="workflow-1",
        shot_id="shot-1",
        dimension="motion_camera",
        expected_state={},
        observed_state={},
        evidence={"issue_codes": ["new_unregistered_blocker"]},
        score=0,
        confidence=1,
        severity="blocking",
        blocking=True,
        threshold_version="v1",
        evaluator_version="v1",
    )

    summary = _quality_gate_summary([row])

    assert summary is not None
    assert summary["ready"] is False
    assert summary["blockers"][0]["code"] == "new_unregistered_blocker"
    assert summary["suggested_repair"]["available"] is False
    assert summary["suggested_repair"]["navigation_url"].endswith("workflow_id=workflow-1&shot_id=shot-1")


def test_missing_observations_fail_closed_instead_of_copying_expected_state() -> None:
    result = evaluate_artifact(
        artifact_id="artifact-missing-evidence",
        artifact_type="video_job",
        expected_state={
            "main_character_id": "character-1",
            "prop_owners": {"prop-1": "character-1"},
            "background": "rainy_alley",
            "ambient_audio": "rain",
            "mp4_required": True,
        },
        observed_state={},
    )

    assert {issue.code for issue in result.blockers} == {
        "main_character_identity_mismatch", "wrong_prop_owner", "corrupt_mp4"
    }
    assert {issue.code for issue in result.warnings} == {
        "background_unverified", "ambient_audio_unverified"
    }
