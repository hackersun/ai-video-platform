from __future__ import annotations

import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1.endpoints.dashboard import (
    ProductionReadinessEvidenceRequest,
    _get_production_metrics,
    write_production_readiness_evidence,
)
from app.core.database import Base
from app.core.security import get_current_user_id
from app.models import ImageJob, MediaGenerationJob, QualityEvaluation, SynthesisJob, TTSJob, VideoJob, Workflow
from app.services.production_metrics import (
    aggregate_production_metrics,
    evaluate_readiness_tiers,
    persist_production_readiness_evidence,
)
from init_db import init_db
from main import app


def _attempts() -> list[dict]:
    shared = {
        "provider_id": "volcengine",
        "model_id": "seedance-2",
        "prompt_version": "prompt-v3",
        "contract_version": "contract-v2",
    }
    return [
        {**shared, "shot_id": "shot-a", "attempt": 1, "status": "accepted", "accepted_final": True, "final_duration_seconds": 60, "cost_rmb": 10, "wall_clock_minutes": 20, "human_review_minutes": 2, "human_repair_minutes": 0, "issue_codes": []},
        {**shared, "shot_id": "shot-b", "attempt": 1, "status": "failed", "accepted_final": False, "final_duration_seconds": 0, "cost_rmb": 5, "wall_clock_minutes": 10, "human_review_minutes": 1, "human_repair_minutes": 0, "issue_codes": ["main_character_identity_mismatch"]},
        {**shared, "shot_id": "shot-b", "attempt": 2, "status": "accepted", "accepted_final": True, "final_duration_seconds": 60, "cost_rmb": 8, "wall_clock_minutes": 30, "human_review_minutes": 2, "human_repair_minutes": 3, "issue_codes": []},
        {**shared, "shot_id": "shot-c", "attempt": 1, "status": "abandoned", "accepted_final": False, "final_duration_seconds": 0, "cost_rmb": 4, "wall_clock_minutes": 5, "human_review_minutes": 0, "human_repair_minutes": 0, "issue_codes": ["wrong_prop_owner"]},
        {**shared, "shot_id": "shot-d", "attempt": 1, "status": "failed", "accepted_final": False, "final_duration_seconds": 0, "cost_rmb": 3, "wall_clock_minutes": 5, "human_review_minutes": 0, "human_repair_minutes": 0, "issue_codes": ["wrong_speaker"]},
    ]


def test_metrics_use_accepted_final_denominator_without_hiding_failed_cost() -> None:
    result = aggregate_production_metrics(_attempts())

    assert result["counts"] == {
        "planned_shots": 4,
        "attempts": 5,
        "accepted_final_shots": 2,
        "failed_attempts": 2,
        "abandoned_attempts": 1,
        "regenerated_attempts": 1,
    }
    assert result["first_pass_shot_acceptance_rate"] == 0.25
    assert result["main_character_hard_failure_rate"] == 0.25
    assert result["state_continuity_conflict_rate"] == 0.25
    assert result["voice_lipsync_hard_failure_rate"] == 0.25
    assert result["regenerated_shots_per_accepted_shot"] == 0.5
    assert result["rmb_per_accepted_final_minute"] == 15.0
    assert result["wall_clock_minutes_per_accepted_final_minute"] == 35.0
    assert result["human_review_repair_minutes_per_accepted_final_minute"] == 4.0
    assert result["failed_abandoned"]["cost_rmb"] == 12.0
    assert result["failed_abandoned"]["attempt_count"] == 3
    assert result["attribution"][0] == {
        "provider_id": "volcengine",
        "model_id": "seedance-2",
        "prompt_version": "prompt-v3",
        "contract_version": "contract-v2",
        "attempts": 5,
        "accepted_final_shots": 2,
        "failed_attempts": 2,
        "abandoned_attempts": 1,
        "cost_rmb": 30.0,
    }


def test_zero_accepted_shots_reports_efficiency_as_unavailable() -> None:
    result = aggregate_production_metrics([
        {"shot_id": "shot-x", "attempt": 1, "status": "failed", "accepted_final": False, "cost_rmb": 6, "wall_clock_minutes": 8, "issue_codes": []},
    ])

    assert result["counts"]["accepted_final_shots"] == 0
    assert result["rmb_per_accepted_final_minute"] is None
    assert result["regenerated_shots_per_accepted_shot"] is None
    assert result["failed_abandoned"]["cost_rmb"] == 6.0


def test_readiness_tiers_are_distinct_and_require_separate_day_runs() -> None:
    deterministic = {"contract_tests": True, "frontend_build": True, "browser_suite": True}
    internal = {"passed": True, "persisted_local_data": True}
    live_runs = [
        {"date": "2026-07-09", "episodes": 3, "passed": True, "thresholds_passed": True, "manual_db_repair": False},
        {"date": "2026-07-10", "episodes": 3, "passed": True, "thresholds_passed": True, "manual_db_repair": False},
        {"date": "2026-07-11", "episodes": 3, "passed": True, "thresholds_passed": True, "manual_db_repair": False},
    ]

    deterministic_only = evaluate_readiness_tiers(deterministic, {}, [])
    assert deterministic_only["current_tier"] == "deterministic_ready"
    internal_ready = evaluate_readiness_tiers(deterministic, internal, [])
    assert internal_ready["current_tier"] == "internal_trial_ready"
    candidate = evaluate_readiness_tiers(deterministic, internal, live_runs[:1])
    assert candidate["current_tier"] == "series_production_candidate"
    commercial = evaluate_readiness_tiers(deterministic, internal, live_runs)
    assert commercial["current_tier"] == "commercial_series_ready"
    assert all(commercial["tiers"].values())

    missing_manual_repair_evidence = [*live_runs[:2], {key: value for key, value in live_runs[2].items() if key != "manual_db_repair"}]
    fail_closed = evaluate_readiness_tiers(deterministic, internal, missing_manual_repair_evidence)
    assert fail_closed["current_tier"] == "series_production_candidate"
    assert fail_closed["tiers"]["commercial_series_ready"] is False


def test_golden_series_fixture_has_sanitized_three_episode_contract() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "golden_series_task8.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    assert payload["sanitized_test_fiction"] is True
    assert 8 <= len(payload["chapters"]) <= 12
    assert len(payload["episodes"]) == 3
    assert all(asset["approval_status"] == "approved" for asset in payload["approved_assets"])
    assert payload["expected_state_events"]
    assert all(episode["required_dialogue"] for episode in payload["episodes"])
    assert all(episode["quality_annotations"] for episode in payload["episodes"])
    assert payload["asset_policy"] == "generated_test_assets_only"
    assert all(asset["uri"].startswith("generated://") for asset in payload["approved_assets"])


def test_dashboard_accepts_only_final_v2_and_keeps_all_media_attempt_costs() -> None:
    async def scenario() -> dict:
        db_path = Path("/tmp/production-os-task8-review.db")
        db_path.unlink(missing_ok=True)
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        now = datetime(2026, 7, 11, 10, 0, 0)
        try:
            async with factory() as db:
                workflow = Workflow(id="wf-metrics", user_id="metrics-user", title="指标", status="completed", metadata_={})
                video_v1 = VideoJob(id="video-v1", user_id="metrics-user", workflow_id=workflow.id, status="succeeded", duration=60, model_id="seedance", created_at=now, updated_at=now + timedelta(minutes=2), extra_data={"shot_id": "shot-1", "cost_rmb": 4, "provider_id": "volcengine", "prompt_skill_version": "prompt-v1", "episode_contract_version": "contract-v1"})
                video_v2 = VideoJob(id="video-v2", user_id="metrics-user", workflow_id=workflow.id, status="succeeded", duration=60, model_id="seedance", created_at=now + timedelta(minutes=3), updated_at=now + timedelta(minutes=6), extra_data={"shot_id": "shot-1", "cost_rmb": 6, "provider_id": "volcengine", "prompt_skill_version": "prompt-v2", "episode_contract_version": "contract-v2"})
                video_v3 = VideoJob(id="video-v3", user_id="metrics-user", workflow_id=workflow.id, status="succeeded", duration=60, model_id="seedance", created_at=now + timedelta(minutes=7), updated_at=now + timedelta(minutes=9), extra_data={"shot_id": "shot-1", "cost_rmb": 2, "provider_id": "volcengine", "prompt_skill_version": "prompt-v3", "episode_contract_version": "contract-v3"})
                supporting = [
                    TTSJob(id="tts-failed", user_id="metrics-user", workflow_id=workflow.id, shot_id="shot-1", text="台词", status="failed", model_id="tts-model", created_at=now, updated_at=now + timedelta(minutes=1), extra_data={"cost_rmb": 1}),
                    MediaGenerationJob(id="media-cancel", user_id="metrics-user", workflow_id=workflow.id, shot_id="shot-1", task_type="shot_audio_video", media_type="audio_video", status="cancelled", created_at=now, updated_at=now + timedelta(minutes=1), extra_data={"cost_rmb": 2}),
                    SynthesisJob(id="synth-failed", user_id="metrics-user", workflow_id=workflow.id, video_url="/v.mp4", status="failed", model_id="ffmpeg", created_at=now, updated_at=now + timedelta(minutes=1), extra_data={"cost_rmb": 3}),
                    ImageJob(id="image-failed", user_id="metrics-user", shot_id="shot-1", prompt="参考", model="seedream", status="failed", cost="4", created_at=now, updated_at=now + timedelta(minutes=1)),
                ]
                rows = [
                    QualityEvaluation(id=f"qe-{index}", artifact_id="video-v2", artifact_type="shot_video", workflow_id=workflow.id, shot_id="shot-1", dimension=dimension, expected_state={}, observed_state={}, evidence={"issue_codes": []}, score=100, confidence=1, severity="pass", blocking=False, threshold_version="threshold-v1", evaluator_version="eval-v1", created_at=now, evaluated_at=now)
                    for index, dimension in enumerate(("narrative_truth", "character_visual", "scene_prop_state", "motion_camera", "voice_lipsync", "delivery_integrity"))
                ]
                incomplete_newer = QualityEvaluation(id="qe-v3-only", artifact_id="video-v3", artifact_type="shot_video", workflow_id=workflow.id, shot_id="shot-1", dimension="narrative_truth", expected_state={}, observed_state={}, evidence={"issue_codes": []}, score=100, confidence=1, severity="pass", blocking=False, threshold_version="threshold-v1", evaluator_version="eval-v1", created_at=now + timedelta(minutes=10), evaluated_at=now + timedelta(minutes=10))
                db.add_all([workflow, video_v1, video_v2, video_v3, *supporting, *rows, incomplete_newer])
                await db.commit()
                return await _get_production_metrics(db, "metrics-user")
        finally:
            await engine.dispose()
            db_path.unlink(missing_ok=True)

    result = asyncio.run(scenario())
    assert result["counts"]["attempts"] == 7
    assert result["counts"]["accepted_final_shots"] == 1
    assert result["first_pass_shot_acceptance_rate"] == 0.0
    assert result["accepted_final_minutes"] == 1.0
    assert result["rmb_per_accepted_final_minute"] == 22.0
    assert result["failed_abandoned"] == {"attempt_count": 4, "cost_rmb": 10.0, "wall_clock_minutes": 4.0}
    assert result["evidence_missing"]["provider_id"] >= 1
    assert result["readiness"]["current_tier"] == "not_ready"


def test_readiness_evidence_writer_merges_runs_and_enforces_workflow_owner() -> None:
    async def scenario():
        db_path = Path("/tmp/production-os-task8-readiness.db")
        db_path.unlink(missing_ok=True)
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with factory() as db:
                db.add(Workflow(id="wf-readiness", user_id="owner", title="就绪证据", status="completed", metadata_={}))
                await db.commit()
                await persist_production_readiness_evidence(db, "owner", "wf-readiness", {
                    "deterministic": {"contract_tests": True, "frontend_build": True, "browser_suite": True},
                    "internal_trial": {"passed": True, "persisted_local_data": True},
                    "live_run": {"run_id": "run-1", "date": "2026-07-10", "episodes": 3, "passed": True, "thresholds_passed": True, "manual_db_repair": False},
                })
                from app.api.v1.endpoints import dashboard as dashboard_endpoint
                original_gate = dashboard_endpoint._readiness_evidence_write_allowed
                dashboard_endpoint._readiness_evidence_write_allowed = lambda: True
                try:
                    api_result = await write_production_readiness_evidence(
                        ProductionReadinessEvidenceRequest(
                            workflow_id="wf-readiness",
                            live_run={"run_id": "run-2", "date": "2026-07-11", "episodes": 3, "passed": True, "thresholds_passed": True, "manual_db_repair": False},
                        ),
                        db,
                        "owner",
                    )
                finally:
                    dashboard_endpoint._readiness_evidence_write_allowed = original_gate
                merged = api_result["evidence"]
                try:
                    await persist_production_readiness_evidence(db, "other", "wf-readiness", {"live_run": {"run_id": "bad"}})
                except ValueError as error:
                    denied = str(error)
                else:
                    denied = ""
                return merged, denied
        finally:
            await engine.dispose()
            db_path.unlink(missing_ok=True)

    merged, denied = asyncio.run(scenario())
    assert [run["run_id"] for run in merged["live_runs"]] == ["run-1", "run-2"]
    assert merged["deterministic"]["frontend_build"] is True
    assert merged["internal_trial"]["persisted_local_data"] is True
    assert "workflow not found" in denied


def test_readiness_endpoint_rejects_three_client_attestations_outside_isolated_dev() -> None:
    async def scenario() -> tuple[list[int], dict]:
        db_path = Path("/tmp/production-os-task8-readiness-denied.db")
        db_path.unlink(missing_ok=True)
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with factory() as db:
                workflow = Workflow(id="wf-readiness-denied", user_id="owner", title="禁止自报", status="completed", metadata_={})
                db.add(workflow)
                await db.commit()
                statuses = []
                for index, date in enumerate(("2026-07-09", "2026-07-10", "2026-07-11"), start=1):
                    try:
                        await write_production_readiness_evidence(
                            ProductionReadinessEvidenceRequest(
                                workflow_id=workflow.id,
                                deterministic={"contract_tests": True, "frontend_build": True, "browser_suite": True},
                                internal_trial={"passed": True, "persisted_local_data": True},
                                live_run={
                                    "run_id": f"forged-{index}", "date": date, "episodes": 3,
                                    "passed": True, "thresholds_passed": True, "manual_db_repair": False,
                                },
                            ),
                            db,
                            "owner",
                        )
                    except HTTPException as exc:
                        statuses.append(exc.status_code)
                await db.refresh(workflow)
                return statuses, dict(workflow.metadata_ or {})
        finally:
            await engine.dispose()
            db_path.unlink(missing_ok=True)

    from app.api.v1.endpoints import dashboard as dashboard_endpoint
    original_gate = dashboard_endpoint._readiness_evidence_write_allowed
    dashboard_endpoint._readiness_evidence_write_allowed = lambda: False
    try:
        statuses, metadata = asyncio.run(scenario())
    finally:
        dashboard_endpoint._readiness_evidence_write_allowed = original_gate
    assert statuses == [403, 403, 403]
    assert "production_readiness_evidence" not in metadata


def test_isolated_dev_writer_accepts_live_audit_only() -> None:
    async def scenario() -> tuple[str, int]:
        db_path = Path("/tmp/production-os-task8-readiness-dev.db")
        db_path.unlink(missing_ok=True)
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with factory() as db:
                db.add(Workflow(id="wf-readiness-dev", user_id="owner", title="隔离审计", status="completed", metadata_={}))
                await db.commit()
                from app.api.v1.endpoints import dashboard as dashboard_endpoint
                original_gate = dashboard_endpoint._readiness_evidence_write_allowed
                dashboard_endpoint._readiness_evidence_write_allowed = lambda: True
                try:
                    rejected = 0
                    try:
                        await write_production_readiness_evidence(
                            ProductionReadinessEvidenceRequest(
                                workflow_id="wf-readiness-dev",
                                deterministic={"contract_tests": True},
                            ),
                            db,
                            "owner",
                        )
                    except HTTPException as exc:
                        rejected = exc.status_code
                    accepted = await write_production_readiness_evidence(
                        ProductionReadinessEvidenceRequest(
                            workflow_id="wf-readiness-dev",
                            live_run={
                                "run_id": "isolated-live-1", "date": "2026-07-11", "episodes": 3,
                                "passed": True, "thresholds_passed": True, "manual_db_repair": False,
                                "job_ids": ["job-1"],
                            },
                        ),
                        db,
                        "owner",
                    )
                finally:
                    dashboard_endpoint._readiness_evidence_write_allowed = original_gate
                return accepted["evidence"]["live_runs"][0]["run_id"], rejected
        finally:
            await engine.dispose()
            db_path.unlink(missing_ok=True)

    run_id, rejected = asyncio.run(scenario())
    assert run_id == "isolated-live-1"
    assert rejected == 422


def test_dashboard_analytics_get_returns_production_metrics() -> None:
    init_db()

    async def override_user_id() -> str:
        return "analytics-metrics-user"

    app.dependency_overrides[get_current_user_id] = override_user_id
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/api/v1/dashboard/analytics?days=7")
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["data_source"] == "database"
    assert "production_metrics" in payload
    assert "readiness" in payload["production_metrics"]
