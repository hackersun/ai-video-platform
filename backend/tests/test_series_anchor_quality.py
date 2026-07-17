from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.database import Base
from app.api.v1.endpoints.series_runs import (
    AcceptAnchorQualityRequest,
    PlanAnchorRepairRequest,
    accept_series_anchor_quality,
    plan_series_anchor_repair,
)
from app.models.novel import Novel
from app.models.series_production_run import SeriesProductionRun
from app.models.workflow import Workflow
from app.models.media_generation_job import MediaGenerationJob

from app.services.quality_evaluation_service import (
    ArtifactBindingError,
    USER_FACING_DIMENSIONS,
    evaluate_bound_anchor,
    validate_persisted_anchor_evaluations,
)
from app.models.quality_evaluation import QUALITY_DIMENSIONS, QualityEvaluation
from app.services.repair_planner import plan_bound_repair


NOW = datetime(2026, 7, 12, 8, 0, tzinfo=timezone.utc)


@pytest_asyncio.fixture()
async def db_session() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


def _binding(**overrides):
    value = {
        "artifact_id": "artifact-ep2-anchor",
        "job_id": "job-ep2-anchor",
        "shot_id": "shot-ep2-anchor",
        "episode_number": 2,
        "episode_contract_version": "contract-ep2-v3",
        "evaluator_version": "anchor-evaluator-v2",
        "artifact_created_at": NOW - timedelta(minutes=2),
        "evaluated_at": NOW,
    }
    value.update(overrides)
    return value


def _expected():
    return {
        "episode_index": 2,
        "as_of_contract_version": "contract-ep2-v3",
        "chapter_event_ids": ["event-ep2-turn"],
        "dialogue_meaning": "林澈拒绝交出玉符",
        "main_character_id": "lin-che",
        "character_traits": {"hair": "black", "coat": "blue"},
        "scene_id": "rain-alley",
        "prop_states": {"jade-token": {"owner": "lin-che", "damage": "cracked"}},
        "style_profile": {"palette": "cool", "line_treatment": "ink"},
        "shot_grammar": "medium-close",
        "speaker_id": "lin-che",
        "voice_binding_id": "voice-lin-v1",
        "language": "zh-CN",
        "subtitle_required": True,
        "mp4_required": True,
    }


def _observed():
    return {
        "source_episode_indices": [1, 2],
        "chapter_event_ids": ["event-ep2-turn"],
        "dialogue_meaning": "林澈拒绝交出玉符",
        "main_character_id": "lin-che",
        "character_traits": {"hair": "black", "coat": "blue"},
        "scene_id": "rain-alley",
        "prop_states": {"jade-token": {"owner": "lin-che", "damage": "cracked"}},
        "style_profile": {"palette": "cool", "line_treatment": "ink"},
        "shot_grammar": "medium-close",
        "speaker_id": "lin-che",
        "voice_binding_id": "voice-lin-v1",
        "language": "zh-CN",
        "dialogue_timing_valid": True,
        "intelligible": True,
        "subtitle_present": True,
        "mp4_valid": True,
        "playable": True,
        "duration_seconds": 6,
        "resolution": "1080p",
        "audio_stream_present": True,
        "manifest_lineage_valid": True,
    }


def _dimension_evidence(binding=None):
    binding = binding or _binding()
    return {
        dimension: {
            "artifact_id": binding["artifact_id"],
            "job_id": binding["job_id"],
            "shot_id": binding["shot_id"],
            "episode_contract_version": binding["episode_contract_version"],
            "evaluator_version": binding["evaluator_version"],
            "created_at": binding["evaluated_at"].isoformat(),
            "references": [f"evidence://{dimension}/1"],
            "source": "server_evaluator",
        }
        for dimension in USER_FACING_DIMENSIONS
    }


def _scores():
    return {
        dimension: {"score": 96, "confidence": 0.94}
        for dimension in USER_FACING_DIMENSIONS
    }


def _canonical():
    return {
        "reference_id": "canonical-series-v1", "version": "v1",
        "character_visual": {"main_character_id": "lin-che", "character_traits": {"hair": "black", "coat": "blue"}},
        "scene_prop_state": {"scene_id": "rain-alley", "prop_states": {"jade-token": {"owner": "lin-che", "damage": "cracked"}}},
        "style_cinematography": {"style_profile": {"palette": "cool", "line_treatment": "ink"}, "shot_grammar": "medium-close"},
        "voice_dialogue": {"speaker_id": "lin-che", "voice_binding_id": "voice-lin-v1", "language": "zh-CN"},
    }


def _previous():
    return {**_canonical(), "artifact_id": "artifact-ep1-anchor", "episode_number": 1, "accepted": True}


@pytest.mark.parametrize(
    "mutation, message",
    [
        ({"artifact_id": "old-artifact"}, "artifact_id"),
        ({"shot_id": "other-shot"}, "shot_id"),
        ({"episode_contract_version": "contract-ep1-v1"}, "episode_contract_version"),
        ({"evaluator_version": "old-evaluator"}, "evaluator_version"),
        ({"created_at": (NOW - timedelta(minutes=5)).isoformat()}, "creation time"),
    ],
)
def test_stale_or_mismatched_dimension_evidence_cannot_pass(mutation, message):
    evidence = _dimension_evidence()
    evidence["character_visual"].update(mutation)

    with pytest.raises(ArtifactBindingError, match=message):
        evaluate_bound_anchor(
            binding=_binding(),
            expected_state=_expected(),
            observed_state=_observed(),
            dimension_evidence=evidence,
            dimension_scores=_scores(),
            canonical_reference=_canonical(), preceding_accepted_anchor=_previous(),
        )


def test_missing_evidence_and_self_reported_job_metadata_cannot_pass():
    evidence = _dimension_evidence()
    evidence["voice_dialogue"] = {
        **evidence["voice_dialogue"],
        "source": "job_metadata",
        "references": [],
    }

    with pytest.raises(ArtifactBindingError, match="trusted evidence"):
        evaluate_bound_anchor(
            binding=_binding(),
            expected_state=_expected(),
            observed_state=_observed(),
            dimension_evidence=evidence,
            dimension_scores=_scores(),
            canonical_reference=_canonical(), preceding_accepted_anchor=_previous(),
        )


def test_exact_six_dimensions_are_scored_with_artifact_lineage_and_thresholds():
    result = evaluate_bound_anchor(
        binding=_binding(),
        expected_state=_expected(),
        observed_state=_observed(),
        dimension_evidence=_dimension_evidence(),
        dimension_scores=_scores(),
        canonical_reference=_canonical(), preceding_accepted_anchor=_previous(),
    )

    assert tuple(result["dimensions"]) == USER_FACING_DIMENSIONS
    assert result["ready"] is True
    assert result["artifact_id"] == "artifact-ep2-anchor"
    for dimension, row in result["dimensions"].items():
        assert row["score"] == 96
        assert row["threshold"] == 80
        assert row["blocking"] is False
        assert row["evidence"]["artifact_id"] == "artifact-ep2-anchor"
        assert row["findings"] == []


def test_recurring_subjects_compare_canonical_and_preceding_anchor():
    canonical = _canonical()
    previous = {**canonical, "artifact_id": "artifact-ep1-anchor", "episode_number": 1, "accepted": True}
    observed = {**_observed(), "voice_binding_id": "voice-other"}

    result = evaluate_bound_anchor(
        binding=_binding(),
        expected_state=_expected(),
        observed_state=observed,
        dimension_evidence=_dimension_evidence(),
        dimension_scores=_scores(),
        canonical_reference=canonical,
        preceding_accepted_anchor=previous,
    )

    assert result["ready"] is False
    voice = result["dimensions"]["voice_dialogue"]
    assert voice["blocking"] is True
    assert {item["comparison"] for item in voice["findings"]} == {"canonical", "preceding_anchor"}
    assert voice["evidence"]["preceding_artifact_id"] == "artifact-ep1-anchor"


def test_narrative_uses_as_of_chapter_contract_and_blocks_future_fact():
    observed = {**_observed(), "source_episode_indices": [2, 4]}
    result = evaluate_bound_anchor(
        binding=_binding(),
        expected_state=_expected(),
        observed_state=observed,
        dimension_evidence=_dimension_evidence(),
        dimension_scores=_scores(),
        canonical_reference=_canonical(), preceding_accepted_anchor=_previous(),
    )

    narrative = result["dimensions"]["narrative_truth"]
    assert narrative["blocking"] is True
    assert narrative["evidence"]["as_of_contract_version"] == "contract-ep2-v3"
    assert "future_episode_leakage" in {item["code"] for item in narrative["findings"]}


def test_repair_is_minimal_parent_linked_idempotent_and_retry_limited():
    first = plan_bound_repair(
        issue="wrong_voice",
        artifact_id="artifact-ep2-anchor",
        candidate_artifact_ids=("artifact-ep1-anchor", "artifact-ep2-anchor"),
        parent_job_id="job-ep2-anchor",
        parent_evaluation_ids=("eval-voice-1",),
        repair_key="run-1:artifact-ep2-anchor:voice_dialogue:v1",
        prior_auto_retry_count=0,
    )
    same = plan_bound_repair(
        issue="wrong_voice",
        artifact_id="artifact-ep2-anchor",
        candidate_artifact_ids=("artifact-ep1-anchor", "artifact-ep2-anchor"),
        parent_job_id="job-ep2-anchor",
        parent_evaluation_ids=("eval-voice-1",),
        repair_key="run-1:artifact-ep2-anchor:voice_dialogue:v1",
        prior_auto_retry_count=0,
    )
    assert first == same
    assert first.auto_retry_allowed is True
    assert first.parent_job_id == "job-ep2-anchor"
    assert first.parent_evaluation_ids == ("eval-voice-1",)
    assert first.affected_artifact_ids == ("artifact-ep2-anchor",)
    assert first.unchanged_artifact_ids == ("artifact-ep1-anchor",)

    exhausted = plan_bound_repair(
        issue="wrong_voice",
        artifact_id="artifact-ep2-anchor",
        candidate_artifact_ids=("artifact-ep2-anchor",),
        parent_job_id="job-ep2-anchor",
        parent_evaluation_ids=("eval-voice-1",),
        repair_key="retry-2",
        prior_auto_retry_count=1,
    )
    semantic = plan_bound_repair(
        issue="future_episode_leakage",
        artifact_id="artifact-ep2-anchor",
        candidate_artifact_ids=("artifact-ep2-anchor",),
        parent_job_id="job-ep2-anchor",
        parent_evaluation_ids=("eval-story-1",),
        repair_key="semantic-1",
        prior_auto_retry_count=0,
    )
    assert exhausted.auto_retry_allowed is False
    assert semantic.auto_retry_allowed is False
    assert semantic.requires_review is True


def _persisted_rows(workflow_id="workflow-run-1"):
    rows = []
    for index, dimension in enumerate(QUALITY_DIMENSIONS):
        rows.append(QualityEvaluation(
            id=f"eval-{index}",
            artifact_id="artifact-ep2-anchor",
            artifact_type="shot_video",
            workflow_id=workflow_id,
            shot_id="shot-ep2-anchor",
            dimension=dimension,
            expected_state={},
            observed_state={},
            evidence={
                "source": "server_evaluator",
                "references": [f"evidence://{dimension}/1"],
                "job_id": "job-ep2-anchor",
                "episode_contract_version": "contract-ep2-v3",
                "threshold": 80,
                "threshold_version": "threshold-v1",
                "evaluator_version": "anchor-evaluator-v2",
                "findings": [],
                "created_at": NOW.isoformat(),
                "episode_number": 2,
                "as_of_contract_version": "contract-ep2-v3",
                "canonical_reference_id": "canonical-series-v1",
                "preceding_artifact_id": "artifact-ep1-anchor",
            },
            score=96,
            confidence=.94,
            severity="pass",
            blocking=False,
            threshold_version="threshold-v1",
            evaluator_version="anchor-evaluator-v2",
            evaluated_at=NOW,
            created_at=NOW,
        ))
    return rows


def _validate_persisted(rows, *, allowed_workflow_ids={"workflow-run-1"}, expected_shot_id="shot-ep2-anchor"):
    return validate_persisted_anchor_evaluations(
        rows,
        allowed_workflow_ids=allowed_workflow_ids,
        expected_shot_id=expected_shot_id,
        expected_episode_number=2,
        expected_canonical_reference_id="canonical-series-v1",
        expected_preceding_artifact_id="artifact-ep1-anchor",
        expected_evaluator_version="anchor-evaluator-v2",
        artifact_completed_at=NOW - timedelta(minutes=1),
        accepted_at=NOW + timedelta(seconds=1),
    )


def test_persisted_evaluations_require_exact_owned_workflow_and_generation():
    report = _validate_persisted(
        _persisted_rows(),
        allowed_workflow_ids={"workflow-run-1"},
        expected_shot_id="shot-ep2-anchor",
    )
    assert report["ready"] is True
    assert tuple(report["dimensions"]) == USER_FACING_DIMENSIONS

    with pytest.raises(ArtifactBindingError, match="outside this series run"):
        _validate_persisted(
            _persisted_rows("workflow-other-user"),
            allowed_workflow_ids={"workflow-run-1"},
            expected_shot_id="shot-ep2-anchor",
        )


def test_sqlite_naive_utc_evaluation_times_remain_strictly_comparable():
    rows = _persisted_rows()
    naive = NOW.replace(tzinfo=None)
    for row in rows:
        row.evaluated_at = naive
        row.created_at = naive
    report = _validate_persisted(
        rows,
        allowed_workflow_ids={"workflow-run-1"},
        expected_shot_id="shot-ep2-anchor",
    )
    assert report["ready"] is True


def test_persisted_cross_episode_evaluation_requires_canonical_and_preceding_evidence():
    rows = _persisted_rows()
    character = next(row for row in rows if row.dimension == "character_visual")
    character.evidence = {**character.evidence, "preceding_artifact_id": None}
    with pytest.raises(ArtifactBindingError, match="preceding-anchor"):
        _validate_persisted(
            rows,
            allowed_workflow_ids={"workflow-run-1"},
            expected_shot_id="shot-ep2-anchor",
        )


def test_persisted_ready_is_recomputed_from_score_threshold_and_findings():
    rows = _persisted_rows()
    narrative = next(row for row in rows if row.dimension == "narrative_truth")
    narrative.score = 1
    narrative.blocking = False
    narrative.severity = "pass"
    report = _validate_persisted(rows)
    assert report["ready"] is False
    assert report["dimensions"]["narrative_truth"]["blocking"] is True
    assert report["dimensions"]["narrative_truth"]["status"] == "blocking"

    malformed = _persisted_rows()
    malformed[0].evidence = {**malformed[0].evidence, "threshold": float("nan")}
    with pytest.raises(ArtifactBindingError, match="threshold"):
        _validate_persisted(malformed)


def test_evidence_cannot_lower_authoritative_threshold_or_evaluator_version():
    lowered = _persisted_rows()
    lowered[0].score = 0
    lowered[0].evidence = {**lowered[0].evidence, "threshold": 0}
    with pytest.raises(ArtifactBindingError, match="server registry"):
        _validate_persisted(lowered)

    downgraded = _persisted_rows()
    downgraded[0].evidence = {**downgraded[0].evidence, "evaluator_version": "caller-evaluator-v0"}
    with pytest.raises(ArtifactBindingError, match="server registry"):
        _validate_persisted(downgraded)


def test_server_expected_episode_and_reference_ids_override_evidence_claims():
    rows = _persisted_rows()
    for row in rows:
        row.evidence = {
            **row.evidence,
            "episode_number": 1,
            "canonical_reference_id": "unverified-anything",
            "preceding_artifact_id": None,
        }
    with pytest.raises(ArtifactBindingError, match="episode number|canonical"):
        _validate_persisted(rows)


def test_persisted_evaluation_must_follow_artifact_completion_and_not_be_future():
    rows = _persisted_rows()
    with pytest.raises(ArtifactBindingError, match="predates"):
        validate_persisted_anchor_evaluations(
            rows, allowed_workflow_ids={"workflow-run-1"}, expected_shot_id="shot-ep2-anchor",
            expected_episode_number=2, expected_canonical_reference_id="canonical-series-v1",
            expected_preceding_artifact_id="artifact-ep1-anchor",
            expected_evaluator_version="anchor-evaluator-v2",
            artifact_completed_at=NOW + timedelta(minutes=1), accepted_at=NOW + timedelta(minutes=2),
        )
    with pytest.raises(ArtifactBindingError, match="future"):
        validate_persisted_anchor_evaluations(
            rows, allowed_workflow_ids={"workflow-run-1"}, expected_shot_id="shot-ep2-anchor",
            expected_episode_number=2, expected_canonical_reference_id="canonical-series-v1",
            expected_preceding_artifact_id="artifact-ep1-anchor",
            expected_evaluator_version="anchor-evaluator-v2",
            artifact_completed_at=NOW - timedelta(minutes=1), accepted_at=NOW - timedelta(minutes=10),
        )


def test_bound_episode_two_requires_locked_canonical_and_preceding_anchor():
    previous = {"artifact_id": "artifact-ep1-anchor", "episode_number": 1, "accepted": True}
    with pytest.raises(ArtifactBindingError, match="canonical"):
        evaluate_bound_anchor(
            binding=_binding(), expected_state=_expected(), observed_state=_observed(),
            dimension_evidence=_dimension_evidence(), dimension_scores=_scores(),
            canonical_reference=None, preceding_accepted_anchor=previous,
        )


def test_episode_one_also_requires_server_locked_canonical_reference():
    binding = _binding(episode_number=1)
    evidence = _dimension_evidence(binding)
    with pytest.raises(ArtifactBindingError, match="canonical reference is required for every episode"):
        evaluate_bound_anchor(
            binding=binding, expected_state=_expected(), observed_state=_observed(),
            dimension_evidence=evidence, dimension_scores=_scores(),
            canonical_reference=None, preceding_accepted_anchor=None,
        )


@pytest.mark.asyncio
async def test_accept_anchor_quality_is_owned_and_idempotent(db_session: AsyncSession):
    current = datetime.now(timezone.utc)
    user_id = "quality-owner"
    novel = Novel(id="quality-novel", user_id=user_id, title="四章小说")
    prior_workflow = Workflow(id="workflow-run-0", user_id=user_id, novel_id=novel.id, title="第一集")
    workflow = Workflow(
        id="workflow-run-1", user_id=user_id, novel_id=novel.id, title="第二集",
        metadata_={"episode_contract": {"production_bible_hash": "canonical-series-v1"}},
    )
    job = MediaGenerationJob(
        id="job-ep2-anchor", user_id=user_id, workflow_id=workflow.id,
        shot_id="shot-ep2-anchor", task_type="shot_video", media_type="video",
        status="succeeded", output_video_url="https://cdn.example/ep2.mp4",
        extra_data={"artifact_id": "artifact-ep2-anchor", "episode_contract_version": "contract-ep2-v3",
                    "canonical_reference_id": "canonical-series-v1"},
        created_at=current - timedelta(minutes=2), updated_at=current - timedelta(minutes=1),
    )
    run = SeriesProductionRun(
        id="quality-run", user_id=user_id, novel_id=novel.id,
        series_plan_version="v1", idempotency_key="quality-run-key", status="anchor_ready",
        current_episode_number=2, requested_stages=[], model_bindings={}, budget_policy={},
        cost_summary={}, gate_summary={}, run_metadata={
            "reference_preparation": {"asset_id": "canonical-series-v1"},
            "anchor_quality_reports": {
                "artifact-ep1-anchor": {"artifact_id": "artifact-ep1-anchor", "episode_number": 1, "ready": True},
            },
        },
        episodes=[
            {"episode_number": 1, "canonical_ids": {"workflow_id": prior_workflow.id}},
            {"episode_number": 2, "canonical_ids": {"workflow_id": workflow.id}},
        ], version=1,
    )
    rows = _persisted_rows()
    for row in rows:
        row.evaluated_at = current
        row.created_at = current
        row.evidence = {**row.evidence, "created_at": current.isoformat()}
    db_session.add_all([novel, prior_workflow, workflow, run, job, *rows])
    await db_session.commit()
    request = AcceptAnchorQualityRequest(
        shot_id="shot-ep2-anchor",
        job_id=job.id,
        evaluation_ids=[row.id for row in rows],
    )

    first = await accept_series_anchor_quality(run.id, request, db_session, user_id)
    second = await accept_series_anchor_quality(run.id, request, db_session, user_id)
    assert first == second
    await db_session.refresh(run)
    assert set(run.run_metadata["anchor_quality_reports"]) == {"artifact-ep1-anchor", "artifact-ep2-anchor"}

    newer_job = MediaGenerationJob(
        id="job-ep2-anchor-new", user_id=user_id, workflow_id=workflow.id,
        shot_id="shot-ep2-anchor", task_type="shot_video", media_type="video",
        status="succeeded", output_video_url="https://cdn.example/ep2-new.mp4",
        extra_data={"artifact_id": "artifact-ep2-anchor-new", "episode_contract_version": "contract-ep2-v3"},
        created_at=current + timedelta(minutes=1), updated_at=current + timedelta(minutes=1),
    )
    db_session.add(newer_job)
    await db_session.commit()
    with pytest.raises(Exception) as stale_error:
        await accept_series_anchor_quality(run.id, request, db_session, user_id)
    assert getattr(stale_error.value, "status_code", None) == 409
    assert "latest completed generation job" in str(getattr(stale_error.value, "detail", ""))

    with pytest.raises(Exception) as exc_info:
        await accept_series_anchor_quality(run.id, request, db_session, "other-user")
    assert getattr(exc_info.value, "status_code", None) == 404


@pytest.mark.asyncio
async def test_repair_endpoint_persists_parent_lineage_and_is_idempotent(db_session: AsyncSession):
    user_id = "repair-owner"
    novel = Novel(id="repair-novel", user_id=user_id, title="四章小说")
    workflow = Workflow(id="repair-workflow", user_id=user_id, novel_id=novel.id, title="第二集")
    report = {
        "artifact_id": "repair-artifact", "job_id": "repair-job",
        "evaluation_ids": ["repair-eval-voice"],
        "dimensions": {
            "voice_dialogue": {
                "blocking": True,
                "findings": [{"code": "wrong_voice"}, {"code": "wrong_speaker"}],
            }
        },
    }
    run = SeriesProductionRun(
        id="repair-run", user_id=user_id, novel_id=novel.id,
        series_plan_version="v1", idempotency_key="repair-key", status="anchor_ready",
        current_episode_number=2, requested_stages=[], model_bindings={}, budget_policy={},
        cost_summary={}, gate_summary={},
        run_metadata={"anchor_quality_reports": {"repair-artifact": report}},
        episodes=[{"episode_number": 2, "canonical_ids": {"workflow_id": workflow.id}}], version=1,
    )
    db_session.add_all([novel, workflow, run])
    await db_session.commit()
    request = PlanAnchorRepairRequest(
        artifact_id="repair-artifact", issue_code="wrong_voice", repair_key="repair-once",
    )

    first = await plan_series_anchor_repair(run.id, request, db_session, user_id)
    second = await plan_series_anchor_repair(run.id, request, db_session, user_id)
    assert first == second
    assert first["parent_job_id"] == "repair-job"
    assert first["parent_evaluation_ids"] == ["repair-eval-voice"]
    assert first["auto_retry_allowed"] is True

    conflict = PlanAnchorRepairRequest(
        artifact_id="repair-artifact", issue_code="wrong_speaker", repair_key="repair-once",
    )
    with pytest.raises(Exception) as conflict_error:
        await plan_series_anchor_repair(run.id, conflict, db_session, user_id)
    assert getattr(conflict_error.value, "status_code", None) == 409
    assert "idempotency key scope conflict" in str(getattr(conflict_error.value, "detail", ""))

    second_key = PlanAnchorRepairRequest(
        artifact_id="repair-artifact", issue_code="wrong_speaker", repair_key="repair-twice",
    )
    capped = await plan_series_anchor_repair(run.id, second_key, db_session, user_id)
    assert capped["auto_retry_allowed"] is False
    assert capped["requires_review"] is False

    stale = _persisted_rows()
    stale[-1].evaluator_version = "old-evaluator"
    with pytest.raises(ArtifactBindingError, match="stale evaluator generation"):
        _validate_persisted(
            stale,
            allowed_workflow_ids={"workflow-run-1"},
            expected_shot_id="shot-ep2-anchor",
        )
