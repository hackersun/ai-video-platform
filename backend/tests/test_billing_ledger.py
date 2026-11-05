"""R03: billing ledger + spend caps (fail-closed; fake excluded from totals)."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.billing import BillingLedgerEntry
from app.models.novel import Novel
from app.models.series_production_run import SeriesProductionRun
from app.services.billing_guard import (
    LiveCallsNotOptedIn,
    SpendCapExceeded,
    default_caps_rmb,
    ensure_user_billing_settings,
    get_or_create_settings,
    ledger_totals_rmb,
)
from app.services.live_canary_budget import BudgetExceeded, reserve_budget, reconcile_reservation, release_reservation
from app.db_migrations.runner import register_production_models


@pytest.fixture(autouse=True)
def _clear_ambient_fake_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ambient e2e shells often export DETERMINISTIC_PROVIDER_FAKE=1; real-path tests must not inherit it."""
    monkeypatch.delenv("DETERMINISTIC_PROVIDER_FAKE", raising=False)


@pytest_asyncio.fixture
async def db(tmp_path):
    register_production_models()
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'billing.sqlite'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        yield session
    await engine.dispose()


async def _run(db: AsyncSession, *, maximum: str = "100.00", user_id: str | None = None) -> SeriesProductionRun:
    uid = user_id or f"user-{uuid4()}"
    novel = Novel(id=str(uuid4()), user_id=uid, title="billing", status="draft")
    run = SeriesProductionRun(
        id=str(uuid4()), user_id=uid, novel_id=novel.id,
        series_plan_version="v1", idempotency_key=str(uuid4()), status="created",
        requested_stages=[], model_bindings={}, budget_policy={"max_rmb": maximum},
        cost_summary={}, gate_summary={}, run_metadata={}, episodes=[], version=1,
    )
    db.add_all([novel, run])
    await db.commit()
    return run


@pytest.mark.asyncio
async def test_defaults_come_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BILLING_PER_USER_CAP_RMB", "180.00")
    monkeypatch.setenv("BILLING_PER_PIPELINE_CAP_RMB", "40.00")
    assert default_caps_rmb() == (Decimal("180.00"), Decimal("40.00"))


@pytest.mark.asyncio
async def test_reserve_without_opt_in_raises_and_writes_blocked_ledger(db: AsyncSession) -> None:
    run = await _run(db)
    await ensure_user_billing_settings(db, run.user_id)  # defaults: not opted in
    with pytest.raises(LiveCallsNotOptedIn) as exc:
        await reserve_budget(db, run, reservation_id="r1", estimate_rmb=Decimal("1.00"))
    assert isinstance(exc.value, BudgetExceeded)
    totals = await ledger_totals_rmb(db, user_id=run.user_id)
    assert totals["reserved"] == Decimal("0.00")
    assert totals["used_toward_cap"] == Decimal("0.00")
    assert totals["blocked_cap"] == Decimal("1.00")
    rows = (await db.execute(
        __import__("sqlalchemy", fromlist=["select"]).select(BillingLedgerEntry).where(
            BillingLedgerEntry.user_id == run.user_id
        )
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].status == "blocked_cap"
    assert rows[0].is_fake is False


@pytest.mark.asyncio
async def test_runaway_retry_stops_at_user_cap(db: AsyncSession) -> None:
    run = await _run(db, maximum="1000.00")
    settings = await get_or_create_settings(db, run.user_id)
    settings.live_calls_opt_in = True
    settings.per_user_cap_rmb = "5.00"
    settings.per_pipeline_cap_rmb = "50.00"
    await db.commit()

    await reserve_budget(db, run, reservation_id="ok-1", estimate_rmb=Decimal("3.00"))
    await reconcile_reservation(db, run, reservation_id="ok-1", actual_rmb=Decimal("3.00"))

    with pytest.raises(SpendCapExceeded):
        await reserve_budget(db, run, reservation_id="over", estimate_rmb=Decimal("3.00"))

    # Retry with a new reservation id still fails (runaway protection)
    with pytest.raises(SpendCapExceeded):
        await reserve_budget(db, run, reservation_id="over-retry", estimate_rmb=Decimal("3.00"))

    totals = await ledger_totals_rmb(db, user_id=run.user_id)
    assert totals["settled"] == Decimal("3.00")
    assert totals["reserved"] == Decimal("0.00")
    # fake excluded
    assert totals["used_toward_cap"] == Decimal("3.00")


@pytest.mark.asyncio
async def test_pipeline_cap_blocks_and_fake_excluded(db: AsyncSession) -> None:
    run = await _run(db, maximum="1000.00")
    settings = await get_or_create_settings(db, run.user_id)
    settings.live_calls_opt_in = True
    settings.per_user_cap_rmb = "200.00"
    settings.per_pipeline_cap_rmb = "4.00"
    await db.commit()

    # Fake reservation must not count toward caps
    await reserve_budget(
        db, run, reservation_id="fake-1", estimate_rmb=Decimal("3.50"),
        is_fake=True, pipeline_id="pipe-1",
    )
    totals = await ledger_totals_rmb(db, user_id=run.user_id)
    assert totals["used_toward_cap"] == Decimal("0.00")
    assert totals["reserved"] == Decimal("0.00")  # fake excluded

    await reserve_budget(
        db, run, reservation_id="live-1", estimate_rmb=Decimal("3.00"),
        pipeline_id="pipe-1",
    )
    with pytest.raises(SpendCapExceeded):
        await reserve_budget(
            db, run, reservation_id="live-2", estimate_rmb=Decimal("2.00"),
            pipeline_id="pipe-1",
        )


@pytest.mark.asyncio
async def test_settle_and_release_update_ledger_status(db: AsyncSession) -> None:
    run = await _run(db, maximum="50.00")
    settings = await get_or_create_settings(db, run.user_id)
    settings.live_calls_opt_in = True
    settings.per_user_cap_rmb = "50.00"
    settings.per_pipeline_cap_rmb = "50.00"
    await db.commit()

    await reserve_budget(db, run, reservation_id="settle-me", estimate_rmb=Decimal("2.50"),
                         capability="image", provider="ark", model="seedream")
    await reconcile_reservation(db, run, reservation_id="settle-me", actual_rmb=Decimal("2.40"))
    totals = await ledger_totals_rmb(db, user_id=run.user_id)
    assert totals["settled"] == Decimal("2.40")
    assert totals["reserved"] == Decimal("0.00")

    await reserve_budget(db, run, reservation_id="release-me", estimate_rmb=Decimal("1.00"))
    await release_reservation(db, run, reservation_id="release-me", provider_state="submission_failed")
    totals = await ledger_totals_rmb(db, user_id=run.user_id)
    assert totals["released"] == Decimal("1.00")
    assert totals["used_toward_cap"] == Decimal("2.40")


@pytest.mark.asyncio
async def test_prepare_requires_opt_in_outside_fake(db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.models.publication_pipeline import NovelPublicationPipeline
    from app.services.publication_pipeline_media import PipelineMediaBlocked
    from app.services import publication_pipeline_prepare as prep

    monkeypatch.setattr(
        "app.services.deterministic_provider_fake.deterministic_provider_fake_enabled",
        lambda: False,
    )
    run = await _run(db)
    run.status = "shots_ready"
    run.model_bindings = {
        "capabilities": {
            "text": {"config_id": "c-text"},
            "image": {"config_id": "c-image"},
            "tts": {"config_id": "c-tts"},
            "video": {"config_id": "c-video"},
        }
    }
    await db.commit()
    pipeline = NovelPublicationPipeline(
        id=str(uuid4()), user_id=run.user_id, novel_id=run.novel_id,
        series_plan_version="v1", idempotency_key=str(uuid4()),
        status="running", stage="media", series_run_id=run.id,
    )
    db.add(pipeline)
    await ensure_user_billing_settings(db, run.user_id)
    await db.commit()

    with pytest.raises(PipelineMediaBlocked) as exc:
        await prep.prepare_run_for_media(db, run, pipeline)
    assert exc.value.code == "live_calls_not_opted_in"
    assert "模型设置" in exc.value.detail or "真实调用" in exc.value.detail

@pytest.mark.asyncio
async def test_reserve_skips_opt_in_when_deterministic_fake_active(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("DETERMINISTIC_PROVIDER_FAKE", "1")
    run = await _run(db)
    await ensure_user_billing_settings(db, run.user_id)  # not opted in
    await reserve_budget(db, run, reservation_id="fake-auto", estimate_rmb=Decimal("1.25"))
    rows = (await db.execute(
        __import__("sqlalchemy", fromlist=["select"]).select(BillingLedgerEntry).where(
            BillingLedgerEntry.user_id == run.user_id,
            BillingLedgerEntry.reservation_id == "fake-auto",
        )
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].is_fake is True
    assert rows[0].status == "reserved"
    totals = await ledger_totals_rmb(db, user_id=run.user_id)
    assert totals["used_toward_cap"] == Decimal("0.00")


@pytest.mark.asyncio
async def test_reserve_requires_opt_in_in_production_even_if_fake_env_set(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DETERMINISTIC_PROVIDER_FAKE", "1")
    run = await _run(db)
    await ensure_user_billing_settings(db, run.user_id)
    with pytest.raises(LiveCallsNotOptedIn):
        await reserve_budget(db, run, reservation_id="prod-block", estimate_rmb=Decimal("1.00"))
    rows = (await db.execute(
        __import__("sqlalchemy", fromlist=["select"]).select(BillingLedgerEntry).where(
            BillingLedgerEntry.user_id == run.user_id,
            BillingLedgerEntry.reservation_id == "prod-block",
        )
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].is_fake is False
    assert rows[0].status == "blocked_cap"


@pytest.mark.asyncio
async def test_prepare_provider_operation_marks_fake_under_deterministic(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.live_canary_budget import prepare_provider_operation

    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("DETERMINISTIC_PROVIDER_FAKE", "1")
    run = await _run(db, maximum="50.00")
    await ensure_user_billing_settings(db, run.user_id)
    op = await prepare_provider_operation(
        db, run, capability="image", job_type="series_composite_reference",
        job_id="job-fake", reservation_id="prep-fake-1", estimate_rmb=Decimal("0.10"),
    )
    assert op is not None
    rows = (await db.execute(
        __import__("sqlalchemy", fromlist=["select"]).select(BillingLedgerEntry).where(
            BillingLedgerEntry.reservation_id == "prep-fake-1",
        )
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].is_fake is True

