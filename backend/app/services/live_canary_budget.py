"""Fail-closed model binding and RMB reservation rules for live canaries."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from uuid import uuid4

from app.models.series_production_run import SeriesProductionRun
from app.models.live_canary_provider_operation import LiveCanaryProviderOperation
from app.services.live_canary_bindings import (
    CAPABILITIES,
    BindingValidationError,
    required_tested_at_for_run,
    validate_model_bindings,
    validate_required_model_bindings,
)
from app.services.live_canary_policy import (
    InvalidAccountingInput,
    money as _money,
    money_text as _text,
    trusted_live_canary_policy,
)
from app.services.live_canary_repair_budget import effective_budget_maximum


class BudgetExceeded(ValueError):
    pass


def _reservation_id(value: str) -> str:
    normalized = str(value).strip()
    if not 1 <= len(normalized) <= 200:
        raise InvalidAccountingInput("reservation id length must be 1..200")
    return normalized


def _summary(run: SeriesProductionRun) -> dict[str, Any]:
    summary = dict(run.cost_summary or {})
    summary.setdefault("spent_rmb", "0.00")
    summary.setdefault("reserved_rmb", "0.00")
    summary["reservations"] = dict(summary.get("reservations") or {})
    return summary


async def _persist(db: AsyncSession, run: SeriesProductionRun, summary: dict[str, Any], *, commit: bool = True) -> None:
    run.cost_summary = summary
    flag_modified(run, "cost_summary")
    if commit:
        await db.commit()
    else:
        await db.flush()


async def reserve_budget(
    db: AsyncSession, run: SeriesProductionRun, *, reservation_id: str, estimate_rmb: Decimal,
    commit: bool = True,
) -> dict[str, Any]:
    summary = _summary(run)
    reservations = summary["reservations"]
    reservation_id = _reservation_id(reservation_id)
    existing = reservations.get(reservation_id)
    estimate = _money(estimate_rmb, positive=True)
    if existing is not None:
        if existing.get("state") != "reserved" or existing.get("estimate_rmb") != _text(estimate):
            raise InvalidAccountingInput("reservation id is terminal or has a different estimate")
        return dict(existing)
    if (run.budget_policy or {}).get("blocked"):
        raise BudgetExceeded("series run budget is blocked")
    spent = _money(summary["spent_rmb"])
    reserved = _money(summary["reserved_rmb"])
    maximum = effective_budget_maximum(run)
    if spent + reserved + estimate > maximum:
        raise BudgetExceeded("series run RMB budget would be exceeded")
    reservation = {"estimate_rmb": _text(estimate), "state": "reserved"}
    reservations[reservation_id] = reservation
    summary["reserved_rmb"] = _text(reserved + estimate)
    await _persist(db, run, summary, commit=commit)
    return dict(reservation)


async def prepare_provider_operation(
    db: AsyncSession,
    run: SeriesProductionRun,
    *,
    capability: str,
    job_type: str,
    job_id: str,
    reservation_id: str,
    estimate_rmb: Decimal,
) -> LiveCanaryProviderOperation:
    """Atomically persist reservation and recoverable operation before provider submission."""
    await reserve_budget(
        db, run, reservation_id=reservation_id, estimate_rmb=estimate_rmb, commit=False
    )
    summary = _summary(run)
    reservation = summary["reservations"][_reservation_id(reservation_id)]
    reservation.update(job_id=str(job_id), job_type=str(job_type), capability=str(capability), provider_task_id=None)
    run.cost_summary = summary
    flag_modified(run, "cost_summary")
    operation = LiveCanaryProviderOperation(
        id=str(uuid4()), run_id=run.id, user_id=run.user_id,
        reservation_id=_reservation_id(reservation_id), capability=str(capability),
        job_type=str(job_type), job_id=str(job_id), provider_task_id=None, status="reserved",
    )
    reservation["operation_id"] = operation.id
    run.cost_summary = summary
    flag_modified(run, "cost_summary")
    db.add(operation)
    await db.commit()
    await db.refresh(operation)
    return operation


async def bind_provider_operation_for_reservation(
    db: AsyncSession, run: SeriesProductionRun, *, reservation_id: str, provider_task_id: str
) -> LiveCanaryProviderOperation:
    operation = await db.scalar(select(LiveCanaryProviderOperation).where(
        LiveCanaryProviderOperation.run_id == run.id,
        LiveCanaryProviderOperation.reservation_id == _reservation_id(reservation_id),
    ))
    if operation is None:
        raise InvalidAccountingInput("provider operation is missing")
    return await bind_provider_operation_task(db, operation, provider_task_id=provider_task_id)


async def mark_provider_operation_confirmed_reject(
    db: AsyncSession, run: SeriesProductionRun, *, reservation_id: str
) -> None:
    operation = await db.scalar(select(LiveCanaryProviderOperation).where(
        LiveCanaryProviderOperation.run_id == run.id,
        LiveCanaryProviderOperation.reservation_id == _reservation_id(reservation_id),
    ))
    if operation is None:
        raise InvalidAccountingInput("provider operation is missing")
    operation.status = "confirmed_rejected_before_acceptance"
    await db.commit()


async def settle_confirmed_provider_rejection(
    db: AsyncSession, run: SeriesProductionRun, *, reservation_id: str
) -> None:
    """Atomically close an operation explicitly rejected before provider acceptance."""
    operation = await db.scalar(select(LiveCanaryProviderOperation).where(
        LiveCanaryProviderOperation.run_id == run.id,
        LiveCanaryProviderOperation.reservation_id == _reservation_id(reservation_id),
    ))
    summary = _summary(run)
    reservation = summary["reservations"].get(_reservation_id(reservation_id))
    if operation is None or reservation is None:
        raise InvalidAccountingInput("provider operation accounting is missing")
    if operation.status == "confirmed_rejected_before_acceptance":
        return
    if operation.provider_task_id is not None or reservation.get("state") != "reserved":
        raise InvalidAccountingInput("confirmed rejection requires an unaccepted reserved operation")
    estimate = _money(reservation["estimate_rmb"])
    summary["reserved_rmb"] = _text(_money(summary["reserved_rmb"]) - estimate)
    reservation["state"] = "confirmed_rejected_before_acceptance"
    run.cost_summary = summary
    flag_modified(run, "cost_summary")
    operation.status = "confirmed_rejected_before_acceptance"
    await db.commit()


async def bind_provider_operation_task(
    db: AsyncSession, operation: LiveCanaryProviderOperation, *, provider_task_id: str
) -> LiveCanaryProviderOperation:
    task_id = str(provider_task_id).strip()
    if not task_id:
        raise InvalidAccountingInput("provider task id is required")
    if operation.provider_task_id not in (None, task_id):
        raise InvalidAccountingInput("provider operation task is already bound")
    if operation.provider_task_id is None:
        run = await db.get(SeriesProductionRun, operation.run_id)
        if run is None:
            raise InvalidAccountingInput("provider operation run is missing")
        summary = _summary(run)
        reservation = summary["reservations"].get(operation.reservation_id)
        if reservation is None:
            raise InvalidAccountingInput("provider operation reservation is missing")
        reservation["provider_task_id"] = task_id
        run.cost_summary = summary
        flag_modified(run, "cost_summary")
        operation.provider_task_id = task_id
        operation.status = "accepted"
        await db.commit()
    return operation


async def settle_provider_operation(
    db: AsyncSession,
    *,
    operation_id: str,
    user_id: str,
    run_id: str,
    reservation_id: str,
    capability: str,
    job_id: str,
    provider_task_id: str,
    provider_status: str,
    actual_rmb: Any = None,
) -> None:
    operation = await db.scalar(select(LiveCanaryProviderOperation).where(
        LiveCanaryProviderOperation.id == operation_id,
        LiveCanaryProviderOperation.user_id == user_id,
    ))
    if operation is None:
        raise InvalidAccountingInput("provider operation is missing")
    expected = (operation.run_id, operation.reservation_id, operation.capability, operation.job_id, operation.provider_task_id)
    supplied = (run_id, reservation_id, capability, job_id, provider_task_id)
    if expected != supplied:
        raise InvalidAccountingInput("provider operation accounting mismatch")
    run = await db.get(SeriesProductionRun, run_id)
    summary = _summary(run) if run else {}
    reservation = (summary.get("reservations") or {}).get(reservation_id)
    if run is None or reservation is None:
        raise InvalidAccountingInput("provider operation reservation is missing")
    reservation_expected = (
        reservation.get("job_id"), reservation.get("capability"), reservation.get("provider_task_id")
    )
    if reservation_expected != (job_id, capability, provider_task_id):
        raise InvalidAccountingInput("reservation accounting mismatch")
    if operation.status in {"reconciled", "provider_failed_released"}:
        return
    if provider_status in {"succeeded", "completed"}:
        if actual_rmb is None:
            actual_rmb = reservation["estimate_rmb"]
            reservation["provider_cost_missing"] = True
            operation.cost_source = "estimated_as_actual"
        await reconcile_reservation(db, run, reservation_id=reservation_id, actual_rmb=Decimal(str(actual_rmb)))
        operation.status = "reconciled"
        operation.actual_rmb = _text(_money(actual_rmb))
        await db.commit()
    elif provider_status in {"failed", "rejected", "cancelled"}:
        estimate = _money(reservation["estimate_rmb"])
        summary["reserved_rmb"] = _text(_money(summary["reserved_rmb"]) - estimate)
        reservation["state"] = "provider_failed_released"
        run.cost_summary = summary
        flag_modified(run, "cost_summary")
        operation.status = "provider_failed_released"
        await db.commit()


async def settle_synchronous_provider_operation(
    db: AsyncSession,
    operation: LiveCanaryProviderOperation,
    *,
    provider_actual_rmb: Any = None,
) -> None:
    """Terminal synchronous success: conservatively use the reserved estimate when cost is absent."""
    run = await db.get(SeriesProductionRun, operation.run_id)
    if run is None:
        raise InvalidAccountingInput("provider operation run is missing")
    summary = _summary(run)
    reservation = summary["reservations"].get(operation.reservation_id)
    if reservation is None or not operation.provider_task_id:
        raise InvalidAccountingInput("provider operation is not accepted and linked")
    actual = provider_actual_rmb
    source = "provider_actual"
    if actual is None:
        actual = reservation["estimate_rmb"]
        source = "estimated_as_actual"
        reservation["provider_cost_missing"] = True
        run.cost_summary = summary
        flag_modified(run, "cost_summary")
    await settle_provider_operation(
        db, operation_id=operation.id, user_id=operation.user_id,
        run_id=operation.run_id, reservation_id=operation.reservation_id,
        capability=operation.capability, job_id=operation.job_id,
        provider_task_id=operation.provider_task_id, provider_status="succeeded",
        actual_rmb=actual,
    )
    operation.cost_source = source
    await db.commit()


async def mark_operation_manual_reconcile(
    db: AsyncSession,
    operation: LiveCanaryProviderOperation,
    *,
    reason: str,
) -> None:
    """Fail-closed recovery for providers that cannot look up an unbound idempotent attempt."""
    if operation.status in {"reconciled", "provider_failed_released"}:
        return
    run = await db.get(SeriesProductionRun, operation.run_id)
    if run is None:
        raise InvalidAccountingInput("provider operation run is missing")
    operation.status = "unknown_manual_reconcile"
    operation.recovery_reason = str(reason)[:100]
    policy = dict(run.budget_policy or {})
    policy.update(blocked=True, blocked_reason="unknown_manual_reconcile")
    run.budget_policy = policy
    flag_modified(run, "budget_policy")
    await db.commit()


async def recover_provider_operations(
    db: AsyncSession,
    *,
    adapters: Mapping[str, Any],
    user_id: str | None = None,
    stale_before: datetime | None = None,
) -> dict[str, Any]:
    """Recover pre-submit/unknown operations using provider-supported lookup/status adapters."""
    query = select(LiveCanaryProviderOperation).where(
        LiveCanaryProviderOperation.status.in_(("reserved", "accepted", "unknown"))
    )
    if user_id:
        query = query.where(LiveCanaryProviderOperation.user_id == user_id)
    if stale_before is not None:
        query = query.where(LiveCanaryProviderOperation.updated_at <= _naive_utc(stale_before))
    operations = list((await db.scalars(query)).all())
    manifest = {"scanned": len(operations), "settled": [], "bound": [], "manual": []}
    for operation in operations:
        adapter = adapters.get(operation.capability)
        if adapter is None:
            await mark_operation_manual_reconcile(db, operation, reason="status_adapter_unavailable")
            manifest["manual"].append(operation.id)
            continue
        if not operation.provider_task_id:
            lookup = getattr(adapter, "lookup_by_idempotency_key", None)
            if lookup is None:
                await mark_operation_manual_reconcile(db, operation, reason="provider_lookup_unsupported")
                manifest["manual"].append(operation.id)
                continue
            task_id = await lookup(operation.id)
            if not task_id:
                await mark_operation_manual_reconcile(db, operation, reason="provider_task_not_found")
                manifest["manual"].append(operation.id)
                continue
            await bind_provider_operation_task(db, operation, provider_task_id=str(task_id))
            manifest["bound"].append(operation.id)
        observed = await adapter.get_status(operation.provider_task_id)
        await settle_provider_operation(
            db, operation_id=operation.id, user_id=operation.user_id,
            run_id=operation.run_id, reservation_id=operation.reservation_id,
            capability=operation.capability, job_id=operation.job_id,
            provider_task_id=operation.provider_task_id,
            provider_status=str(observed.get("status") or "unknown"),
            actual_rmb=observed.get("actual_cost_rmb", observed.get("cost_rmb")),
        )
        if operation.status in {"reconciled", "provider_failed_released"}:
            manifest["settled"].append(operation.id)
    for key in ("settled", "bound", "manual"):
        manifest[key].sort()
    return manifest


async def reconcile_reservation(
    db: AsyncSession, run: SeriesProductionRun, *, reservation_id: str, actual_rmb: Decimal
) -> dict[str, Any]:
    summary = _summary(run)
    reservation_id = _reservation_id(reservation_id)
    reservation = summary["reservations"].get(reservation_id)
    if reservation is None:
        raise InvalidAccountingInput("unknown reservation id")
    actual = _money(actual_rmb)
    if reservation.get("state") == "reconciled":
        if reservation.get("actual_rmb") != _text(actual):
            raise InvalidAccountingInput("reservation already reconciled with different actual cost")
        return dict(reservation)
    if reservation.get("state") != "reserved":
        raise InvalidAccountingInput("only a reserved item can be reconciled")
    estimate = _money(reservation["estimate_rmb"])
    summary["reserved_rmb"] = _text(_money(summary["reserved_rmb"]) - estimate)
    summary["spent_rmb"] = _text(_money(summary["spent_rmb"]) + actual)
    total = _money(summary["spent_rmb"]) + _money(summary["reserved_rmb"])
    maximum = effective_budget_maximum(run)
    state = "reconciled"
    if total > maximum:
        state = "reconciled_over_budget"
        policy = dict(run.budget_policy or {})
        policy.update(blocked=True, overage_rmb=_text(total - maximum))
        run.budget_policy = policy
        flag_modified(run, "budget_policy")
    reservation.update(state=state, actual_rmb=_text(actual))
    await _persist(db, run, summary)
    return dict(reservation)


async def release_reservation(
    db: AsyncSession, run: SeriesProductionRun, *, reservation_id: str, provider_state: str
) -> dict[str, Any]:
    summary = _summary(run)
    reservation_id = _reservation_id(reservation_id)
    reservation = summary["reservations"].get(reservation_id)
    if reservation is None:
        raise InvalidAccountingInput("unknown reservation id")
    if provider_state == "unknown" or reservation.get("state") == "released":
        return dict(reservation)
    if provider_state != "submission_failed":
        raise InvalidAccountingInput("release requires a confirmed submission failure")
    if reservation.get("state") != "reserved":
        raise InvalidAccountingInput("only a reserved item can be released")
    estimate = _money(reservation["estimate_rmb"])
    summary["reserved_rmb"] = _text(_money(summary["reserved_rmb"]) - estimate)
    reservation["state"] = "released"
    await _persist(db, run, summary)
    return dict(reservation)


async def link_provider_attempt(
    db: AsyncSession,
    run: SeriesProductionRun,
    *,
    reservation_id: str,
    provider_task_id: str | None,
    job_id: str,
    capability: str,
) -> dict[str, Any]:
    """Persist the recoverable join between a run reservation and server-owned provider job."""
    summary = _summary(run)
    normalized = _reservation_id(reservation_id)
    reservation = summary["reservations"].get(normalized)
    if reservation is None:
        raise InvalidAccountingInput("unknown reservation id")
    linkage = {
        "provider_task_id": str(provider_task_id) if provider_task_id else None,
        "job_id": str(job_id),
        "capability": str(capability),
    }
    existing = {key: reservation.get(key) for key in linkage}
    if any(value is not None for value in existing.values()) and existing != linkage:
        raise InvalidAccountingInput("reservation already linked to another provider attempt")
    reservation.update(linkage)
    await _persist(db, run, summary)
    return dict(reservation)


async def settle_linked_provider_attempt(
    db: AsyncSession,
    *,
    user_id: str,
    accounting: dict[str, Any],
    provider_task_id: str,
    provider_status: str,
    actual_rmb: Any = None,
) -> None:
    """Idempotently settle only from a server-observed provider polling result."""
    run_id = str(accounting.get("series_run_id") or "")
    reservation_id = str(accounting.get("reservation_id") or "")
    if not run_id or not reservation_id or str(accounting.get("provider_task_id") or "") != str(provider_task_id):
        return
    run = await db.scalar(select(SeriesProductionRun).where(
        SeriesProductionRun.id == run_id, SeriesProductionRun.user_id == user_id,
    ))
    if run is None:
        return
    reservation = (_summary(run)["reservations"]).get(reservation_id) or {}
    if reservation.get("state") != "reserved":
        return
    if provider_status in {"succeeded", "completed"} and actual_rmb is not None:
        await reconcile_reservation(db, run, reservation_id=reservation_id, actual_rmb=Decimal(str(actual_rmb)))
    elif provider_status in {"failed", "rejected", "cancelled"}:
        await release_reservation(db, run, reservation_id=reservation_id, provider_state="submission_failed")


def _naive_utc(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value
