"""Add customer billing accounts, reservations and append-only facts.

Revision ID: 20260809_0005
Revises: 20260809_0004
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa


revision = "20260809_0005"
down_revision = "20260809_0004"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    tables = _table_names()
    if "billing_accounts" not in tables:
        op.create_table(
            "billing_accounts",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("owner_type", sa.String(20), nullable=False),
            sa.Column("owner_id", sa.String(36), nullable=False),
            sa.Column("currency", sa.String(3), nullable=False, server_default="CNY"),
            sa.Column("status", sa.String(30), nullable=False, server_default="active"),
            sa.Column("available_micros", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("reserved_micros", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("period_spent_micros", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("period_started_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("monthly_quota_micros", sa.BigInteger(), nullable=True),
            sa.Column("max_concurrent_jobs", sa.Integer(), nullable=False, server_default="4"),
            sa.Column("active_reservations", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("pricing_markup_bps", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.CheckConstraint("reserved_micros >= 0", name="ck_billing_account_reserved_nonnegative"),
            sa.CheckConstraint("active_reservations >= 0", name="ck_billing_account_active_nonnegative"),
            sa.UniqueConstraint("owner_type", "owner_id", name="uq_billing_account_owner"),
        )
        op.create_index("ix_billing_accounts_owner_id", "billing_accounts", ["owner_id"])
    if "project_billing_budgets" not in tables:
        op.create_table(
            "project_billing_budgets",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("account_id", sa.String(36), sa.ForeignKey("billing_accounts.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("project_id", sa.String(36), nullable=False),
            sa.Column("limit_micros", sa.BigInteger(), nullable=False),
            sa.Column("spent_micros", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("reserved_micros", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.CheckConstraint("limit_micros >= 0", name="ck_project_budget_limit_nonnegative"),
            sa.CheckConstraint("spent_micros >= 0", name="ck_project_budget_spent_nonnegative"),
            sa.CheckConstraint("reserved_micros >= 0", name="ck_project_budget_reserved_nonnegative"),
            sa.UniqueConstraint("account_id", "project_id", name="uq_project_billing_budget"),
        )
        op.create_index("ix_project_billing_budgets_account_id", "project_billing_budgets", ["account_id"])
        op.create_index("ix_project_billing_budgets_project_id", "project_billing_budgets", ["project_id"])
    if "billing_reservations" not in tables:
        op.create_table(
            "billing_reservations",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("account_id", sa.String(36), sa.ForeignKey("billing_accounts.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("user_id", sa.String(36), nullable=False),
            sa.Column("project_id", sa.String(36), nullable=True),
            sa.Column("provider_operation_id", sa.String(36), nullable=True),
            sa.Column("provider_task_id", sa.String(200), nullable=True),
            sa.Column("idempotency_key", sa.String(200), nullable=False),
            sa.Column("state", sa.String(30), nullable=False, server_default="reserved"),
            sa.Column("estimated_charge_micros", sa.BigInteger(), nullable=False),
            sa.Column("supplier_estimate_micros", sa.BigInteger(), nullable=False),
            sa.Column("captured_charge_micros", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("supplier_actual_micros", sa.BigInteger(), nullable=True),
            sa.Column("refunded_micros", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("markup_bps", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("settled_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("account_id", "idempotency_key", name="uq_billing_reservation_idempotency"),
            sa.UniqueConstraint("provider_operation_id", name="uq_billing_reservation_provider_operation"),
        )
        for column in ("account_id", "user_id", "project_id", "provider_operation_id", "provider_task_id"):
            op.create_index(f"ix_billing_reservations_{column}", "billing_reservations", [column])
        op.create_index("ix_billing_reservations_account_state", "billing_reservations", ["account_id", "state", "created_at"])
    _create_financial_fact_tables()
    _create_immutability_guards()


def _create_financial_fact_tables() -> None:
    tables = _table_names()
    if "billing_ledger_entries" not in tables:
        op.create_table(
            "billing_ledger_entries",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("account_id", sa.String(36), sa.ForeignKey("billing_accounts.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("reservation_id", sa.String(36), sa.ForeignKey("billing_reservations.id", ondelete="RESTRICT"), nullable=True),
            sa.Column("entry_type", sa.String(30), nullable=False),
            sa.Column("idempotency_key", sa.String(220), nullable=False),
            sa.Column("currency", sa.String(3), nullable=False, server_default="CNY"),
            sa.Column("amount_micros", sa.BigInteger(), nullable=False),
            sa.Column("available_delta_micros", sa.BigInteger(), nullable=False),
            sa.Column("reserved_delta_micros", sa.BigInteger(), nullable=False),
            sa.Column("available_after_micros", sa.BigInteger(), nullable=False),
            sa.Column("reserved_after_micros", sa.BigInteger(), nullable=False),
            sa.Column("actor_user_id", sa.String(36), nullable=True),
            sa.Column("reason", sa.String(200), nullable=False),
            sa.Column("entry_metadata", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("account_id", "idempotency_key", name="uq_billing_ledger_idempotency"),
        )
        op.create_index("ix_billing_ledger_entries_account_id", "billing_ledger_entries", ["account_id"])
        op.create_index("ix_billing_ledger_entries_reservation_id", "billing_ledger_entries", ["reservation_id"])
        op.create_index("ix_billing_ledger_account_time", "billing_ledger_entries", ["account_id", "created_at"])
    if "usage_events" not in tables:
        op.create_table(
            "usage_events",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("account_id", sa.String(36), sa.ForeignKey("billing_accounts.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("reservation_id", sa.String(36), sa.ForeignKey("billing_reservations.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("user_id", sa.String(36), nullable=False),
            sa.Column("project_id", sa.String(36), nullable=True),
            sa.Column("task_type", sa.String(80), nullable=False),
            sa.Column("model_id", sa.String(160), nullable=True),
            sa.Column("provider_id", sa.String(80), nullable=True),
            sa.Column("provider_task_id", sa.String(200), nullable=True),
            sa.Column("usage_dimensions", sa.JSON(), nullable=False),
            sa.Column("supplier_cost_micros", sa.BigInteger(), nullable=True),
            sa.Column("customer_charge_micros", sa.BigInteger(), nullable=False),
            sa.Column("gross_margin_micros", sa.BigInteger(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("reservation_id", name="uq_usage_event_reservation"),
        )
        for column in ("account_id", "user_id", "project_id", "provider_task_id"):
            op.create_index(f"ix_usage_events_{column}", "usage_events", [column])
        op.create_index("ix_usage_events_account_time", "usage_events", ["account_id", "created_at"])
    if "provider_reconciliations" not in tables:
        op.create_table(
            "provider_reconciliations",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("account_id", sa.String(36), sa.ForeignKey("billing_accounts.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("reservation_id", sa.String(36), sa.ForeignKey("billing_reservations.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("usage_event_id", sa.String(36), sa.ForeignKey("usage_events.id", ondelete="RESTRICT"), nullable=True),
            sa.Column("provider_task_id", sa.String(200), nullable=True),
            sa.Column("bill_reference", sa.String(200), nullable=False),
            sa.Column("internal_supplier_cost_micros", sa.BigInteger(), nullable=True),
            sa.Column("billed_supplier_cost_micros", sa.BigInteger(), nullable=True),
            sa.Column("difference_micros", sa.BigInteger(), nullable=True),
            sa.Column("status", sa.String(30), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("reservation_id", "bill_reference", name="uq_provider_reconciliation_bill"),
        )
        for column in ("account_id", "provider_task_id"):
            op.create_index(f"ix_provider_reconciliations_{column}", "provider_reconciliations", [column])
        op.create_index("ix_provider_reconciliations_account_status", "provider_reconciliations", ["account_id", "status", "created_at"])


def _create_immutability_guards() -> None:
    tables = ("billing_ledger_entries", "usage_events", "provider_reconciliations")
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("""
            CREATE OR REPLACE FUNCTION reject_financial_fact_mutation()
            RETURNS trigger AS $$ BEGIN
                RAISE EXCEPTION 'financial facts are append-only';
            END; $$ LANGUAGE plpgsql
        """)
        for table in tables:
            trigger = f"trg_{table}_append_only"
            op.execute(f"DROP TRIGGER IF EXISTS {trigger} ON {table}")
            op.execute(f"CREATE TRIGGER {trigger} BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION reject_financial_fact_mutation()")
    elif dialect == "sqlite":
        for table in tables:
            for operation in ("UPDATE", "DELETE"):
                trigger = f"trg_{table}_no_{operation.lower()}"
                op.execute(f"DROP TRIGGER IF EXISTS {trigger}")
                op.execute(f"CREATE TRIGGER {trigger} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT, 'financial facts are append-only'); END")


def downgrade() -> None:
    raise RuntimeError("客户计费迁移不可安全降级；请恢复迁移前备份")
