from io import BytesIO

import pytest
from PIL import Image

from app.services.reference_layout_evaluator import (
    EVALUATOR_VERSION,
    MIN_LAYOUT_SCORE,
    ReferenceLayoutValidationError,
    evaluate_reference_layout,
)


def test_below_threshold_layout_exposes_secret_safe_scoring_evidence() -> None:
    buffer = BytesIO()
    Image.new("RGB", (1536, 1024), "white").save(buffer, format="PNG")

    with pytest.raises(ReferenceLayoutValidationError) as caught:
        evaluate_reference_layout(buffer.getvalue())

    assert caught.value.summary == {
        "failure_stage": "layout_scoring",
        "layout_score": 0.0,
        "threshold": MIN_LAYOUT_SCORE,
        "evaluator_version": EVALUATOR_VERSION,
    }
    assert "bytes_sha256" not in caught.value.summary
    assert "character_panels" not in caught.value.summary
