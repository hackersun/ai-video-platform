"""Commercial customer accounts, reservations, immutable ledger and reconciliation facts."""

from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    event,
)

from app.core.database import Base
from app.core.time_utils import utc_now


class BillingAccount(Base):
    __tablename__ = "billing_accounts"
    __table_args__ = (
        UniqueConstraint("owner_type", "owner_id", name="uq_billing_account_owner"),
        CheckConstraint("reserved_micros >= 0", name="ck_billing_account_reserved_nonnegative"),
        CheckConstraint("active_reservations >= 0", name="ck_billing_account_active_nonnegative"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_type = Column(String(20), nullable=False)
    owner_id = Column(String(36), nullable=False, index=True)
    currency = Column(String(3), nullable=False, default="CNY", server_default="CNY")
    status = Column(String(30), nullable=False, default="active", server_default="active")
    available_micros = Column(BigInteger, nullable=False, default=0, server_default="0")
    reserved_micros = Column(BigInteger, nullable=False, default=0, server_default="0")
    period_spent_micros = Column(BigInteger, nullable=False, default=0, server_default="0")
    period_started_at = Column(DateTime, nullable=False, default=utc_now)
    monthly_quota_micros = Column(BigInteger, nullable=True)
    max_concurrent_jobs = Column(Integer, nullable=False, default=4, server_default="4")
    active_reservations = Column(Integer, nullable=False, default=0, server_default="0")
    pricing_markup_bps = Column(Integer, nullable=False, default=0, server_default="0")
    version = Column(Integer, nullable=False, default=1, server_default="1")
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)


class ProjectBillingBudget(Base):
    __tablename__ = "project_billing_budgets"
    __table_args__ = (
        UniqueConstraint("account_id", "project_id", name="uq_project_billing_budget"),
        CheckConstraint("limit_micros >= 0", name="ck_project_budget_limit_nonnegative"),
        CheckConstraint("spent_micros >= 0", name="ck_project_budget_spent_nonnegative"),
        CheckConstraint("reserved_micros >= 0", name="ck_project_budget_reserved_nonnegative"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    account_id = Column(String(36), ForeignKey("billing_accounts.id", ondelete="RESTRICT"), nullable=False, index=True)
    project_id = Column(String(36), nullable=False, index=True)
    limit_micros = Column(BigInteger, nullable=False)
    spent_micros = Column(BigInteger, nullable=False, default=0, server_default="0")
    reserved_micros = Column(BigInteger, nullable=False, default=0, server_default="0")
    version = Column(Integer, nullable=False, default=1, server_default="1")
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)


class BillingReservation(Base):
    __tablename__ = "billing_reservations"
    __table_args__ = (
        UniqueConstraint("account_id", "idempotency_key", name="uq_billing_reservation_idempotency"),
        UniqueConstraint("provider_operation_id", name="uq_billing_reservation_provider_operation"),
        Index("ix_billing_reservations_account_state", "account_id", "state", "created_at"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    account_id = Column(String(36), ForeignKey("billing_accounts.id", ondelete="RESTRICT"), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    project_id = Column(String(36), nullable=True, index=True)
    provider_operation_id = Column(String(36), nullable=True, index=True)
    provider_task_id = Column(String(200), nullable=True, index=True)
    idempotency_key = Column(String(200), nullable=False)
    state = Column(String(30), nullable=False, default="reserved", server_default="reserved")
    estimated_charge_micros = Column(BigInteger, nullable=False)
    supplier_estimate_micros = Column(BigInteger, nullable=False)
    captured_charge_micros = Column(BigInteger, nullable=False, default=0, server_default="0")
    supplier_actual_micros = Column(BigInteger, nullable=True)
    refunded_micros = Column(BigInteger, nullable=False, default=0, server_default="0")
    markup_bps = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)
    settled_at = Column(DateTime, nullable=True)


class BillingLedgerEntry(Base):
    __tablename__ = "billing_ledger_entries"
    __table_args__ = (
        UniqueConstraint("account_id", "idempotency_key", name="uq_billing_ledger_idempotency"),
        Index("ix_billing_ledger_account_time", "account_id", "created_at"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    account_id = Column(String(36), ForeignKey("billing_accounts.id", ondelete="RESTRICT"), nullable=False, index=True)
    reservation_id = Column(String(36), ForeignKey("billing_reservations.id", ondelete="RESTRICT"), nullable=True, index=True)
    entry_type = Column(String(30), nullable=False)
    idempotency_key = Column(String(220), nullable=False)
    currency = Column(String(3), nullable=False, default="CNY", server_default="CNY")
    amount_micros = Column(BigInteger, nullable=False)
    available_delta_micros = Column(BigInteger, nullable=False)
    reserved_delta_micros = Column(BigInteger, nullable=False)
    available_after_micros = Column(BigInteger, nullable=False)
    reserved_after_micros = Column(BigInteger, nullable=False)
    actor_user_id = Column(String(36), nullable=True)
    reason = Column(String(200), nullable=False)
    entry_metadata = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=utc_now)


class UsageEvent(Base):
    __tablename__ = "usage_events"
    __table_args__ = (
        UniqueConstraint("reservation_id", name="uq_usage_event_reservation"),
        Index("ix_usage_events_account_time", "account_id", "created_at"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    account_id = Column(String(36), ForeignKey("billing_accounts.id", ondelete="RESTRICT"), nullable=False, index=True)
    reservation_id = Column(String(36), ForeignKey("billing_reservations.id", ondelete="RESTRICT"), nullable=False)
    user_id = Column(String(36), nullable=False, index=True)
    project_id = Column(String(36), nullable=True, index=True)
    task_type = Column(String(80), nullable=False)
    model_id = Column(String(160), nullable=True)
    provider_id = Column(String(80), nullable=True)
    provider_task_id = Column(String(200), nullable=True, index=True)
    usage_dimensions = Column(JSON, nullable=False, default=dict)
    supplier_cost_micros = Column(BigInteger, nullable=True)
    customer_charge_micros = Column(BigInteger, nullable=False)
    gross_margin_micros = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)


class ProviderReconciliation(Base):
    __tablename__ = "provider_reconciliations"
    __table_args__ = (
        UniqueConstraint("reservation_id", "bill_reference", name="uq_provider_reconciliation_bill"),
        Index("ix_provider_reconciliations_account_status", "account_id", "status", "created_at"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    account_id = Column(String(36), ForeignKey("billing_accounts.id", ondelete="RESTRICT"), nullable=False, index=True)
    reservation_id = Column(String(36), ForeignKey("billing_reservations.id", ondelete="RESTRICT"), nullable=False)
    usage_event_id = Column(String(36), ForeignKey("usage_events.id", ondelete="RESTRICT"), nullable=True)
    provider_task_id = Column(String(200), nullable=True, index=True)
    bill_reference = Column(String(200), nullable=False)
    internal_supplier_cost_micros = Column(BigInteger, nullable=True)
    billed_supplier_cost_micros = Column(BigInteger, nullable=True)
    difference_micros = Column(BigInteger, nullable=True)
    status = Column(String(30), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)


@event.listens_for(BillingLedgerEntry, "before_update")
@event.listens_for(BillingLedgerEntry, "before_delete")
@event.listens_for(UsageEvent, "before_update")
@event.listens_for(UsageEvent, "before_delete")
@event.listens_for(ProviderReconciliation, "before_update")
@event.listens_for(ProviderReconciliation, "before_delete")
def _reject_financial_fact_mutation(_mapper, _connection, _target) -> None:
    raise RuntimeError("财务事实不可修改或删除")
