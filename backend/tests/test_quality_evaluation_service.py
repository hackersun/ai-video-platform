from datetime import datetime, timezone

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, delete, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.quality_evaluation import QUALITY_DIMENSIONS, QualityEvaluation
from app.services.quality_evaluation_service import evaluate_artifact


def _baseline_expected() -> dict:
    return {
        "episode_index": 2,
        "main_character_id": "character-lin",
        "prop_owners": {"jade-token": "character-lin"},
        "speaker_id": "character-lin",
        "subtitle_required": True,
        "mp4_required": True,
        "background": "rainy-alley",
        "ambient_audio": "light-rain",
    }


def _baseline_observed() -> dict:
    return {
        "source_episode_indices": [1, 2],
        "main_character_id": "character-lin",
        "prop_owners": {"jade-token": "character-lin"},
        "speaker_id": "character-lin",
        "subtitle_present": True,
        "mp4_valid": True,
        "background": "rainy-alley",
        "ambient_audio": "light-rain",
    }


def test_evaluate_artifact_returns_exactly_six_ready_dimensions_with_lineage() -> None:
    evaluated_at = datetime(2026, 7, 11, tzinfo=timezone.utc)

    result = evaluate_artifact(
        artifact_id="artifact-video-1",
        artifact_type="shot_video",
        workflow_id="workflow-1",
        shot_id="shot-1",
        provider_id="volcengine",
        model_id="seedance-2",
        expected_state=_baseline_expected(),
        observed_state=_baseline_observed(),
        evidence={"manifest_id": "manifest-1"},
        threshold_version="thresholds-2026-07",
        evaluator_version="deterministic-1",
        evaluated_at=evaluated_at,
    )

    assert tuple(item.dimension for item in result.dimension_results) == QUALITY_DIMENSIONS
    assert result.ready is True
    assert result.blockers == ()
    assert result.warnings == ()
    assert all(item.score == 100 for item in result.dimension_results)
    assert all(item.confidence == 1.0 for item in result.dimension_results)
    assert all(item.artifact_id == "artifact-video-1" for item in result.dimension_results)
    assert all(item.workflow_id == "workflow-1" for item in result.dimension_results)
    assert all(item.shot_id == "shot-1" for item in result.dimension_results)
    assert all(item.provider_id == "volcengine" for item in result.dimension_results)
    assert all(item.model_id == "seedance-2" for item in result.dimension_results)
    assert all(item.threshold_version == "thresholds-2026-07" for item in result.dimension_results)
    assert all(item.evaluator_version == "deterministic-1" for item in result.dimension_results)
    assert all(item.created_at == evaluated_at for item in result.dimension_results)


@pytest.mark.parametrize(
    ("mutation", "expected_code", "expected_dimension"),
    [
        ({"main_character_id": "character-other"}, "main_character_identity_mismatch", "character_visual"),
        ({"source_episode_indices": [1, 3]}, "future_episode_leakage", "narrative_truth"),
        ({"prop_owners": {"jade-token": "character-other"}}, "wrong_prop_owner", "scene_prop_state"),
        ({"speaker_id": "character-other"}, "wrong_speaker", "voice_lipsync"),
        ({"subtitle_present": False}, "missing_subtitle", "delivery_integrity"),
        ({"mp4_valid": False}, "corrupt_mp4", "delivery_integrity"),
    ],
)
def test_deterministic_mismatches_are_blocking(
    mutation: dict,
    expected_code: str,
    expected_dimension: str,
) -> None:
    observed = {**_baseline_observed(), **mutation}

    result = evaluate_artifact(
        artifact_id="artifact-video-1",
        artifact_type="shot_video",
        expected_state=_baseline_expected(),
        observed_state=observed,
    )

    assert result.ready is False
    assert expected_code in {item.code for item in result.blockers}
    blocker = next(item for item in result.blockers if item.code == expected_code)
    assert blocker.dimension == expected_dimension
    dimension = next(item for item in result.dimension_results if item.dimension == expected_dimension)
    assert dimension.blocking is True
    assert dimension.severity == "blocking"


def test_semantic_score_cannot_override_a_deterministic_blocker() -> None:
    observed = {**_baseline_observed(), "mp4_valid": False}

    result = evaluate_artifact(
        artifact_id="artifact-video-1",
        artifact_type="shot_video",
        expected_state=_baseline_expected(),
        observed_state=observed,
        semantic_scores={
            dimension: {"score": 100, "confidence": 0.99}
            for dimension in QUALITY_DIMENSIONS
        },
    )

    delivery = next(item for item in result.dimension_results if item.dimension == "delivery_integrity")
    assert result.ready is False
    assert delivery.blocking is True
    assert delivery.score < 60
    assert {item.code for item in result.blockers} == {"corrupt_mp4"}


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ({"background": "rainy-alley-with-extra-lanterns"}, "background_variation"),
        ({"ambient_audio": "light-rain-and-distant-bells"}, "ambient_difference"),
    ],
)
def test_noncritical_variations_are_warnings(mutation: dict, expected_code: str) -> None:
    observed = {**_baseline_observed(), **mutation}

    result = evaluate_artifact(
        artifact_id="artifact-video-1",
        artifact_type="shot_video",
        expected_state=_baseline_expected(),
        observed_state=observed,
    )

    assert result.ready is True
    assert result.blockers == ()
    assert expected_code in {item.code for item in result.warnings}
    warning = next(item for item in result.warnings if item.code == expected_code)
    assert warning.severity == "warning"
    assert warning.blocking is False


def test_quality_evaluation_rows_are_immutable_after_insert() -> None:
    engine = create_engine("sqlite:///:memory:")
    QualityEvaluation.__table__.create(engine)
    row = evaluate_artifact(
        artifact_id="artifact-video-1",
        artifact_type="shot_video",
        expected_state=_baseline_expected(),
        observed_state=_baseline_observed(),
    ).dimension_results[0]

    with Session(engine) as session:
        session.add(row)
        session.commit()
        row.score = 12
        with pytest.raises(ValueError, match="immutable"):
            session.commit()


def test_bulk_update_cannot_bypass_quality_evaluation_immutability() -> None:
    engine = create_engine("sqlite:///:memory:")
    QualityEvaluation.__table__.create(engine)
    row = evaluate_artifact(
        artifact_id="artifact-video-1",
        artifact_type="shot_video",
        expected_state=_baseline_expected(),
        observed_state=_baseline_observed(),
    ).dimension_results[0]

    with Session(engine) as session:
        session.add(row)
        session.commit()
        with pytest.raises(ValueError, match="immutable"):
            session.execute(
                update(QualityEvaluation)
                .where(QualityEvaluation.id == row.id)
                .values(score=12)
            )
        session.rollback()
        assert session.get(QualityEvaluation, row.id).score == 100


def test_bulk_delete_cannot_bypass_quality_evaluation_immutability() -> None:
    engine = create_engine("sqlite:///:memory:")
    QualityEvaluation.__table__.create(engine)
    row = evaluate_artifact(
        artifact_id="artifact-video-1",
        artifact_type="shot_video",
        expected_state=_baseline_expected(),
        observed_state=_baseline_observed(),
    ).dimension_results[0]

    with Session(engine) as session:
        session.add(row)
        session.commit()
        with pytest.raises(ValueError, match="immutable"):
            session.execute(delete(QualityEvaluation).where(QualityEvaluation.id == row.id))
        session.rollback()
        assert session.get(QualityEvaluation, row.id) is not None


def test_immutability_guard_does_not_block_bulk_dml_for_other_tables() -> None:
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    other_records = Table(
        "other_records",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("value", Integer, nullable=False),
    )
    metadata.create_all(engine)

    with Session(engine) as session:
        session.execute(other_records.insert().values(id=1, value=10))
        session.execute(update(other_records).where(other_records.c.id == 1).values(value=20))
        session.commit()
        assert session.execute(other_records.select()).one().value == 20


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("dimension", "style"),
        ("severity", "fatal"),
        ("score", -0.01),
        ("score", 100.01),
        ("confidence", -0.01),
        ("confidence", 1.01),
    ],
)
def test_database_constraints_reject_invalid_evaluation_values(
    field: str,
    invalid_value: object,
) -> None:
    engine = create_engine("sqlite:///:memory:")
    QualityEvaluation.__table__.create(engine)
    row = evaluate_artifact(
        artifact_id="artifact-video-1",
        artifact_type="shot_video",
        expected_state=_baseline_expected(),
        observed_state=_baseline_observed(),
    ).dimension_results[0]
    setattr(row, field, invalid_value)

    with Session(engine) as session:
        session.add(row)
        with pytest.raises(IntegrityError):
            session.commit()


def test_semantic_score_below_warning_threshold_is_nonblocking_warning() -> None:
    result = evaluate_artifact(
        artifact_id="artifact-video-1",
        artifact_type="shot_video",
        expected_state=_baseline_expected(),
        observed_state=_baseline_observed(),
        semantic_scores={"motion_camera": {"score": 79, "confidence": 0.8}},
        dimension_thresholds={"motion_camera": {"warning": 80, "blocking": 60}},
    )

    assert result.ready is True
    assert result.overall_readiness == "warning"
    assert {item.code for item in result.warnings} == {"semantic_score_below_warning"}
    motion = next(item for item in result.dimension_results if item.dimension == "motion_camera")
    assert motion.severity == "warning"
    assert motion.blocking is False
    assert motion.score == 79


def test_semantic_score_below_hard_threshold_blocks_overall_readiness() -> None:
    result = evaluate_artifact(
        artifact_id="artifact-video-1",
        artifact_type="shot_video",
        expected_state=_baseline_expected(),
        observed_state=_baseline_observed(),
        semantic_scores={"motion_camera": {"score": 59, "confidence": 0.8}},
        dimension_thresholds={"motion_camera": {"warning": 80, "blocking": 60}},
    )

    assert result.ready is False
    assert result.overall_readiness == "blocked"
    assert {item.code for item in result.blockers} == {"semantic_score_below_blocking"}
    motion = next(item for item in result.dimension_results if item.dimension == "motion_camera")
    assert motion.severity == "blocking"
    assert motion.blocking is True
    assert motion.score == 59


def test_semantic_blocker_repair_action_precedes_same_dimension_warning() -> None:
    observed = {
        **_baseline_observed(),
        "background": "rainy-alley-with-extra-lanterns",
    }

    result = evaluate_artifact(
        artifact_id="artifact-video-1",
        artifact_type="shot_video",
        expected_state=_baseline_expected(),
        observed_state=observed,
        semantic_scores={"scene_prop_state": {"score": 59, "confidence": 0.8}},
        dimension_thresholds={"scene_prop_state": {"warning": 80, "blocking": 60}},
    )

    scene = next(
        item for item in result.dimension_results if item.dimension == "scene_prop_state"
    )
    assert scene.blocking is True
    assert scene.repair_action == {"code": "review_quality_evidence"}
    assert [item["code"] for item in scene.evidence["deterministic"]] == [
        "background_variation"
    ]
    assert [item["code"] for item in scene.evidence["semantic_thresholds"]] == [
        "semantic_score_below_blocking"
    ]
