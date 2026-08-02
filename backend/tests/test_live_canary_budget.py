from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm.exc import StaleDataError

from app.core.database import Base
from app.models.llm_config import LLMConfig, LLMModel, LLMProvider
from app.models.novel import Novel
from app.models.series_production_run import SeriesProductionRun
from app.services.live_canary_budget import (
    BudgetExceeded,
    BindingValidationError,
    InvalidAccountingInput,
    reconcile_reservation,
    release_reservation,
    required_tested_at_for_run,
    trusted_live_canary_policy,
    link_provider_attempt,
    settle_linked_provider_attempt,
    bind_provider_operation_task,
    prepare_provider_operation,
    settle_provider_operation,
    settle_synchronous_provider_operation,
    mark_operation_manual_reconcile,
    settle_confirmed_provider_rejection,
    reserve_budget,
    validate_model_bindings,
)
from app.services.live_canary_staging_proof import PROOF_KEY, build_staging_proof
from app.services.live_canary_bindings import (
    validate_persisted_model_bindings,
    validate_required_model_bindings,
)


@pytest_asyncio.fixture
async def db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'budget.sqlite'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        yield session
    await engine.dispose()


async def _run(db: AsyncSession, *, maximum: str = "10.00") -> SeriesProductionRun:
    user_id = f"user-{uuid4()}"
    novel = Novel(id=str(uuid4()), user_id=user_id, title="synthetic", status="draft")
    run = SeriesProductionRun(
        id=str(uuid4()), user_id=user_id, novel_id=novel.id,
        series_plan_version="v1", idempotency_key=str(uuid4()), status="created",
        requested_stages=[], model_bindings={}, budget_policy={"max_rmb": maximum},
        cost_summary={}, gate_summary={}, run_metadata={}, episodes=[], version=1,
    )
    db.add_all([novel, run])
    await db.commit()
    return run


@pytest.mark.asyncio
async def test_persisted_run_binding_survives_elapsed_freshness_but_not_config_change(db: AsyncSession) -> None:
    run = await _run(db)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    provider = LLMProvider(id=str(uuid4()), name=f"snapshot-{uuid4()}", is_active=True)
    model = LLMModel(id=str(uuid4()), provider_id=provider.id, model_id="snapshot-video",
                     model_name="snapshot", model_type="video-generation",
                     capabilities=["video-generation"], is_active=True)
    config = LLMConfig(id=str(uuid4()), user_id=run.user_id, model_id=model.id, name="snapshot",
                       api_key=b"opaque", is_active=True, test_status="success", tested_at=now)
    db.add_all([provider, model, config])
    await db.commit()
    await validate_required_model_bindings(
        db, run, {"video": config.id}, required_tested_at=now - timedelta(seconds=1),
        freshness_seconds=300, persist=True,
    )

    verified = await validate_persisted_model_bindings(db, run, required_capabilities={"video"})
    assert verified["video"]["config_id"] == config.id

    config.is_active = False
    await db.commit()
    with pytest.raises(BindingValidationError, match="video"):
        await validate_persisted_model_bindings(db, run, required_capabilities={"video"})


@pytest.mark.asyncio
async def test_budget_reservation_is_decimal_idempotent_and_reconciles_actual(db: AsyncSession) -> None:
    run = await _run(db)

    first = await reserve_budget(db, run, reservation_id="job-1", estimate_rmb=Decimal("3.335"))
    duplicate = await reserve_budget(db, run, reservation_id="job-1", estimate_rmb=Decimal("3.335"))
    assert first == duplicate
    assert run.cost_summary["reserved_rmb"] == "3.34"

    await reconcile_reservation(db, run, reservation_id="job-1", actual_rmb=Decimal("2.015"))
    assert run.cost_summary["reserved_rmb"] == "0.00"
    assert run.cost_summary["spent_rmb"] == "2.02"

    await reserve_budget(db, run, reservation_id="job-2", estimate_rmb=Decimal("7.98"))
    with pytest.raises(BudgetExceeded):
        await reserve_budget(db, run, reservation_id="job-3", estimate_rmb=Decimal("0.01"))


@pytest.mark.asyncio
@pytest.mark.parametrize("amount", [Decimal("0"), Decimal("NaN"), Decimal("Infinity"), Decimal("1000000001")])
async def test_reservation_rejects_nonpositive_nonfinite_and_huge_amounts(db: AsyncSession, amount: Decimal) -> None:
    run = await _run(db, maximum="2000000000")
    with pytest.raises(InvalidAccountingInput):
        await reserve_budget(db, run, reservation_id="bounded", estimate_rmb=amount)


@pytest.mark.asyncio
async def test_reservation_id_is_trimmed_bounded_and_terminal_duplicates_fail(db: AsyncSession) -> None:
    run = await _run(db)
    await reserve_budget(db, run, reservation_id="  job  ", estimate_rmb=Decimal("1"))
    await release_reservation(db, run, reservation_id="job", provider_state="submission_failed")
    with pytest.raises(InvalidAccountingInput):
        await reserve_budget(db, run, reservation_id="job", estimate_rmb=Decimal("1"))
    with pytest.raises(InvalidAccountingInput):
        await reserve_budget(db, run, reservation_id="x" * 201, estimate_rmb=Decimal("1"))


@pytest.mark.asyncio
async def test_failed_submission_releases_but_unknown_provider_state_retains_reservation(db: AsyncSession) -> None:
    run = await _run(db)
    await reserve_budget(db, run, reservation_id="failed", estimate_rmb=Decimal("1.00"))
    await release_reservation(db, run, reservation_id="failed", provider_state="submission_failed")
    assert run.cost_summary["reserved_rmb"] == "0.00"

    await reserve_budget(db, run, reservation_id="unknown", estimate_rmb=Decimal("1.00"))
    await release_reservation(db, run, reservation_id="unknown", provider_state="unknown")
    assert run.cost_summary["reserved_rmb"] == "1.00"


@pytest.mark.asyncio
async def test_reconcile_overage_is_recorded_and_blocks_future_reservations(db: AsyncSession) -> None:
    run = await _run(db, maximum="10")
    await reserve_budget(db, run, reservation_id="one", estimate_rmb=Decimal("4"))
    await reserve_budget(db, run, reservation_id="two", estimate_rmb=Decimal("4"))
    await reconcile_reservation(db, run, reservation_id="one", actual_rmb=Decimal("7"))
    assert run.cost_summary["reservations"]["one"]["state"] == "reconciled_over_budget"
    assert run.budget_policy["blocked"] is True
    assert run.budget_policy["overage_rmb"] == "1.00"
    with pytest.raises(BudgetExceeded):
        await reserve_budget(db, run, reservation_id="three", estimate_rmb=Decimal("0.01"))


@pytest.mark.asyncio
async def test_stale_concurrent_budget_update_fails_closed(db: AsyncSession) -> None:
    run = await _run(db)
    maker = async_sessionmaker(db.bind, expire_on_commit=False, class_=AsyncSession)
    async with maker() as left, maker() as right:
        left_run = await left.get(SeriesProductionRun, run.id)
        right_run = await right.get(SeriesProductionRun, run.id)
        await reserve_budget(left, left_run, reservation_id="left", estimate_rmb=Decimal("6.00"))
        with pytest.raises(StaleDataError):
            await reserve_budget(right, right_run, reservation_id="right", estimate_rmb=Decimal("6.00"))


@pytest.mark.asyncio
async def test_bindings_require_owned_active_fresh_success_and_matching_capability(db: AsyncSession, monkeypatch) -> None:
    run = await _run(db)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    capability_specs = {
        "text": ["chat"], "image": ["text-to-image"],
        "tts": ["text_to_speech"], "video": [],
    }
    bindings = {}
    for capability, tags in capability_specs.items():
        provider = LLMProvider(id=str(uuid4()), name=f"provider-{capability}-{uuid4()}", is_active=True)
        model = LLMModel(
            id=str(uuid4()), provider_id=provider.id, model_id=f"model-{capability}",
            model_name=capability,
            model_type="video-generation" if capability == "video" else (capability if capability != "text" else "chat"),
            capabilities=tags, is_active=True,
        )
        config = LLMConfig(
            id=str(uuid4()), user_id=run.user_id, model_id=model.id, name=capability,
            api_key=b"opaque-do-not-snapshot", api_secret=b"opaque-secret",
            is_active=True, test_status="success", tested_at=now,
        )
        db.add_all([provider, model, config])
        bindings[capability] = config.id
    await db.commit()

    snapshot = await validate_model_bindings(
        db, run, bindings, required_tested_at=now - timedelta(seconds=1), freshness_seconds=300,
    )
    assert set(snapshot) == set(capability_specs)
    expected_fields = {
        "config_id", "db_model_id", "api_model_id", "provider_id", "tested_at", "proof_kind",
        "contract_version", "prompt_profile", "verification_status",
    }
    assert all(set(item) == expected_fields for item in snapshot.values())
    assert all(item["verification_status"] == "unverified" for item in snapshot.values())
    assert all(item["proof_kind"] == "fresh_server_test" for item in snapshot.values())
    assert run.model_bindings["capabilities"] == snapshot
    assert run.model_bindings["provider_id"] == snapshot["video"]["provider_id"]
    assert run.model_bindings["model_id"] == "model-video"
    assert "opaque" not in repr(snapshot)

    stale = await db.get(LLMConfig, bindings["video"])
    stale.tested_at = now - timedelta(hours=2)
    await db.commit()
    with pytest.raises(BindingValidationError, match="video"):
        await validate_model_bindings(
            db, run, bindings, required_tested_at=now - timedelta(seconds=1), freshness_seconds=300,
        )

    stale.tested_at = now
    stale.test_status = "pending"
    await db.commit()
    with pytest.raises(BindingValidationError, match="video"):
        await validate_model_bindings(db, run, bindings, required_tested_at=now - timedelta(seconds=1))

    import app.services.series_run_orchestrator as orchestrator_module
    from app.services.series_run_orchestrator import SeriesRunOrchestrator

    async def ready_preflight(_db, _run, **_kwargs):
        return {"ready": True, "issues": [], "input_snapshot": {}, "snapshot_hash": "synthetic"}

    monkeypatch.setattr(orchestrator_module, "evaluate_media_preflight", ready_preflight)
    run.status = "anchor_ready"
    run.budget_policy = {"live_canary": True, "max_rmb": "10.00"}
    await db.commit()
    with pytest.raises(BindingValidationError, match="video"):
        await SeriesRunOrchestrator().enter_media_running(db, run)

    stale.test_status = "success"
    stale.tested_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.commit()
    await SeriesRunOrchestrator().enter_media_running(db, run)
    assert run.status == "media_running"


@pytest.mark.asyncio
@pytest.mark.parametrize("proof_state", ["missing", "tampered", "expired"])
async def test_isolated_staging_requires_recent_untampered_historical_success(
    db: AsyncSession, proof_state: str,
) -> None:
    run = await _run(db)
    run.budget_policy = {
        "profile": "isolated_live_canary", "live_canary": True, "max_rmb": "10.00",
    }
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    historical = now - timedelta(days=30)
    bindings: dict[str, str] = {}
    for capability, tags in {
        "text": ["chat"], "image": ["text-to-image"],
        "tts": ["text-to-speech"], "video": ["image-to-video"],
    }.items():
        provider = LLMProvider(
            id=str(uuid4()), name=f"isolated-{capability}-{uuid4()}", is_active=True,
        )
        model = LLMModel(
            id=str(uuid4()), provider_id=provider.id, model_id=f"isolated-{capability}",
            model_name=capability, model_type=capability, capabilities=tags, is_active=True,
        )
        config = LLMConfig(
            id=str(uuid4()), user_id=run.user_id, model_id=model.id, name=capability,
            api_key=b"opaque", is_active=True, test_status="success", tested_at=historical,
        )
        staged_at = now - timedelta(minutes=16 if proof_state == "expired" else 1)
        proof = build_staging_proof(
            staged_at=staged_at, source_test_status="success", source_tested_at=historical,
            config_id=config.id, model_id=model.id, provider_id=provider.id,
            target_user_id=run.user_id,
        )
        config.extra_params = {} if proof_state == "missing" else {PROOF_KEY: proof}
        if proof_state == "tampered":
            config.extra_params[PROOF_KEY] = {**proof, "provider_id": "foreign-provider"}
        db.add_all([provider, model, config])
        bindings[capability] = config.id
    await db.commit()

    with pytest.raises(BindingValidationError, match="isolated staging"):
        await validate_model_bindings(
            db, run, bindings, required_tested_at=now, freshness_seconds=300,
        )


@pytest.mark.asyncio
async def test_isolated_staging_is_explicit_proof_not_a_fresh_config_test(db: AsyncSession) -> None:
    run = await _run(db)
    run.budget_policy = {
        "profile": "isolated_live_canary", "live_canary": True, "max_rmb": "10.00",
    }
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    historical = now - timedelta(days=30)
    bindings: dict[str, str] = {}
    for capability, tags in {
        "text": ["chat"], "image": ["text-to-image"],
        "tts": ["text-to-speech"], "video": ["image-to-video"],
    }.items():
        provider = LLMProvider(
            id=str(uuid4()), name=f"staged-{capability}-{uuid4()}", is_active=True,
        )
        model = LLMModel(
            id=str(uuid4()), provider_id=provider.id, model_id=f"staged-{capability}",
            model_name=capability, model_type=capability, capabilities=tags, is_active=True,
        )
        config = LLMConfig(
            id=str(uuid4()), user_id=run.user_id, model_id=model.id, name=capability,
            api_key=b"opaque", is_active=True, test_status="success", tested_at=historical,
        )
        config.extra_params = {PROOF_KEY: build_staging_proof(
            staged_at=now - timedelta(minutes=1), source_test_status="success",
            source_tested_at=historical, config_id=config.id, model_id=model.id,
            provider_id=provider.id, target_user_id=run.user_id,
        )}
        db.add_all([provider, model, config])
        bindings[capability] = config.id
    await db.commit()

    snapshot = await validate_model_bindings(
        db, run, bindings, required_tested_at=now, freshness_seconds=300,
    )

    assert all(item["proof_kind"] == "isolated_staging" for item in snapshot.values())
    assert all(item["tested_at"] == historical.isoformat() for item in snapshot.values())

    run.budget_policy = {"max_rmb": "10.00"}
    await db.commit()
    with pytest.raises(BindingValidationError, match="fresh successful server test"):
        await validate_model_bindings(
            db, run, bindings, required_tested_at=now, freshness_seconds=300,
        )


def test_public_budget_mutation_routes_do_not_exist() -> None:
    from main import app
    paths = {route.path for route in app.routes}
    assert not any(path.endswith("/budget/reserve") for path in paths)
    assert not any(path.endswith("/budget/reconcile") for path in paths)
    assert not any(path.endswith("/budget/release") for path in paths)


def test_required_time_normalizes_offset_to_utc_and_rejects_malformed() -> None:
    run = SeriesProductionRun(
        created_at=datetime(2026, 7, 12, 1, 0, 0),
        run_metadata={"canary_staging_required_at": "2026-07-12T10:30:00+08:00"},
    )
    assert required_tested_at_for_run(run) == datetime(2026, 7, 12, 2, 30, 0)
    run.run_metadata = {"canary_staging_required_at": "not-a-time"}
    with pytest.raises(BindingValidationError, match="timestamp"):
        required_tested_at_for_run(run)


def test_live_policy_uses_only_server_owned_amounts() -> None:
    environment = {
        "LIVE_CANARY_MAX_RMB": "10",
        "LIVE_CANARY_IMAGE_ESTIMATE_RMB": "1",
        "LIVE_CANARY_VIDEO_ESTIMATE_RMB": "2",
        "LIVE_CANARY_TTS_ESTIMATE_RMB": "0.5",
    }
    policy = trusted_live_canary_policy({"profile": "isolated_live_canary"}, environ=environment)
    assert policy["max_rmb"] == "10.00"
    assert policy["estimates_rmb"] == {"image": "1.00", "video": "2.00", "tts": "0.50"}
    with pytest.raises(InvalidAccountingInput):
        trusted_live_canary_policy({"profile": "isolated_live_canary", "max_rmb": "999"}, environ=environment)


@pytest.mark.asyncio
async def test_provider_linkage_is_durable_and_poll_settlement_is_idempotent(db: AsyncSession) -> None:
    run = await _run(db)
    await reserve_budget(db, run, reservation_id="provider-attempt", estimate_rmb=Decimal("2"))
    linked = await link_provider_attempt(
        db, run, reservation_id="provider-attempt", provider_task_id="provider-task",
        job_id="job-1", capability="video",
    )
    assert linked["provider_task_id"] == "provider-task"
    accounting = {
        "series_run_id": run.id, "reservation_id": "provider-attempt",
        "provider_task_id": "provider-task", "capability": "video",
    }
    await settle_linked_provider_attempt(
        db, user_id=run.user_id, accounting=accounting, provider_task_id="provider-task",
        provider_status="succeeded", actual_rmb="1.25",
    )
    await settle_linked_provider_attempt(
        db, user_id=run.user_id, accounting=accounting, provider_task_id="provider-task",
        provider_status="succeeded", actual_rmb="1.25",
    )
    assert run.cost_summary["spent_rmb"] == "1.25"
    assert run.cost_summary["reserved_rmb"] == "0.00"


@pytest.mark.asyncio
async def test_operation_is_persisted_before_provider_task_and_settlement_requires_exact_match(db: AsyncSession) -> None:
    run = await _run(db)
    operation = await prepare_provider_operation(
        db, run, capability="video", job_type="video_job", job_id="job-prelinked",
        reservation_id="operation-reservation", estimate_rmb=Decimal("2"),
    )
    assert operation.provider_task_id is None
    assert run.cost_summary["reservations"]["operation-reservation"]["job_id"] == "job-prelinked"
    await bind_provider_operation_task(db, operation, provider_task_id="provider-accepted")
    await bind_provider_operation_task(db, operation, provider_task_id="provider-accepted")
    with pytest.raises(InvalidAccountingInput):
        await settle_provider_operation(
            db, operation_id=operation.id, user_id=run.user_id, run_id=run.id,
            reservation_id="operation-reservation", capability="tts", job_id="job-prelinked",
            provider_task_id="provider-accepted", provider_status="succeeded", actual_rmb="1.50",
        )
    await settle_provider_operation(
        db, operation_id=operation.id, user_id=run.user_id, run_id=run.id,
        reservation_id="operation-reservation", capability="video", job_id="job-prelinked",
        provider_task_id="provider-accepted", provider_status="succeeded", actual_rmb="1.50",
    )
    assert run.cost_summary["spent_rmb"] == "1.50"


@pytest.mark.asyncio
async def test_sync_missing_provider_cost_uses_trusted_estimate_and_manual_recovery_retains(db: AsyncSession) -> None:
    run = await _run(db)
    operation = await prepare_provider_operation(
        db, run, capability="image", job_type="image_job", job_id="sync-image",
        reservation_id="sync-reservation", estimate_rmb=Decimal("1.25"),
    )
    await bind_provider_operation_task(db, operation, provider_task_id="sync-task")
    await settle_synchronous_provider_operation(db, operation, provider_actual_rmb=None)
    assert operation.status == "reconciled"
    assert operation.cost_source == "estimated_as_actual"
    assert run.cost_summary["spent_rmb"] == "1.25"

    unknown = await prepare_provider_operation(
        db, run, capability="tts", job_type="tts_job", job_id="unknown-job",
        reservation_id="unknown-recovery", estimate_rmb=Decimal("0.50"),
    )
    await mark_operation_manual_reconcile(db, unknown, reason="provider_lookup_unsupported")
    assert unknown.status == "unknown_manual_reconcile"
    assert run.budget_policy["blocked"] is True
    assert run.cost_summary["reserved_rmb"] == "0.50"


@pytest.mark.asyncio
async def test_async_terminal_success_without_provider_cost_uses_reserved_estimate(db: AsyncSession) -> None:
    run = await _run(db)
    operation = await prepare_provider_operation(
        db, run, capability="video", job_type="video_job", job_id="async-video",
        reservation_id="async-video-reservation", estimate_rmb=Decimal("3.50"),
    )
    await bind_provider_operation_task(db, operation, provider_task_id="video-task")

    await settle_provider_operation(
        db, operation_id=operation.id, user_id=run.user_id, run_id=run.id,
        reservation_id=operation.reservation_id, capability="video", job_id=operation.job_id,
        provider_task_id="video-task", provider_status="succeeded", actual_rmb=None,
    )

    assert operation.status == "reconciled"
    assert operation.cost_source == "estimated_as_actual"
    assert run.cost_summary["spent_rmb"] == "3.50"
    assert run.cost_summary["reserved_rmb"] == "0.00"
    assert run.cost_summary["reservations"][operation.reservation_id]["provider_cost_missing"] is True


@pytest.mark.asyncio
async def test_mocked_provider_observes_precommitted_operation_then_bind_and_settle(db: AsyncSession) -> None:
    run = await _run(db)
    operation = await prepare_provider_operation(
        db, run, capability="tts", job_type="tts_job", job_id="ordered-job",
        reservation_id="ordered-reservation", estimate_rmb=Decimal("0.75"),
    )
    calls = []

    async def provider_call():
        persisted = await db.get(type(operation), operation.id)
        assert persisted.status == "reserved"
        assert persisted.provider_task_id is None
        assert run.cost_summary["reserved_rmb"] == "0.75"
        calls.append("provider")
        return {"task_id": "ordered-task", "audio_url": "https://invalid.example/audio.mp3"}

    result = await provider_call()
    await bind_provider_operation_task(db, operation, provider_task_id=result["task_id"])
    await settle_synchronous_provider_operation(db, operation, provider_actual_rmb=None)
    assert calls == ["provider"]
    assert operation.status == "reconciled"
    assert run.cost_summary["reservations"]["ordered-reservation"]["state"] == "reconciled"

    rejected = await prepare_provider_operation(
        db, run, capability="image", job_type="image_job", job_id="reject-job",
        reservation_id="reject-reservation", estimate_rmb=Decimal("0.25"),
    )
    await settle_confirmed_provider_rejection(db, run, reservation_id=rejected.reservation_id)
    assert rejected.status == "confirmed_rejected_before_acceptance"

    unknown = await prepare_provider_operation(
        db, run, capability="video", job_type="video_job", job_id="unknown-order-job",
        reservation_id="unknown-order-reservation", estimate_rmb=Decimal("0.25"),
    )
    assert unknown.status == "reserved"
    assert run.cost_summary["reservations"][unknown.reservation_id]["state"] == "reserved"
