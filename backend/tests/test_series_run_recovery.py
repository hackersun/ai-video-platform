from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.database import AsyncSessionLocal
from app.features.series_run_recovery import recovery_for_operation
from app.models.live_canary_provider_operation import LiveCanaryProviderOperation
from app.models.novel import Novel
from app.models.series_production_run import SeriesProductionRun
from init_db import init_db
from main import app


@pytest.fixture(scope="module", autouse=True)
def _database() -> None:
    init_db()


def _operation(status: str, capability: str = "tts") -> SimpleNamespace:
    return SimpleNamespace(
        id="operation-1",
        status=status,
        capability=capability,
        job_id="job-1",
        provider_task_id=None,
        actual_rmb=None,
        cost_source=None,
        recovery_reason=None,
    )


@pytest_asyncio.fixture
async def recovery_api_records():
    owner, other = f"recovery-owner-{uuid4()}", f"recovery-other-{uuid4()}"
    novel_id, run_id, operation_id = str(uuid4()), str(uuid4()), str(uuid4())
    async with AsyncSessionLocal() as db:
        db.add(Novel(id=novel_id, user_id=owner, title="恢复测试小说"))
        db.add(SeriesProductionRun(
            id=run_id, user_id=owner, novel_id=novel_id, series_plan_version="v1",
            idempotency_key=str(uuid4()), requested_stages=[], model_bindings={},
            budget_policy={}, cost_summary={}, gate_summary={},
            run_metadata={"reference_preparation": {"asset_id": "reference-1"}}, episodes=[],
        ))
        db.add(LiveCanaryProviderOperation(
            id=operation_id, run_id=run_id, user_id=owner, reservation_id=str(uuid4()),
            capability="tts", job_type="tts_job", job_id="job-1",
            status="confirmed_rejected_before_acceptance",
        ))
        await db.commit()
    yield owner, other, run_id, operation_id
    async with AsyncSessionLocal() as db:
        await db.execute(delete(LiveCanaryProviderOperation).where(LiveCanaryProviderOperation.id == operation_id))
        await db.execute(delete(SeriesProductionRun).where(SeriesProductionRun.id == run_id))
        await db.execute(delete(Novel).where(Novel.id == novel_id))
        await db.commit()


def test_confirmed_rejection_allows_failed_stage_retry() -> None:
    descriptor = recovery_for_operation(_operation("confirmed_rejected_before_acceptance"))

    assert descriptor.safe_retry is True
    assert descriptor.cost_state == "released"
    assert descriptor.retry_scope == "failed_stage"
    assert {item.code for item in descriptor.actions} >= {
        "edit_voice", "retest_config", "retry_failed_stage",
    }


@pytest.mark.parametrize("status", ["accepted", "reserved", "unknown_manual_reconcile"])
def test_uncertain_operation_never_offers_resubmit(status: str) -> None:
    descriptor = recovery_for_operation(_operation(status, capability="video"))

    assert descriptor.safe_retry is False
    assert {item.code for item in descriptor.actions} <= {
        "refresh_status", "manual_reconcile",
    }


def test_succeeded_operation_has_no_recovery_action() -> None:
    descriptor = recovery_for_operation(_operation("succeeded", capability="image"))

    assert descriptor.safe_retry is False
    assert descriptor.actions == ()


@pytest.mark.asyncio
async def test_recovery_api_is_owner_scoped_and_rejects_stale_run_version(recovery_api_records) -> None:
    owner, other, run_id, operation_id = recovery_api_records
    client = TestClient(app)
    owner_headers, other_headers = {"Authorization": f"Bearer {owner}"}, {"Authorization": f"Bearer {other}"}
    recovery = client.get(f"/api/v1/series-runs/{run_id}/recovery", headers=owner_headers)
    assert recovery.status_code == 200
    assert recovery.json()["preserved_artifacts"] == [{
        "kind": "reference_image", "asset_id": "reference-1",
        "message": "参考图已锁定，不会重新生成",
    }]
    assert client.get(f"/api/v1/series-runs/{run_id}/recovery", headers=other_headers).status_code == 404

    version = recovery.json()["run_version"]
    stale = client.post(
        f"/api/v1/series-runs/{run_id}/recovery/actions/retry_failed_stage",
        headers=owner_headers,
        json={"operation_id": operation_id, "expected_run_version": version + 1},
    )
    assert stale.status_code == 409
    accepted = client.post(
        f"/api/v1/series-runs/{run_id}/recovery/actions/retry_failed_stage",
        headers=owner_headers,
        json={"operation_id": operation_id, "expected_run_version": version},
    )
    assert accepted.status_code == 200
    assert accepted.json()["requires_provider_submission"] is False

    async with AsyncSessionLocal() as db:
        operation = await db.get(LiveCanaryProviderOperation, operation_id)
        assert operation.status == "confirmed_rejected_before_acceptance"
