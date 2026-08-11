"""Add durable task executions and append-only events.

Revision ID: 20260809_0004
Revises: 20260809_0003
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa


revision = "20260809_0004"
down_revision = "20260809_0003"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    tables = _table_names()
    if "task_executions" not in tables:
        op.create_table(
            "task_executions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), nullable=False),
            sa.Column("project_id", sa.String(36), nullable=True),
            sa.Column("task_type", sa.String(80), nullable=False),
            sa.Column("idempotency_key", sa.String(200), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
            sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("next_attempt_at", sa.DateTime(), nullable=False),
            sa.Column("lease_owner", sa.String(100), nullable=True),
            sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
            sa.Column("heartbeat_at", sa.DateTime(), nullable=True),
            sa.Column("provider_task_id", sa.String(160), nullable=True),
            sa.Column("result_summary", sa.JSON(), nullable=False),
            sa.Column("last_error_code", sa.String(80), nullable=True),
            sa.Column("last_error_message", sa.Text(), nullable=True),
            sa.Column("cancel_requested_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint(
                "user_id", "task_type", "idempotency_key", name="uq_task_execution_idempotency"
            ),
        )
        op.create_index("ix_task_executions_user_id", "task_executions", ["user_id"])
        op.create_index("ix_task_executions_project_id", "task_executions", ["project_id"])
        op.create_index("ix_task_executions_task_type", "task_executions", ["task_type"])
        op.create_index("ix_task_executions_provider_task_id", "task_executions", ["provider_task_id"])
        op.create_index(
            "ix_task_executions_claim",
            "task_executions",
            ["status", "next_attempt_at", "priority", "created_at"],
        )
        op.create_index(
            "ix_task_executions_user_status",
            "task_executions",
            ["user_id", "status", "created_at"],
        )
    tables = _table_names()
    if "task_execution_events" not in tables:
        op.create_table(
            "task_execution_events",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "execution_id",
                sa.String(36),
                sa.ForeignKey("task_executions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("event_type", sa.String(40), nullable=False),
            sa.Column("status", sa.String(24), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("details", sa.JSON(), nullable=False),
            sa.Column("worker_id", sa.String(100), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index(
            "ix_task_execution_events_execution_id", "task_execution_events", ["execution_id"]
        )
        op.create_index(
            "ix_task_execution_events_execution_time",
            "task_execution_events",
            ["execution_id", "created_at"],
        )
    _create_event_immutability_guard()


def _create_event_immutability_guard() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE OR REPLACE FUNCTION reject_task_execution_event_mutation()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'task execution events are append-only';
            END;
            $$ LANGUAGE plpgsql
            """
        )
        op.execute("DROP TRIGGER IF EXISTS trg_task_execution_events_append_only ON task_execution_events")
        op.execute(
            """
            CREATE TRIGGER trg_task_execution_events_append_only
            BEFORE UPDATE OR DELETE ON task_execution_events
            FOR EACH ROW EXECUTE FUNCTION reject_task_execution_event_mutation()
            """
        )
        return
    if op.get_bind().dialect.name == "sqlite":
        for operation in ("UPDATE", "DELETE"):
            trigger = f"trg_task_execution_events_no_{operation.lower()}"
            op.execute(f"DROP TRIGGER IF EXISTS {trigger}")
            op.execute(
                f"""
                CREATE TRIGGER {trigger}
                BEFORE {operation} ON task_execution_events
                BEGIN
                    SELECT RAISE(ABORT, 'task execution events are append-only');
                END
                """
            )


def downgrade() -> None:
    raise RuntimeError("持久任务迁移不可安全降级；请恢复迁移前备份")
