"""R03: per-user billing settings and immutable-ish spend ledger."""

from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, Index, String, Text, UniqueConstraint

from app.core.database import Base
from app.core.time_utils import utc_now


class UserBillingSettings(Base):
    __tablename__ = "user_billing_settings"

    user_id = Column(String(36), primary_key=True)
    live_calls_opt_in = Column(Boolean, nullable=False, default=False)
    opted_in_at = Column(DateTime, nullable=True)
    # Decimal amounts stored as text for Decimal fidelity (same pattern as cost_summary).
    per_user_cap_rmb = Column(String(50), nullable=False)
    per_pipeline_cap_rmb = Column(String(50), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)


class BillingLedgerEntry(Base):
    __tablename__ = "billing_ledger"
    __table_args__ = (
        UniqueConstraint("user_id", "reservation_id", name="uq_billing_ledger_user_reservation"),
        Index("ix_billing_ledger_user_status", "user_id", "status"),
        Index("ix_billing_ledger_pipeline", "pipeline_id"),
        Index("ix_billing_ledger_series_run", "series_run_id"),
    )

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    novel_id = Column(String(36), nullable=True, index=True)
    pipeline_id = Column(String(36), nullable=True)
    series_run_id = Column(String(36), nullable=True)
    provider = Column(String(80), nullable=True)
    model = Column(String(120), nullable=True)
    capability = Column(String(40), nullable=True)
    units = Column(String(50), nullable=True)
    estimated_cost_rmb = Column(String(50), nullable=False, default="0.00")
    actual_cost_rmb = Column(String(50), nullable=True)
    status = Column(String(30), nullable=False, index=True)  # reserved|settled|released|blocked_cap
    reservation_id = Column(String(200), nullable=False)
    is_fake = Column(Boolean, nullable=False, default=False)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)
