from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.novel import Novel
from app.models.series_production_run import SeriesProductionRun
from app.services.live_canary_budget import BudgetExceeded, reserve_budget
from app.services.live_canary_repair_budget import (
    RepairBudgetExtensionError,
    effective_budget_maximum,
    grant_live_canary_repair_extension,
)
from app.services.series_run_reference_preparation import reference_budget_plan_is_safe


@pytest_asyncio.fixture
async def db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'repair-budget.sqlite'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        yield session
    await engine.dispose()


async def _run(db: AsyncSession) -> SeriesProductionRun:
    user_id = f"user-{uuid4()}"
    novel = Novel(id=str(uuid4()), user_id=user_id, title="repair", status="draft")
    run = SeriesProductionRun(
        id=str(uuid4()), user_id=user_id, novel_id=novel.id,
        series_plan_version="v1", idempotency_key=str(uuid4()), status="media_running",
        requested_stages=[], model_bindings={},
        budget_policy={"profile": "isolated_live_canary", "live_canary": True, "max_rmb": "10.00"},
        cost_summary={"spent_rmb": "7.00", "reserved_rmb": "0.00", "reservations": {}},
        gate_summary={}, run_metadata={}, episodes=[], version=1,
    )
    db.add_all([novel, run])
    await db.commit()
    return run


@pytest.mark.asyncio
async def test_one_yuan_repair_extension_is_audited_and_used_by_reservations(db: AsyncSession) -> None:
    run = await _run(db)

    audit = await grant_live_canary_repair_extension(
        db, run, amount=Decimal("1.00"), reason="hair_color_consistency_repair",
        artifact_ids=["stale-reference", "wrong-first-frame"],
    )

    assert audit["effective_maximum_rmb"] == "11.00"
    assert effective_budget_maximum(run) == Decimal("11.00")
    assert run.run_metadata["repair_budget_extension"]["reason"] == "hair_color_consistency_repair"
    await reserve_budget(db, run, reservation_id="repair", estimate_rmb=Decimal("4.00"))
    with pytest.raises(BudgetExceeded):
        await reserve_budget(db, run, reservation_id="over", estimate_rmb=Decimal("0.01"))
    with pytest.raises(RepairBudgetExtensionError, match="already granted"):
        await grant_live_canary_repair_extension(
            db, run, amount=Decimal("1.00"), reason="duplicate", artifact_ids=["another"],
        )


@pytest.mark.asyncio
async def test_repair_extension_rejects_unbounded_or_unscoped_requests(db: AsyncSession) -> None:
    run = await _run(db)
    with pytest.raises(RepairBudgetExtensionError):
        await grant_live_canary_repair_extension(
            db, run, amount=Decimal("2.00"), reason="too much", artifact_ids=["asset"],
        )
    with pytest.raises(RepairBudgetExtensionError):
        await grant_live_canary_repair_extension(
            db, run, amount=Decimal("1.00"), reason="", artifact_ids=[],
        )


def test_reference_budget_safety_uses_the_audited_effective_maximum() -> None:
    assert reference_budget_plan_is_safe({
        "blocker_codes": [],
        "budget": {"projected_total_rmb": "11.00", "maximum_rmb": "11.00"},
    })
    assert not reference_budget_plan_is_safe({
        "blocker_codes": [],
        "budget": {"projected_total_rmb": "11.01", "maximum_rmb": "11.00"},
    })


def test_scoped_repair_can_reserve_reference_without_replanning_all_existing_media() -> None:
    plan = {
        "blocker_codes": ["provider_binding_not_ready", "projected_budget_exceeded"],
        "budget": {
            "projected_total_rmb": "12.00",
            "maximum_rmb": "11.00",
            "remaining_rmb": "4.00",
        },
    }
    assert not reference_budget_plan_is_safe(plan)
    assert reference_budget_plan_is_safe(
        plan, scoped_repair_reservation_rmb=Decimal("1.00"),
    )
